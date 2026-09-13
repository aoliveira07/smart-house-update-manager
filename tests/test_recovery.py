import asyncio
import pytest
from app.reboot import Reboot
from app.state import Busy, State
from app.updater import Manager
from conftest import add_update, pump


async def test_concurrent_maintenance_rejected(env):
    results = await asyncio.gather(env.m.start(), env.m.start(), return_exceptions=True)
    assert sum(isinstance(r, Busy) for r in results) == 1


async def test_persistent_lock_across_connections(env, tmp_path):
    await env.m.start()
    other = State(tmp_path / "state.db")
    try:
        with pytest.raises(Busy):
            other.acquire({"run_id": "other"})
    finally:
        other.close()


async def test_app_restart_resumes_backup_job_without_duplicate(env):
    add_update(env, "CORE")
    env.sup.hold_jobs = True
    await env.m.start()
    await pump(env, 4)
    assert env.state.active()["backup_job_id"]
    env.m = Manager(env.state, env.sup, env.ha, env.m.config, lambda: env.now[0])
    env.sup.job_list[0]["done"] = True
    env.sup.hold_jobs = False
    await pump(env)
    assert len(env.sup.posts("/backups/new/full")) == 1
    assert env.state.history()[0]["status"] == "success"


async def test_uncertain_post_holds_lock_and_blocks_reboot(env):
    add_update(env, "CORE")
    env.sup.uncertain.add("/backups/new/full")
    await env.m.start()
    await pump(env)
    assert env.state.active()["status"] == "blocked"
    await env.r.request("2026-09-12", env.now[0])
    await env.r.tick()
    assert not env.sup.posts("/host/reboot")
    assert len(env.sup.posts("/backups/new/full")) == 1


async def test_recover_reboot_after_new_manager(env):
    add_update(env, "OS")
    await env.m.start()
    await pump(env)
    await env.r.request("2026-09-12", env.now[0])
    await env.r.tick()
    manager = Manager(env.state, env.sup, env.ha, env.m.config, lambda: env.now[0])
    env.sup.boot += 1
    env.sup.os.update(version="2", version_pending=None)
    await Reboot(manager).tick()
    assert env.state.get("reboot")["status"] == "success"
    assert env.state.history()[0]["status"] == "success"


async def test_operator_can_close_uncertain_run_only_when_safe(env):
    add_update(env, "CORE")
    env.sup.uncertain.add("/backups/new/full")
    await env.m.start()
    await pump(env)
    env.sup.job_list = [{"done": False}]
    with pytest.raises(Busy):
        await env.m.resolve_blocked()
    env.sup.job_list = []
    await env.m.resolve_blocked()
    assert env.state.active() is None
    assert env.state.history()[0]["status"] == "failed"
