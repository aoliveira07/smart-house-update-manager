import pytest
from app.supervisor import active_jobs, job_complete, APIError


def test_recursive_active_job_and_unknown_job():
    job = {"done": True, "child_jobs": [{"name": "unknown_future_job", "done": False}]}
    assert active_jobs([job]) == job["child_jobs"]
    assert not job_complete(job)
    assert active_jobs([{}])


def test_job_errors_even_with_done_true():
    with pytest.raises(APIError):
        job_complete({"done": True, "errors": [{"message": "failure"}]})
