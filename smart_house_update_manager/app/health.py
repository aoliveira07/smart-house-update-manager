from .supervisor import APIError, active_jobs, segment


def hacs_restart_required(entity):
    attrs = entity.get("attributes", {})
    summary = str(attrs.get("release_summary", "")).lower()
    return "restart" in summary and "required" in summary


def hacs_update_staged(entity, target=None):
    attrs = entity.get("attributes", {})
    return (entity.get("state") == "on" and
            (target is None or attrs.get("installed_version") == target) and
            attrs.get("installed_version") == attrs.get("latest_version") and
            not attrs.get("in_progress") and hacs_restart_required(entity))


async def health(sup, ha):
    supervisor = await sup.get("/supervisor/info")
    core = await sup.get("/core/info")
    os_info = await sup.get("/os/info")
    await ha.request("GET", "")
    ha_config = await ha.request("GET", "config")
    if core.get("state", "started") != "started" or ha_config.get("state") != "RUNNING":
        raise APIError(503)
    if not core.get("version") or not os_info.get("version") or not supervisor.get("version"):
        raise APIError()
    if active_jobs(await sup.jobs()):
        raise APIError(409)
    return {"core": core["version"], "os": os_info["version"], "supervisor": supervisor["version"]}


async def validate_update(sup, ha, update, after_boot=False):
    category = update["category"]
    if category == "HACS_SOFTWARE":
        entity = await ha.entity(update["id"])
        attrs = entity.get("attributes", {})
        if (attrs.get("installed_version") != update["target"] or
                attrs.get("in_progress")):
            return False
        if entity.get("state") == "off":
            return True
        # HACS can finish the download while Home Assistant still has the
        # previous integration loaded. In that case the entity remains on
        # and explicitly reports that a restart is required. The downloaded
        # target is durable evidence; retrying install would be a duplicate.
        return hacs_restart_required(entity)
    if category == "FIRMWARE":
        entity = await ha.entity(update["id"])
        return (entity.get("state") == "off" and
                entity.get("attributes", {}).get("installed_version") == update["target"] and
                not entity.get("attributes", {}).get("in_progress"))
    path = "/addons/" + segment(update["id"]) + "/info" if category == "APP" else "/" + category.lower() + "/info"
    data = await sup.get(path)
    if category == "OS" and not after_boot:
        return data.get("version_pending") == update["target"] or any(
            slot.get("version") == update["target"] and slot.get("state") == "inactive"
            and slot.get("status") == "good" for slot in data.get("boot_slots", {}).values())
    return data.get("version") == update["target"] and not data.get("update_available", False) and (
        category != "OS" or not data.get("version_pending"))
