import logging
from datetime import datetime, timezone


def stamp():
    return datetime.now(timezone.utc).isoformat()


class Journal:
    def __init__(self, state):
        self.state = state

    def log(self, run_id, phase, message):
        # Callers supply controlled messages, never HTTP bodies or exception strings.
        self.state.event(run_id, stamp(), phase, message)
        logging.getLogger("shum").info("[SHUM][RUN:%s][%s] %s", run_id, phase, message)
