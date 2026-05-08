import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.histopathology.roi import roi_contains, validate_roi_pair
from app.histopathology.schemas import ROIBox


def parse_roi(value: str) -> ROIBox:
    try:
        x, y, width, height = [int(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "ROI must use the format x,y,width,height"
        ) from exc

    return ROIBox(x=x, y=y, width=width, height=height)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Integration test helper for the histopathology module."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="FastAPI base URL. Default: http://localhost:8001",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Check /api/histopathology/status")

    roi_parser = subparsers.add_parser("roi", help="Run ROI validation locally")
    roi_parser.add_argument("--roi-1", required=True, type=parse_roi)
    roi_parser.add_argument("--roi-2", required=True, type=parse_roi)
    roi_parser.add_argument("--slide-width", required=True, type=int)
    roi_parser.add_argument("--slide-height", required=True, type=int)

    analyze_parser = subparsers.add_parser(
        "analyze", help="Call /api/histopathology/analyze-roi"
    )
    analyze_parser.add_argument("--image-id", required=True, type=int)
    analyze_parser.add_argument("--roi-1", required=True, type=parse_roi)
    analyze_parser.add_argument("--roi-2", required=True, type=parse_roi)

    smoke_parser = subparsers.add_parser(
        "smoke",
        help="Run a small PASS/FAIL smoke suite for the histopathology module",
    )
    smoke_parser.add_argument(
        "--image-id",
        type=int,
        help="Optional image id for end-to-end analyze-roi check",
    )
    smoke_parser.add_argument(
        "--skip-status",
        action="store_true",
        help="Skip the backend status endpoint check",
    )
    smoke_parser.add_argument(
        "--skip-analyze",
        action="store_true",
        help="Skip the analyze-roi endpoint check even if image-id is provided",
    )

    return parser


def run_status(base_url: str) -> int:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{base_url}/api/histopathology/status")

    print(json.dumps(response.json(), indent=2, ensure_ascii=True))
    return 0 if response.is_success else 1


def run_roi_validation(roi_1: ROIBox, roi_2: ROIBox, slide_width: int, slide_height: int) -> int:
    try:
        validate_roi_pair(roi_1, roi_2, slide_width=slide_width, slide_height=slide_height)
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "detail": str(exc),
                    "roi_contains": roi_contains(roi_1, roi_2),
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "detail": "ROI pair is valid",
                "roi_contains": roi_contains(roi_1, roi_2),
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


def run_analyze(base_url: str, image_id: int, roi_1: ROIBox, roi_2: ROIBox) -> int:
    payload = {
        "image_id": image_id,
        "roi_1": roi_1.model_dump(),
        "roi_2": roi_2.model_dump(),
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{base_url}/api/histopathology/analyze-roi",
            json=payload,
        )

    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}

    print(json.dumps(data, indent=2, ensure_ascii=True))
    return 0 if response.is_success else 1


def run_smoke(base_url: str, image_id: int | None, skip_status: bool, skip_analyze: bool) -> int:
    checks = []

    def record(name: str, ok: bool, detail):
        checks.append(
            {
                "name": name,
                "ok": ok,
                "detail": detail,
            }
        )

    valid_roi_1 = ROIBox(x=100, y=100, width=500, height=500)
    valid_roi_2 = ROIBox(x=200, y=220, width=128, height=128)
    invalid_roi_2 = ROIBox(x=520, y=540, width=128, height=128)

    try:
        validate_roi_pair(valid_roi_1, valid_roi_2, slide_width=1000, slide_height=1000)
        record("roi_valid_pair", True, "ROI 2 is correctly contained in ROI 1")
    except ValueError as exc:
        record("roi_valid_pair", False, str(exc))

    try:
        validate_roi_pair(valid_roi_1, invalid_roi_2, slide_width=1000, slide_height=1000)
        record("roi_invalid_pair", False, "Expected a containment error but validation passed")
    except ValueError as exc:
        record("roi_invalid_pair", True, str(exc))

    if not skip_status:
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(f"{base_url}/api/histopathology/status")
            if response.is_success:
                record("backend_status", True, response.json())
            else:
                record("backend_status", False, {"status_code": response.status_code, "body": response.text})
        except Exception as exc:
            record("backend_status", False, str(exc))
    else:
        record("backend_status", True, "Skipped by user")

    if image_id is not None and not skip_analyze:
        try:
            payload = {
                "image_id": image_id,
                "roi_1": {
                    "x": 1000,
                    "y": 1000,
                    "width": 2000,
                    "height": 2000,
                },
                "roi_2": {
                    "x": 1200,
                    "y": 1300,
                    "width": 512,
                    "height": 512,
                },
            }

            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{base_url}/api/histopathology/analyze-roi",
                    json=payload,
                )

            if response.is_success:
                record("analyze_roi", True, response.json())
            else:
                try:
                    detail = response.json()
                except ValueError:
                    detail = response.text
                record("analyze_roi", False, {"status_code": response.status_code, "body": detail})
        except Exception as exc:
            record("analyze_roi", False, str(exc))
    else:
        detail = "Skipped because no image-id was provided" if image_id is None else "Skipped by user"
        record("analyze_roi", True, detail)

    overall_ok = all(check["ok"] for check in checks)
    summary = {
        "overall": "PASS" if overall_ok else "FAIL",
        "checks": checks,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0 if overall_ok else 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        return run_status(args.base_url)

    if args.command == "roi":
        return run_roi_validation(args.roi_1, args.roi_2, args.slide_width, args.slide_height)

    if args.command == "analyze":
        return run_analyze(args.base_url, args.image_id, args.roi_1, args.roi_2)

    if args.command == "smoke":
        return run_smoke(args.base_url, args.image_id, args.skip_status, args.skip_analyze)

    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
