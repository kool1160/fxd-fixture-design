#!/usr/bin/env python3
"""Run the Milestone 1 synthetic geometry proof."""

import pathlib
import sys

# Keep the proof directly executable from the repository root without a
# package install; production packaging is outside this baseline milestone.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fxd_geometry import Box, Transform, Vec3, neutral_export


def main() -> None:
    product = Box(Vec3(100, 40, 20), Transform(Vec3(50, 0, 10)))
    support = Box(Vec3(20, 40, 5), Transform(Vec3(90, 0, 15)))
    clearance_block = Box(Vec3(20, 40, 5), Transform(Vec3(150, 0, 10)))

    product_bounds = product.bounds()
    assert product_bounds.intersects(support.bounds())
    assert product_bounds.intersection(support.bounds()) is not None
    assert product_bounds.clearance_to(clearance_block.bounds()) == 0.0
    assert not product_bounds.intersects(clearance_block.bounds())

    print(neutral_export([product, support]))
    print("FXD geometry proof passed: transform, intersection, clearance, neutral export")


if __name__ == "__main__":
    main()
