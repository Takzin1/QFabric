"""Offline, bounded audit of user-supplied Caune et al. fast-feedback raw HDF5.

This is the *only* Caune lane requiring the optional research-hdf5 extra.
Never execute embedded Stim programs, HDF5 object/string datasets, code or
external links. Source checksum refers to user copy, not authenticated Zenodo.
Output derived statistics only: do not redistribute experimental raw bytes.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from statistics import fmean
from typing import Any

from qfabric.caune_feedback import _weighted_exponential_fit

HDF5_NAME = "fast_feedback_raw_data.h5"
HDF5_SHA256 = "dd2a3d48e86ea81094b44439fb58a3d9788757e26799bd4ee7497eb94798ed08"
MAX_HDF5_BYTES = 12 * 1024 * 1024
SCHEMA = "qfabric-caune-2024-fast-feedback-hdf5-audit/1"
EXPECTED_QUBITS = {"36", "37", "38", "43", "45", "50", "51", "52"}


def _hashed_path(path: Path, *, enforce_pin: bool) -> tuple[str, int]:
    if path.name != HDF5_NAME or not path.is_file():
        raise ValueError("expected local fast_feedback_raw_data.h5")
    size = path.stat().st_size
    if not 0 < size <= MAX_HDF5_BYTES:
        raise ValueError("HDF5 exceeds audited size limit")
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            total += len(block)
            if total > MAX_HDF5_BYTES:
                raise ValueError("HDF5 grew during hash")
            digest.update(block)
    if total != size:
        raise ValueError("HDF5 changed during hash")
    actual = digest.hexdigest()
    if enforce_pin and actual != HDF5_SHA256:
        raise ValueError("HDF5 SHA-256 differs from pinned user-provided file")
    return actual, size


def _child(parent: Any, path: str, h5py: Any, *, dataset: bool = False) -> Any:
    """Traverse only hard links, avoiding HDF5 external/soft links."""
    target = parent
    for part in path.split("/"):
        if not part or part in {".", ".."}:
            raise ValueError("invalid HDF5 link path")
        if part not in target or not isinstance(target.get(part, getlink=True), h5py.HardLink):
            raise ValueError("missing group or nonlocal HDF5 link")
        target = target[part]
    expected = h5py.Dataset if dataset else h5py.Group
    if not isinstance(target, expected):
        raise TypeError("HDF5 node has incorrect type")
    return target


def _bits(dataset: Any, *, rows: int, cols: int) -> list[int]:
    if dataset.shape != (rows, cols) or dataset.dtype.kind != "u":
        raise ValueError("wrong hard-measurement shape or unsigned dtype")
    values = dataset[()]
    if not ((values == 0) | (values == 1)).all():
        raise ValueError("hard measurement is not binary")
    return values[:, -1].astype("int8").tolist()



def _audit_double_measurement_reference(
    reference: Any, h5py: Any, *, measured_zero_as_one: float,
    fitted_t1: dict[str, float],
) -> dict[str, Any]:
    """Reconstruct Appendix E2/E3 post-measurement estimates from two shots.

    Equal numbers of initially prepared 0/1 shots are pooled by the first
    measured bit. This is a source-specific descriptive calculation, not the
    original author's uncertainty propagation or a hardware reset procedure.
    """
    double = _child(reference, "double_measurement", h5py)
    counts = [[0, 0], [0, 0]]
    by_preparation = []
    for state, prepared in (("zeros", 0), ("ones", 1)):
        group = _child(double, f"{state}/result", h5py)
        if int(group.attrs.get("init", -1)) != prepared:
            raise ValueError("double-measurement preparation label mismatch")
        ds = _child(group, "hard_measurements/50", h5py, dataset=True)
        if ds.shape != (10000, 2) or ds.dtype.kind != "u":
            raise ValueError("double-measurement reference has wrong binary shape")
        observations = ds[()]
        if not ((observations == 0) | (observations == 1)).all():
            raise ValueError("double-measurement reference is not binary")
        pairs = [[0, 0], [0, 0]]
        for first, second in observations:
            i, j = int(first), int(second)
            pairs[i][j] += 1
            counts[i][j] += 1
        by_preparation.append({
            "preparedState": prepared, "shots": 10000,
            "firstThenSecondBitCounts": pairs,
        })
    t1 = fitted_t1["fittedT1Us"]
    a = fitted_t1["fittedAmplitudeA"]
    b = fitted_t1["fittedOffsetB"]
    ringdown_us = 0.5  # Appendix E3 and Fig. 4(f), 500 ns ringdown.
    excited_second_one = a * math.exp(-ringdown_us / t1) + b
    denominator = excited_second_one - measured_zero_as_one
    if denominator <= 0:
        raise ValueError("cannot infer post-measurement state from calibration")
    estimates = []
    for first in (0, 1):
        total = sum(counts[first])
        if not total:
            raise ValueError("no first-measurement outcomes for a state")
        p = counts[first][1] / total
        q = (p - measured_zero_as_one) / denominator
        if not 0 <= q <= 1:
            raise ValueError("post-measurement inference left probability domain")
        estimates.append({
            "firstMeasuredBit": first,
            "conditionalSamples": total,
            "secondMeasuredOneFraction": p,
            "inferredPostFirstStateOneFraction": q,
            "inferredPostFirstStateZeroFraction": 1 - q,
        })
    return {
        "source": "reference_data/double_measurement",
        "twoReadoutShotsPerPreparation": 10000,
        "preparedStateSpecificCounts": by_preparation,
        "pooledFirstThenSecondCounts": counts,
        "pooledFirstStateConditionals": estimates,
        "assumedBalancedPreparationForPooledReference": True,
        "ringdownDelayUsFromPaper": ringdown_us,
        "pM2OneGivenZeroFromCalibration": measured_zero_as_one,
        "pM2OneGivenOneFromT1Reference": excited_second_one,
        "equation": "Supplementary Appendix E2/E3",
        "uncertaintyOfDerivedStateNotPropagated": True,
        "qubitReinitializationPerformedByQFabric": False,
    }


def audit_fast_feedback_hdf5(
    source: str | Path, *, enforce_pin: bool = True,
) -> dict[str, Any]:
    """Validate original 8x1000 shots + reference sets without dumping samples.

    The 'time' HDF5 dataset has no explicit engineering unit; all time
    statistics of that dataset therefore remain in unconverted native units.
    """
    # Optional dependency only in a specifically requested research-data path.
    try:
        import h5py
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            'Install the optional "research-hdf5" extra to audit HDF5.'
        ) from exc

    path = Path(source)
    digest, size = _hashed_path(path, enforce_pin=enforce_pin)
    with h5py.File(path, "r") as root:
        required = {*(f"circuit_{n}" for n in range(8)), "reference_data", "session_data"}
        if set(root.keys()) != required:
            raise ValueError("unexpected HDF5 root schema")
        session = _child(root, "session_data", h5py)
        qpu_name = _child(session, "qpu_name", h5py, dataset=True)
        if qpu_name.shape != () or qpu_name.dtype.kind != "O" or qpu_name[()] != b"Ankaa-2":
            raise ValueError("unexpected author-reported QPU")
        circuits = []
        for index in range(8):
            rounds = index + 2
            result = _child(root, f"circuit_{index}/result", h5py)
            if int(result.attrs.get("rounds", "-1")) != rounds:
                raise ValueError("HDF5 circuit round mismatch")
            time_ds = _child(result, "time", h5py, dataset=True)
            if time_ds.shape != (1000,) or time_ds.dtype.kind != "i":
                raise ValueError("unexpected native timing shape")
            native = time_ds[()]
            if not (native > 0).all():
                raise ValueError("invalid native timing values")
            decoder = _child(result, "decoder_shot_results", h5py, dataset=True)
            width = 8 if rounds <= 6 else 9
            if decoder.shape != (1000, width) or decoder.dtype.kind != "i":
                raise ValueError("unexpected decoder register shape")
            register_names = [str(x) for x in decoder.attrs.get("decoder_registers", [])]
            if (
                register_names[:2] != ["DASR", "DSR"]
                or register_names[2:7] != [f"MGUEVCNTR_{i}" for i in range(5)]
                or register_names[7:] != (
                    ["SYNG_0_lower"] if width == 8 else
                    ["SYNG_0_lower", "SYNG_0_upper"]
                )
            ):
                raise ValueError("unexpected FPGA register labels")
            hard = _child(result, "hard_measurements", h5py)
            soft = _child(result, "soft_measurements", h5py)
            if set(hard.keys()) != EXPECTED_QUBITS or set(soft.keys()) != EXPECTED_QUBITS:
                raise ValueError("incomplete qubit readout channels")
            for qubit in sorted(EXPECTED_QUBITS):
                width_q = (rounds + 1 if qubit == "50" else
                           rounds if qubit in {"36", "38", "52"} else 1)
                data = _child(hard, qubit, h5py, dataset=True)
                _bits(data, rows=1000, cols=width_q)
                analog = _child(soft, qubit, h5py, dataset=True)
                if analog.shape != data.shape or analog.dtype.kind != "c":
                    raise ValueError("soft IQ channels do not match hard measurements")
                if not np.isfinite(analog[()]).all():
                    raise ValueError("nonfinite IQ source data")
            ordered = sorted(int(v) for v in native)
            circuits.append({
                "rounds": rounds, "shotCount": 1000,
                "nativeTimeUnit": "UNRESOLVED_unlabeled_HDF5_integer",
                "nativeTimeMean": fmean(ordered),
                "nativeTimeMedian": ordered[499],
                "nativeTimeP95": ordered[949],
                "nativeTimeP99": ordered[989],
                "nativeTimeMaximum": ordered[-1],
                "fpgaRegisterLabels": register_names,
                "qubitHardSoftChannelShapesValidated": True,
                "derivedLatencyMicroseconds": None,
                "perShotSyndromeInterpretationValidated": False,
            })
        reference = _child(root, "reference_data", h5py)
        fidelity = _child(reference, "measurement_fidelity", h5py)
        fractions = {}
        for state in ("ones", "zeros"):
            data = _child(
                fidelity, f"{state}/result/hard_measurements/50", h5py, dataset=True,
            )
            fractions[state] = fmean(_bits(data, rows=10000, cols=1))
        delays = _child(reference, "delays", h5py)
        points = []
        for index in range(13):
            result = _child(delays, f"delay_{index}/result", h5py)
            delay_seconds = float(result.attrs.get("delay", "nan"))
            if (not math.isfinite(delay_seconds) or
                    abs(delay_seconds - 8e-7 * index) > 1e-10):
                raise ValueError("unexpected T1 delay schedule in raw HDF5")
            hard = _child(result, "hard_measurements/50", h5py, dataset=True)
            p = fmean(_bits(hard, rows=10000, cols=1))
            sigma = math.sqrt(p * (1 - p) / 10000)
            if sigma <= 0:
                raise ValueError("degenerate T1 population measurement")
            points.append((delay_seconds * 1e6, p, sigma))
        fitted = _weighted_exponential_fit(points)
        double_measurement = _audit_double_measurement_reference(
            reference, h5py,
            measured_zero_as_one=fractions["zeros"], fitted_t1=fitted,
        )
        return {
            "schemaVersion": SCHEMA,
            "filename": HDF5_NAME, "userCopySha256": digest, "fileBytes": size,
            "paper": "https://arxiv.org/abs/2410.05202",
            "authorReportedDevice": "Ankaa-2",
            "inputKind": "historical_hardware_shots_and_reference_measurements",
            "experimentalCircuits": circuits,
            "referenceReadout": {
                "shotsPerPreparedState": 10000,
                "observedOneFrequencyPreparedOne": fractions["ones"],
                "observedOneFrequencyPreparedZero": fractions["zeros"],
                "balancedClassificationAccuracyAssumingPreparedLabels": (
                    fractions["ones"] + (1 - fractions["zeros"])
                ) / 2,
            },
            "doubleMeasurementReference": double_measurement,
            "t1RawShotReference": {
                "numberOfDelays": 13, "shotsPerDelay": 10000,
                "delayUnit": "microseconds",
                "points": [{
                    "delayUs": t, "observedOneFraction": p,
                    "binomialSeAssumingIndependentShots": sigma,
                } for t, p, sigma in points],
                "weightedExponentialFit": fitted,
                "paperReportedT1Us": 13,
                "paperReportedT1PlusMinusUs": 1,
            },
            "readoutSignalsPreservedOnlyInOriginalLocalHdf5": True,
            "embeddedStimProgramsNeverReadOrExecuted": True,
            "hdf5TimingClockUnitVerified": False,
            "fpgaRegisterBitfieldSemanticsVerified": False,
            "fastFeedbackLogicalCorrectionRecovered": False,
            "rawMeasurementProvenanceAuthenticatedAgainstZenodo": False,
            "rawFileRedistributionRightsVerified": False,
            "qfabricHardwareExecuted": False,
            "newQuantumMeasurements": False,
            "note": (
                "1000 shots per circuit and 10,000 per reference condition are "
                "author-supplied raw measurements; QFabric computed derived summaries "
                "but did not decode logical states or validate hardware timings."
            ),
        }
