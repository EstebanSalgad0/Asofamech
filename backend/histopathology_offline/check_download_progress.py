"""
Muestra cuantas laminas de la lista de descarga ya estan disponibles localmente.
Corre este script en cualquier momento para ver el progreso.

Uso:
  python check_download_progress.py
  python check_download_progress.py --watch          # refresca cada 60s
  python check_download_progress.py --watch --interval 30
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

IMAGES_DIR = Path(__file__).resolve().parents[1] / "data" / "camelyon17" / "images"
PRIORITY_LIST = Path(__file__).resolve().parents[1] / "data" / "camelyon17" / "download_priority_list.txt"

PRIORITY_LABELS = {
    1: "Positivas centro 3 y 4 (mayor impacto)",
    2: "Negativas centro 3 y 4",
    3: "Positivas centros 0, 1, 2",
    4: "Negativas centros 0, 1, 2",
}


def load_priority_list(path: Path) -> dict[str, int]:
    """Devuelve {filename: priority} desde el archivo de lista."""
    result = {}
    current_priority = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            for priority in (1, 2, 3, 4):
                if f"PRIORIDAD {priority}" in line:
                    current_priority = priority
            continue
        if line.endswith(".tif") and current_priority is not None:
            result[line] = current_priority
    return result


def build_progress(priority_list: dict[str, int]) -> dict[int, dict]:
    present = set(os.listdir(IMAGES_DIR)) if IMAGES_DIR.exists() else set()
    by_priority: dict[int, dict] = {
        priority: {"total": 0, "done": 0, "pending": []}
        for priority in (1, 2, 3, 4)
    }

    for filename, priority in priority_list.items():
        by_priority[priority]["total"] += 1
        if filename in present:
            by_priority[priority]["done"] += 1
        else:
            by_priority[priority]["pending"].append(filename)
    return by_priority


def progress_bar(done: int, total: int, width: int = 24) -> str:
    filled = int(width * done / total) if total else 0
    return "#" * filled + "." * (width - filled)


def check(priority_list: dict[str, int]) -> None:
    by_priority = build_progress(priority_list)
    total = sum(value["total"] for value in by_priority.values())
    done = sum(value["done"] for value in by_priority.values())
    pct = done / total * 100 if total else 0

    print(f"\n{'=' * 56}")
    print("  PROGRESO DE DESCARGA CAMELYON17")
    print(f"  {done}/{total} laminas descargadas  ({pct:.1f}%)")
    print(f"{'=' * 56}")

    for priority in (1, 2, 3, 4):
        data = by_priority[priority]
        p_pct = data["done"] / data["total"] * 100 if data["total"] else 0
        status = "COMPLETO" if data["done"] == data["total"] else f"{data['done']}/{data['total']}"
        print(f"\n  P{priority}: {PRIORITY_LABELS[priority]}")
        print(f"  [{progress_bar(data['done'], data['total'])}] {p_pct:.0f}%  {status}")
        if data["pending"] and priority in (1, 2):
            show = data["pending"][:5]
            remaining = len(data["pending"]) - len(show)
            suffix = f" ... +{remaining}" if remaining > 0 else ""
            print(f"  Proximas: {', '.join(show)}{suffix}")

    if by_priority[1]["done"] == by_priority[1]["total"] and by_priority[1]["total"] > 0:
        print("\n  *** Prioridad 1 lista - puedes correr Stage 14 ***")
        print("  Ver docs/HISTOPATHOLOGY_ROADMAP.md para el flujo Stage 14 reproducible.")

    print(f"\n  Ultima revision: {time.strftime('%H:%M:%S')}")
    print(f"{'=' * 56}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitorea el progreso de descarga de CAMELYON17.")
    parser.add_argument("--watch", action="store_true", help="Refresca automaticamente.")
    parser.add_argument("--interval", type=int, default=60, help="Segundos entre refresco (default: 60).")
    args = parser.parse_args()

    if not PRIORITY_LIST.exists():
        raise SystemExit(
            f"Lista de descarga no encontrada: {PRIORITY_LIST}\n"
            "Recrea backend/data/camelyon17/download_priority_list.txt antes de continuar."
        )

    priority_list = load_priority_list(PRIORITY_LIST)

    if not args.watch:
        check(priority_list)
        return

    print(f"Monitoreando cada {args.interval}s  (Ctrl+C para detener)\n")
    try:
        while True:
            check(priority_list)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nMonitoreo detenido.")


if __name__ == "__main__":
    main()
