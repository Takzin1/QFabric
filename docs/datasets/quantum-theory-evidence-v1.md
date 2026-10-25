# Quantum theory evidence registry v1 (curated, metadata-only)

The JSON at [data/quantum_theory_evidence_v1.json](../../data/quantum_theory_evidence_v1.json)
has eleven primary research references, ranging from quantum simulation/algorithms
to 2026 quantum error correction and hybrid quantum-chemistry/HPC research.

**Purpose:** provide evidence-aware research questions, falsifiability limits,
DOIs and source-backed *citation-count snapshots*. It does not implement those
published algorithms, ingest their experimental datasets, or justify a claim
that classical educational crystallization is a quantum calculation.

## Evidence standards

- DOI and year were checked against the original publisher/conference record.
- Six foundational papers have 2026-10-26 OpenAlex displayed count snapshots.
  The Shor FOCS record is labeled 2002 by OpenAlex but the proceedings' DOI
  and original paper date are 1994; the discrepancy is explicitly flagged.
- Two QEC articles have publisher-displayed citation snapshots. For recent
  publications with no comparable verified count, the value is \`null\`.
- Cite source publications to support *their actual findings only*. Reviews
  and highly cited work aren't substitute validation of the simulator.
- The Google Quantum AI surface-code article is the 2025 journal-volume
  reference (online in December 2024), and the registry notes its April 2026
  author correction.
- SHA-256, if computed on a local JSON file, checks exact bytes only. It is not
  a digital signature, a publisher authentication or peer-review proof.

## Existing datasets and intended use

\`\`\`text
Literature registry (theory and research questions)
  +--> QFabric: offline validation + independent future benchmark design
  +--> CrystalTwinAI: context-only bibliography panel (public JSON copy)

Quantum dataset candidates (existing catalog)
  +--> source-intake/licensing/permission checks
  +--> possible independent measured-data comparisons (future)

CrystalTwinAI educational crystallization engine
  +--> remains classical, synthetic and unchanged
  +--> no imported coefficients; no assertions of quantum kinetics
\`\`\`

This separation is deliberate. An electronic-structure energy calculation,
even if validated on quantum hardware, does not by itself derive crystal
nucleation kinetics, prove a transport or cooling model, or establish an
NVIDIA GPU/quantum advantage for CrystalTwinAI.

## Versioning and synchronization

Canonical file: \`QFabric/data/quantum_theory_evidence_v1.json\`

Mirrored file: \`crystaltwinai/public/examples/quantum-theory-evidence-v1.json\`

The repository owner should update the mirror with **identical bytes** when
updating the bibliography; do not auto-fetch mutable remote metadata at UI
runtime. The two independent CI checks validate each copy. A future cross-repo
release could pin both by content SHA-256 in a signed release manifest.

\`\`\`bash
python -m pip install -e ".[dev]"
python -m pytest tests/test_theory_evidence.py
python -c 'from pathlib import Path; from qfabric.theory_evidence import load_registry; p=Path("data/quantum_theory_evidence_v1.json"); print(len(load_registry(p)["entries"]))'
\`\`\`

## Next research milestones

1. Attach source-level reproducibility and dataset licenses to individual
   papers, with verified source archives and explicit measurement provenance.
2. For an actual benchmark, choose a quantum task and independently executable
   classical baseline, with finite-shot uncertainty/noise models. The
   literature registry alone is not a benchmark.
3. For a crystallization extension, obtain domain-specific kinetic
   experiments with physical units, temperature control traces and uncertainty;
   compare those to classical CrystalTwinAI first.
4. Require an independently evaluated mapping (Hamiltonian/material model,
   boundary conditions, scaling evidence and measurement chain) before
   asserting a connection between quantum chemistry and a real crystallizer.

## Primary citation providers

- OpenAlex topic citation listing: https://openalex.org/topics/T10682
- Publisher originals are linked individually under each entry's \`primaryUrl\`.
- QFabric's existing dataset catalog is in
  [quantum-research-dataset-catalog.md](quantum-research-dataset-catalog.md).
