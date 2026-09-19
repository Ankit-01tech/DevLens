#!/usr/bin/env python3
"""DevLens entry point.

Usage:
    python devlens.py /path/to/project
"""

import sys

from devlens.cli import main

if __name__ == "__main__":
    sys.exit(main())
