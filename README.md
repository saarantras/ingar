# Ingar v1

Polls the CS200 Remote Alarm dry contact via GPIO and posts to Slack on state
changes. Heartbeats Healthchecks.io so a dead Pi also pages.

See `CLAUDE.md` for project context.

## Files

- `monitor.py`     -- service loop
- `ingar.service`  -- systemd unit
- `.env.example`   -- copy to `~/.config/ingar/ingar.env`

## Testing mode

Set `INGAR_TESTING=1` and every Slack message gets a `[TESTING] ` prefix.
Leave this on through the breadboard phase and the first real-freezer test.
Flip to `0` only after you've confirmed end-to-end behavior on real hardware.

## Hardware-free test (laptop or Pi, no wiring)

```
STUB_GPIO=1 INGAR_TESTING=1 SLACK_WEBHOOK_URL=... python3 monitor.py
# in another shell:
echo 1 > /tmp/ingar_stub_state   # simulate alarm  -> Slack fires after debounce
echo 0 > /tmp/ingar_stub_state   # back to normal  -> recovery message
```

## Breadboard layout (no freezer yet)

You're simulating the freezer's NC<->C contact with a tactile switch (or a
jumper wire you pull in/out). The internal pull-up on the Pi does all the
work; you do not need an external resistor.

```
  Pi header (BCM 17 = physical pin 11)        Breadboard
  -------------------------------------       -----------------------
  Pin 11 (GPIO 17)  ----------------------->  switch leg A
  Pin 9  (GND)      ----------------------->  switch leg B
```

State table:

| Switch        | Pin reads | Means       | Slack                |
|---------------|-----------|-------------|----------------------|
| Closed (down) | LOW       | normal      | (no message)         |
| Open  (up)    | HIGH      | ALARM       | "FREEZER ALARM ..."  |

ASCII view of the breadboard:

```
       +-----------------------------+
  GPIO17 o---+                       |
             |  [ tactile switch ]   |
  GND    o---+                       |
       +-----------------------------+
```

If you only have jumper wires: touch the GPIO17 wire to the GND wire to
simulate "normal" (closed); separate them to simulate "alarm" (open).

### What to verify on the breadboard

1. Service starts, posts `[TESTING] Ingar online. Initial state: ...`.
2. Open the switch -> after ~2s debounce, `[TESTING] FREEZER ALARM ...` lands.
3. Close the switch -> `[TESTING] Freezer back to normal.` lands.
4. Pull the Pi's power -> Healthchecks alerts after the grace period.
5. Toggle rapidly (<2s) -> no Slack spam (debounce works).

Once all five pass, move to the freezer:

- Wire NC -> GPIO17, C -> GND on the CS200 Remote Alarm terminals.
- Trigger a test alarm on the controller; confirm `[TESTING]` Slack fires.
- When you're satisfied, set `INGAR_TESTING=0` and restart the service.

## Deploy on the Pi

```bash
ssh ingar
cd ~/ingar && git pull
sudo cp ingar.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ingar
journalctl -u ingar -f
```
