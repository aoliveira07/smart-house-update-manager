import asyncio
import logging
import os
import signal
from pathlib import Path
import aiohttp
from aiohttp import web
from .config import load
from .homeassistant import HomeAssistant
from .reboot import Reboot
from .scheduler import due, local_now
from .state import Busy, State
from .supervisor import APIError, Supervisor
from .updater import Manager
from .web import create_app


async def serve():
    # OS-level lock prevents two processes from reconciling the same durable intent.
    import fcntl
    Path("/data").mkdir(exist_ok=True)
    process_lock = open("/data/process.lock", "a+")
    fcntl.flock(process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = State("/data/state.sqlite3")
    token = os.environ["SUPERVISOR_TOKEN"]
    async with aiohttp.ClientSession() as session:
        sup, ha = Supervisor(session, token), HomeAssistant(session, token)
        manager = Manager(state, sup, ha, load())
        reboot = Reboot(manager)
        detected_zone = state.get("timezone", "UTC")

        def zone():
            return detected_zone if manager.config["timezone"] == "auto" else manager.config["timezone"]

        runner = web.AppRunner(create_app(manager, reboot, zone), access_log=None)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", 8099).start()
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        while not stop.is_set():
            try:
                # Auto timezone must be resolved before any scheduled mutation.
                config = await ha.request("GET", "config")
                detected_zone = config["time_zone"]
                state.put("timezone", detected_zone)
                now = local_now(zone())
                opts = manager.config
                if opts["enabled"]:
                    daily = opts["daily_host_reboot"]
                    if daily["enabled"] and due(now, daily["time"], state.get("reboot_date")):
                        hour, minute = map(int, daily["time"].split(":"))
                        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp()
                        if opts["dry_run"]:
                            manager.journal.log("reboot-" + now.date().isoformat(), "REBOOT", "dry_run: reboot não enviado")
                        else:
                            await reboot.request(now.date().isoformat(), scheduled)
                        state.put("reboot_date", now.date().isoformat())
                    if due(now, opts["maintenance_time"], state.get("maintenance_date")) and not state.active():
                        await manager.start(scheduled_date=now.date().isoformat())
            except (APIError, Busy):
                pass
            except Exception as exc:
                logging.error("[SHUM][SCHEDULER] %s", type(exc).__name__)
            for action in (manager.tick, reboot.tick, manager.flush_notifications):
                try:
                    await action()
                except Exception as exc:
                    # Keep UI alive; log only the exception type, not data or credentials.
                    logging.error("[SHUM][LOOP] %s", type(exc).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass
        if manager.task:
            manager.task.cancel()
            await asyncio.gather(manager.task, return_exceptions=True)
        await runner.cleanup()
    state.close()
    process_lock.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    asyncio.run(serve())
