import asyncio
import aiohttp
from .supervisor import APIError, segment


class HomeAssistant:
    def __init__(self, session, token, base="http://supervisor/core"):
        self.session, self.token, self.base = session, token, base

    async def request(self, method, path, body=None, timeout=30):
        try:
            async with self.session.request(method, self.base + "/api/" + path, json=body,
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status >= 400:
                    raise APIError(response.status, method == "POST" and response.status >= 500)
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise APIError(0, method == "POST") from None

    async def states(self):
        return await self.request("GET", "states")

    async def entity(self, entity_id):
        return await self.request("GET", "states/" + segment(entity_id))

    async def registry(self):
        try:
            async with asyncio.timeout(30):
                async with self.session.ws_connect(self.base + "/websocket") as ws:
                    if (await ws.receive_json()).get("type") != "auth_required":
                        raise APIError()
                    await ws.send_json({"type": "auth", "access_token": self.token})
                    if (await ws.receive_json()).get("type") != "auth_ok":
                        raise APIError(401)
                    await ws.send_json({"id": 1, "type": "config/entity_registry/list"})
                    result = await ws.receive_json()
                    if not result.get("success") or not isinstance(result.get("result"), list):
                        raise APIError()
                    return {entry["entity_id"]: entry for entry in result["result"]}
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError):
            raise APIError() from None

    async def install(self, update, timeout):
        entity = await self.entity(update["id"])
        attrs = entity.get("attributes", {})
        if entity.get("state") != "on" or attrs.get("latest_version") != update["target"]:
            raise APIError(409)
        payload = {"entity_id": update["id"]}
        if attrs.get("supported_features", 0) & 2:
            payload["version"] = update["target"]
        return await self.request("POST", "services/update/install", payload, timeout)

    async def notify(self, ident, message):
        await self.request("POST", "services/persistent_notification/create", {
            "notification_id": "shum_" + ident, "title": "Smart House Update Manager", "message": message})
