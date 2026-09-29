from __future__ import annotations

from pathlib import Path

from qfabric.drift import (
    extract_method_parameters,
    inspect_source_tree,
    load_manifest,
)
from qfabric.profiles.qick import (
    QICK_REFERENCE_COMMIT,
    QICK_REFERENCE_REPOSITORY,
)

FIXTURE_ROOT = Path("tests/fixtures/qick_contract")
MANIFEST_PATH = Path("compat/qick/api_contract.json")


def test_pinned_fixture_matches_manifest() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    report = inspect_source_tree(FIXTURE_ROOT, manifest)

    assert report.compatible is True
    assert len(report.findings) == 3
    assert all(finding.compatible for finding in report.findings)


def test_manifest_and_qick_profile_share_the_same_reference() -> None:
    manifest = load_manifest(MANIFEST_PATH)

    assert manifest.reference_repository == QICK_REFERENCE_REPOSITORY
    assert manifest.reference_commit == QICK_REFERENCE_COMMIT


def test_extracts_var_keyword_contract() -> None:
    source = """
class QickProgramV2:
    def add_pulse(self, ch, name, **kwargs):
        pass
"""
    observed = extract_method_parameters(
        source,
        class_name="QickProgramV2",
        method_name="add_pulse",
    )

    assert observed is not None
    assert [(item.name, item.kind, item.default) for item in observed] == [
        ("self", "positional", None),
        ("ch", "positional", None),
        ("name", "positional", None),
        ("kwargs", "var_keyword", None),
    ]


def test_reports_compatible_signature_drift(tmp_path: Path) -> None:
    manifest = load_manifest(MANIFEST_PATH)

    qick_asm = tmp_path / "qick_lib/qick/qick_asm.py"
    qick_asm.parent.mkdir(parents=True)
    qick_asm.write_text(
        """
class AbsQickProgram:
    def declare_gen(
        self,
        ch,
        nqz=2,
        mixer_freq=None,
        mixer_fullscale=False,
        mux_freqs=None,
        mux_gains=None,
        mux_phases=None,
        ro_ch=None,
        new_optional=None,
    ):
        pass
""",
        encoding="utf-8",
    )

    asm_v2 = tmp_path / "qick_lib/qick/asm_v2.py"
    asm_v2.write_text(
        """
class AsmV2:
    def pulse(self, ch, name, t=0, tag=None):
        pass

class QickProgramV2:
    def add_pulse(self, ch, name, **kwargs):
        pass
""",
        encoding="utf-8",
    )

    report = inspect_source_tree(tmp_path, manifest)

    assert report.compatible is True
    assert report.drifted is True
    changed = [finding for finding in report.findings if finding.drifted]
    assert len(changed) == 1
    assert changed[0].method_name == "declare_gen"
    assert "remains compatible" in changed[0].detail


def test_detects_breaking_required_keyword_drift(tmp_path: Path) -> None:
    manifest = load_manifest(MANIFEST_PATH)

    qick_asm = tmp_path / "qick_lib/qick/qick_asm.py"
    qick_asm.parent.mkdir(parents=True)
    qick_asm.write_text(
        """
class AbsQickProgram:
    def declare_gen(self, channel, nqz=1):
        pass
""",
        encoding="utf-8",
    )

    asm_v2 = tmp_path / "qick_lib/qick/asm_v2.py"
    asm_v2.write_text(
        """
class AsmV2:
    def pulse(self, ch, name, t=0, tag=None):
        pass

class QickProgramV2:
    def add_pulse(self, ch, name, **kwargs):
        pass
""",
        encoding="utf-8",
    )

    report = inspect_source_tree(tmp_path, manifest)

    assert report.compatible is False
    assert report.drifted is True
    failing = [finding for finding in report.findings if not finding.compatible]
    assert len(failing) == 1
    assert failing[0].method_name == "declare_gen"
    assert failing[0].missing_keywords == frozenset({"ch"})


def test_detects_missing_method(tmp_path: Path) -> None:
    manifest = load_manifest(MANIFEST_PATH)

    qick_asm = tmp_path / "qick_lib/qick/qick_asm.py"
    qick_asm.parent.mkdir(parents=True)
    qick_asm.write_text(
        """
class AbsQickProgram:
    pass
""",
        encoding="utf-8",
    )

    asm_v2 = tmp_path / "qick_lib/qick/asm_v2.py"
    asm_v2.write_text(
        """
class AsmV2:
    def pulse(self, ch, name, t=0, tag=None):
        pass

class QickProgramV2:
    def add_pulse(self, ch, name, **kwargs):
        pass
""",
        encoding="utf-8",
    )

    report = inspect_source_tree(tmp_path, manifest)

    assert report.compatible is False
    failing = [finding for finding in report.findings if not finding.compatible]
    assert len(failing) == 1
    assert failing[0].detail == "class or method is missing"
