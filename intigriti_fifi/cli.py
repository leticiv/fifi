import os
import sys
import json
import logging
import argparse
from datetime import datetime

try:
    import yaml
except ImportError:
    print("error: install pyyaml — pip install pyyaml")
    sys.exit(1)

from .api import IntigritiAPI
from .monitor import Monitor

LOG = logging.getLogger("fifi")


def setup_logging(cfg):
    log_cfg = cfg.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    handlers = [logging.StreamHandler()]

    log_file = log_cfg.get("file")
    if log_file:
        from logging.handlers import RotatingFileHandler
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        handlers.append(RotatingFileHandler(
            log_file,
            maxBytes=log_cfg.get("max_bytes", 10 * 1024 * 1024),
            backupCount=log_cfg.get("backup_count", 3),
        ))

    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def load_config(path):
    cfg = {}
    if os.path.exists(path):
        with open(path) as f:
            cfg = yaml.safe_load(f) or {}

    cfg.setdefault("intigriti", {})
    cfg.setdefault("discord", {})
    cfg.setdefault("mentions", {})
    cfg.setdefault("filters", {"programs": [], "statuses": [3, 4, 5]})

    monitoring = cfg.setdefault("monitoring", {})
    monitoring.setdefault("interval", 300)
    monitoring.setdefault("follow_only", False)
    activity_types = monitoring.setdefault("activity_types", {})
    activity_types.setdefault("status_change", True)
    activity_types.setdefault("domains_update", False)
    activity_types.setdefault("rules_update", False)

    logging_cfg = cfg.setdefault("logging", {})
    logging_cfg.setdefault("level", "INFO")
    logging_cfg.setdefault("file", "logs/monitor.log")
    logging_cfg.setdefault("max_bytes", 10485760)
    logging_cfg.setdefault("backup_count", 3)

    cfg["intigriti"]["pat"] = cfg["intigriti"].get("pat") or os.environ.get("INTIGRITI_PAT", "")
    cfg["discord"]["webhook_url"] = cfg["discord"].get("webhook_url") or os.environ.get("DISCORD_WEBHOOK_URL", "")

    return cfg


EPILOG = """
docs: https://github.com/youruser/intigriti-fifi
"""


def main():
    p = argparse.ArgumentParser(
        prog="fifi",
        description="intigriti fifi — monitor program changes and get discord alerts",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-c", "--config", default="config.yaml", help="config path (default: config.yaml)")
    p.add_argument("--test", action="store_true", help="quick test — api, discord, programs")
    p.add_argument("--list", action="store_true", help="list all programs")
    p.add_argument("--reset", action="store_true", help="reset notification state")
    p.add_argument("--catchup", action="store_true", help="process all past activities")
    p.add_argument("--since", help="start from a date (ISO: 2025-06-01T14:30:00 or unix ts)")
    args = p.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg)

    pat = cfg["intigriti"]["pat"]
    webhook = cfg["discord"]["webhook_url"]

    if not pat:
        print("error: no pat found — set INTIGRITI_PAT or add it to config.yaml")
        sys.exit(1)

    api = IntigritiAPI(pat)
    monitor = Monitor(api, cfg)

    if args.test:
        if not webhook:
            print("  warning: no webhook set — discord test skipped")
        monitor.test()
        return

    if args.list:
        data = api.list_programs(following_only=cfg["monitoring"].get("follow_only", False))
        if not data or not data.get("records"):
            print("  no programs found")
            return
        for p in data["records"]:
            s = p.get("status", {}).get("value", "?")
            t = p.get("type", {}).get("value", "?")
            f = "•" if p.get("following") else ""
            print(f"  {f} {p['name']:<40} {p['handle']:<25} {s:<12}")
        print(f"\n  {len(data['records'])} programs")
        return

    if not webhook:
        print("error: no discord webhook — set DISCORD_WEBHOOK_URL or add it to config.yaml")
        sys.exit(1)

    if args.reset:
        state_path = "state/state.json"
        os.makedirs("state", exist_ok=True)
        with open(state_path, "w") as f:
            json.dump({"last_check": int(datetime.now().timestamp()), "notified": {}}, f)
        print("  state reset")

    since_ts = None
    if args.since:
        try:
            since_ts = int(args.since)
        except ValueError:
            since_ts = int(datetime.fromisoformat(args.since).timestamp())
        print(f"  since: {args.since}")

    monitor.run(catchup=args.catchup, since=since_ts)


if __name__ == "__main__":
    main()
