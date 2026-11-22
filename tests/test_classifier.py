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


def test_hacs_release_metadata_is_classified_without_registry_source():
    entity = {"entity_id": "update.kiosk_mode_update", "attributes": {
        "auto_update": False,
        "installed_version": "v15.0.0",
        "latest_version": "v16.0.0",
        "release_url": "https://github.com/NemesisRE/kiosk-mode/releases/tag/v16.0.0",
    }}
    assert classify(entity, {}) == "HACS_SOFTWARE"


def test_github_release_without_hacs_markers_remains_unknown():
    entity = {"entity_id": "update.custom", "attributes": {
        "installed_version": "1.0.0",
        "latest_version": "1.1.0",
        "release_url": "https://github.com/example/project/releases/tag/v1.1.0",
    }}
    assert classify(entity, {}) == "UNKNOWN"


async def test_self_update_excluded(env):
    add_update(env, "APP")
    env.sup.addons[0]["slug"] = "abc_smart_house_update_manager"
    await env.m.start()
    await pump(env)
    assert not env.sup.posts()

