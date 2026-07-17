#!/usr/bin/env python3
"""Launch the local FXD engineering review application from the repository root."""
from pathlib import Path
import sys
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fxd_qt_app import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch the FXD local engineering workbench.")
    parser.add_argument("--step", type=Path, help="load a STEP file immediately after launch")
    args = parser.parse_args()
    raise SystemExit(main(args.step))
