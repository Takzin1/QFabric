"""Audit paper-author simulation CSV without executing their code.

Input is a pinned GitHub blob of authors' *simulation summaries*, not
experimental qubit measurements or independent reproduction of the paper.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from typing import Any

from qfabric.gari_reference import per_round_logical_error_rate

SOURCE_REPO = "https://github.com/astra-decoders/gari-nms"
SOURCE_COMMIT = "6380d52e76d8c9cb0b4eedf3e8d2429b24cef78d"
SOURCE_PATH = "data/final/BB_final_google_si1000_data.csv"
SOURCE_BLOB_SHA1 = "f9cadb313eb60a71fb1c9fc893c4b9d288178502"
MAX_CSV_BYTES = 64 * 1024
FIELDS = ("shots", "errors", "discards", "seconds", "decoder",
          "strong_id", "json_metadata", "custom_counts")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in items:
        if key in obj:
            raise ValueError("duplicate field in metadata")
        obj[key] = value
    return obj


def _no_nonfinite(value: str) -> None:
    raise ValueError(f"nonfinite JSON number {value}")


def parse_author_si1000_csv(raw: bytes, *, enforce_upstream_blob: bool = True) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_CSV_BYTES:
        raise ValueError("bounded UTF-8 CSV bytes required")
    blob_sha = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    if enforce_upstream_blob and blob_sha != SOURCE_BLOB_SHA1:
        raise ValueError("CSV bytes differ from upstream pinned Git blob")
    text = raw.decode("utf-8", errors="strict")
    reader = csv.DictReader(io.StringIO(text), skipinitialspace=True, strict=True)
    if reader.fieldnames is None or tuple(x.strip() for x in reader.fieldnames) != FIELDS:
        raise ValueError("unexpected author CSV schema")
    records = []
    for row in reader:
        if None in row or not any((v or "").strip() for v in row.values()):
            if not any((v or "").strip() for v in row.values()):
                continue
            raise ValueError("CSV row has excess columns")
        if len(records) >= 100:
            raise ValueError("CSV record count exceeds audit limit")
        n, k, discards = (int(row[name].strip()) for name in ("shots", "errors", "discards"))
        if not 0 <= k <= n // 2 or n <= 0 or discards < 0:
            raise ValueError("invalid simulation count values")
        runtime = float(row["seconds"].strip())
        if not math.isfinite(runtime) or runtime < 0:
            raise ValueError("invalid runtime")
        label = row["decoder"].strip()
        strong_id = row["strong_id"].strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", label):
            raise ValueError("malformed decoder label")
        if not re.fullmatch(r"[a-f0-9]{64}", strong_id):
            raise ValueError("malformed Sinter strong_id")
        metadata = json.loads(
            row["json_metadata"], object_pairs_hook=_pairs,
            parse_constant=_no_nonfinite,
        )
        if not isinstance(metadata, dict) or set(metadata) != {"d", "p", "rounds"}:
            raise ValueError("missing source simulation metadata")
        distance, rounds, p = metadata["d"], metadata["rounds"], metadata["p"]
        if (
            type(distance) is not int or distance not in {6, 10, 12}
            or type(rounds) is not int or rounds != distance
            or type(p) not in (float, int) or not math.isfinite(p)
            or not 0 < p <= 0.1
        ):
            raise ValueError("invalid code distance, rounds or noise probability")
        counts_text = (row["custom_counts"] or "").strip()
        counts = json.loads(
            counts_text, object_pairs_hook=_pairs, parse_constant=_no_nonfinite
        ) if counts_text else None
        if counts is not None and not isinstance(counts, dict):
            raise ValueError("unexpected custom_counts")
        records.append({
            "decoder": label,
            "strongId": strong_id,
            "shots": n,
            "errors": k,
            "discards": discards,
            "runtimeSecondsAuthorsClaim": runtime,
            "codeDistance": distance,
            "physicalErrorProbability": p,
            "syndromeRounds": rounds,
            "failureRatioFromPublishedCounts": k / n,
            "perRoundLERFromPublishedCounts": per_round_logical_error_rate(k, n, rounds),
            "customCountsAuthorsClaim": counts,
        })
    if not records:
        raise ValueError("no simulation records in upstream summary")
    return {
        "schemaVersion": "qfabric-gari-author-csv-audit/1",
        "origin": "authors_published_simulation_summary",
        "upstreamRepository": SOURCE_REPO,
        "upstreamCommit": SOURCE_COMMIT,
        "upstreamPath": SOURCE_PATH,
        "upstreamGitBlobSha1": SOURCE_BLOB_SHA1,
        "rawSha256Computed": hashlib.sha256(raw).hexdigest(),
        "upstreamBlobMatched": blob_sha == SOURCE_BLOB_SHA1,
        "records": records,
        "authorCodeExecuted": False,
        "newSimulationPerformed": False,
        "measurementVerified": False,
        "paperNumericsFullyReproduced": False,
        "fpgaMeasured": False,
    }
