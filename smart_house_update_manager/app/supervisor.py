"""Official Supervisor v1 API; mutations are never retried by transport."""
import asyncio
from urllib.parse import quote
import aiohttp


class APIError(RuntimeError):
    def __init__(self, status=0, uncertain=False):
        super().__init__(f"API indisponível ou requisição recusada (HTTP {status})")
        self.status = status
        self.uncertain = uncertain


def segment(value):
    return quote(str(value), safe="")


class Supervisor:
    def __init__(self, session, token, base="http://supervisor"):
        self.session, self.token, self.base = session, token, base

    async def request(self, method, path, body=None, timeout=30):
        try:
            async with self.session.request(method, self.base + path, json=body,
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status >= 400:
                    raise APIError(response.status, method == "POST" and response.status >= 500)
                payload = await response.json()
                if payload.get("result") != "ok":
                    raise APIError(response.status, method == "POST")
                return payload.get("data", {})
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise APIError(0, method == "POST") from None

    async def get(self, path):
        return await self.request("GET", path)

    async def post(self, path, body=None, timeout=30):
        return await self.request("POST", path, body or {}, timeout)

    async def jobs(self):
        data = await self.get("/jobs/info")
        if not isinstance(data.get("jobs"), list):
            raise APIError()
        return data["jobs"]


def flatten(jobs):
    for job in jobs:
        if not isinstance(job, dict):
            raise APIError()
        yield job
        yield from flatten(job.get("child_jobs", []))


def active_jobs(jobs):
    # Unknown jobs are also treated as critical, including active children of done parents.
    return [j for j in flatten(jobs) if j.get("done") is not True]


def job_complete(job):
    nodes = list(flatten([job]))
    if any(node.get("errors") for node in nodes):
        raise APIError(200)
    return all(node.get("done") is True for node in nodes)
