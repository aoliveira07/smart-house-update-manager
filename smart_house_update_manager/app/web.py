"""Ingress-only UI, relative paths, CSRF protection and bounded request bodies."""
import secrets
from pathlib import Path
from aiohttp import web
from .config import validate
from .discovery import discover
from .scheduler import local_now, next_time
from .state import Busy
from .supervisor import APIError

ROOT = Path(__file__).resolve().parent.parent


def create_app(manager, reboot, zone):
    csrf = secrets.token_urlsafe(32)

    @web.middleware
    async def guard(request, handler):
        # Trust the TCP peer, never forwarded headers supplied by a caller.
        if request.remote != "172.30.32.2":
            raise web.HTTPForbidden(text="Acesso somente pelo Home Assistant Ingress")
        if request.method == "POST" and not secrets.compare_digest(request.headers.get("X-SHUM-CSRF", ""), csrf):
            raise web.HTTPForbidden(text="Token CSRF inválido")
        try:
            return await handler(request)
        except Busy as exc:
            return web.json_response({"error": str(exc)}, status=409)
        except (ValueError, KeyError):
            return web.json_response({"error": "Opções ou parâmetros inválidos"}, status=400)
        except APIError:
            return web.json_response({"error": "API indisponível; consulte o histórico"}, status=503)

    app = web.Application(middlewares=[guard], client_max_size=32768)

    async def index(request):
        return web.Response(text=(ROOT / "templates/index.html").read_text(encoding="utf-8"), content_type="text/html")

    async def status(request):
        now = local_now(zone())
        return web.json_response({"csrf": csrf, "active": manager.state.active(),
            "config": manager.config, "timezone": zone(), "history": manager.state.history(),
            "events": manager.state.events(), "reboot": manager.state.get("reboot", {}),
            "reboot_history": manager.state.get("reboot_history", []),
            "notifications_pending": len(manager.state.get("notifications", {})),
            "next_maintenance": next_time(now, manager.config["maintenance_time"], manager.state.get("maintenance_date")),
            "next_reboot": next_time(now, manager.config["daily_host_reboot"]["time"], manager.state.get("reboot_date"))})

    async def action(request):
        name = request.match_info["name"]
        body = await request.json()
        if name in ("maintenance", "dry-run"):
            return web.json_response({"run_id": await manager.start(dry=name == "dry-run")}, status=202)
        if name == "reboot":
            if body.get("confirm") is not True:
                raise ValueError()
            await reboot.request(local_now(zone()).date().isoformat(), manager.clock(), manual=True)
        elif name == "resolve":
            if body.get("confirm") is not True:
                raise ValueError()
            await manager.resolve_blocked()
        elif name == "updates":
            self_slug = (await manager.sup.get("/addons/self/info"))["slug"]
            return web.json_response(await discover(manager.sup, manager.ha, manager.config, self_slug))
        else:
            raise web.HTTPNotFound()
        return web.json_response({"accepted": True}, status=202)

    async def options(request):
        new = validate(await request.json())
        async with manager.mutex:
            if manager.state.active() or manager.state.get("reboot", {}).get("status") in ("waiting", "requested"):
                raise Busy("Aguarde a execução atual antes de alterar configurações")
            # Persist in Supervisor, so its options editor and this panel cannot diverge.
            await manager.sup.post("/addons/self/options", {"options": new})
            manager.config = new
        return web.json_response({"saved": True})

    app.router.add_get("/", index)
    app.router.add_get("/api/status", status)
    app.router.add_post("/api/action/{name}", action)
    app.router.add_post("/api/options", options)
    app.router.add_static("/static", ROOT / "static")
    return app
