"""Synthetic HDF5 data; authentic hardware traces are never put in GitHub."""
from __future__ import annotations

import math
from pathlib import Path

import h5py
import numpy as np
import pytest

from qfabric.caune_hdf5 import HDF5_SHA256, audit_fast_feedback_hdf5


def _fixture(directory: Path) -> Path:
    path = directory / "fast_feedback_raw_data.h5"
    with h5py.File(path, "w") as f:
        session = f.create_group("session_data")
        session.create_dataset("qpu_name", data="Ankaa-2",
                               dtype=h5py.string_dtype(encoding="utf-8"))
        for i in range(8):
            n = i + 2
            result = f.create_group(f"circuit_{i}/result")
            result.attrs["rounds"] = str(n)
            result.create_dataset("time", data=np.full(1000, 300 + 100 * n,
                                                     dtype="int32"))
            names = (["DASR", "DSR"] + [f"MGUEVCNTR_{j}" for j in range(5)]
                     + ["SYNG_0_lower"] + (["SYNG_0_upper"] if n > 6 else []))
            registers = result.create_dataset(
                "decoder_shot_results", data=np.zeros((1000, len(names)), dtype="int32")
            )
            registers.attrs.create("decoder_registers", names,
                                   dtype=h5py.string_dtype("utf-8"))
            hard = result.create_group("hard_measurements")
            soft = result.create_group("soft_measurements")
            for qubit in ("36", "37", "38", "43", "45", "50", "51", "52"):
                cols = n + 1 if qubit == "50" else (
                    n if qubit in {"36", "38", "52"} else 1
                )
                hard.create_dataset(qubit, data=np.zeros((1000, cols), dtype="uint8"))
                soft.create_dataset(qubit, data=np.zeros((1000, cols), dtype="complex64"))
        reference = f.create_group("reference_data")
        fid = reference.create_group("measurement_fidelity")
        for state, ones in (("ones", 9466), ("zeros", 328)):
            result = fid.create_group(f"{state}/result")
            bits = np.zeros((10000, 1), dtype="uint8")
            bits[:ones] = 1
            result.create_dataset("hard_measurements/50", data=bits)
        # Independent synthetic, balanced prepared-state references.
        double = reference.create_group("double_measurement")
        for state, prepared, cells in (
            ("zeros", 0, ((9300, 400), (290, 10))),
            ("ones", 1, ((400, 100), (1000, 8500))),
        ):
            result = double.create_group(f"{state}/result")
            result.attrs["init"] = prepared
            observations = np.concatenate([
                np.tile(np.array([[first, second]], dtype="uint8"), (count, 1))
                for first, counts in enumerate(cells)
                for second, count in enumerate(counts)
            ])
            assert observations.shape == (10000, 2)
            result.create_dataset("hard_measurements/50", data=observations)
        delays = reference.create_group("delays")
        for i in range(13):
            result = delays.create_group(f"delay_{i}/result")
            result.attrs["delay"] = str(i * 8e-7)
            population = 0.86 * math.exp(-(i * 0.8) / 13) + 0.08
            ones = round(population * 10000)
            bits = np.zeros((10000, 1), dtype="uint8")
            bits[:ones] = 1
            result.create_dataset("hard_measurements/50", data=bits)
    return path


