"""Run the bounded GARI algebra reference and the pinned author CSV audit.

No author C code, downloadable archive, QPU or FPGA code is executed.
"""
from __future__ import annotations

import json
from pathlib import Path

from qfabric.gari_evidence import parse_author_si1000_csv
from qfabric.gari_reference import build_gari_reference, four_cycles

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    reference = build_gari_reference(
        dx=[[1, 1], [1, 0]],
        dz=[[1, 0], [1, 1]],
        y_x=[[1, 1], [1, 1]],
        y_z=[[1, 0], [1, 1]],
    )
    tested = reference.assert_equivalent()
    upstream = parse_author_si1000_csv(
        (ROOT / "data/reference/gari_nms_si1000_upstream.csv").read_bytes()
    )
    result = {
        "schemaVersion": "qfabric-gari-reference-smoke/1",
        "sourceDOI": "10.1038/s41467-026-70556-3",
        "tinySyntheticErrorVectorsChecked": tested,
        "originalFourCycles": four_cycles(reference.original),
        "augmentedFourCycles": four_cycles(reference.augmented),
        "authorCSVRecordsAudited": len(upstream["records"]),
        "authorGitBlobMatched": upstream["upstreamBlobMatched"],
        "newSimulationPerformed": False,
        "fullPaperNumericalReplication": False,
        "fpgaMeasured": False,
        "hardwareExecuted": False,
    }
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
