import pytest
from app.state import Busy
from conftest import add_update, pump


@pytest.mark.parametrize("global_mode", [True, False])
async def test_dry_run_has_no_mutations(env, global_mode):
    for category in ["CORE", "OS", "APP", "HACS_SOFTWARE"]:
        add_update(env, category)
    env.sup.supervisor["auto_update"] = False
    env.m.config["dry_run"] = global_mode
    await env.m.start(dry=not global_mode)
    await pump(env)
    assert not env.sup.posts()
    assert not env.ha.calls
    assert env.state.history()[0]["status"] == "dry_run"


async def test_global_dry_run_blocks_manual_reboot(env):
    env.m.config["dry_run"] = True
    with pytest.raises(Busy):
        await env.r.request("2026-09-12", env.now[0], manual=True)
