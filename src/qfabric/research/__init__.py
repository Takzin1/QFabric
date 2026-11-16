"""Offline research and verification layers (standard library only).

Nothing here imports a vendor SDK, opens a network connection or addresses
hardware. Every result carries one of four provenance labels and they are never
merged: ``measured`` (a physical experiment produced it), ``simulated`` (a
physics model produced it), ``synthetic`` (a fixture with no physical content)
and ``inferred`` (derived from other data through a model or fit).
"""

PROVENANCE = ("measured", "simulated", "synthetic", "inferred")
# What a comparison can establish. Each report states exactly one of these.
COMPARISON_TESTS = ("software_correctness", "scientific_hypothesis", "experimental_validity")
