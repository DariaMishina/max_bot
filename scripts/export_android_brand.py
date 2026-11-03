"""The RuStore listing icon is the raster avatar, not the in-app vector mark.

Source of truth: docs/design/workshop-refinement/tarot-sphere-rustore-icon.png
This script no longer rebuilds that file from sphere_mark.xml.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "docs/design/workshop-refinement/tarot-sphere-rustore-icon.png"


def main():
    if not ICON.is_file():
        sys.exit(f"missing RuStore icon: {ICON}")
    print(ICON)


if __name__ == "__main__":
    main()
