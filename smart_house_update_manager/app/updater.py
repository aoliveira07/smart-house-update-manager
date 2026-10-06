"""Persistent, single-writer maintenance state machine.

Every external mutation has a committed intent before dispatch. An interrupted
POST is never replayed blindly: its job/result is reconciled, or a bounded safe
retry is prepared only after the previous operation is no longer active.
"""
import asyncio
import copy
import time
import uuid
from .backup import poll_backup
from .discovery import discover
from .health import health, validate_update
from .journal import Journal, stamp
from .state import Busy
from .supervisor import APIError, active_jobs, job_complete, segment

HACS_ACK_TIMEOUT_SECONDS = 60


class Manager:
    def __init__(self, state, sup, ha, config, clock=time.time):
        self.state, self.sup, self.ha = state, sup, ha
        self.config, self.clock = config, clock
        self.mutex = asyncio.Lock()
        self.task = None
        self.journal = Journal(state)
        self.self_slug = "smart_house_update_manager"

    async def notify(self, ident, text, kind):
        if not self.config["notifications"][kind]:
            return
        pending = self.state.get("notifications", {})
        pending[ident] = text
        self.state.put("notifications", pending)

    async def flush_notifications(self):
        pending = self.state.get("notifications", {})
        for ident, message in list(pending.items()):
            try:
                await self.ha.notify(ident, message)
            except APIError:
                return
            del pending[ident]
            self.state.put("notifications", pending)

    async def start(self, dry=False, scheduled_date=None, source="manual", timezone=None):
        async with self.mutex:
            if self.state.active() or self.state.get("reboot", {}).get("status") in ("waiting", "requested"):
                raise Busy("Manutenção ou reboot já pendente")
            if not self.config["enabled"] and not dry:
                raise Busy("App desabilitado; apenas Dry Run disponível")
            run = {"run_id": uuid.uuid4().hex, "started_at": stamp(), "status": "running",
                   "current_step": "discovery", "dry_run": dry or self.config["dry_run"],
                   "source": "dry_run" if dry else source, "timezone": timezone,
                   "options": copy.deepcopy(self.config), "updates_detected": [],
                   "updates_completed": [], "updates_failed": [], "errors": [],
                   "backup_status": "not_needed", "backup_job_id": None,
                   "core_target": None, "os_target": None, "os_reboot_required": False,
                   "operation": None, "index": 0, "scheduled_date": scheduled_date}
            self.state.acquire(run)
            self.journal.log(run["run_id"], "RUN", "started")
            return run["run_id"]

    async def finish(self, run, status):
        run.update(status=status, current_step=status, finished_at=stamp(), operation=None)
        self.state.save(run, release=True)
        self.journal.log(run["run_id"], "RUN", status)
        if not run["dry_run"]:
            await self.notify(run["run_id"], f"Execução {run['run_id']}: {status}. Consulte o histórico.",
                              "success" if status == "success" else "failure")

    async def block(self, run, reason):
        if reason not in run["errors"]:
            run["errors"].append(reason)
            self.journal.log(run["run_id"], run["current_step"], reason)
            await self.notify(run["run_id"], f"Execução bloqueada: {reason}. Consulte o painel.", "failure")
        recovery = run.setdefault("recovery", {"attempts": 0})
        recovery.setdefault("attempts", 0)
        recovery.update(next_at=self.clock(), last_blocked_at=stamp(), last_reason=reason)
        run["status"] = "blocked"
        run["abort"] = True  # Reconciliation clears this only after external state is safe.
        self.state.save(run)

    async def defer(self, run, reason):
        """Close a safe preflight wait without leaving a permanent lock."""
        if reason not in run["errors"]:
            run["errors"].append(reason)
        run.update(status="deferred", current_step="deferred", deferred_reason=reason,
                   finished_at=stamp(), operation=None)
        self.state.save(run, release=True)
        self.journal.log(run["run_id"], "RUN", "deferred: " + reason)
        if not run["dry_run"]:
            await self.notify(run["run_id"], f"Execução {run['run_id']}: adiada. Consulte o histórico.", "failure")

    async def safe(self):
        if active_jobs(await self.sup.jobs()):
            return False
        # HACS/device work can exist outside Supervisor's job tree.
        for entity in await self.ha.states():
            if entity["entity_id"].startswith("update.") and entity.get("attributes", {}).get("in_progress"):
                return False
        return True

    async def wait_safe(self, run):
        if await self.safe():
            run.pop("idle_wait_started", None)
            return True
        started = run.setdefault("idle_wait_started", self.clock())
        if self.clock() - started > run["options"]["update_timeout_minutes"] * 60:
            await self.defer(run, "preflight ocupado excedeu o prazo; nenhuma operação nova foi iniciada")
        self.state.save(run)
        return False

    def recovery_config(self, run):
        values = run.get("options", {}).get("recovery", {})
        return {"retry_interval_minutes": values.get("retry_interval_minutes", 5),
                "max_attempts": values.get("max_attempts", 3)}

    def recovery_wait(self, run, reason):
        recovery = run.setdefault("recovery", {"attempts": 0})
        recovery.setdefault("attempts", 0)
        recovery.update(next_at=self.clock() + self.recovery_config(run)["retry_interval_minutes"] * 60,
                        last_check_at=stamp(), last_reason=reason)
        self.state.save(run)
        if recovery.get("last_logged_reason") != reason:
            recovery["last_logged_reason"] = reason
            self.state.save(run)
            self.journal.log(run["run_id"], "RECOVERY", "aguardando: " + reason)

    async def operation_job_state(self, operation):
        job_id = operation.get("job_id")
        if not job_id:
            return "missing"
        try:
            job = await self.sup.get("/jobs/" + segment(job_id))
        except APIError as exc:
            if exc.status == 404:
                return "missing"
            raise
        try:
            return "complete" if job_complete(job) else "active"
        except APIError as exc:
            if exc.status == 200:
                return "failed"
            raise

    async def operation_confirmed(self, operation):
        kind = operation.get("kind")
        if kind == "native_supervisor":
            return (await self.sup.get("/supervisor/info")).get("auto_update") is True
        if kind == "backup":
            if not operation.get("job_id"):
                return False
            try:
                return await poll_backup(self.sup, operation)
            except APIError as exc:
                if exc.status == 200:
                    return False
                raise
        update = operation.get("update")
        return bool(update and await validate_update(self.sup, self.ha, update))

    async def complete_operation(self, run, operation, reconciled=False):
        if not await self.safe():
            return False
        if operation["kind"] == "backup":
            run.update(backup_status="success", backup_slug=operation["slug"],
                       backup_name=operation["name"],
                       backup_duration_seconds=self.clock() - operation["started"],
                       current_step="updates")
            self.journal.log(run["run_id"], "BACKUP", "completed")
        elif operation["kind"] == "native_supervisor":
            run.update(supervisor_auto_update=True, current_step="backup_gate")
        else:
            update = operation["update"]
            if update["category"] == "OS":
                run.update(os_reboot_required=True, status="waiting_reboot", current_step="waiting_reboot")
                run["os_staged_at"] = stamp()
            else:
                run["updates_completed"].append({**update, "result": "success"})
                run["index"] += 1
                run["current_step"] = "updates"
                self.journal.log(run["run_id"], "UPDATE",
                                 "reconciled after timeout" if reconciled else "validated")
        run["operation"] = None
        if reconciled:
            run["status"] = "waiting_reboot" if run.get("os_reboot_required") else "running"
            run["abort"] = False
            run.setdefault("recovery", {})["reconciled_at"] = stamp()
            self.journal.log(run["run_id"], "RECOVERY", "operação concluída com evidência")
        self.state.save(run)
        return True

    async def retry_blocked(self, run, operation, reason):
        recovery = run.setdefault("recovery", {"attempts": 0})
        recovery.setdefault("attempts", 0)
        config = self.recovery_config(run)
        if recovery["attempts"] >= config["max_attempts"]:
            run["errors"].append("recuperação automática esgotou as tentativas; nova janela será permitida")
            await self.finish(run, "failed")
            self.journal.log(run["run_id"], "RECOVERY", "tentativas esgotadas; lock liberado")
            return
        attempt = recovery["attempts"] + 1
        recovery.update(attempts=attempt,
                        next_at=self.clock() if attempt == 1 else
                        self.clock() + config["retry_interval_minutes"] * 60,
                        last_retry_at=stamp(), last_retry_reason=reason)
        run["operation"] = None
        run["abort"] = False
        run["status"] = "running"
        if operation.get("kind") == "backup":
            run["backup_status"] = "not_needed"
            run["current_step"] = "backup_gate"
        elif operation.get("kind") == "native_supervisor":
            run["current_step"] = "native_supervisor"
        else:
            run["current_step"] = "updates"
        self.state.save(run)
        self.journal.log(run["run_id"], "RECOVERY", f"nova tentativa preparada ({attempt}): {reason}")

    async def reconcile_blocked(self, run):
        operation = run.get("operation")
        if not operation:
            try:
                if await self.safe():
                    run["errors"].append("execução bloqueada sem operação; lock liberado para nova janela")
                    await self.finish(run, "failed")
                else:
                    self.recovery_wait(run, "não foi possível provar que não há operação ativa")
            except APIError:
                self.recovery_wait(run, "API indisponível para validar uma execução bloqueada")
            return
        if self.clock() < run.get("recovery", {}).get("next_at", 0):
            return
        if self.task:
            if not self.task.done():
                self.recovery_wait(run, "requisição original ainda está em andamento")
                return
            task, self.task = self.task, None
            try:
                response = task.result()
            except APIError:
                response = None
            if response is not None:
                operation["accepted"] = True
                if isinstance(response, dict) and response.get("job_id"):
                    operation["job_id"] = response["job_id"]
                self.state.save(run)
        # A lost/timeout response can still leave durable evidence behind.
        # Check the installed version (or staged HACS state) before requiring
        # an accepted response or job id; otherwise a completed mutation is
        # incorrectly replayed during recovery.
        try:
            if await self.operation_confirmed(operation):
                if not await self.complete_operation(run, operation, reconciled=True):
                    self.recovery_wait(run, "operação concluída, mas há outra atividade crítica ativa")
                return
        except APIError:
            self.recovery_wait(run, "API indisponível durante a reconciliação")
            return
        if not operation.get("accepted") and not operation.get("job_id"):
            try:
                if await self.safe():
                    recovery = run.setdefault("recovery", {"attempts": 0})
                    recovery.setdefault("attempts", 0)
                    if recovery["attempts"] >= self.recovery_config(run)["max_attempts"]:
                        run["errors"].append("POST incerto sem confirmação; lock liberado após reconciliação")
                        await self.finish(run, "failed")
                        self.journal.log(run["run_id"], "RECOVERY", "POST incerto expirou; lock liberado")
                    else:
                        recovery["attempts"] += 1
                        recovery.update(
                            next_at=self.clock() + self.recovery_config(run)["retry_interval_minutes"] * 60,
                            last_check_at=stamp(), last_reason="POST incerto sem confirmação")
                        self.state.save(run)
                        self.journal.log(run["run_id"], "RECOVERY",
                                         f"POST incerto aguardando reconciliação ({recovery['attempts']})")
                else:
                    self.recovery_wait(run, "POST incerto e ainda há operação crítica ativa")
            except APIError:
                self.recovery_wait(run, "API indisponível para reconciliar POST incerto")
            return
        try:
            state = await self.operation_job_state(operation)
            if state == "active":
                self.recovery_wait(run, "job ainda ativo; nenhuma nova operação será enviada")
                return
            if state == "failed":
                run["errors"].append("job terminou com erro durante a reconciliação")
                await self.finish(run, "failed")
                return
            if not await self.safe():
                self.recovery_wait(run, "job terminou, mas a condição segura ainda não foi confirmada")
                return
            await self.retry_blocked(run, operation,
                                     "job ausente ou concluído sem a versão alvo; nova tentativa segura")
        except APIError:
            self.recovery_wait(run, "API indisponível durante a reconciliação")

    async def finalize_run(self, run):
        """Re-discover after the plan and reject silent pending updates."""
        await health(self.sup, self.ha)
        self_slug = (await self.sup.get("/addons/self/info"))["slug"]
        remaining = await discover(self.sup, self.ha, run["options"], self_slug)
        planned = {(u["id"], u.get("target")) for u in run.get("queue", []) if u.get("selected")}
        pending = [u for u in remaining if u.get("selected") and
                   (u.get("id"), u.get("target")) in planned]
        run["post_validation"] = {"pending": copy.deepcopy(pending), "checked_at": stamp()}
        self.journal.log(run["run_id"], "VALIDATION",
                         "pending updates remain" if pending else "all planned updates cleared")
        self.state.save(run)
        if pending:
            reason = "update selecionado continua pendente após a validação pós-update"
            run["errors"].append(reason)
            await self.finish(run, "failed")
            return False
        return True

    def dispatch(self, run, kind, request, **fields):
        timeout = run["options"]["backup"]["timeout_minutes"] if kind == "backup" else run["options"]["update_timeout_minutes"]
        operation = {"kind": kind, "started": self.clock(), "deadline": self.clock() + timeout * 60,
                     "accepted": False, **fields}
        run["operation"] = operation
        run["current_step"] = fields.get("update", {}).get("category", kind)
        self.state.save(run)  # Intent durable BEFORE the request is sent.
        self.journal.log(run["run_id"], run["current_step"], "started")
        self.task = asyncio.create_task(request())

    async def tick(self):
        async with self.mutex:
            run = self.state.active()
            if not run or run["status"] == "waiting_reboot":
                return
            try:
                if run.get("operation"):
                    await self.poll(run)
                    return
                if run["status"] == "blocked":
                    await self.reconcile_blocked(run)
                    return
                if run["current_step"] == "discovery":
                    self.journal.log(run["run_id"], "DISCOVERY", "started")
                    self.self_slug = (await self.sup.get("/addons/self/info"))["slug"]
                    run["updates_detected"] = await discover(self.sup, self.ha, run["options"], self.self_slug)
                    for update in run["updates_detected"]:
                        reason = "selected" if update.get("selected") else "policy or capability"
                        self.journal.log(run["run_id"], "DISCOVERY",
                                         f"{update.get('category')} {update.get('id')} {update.get('current')}->{update.get('target')} {reason}")
                    run["jobs_at_discovery"] = [{"job_id": j.get("uuid"), "name": j.get("name"),
                                                  "done": j.get("done")} for j in active_jobs(await self.sup.jobs())]
                    run["queue"] = [copy.deepcopy(u) for u in run["updates_detected"] if u["selected"]]
                    run["supervisor_auto_update"] = (await self.sup.get("/supervisor/info")).get("auto_update")
                    self.state.save(run)
                    if run["dry_run"]:
                        self.journal.log(run["run_id"], "DISCOVERY", "dry_run plan complete")
                        await self.finish(run, "dry_run")
                        return
                    run["current_step"] = "native_supervisor"
                    self.state.save(run)
                if run["current_step"] == "native_supervisor":
                    if (run["options"]["supervisor"]["ensure_native_auto_update"] and
                            run["supervisor_auto_update"] is not True):
                        if not await self.wait_safe(run):
                            return
                        self.dispatch(run, "native_supervisor", lambda: self.sup.post(
                            "/supervisor/options", {"auto_update": True}))
                        return
                    run["current_step"] = "backup_gate"
                    self.state.save(run)
                if run["current_step"] == "backup_gate":
                    if run["queue"] and run["options"]["backup"]["enabled"]:
                        if not await self.wait_safe(run):
                            return
                        name = "SHUM-" + run["run_id"]
                        run["backup_status"] = "running"
                        self.dispatch(run, "backup", lambda: self.sup.post("/backups/new/full",
                                      {"background": True, "name": name}), name=name)
                        return
                    run["backup_status"] = "disabled" if run["queue"] else "not_needed"
                    run["current_step"] = "updates"
                    self.state.save(run)
                if run["current_step"] == "updates":
                    if not await self.wait_safe(run):
                        return
                    run.pop("idle_wait_started", None)
                    if run["index"] >= len(run["queue"]):
                        if await self.finalize_run(run):
                            await self.finish(run, "success")
                        return
                    update = run["queue"][run["index"]]
                    category = update["category"]
                    timeout = run["options"]["update_timeout_minutes"] * 60
                    if category == "CORE":
                        run["core_target"] = update["target"]
                    if category == "OS":
                        run["os_target"] = update["target"]
                        if "version_pending" not in await self.sup.get("/os/info"):
                            run["errors"].append("Supervisor sem contrato version_pending: OS não enviado para evitar reboot imediato legado")
                            await self.finish(run, "failed")
                            return
                    if category == "APP":
                        info = await self.sup.get("/addons/" + segment(update["id"]) + "/info")
                        if info.get("version_latest") != update["target"]:
                            run["errors"].append("versão disponível do App mudou após o plano; executar nova descoberta")
                            await self.finish(run, "failed")
                            return
                    async def request():
                        if category == "APP":
                            return await self.sup.post("/store/addons/" + segment(update["id"]) + "/update",
                                                       {"background": True, "backup": False})
                        if category in ("CORE", "OS"):
                            body = {"version": update["target"]}
                            if category == "CORE":
                                body["backup"] = False
                            return await self.sup.post("/" + category.lower() + "/update", body, timeout)
                        # HACS has no Supervisor job to poll and its service
                        # call may stay open while files are downloaded. A
                        # bounded acknowledgement timeout moves the durable
                        # operation into reconciliation; validation then
                        # proves completion without replaying the install.
                        request_timeout = min(timeout, HACS_ACK_TIMEOUT_SECONDS)
                        return await self.ha.install(update, request_timeout)
                    self.dispatch(run, "update", request, update=update)
            except APIError:
                # Discovery/health errors never imply that a mutation completed.
                if run.get("operation"):
                    await self.block(run, "falha de API durante operação; validar antes de prosseguir")
                else:
                    run["errors"].append("falha de API na descoberta, preparação ou health check")
                    await self.finish(run, "failed")

    async def poll(self, run):
        op = run["operation"]
        if run.get("status") == "blocked":
            await self.reconcile_blocked(run)
            return
        if self.task:
            if not self.task.done():
                if self.clock() > op["deadline"]:
                    await self.block(run, "timeout; operação pode continuar no Supervisor")
                return
            task, self.task = self.task, None
            try:
                response = task.result()
            except APIError as exc:
                if exc.uncertain:
                    self.state.save(run)
                    await self.block(run, "resposta perdida; não repetir POST")
                    return
                # A confirmed rejection means no mutation was accepted.  It is
                # safe to record a failed run and release the lock.
                op["rejected"] = True
                if op["kind"] == "backup":
                    run["backup_status"] = "failed"
                elif op.get("update"):
                    run["updates_failed"].append({**op["update"], "result": "failed"})
                run["errors"].append("operação recusada pelo Supervisor/Home Assistant")
                await self.finish(run, "failed")
                return
            op["accepted"] = True
            if isinstance(response, dict) and response.get("job_id"):
                op["job_id"] = response["job_id"]
                if op["kind"] == "backup":
                    run["backup_job_id"] = response["job_id"]
                self.journal.log(run["run_id"], run["current_step"], "job accepted")
            self.state.save(run)
        if op.get("rejected"):
            if await self.safe():
                if op["kind"] == "backup":
                    run["backup_status"] = "failed"
                elif op.get("update"):
                    run["updates_failed"].append({**op["update"], "result": "failed"})
                await self.finish(run, "failed")
            return
        try:
            done = False
            if op["kind"] == "native_supervisor":
                done = (await self.sup.get("/supervisor/info")).get("auto_update") is True
            elif op["kind"] == "backup":
                if op.get("job_id"):
                    done = await poll_backup(self.sup, op)
                elif op["accepted"]:
                    await self.block(run, "backup sem job_id; conclusão não comprovada")
            else:
                update = op["update"]
                if update["category"] == "APP" and not op.get("job_id"):
                    if op["accepted"]:
                        await self.block(run, "App update sem job_id; conclusão não comprovada")
                else:
                    done = (not op.get("job_id") or job_complete(await self.sup.get("/jobs/" + segment(op["job_id"]))))
                    done = done and await validate_update(self.sup, self.ha, update)
                    if done:
                        await health(self.sup, self.ha)
            if done:
                if not await self.safe():
                    return
                self.journal.log(run["run_id"], run["current_step"],
                                 "staged; aguardando reboot diário" if op.get("update", {}).get("category") == "OS" else "success")
                if op["kind"] == "backup":
                    run.update(backup_status="success", backup_slug=op["slug"], backup_name=op["name"],
                               backup_duration_seconds=self.clock() - op["started"], current_step="updates")
                    self.journal.log(run["run_id"], "BACKUP", "completed")
                elif op["kind"] == "native_supervisor":
                    run.update(supervisor_auto_update=True, current_step="backup_gate")
                else:
                    update = op["update"]
                    if update["category"] == "OS":
                        run.update(os_reboot_required=True, status="waiting_reboot", current_step="waiting_reboot")
                        run["os_staged_at"] = stamp()
                    else:
                        run["updates_completed"].append({**update, "result": "success"})
                        run["index"] += 1
                        run["current_step"] = "updates"
                        self.journal.log(run["run_id"], "UPDATE", "validated")
                run["operation"] = None
                self.state.save(run)
                if run.get("abort"):
                    if run["os_reboot_required"]:
                        # Preserve pending OS validation even if its HTTP reply was interrupted.
                        return
                    await self.finish(run, "failed")
                return
        except APIError:
            # A job error is a failed run; API outages are conservatively held until timeout.
            if op.get("job_id"):
                try:
                    job_complete(await self.sup.get("/jobs/" + segment(op["job_id"])))
                except APIError as exc:
                    if exc.status == 200:
                        op["rejected"] = True
                        if op["kind"] == "backup":
                            run["backup_status"] = "failed"
                        if op.get("update"):
                            run["updates_failed"].append({**op["update"], "result": "failed"})
                        run["errors"].append("job concluído com erro")
                        await self.finish(run, "failed")
                        return
        if self.clock() > op["deadline"]:
            if op["kind"] == "backup":
                run["backup_status"] = "timeout"
            await self.block(run, "timeout; conclusão não comprovada")
        elif not op["accepted"] and not op.get("job_id"):
            await self.block(run, "retomada de POST sem resposta persistida; não repetir operação")

    async def resolve_blocked(self):
        """Explicit operator acknowledgement, never an automatic lock reset."""
        async with self.mutex:
            run = self.state.active()
            if not run or run["status"] != "blocked" or (self.task and not self.task.done()):
                raise Busy("A execução não pode ser encerrada neste estado")
            if not await self.safe():
                raise Busy("Ainda há operação crítica ativa")
            if run.get("os_reboot_required"):
                raise Busy("OS ainda aguarda reboot e validação")
            if self.task:
                try:
                    self.task.result()
                except APIError:
                    pass
                self.task = None
            run["errors"].append("operador confirmou término externo; execução encerrada como falha")
            await self.finish(run, "failed")
