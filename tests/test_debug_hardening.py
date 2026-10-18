"""Regression cases for historically missed input and evidence-safety boundaries."""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from qfabric.dataset_baseline import audit_local_candidate_file, validate_catalog
from qfabric.errors import ErrorCode, ProtocolError
from qfabric.protocol import command_envelope_from_dict, loads_command_envelope
from qfabric.version import PROTOCOL_VERSION

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "quantum_dataset_cli_hardening", ROOT / "scripts/quantum_dataset_baseline.py"
)
assert SPEC and SPEC.loader
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def _envelope() -> dict:
    return {
        "message_type": "command",
        "protocol_version": PROTOCOL_VERSION,
        "message_id": "hardening-001",
        "device_id": "sim-001",
        "sent_at": datetime(2026, 10, 19, tzinfo=UTC).isoformat(),
        "request": {
            "commands": [{
                "channel": "drive",
                "value": 0.25,
                "unit": "arb",
                "duration_s": 0.01,
                "metadata": {"phase": 0.0},
            }],
            "metadata": {"scenario": "synthetic-protocol-test"},
        },
    }


@pytest.mark.parametrize(
    "payload",
    [
        '{"message_type":"command","message_type":"command"}',
        '{"outer":{"inner":1,"inner":2}}',
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":-Infinity}',
        '{"x":1e309}',
        '{"x":-1e309}',
        '{"x":',
        "[]" * 600_000,
        "[" * 10_000,
    ],
)
def test_protocol_strict_json_rejects_bad_or_oversized_payload(payload: str) -> None:
    with pytest.raises(ProtocolError) as exc:
        loads_command_envelope(payload)
    assert exc.value.code == ErrorCode.INVALID_MESSAGE


def test_protocol_can_still_round_trip_valid_document() -> None:
    result = loads_command_envelope(json.dumps(_envelope()))
    assert result.message_id == "hardening-001"
    assert result.request.commands[0].value == 0.25


@pytest.mark.parametrize("field", ["value", "duration_s"])
@pytest.mark.parametrize("bad_number", [float("nan"), float("inf"), float("-inf"), 10**400])
def test_from_dict_catches_nonfinite_and_overflow_before_domain_models(
    field: str, bad_number: object
) -> None:
    data = _envelope()
    data["request"]["commands"][0][field] = bad_number
    with pytest.raises(ProtocolError) as exc:
        command_envelope_from_dict(data)
    assert exc.value.code == ErrorCode.INVALID_MESSAGE


def test_json_loader_rejects_overflow_float_in_real_command() -> None:
    raw = json.dumps(_envelope()).replace('"value": 0.25', '"value": 1e309')
    with pytest.raises(ProtocolError):
        loads_command_envelope(raw)


def _catalog_for_file(name: str, md5: str | None = None) -> bytes:
    master = json.loads((ROOT / "data/quantum_dataset_candidates.json").read_text())
    master["datasets"] = [master["datasets"][0]]
    master["datasets"][0]["filename"] = name
    master["datasets"][0]["publishedMd5"] = md5
    return json.dumps(master).encode()


@pytest.mark.parametrize("bad_name", ["poison\n.csv", "bad\r.csv", "bell\x07.csv"])
def test_catalog_rejects_terminal_control_chars_in_filenames(bad_name: str) -> None:
    with pytest.raises(ValueError, match="safe basename"):
        validate_catalog(_catalog_for_file(bad_name))


def test_synthetic_baseline_refuses_overwrite_of_input(tmp_path: Path) -> None:
    source = tmp_path / "fixture.json"
    original = (ROOT / "tests/fixtures/quantum_counts.synthetic.json").read_bytes()
    source.write_bytes(original)
    assert cli.main(["synthetic-baseline", str(source), "--output", str(source)]) == 1
    assert source.read_bytes() == original


def test_synthetic_baseline_refuses_overwrite_of_prior_report(tmp_path: Path) -> None:
    source = ROOT / "tests/fixtures/quantum_counts.synthetic.json"
    output = tmp_path / "audit.json"
    output.write_text("previous audit evidence\n")
    assert cli.main(["synthetic-baseline", str(source), "--output", str(output)]) == 1
    assert output.read_text() == "previous audit evidence\n"


def test_local_audit_does_not_overwrite_source_data(tmp_path: Path) -> None:
    file = tmp_path / "small.csv"
    content = b"synthetic-test-only\n"
    file.write_bytes(content)
    manifest = tmp_path / "catalog.json"
    manifest.write_bytes(_catalog_for_file(file.name))
    assert cli.main([
        "audit-local-file", str(manifest), "QRD-001", str(file),
        "--output", str(file),
    ]) == 1
    assert file.read_bytes() == content


def test_local_audit_does_not_overwrite_catalog(tmp_path: Path) -> None:
    file = tmp_path / "small.csv"
    file.write_bytes(b"fake local fixture\n")
    manifest = tmp_path / "catalog.json"
    original = _catalog_for_file(file.name)
    manifest.write_bytes(original)
    assert cli.main([
        "audit-local-file", str(manifest), "QRD-001", str(file),
        "--output", str(manifest),
    ]) == 1
    assert manifest.read_bytes() == original


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="named pipe not supported")
def test_local_byte_audit_refuses_nonregular_pipe_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "named_pipe.csv"
    os.mkfifo(fifo)
    with pytest.raises(OSError):
        audit_local_candidate_file(_catalog_for_file(fifo.name), "QRD-001", fifo)
