"""Tests para recover_stale_heatmap_jobs y list_heatmap_jobs."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import db as app_db
from app.histopathology import heatmap_jobs
from app.models import HeatmapJob


class HeatmapJobsRecoveryTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "test_recovery.db"
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        HeatmapJob.__table__.create(self.engine)
        self._original = app_db.SessionLocal
        app_db.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def tearDown(self):
        app_db.SessionLocal = self._original
        self.engine.dispose()
        self._tmpdir.cleanup()

    def _payload(self, trace_id, user_id=None):
        return {
            "trace_id": trace_id,
            "user_id": user_id,
            "request": {"image_id": 1, "roi": {"x": 0, "y": 0, "width": 256, "height": 256}},
        }

    def test_recover_marks_queued_jobs_as_failed(self):
        heatmap_jobs.create_heatmap_job(self._payload("trace-q1"))
        heatmap_jobs.create_heatmap_job(self._payload("trace-q2"))
        recovered = heatmap_jobs.recover_stale_heatmap_jobs()
        self.assertEqual(recovered, 2)
        job = heatmap_jobs.get_heatmap_job(
            heatmap_jobs.create_heatmap_job(self._payload("trace-q3"))["job_id"]
        )
        # New job is queued; recover again counts it
        count = heatmap_jobs.recover_stale_heatmap_jobs()
        self.assertEqual(count, 1)

    def test_recover_marks_running_jobs_as_failed(self):
        job = heatmap_jobs.create_heatmap_job(self._payload("trace-r1"))
        heatmap_jobs.update_heatmap_job(job["job_id"], status="running")
        recovered = heatmap_jobs.recover_stale_heatmap_jobs()
        self.assertEqual(recovered, 1)
        updated = heatmap_jobs.get_heatmap_job(job["job_id"])
        self.assertEqual(updated["status"], "failed")
        self.assertIn("reinició", updated["error"])

    def test_recover_does_not_touch_completed_jobs(self):
        job = heatmap_jobs.create_heatmap_job(self._payload("trace-c1"))
        heatmap_jobs.update_heatmap_job(job["job_id"], status="completed")
        recovered = heatmap_jobs.recover_stale_heatmap_jobs()
        self.assertEqual(recovered, 0)
        updated = heatmap_jobs.get_heatmap_job(job["job_id"])
        self.assertEqual(updated["status"], "completed")

    def test_recover_does_not_touch_failed_jobs(self):
        job = heatmap_jobs.create_heatmap_job(self._payload("trace-f1"))
        heatmap_jobs.update_heatmap_job(job["job_id"], status="failed", error="previo")
        recovered = heatmap_jobs.recover_stale_heatmap_jobs()
        self.assertEqual(recovered, 0)

    def test_recover_returns_zero_when_no_stale_jobs(self):
        recovered = heatmap_jobs.recover_stale_heatmap_jobs()
        self.assertEqual(recovered, 0)


class HeatmapJobsListTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "test_list.db"
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        HeatmapJob.__table__.create(self.engine)
        self._original = app_db.SessionLocal
        app_db.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def tearDown(self):
        app_db.SessionLocal = self._original
        self.engine.dispose()
        self._tmpdir.cleanup()

    def _payload(self, trace_id, user_id=None):
        return {
            "trace_id": trace_id,
            "user_id": user_id,
            "request": {"image_id": 1, "roi": {"x": 0, "y": 0, "width": 256, "height": 256}},
        }

    def test_list_all_jobs_returns_all(self):
        heatmap_jobs.create_heatmap_job(self._payload("t1", user_id=1))
        heatmap_jobs.create_heatmap_job(self._payload("t2", user_id=2))
        heatmap_jobs.create_heatmap_job(self._payload("t3", user_id=1))
        jobs = heatmap_jobs.list_heatmap_jobs()
        self.assertEqual(len(jobs), 3)

    def test_list_filtered_by_user_id(self):
        heatmap_jobs.create_heatmap_job(self._payload("t1", user_id=1))
        heatmap_jobs.create_heatmap_job(self._payload("t2", user_id=2))
        heatmap_jobs.create_heatmap_job(self._payload("t3", user_id=1))
        jobs = heatmap_jobs.list_heatmap_jobs(user_id=1)
        self.assertEqual(len(jobs), 2)
        self.assertTrue(all(j["user_id"] == 1 for j in jobs))

    def test_list_filtered_by_status(self):
        j1 = heatmap_jobs.create_heatmap_job(self._payload("t1"))
        j2 = heatmap_jobs.create_heatmap_job(self._payload("t2"))
        heatmap_jobs.update_heatmap_job(j1["job_id"], status="completed")
        jobs = heatmap_jobs.list_heatmap_jobs(status="completed")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["status"], "completed")

    def test_list_respects_limit(self):
        for i in range(10):
            heatmap_jobs.create_heatmap_job(self._payload(f"trace-{i}"))
        jobs = heatmap_jobs.list_heatmap_jobs(limit=3)
        self.assertEqual(len(jobs), 3)

    def test_list_returns_newest_first(self):
        j1 = heatmap_jobs.create_heatmap_job(self._payload("t-old"))
        j2 = heatmap_jobs.create_heatmap_job(self._payload("t-new"))
        jobs = heatmap_jobs.list_heatmap_jobs()
        # newest first
        self.assertEqual(jobs[0]["trace_id"], "t-new")
        self.assertEqual(jobs[1]["trace_id"], "t-old")

    def test_list_empty_when_no_jobs(self):
        jobs = heatmap_jobs.list_heatmap_jobs()
        self.assertEqual(jobs, [])
