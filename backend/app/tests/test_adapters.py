"""P2-4: Each adapter returns normalized RawJobs from a fixture."""

from app.adapters.base import RawJob
from app.adapters.himalayas import HimalayasAdapter
from app.adapters.remoteok import RemoteOKAdapter
from app.adapters.remotive import RemotiveAdapter
from app.adapters.weworkremotely import WeWorkRemotelyAdapter

# --- RemoteOK ---
_REMOTEOK_RAW = {
    "id": 12345,
    "position": "Senior Python Developer",
    "company": "Acme Corp",
    "description": "Build cool stuff.",
    "tags": ["python", "fastapi"],
    "date": "2026-11-15T10:00:00Z",
}


def test_remoteok_normalize() -> None:
    adapter = RemoteOKAdapter()
    job = adapter.normalize(_REMOTEOK_RAW)
    assert isinstance(job, RawJob)
    assert job.platform == "remoteok"
    assert job.external_id == "12345"
    assert job.title == "Senior Python Developer"
    assert job.company == "Acme Corp"
    assert "python" in job.skills
    assert job.posted_at is not None


def test_remoteok_skip_empty() -> None:
    adapter = RemoteOKAdapter()
    assert adapter.normalize({}) is None


# --- Remotive ---
_REMOTIVE_RAW = {
    "id": 67890,
    "title": "Frontend Engineer",
    "company_name": "Widgets Inc",
    "description": "React and TypeScript.",
    "tags": ["react", "typescript"],
    "category": "Software Development",
    "url": "https://remotive.com/remote-jobs/67890",
    "publication_date": "2026-11-14T08:00:00Z",
    "salary": "$80,000-$120,000",
}


def test_remotive_normalize() -> None:
    adapter = RemotiveAdapter()
    job = adapter.normalize(_REMOTIVE_RAW)
    assert isinstance(job, RawJob)
    assert job.platform == "remotive"
    assert job.title == "Frontend Engineer"
    assert job.budget_min == 80000.0
    assert job.budget_max == 120000.0
    assert job.category == "Software Development"


def test_remotive_no_salary() -> None:
    raw = {**_REMOTIVE_RAW, "salary": ""}
    adapter = RemotiveAdapter()
    job = adapter.normalize(raw)
    assert job is not None
    assert job.budget_min is None


# --- Himalayas ---
_HIMALAYAS_RAW = {
    "id": "abc-123",
    "title": "DevOps Engineer",
    "companyName": "CloudCo",
    "description": "K8s and Terraform.",
    "skills": [{"name": "kubernetes"}, {"name": "terraform"}],
    "categoryName": "DevOps",
    "publishedDate": "2026-11-13T12:00:00Z",
    "salaryCurrencyMinValue": 90000,
    "salaryCurrencyMaxValue": 150000,
    "applicationLink": "https://himalayas.app/jobs/abc-123",
}


def test_himalayas_normalize() -> None:
    adapter = HimalayasAdapter()
    job = adapter.normalize(_HIMALAYAS_RAW)
    assert isinstance(job, RawJob)
    assert job.platform == "himalayas"
    assert job.external_id == "abc-123"
    assert "kubernetes" in job.skills
    assert job.budget_min == 90000.0


def test_himalayas_string_skills() -> None:
    raw = {**_HIMALAYAS_RAW, "skills": ["docker", "linux"]}
    adapter = HimalayasAdapter()
    job = adapter.normalize(raw)
    assert "docker" in job.skills


# --- WeWorkRemotely ---
_WWR_RAW = {
    "title": "Acme Corp: Full Stack Developer",
    "link": "https://weworkremotely.com/remote-jobs/acme-full-stack",
    "description": "<p>Build web apps with <b>React</b> and Node.</p>",
    "pubDate": "Wed, 12 Nov 2026 10:00:00 +0000",
    "category": "Programming",
}


def test_wwr_normalize() -> None:
    adapter = WeWorkRemotelyAdapter()
    job = adapter.normalize(_WWR_RAW)
    assert isinstance(job, RawJob)
    assert job.platform == "weworkremotely"
    assert job.company == "Acme Corp"
    assert "<" not in job.description  # HTML stripped
    assert job.posted_at is not None
    assert job.category == "Programming"


def test_wwr_skip_empty() -> None:
    adapter = WeWorkRemotelyAdapter()
    assert adapter.normalize({}) is None
