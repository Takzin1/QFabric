"""Compatibility drift inspection for pinned backend API contracts."""

from __future__ import annotations

import ast
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ParameterContract:
    name: str
    kind: str
    default: str | None


@dataclass(frozen=True, slots=True)
class MethodContract:
    path: str
    class_name: str
    method_name: str
    required_keywords: frozenset[str]
    baseline_parameters: tuple[ParameterContract, ...]


@dataclass(frozen=True, slots=True)
class ApiContractManifest:
    schema_version: int
    backend: str
    reference_repository: str
    reference_commit: str
    contracts: tuple[MethodContract, ...]


@dataclass(frozen=True, slots=True)
class DriftFinding:
    path: str
    class_name: str
    method_name: str
    compatible: bool
    drifted: bool
    detail: str
    expected: tuple[ParameterContract, ...] = ()
    observed: tuple[ParameterContract, ...] = ()
    missing_keywords: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class DriftReport:
    backend: str
    reference_repository: str
    reference_commit: str
    findings: tuple[DriftFinding, ...]

    @property
    def compatible(self) -> bool:
        return all(finding.compatible for finding in self.findings)

    @property
    def drifted(self) -> bool:
        return any(finding.drifted for finding in self.findings)


def _parse_parameter(raw: Mapping[str, Any]) -> ParameterContract:
    return ParameterContract(
        name=str(raw["name"]),
        kind=str(raw["kind"]),
        default=None if raw.get("default") is None else str(raw["default"]),
    )


def load_manifest(path: str | Path) -> ApiContractManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    contracts = tuple(
        MethodContract(
            path=str(raw["path"]),
            class_name=str(raw["class_name"]),
            method_name=str(raw["method_name"]),
            required_keywords=frozenset(str(item) for item in raw["required_keywords"]),
            baseline_parameters=tuple(
                _parse_parameter(item) for item in raw["baseline_parameters"]
            ),
        )
        for raw in payload["contracts"]
    )
    return ApiContractManifest(
        schema_version=int(payload["schema_version"]),
        backend=str(payload["backend"]),
        reference_repository=str(payload["reference_repository"]),
        reference_commit=str(payload["reference_commit"]),
        contracts=contracts,
    )


def _default_map(
    arguments: Sequence[ast.arg],
    defaults: Sequence[ast.expr],
) -> dict[str, str]:
    if not defaults:
        return {}
    offset = len(arguments) - len(defaults)
    return {
        arguments[offset + index].arg: ast.unparse(default)
        for index, default in enumerate(defaults)
    }


def _extract_parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[ParameterContract, ...]:
    params: list[ParameterContract] = []
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = _default_map(positional, node.args.defaults)

    for arg in node.args.posonlyargs:
        params.append(
            ParameterContract(
                name=arg.arg,
                kind="positional_only",
                default=defaults.get(arg.arg),
            )
        )
    for arg in node.args.args:
        params.append(
            ParameterContract(
                name=arg.arg,
                kind="positional",
                default=defaults.get(arg.arg),
            )
        )
    if node.args.vararg is not None:
        params.append(
            ParameterContract(
                name=node.args.vararg.arg,
                kind="var_positional",
                default=None,
            )
        )
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
        params.append(
            ParameterContract(
                name=arg.arg,
                kind="keyword_only",
                default=None if default is None else ast.unparse(default),
            )
        )
    if node.args.kwarg is not None:
        params.append(
            ParameterContract(
                name=node.args.kwarg.arg,
                kind="var_keyword",
                default=None,
            )
        )
    return tuple(params)


def extract_method_parameters(
    source: str,
    *,
    class_name: str,
    method_name: str,
) -> tuple[ParameterContract, ...] | None:
    tree = ast.parse(source)

    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if (
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == method_name
            ):
                return _extract_parameters(item)
    return None


def _missing_required_keywords(
    observed: tuple[ParameterContract, ...],
    required_keywords: frozenset[str],
) -> frozenset[str]:
    accepts_var_keyword = any(item.kind == "var_keyword" for item in observed)
    if accepts_var_keyword:
        return frozenset()

    accepted = {
        item.name
        for item in observed
        if item.kind in {"positional", "keyword_only"}
    }
    return frozenset(required_keywords - accepted)


def inspect_source_tree(
    root: str | Path,
    manifest: ApiContractManifest,
) -> DriftReport:
    base = Path(root)
    findings: list[DriftFinding] = []

    for contract in manifest.contracts:
        source_path = base / contract.path
        if not source_path.exists():
            findings.append(
                DriftFinding(
                    path=contract.path,
                    class_name=contract.class_name,
                    method_name=contract.method_name,
                    compatible=False,
                    drifted=True,
                    detail="source file is missing",
                    expected=contract.baseline_parameters,
                )
            )
            continue

        try:
            source = source_path.read_text(encoding="utf-8")
            observed = extract_method_parameters(
                source,
                class_name=contract.class_name,
                method_name=contract.method_name,
            )
        except (OSError, SyntaxError, UnicodeError) as exc:
            findings.append(
                DriftFinding(
                    path=contract.path,
                    class_name=contract.class_name,
                    method_name=contract.method_name,
                    compatible=False,
                    drifted=True,
                    detail=f"source could not be inspected: {exc}",
                    expected=contract.baseline_parameters,
                )
            )
            continue

        if observed is None:
            findings.append(
                DriftFinding(
                    path=contract.path,
                    class_name=contract.class_name,
                    method_name=contract.method_name,
                    compatible=False,
                    drifted=True,
                    detail="class or method is missing",
                    expected=contract.baseline_parameters,
                )
            )
            continue

        drifted = observed != contract.baseline_parameters
        missing = _missing_required_keywords(observed, contract.required_keywords)
        compatible = not missing

        if not compatible:
            detail = "required QFabric call keyword(s) are no longer accepted"
        elif drifted:
            detail = "API surface drifted but required call shape remains compatible"
        else:
            detail = "API surface matches pinned contract"

        findings.append(
            DriftFinding(
                path=contract.path,
                class_name=contract.class_name,
                method_name=contract.method_name,
                compatible=compatible,
                drifted=drifted,
                detail=detail,
                expected=contract.baseline_parameters,
                observed=observed,
                missing_keywords=missing,
            )
        )

    return DriftReport(
        backend=manifest.backend,
        reference_repository=manifest.reference_repository,
        reference_commit=manifest.reference_commit,
        findings=tuple(findings),
    )


def format_report(report: DriftReport) -> str:
    lines = [
        f"backend={report.backend}",
        f"reference_repository={report.reference_repository}",
        f"reference_commit={report.reference_commit}",
        f"compatible={str(report.compatible).lower()}",
        f"drifted={str(report.drifted).lower()}",
    ]
    for finding in report.findings:
        status = "PASS" if finding.compatible else "FAIL"
        drift = "DRIFT" if finding.drifted else "STABLE"
        lines.append(
            f"{status}/{drift} {finding.path}::"
            f"{finding.class_name}.{finding.method_name} - {finding.detail}"
        )
        if finding.missing_keywords:
            lines.append(
                f"  missing_keywords={sorted(finding.missing_keywords)!r}"
            )
        if finding.drifted:
            lines.append(f"  baseline={finding.expected!r}")
            lines.append(f"  observed={finding.observed!r}")
    return "\n".join(lines)
