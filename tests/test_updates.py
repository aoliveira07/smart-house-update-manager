import pytest
from conftest import add_update, pump


@pytest.mark.parametrize("category", ["CORE", "APP", "HACS_SOFTWARE"])
async def test_individual_update_success(env, category):
    add_update(env, category)
    await env.m.start()
    await pump(env)
    run = env.state.history()[0]
    assert run["status"] == "success"
    assert [u["category"] for u in run["updates_completed"]] == [category]


@pytest.mark.parametrize("category,path", [("CORE", "/core/update"), ("APP", "/store/addons/test_app/update"), ("OS", "/os/update")])
async def test_update_failure(env, category, path):
    add_update(env, category)
    env.sup.fail.add(path)
    await env.m.start()
    await pump(env)
    run = env.state.history()[0]
    assert run["status"] == "failed"
    assert not run["os_reboot_required"]
    assert len(env.sup.posts(path)) == 1


async def test_os_staged_without_immediate_reboot(env):
    add_update(env, "OS")
    await env.m.start()
    await pump(env)
    assert env.state.active()["status"] == "waiting_reboot"
    assert env.state.active()["os_reboot_required"]
    assert not env.sup.posts("/host/reboot")


async def test_order_and_complete_plan(env):
    for category in ["OS", "CORE", "HACS_SOFTWARE", "APP"]:
        add_update(env, category)
    await env.m.start()
    await pump(env)
    assert [u["category"] for u in env.state.active()["queue"]] == ["APP", "HACS_SOFTWARE", "CORE", "OS"]
    assert [c[1] for c in env.sup.posts()] == ["/backups/new/full", "/store/addons/test_app/update", "/core/update", "/os/update"]


@pytest.mark.parametrize("enabled", [True, False])
async def test_supervisor_native_auto_update(env, enabled):
    env.sup.supervisor["auto_update"] = enabled
    await env.m.start()
    await pump(env)
    assert len(env.sup.posts("/supervisor/options")) == (0 if enabled else 1)
    assert not env.sup.posts("/supervisor/update")


async def test_native_auto_update_opt_out(env):
    env.sup.supervisor["auto_update"] = False
    env.m.config["supervisor"]["ensure_native_auto_update"] = False
    await env.m.start()
    await pump(env)
    assert not env.sup.posts()
