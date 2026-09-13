from .supervisor import APIError, active_jobs, segment


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
    if category in ("HACS_SOFTWARE", "FIRMWARE"):
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
