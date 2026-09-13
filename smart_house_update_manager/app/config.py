"""Validated options. Supervisor's /data/options.json is the single source."""
import copy
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULTS = {
    "enabled": True, "maintenance_time": "04:00", "timezone": "auto",
    "daily_host_reboot": {"enabled": True, "time": "05:30",
                          "retry_interval_minutes": 5, "max_wait_minutes": 120,
                          "force": False},
    "updates": {"core": True, "os": True, "apps": True,
                "hacs_software": True, "firmware": False, "unknown": False},
    "automatic_firmware_updates": False,
    "backup": {"enabled": True, "only_when_updates": True, "timeout_minutes": 60},
    "supervisor": {"ensure_native_auto_update": True},
    "notifications": {"success": True, "failure": True, "reboot_failure": True},
    "dry_run": False, "update_timeout_minutes": 120, "health_timeout_minutes": 15,
}


def validate(raw):
    result = copy.deepcopy(DEFAULTS)
    if not isinstance(raw, dict):
        raise ValueError("As opções devem ser um objeto JSON")
    for key, value in raw.items():
        if key not in result:
            raise ValueError(f"Opção desconhecida: {key}")
        if isinstance(result[key], dict):
            if not isinstance(value, dict) or set(value) - set(result[key]):
                raise ValueError(f"Grupo inválido: {key}")
            result[key].update(value)
        else:
            result[key] = value
    def check(values, defaults):
        for key, default in defaults.items():
            value = values[key]
            if isinstance(default, dict):
                check(value, default)
            elif type(value) is not type(default):
                raise ValueError(f"Tipo inválido: {key}")
            elif isinstance(default, int) and not isinstance(default, bool):
                if not 1 <= value <= 1440:
                    raise ValueError(f"Fora do intervalo 1–1440: {key}")
    check(result, DEFAULTS)
    for value in [result["maintenance_time"], result["daily_host_reboot"]["time"]]:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Horário deve usar HH:MM")
    if result["timezone"] != "auto":
        ZoneInfo(result["timezone"])
    if result["daily_host_reboot"]["force"] or result["updates"]["unknown"]:
        raise ValueError("Reboot forçado e atualização UNKNOWN não são permitidos")
    if not result["backup"]["only_when_updates"]:
        raise ValueError("Backup somente quando houver updates deve permanecer habilitado")
    return result


def load(path="/data/options.json"):
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))
