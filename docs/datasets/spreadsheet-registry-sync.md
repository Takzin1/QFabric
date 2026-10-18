# QFabric research registry — spreadsheet-to-GitHub synchronization

**Snapshot:** 2026-10-19 · **Original:** `QFabric_Quantum_Research_Evidence_Registry_2026-10-19.xlsx`

**Important:** GitHub stores a **one-way export of spreadsheet cell values** (9 CSVs) plus a provenance manifest and consistency checks. The original binary `.xlsx` workbook is **not** uploaded here. CSV does not preserve Excel formulas, cell styling, charts, validations, or merged cells; computed formula results are values *at export time* only.

## Source and checksum

- Source workbook size: **42,441 bytes**.
- SHA-256 independently calculated on the original local workbook file:

  `624c993cf69127793459f6d030a94077d6b2f8567510f4d2936e2c59023933f7`

- [Export manifest](../../data/spreadsheets/qfabric_registry_2026-10-19/export_manifest.json) records the workbook identity, nine expected sheet layouts, and explicit `xlsxBinaryCommitted=false`, `formulasPreserved=false`, `stylesPreserved=false`.
- Research dataset contents have **not** been downloaded or scientifically checked, regardless of workbook completeness.

## Export mapping

| Original Excel tab | GitHub CSV snapshot | CSV contents |
| --- | --- | --- |
| Dashboard | [Dashboard.csv](../../data/spreadsheets/qfabric_registry_2026-10-19/Dashboard.csv) | All 31 original rows; cached dashboard figures |
| Pinned_Candidates | [Pinned_Candidates.csv](../../data/spreadsheets/qfabric_registry_2026-10-19/Pinned_Candidates.csv) | Header plus 15 candidate source rows |
| New_Source_Leads | [New_Source_Leads.csv](../../data/spreadsheets/qfabric_registry_2026-10-19/New_Source_Leads.csv) | Header plus 7 research/tool leads |
| Artifact_Leads | [Artifact_Leads.csv](../../data/spreadsheets/qfabric_registry_2026-10-19/Artifact_Leads.csv) | Header plus 12 nested artifact leads |
| AI_Benchmark | [AI_Benchmark.csv](../../data/spreadsheets/qfabric_registry_2026-10-19/AI_Benchmark.csv) | Header plus NVIDIA QCalEval candidate |
| Verification_Queue | [Verification_Queue.csv](../../data/spreadsheets/qfabric_registry_2026-10-19/Verification_Queue.csv) | Header plus 28 verification work items and computed HOLD statuses |
| Normalization_Map | [Normalization_Map.csv](../../data/spreadsheets/qfabric_registry_2026-10-19/Normalization_Map.csv) | Header plus 27 **unmapped** measurement/unit placeholders |
| Action_Plan | [Action_Plan.csv](../../data/spreadsheets/qfabric_registry_2026-10-19/Action_Plan.csv) | Header plus 10 planning tasks |
| Guide | [Guide.csv](../../data/spreadsheets/qfabric_registry_2026-10-19/Guide.csv) | All 25 original rows |

For 7 tabular sheets, original sheet rows 1–3 (title, subtitle, spacer) are omitted and Excel row 4 is used as the CSV header. Dashboard and Guide preserve all displayed cell values. CSVs are UTF-8 and include no untrusted formulas.

## Canonical source of truth and safety

The CSV export is a **snapshot**. Existing versioned JSON manifests remain authoritative on research metadata:

- `data/quantum_dataset_candidates.json`: 15 known candidates.
- `data/quantum_source_intake.json`: 7 additional leads, 12 artifacts.
- `data/quantum_ai_eval_candidates.json`: 1 separate NVIDIA QCalEval candidate.

`Verification_Queue`, `Normalization_Map` and `Action_Plan` are workbook-specific planning aids. They do **not** change source manifest verification flags or authorize hardware execution.

An Excel cell showing “Evidence recorded” cannot by itself promote a dataset to measured/validated status. Doing so requires an independently versioned evidence contract, primary-source documentation, file rights check, local file SHA-256, units/methods audit and paper-specific numerical reproduction.

## CI validation

The standard library-only verifier checks:

1. Exact 9-sheet export list, row/column counts and source workbook identity.
2. `Pinned_Candidates` versus the authoritative pinned JSON: IDs, URLs, DOIs, upstream provenance/MD5 claims, and explicitly unverified status.
3. Source and artifact IDs and metadata versus the nested source intake JSON; AI lane stays distinct.
4. 28 expected verification work items remain **not started**, evidence status stays **HOLD**, and 27 unit-mapping rows remain **Unmapped**.
5. No candidate spreadsheet or manifest claims a downloaded dataset, verified scientific result or published binary workbook.

```bash
python scripts/verify_registry_csv_snapshot.py
python -m pytest tests/test_registry_csv_snapshot.py -q
```

CI runs this alongside the QFabric test suite under Python 3.11/3.12. It detects inconsistent **snapshot metadata**, not modified experimental measurements (there are none).

## Changing the spreadsheet later

1. Keep the authoritative JSON manifests unchanged unless a source has genuinely been reviewed.
2. Edit the **original Excel workbook** locally. Its charts/formatting/formulas are retained in that copy, **not** in the GitHub CSV export.
3. Re-export to CSV, create a **new dated snapshot folder**, record the new original-file SHA-256, reconcile the cross-manifest references, and run CI.
4. Any updated “completed” research evidence state must use a separate verified-evidence workflow and supporting reports; do not silently update the unverified v1 candidate catalogs.

**Not implemented here:** continuous two-way Excel/Google Sheets sync, uploading the binary XLSX to GitHub, downloading third-party research files, or verifying measured quantum data.
