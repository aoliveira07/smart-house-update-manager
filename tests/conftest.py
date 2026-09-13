import asyncio
import copy
from types import SimpleNamespace
import pytest
from app.config import DEFAULTS
from app.reboot import Reboot
from app.state import State
from app.supervisor import APIError
from app.updater import Manager


class FakeSupervisor:
    def __init__(self):
        self.calls = []
        self.job_list = []
        self.backups = []
        self.fail = set()
        self.uncertain = set()
        self.hold_jobs = False
        self.core = {"version": "1", "version_latest": "2", "update_available": False, "state": "started"}
        self.os = {"version": "1", "version_latest": "2", "update_available": False, "version_pending": None}
        self.supervisor = {"version": "1", "auto_update": True}
        self.addons = []
        self.boot = 100

    async def get(self, path):
        self.calls.append(("GET", path, None))
        if path in self.fail:
            raise APIError(503)
        data = {"/available_updates": {"available_updates": []}, "/core/info": self.core,
                "/os/info": self.os, "/supervisor/info": self.supervisor,
                "/addons": {"addons": self.addons}, "/addons/self/info": {"slug": "abc_smart_house_update_manager"},
                "/backups/info": {"backups": self.backups}, "/host/info": {"boot_timestamp": self.boot}}
        if path.startswith("/jobs/") and path != "/jobs/info":
            return copy.deepcopy(next(j for j in self.job_list if j["uuid"] == path.split("/")[-1]))
        if path.startswith("/addons/") and path.endswith("/info") and path not in data:
            return copy.deepcopy(next(a for a in self.addons if a["slug"] == path.split("/")[2]))
        if path == "/jobs/info":
            return {"jobs": copy.deepcopy(self.job_list)}
        return copy.deepcopy(data[path])

    async def jobs(self):
        return (await self.get("/jobs/info"))["jobs"]

    async def post(self, path, body=None, timeout=30):
        self.calls.append(("POST", path, body))
        if path in self.uncertain:
            raise APIError(0, True)
        if path in self.fail:
            raise APIError(400)
        if path == "/backups/new/full":
            self.backups.append({"name": body["name"], "type": "full", "slug": "backup-slug"})
        elif path == "/supervisor/options":
            self.supervisor["auto_update"] = body["auto_update"]
        elif path == "/core/update":
            self.core.update(version=body["version"], update_available=False)
        elif path == "/os/update":
            self.os.update(version_pending=body["version"], update_available=False)
        elif path.startswith("/store/addons/"):
            addon = next(a for a in self.addons if a["slug"] == path.split("/")[3])
            addon.update(version=addon["version_latest"], update_available=False)
        if (body or {}).get("background"):
            job_id = str(len(self.job_list) + 1)
            self.job_list.append({"uuid": job_id, "done": not self.hold_jobs, "errors": [], "child_jobs": []})
            return {"job_id": job_id}
        return {}

    def posts(self, path=None):
        return [c for c in self.calls if c[0] == "POST" and (not path or c[1] == path)]


class FakeHA:
    def __init__(self):
        self.entities, self.entries, self.calls = [], {}, []
        self.online = True

    async def request(self, method, path, body=None, timeout=30):
        if not self.online:
            raise APIError(503)
        return {"state": "RUNNING", "time_zone": "America/Sao_Paulo"}

    async def registry(self):
        return self.entries

    async def states(self):
        if not self.online:
            raise APIError(503)
        return copy.deepcopy(self.entities)

    async def entity(self, ident):
        return copy.deepcopy(next(e for e in self.entities if e["entity_id"] == ident))

    async def install(self, update, timeout):
        self.calls.append(("install", update["id"]))
        entity = next(e for e in self.entities if e["entity_id"] == update["id"])
        entity["state"] = "off"
        entity["attributes"]["installed_version"] = update["target"]
        return []

    async def notify(self, ident, message):
        self.calls.append(("notify", ident))


@pytest.fixture
def env(tmp_path):
    state = State(tmp_path / "state.db")
    sup, ha = FakeSupervisor(), FakeHA()
    now = [1000.0]
    manager = Manager(state, sup, ha, copy.deepcopy(DEFAULTS), lambda: now[0])
    result = SimpleNamespace(state=state, sup=sup, ha=ha, m=manager, r=Reboot(manager), now=now)
    yield result
    state.close()


async def pump(env, n=30):
    for _ in range(n):
        await env.m.tick()
        await asyncio.sleep(0)


def add_update(env, category):
    if category == "CORE":
        env.sup.core["update_available"] = True
    elif category == "OS":
        env.sup.os["update_available"] = True
    elif category == "APP":
        env.sup.addons.append({"slug": "test_app", "name": "Test", "version": "1", "version_latest": "2", "update_available": True})
    else:
        ident = "update.test"
        env.ha.entities.append({"entity_id": ident, "state": "on", "attributes": {
            "device_class": "firmware" if category == "FIRMWARE" else None,
            "installed_version": "1", "latest_version": "2", "supported_features": 1}})
        env.ha.entries[ident] = {"platform": "hacs" if category == "HACS_SOFTWARE" else "custom"}
