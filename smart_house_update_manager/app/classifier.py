ORDER = {"APP": 0, "HACS_SOFTWARE": 1, "FIRMWARE": 2, "CORE": 3, "OS": 4,
         "SUPERVISOR": 5, "UNKNOWN": 6}
KEY = {"APP": "apps", "HACS_SOFTWARE": "hacs_software", "FIRMWARE": "firmware",
       "CORE": "core", "OS": "os"}


def _has_hacs_release_metadata(attrs):
    """Recognize the stable metadata exposed by HACS update entities."""
    release_url = attrs.get("release_url")
    return (
        isinstance(release_url, str)
        and release_url.startswith("https://github.com/")
        and "/releases/tag/" in release_url
        and "auto_update" in attrs
        and attrs.get("installed_version") is not None
        and attrs.get("latest_version") is not None
    )


def classify(entity, registry):
    entry = registry.get(entity["entity_id"])
    if entry and entry.get("platform") == "hassio":
        return None  # Supervisor-owned entities must not re-enter via update.install.
    attrs = entity.get("attributes", {})
    if attrs.get("device_class") == "firmware":
        return "FIRMWARE"
    if not entry:
        return "HACS_SOFTWARE" if _has_hacs_release_metadata(attrs) else "UNKNOWN"
    if (entry.get("platform") == "hacs" or attrs.get("device_class") == "software" or
            _has_hacs_release_metadata(attrs)):
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

