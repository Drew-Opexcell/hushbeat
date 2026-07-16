# hushbeat

Monitoring that only speaks when something is wrong. One file, stdlib only.

I run a fleet of automations for clients (mail pipelines, CRM syncs, schedulers). The
failure mode that actually hurts was never a loud crash; it was a system going quietly
dark and nobody noticing for days. This is the pattern I use against that, extracted
into a standalone tool.

## The two checks

**URL checks**: is the endpoint reachable? A 4xx counts as alive, because
reachable-but-auth-gated is not an outage; only 5xx and unreachable are failures.
This one decision kills most false pages.

**Ping checks (dead-man's switch)**: for everything a URL can't see. Each cron job or
scheduled task calls `hushbeat ping <name>` at the end of a successful run. `hushbeat
check` flags any ping older than its max age. A sleeping machine, a disabled scheduler,
and a script that crashes on every run are indistinguishable from outside, and all three
show up the same way: stale.

Rule of thumb for max ages: about 2x the job's cadence, so one hiccup doesn't page you.

## Setup

`hushbeat.json`:

```json
{
  "urls": [
    {"name": "api", "url": "https://api.example.com/health"},
    {"name": "site", "url": "https://example.com"}
  ],
  "pings": {
    "nightly-backup": 30,
    "hourly-sync": 3
  },
  "webhook": "https://hooks.slack.com/services/T000/B000/XXXX"
}
```

In each cron job, after success:

```
hushbeat ping nightly-backup
```

Then check on a schedule (cron, Task Scheduler, or CI):

```
hushbeat check
```

Prints nothing and exits 0 when everything is healthy. On failure it prints what's
down, POSTs the list to the webhook if configured, and exits 1.

## Why the exit code matters

Run the check from GitHub Actions (or any CI with notifications) and the alert path
survives its own delivery channel dying: if the webhook is misconfigured or the token
expired, the non-zero exit still fails the workflow and CI emails you. Never depend on
a single channel to tell you the monitoring is broken.

```yaml
on:
  schedule: [{cron: "0 13 * * *"}]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python hushbeat.py check
```

## Tests

```
python -m unittest test_hushbeat
```

## License

MIT
