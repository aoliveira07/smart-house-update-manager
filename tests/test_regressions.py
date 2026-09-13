from conftest import add_update, pump


async def test_legacy_os_contract_is_rejected_before_update(env):
    add_update(env, "OS")
    del env.sup.os["version_pending"]
    await env.m.start()
    await pump(env)
    assert not env.sup.posts("/os/update")
    assert env.state.history()[0]["status"] == "failed"


async def test_schedule_dates_are_committed_with_intent(env):
    await env.m.start(scheduled_date="2026-09-12")
    assert env.state.get("maintenance_date") == "2026-09-12"
    await env.r.request("2026-09-12", env.now[0])
    assert env.state.get("reboot_date") == "2026-09-12"


async def test_os_wrong_version_after_boot_fails(env):
    add_update(env, "OS")
    await env.m.start()
    await pump(env)
    await env.r.request("2026-09-12", env.now[0])
    await env.r.tick()
    env.sup.boot += 1
    env.sup.os["version_pending"] = None
    await env.r.tick()
    assert env.state.get("reboot")["status"] == "failed"
    assert env.state.history()[0]["status"] == "failed"


async def test_in_progress_entity_blocks_reboot(env):
    add_update(env, "HACS_SOFTWARE")
    env.ha.entities[0]["attributes"]["in_progress"] = True
    await env.r.request("2026-09-12", env.now[0])
    await env.r.tick()
    assert not env.sup.posts("/host/reboot")


async def test_jobs_block_backup_until_timeout(env):
    add_update(env, "CORE")
    env.sup.job_list = [{"done": False}]
    await env.m.start()
    await pump(env, 2)
    env.now[0] += 7201
    await pump(env, 2)
    assert env.state.active()["status"] == "blocked"
    assert not env.sup.posts()
