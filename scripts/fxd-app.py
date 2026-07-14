#!/usr/bin/env python3
"""Launch the local FXD engineering review application from the repository root."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_app import main


if __name__ == "__main__":
    main()
