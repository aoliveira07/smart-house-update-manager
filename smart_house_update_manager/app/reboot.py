"""Daily reboot state is independent of maintenance, with durable intent."""
from .health import health, validate_update
from .journal import stamp
from .state import Busy
from .supervisor import APIError


class Reboot:
    def __init__(self, manager):
        self.m = manager

    async def request(self, date, scheduled_at, manual=False):
        async with self.m.mutex:
            config = self.m.config
            if config["dry_run"] or not config["enabled"]:
                raise Busy("Reboot indisponível em Dry Run ou com App desabilitado")
            old = self.m.state.get("reboot", {})
            if old.get("status") in ("waiting", "requested"):
                raise Busy("Reboot já pendente")
            item = {"status": "waiting", "date": date,
                "manual": manual, "scheduled_at": scheduled_at, "created_at": stamp(),
                "deadline": scheduled_at + config["daily_host_reboot"]["max_wait_minutes"] * 60,
                "next_attempt": scheduled_at, "deferred": False, "reason": None}
            values = {"reboot": item}
            if not manual:
                values["reboot_date"] = date
            self.m.state.put_many(values)

    async def fail(self, item, reason):
        item.update(status="failed", reason=reason, finished_at=stamp())
        self.m.state.put("reboot", item)
        history = self.m.state.get("reboot_history", [])
        self.m.state.put("reboot_history", (history + [item])[-100:])
        self.m.journal.log("reboot-" + item["date"], "REBOOT", reason)
        await self.m.notify("reboot-" + item["date"], "Reboot diário falhou: " + reason, "reboot_failure")

    async def tick(self):
        async with self.m.mutex:
            item = self.m.state.get("reboot", {})
            now = self.m.clock()
            if item.get("status") == "requested":
                try:
                    host = await self.m.sup.get("/host/info")
                    new_boot = host.get("boot_timestamp")
                    if new_boot and new_boot != item["boot_before"]:
                        versions = await health(self.m.sup, self.m.ha)
                        run = self.m.state.active()
                        if run and run.get("os_reboot_required"):
                            update = next(u for u in run["queue"] if u["category"] == "OS")
                            if not await validate_update(self.m.sup, self.m.ha, update, after_boot=True):
                                await self.fail(item, "reboot ocorreu, mas a versão esperada do OS não foi confirmada")
                                run["os_reboot_required"] = False
                                run["updates_failed"].append({**update, "result": "failed"})
                                await self.m.finish(run, "failed")
                                return
                            run["updates_completed"].append({**update, "result": "success"})
                            run.update(os_reboot_required=False, last_boot_timestamp=new_boot)
                            await self.m.finish(run, "failed" if run.get("abort") else "success")
                        item.update(status="success", boot_after=new_boot, versions=versions, finished_at=stamp())
                        self.m.state.put("reboot", item)
                        self.m.state.put("last_boot_timestamp", new_boot)
                        history = self.m.state.get("reboot_history", [])
                        self.m.state.put("reboot_history", (history + [item])[-100:])
                        self.m.journal.log("reboot-" + item["date"], "REBOOT", "confirmed")
                        await self.m.notify("reboot-" + item["date"], "Reboot do host confirmado e APIs operacionais.", "success")
                        return
                except APIError:
                    pass
                if now > item["confirm_deadline"]:
                    await self.fail(item, "boot_timestamp/health não confirmou reboot no prazo; POST não será repetido")
                return
            if item.get("status") != "waiting" or now < item["next_attempt"]:
                return
            if now >= item["deadline"]:
                await self.fail(item, "timeout aguardando condição segura; nenhum reboot forçado")
                return
            if self.m.config["dry_run"] or not self.m.config["enabled"]:
                await self.fail(item, "reboot cancelado pela configuração")
                return
            try:
                run = self.m.state.active()
                if run and run["status"] != "waiting_reboot":
                    raise Busy("rotina de manutenção ou operação incerta em andamento")
                if not await self.m.safe():
                    raise Busy("job crítico ou update de entidade em andamento")
                host = await self.m.sup.get("/host/info")
                if not host.get("boot_timestamp"):
                    raise Busy("boot_timestamp indisponível")
                # Check again immediately before committing the reboot intent.
                if not await self.m.safe():
                    raise Busy("operação crítica detectada na verificação final")
                item.update(status="requested", requested_at=stamp(), boot_before=host["boot_timestamp"],
                            confirm_deadline=now + self.m.config["health_timeout_minutes"] * 60)
                self.m.state.put("reboot", item)
                self.m.journal.log("reboot-" + item["date"], "REBOOT", "requested")
                try:
                    await self.m.sup.post("/host/reboot", {"force": False})
                except APIError as exc:
                    if not exc.uncertain:
                        await self.fail(item, "Supervisor recusou o reboot")
                    # Lost response is reconciled by boot timestamp, never resubmitted.
            except (Busy, APIError) as exc:
                reason = str(exc) if isinstance(exc, Busy) else "API indisponível; segurança não confirmada"
                item.update(deferred=True, reason=reason,
                    next_attempt=now + self.m.config["daily_host_reboot"]["retry_interval_minutes"] * 60)
                self.m.state.put("reboot", item)
                self.m.journal.log("reboot-" + item["date"], "REBOOT", "reboot adiado: " + reason)
