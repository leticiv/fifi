import time
import logging
import requests

log = logging.getLogger("fifi.api")

API_BASE = "https://api.intigriti.com/external/researcher/v1"

STATUS_MAP = {3: "Open", 4: "Suspended", 5: "Closing"}
ACTIVITY_TYPE_MAP = {1: "domains_updated", 2: "rules_updated", 3: "status_changed"}
CONFIDENTIALITY_MAP = {1: "Invite only", 2: "Application", 3: "Registered", 4: "Public"}


class IntigritiAPI:
    def __init__(self, pat):
        self.headers = {"Authorization": f"Bearer {pat}"}

    def _get(self, path, params=None):
        url = f"{API_BASE}{path}"
        r = requests.get(url, headers=self.headers, params=params, timeout=30)
        if r.status_code == 401:
            log.critical("Authentication failed — check your PAT token")
            raise SystemExit(1)
        if r.status_code == 429:
            log.warning("Rate limited — sleeping 60s")
            time.sleep(60)
            return None
        r.raise_for_status()
        return r.json()

    def list_programs(self, following_only=False, limit=500):
        params = {"limit": limit}
        if following_only:
            params["following"] = True
        return self._get("/programs", params)

    def get_program(self, program_id):
        return self._get(f"/programs/{program_id}")

    def get_activities(self, created_since=None, following=False, limit=500):
        params = {"limit": limit}
        if created_since is not None:
            params["createdSince"] = created_since
        if following:
            params["following"] = True
        return self._get("/programs/activities", params)
