"""Pinned Zenodo v2 data intake and offline Caune reproduction for QFabric.

Only downloads 15 small, named source artifacts into a private temporary directory.
No original experiment data is written to Git, a log, or an output report.
Checks publisher-listed MD5 for downloaded bytes before executing existing
QFabric user-copy SHA-256 pinned scientific reanalysis modules.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from qfabric.caune_addenda import MEAN_NAME, STABILITY_NAME, audit_additional_summaries
from qfabric.caune_evidence import audit_uploaded_caune_bundle
from qfabric.caune_feedback import audit_caune_feedback_figures
from qfabric.caune_hdf5 import HDF5_NAME, audit_fast_feedback_hdf5
from qfabric.caune_lep import SOURCE_SPECS, audit_caune_lep_bundle

MANIFEST_SCHEMA = "qfabric-caune-zenodo-v2-source-manifest/1"
REPORT_SCHEMA = "qfabric-caune-zenodo-v2-independent-file-authentication/1"
SOURCE_RECORD = "15364358"
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 25 * 1024 * 1024
ALLOWED = frozenset({
    "decoder_timings_each_repetition.csv",
    "defect_rates_per_round.txt",
    "defect_rates_per_round_stability_9.txt",
    HDF5_NAME,
    "fig4b_decoding_response_time.csv",
    "figS4c_feedback_response_time_probability_density_data.csv",
    "figS4c_feedback_response_time_probability_density_fit_parameters.csv",
    "figS4d_t1_time_fitting.csv",
    MEAN_NAME,
    STABILITY_NAME,
    *SOURCE_SPECS,
})


def validate_manifest(data: Any) -> list[dict[str, str]]:
    """Fail closed on unknown record IDs, file names, or malformed published hashes."""
    if not isinstance(data, dict) or data.get("schemaVersion") != MANIFEST_SCHEMA:
        raise ValueError("unexpected Caune source manifest schema")
    if data.get("zenodoRecordId") != SOURCE_RECORD or data.get("sourceVersion") != "v2":
        raise ValueError("Caune source must pin Zenodo record 15364358 v2")
    if data.get("datasetLicenseReview") != "not_verified_do_not_redistribute":
        raise ValueError("dataset redistribution gate cannot be lifted by this manifest")
    if data.get("rawFilesRedistributed") is not False:
        raise ValueError("raw data may not be redistributed")
    entries = data.get("files")
    if not isinstance(entries, list) or len(entries) != len(ALLOWED):
        raise ValueError("unexpected number of Caune files")
    result = []
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"name", "publishedMd5"}:
            raise ValueError("unexpected file manifest entry")
        name, md5 = item["name"], item["publishedMd5"]
        if not isinstance(name, str) or name not in ALLOWED:
            raise ValueError("unapproved source file")
        if not isinstance(md5, str) or not re.fullmatch(r"[0-9a-f]{32}", md5):
            raise ValueError("malformed Zenodo published MD5")
        result.append({"name": name, "publishedMd5": md5})
    if {x["name"] for x in result} != ALLOWED or len(set(x["name"] for x in result)) != len(result):
        raise ValueError("missing or duplicated Caune file")
    return result


def _pinned_download_url(name: str) -> str:
    if name not in ALLOWED:
        raise ValueError("file is not allowlisted")
    return f"https://zenodo.org/records/{SOURCE_RECORD}/files/{quote(name)}?download=1"


def _trusted_download_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname == "zenodo.org" and (
        parsed.port in (None, 443)
    ) and not parsed.username and not parsed.password


def download_checked(
    entry: dict[str, str], directory: Path, *,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Stream a source file to a private directory and check publisher MD5.

    The downloader never unpickles, decompresses, imports, executes, or uploads
    source file content. Before scientific use, per-file SHA pins are checked
    by the existing offline Caune audit implementation.
    """
    name = entry["name"]
    if name not in ALLOWED or not re.fullmatch(r"[0-9a-f]{32}", entry["publishedMd5"]):
        raise ValueError("invalid file entry")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("source directory must be a real directory")
    destination = directory / name
    req = Request(
        _pinned_download_url(name),
        headers={"User-Agent": "QFabric-research-evidence/0.9 (Zenodo v2; offline audit)"},
    )
    md5, sha256 = hashlib.md5(), hashlib.sha256()  # noqa: S324 - match provider checksum
    total = 0
    try:
        with opener(req, timeout=45) as response:
            if not _trusted_download_url(response.geturl()):
                raise ValueError("Zenodo download redirected outside trusted origin")
            with destination.open("xb") as target:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > MAX_FILE_BYTES:
                        raise ValueError("download exceeds per-file size cap")
                    md5.update(block)
                    sha256.update(block)
                    target.write(block)
        if total == 0 or md5.hexdigest() != entry["publishedMd5"]:
            raise ValueError("downloaded file differs from Zenodo published MD5")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return {
        "filename": name, "bytes": total,
        "publisherMd5Matched": True,
        "sourcePublisherMd5": entry["publishedMd5"],
        "sha256OfDownloadedBytes": sha256.hexdigest(),
    }


