"""GPIO sanity scanner. Touch a GND wire to each listed BCM pin in turn and
watch the corresponding column flip 1 -> 0 while held. Any pin that stays at
1 is floating (bad solder joint, wrong header position, or dead pin).

Pins covered:
  17           -- v1 alarm contact
  8,9,10,11    -- SPI (CE0, MISO, MOSI, SCLK) for MCP2515 in v2
  25           -- spare interrupt line for MCP2515 in v2
"""

import time
import RPi.GPIO as G

PINS = [8, 9, 10, 11, 17, 25]

G.setmode(G.BCM)
for p in PINS:
    G.setup(p, G.IN, pull_up_down=G.PUD_UP)

header = "  ".join(f"BCM{p:>2}" for p in PINS)
print("Touch a GND wire to each BCM pin in turn. Expect 1 -> 0 while held.")
print("Header: " + header)

try:
    while True:
        vals = [G.input(p) for p in PINS]
        print("Read:   " + "  ".join(f"  {v}  " for v in vals), end="\r", flush=True)
        time.sleep(0.1)
except KeyboardInterrupt:
    print()
    G.cleanup()
