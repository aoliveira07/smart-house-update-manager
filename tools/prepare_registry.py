"""Set the real GitHub coordinates after GHCR image publication.

Usage: python tools/prepare_registry.py owner repository
Writes full YAML files; makes no network requests and publishes nothing.
"""
import re
import sys
from pathlib import Path
import yaml

if len(sys.argv) != 3 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", arg) for arg in sys.argv[1:]):
    raise SystemExit("Usage: python tools/prepare_registry.py OWNER REPOSITORY")
owner, repository = sys.argv[1:]
root = Path(__file__).resolve().parents[1]
url = f"https://github.com/{owner}/{repository}"
for filename in ["repository.yaml", "smart_house_update_manager/config.yaml"]:
    path = root / filename
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["url"] = url if filename == "repository.yaml" else url + "/tree/main/smart_house_update_manager"
    if filename.endswith("config.yaml"):
        data["image"] = f"ghcr.io/{owner.lower()}/{repository.lower()}"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")
print("Full manifests updated locally. Commit only after verifying the matching public GHCR tag.")