def test_synthetic_hdf5_schema_t1_and_native_time_are_audited(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    report = audit_fast_feedback_hdf5(path, enforce_pin=False)
    assert report["schemaVersion"] == "qfabric-caune-2024-fast-feedback-hdf5-audit/1"
    assert report["authorReportedDevice"] == "Ankaa-2"
    assert len(report["experimentalCircuits"]) == 8
    assert report["experimentalCircuits"][7]["shotCount"] == 1000
    assert report["experimentalCircuits"][7]["rounds"] == 9
    assert report["experimentalCircuits"][7]["derivedLatencyMicroseconds"] is None
    assert report["referenceReadout"]["observedOneFrequencyPreparedOne"] == 0.9466
    assert report["referenceReadout"]["observedOneFrequencyPreparedZero"] == 0.0328
    assert report["t1RawShotReference"]["numberOfDelays"] == 13
    assert report["t1RawShotReference"]["weightedExponentialFit"]["fittedT1Us"] == (
        pytest.approx(13, abs=0.1)
    )
    reference = report["doubleMeasurementReference"]
    assert reference["twoReadoutShotsPerPreparation"] == 10000
    assert reference["pooledFirstThenSecondCounts"] == [[9700, 500], [1290, 8510]]
    assert reference["pooledFirstStateConditionals"][0][
        "inferredPostFirstStateOneFraction"
    ] == pytest.approx(0.0185, abs=0.002)
    assert reference["pooledFirstStateConditionals"][1][
        "inferredPostFirstStateOneFraction"
    ] == pytest.approx(0.955, abs=0.003)
    assert reference["uncertaintyOfDerivedStateNotPropagated"] is True
    assert report["fpgaRegisterBitfieldSemanticsVerified"] is False
    assert report["fastFeedbackLogicalCorrectionRecovered"] is False
    assert report["hdf5TimingClockUnitVerified"] is False
    assert report["newQuantumMeasurements"] is False
    assert report["qfabricHardwareExecuted"] is False


def test_real_user_hash_is_not_replaced_by_synthetic_test_bytes(tmp_path: Path) -> None:
    assert len(HDF5_SHA256) == 64
    with pytest.raises(ValueError, match="SHA-256"):
        audit_fast_feedback_hdf5(_fixture(tmp_path))


def test_external_hdf5_link_never_followed(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    with h5py.File(path, "r+") as f:
        del f["circuit_0/result/time"]
        f["circuit_0/result/time"] = h5py.ExternalLink(
            "/tmp/untrusted-external.h5", "evil"
        )
    with pytest.raises(ValueError, match="nonlocal HDF5 link"):
        audit_fast_feedback_hdf5(path, enforce_pin=False)


def test_nonbinary_hard_measurement_fails(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    with h5py.File(path, "r+") as f:
        f["reference_data/measurement_fidelity/ones/result/hard_measurements/50"][0] = 2
    with pytest.raises(ValueError, match="not binary"):
        audit_fast_feedback_hdf5(path, enforce_pin=False)


def test_wrong_fpga_register_shape_fails(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    with h5py.File(path, "r+") as f:
        del f["circuit_2/result/decoder_shot_results"]
        f["circuit_2/result"].create_dataset(
            "decoder_shot_results", data=np.zeros((1000, 7), dtype="int32"),
        )
    with pytest.raises(ValueError, match="register shape"):
        audit_fast_feedback_hdf5(path, enforce_pin=False)


def test_double_measurement_rejects_bad_preparation_and_nonbinary_source(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    with h5py.File(path, "r+") as f:
        f["reference_data/double_measurement/ones/result"].attrs["init"] = 0
    with pytest.raises(ValueError, match="preparation label"):
        audit_fast_feedback_hdf5(path, enforce_pin=False)

    path = _fixture(tmp_path)
    with h5py.File(path, "r+") as f:
        f["reference_data/double_measurement/ones/result/hard_measurements/50"][0, 1] = 2
    with pytest.raises(ValueError, match="not binary"):
        audit_fast_feedback_hdf5(path, enforce_pin=False)


def test_double_measurement_rejects_wrong_shape_and_external_link(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    with h5py.File(path, "r+") as f:
        name = "reference_data/double_measurement/zeros/result/hard_measurements/50"
        del f[name]
        f.create_dataset(name, data=np.zeros((10000, 1), dtype="uint8"))
    with pytest.raises(ValueError, match="wrong binary shape"):
        audit_fast_feedback_hdf5(path, enforce_pin=False)

    path = _fixture(tmp_path)
    with h5py.File(path, "r+") as f:
        name = "reference_data/double_measurement/zeros/result/hard_measurements/50"
        del f[name]
        f[name] = h5py.ExternalLink("/tmp/untrusted.h5", "fake")
    with pytest.raises(ValueError, match="nonlocal HDF5 link"):
        audit_fast_feedback_hdf5(path, enforce_pin=False)
