from conftest import add_update, pump


async def test_backup_confirmed_before_update(env):
    add_update(env, "CORE")
    await env.m.start()
    await pump(env)
    calls = env.sup.calls
    assert next(i for i,c in enumerate(calls) if c[1] == "/jobs/1") < next(i for i,c in enumerate(calls) if c[1] == "/core/update")
    assert env.state.history()[0]["backup_status"] == "success"


async def test_backup_failure_aborts_updates(env):
    add_update(env, "CORE")
    env.sup.fail.add("/backups/new/full")
    await env.m.start()
    await pump(env)
    assert not env.sup.posts("/core/update")
    assert env.state.history()[0]["status"] == "failed"


async def test_backup_timeout_never_installs_even_if_job_later_finishes(env):
    add_update(env, "CORE")
    env.sup.hold_jobs = True
    await env.m.start()
    await pump(env, 4)
    env.now[0] += 3601
    await pump(env, 2)
    assert env.state.active()["status"] == "blocked"
    env.sup.job_list[0]["done"] = True
    await pump(env)
    assert not env.sup.posts("/core/update")
    assert env.state.history()[0]["status"] == "failed"


async def test_child_error_fails_backup(env):
    add_update(env, "CORE")
    env.sup.hold_jobs = True
    await env.m.start()
    await pump(env, 3)
    env.sup.job_list[0].update(done=True, child_jobs=[{"done": True, "errors": [{"type": "BackupError"}]}])
    await pump(env)
    assert not env.sup.posts("/core/update")
    assert env.state.history()[0]["status"] == "failed"
