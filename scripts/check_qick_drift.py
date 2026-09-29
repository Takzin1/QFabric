"""Check a local QICK checkout against QFabric's pinned API contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qfabric.drift import format_report, inspect_source_tree, load_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Path to a local checkout of openquantumhardware/qick",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("compat/qick/api_contract.json"),
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    report = inspect_source_tree(args.root, manifest)
    print(format_report(report))
    return 0 if report.compatible else 1


if __name__ == "__main__":
    sys.exit(main())
