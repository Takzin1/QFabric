from qfabric.adapters import DeterministicSimulatorAdapter
from qfabric.conformance import inspect_adapter_contract


def test_reference_adapter_passes_non_invasive_conformance() -> None:
    adapter = DeterministicSimulatorAdapter()

    report = inspect_adapter_contract(adapter)

    assert report.passed is True
    assert all(check.passed for check in report.checks)
    assert adapter.read_telemetry() == ()
