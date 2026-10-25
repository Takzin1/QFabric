# Experiment Orchestration v0.7 — Untrusted proposal → assessment → review

**Status:** offline, CPU-only proposal-gating foundation. No API credentials, AI
service, quantum hardware, GPU, crystallization experiment, or equipment I/O.

## Why a separate layer?

A language model's suggestion is *untrusted user-supplied data*, even if it
arrives through an NVIDIA or Nebius endpoint. The research gate accepts a
small versioned JSON payload, rejects unknown commands, binds the suggestion
to the **exact bytes** of a previously validated synthetic CrystalTwinAI
snapshot, and checks whether the requested educational parameter change is
in range. An assessed suggestion is NOT authorized.

The first milestone does not connect to Nebius Token Factory or NVIDIA
Nemotron. Those require actual credentials, verified endpoint contracts,
service terms, and a separate integration test. Provider/model names inside
proposals are unverified **labels**, not proof of where inference ran.

## Non-executing architecture

```text
Untrusted provider JSON / local synthetic fixture / human draft
            |
            v
parse_proposal: strict schema, bounded UTF-8, no unknown fields,
                duplicate keys, NaN, hardware action or imperative command
            |
            v
make_assessment(snapshot bytes + proposal bytes):
SHA-256 source binding -> CrystalTwinAI input limits ->
ready_for_review OR rejected (no auto approval)
            |
            v
make_review(assessment + both original inputs + claimed reviewer):
recomputes assessment; rejects any stale/tampered mismatch
            |
            v
manual educational simulator input only
(NO model inference, hardware executor, QICK acquisition, process control)
```

## Schemas and compatibility

- Source snapshot: `crystaltwin-qfabric-snapshot/1` (unchanged).
- Model-neutral proposal: `qfabric-research-proposal/1`.
- Guardrail report: `qfabric-research-assessment/1`.
- Self-attested review: `qfabric-human-review/1`.
- Existing QFabric/CrystalTwinAI report: `qfabric-crystaltwin-report/1`
  (untouched). QFabric command protocol remains `0.2.0`.

Proposal example (replace `snapshotSha256` with the true SHA-256 of
your exported snapshot, not a fabricated hash):

```json
{
  "schemaVersion": "qfabric-research-proposal/1",
  "kind": "educational_parameter_change",
  "proposalId": "example-001",
  "snapshotSha256": "YOUR_ACTUAL_LOWERCASE_SHA256",
  "source": {
    "origin": "unverified_model",
    "providerLabel": "unverified-provider",
    "modelLabel": "unverified-model"
  },
  "hypothesis": "Lower cooling rate might change the simulation outcome.",
  "rationale": "Educational sensitivity exploration, not a physical process recommendation.",
  "changes": {"coolingRate": 0.25},
  "requestedAction": "simulation_only"
}
```

Use the CLI `prepare` command below to create a correctly hashed *fixture*,
not to masquerade as a real Nemotron call. It explicitly labels its source
as `synthetic_fixture` and `modelLabel=none`.

## Complete reproducible demo

```bash
python -m pip install -e ".[dev]"
SNAP=tests/fixtures/crystaltwin_snapshot.synthetic.json

python scripts/research_agent_gate.py prepare "$SNAP" proposal.json \
  --parameter coolingRate --value 0.25

python scripts/research_agent_gate.py assess "$SNAP" proposal.json assessment.json

python scripts/research_agent_gate.py review "$SNAP" proposal.json assessment.json review.json \
  --reviewer-label "demo-human" --decision approve --attest-educational-only
```

The assessment includes exact source and proposal SHA-256 hashes, simulated
change diff, and refusal reasons. A rejected proposal writes
`status=rejected` and exits **2**. An invalid proposal exits **1**. Only
`status=ready_for_review` exits **0** and can be subsequently self-attested.

`review.json` includes `simulationInput` only on explicitly approved,
recomputed, non-tampered assessments. It **does not** run the simulator:
manual transfer/application is a future UI integration. All approval is
self-attested, **not authenticated**, cryptographically signed or a secure
multi-user approval workflow. Rejected reviews release no input.

## Decision gate and safety scope

- Only six known CrystalTwinAI parameters are accepted, with at most **three**
  changed fields per proposal.
- Limits mirror CrystalTwinAI's `src/config/parameters.ts` as inspected on
  2026-10-18: temperature 20–90 °C, concentration 0.1–0.6 g/mL,
  stirringSpeed 0–1000 rpm, coolingRate 0.05–2 °C/min,
  impurityLevel 0–5%, timeSteps 10–200 integer. These are educational
  *model input limits*, not experimentally established safety limits.
- The existing short two-row synthetic demo snapshot remains accepted as a
  legacy source, but any *newly proposed* timeSteps value must be 10–200.
- The source snapshot is restricted to synthetic educational inputs. Model
  outputs and textual rationales are never evaluated as commands or code.
- Source/proposal file-size limits, duplicate-key refusal, JSON type checks,
  finite-value checks and byte-hash matching prevent ambiguous data from
  silently moving between stages.
- The gate has **no execute, trigger, QICK acquisition, process actuator,
  network or generic hardware dispatch methods**.
- A correct source hash proves only content consistency, not authenticity,
  authorship, source validity, or actual NVIDIA/Nebius model use.

## Next practical steps

1. Add a *separate* provider client with a **verified** Nebius/NVIDIA
   supported model, authentication via environment variables, explicit
   timeouts, limited requests and **structured response parsing only**.
2. Connect approved educational `simulationInput` to a controlled
   CrystalTwinAI UI *preview* (never hardware) and compute a before/after
   educational simulation comparison.
3. Report measured API latency, provider errors and request counts without
   exposing credentials. Add mocked contract tests and an opt-in live smoke.
4. Demonstrate a rejected prompt-injection / out-of-range proposal and a
   successful review as distinct paths for hackathon judges.

**Update (CrystalPilot):** steps 1–4 are now implemented in CrystalTwinAI's
`/pilot` app (server-side Nebius Token Factory client, before/after
simulation comparison, mocked contract tests plus an opt-in live smoke test,
and rejection demos). See [crystalpilot.md](crystalpilot.md). This QFabric
module itself still makes no network or model calls.

**Not implemented here:** a production operator identity system, actual
NVIDIA GPU validation or physical quantum readout.
