#!/usr/bin/env python3
"""Checks URLs and cron heartbeats, prints and alerts only on failures."""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_CONFIG = Path("hushbeat.json")
STATE_FILE = Path(".hushbeat-pings.json")


def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg.setdefault("urls", [])
    cfg.setdefault("pings", {})
    cfg.setdefault("webhook", None)
    cfg.setdefault("timeout_seconds", 20)
    return cfg


def load_state(state_path):
    p = Path(state_path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def cmd_ping(args):
    state_path = Path(args.state)
    state = load_state(state_path)
    state[args.name] = time.time()
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"ok: {args.name}")
    return 0


def check_url(entry, timeout):
    name, url = entry["name"], entry["url"]
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "hushbeat/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status >= 500:
                return f"{name}: HTTP {r.status}"
    except urllib.error.HTTPError as e:
        if e.code >= 500:
            return f"{name}: HTTP {e.code}"
        # a 4xx still means it's up
    except Exception as e:
        return f"{name}: unreachable ({str(e)[:80]})"
    return None


def check_pings(cfg, state):
    failures = []
    now = time.time()
    for name, max_age_hours in cfg["pings"].items():
        last = state.get(name)
        if last is None:
            failures.append(f"{name}: never pinged")
            continue
        age_h = (now - last) / 3600
        if age_h > max_age_hours:
            failures.append(f"{name}: last ping {age_h:.1f}h ago (max {max_age_hours}h)")
    return failures


def alert(webhook, failures):
    body = json.dumps({"text": "hushbeat: DOWN\n" + "\n".join(failures)}).encode()
    req = urllib.request.Request(webhook, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        # don't raise, the non-zero exit is the backup channel
        print(f"webhook delivery failed: {e}", file=sys.stderr)


def cmd_check(args):
    cfg = load_config(args.config)
    state = load_state(args.state)
    failures = []
    for entry in cfg["urls"]:
        f = check_url(entry, cfg["timeout_seconds"])
        if f:
            failures.append(f)
    failures.extend(check_pings(cfg, state))

    if not failures:
        return 0
    for f in failures:
        print(f"DOWN  {f}")
    if cfg["webhook"]:
        alert(cfg["webhook"], failures)
    return 1


def main():
    ap = argparse.ArgumentParser(prog="hushbeat", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--state", default=str(STATE_FILE))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ping", help="record that a job just succeeded")
    p.add_argument("name")
    sub.add_parser("check", help="check everything; exit 1 if anything is down")
    args = ap.parse_args()
    if args.cmd == "ping":
        sys.exit(cmd_ping(args))
    sys.exit(cmd_check(args))


if __name__ == "__main__":
    main()
