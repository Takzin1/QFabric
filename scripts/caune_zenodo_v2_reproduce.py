"""CLI to authenticate Caune Zenodo v2 downloads and run offline QFabric audits.

Run from repository root:
  python scripts/caune_zenodo_v2_reproduce.py --mode metadata
  python scripts/caune_zenodo_v2_reproduce.py --mode reproduce --output /tmp/report.json

Only the derived JSON report survives: originals are temporary and removed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qfabric.caune_zenodo import load_manifest, reproduce, validate_manifest

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[1] / "data" / "caune_zenodo_v2_source_manifest.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("metadata", "reproduce"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "reproduce" and args.output is None:
        parser.error("--output is required for source download/reproduction")
    if args.output is not None and args.output.exists():
        parser.error("evidence report must not overwrite an existing file")
    manifest = load_manifest(args.manifest)
    if args.mode == "metadata":
        entries = validate_manifest(manifest)
        print(json.dumps({
            "record": manifest["sourceRecordUrl"],
            "pinnedVersion": "v2",
            "allowlistedFileCount": len(entries),
            "filesDownloaded": 0,
            "rawRedistributionAllowed": False,
        }, indent=2))
        return
    result = reproduce(manifest)
    with args.output.open("x", encoding="utf-8") as report:
        json.dump(result, report, indent=2, ensure_ascii=False, allow_nan=False)
        report.write("\n")
    print(json.dumps({
        "report": str(args.output),
        "zenodoRecord": result["pinnedZenodoRecord"],
        "publisherMd5Matches": result["publisherMd5Matches"],
        "existingUserCopySha256PinsAllMatched": result["existingUserCopySha256PinsAllMatched"],
        "rawFilesCommitted": False,
        "quantumHardwareReexecuted": False,
    }, indent=2))


if __name__ == "__main__":
    main()
