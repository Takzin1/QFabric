# Nebius Token Factory → QFabric research proposal adapter

**Scope:** opt-in outbound inference only. Nothing in this adapter starts a
quantum device, QICK acquisition, crystallization simulator, or physical process.
All model output is untrusted and passes the existing offline QFabric guard.

## Architecture

```text
CrystalTwinAI synthetic snapshot (exact SHA-256)
       |
       v
Nebius Token Factory / NVIDIA Nemotron, opt-in HTTPS request
       |  educational input/summary/bounds only
       v
strict JSON response parser (no scripts or tool calls)
       |
       v
qfabric-research-proposal/1 + local provider receipt
       |
       v
existing offline assess command (never auto-approved)
       |
       +--> rejected: STOP
       |
       +--> ready_for_review: self-attested HUMAN decision
                                    |
                                    v
                           manual educational preview only
```

The model endpoint is fixed to
https://api.tokenfactory.nebius.com/v1/chat/completions.
The default model is `nvidia/Nemotron-3_5-Lightning`, as documented by Nebius.
Verify access for your key. The adapter uses Python's standard-library
`urllib`; the core continues to have no provider SDK.

## Run (explicitly requires your API key)

```bash
python -m pip install -e ".[dev]"
export NEBIUS_API_KEY='your-own-nebius-token-factory-key'
SNAP=tests/fixtures/crystaltwin_snapshot.synthetic.json

python scripts/nebius_research_propose.py "$SNAP" proposal.json receipt.json
python scripts/research_agent_gate.py assess "$SNAP" proposal.json assessment.json

# Inspect the proposed changes and assessed reasons first.
python scripts/research_agent_gate.py review "$SNAP" proposal.json assessment.json review.json \
  --reviewer-label "local-human" --decision approve --attest-educational-only
```

You may specify `--model MODEL_ID` when the authenticated Nebius catalog shows
a supported alternative. Never paste the credential in a commit or share the
resulting request's authorization headers. The adapter doesn't retry, stream,
accept arbitrary endpoint URLs or use a general hardware/simulator executor.

A schema-valid but out-of-range proposal is written as evidence and the live
adapter exits 2. Failed parsing/HTTP returns 1. No files are overwritten.
The proposal and response receipt are local evidence: the hashes show byte
consistency, **not** an authenticated provider, model, reviewer or physical
experiment. The output model label is not cryptographically verified.

The existing offline `make_assessment` result has `modelInvoked=False`: this
describes that **offline assessment function**, not the separate opt-in
HTTP call. The new receipt is the separate record of returned API bytes.
Self-attested review remains a human label, not login authentication.

## Validation

```bash
pytest tests/test_nebius_research_propose.py
ruff check .
pytest
```

These tests use a fake transport without requiring a credential or making
paid requests. They cover valid proposal/assessment links, rejection of
unexpected keys, duplicate JSON members, NaN, truncation, forbidden tool calls,
excessive response sizes, spoofed snapshot provenance and overwrites.
Tests cannot establish live Nebius access, NVIDIA GPU acceleration, quantum
hardware interoperability or scientifically valid results.

The network request is restricted to validated **synthetic educational**
snapshots. Do not submit confidential or measured research data as if it were
synthetic. The 20-second timeout and 64 KiB response bound limit errors and
resource use. No approval implies automatic simulator execution.

## Vendor documentation

- Nebius Token Factory: https://dev.nebius.com/token-factory
- NVIDIA Nemotron via Nebius: https://nebius.com/services/token-factory/nemotron
- Existing offline protocol: [experiment-orchestration](experiment-orchestration.md)
