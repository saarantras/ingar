# Project Ingar

Remote monitoring and alerting system for an IC Biomedical K-Series cryofreezer (model 10K-CS200, serial 10S23120650) at Yale. Named after St. Ingar, the librarian saint from Rachel Hartman's *Seraphina*.

The CS200 has no standard serial interface or commercial monitoring solution. Ingar builds that infrastructure from scratch, with a possible secondary goal of publishing the reverse-engineering findings (no public documentation of the Cryowire protocol currently exists).

---

## Hardware

- **Freezer**: IC Biomedical CS200 controller
  - Cryowire (proprietary CAN-based) network on RJ-45 jacks
  - Remote Alarm dry contact: NO / C / NC terminals
  - No RS-232 or standard serial
- **Compute**: Raspberry Pi Zero 2 W, hostname `ingar`
  - OS: Raspberry Pi OS Lite 64-bit
  - 512MB RAM — Pi is the deployment target only, not a dev machine
- **Future hardware (v2)**: MCP2515 CAN breakout board

---

## Development workflow

**Do not run Claude Code on the Pi.** The Zero 2 W's 512MB RAM makes it impractical. The workflow is:

1. Edit and commit code on the laptop with Claude Code
2. Push to GitHub
3. SSH into `ingar` and pull: `ssh ingar 'cd ~/ingar && git pull && sudo systemctl restart ingar'`

The Pi is deployment-only. All development, testing logic, and tooling live on the laptop.

---

## Project phases

### v1 (current) — Basic fail alerting
**Goal**: Know immediately if the freezer alarms or loses power.

**Architecture**:
- Remote Alarm dry contact → Pi GPIO (fail-safe wiring via NC/C terminals)
- Python service loops forever: reads GPIO pin state, sends heartbeat to Healthchecks.io, posts to Slack on state changes
- Deployed as a systemd service (`ingar.service`)

**Key behavior**:
- NC↔C wiring means power loss to the freezer controller *also* trips the alarm — fail-safe by design
- Service must restart automatically on crash (`Restart=always` in systemd unit)
- Heartbeat interval: ~10 minutes; Healthchecks grace period: ~5 minutes

### v2 (planned) — Cryowire CAN protocol reverse-engineering
**Goal**: Extract temperature, liquid nitrogen level, events, and logs from the Cryowire network.

**Architecture**:
- MCP2515 breakout board connected to Pi via SPI
- Sniff and decode CAN frames from the RJ-45 Cryowire port
- No public documentation of the Cryowire protocol exists — this requires active reverse-engineering

**Possible publication**: HardwareX or protocols.io

---

## Repo structure

```
ingar/
├── monitor.py          # Main service loop (GPIO read, heartbeat, Slack alerts)
├── ingar.service       # systemd unit file
├── .env.example        # Template — copy to .env and fill in secrets
├── .gitignore          # Excludes .env, __pycache__, *.pyc
└── README.md
```

---

## Configuration / secrets

Secrets live in `~/.config/ingar/ingar.env` on the Pi (not in the repo). The systemd unit loads them via `EnvironmentFile=`.

```ini
# ~/.config/ingar/ingar.env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
HEALTHCHECKS_URL=https://hc-ping.com/...
```

```ini
# ingar.service snippet
[Service]
EnvironmentFile=/home/pi/.config/ingar/ingar.env
```



---

## Deployment

```bash
# On the Pi — standard deploy
cd ~/ingar
git pull
sudo systemctl restart ingar
journalctl -u ingar -f

# Check service status
sudo systemctl status ingar
```

The service should be enabled to start on boot:
```bash
sudo systemctl enable ingar
```

---

## GPIO wiring (v1)

- Freezer NC terminal → GPIO pin (configured with internal pull-up)
- Freezer C terminal → Pi GND
- NO terminal unused in v1

In the normal (non-alarm) state, NC↔C is closed → GPIO reads LOW. When the freezer alarms or loses power, the relay opens → GPIO floats HIGH (pulled up internally) → alert fires.

---

## Coding conventions

- Python 3, standard library where possible (`os`, `time`, `urllib.request`)
- Avoid heavy dependencies — the Pi's SD card and RAM are limited
- All secrets via environment variables, never hardcoded
- Log to stdout/stderr (systemd/journald handles capture)
- The monitor loop should be robust: catch and log exceptions, never silently die
- GPIO via `RPi.GPIO` (already available on Raspberry Pi OS)

---

## Testing without hardware

The GPIO read can be stubbed to simulate alarm/normal states for pipeline testing without physical wiring. Use an environment variable like `STUB_GPIO=1` to switch between real and simulated reads.

---

## Pi system notes

- Connect: `ssh ingar` (assumes `ingar` in `~/.ssh/config` or `/etc/hosts`)
- The Pi is on Yale's network (YaleSecure); Tailscale recommended for remote access
- `sudo` available, passwordless for the default user
- Python packages installed system-wide with `--break-system-packages` or in a venv at `~/ingar/venv`