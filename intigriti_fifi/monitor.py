import os
import json
import time
import logging
import requests
from datetime import datetime, timezone

log = logging.getLogger("fifi")

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state", "state.json")

# catppuccin mocha palette
COLORS = {"Open": 0xA6E3A1, "Suspended": 0xF9E2AF, "Closing": 0xF38BA8,
           "domains_updated": 0x89B4FA, "rules_updated": 0xF5C2E7}
EMOJIS = {"Open": "🔥", "Suspended": "💤", "Closing": "🚫",
           "domains_updated": "🔗", "rules_updated": "📝"}


class Monitor:
    def __init__(self, api, config):
        self.api = api
        self.cfg = config
        self.webhook_url = config["discord"]["webhook_url"]
        self.state = self._load_state()

    def _load_state(self):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                return json.load(f)
        return {"last_check": int(time.time()), "notified": {}}

    def _save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)

    def _send_discord(self, program, activity_value, activity_type_id, mention=""):
        mon = self.cfg["monitoring"]
        name = program["name"]
        emoji = EMOJIS.get(activity_value, "🔔")
        color = COLORS.get(activity_value, 0x89B4FA)

        embed = {
            "title": f"{emoji} {name}  ·  {activity_value}",
            "url": program["webLinks"]["detail"],
            "color": color,
            "fields": [
                {"name": "handle", "value": program["handle"], "inline": True},
                {"name": "type", "value": program.get("type", {}).get("value", "?"), "inline": True},
            ],
            "footer": {"text": "fifi · intigriti", "icon_url": ""},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if program.get("minBounty") and program.get("maxBounty"):
            mn = program["minBounty"].get("value", "?")
            mx = program["maxBounty"].get("value", "?")
            cu = program["minBounty"].get("currency", "")
            embed["fields"].append({"name": "bounty", "value": f"{mn} – {mx} {cu}", "inline": False})

        payload = {"embeds": [embed]}
        if mention:
            payload["content"] = mention
        r = requests.post(self.webhook_url, json=payload, timeout=15)
        if r.status_code == 429:
            time.sleep(10)
            return self._send_discord(program, activity_value, activity_type_id, mention)
        r.raise_for_status()

    def _should_notify(self, activity_type_id):
        t = self.cfg["monitoring"]["activity_types"]
        if activity_type_id == 3 and t.get("status_change", True):
            return True
        if activity_type_id == 1 and t.get("domains_update", False):
            return True
        if activity_type_id == 2 and t.get("rules_update", False):
            return True
        return False

    def _passes_filters(self, program):
        f = self.cfg.get("filters", {})
        handle = program.get("handle", "")
        sid = program.get("status", {}).get("id")

        allowed = f.get("programs", [])
        if allowed and handle not in allowed:
            return False

        statuses = f.get("statuses", [3, 4, 5])
        if sid not in statuses:
            return False

        return True

    def run(self, catchup=False, since=None):
        last_check = self.state["last_check"]
        notified = self.state.get("notified", {})

        if catchup:
            last_check = 0
            notified = {}

        if since is not None:
            last_check = since
            notified = {}

        interval = self.cfg["monitoring"]["interval"]
        log.info("started  ·  interval=%ds  ·  watching=%s", interval,
                 "all" if not self.cfg["monitoring"]["follow_only"] else "followed")

        while True:
            try:
                data = self.api.get_activities(
                    created_since=last_check,
                    following=self.cfg["monitoring"]["follow_only"],
                )
                if data is None:
                    time.sleep(interval)
                    continue

                for act in data.get("records", []):
                    atype = act.get("type", {}).get("id")
                    pid = act["programId"]

                    if not self._should_notify(atype):
                        continue
                    if pid in notified:
                        continue

                    prog = self.api.get_program(pid)
                    if prog is None:
                        continue

                    if not self._passes_filters(prog):
                        notified[pid] = {"status": prog.get("status", {}).get("id"), "at": int(time.time())}
                        continue

                    activity_value = prog.get("status", {}).get("value", "?")
                    if atype == 1:
                        activity_value = "domains_updated"
                    elif atype == 2:
                        activity_value = "rules_updated"
                    log.info("%s → %s", prog.get("handle"), activity_value)
                    mentions = self.cfg.get("mentions", {})
                    mention = mentions.get(prog.get("handle"), "")
                    self._send_discord(prog, activity_value, atype, mention)
                    notified[pid] = {"status": prog.get("status", {}).get("id"), "at": int(time.time())}

                self.state["notified"] = notified
                self.state["last_check"] = int(time.time())
                self._save_state()

            except requests.exceptions.RequestException as e:
                log.error("request failed: %s", e)
            except Exception as e:
                log.exception("error: %s", e)

            time.sleep(interval)

    def test(self):
        print("\n  · api")
        data = self.api.get_activities(limit=5)
        if data:
            print(f"    ok  ·  {data.get('maxCount', '?')} activities available")
        else:
            print("    fail")
            return

        print("  · discord")
        if self.webhook_url:
            embed = {
                "embeds": [{
                    "title": "🧪 fifizudo · test",
                    "description": "monitor configured successfullyyyyyy",
                    "color": 0x5865F2,
                    "footer": {"text": "fifi · intigriti"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }]
            }
            try:
                r = requests.post(self.webhook_url, json=embed, timeout=15)
                if r.ok:
                    print("    ok")
                else:
                    print(f"    fail  ·  {r.status_code}")
            except Exception as e:
                print(f"    fail  ·  {e}")
        else:
            print("    skipped  ·  no webhook set")

        print("  · programs")
        data = self.api.list_programs(following_only=self.cfg["monitoring"]["follow_only"])
        if data:
            for p in data.get("records", []):
                s = p.get("status", {}).get("value", "?")
                t = p.get("type", {}).get("value", "?")
                f = "•" if p.get("following") else ""
                print(f"    {f} {p['name']:<38} {p['handle']:<25} {s:<12}  {t}")
        else:
            print("    (none)")
        print()
