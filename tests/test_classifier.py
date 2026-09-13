import pytest
from app.classifier import classify
from conftest import add_update, pump


@pytest.mark.parametrize("category", ["FIRMWARE", "UNKNOWN"])
async def test_manual_categories_ignored(env, category):
    add_update(env, category)
    await env.m.start()
    await pump(env)
    assert not env.sup.posts()
    assert not env.ha.calls
    assert env.state.history()[0]["updates_detected"][0]["selected"] is False


def test_supervisor_ownership_and_firmware_precedence():
    entity = {"entity_id": "update.x", "attributes": {"device_class": "firmware"}}
    assert classify(entity, {"update.x": {"platform": "hassio"}}) is None
    assert classify(entity, {"update.x": {"platform": "hacs"}}) == "FIRMWARE"
    entity["attributes"] = {"device_class": "software"}
    assert classify(entity, {}) == "UNKNOWN"


async def test_self_update_excluded(env):
    add_update(env, "APP")
    env.sup.addons[0]["slug"] = "abc_smart_house_update_manager"
    await env.m.start()
    await pump(env)
    assert not env.sup.posts()
