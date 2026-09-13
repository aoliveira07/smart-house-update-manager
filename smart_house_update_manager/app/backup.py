from .supervisor import APIError, job_complete, segment


async def poll_backup(sup, operation):
    job = await sup.get("/jobs/" + segment(operation["job_id"]))
    if not job_complete(job):
        return False
    # Job completion alone is insufficient: the resulting full backup must exist.
    matches = [b for b in (await sup.get("/backups/info"))["backups"]
               if b.get("name") == operation["name"] and b.get("type") == "full"]
    if len(matches) != 1:
        raise APIError()
    operation["slug"] = matches[0]["slug"]
    return True
