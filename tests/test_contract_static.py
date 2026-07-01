import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "intent_escrow.py"
README = ROOT / "README.md"
CONSENSUS_DOC = ROOT / "docs" / "consensus-design.md"
EXAMPLES_DOC = ROOT / "docs" / "examples.md"


def read_contract() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_contract_exists_and_uses_pinned_genvm_runner():
    source = read_contract()
    assert source.splitlines()[0] == '# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }'
    assert "py-genlayer:test" not in source
    assert "py-genlayer:latest" not in source


def test_contract_declares_agent_market_state():
    source = read_contract()
    for name in ["Intent", "Commitment", "ResolutionPacket", "AgentReputation"]:
        assert f"class {name}" in source
    for field in [
        "intents: TreeMap[str, Intent]",
        "commitments: TreeMap[str, Commitment]",
        "resolutions: TreeMap[str, ResolutionPacket]",
        "reputations: TreeMap[Address, AgentReputation]",
        "intent_order: DynArray[str]",
    ]:
        assert field in source


def test_contract_has_public_market_methods():
    source = read_contract()
    for method in [
        "create_intent",
        "propose_commitment",
        "select_commitment",
        "submit_execution_trace",
        "resolve_execution",
        "get_intent",
        "get_commitment",
        "get_resolution",
        "get_reputation",
    ]:
        assert re.search(rf"def {method}\(", source), method


def test_contract_uses_two_consensus_boundaries():
    source = read_contract()
    assert "_derive_selection" in source
    assert "_compare_selections" in source
    assert "_derive_resolution" in source
    assert "_compare_resolutions" in source
    assert source.count("gl.vm.run_nondet_unsafe") >= 2


def test_contract_compares_semantic_fields_not_raw_prose():
    source = read_contract()
    for phrase in [
        "outcome_bucket",
        "payout_band",
        "reputation_delta_band",
        "hard_constraint_failures",
        "misrepresentation",
        "selected_commitment_id",
    ]:
        assert phrase in source
    assert "strict_eq(" not in source
    assert "schema-only" in source.lower() or "not a generic oracle" in source.lower()


def test_contract_uses_storage_types_not_builtin_storage_collections():
    source = read_contract()
    storage_section = source.split("class IntentEscrow(gl.Contract):", 1)[1].split("def __init__", 1)[0]
    assert "TreeMap" in storage_section
    assert "DynArray" in storage_section
    assert not re.search(r":\s*dict\b", storage_section)
    assert not re.search(r":\s*list\b", storage_section)


def test_docs_explain_commitment_market_and_examples():
    combined = README.read_text(encoding="utf-8") + CONSENSUS_DOC.read_text(encoding="utf-8")
    examples = EXAMPLES_DOC.read_text(encoding="utf-8").lower()
    for phrase in ["commitment", "autonomous agents", "payout band", "reputation delta"]:
        assert phrase in combined.lower()
    for phrase in ["shopping agent", "code-fixing agent", "research agent", "dao operations"]:
        assert phrase in examples
