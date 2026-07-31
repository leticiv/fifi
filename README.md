# fifi

monitor intigriti program changes and get discord alerts.

## install

```bash
pip install -r requirements.txt
```

## configure

edit `config.yaml`:

```yaml
intigriti:
  pat: "your_personal_access_token"

discord:
  webhook_url: "https://discord.com/api/webhooks/..."
```

**pat** → generate at `app.intigriti.com/profile/api`

**webhook** → discord channel → settings → integrations → webhooks

## quick test

```bash
python run.py --test
```

## usage

| command | what it does |
|---|---|
| `python run.py` | start monitoring |
| `python run.py --test` | test api + discord + list programs |
| `python run.py --list` | list all programs |
| `python run.py --catchup` | process all past activities |
| `python run.py --since 2025-06-01T14:30:00` | start from a date |

## config

`config.yaml` — all optional fields with defaults:

```yaml
intigriti:
  pat: ""                     # or INTIGRITI_PAT env

discord:
  webhook_url: ""             # or DISCORD_WEBHOOK_URL env

monitoring:
  interval: 300               # polling interval (seconds)
  follow_only: false          # monitor all programs
  activity_types:
    status_change: true
    domains_update: false
    rules_update: false

filters:
  programs: []                # empty = all. ex: ["handle-1", "handle-2"]
  statuses: [3, 4, 5]        # 3=open  4=suspended  5=closing

logging:
  level: INFO
  file: logs/monitor.log
  max_bytes: 10485760          # 10 MB
  backup_count: 3
```

## deploy

### systemd

```ini
[Unit]
Description=fifi
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/fifi
Environment=INTIGRITI_PAT=xxx
Environment=DISCORD_WEBHOOK_URL=xxx
ExecStart=/usr/bin/python3 run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### termux (android)

```bash
pkg install python
pip install -r requirements.txt
python run.py
```

### railway / render

same codebase — just set the env vars in the dashboard.

## structure

```
fifi/
├── run.py
├── config.yaml
├── requirements.txt
├── logo.svg
├── intigriti_fifi/
│   ├── api.py
│   ├── monitor.py
│   └── cli.py
├── state/
└── logs/
```
