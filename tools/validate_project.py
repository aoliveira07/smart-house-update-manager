"""Validate manifests and the project's deliberate permission boundaries."""
import ast
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "smart_house_update_manager"))
from app.config import validate

for path in ROOT.rglob("*.yaml"):
    yaml.safe_load(path.read_text(encoding="utf-8"))
for path in ROOT.rglob("*.yml"):
    yaml.safe_load(path.read_text(encoding="utf-8"))
for path in ROOT.rglob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
config = yaml.safe_load((ROOT / "smart_house_update_manager/config.yaml").read_text(encoding="utf-8"))
validate(config["options"])
assert config["hassio_role"] == "manager"
assert config["arch"] == ["amd64", "aarch64"]
assert config["ingress"] and config["panel_admin"]
assert not set(config).intersection({"full_access", "docker_api", "privileged", "host_network", "ports"})
assert not list(ROOT.rglob("build.yaml"))
code = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "smart_house_update_manager/app").glob("*.py"))
assert '"/supervisor/update"' not in code
assert '"/store/addons/"' in code
assert '{"force": False}' in code
dockerfile = (ROOT / "smart_house_update_manager/Dockerfile").read_text()
assert '\nWORKDIR /opt/shum\n' in dockerfile
assert 'FROM python:' in dockerfile and 'BUILD_FROM' not in dockerfile
for path in [ROOT / "smart_house_update_manager/run.sh", ROOT / "smart_house_update_manager/Dockerfile"]:
    assert b'\r\n' not in path.read_bytes(), f"CRLF in {path.name}"
print("Project manifests, Python syntax, permissions, endpoints and LF checks passed")
