import threading
import unittest
from datetime import datetime

from app.histopathology import heatmap_jobs


class HeatmapJobsTestCase(unittest.TestCase):
    def setUp(self):
        with heatmap_jobs._LOCK:
            heatmap_jobs._JOBS.clear()

    def _payload(self, trace_id="trace-test", image_id=1):
        return {
            "trace_id": trace_id,
            "request": {
                "image_id": image_id,
                "roi": {"x": 0, "y": 0, "width": 512, "height": 512},
            },
        }

    def test_create_job_returns_queued_state(self):
        job = heatmap_jobs.create_heatmap_job(self._payload())
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["progress"], 0.0)
        self.assertEqual(job["processed_tiles"], 0)
        self.assertEqual(job["total_tiles"], 0)
        self.assertIsNone(job["result"])
        self.assertIsNone(job["error"])

    def test_create_job_assigns_unique_job_id(self):
        job_a = heatmap_jobs.create_heatmap_job(self._payload(trace_id="a"))
        job_b = heatmap_jobs.create_heatmap_job(self._payload(trace_id="b"))
        self.assertIsNotNone(job_a["job_id"])
        self.assertIsNotNone(job_b["job_id"])
        self.assertNotEqual(job_a["job_id"], job_b["job_id"])

    def test_create_job_stores_created_at_timestamp(self):
        job = heatmap_jobs.create_heatmap_job(self._payload())
        self.assertIsNotNone(job["created_at"])
        dt = datetime.fromisoformat(job["created_at"])
        self.assertIsNotNone(dt)

    def test_get_existing_job(self):
        job = heatmap_jobs.create_heatmap_job(self._payload())
        fetched = heatmap_jobs.get_heatmap_job(job["job_id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["job_id"], job["job_id"])

    def test_get_missing_job_returns_none(self):
        result = heatmap_jobs.get_heatmap_job("nonexistent-uuid-000")
        self.assertIsNone(result)

    def test_update_job_to_running(self):
        job = heatmap_jobs.create_heatmap_job(self._payload())
        updated = heatmap_jobs.update_heatmap_job(
            job["job_id"],
            status="running",
            started_at=heatmap_jobs.utc_now(),
            total_tiles=8,
        )
        self.assertEqual(updated["status"], "running")
        self.assertEqual(updated["total_tiles"], 8)
        self.assertIsNotNone(updated["started_at"])

    def test_update_job_progress_fields(self):
        job = heatmap_jobs.create_heatmap_job(self._payload())
        heatmap_jobs.update_heatmap_job(job["job_id"], status="running", total_tiles=4)
        updated = heatmap_jobs.update_heatmap_job(
            job["job_id"], processed_tiles=2, progress=0.5
        )
        self.assertEqual(updated["processed_tiles"], 2)
        self.assertAlmostEqual(updated["progress"], 0.5)

    def test_update_job_to_completed(self):
        job = heatmap_jobs.create_heatmap_job(self._payload())
        result_payload = {"tile_count": 4, "tiles": [], "summary": {}}
        updated = heatmap_jobs.update_heatmap_job(
            job["job_id"],
            status="completed",
            progress=1.0,
            processed_tiles=4,
            completed_at=heatmap_jobs.utc_now(),
            result=result_payload,
        )
        self.assertEqual(updated["status"], "completed")
        self.assertAlmostEqual(updated["progress"], 1.0)
        self.assertIsNotNone(updated["completed_at"])
        self.assertEqual(updated["result"]["tile_count"], 4)

    def test_update_job_to_failed(self):
        job = heatmap_jobs.create_heatmap_job(self._payload())
        updated = heatmap_jobs.update_heatmap_job(
            job["job_id"],
            status="failed",
            error="GPU no disponible",
            failed_at=heatmap_jobs.utc_now(),
        )
        self.assertEqual(updated["status"], "failed")
        self.assertEqual(updated["error"], "GPU no disponible")
        self.assertIsNotNone(updated["failed_at"])

    def test_update_missing_job_returns_none(self):
        result = heatmap_jobs.update_heatmap_job("nonexistent", status="running")
        self.assertIsNone(result)

    def test_returned_dicts_are_deep_copies(self):
        job = heatmap_jobs.create_heatmap_job(self._payload())
        copy = heatmap_jobs.get_heatmap_job(job["job_id"])
        copy["status"] = "mutated"
        fetched = heatmap_jobs.get_heatmap_job(job["job_id"])
        self.assertEqual(fetched["status"], "queued")

    def test_multiple_jobs_tracked_independently(self):
        job_a = heatmap_jobs.create_heatmap_job(self._payload(trace_id="a"))
        job_b = heatmap_jobs.create_heatmap_job(self._payload(trace_id="b"))
        heatmap_jobs.update_heatmap_job(job_a["job_id"], status="running")
        state_a = heatmap_jobs.get_heatmap_job(job_a["job_id"])
        state_b = heatmap_jobs.get_heatmap_job(job_b["job_id"])
        self.assertEqual(state_a["status"], "running")
        self.assertEqual(state_b["status"], "queued")

    def test_utc_now_returns_iso_string(self):
        ts = heatmap_jobs.utc_now()
        self.assertIsInstance(ts, str)
        dt = datetime.fromisoformat(ts)
        self.assertIsNotNone(dt)

    def test_worker_limit_is_positive_int(self):
        limit = heatmap_jobs.heatmap_worker_limit()
        self.assertIsInstance(limit, int)
        self.assertGreaterEqual(limit, 1)

    def test_concurrent_job_creation_no_duplicates(self):
        ids = []
        lock = threading.Lock()

        def create():
            job = heatmap_jobs.create_heatmap_job(self._payload())
            with lock:
                ids.append(job["job_id"])

        threads = [threading.Thread(target=create) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(ids), len(set(ids)), "Se generaron job_ids duplicados bajo concurrencia")


if __name__ == "__main__":
    unittest.main()
