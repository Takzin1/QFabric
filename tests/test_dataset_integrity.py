"""Track separation and offline, bounded local-byte audit regression tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from qfabric.dataset_baseline import (
    AI_EVAL_CATALOG_VERSION,
    LOCAL_AUDIT_VERSION,
    MAX_LOCAL_FILE_BYTES,
    audit_local_candidate_file,
    validate_ai_eval_catalog,
    validate_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / "data/quantum_dataset_candidates.json").read_bytes()
AI_CATALOG = (ROOT / "data/quantum_ai_eval_candidates.json").read_bytes()


def _bytes(obj: object) -> bytes:
    return json.dumps(obj).encode()


def _fixture_catalog(*, name: str, checksum: str | None) -> bytes:
    doc = json.loads(CATALOG)
    doc["datasets"] = [doc["datasets"][0]]
    doc["datasets"][0]["filename"] = name
    doc["datasets"][0]["publishedMd5"] = checksum
    return _bytes(doc)


def test_quantum_citation_catalog_updates_are_unverified() -> None:
    doc = validate_catalog(CATALOG)
    records = {v["datasetId"]: v for v in doc["datasets"]}
    assert len(records) == 15
    assert records["QRD-017"]["recordUrl"] == "https://zenodo.org/records/11621878"
    assert records["QRD-018"]["recordUrl"] == "https://zenodo.org/records/17518472"
    assert all(v["ingestStatus"] == "not_downloaded" for v in records.values())
    assert all(v["licenseStatus"] == "unverified" for v in records.values())
    assert all(v["unitStatus"] == "unverified" for v in records.values())
    assert all(v["rawSha256"] is None for v in records.values())


def test_nvidia_qcaleval_is_not_count_or_hardware_data() -> None:
    doc = validate_ai_eval_catalog(AI_CATALOG)
    assert doc["schemaVersion"] == AI_EVAL_CATALOG_VERSION
    assert len(doc["datasets"]) == 1
    q = doc["datasets"][0]
    assert q["dataProvenance"] == "mixed_claim"
    assert q["datasetLicenseClaim"] == "CC-BY-4.0"
    assert q["codeLicenseClaim"] == "Apache-2.0"
    assert q["sourceFileSha256"] is None
    assert q["benchmarkScore"] is None
    assert q["modelEvaluated"] is False
    assert q["downloadStatus"] == "not_downloaded"
    with pytest.raises(ValueError):
        validate_catalog(AI_CATALOG)
    with pytest.raises(ValueError):
        validate_ai_eval_catalog(CATALOG)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("datasetUrl", "https://evil.invalid/datasets/nvidia/QCalEval"),
        ("evaluationCodeUrl", "https://github.com/NVIDIA/Ising"),
        ("tasks", ["Q1", "Q6"]),
        ("dataProvenance", "measured_claim"),
        ("datasetLicenseClaim", "Apache-2.0"),
        ("codeLicenseClaim", "CC-BY-4.0"),
        ("licenseClaimSource", "https://evil.invalid/readme"),
        ("datasetRevision", "fabricated-sha"),
        ("sourceFileSha256", "a" * 64),
        ("downloadStatus", "downloaded"),
        ("modelEvaluated", True),
        ("benchmarkScore", 98.5),
    ],
)
def test_qcaleval_cannot_promote_unverified_claim(field, value) -> None:
    doc = json.loads(AI_CATALOG)
    doc["datasets"][0][field] = value
    with pytest.raises(ValueError):
        validate_ai_eval_catalog(_bytes(doc))


def test_qcaleval_rejects_extra_fields_duplicate_keys_and_nonfinite() -> None:
    doc = json.loads(AI_CATALOG)
    doc["datasets"][0]["quantumHardwareVerified"] = True
    with pytest.raises(ValueError, match="fields"):
        validate_ai_eval_catalog(_bytes(doc))
    with pytest.raises(ValueError, match="duplicate"):
        validate_ai_eval_catalog(b'{"schemaVersion":1,"schemaVersion":2}')
    with pytest.raises(ValueError):
        validate_ai_eval_catalog(b'{"schemaVersion":NaN}')


def test_local_audit_matches_provider_md5_only_not_scientific_validation(tmp_path: Path) -> None:
    content = b"synthetic audit bytes only\n"
    file = tmp_path / "known.csv"
    file.write_bytes(content)
    checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
    report = audit_local_candidate_file(
        _fixture_catalog(name=file.name, checksum=checksum), "QRD-001", file
    )
    assert report["schemaVersion"] == LOCAL_AUDIT_VERSION
    assert report["byteLength"] == len(content)
    assert report["computedSha256"] == hashlib.sha256(content).hexdigest()
    assert report["publishedMd5Matched"] is True
    assert report["byteIntegrityStatus"] == "matches_provider_md5_claim"
    assert report["datasetAccepted"] is False
    assert report["dataParsed"] is False
    assert report["measurementVerified"] is False
    assert report["unitsVerified"] is False
    assert report["licenseVerified"] is False
    assert report["scientificallyReproduced"] is False
    assert report["hardwareExecuted"] is False


def test_local_audit_refuses_mismatch_and_unknown_source(tmp_path: Path) -> None:
    file = tmp_path / "known.csv"
    file.write_bytes(b"bad data")
    catalog = _fixture_catalog(name=file.name, checksum="0" * 32)
    with pytest.raises(ValueError, match="MD5"):
        audit_local_candidate_file(catalog, "QRD-001", file)
    with pytest.raises(ValueError, match="not in"):
        audit_local_candidate_file(catalog, "QRD-999", file)


def test_local_audit_without_published_checksum_remains_uncorroborated(
    tmp_path: Path,
) -> None:
    file = tmp_path / "unsourced.csv"
    file.write_bytes(b"arbitrary local bytes")
    report = audit_local_candidate_file(
        _fixture_catalog(name=file.name, checksum=None), "QRD-001", file
    )
    assert report["publishedMd5Matched"] is False
    assert report["byteIntegrityStatus"] == "no_provider_checksum_available"
    assert report["datasetAccepted"] is False


def test_local_audit_rejects_filename_symlink_and_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "known.csv"
    path.write_bytes(b"source")
    doc = _fixture_catalog(name=path.name, checksum=None)
    with pytest.raises(ValueError, match="filename"):
        audit_local_candidate_file(doc, "QRD-001", tmp_path / "other.csv")
    link = tmp_path / "link.csv"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="ordinary file"):
        audit_local_candidate_file(_fixture_catalog(name=link.name, checksum=None), "QRD-001", link)
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="bounded regular file"):
        audit_local_candidate_file(doc, "QRD-001", path)


def test_local_audit_refuses_large_file_without_parsing(tmp_path: Path) -> None:
    path = tmp_path / "known.csv"
    with path.open("wb") as out:
        out.truncate(MAX_LOCAL_FILE_BYTES + 1)
    with pytest.raises(ValueError, match="bounded regular file"):
        audit_local_candidate_file(
            _fixture_catalog(name=path.name, checksum=None), "QRD-001", path
        )
