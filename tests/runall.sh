#!/bin/sh
# The app's unit tests (python3.12 -m unittest). tools/smoke_pages.py --checks runs this.
cd "$(dirname "$0")/.." && PYTHONDONTWRITEBYTECODE=1 SOE2_NO_BOARD=1 exec python3.12 -m unittest discover -s tests -v
