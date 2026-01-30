import random
# No torch, no heavy libraries!
import sys

# Read board (consume input)
for line in sys.stdin:
    # Pick col 0-6
    print(random.randint(0, 6))
    sys.stdout.flush()