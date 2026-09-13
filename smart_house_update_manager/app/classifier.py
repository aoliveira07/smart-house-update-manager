ORDER = {"APP": 0, "HACS_SOFTWARE": 1, "FIRMWARE": 2, "CORE": 3, "OS": 4,
         "SUPERVISOR": 5, "UNKNOWN": 6}
KEY = {"APP": "apps", "HACS_SOFTWARE": "hacs_software", "FIRMWARE": "firmware",
       "CORE": "core", "OS": "os"}


def classify(entity, registry):
    entry = registry.get(entity["entity_id"])
    if entry and entry.get("platform") == "hassio":
        return None  # Supervisor-owned entities must not re-enter via update.install.
    attrs = entity.get("attributes", {})
    if attrs.get("device_class") == "firmware":
        return "FIRMWARE"
    if not entry:
        return "UNKNOWN"
    if entry.get("platform") == "hacs" or attrs.get("device_class") == "software":
        return "HACS_SOFTWARE"
    return "UNKNOWN"


def eligible(update, config, self_slug):
    category = update["category"]
    if category not in KEY or not update.get("target"):
        return False
    if category == "APP" and (update["id"] == self_slug or
            update["id"].endswith("_smart_house_update_manager") or
            update["id"] == "smart_house_update_manager"):
        return False
    if category == "FIRMWARE" and not config["automatic_firmware_updates"]:
        return False
    return config["updates"][KEY[category]] and update.get("installable", True)
