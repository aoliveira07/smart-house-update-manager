import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request
import pytest
from app.config import validate
from app.homeassistant import HomeAssistant
from app.supervisor import APIError, Supervisor
from app.web import create_app


async def test_supervisor_envelope_and_bearer_not_exposed():
    seen = []
    async def endpoint(request):
        seen.append(request.headers.get("Authorization"))
        if request.path == "/reject":
            return web.json_response({"result": "error", "message": "secret-value"}, status=403)
        return web.json_response({"result": "ok", "data": {"job_id": "abc"}})
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", endpoint)
    async with TestServer(app) as server, aiohttp.ClientSession() as session:
        client = Supervisor(session, "private-token", str(server.make_url("/")).rstrip("/"))
        assert await client.post("/backups/new/full", {"background": True}) == {"job_id": "abc"}
        with pytest.raises(APIError) as error:
            await client.post("/reject")
        assert "secret-value" not in str(error.value)
        assert "private-token" not in str(error.value)
    assert seen == ["Bearer private-token"] * 2


async def test_websocket_registry_authentication():
    async def handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_json({"type": "auth_required"})
        assert (await ws.receive_json())["access_token"] == "token"
        await ws.send_json({"type": "auth_ok"})
        command = await ws.receive_json()
        assert command["type"] == "config/entity_registry/list"
        await ws.send_json({"id": command["id"], "success": True,
                            "result": [{"entity_id": "update.test", "platform": "hacs"}]})
        await ws.close()
        return ws
    app = web.Application()
    app.router.add_get("/websocket", handler)
    async with TestServer(app) as server, aiohttp.ClientSession() as session:
        ha = HomeAssistant(session, "token", str(server.make_url("/")).rstrip("/"))
        assert (await ha.registry())["update.test"]["platform"] == "hacs"


async def test_ingress_rejects_direct_peer_and_spoofed_forwarded_header(env):
    app = create_app(env.m, env.r, lambda: "UTC")
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/api/status", headers={"X-Forwarded-For": "172.30.32.2"})
        assert response.status == 403


async def test_csrf_and_confirmation_required(env):
    app = create_app(env.m, env.r, lambda: "UTC")
    guard = app.middlewares[0]
    class Transport:
        def get_extra_info(self, name, default=None):
            return ("172.30.32.2", 5555) if name == "peername" else default
    get = make_mocked_request("GET", "/api/status", app=app, transport=Transport())
    route = next(r for r in app.router.routes() if r.method == "GET" and r.resource.canonical == "/api/status")
    response = await guard(get, route.handler)
    import json
    token = json.loads(response.text)["csrf"]
    assert token
    post = make_mocked_request("POST", "/api/action/reboot", app=app, transport=Transport())
    with pytest.raises(web.HTTPForbidden):
        await guard(post, route.handler)
    action = next(r for r in app.router.routes() if r.method == "POST" and r.resource.canonical == "/api/action/{name}")
    class Request:
        match_info = {"name": "reboot"}
        async def json(self):
            return {"confirm": False}
    with pytest.raises(ValueError):
        await action.handler(Request())


@pytest.mark.parametrize("raw", [{"daily_host_reboot": {"force": True}}, {"updates": {"unknown": True}},
                                 {"maintenance_time": "25:00"}, {"backup": {"timeout_minutes": 0}},
                                 {"enabled": "true"}])
def test_invalid_config_rejected(raw):
    with pytest.raises(ValueError):
        validate(raw)
