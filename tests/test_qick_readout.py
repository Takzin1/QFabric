"""Fail-closed tests for QICK readout preflight; no QICK import or hardware."""

import math

import pytest

from qfabric.errors import ErrorCode, ValidationError
from qfabric.profiles.qick_readout import (
    MAX_READOUT_SHOTS,
    QickReadoutIntent,
    QickReadoutPlanner,
)


def _intent(**overrides):
    data = {
        "device_id": "qick-demo-no-hardware",
        "readout_gen_ch": 0,
        "adc_channels": (0, 2),
        "frequency_mhz": 100.0,
        "capture_length_us": 2.0,
        "trigger_offset_us": 0.0,
        "shots": 1024,
        "calibration_ref": "unverified",
    }
    data.update(overrides)
    return QickReadoutIntent(**data)


def _planner():
    return QickReadoutPlanner(
        device_id="qick-demo-no-hardware",
        generator_channels=(0, 3),
        adc_channels=(0, 1, 2),
    )


def test_readout_intent_is_data_only_not_an_acquisition_call() -> None:
    plan = _planner().plan(_intent())
    assert not hasattr(plan, "calls")
    assert not hasattr(plan, "execute")
    payload = plan.to_dict()
    assert payload["kind"] == "qick_readout_proposal"
    assert payload["status"] == "intent_only"
    assert payload["hardwareExecuted"] is False
    assert payload["provenance"] == "synthetic_intent"
    assert payload["shots"] == 1024
    assert payload["adc_channels"] == [0, 2]
    assert "declare_readout" in payload["note"]
    assert "qick_reference_commit" in payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("device_id", ""),
        ("readout_gen_ch", True),
        ("readout_gen_ch", -1),
        ("adc_channels", (0, 0)),
        ("adc_channels", (False,)),
        ("adc_channels", ()),
        ("adc_channels", (0.1,)),
        ("frequency_mhz", math.nan),
        ("frequency_mhz", math.inf),
        ("frequency_mhz", -0.1),
        ("capture_length_us", 0.0),
        ("capture_length_us", math.inf),
        ("capture_length_us", 1_000_000.1),
        ("trigger_offset_us", -1.0),
        ("trigger_offset_us", math.nan),
        ("shots", True),
        ("shots", 0),
        ("shots", MAX_READOUT_SHOTS + 1),
        ("shots", 1.5),
        ("calibration_ref", ""),
    ],
)
def test_rejects_invalid_readout_fields(field, value) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _intent(**{field: value})
    assert exc_info.value.code is ErrorCode.INVALID_MESSAGE


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"device_id": "other-device"}, ErrorCode.DEVICE_MISMATCH),
        ({"readout_gen_ch": 7}, ErrorCode.CAPABILITY_MISMATCH),
        ({"adc_channels": (4,)}, ErrorCode.CAPABILITY_MISMATCH),
    ],
)
def test_readout_planner_fail_closed_on_unknown_device_and_channels(overrides, code) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _planner().plan(_intent(**overrides))
    assert exc_info.value.code is code


@pytest.mark.parametrize(
    "allowlists",
    [
        {"generator_channels": (), "adc_channels": (0,)},
        {"generator_channels": (0, 0), "adc_channels": (0,)},
        {"generator_channels": (0,), "adc_channels": (0, 0)},
    ],
)
def test_invalid_config_is_rejected(allowlists) -> None:
    with pytest.raises(ValueError):
        QickReadoutPlanner(device_id="demo", **allowlists)