def produce_derived_report(directory: Path, checksums: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the entire existing source-specific evidence suite against verified files."""
    def raw(name: str) -> bytes:
        return (directory / name).read_bytes()

    timing = audit_uploaded_caune_bundle(
        raw("decoder_timings_each_repetition.csv"),
        raw("defect_rates_per_round.txt"),
        raw("defect_rates_per_round_stability_9.txt"),
    )
    feedback = audit_caune_feedback_figures(
        raw("fig4b_decoding_response_time.csv"),
        raw("figS4c_feedback_response_time_probability_density_data.csv"),
        raw("figS4c_feedback_response_time_probability_density_fit_parameters.csv"),
        raw("figS4d_t1_time_fitting.csv"),
    )
    lep = audit_caune_lep_bundle({name: raw(name) for name in SOURCE_SPECS})
    addenda = audit_additional_summaries(raw(MEAN_NAME), raw(STABILITY_NAME))
    hdf5 = audit_fast_feedback_hdf5(directory / HDF5_NAME)
    return {
        "schemaVersion": REPORT_SCHEMA,
        "pinnedZenodoRecord": SOURCE_RECORD,
        "pinnedZenodoVersion": "v2",
        "publisherMd5Matches": len(checksums),
        "existingUserCopySha256PinsAllMatched": True,
        "verifiedDownloadedFiles": sorted(checksums, key=lambda row: row["filename"]),
        "derivedResearchReports": {
            "timingAndDefects": timing,
            "figureFeedback": feedback,
            "logicalErrorProbabilities": lep,
            "timingAddenda": addenda,
            "fastFeedbackHdf5": hdf5,
        },
        "fileProvenance": "downloaded_Zenodo_v2_publisher_MD5_and_QFabric_SHA256_matched",
        "zenodoDatasetRedistributionLicenseIndependentlyVerified": False,
        "sourceFilesCommittedOrIncludedInReport": False,
        "sourceCodeOrEmbeddedStimExecuted": False,
        "newHardwareMeasurementPerformed": False,
        "paperFullyReproduced": False,
        "caveats": [
            "No independently executed FPGA decoder, physical quantum device, or full experimental replication.",
            "HDF5 time units and decoder register semantics remain unresolved.",
            "Zenodo publisher MD5 is a file identity check, not proof of authorship or experiment quality.",
            "This report intentionally excludes the 130/344/741 MB stability HDF5 archives.",
        ],
    }


def reproduce(manifest: dict[str, Any], *, opener: Callable[..., Any] = urlopen) -> dict[str, Any]:
    entries = validate_manifest(manifest)
    with tempfile.TemporaryDirectory(prefix="qfabric-caune-zenodo-") as folder:
        directory = Path(folder)
        checksums = []
        total = 0
        for entry in entries:
            result = download_checked(entry, directory, opener=opener)
            total += result["bytes"]
            if total > MAX_TOTAL_BYTES:
                raise ValueError("total original data exceeds intake size cap")
            checksums.append(result)
        return produce_derived_report(directory, checksums)


def load_manifest(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024:
        raise ValueError("invalid source manifest path")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(data)
    return data
