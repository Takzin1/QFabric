# Caune Zenodo v2 independent-source evidence lane

**Status:** upstream file provenance verification is **implemented**, but no authentication is claimed until the GitHub Action completes successfully. This is a stacked extension to PR #25, not a new quantum experiment.

## Authoritative sources

- Paper (version of record): Caune et al., *Nature Communications* **17**, 7383 (2026), [DOI:10.1038/s41467-026-73331-6](https://doi.org/10.1038/s41467-026-73331-6)
- Zenodo concept DOI cited by the paper: [10.5281/zenodo.13961129](https://doi.org/10.5281/zenodo.13961129)
- Exact dataset version used by this workflow: [Zenodo v2 record 15364358](https://zenodo.org/records/15364358)
- Version v2 lists original file-specific **MD5** checksums for the 15 selected original sources. These checksums are recorded in [the pinned manifest](../../data/caune_zenodo_v2_source_manifest.json).

**Rights caveat:** the publisher article is CC BY 4.0, but that alone does not establish the per-dataset/per-file redistribution terms. The current Zenodo record's license has not been independently recorded as verified. Do not commit or redistribute original third-party raw files.

## What is new

`src/qfabric/caune_zenodo.py` downloads exactly 15 allowlisted files, each at most 16 MiB and at most 25 MiB total, from the pinned Zenodo origin. Files are stored in a private temporary directory, checked against Zenodo's displayed MD5, and then fed to the existing PR #25 Caune scientific audits, which separately check **SHA-256 pins of the previously user-supplied copies**. Only when both checks match does it produce a structured derived report. Output excludes raw experiment rows, IQ traces and embedded Stim programs.

This deliberately **excludes** the three large stability HDF5 archives (approximately 130 MB, 344 MB and 741 MB). Their scientific reuse requires an explicitly separate, capacity-limited and provenance-aware milestone.

Run locally with Python 3.11+:

```bash
python -m pip install -e ".[dev,research-hdf5]"
python scripts/caune_zenodo_v2_reproduce.py --mode metadata
python scripts/caune_zenodo_v2_reproduce.py --mode reproduce --output /tmp/caune-zenodo-v2-derived.json
```

A dedicated GitHub workflow (`.github/workflows/caune_zenodo_v2.yml`) exercises the same path on a controlled public runner, then uploads **only a JSON derived-evidence artifact** with 7-day retention. Network, upstream record availability, and GitHub Actions permissions can still block the run; these are visible failures, not license to bypass checks.

## Scientific boundaries

- `MD5 matched` means downloaded bytes matched the file digest listed on Zenodo v2; `prior SHA-256 pin matched` means they also matched the earlier user-uploaded source copies.
- Neither proves independent QPU operation, real-time FPGA decoding, nor complete experimental reproducibility.
- Figures, conditional calibration inferences, timings, logical error probabilities, and HDF5 unit ambiguities retain the distinct labels and limitations defined in PR #25.
- Any failed MD5, SHA-256, expected size, filename, checksum, redirected-origin, or parser validation makes the run fail closed.
- QICK plan-only behavior is unchanged and no source code embedded in HDF5 is executed.

**Gate to merge:** CI passing on synthetic and direct-source checks; independently inspect the resulting derived JSON before calling source provenance verified.
