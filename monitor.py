#!/usr/bin/env python3
"""Ingar v1: poll the freezer's Remote Alarm dry contact and notify Slack on
state changes. Also posts a periodic heartbeat to the same Slack channel so
lab members can eyeball that the monitor is still alive.

Wiring (fail-safe):
  Freezer NC --- GPIO pin (input, internal pull-up enabled)
  Freezer C  --- Pi GND
  NO         --- unused

Normal:  NC<->C closed -> pin reads LOW
Alarm:   relay opens (alarm OR power loss) -> pin reads HIGH
"""

import json
import os
import signal
import sys
import time
import urllib.request

ALARM_PIN = int(os.environ.get("INGAR_ALARM_PIN", "17"))
POLL_INTERVAL_S = float(os.environ.get("INGAR_POLL_INTERVAL_S", "1.0"))
DEBOUNCE_S = float(os.environ.get("INGAR_DEBOUNCE_S", "2.0"))
HEARTBEAT_INTERVAL_S = float(os.environ.get("INGAR_HEARTBEAT_INTERVAL_S", "21600"))

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
TESTING = os.environ.get("INGAR_TESTING", "0") == "1"
STUB_GPIO = os.environ.get("STUB_GPIO", "0") == "1"
STUB_STATE_FILE = os.environ.get("STUB_STATE_FILE", "/tmp/ingar_stub_state")


def log(msg):
    print(f"[ingar] {msg}", flush=True)


def slack(msg):
    prefix = "[TESTING] " if TESTING else ""
    text = f"{prefix}{msg}"
    log(f"slack: {text}")
    if not SLACK_WEBHOOK_URL:
        log("SLACK_WEBHOOK_URL not set; skipping post")
        return
    try:
        data = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception as e:
        log(f"slack post failed: {e}")


def setup_gpio():
    if STUB_GPIO:
        log(f"STUB_GPIO=1; reading state from {STUB_STATE_FILE} (0=normal, 1=alarm)")
        return None
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(ALARM_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    log(f"GPIO ready on BCM pin {ALARM_PIN} (pull-up)")
    return GPIO


def read_alarm(GPIO):
    """Return True if the freezer is in alarm state."""
    if STUB_GPIO:
        try:
            with open(STUB_STATE_FILE) as f:
                return f.read().strip() == "1"
        except FileNotFoundError:
            return False
    return GPIO.input(ALARM_PIN) == 1  # HIGH = open contact = alarm


def main():
    log(f"starting (TESTING={TESTING}, STUB_GPIO={STUB_GPIO}, pin={ALARM_PIN})")

    GPIO = setup_gpio()

    def shutdown(signum, frame):
        log(f"received signal {signum}; exiting")
        if GPIO is not None:
            GPIO.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        current = read_alarm(GPIO)
    except Exception as e:
        log(f"initial read failed: {e}; assuming normal")
        current = False

    slack(
        f"Ingar online. Initial state: {'ALARM' if current else 'normal'}."
    )
    last_heartbeat = time.monotonic()

    pending_state = current
    pending_since = None

    while True:
        try:
            reading = read_alarm(GPIO)

            # debounce: a candidate change must persist DEBOUNCE_S before we accept it
            if reading != current:
                if pending_state != reading:
                    pending_state = reading
                    pending_since = time.monotonic()
                elif time.monotonic() - pending_since >= DEBOUNCE_S:
                    current = reading
                    pending_since = None
                    if current:
                        slack(":rotating_light: FREEZER ALARM (or power loss). "
                              "Check the CS200 immediately.")
                    else:
                        slack(":white_check_mark: Freezer back to normal.")
            else:
                pending_state = current
                pending_since = None

            if time.monotonic() - last_heartbeat >= HEARTBEAT_INTERVAL_S:
                state = "ALARM" if current else "normal"
                slack(f":heartbeat: heartbeat -- monitor alive, state: {state}")
                last_heartbeat = time.monotonic()

        except Exception as e:
            log(f"loop error: {e}")

        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    main()
