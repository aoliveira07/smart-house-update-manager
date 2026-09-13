import pytest
from app.state import Busy
from conftest import add_update, pump


async def request(env):
    await env.r.request("2026-09-12", env.now[0])
    await env.r.tick()


@pytest.mark.parametrize("category", [None, "CORE", "APP", "HACS_SOFTWARE", "OS"])
async def test_daily_reboot_with_or_without_updates(env, category):
    if category:
        add_update(env, category)
    await env.m.start()
    await pump(env)
    await request(env)
    assert len(env.sup.posts("/host/reboot")) == 1
    assert env.sup.posts("/host/reboot")[0][2] == {"force": False}
    env.sup.boot += 1
    if category == "OS":
        env.sup.os.update(version="2", version_pending=None)
    await env.r.tick()
    assert env.state.get("reboot")["status"] == "success"
    assert env.state.history()[0]["status"] == "success"
    await env.r.tick()
    assert len(env.sup.posts("/host/reboot")) == 1


async def test_job_at_0530_defers_then_reboots(env):
    env.sup.job_list = [{"uuid": "external", "done": False}]
    await request(env)
    assert env.state.get("reboot")["deferred"]
    assert not env.sup.posts("/host/reboot")
    env.sup.job_list[0]["done"] = True
    env.now[0] += 299
    await env.r.tick()
    assert not env.sup.posts("/host/reboot")
    env.now[0] += 1
    await env.r.tick()
    assert len(env.sup.posts("/host/reboot")) == 1


async def test_busy_timeout_and_notification(env):
    env.sup.job_list = [{"done": False}]
    await request(env)
    env.now[0] += 7200
    await env.r.tick()
    assert env.state.get("reboot")["status"] == "failed"
    assert not env.sup.posts("/host/reboot")
    await env.m.flush_notifications()
    assert env.ha.calls[0][0] == "notify"


async def test_reboot_rejected(env):
    env.sup.fail.add("/host/reboot")
    await request(env)
    assert env.state.get("reboot")["status"] == "failed"


async def test_lost_reboot_response_is_not_retried(env):
    env.sup.uncertain.add("/host/reboot")
    await request(env)
    await env.r.tick()
    assert len(env.sup.posts("/host/reboot")) == 1
    env.sup.boot += 1
    await env.r.tick()
    assert env.state.get("reboot")["status"] == "success"


async def test_same_boot_is_not_success(env):
    await request(env)
    env.now[0] += 901
    await env.r.tick()
    assert env.state.get("reboot")["status"] == "failed"


async def test_reboot_after_failed_update(env):
    add_update(env, "CORE")
    env.sup.fail.add("/core/update")
    await env.m.start()
    await pump(env)
    await request(env)
    assert env.sup.posts("/host/reboot")


async def test_reboot_needs_ha_and_jobs_visibility(env):
    env.ha.online = False
    await request(env)
    assert not env.sup.posts("/host/reboot")
    assert env.state.get("reboot")["deferred"]


async def test_missing_boot_blocks_reboot(env):
    env.sup.boot = None
    await request(env)
    assert not env.sup.posts("/host/reboot")


async def test_duplicate_reboot_request_rejected(env):
    await request(env)
    with pytest.raises(Busy):
        await env.r.request("2026-09-12", env.now[0])
