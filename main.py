#!/usr/bin/env python3
"""Video Compiler entry point.

Interactive:      python main.py
Non-interactive:  python main.py -r maths -s 01:30 -e 58:00 -o maths_week1
Batch:            python main.py --batch -s 01:30 -e 58:00

See README.md and pipeline.md for the full specification.
"""

import sys

from vcompiler.cli import main

if __name__ == "__main__":
    sys.exit(main())
