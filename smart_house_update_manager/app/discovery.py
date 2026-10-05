from .classifier import ORDER, classify, eligible


async def discover(sup, ha, config, self_slug):
    available = await sup.get("/available_updates")
    available_by_type = {
        str(item.get("update_type", "")).upper(): item
        for item in available.get("available_updates", [])
        if isinstance(item, dict)
    }
    result = []
    for category, path in [("CORE", "/core/info"), ("OS", "/os/info"), ("SUPERVISOR", "/supervisor/info")]:
        data = await sup.get(path)
        if data.get("update_available") or any(x.get("update_type") == category.lower()
                for x in available.get("available_updates", [])):
            result.append({"id": category.lower(), "name": category, "category": category,
                           "current": data.get("version"), "target": data.get("version_latest") or
                           available_by_type.get(category, {}).get("version")})
    for addon in (await sup.get("/addons"))["addons"]:
        if addon.get("update_available"):
            result.append({"id": addon["slug"], "name": addon.get("name", addon["slug"]),
                           "category": "APP", "current": addon.get("version"),
                           "target": addon.get("version_latest")})
    registry = await ha.registry()  # Failure aborts; never guess ownership from names.
    for entity in await ha.states():
        if not entity["entity_id"].startswith("update.") or entity.get("state") != "on":
            continue
        category = classify(entity, registry)
        if category is None:
            continue
        attrs = entity.get("attributes", {})
        result.append({"id": entity["entity_id"], "name": attrs.get("friendly_name", entity["entity_id"]),
                       "category": category, "current": attrs.get("installed_version"),
                       "target": attrs.get("latest_version"),
                       "installable": bool(attrs.get("supported_features", 0) & 1)})
    unique = {}
    for item in result:
        item["selected"] = bool(eligible(item, config, self_slug))
        item["result"] = "planned" if item["selected"] else "ignored"
        unique[(item["category"], item["id"])] = item
    return sorted(unique.values(), key=lambda x: ORDER[x["category"]])
