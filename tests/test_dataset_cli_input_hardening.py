"""Regression tests for unsafe CLI input-file types and overflowing JSON floats."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

from qfabric.dataset_baseline import (
    compute_synthetic_count_baseline,
    validate_ai_eval_catalog,
    validate_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "quantum_dataset_cli_file_safety", ROOT / "scripts/quantum_dataset_baseline.py"
)
assert SPEC and SPEC.loader
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def _catalog() -> bytes:
    return (ROOT / "data/quantum_dataset_candidates.json").read_bytes()


@pytest.mark.parametrize("mode", ["validate-catalog", "validate-ai-catalog", "synthetic-baseline"])
@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="named pipes are unsupported")
def test_cli_rejects_named_pipe_inputs_without_blocking(tmp_path: Path, mode: str) -> None:
    fifo = tmp_path / "untrusted.json"
    os.mkfifo(fifo)
    assert cli.main([mode, str(fifo)]) == 1


@pytest.mark.parametrize("mode", ["validate-catalog", "validate-ai-catalog", "synthetic-baseline"])
def test_cli_rejects_symlink_inputs(tmp_path: Path, mode: str) -> None:
    link = tmp_path / "source.json"
    link.symlink_to(ROOT / "data/quantum_dataset_candidates.json")
    assert cli.main([mode, str(link)]) == 1


def test_cli_rejects_fifo_manifest_in_local_file_audit(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("named pipes are unsupported")
    fifo = tmp_path / "catalog.json"
    source = tmp_path / "source.csv"
    os.mkfifo(fifo)
    source.write_bytes(b"synthetic fixture, not a measurement")
    assert cli.main(["audit-local-file", str(fifo), "QRD-001", str(source)]) == 1


def test_cli_rejects_oversized_manifest(tmp_path: Path) -> None:
    large = tmp_path / "too_big.json"
    with large.open("wb") as target:
        target.truncate(128 * 1024 + 1)
    assert cli.main(["validate-catalog", str(large)]) == 1


def test_cli_regular_files_still_validate() -> None:
    assert cli.main([
        "validate-catalog", str(ROOT / "data/quantum_dataset_candidates.json")
    ]) == 0
    assert cli.main([
        "validate-ai-catalog", str(ROOT / "data/quantum_ai_eval_candidates.json")
    ]) == 0
    assert cli.main([
        "synthetic-baseline", str(ROOT / "tests/fixtures/quantum_counts.synthetic.json")
    ]) == 0


@pytest.mark.parametrize(
    ("validator", "raw"),
    [
        (
            validate_catalog,
            _catalog().replace(b'"priority": "P0"', b'"priority": 1e309', 1),
        ),
        (
            validate_ai_eval_catalog,
            b'{"schemaVersion":1e309}',
        ),
        (
            compute_synthetic_count_baseline,
            b'{"schemaVersion":"qfabric-synthetic-counts/1","kind":"synthetic_fixture",'
            b'"groups":[{"name":"g","shots":1e309,"errors":0}]}',
        ),
    ],
)
def test_dataset_json_rejects_exponent_overflow_during_parsing(validator, raw) -> None:
    with pytest.raises(ValueError, match="finite floating-point range"):
        validator(raw)


def test_dataset_validation_does_not_relabel_provenance() -> None:
    catalog = validate_catalog(_catalog())
    assert all(x["ingestStatus"] == "not_downloaded" for x in catalog["datasets"])
    assert all(x["rawSha256"] is None for x in catalog["datasets"])
    assert all(x["unitStatus"] == "unverified" for x in catalog["datasets"])


def test_extra_nested_keys_remain_rejected() -> None:
    catalog = json.loads(_catalog())
    catalog["datasets"][0]["rawFileAuthenticated"] = True
    with pytest.raises(ValueError, match="fields"):
        validate_catalog(json.dumps(catalog).encode())
