import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "intent_escrow.py"


def source() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_outcome_and_payout_buckets_are_coarse_enough_for_consensus():
    text = source()
    outcomes = set(re.findall(r'OUTCOME_[A-Z_]+ = "([^"]+)"', text))
    payouts = set(re.findall(r'PAYOUT_[A-Z_]+ = "([^"]+)"', text))
    reputation = set(re.findall(r'REP_[A-Z_]+ = "([^"]+)"', text))
    assert outcomes == {"satisfied", "partial", "failed", "invalid_trace", "misrepresented_plan"}
    assert payouts == {"none", "low_partial", "high_partial", "full"}
    assert reputation == {"major_negative", "minor_negative", "neutral", "positive", "strong_positive"}


def test_selection_prompt_ranks_commitments_not_freeform_winner():
    text = source()
    section = text.split("def _derive_selection", 1)[1].split("def _compare_selections", 1)[0]
    for phrase in [
        "hard constraints",
        "fee efficiency",
        "deadline feasibility",
        "agent reputation",
        "risk disclosure",
        "selected_commitment_id",
    ]:
        assert phrase in section


def test_resolution_prompt_requires_trace_against_intent_and_commitment():
    text = source()
    section = text.split("def _derive_resolution", 1)[1].split("def _compare_resolutions", 1)[0]
    for phrase in [
        "execution trace",
        "original intent",
        "accepted commitment",
        "hard_constraint_failures",
        "misrepresentation",
        "payout_band",
        "reputation_delta_band",
    ]:
        assert phrase in section


def test_fixture_intent_and_trace_shapes_are_json_serializable():
    intent_constraints = [
        {"id": "budget", "type": "hard", "rule": "total fee must stay <= 30 USDC"},
        {"id": "deadline", "type": "hard", "rule": "complete before 2026-07-05T00:00:00Z"},
    ]
    trace = [
        {"step": "search", "artifact": "https://example.org/results", "claim": "found 3 qualifying options"},
        {"step": "reserve", "artifact": "receipt#abc", "claim": "reserved selected option"},
    ]
    assert json.loads(json.dumps(intent_constraints))[0]["id"] == "budget"
    assert json.loads(json.dumps(trace))[1]["step"] == "reserve"
