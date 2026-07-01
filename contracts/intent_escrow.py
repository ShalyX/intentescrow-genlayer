# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from dataclasses import dataclass
import json


ERROR_EXPECTED = "[EXPECTED]"
ERROR_LLM = "[LLM_ERROR]"

OUTCOME_SATISFIED = "satisfied"
OUTCOME_PARTIAL = "partial"
OUTCOME_FAILED = "failed"
OUTCOME_INVALID_TRACE = "invalid_trace"
OUTCOME_MISREPRESENTED_PLAN = "misrepresented_plan"

PAYOUT_NONE = "none"
PAYOUT_LOW_PARTIAL = "low_partial"
PAYOUT_HIGH_PARTIAL = "high_partial"
PAYOUT_FULL = "full"

REP_MAJOR_NEGATIVE = "major_negative"
REP_MINOR_NEGATIVE = "minor_negative"
REP_NEUTRAL = "neutral"
REP_POSITIVE = "positive"
REP_STRONG_POSITIVE = "strong_positive"


@allow_storage
@dataclass
class Intent:
    creator: Address
    goal: str
    hard_constraints_json: str
    soft_preferences_json: str
    max_fee: u256
    escrow_label: str
    deadline_iso: str
    status: str
    selected_commitment_id: str
    created_at: str


@allow_storage
@dataclass
class Commitment:
    intent_id: str
    agent: Address
    plan_summary: str
    capability_tags_json: str
    requested_fee: u256
    deadline_iso: str
    risk_disclosures_json: str
    status: str
    trace_json: str
    created_at: str


@allow_storage
@dataclass
class ResolutionPacket:
    intent_id: str
    commitment_id: str
    outcome_bucket: str
    payout_band: str
    reputation_delta_band: str
    hard_constraint_failures_json: str
    soft_preference_score: u256
    misrepresentation: bool
    trace_refs_json: str
    rationale: str
    resolved_at: str


@allow_storage
@dataclass
class AgentReputation:
    completed_count: u256
    failed_count: u256
    misrepresentation_count: u256
    last_delta_band: str
    domain_tags_json: str


class IntentEscrow(gl.Contract):
    """Autonomous-agent commitment router and escrow coordination primitive.

    IntentEscrow is not a generic oracle and not a schema-only trace checker.
    GenLayer consensus is used twice: first to select the best agent commitment,
    then to resolve whether the selected agent's execution trace satisfied the
    original intent and its own commitment.
    """

    owner: Address
    intents: TreeMap[str, Intent]
    commitments: TreeMap[str, Commitment]
    resolutions: TreeMap[str, ResolutionPacket]
    reputations: TreeMap[Address, AgentReputation]
    intent_order: DynArray[str]
    commitment_order: DynArray[str]
    resolution_order: DynArray[str]
    counters: TreeMap[str, u256]

    def __init__(self):
        self.owner = gl.message.sender_address
        self.counters["intents"] = u256(0)
        self.counters["commitments"] = u256(0)
        self.counters["resolutions"] = u256(0)

    @gl.public.write
    def create_intent(self, goal: str, hard_constraints_json: str, soft_preferences_json: str, max_fee: u256, escrow_label: str, deadline_iso: str) -> str:
        if len(goal.strip()) < 16:
            raise gl.UserError(f"{ERROR_EXPECTED} goal too short")
        hard_constraints = self._parse_json_array(hard_constraints_json, "hard_constraints_json")
        soft_preferences = self._parse_json_array(soft_preferences_json, "soft_preferences_json")
        if len(hard_constraints) == 0:
            raise gl.UserError(f"{ERROR_EXPECTED} at least one hard constraint required")
        if int(max_fee) <= 0:
            raise gl.UserError(f"{ERROR_EXPECTED} max_fee must be positive")

        intent_id = self._next_id("intent", "intents")
        self.intents[intent_id] = Intent(
            creator=gl.message.sender_address,
            goal=goal.strip(),
            hard_constraints_json=self._canonical_json(hard_constraints),
            soft_preferences_json=self._canonical_json(soft_preferences),
            max_fee=max_fee,
            escrow_label=escrow_label.strip(),
            deadline_iso=deadline_iso.strip(),
            status="open",
            selected_commitment_id="",
            created_at=self._now_iso(),
        )
        self.intent_order.append(intent_id)
        return intent_id

    @gl.public.write
    def propose_commitment(self, intent_id: str, plan_summary: str, capability_tags_json: str, requested_fee: u256, deadline_iso: str, risk_disclosures_json: str) -> str:
        intent = self._require_intent(intent_id)
        if intent.status != "open":
            raise gl.UserError(f"{ERROR_EXPECTED} intent is not open")
        if int(requested_fee) > int(intent.max_fee):
            raise gl.UserError(f"{ERROR_EXPECTED} requested fee exceeds max_fee")
        if len(plan_summary.strip()) < 24:
            raise gl.UserError(f"{ERROR_EXPECTED} plan summary too short")
        capability_tags = self._parse_json_array(capability_tags_json, "capability_tags_json")
        risk_disclosures = self._parse_json_array(risk_disclosures_json, "risk_disclosures_json")

        commitment_id = self._next_id("commitment", "commitments")
        self.commitments[commitment_id] = Commitment(
            intent_id=intent_id,
            agent=gl.message.sender_address,
            plan_summary=plan_summary.strip(),
            capability_tags_json=self._canonical_json(capability_tags),
            requested_fee=requested_fee,
            deadline_iso=deadline_iso.strip(),
            risk_disclosures_json=self._canonical_json(risk_disclosures),
            status="proposed",
            trace_json="[]",
            created_at=self._now_iso(),
        )
        self._ensure_reputation(gl.message.sender_address, capability_tags)
        self.commitment_order.append(commitment_id)
        return commitment_id

    @gl.public.write
    def select_commitment(self, intent_id: str) -> str:
        intent = self._require_intent(intent_id)
        if intent.status != "open":
            raise gl.UserError(f"{ERROR_EXPECTED} intent is not open")
        candidates_json = self._commitments_for_intent(intent_id)
        if candidates_json == "[]":
            raise gl.UserError(f"{ERROR_EXPECTED} no commitments proposed")

        def leader_fn():
            return self._derive_selection(intent, candidates_json)

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            validator_selection = leader_fn()
            return self._compare_selections(leaders_res.calldata, validator_selection)

        selection = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        selected_commitment_id = selection["selected_commitment_id"]
        commitment = self._require_commitment(selected_commitment_id)
        if commitment.intent_id != intent_id:
            raise gl.UserError(f"{ERROR_LLM} selected commitment belongs to different intent")
        intent.status = "assigned"
        intent.selected_commitment_id = selected_commitment_id
        commitment.status = "accepted"
        self.intents[intent_id] = intent
        self.commitments[selected_commitment_id] = commitment
        return selected_commitment_id

    @gl.public.write
    def submit_execution_trace(self, commitment_id: str, trace_json: str) -> str:
        commitment = self._require_commitment(commitment_id)
        if commitment.agent != gl.message.sender_address:
            raise gl.UserError(f"{ERROR_EXPECTED} only selected agent can submit trace")
        if commitment.status != "accepted":
            raise gl.UserError(f"{ERROR_EXPECTED} commitment is not accepted")
        trace = self._parse_json_array(trace_json, "trace_json")
        if len(trace) == 0:
            raise gl.UserError(f"{ERROR_EXPECTED} execution trace required")
        commitment.trace_json = self._canonical_json(trace)
        commitment.status = "submitted"
        self.commitments[commitment_id] = commitment
        return commitment_id

    @gl.public.write
    def resolve_execution(self, commitment_id: str) -> str:
        commitment = self._require_commitment(commitment_id)
        if commitment.status != "submitted":
            raise gl.UserError(f"{ERROR_EXPECTED} commitment has no submitted trace")
        intent = self._require_intent(commitment.intent_id)
        if intent.selected_commitment_id != commitment_id:
            raise gl.UserError(f"{ERROR_EXPECTED} commitment was not selected")

        def leader_fn():
            return self._derive_resolution(intent, commitment)

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            validator_resolution = leader_fn()
            return self._compare_resolutions(leaders_res.calldata, validator_resolution)

        resolution = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        resolution_id = self._store_resolution(commitment_id, resolution)
        commitment.status = "resolved"
        intent.status = resolution["outcome_bucket"]
        self.commitments[commitment_id] = commitment
        self.intents[commitment.intent_id] = intent
        self._apply_reputation_delta(commitment.agent, resolution)
        return resolution_id

    @gl.public.view
    def get_intent(self, intent_id: str) -> dict:
        intent = self._require_intent(intent_id)
        return {
            "creator": str(intent.creator),
            "goal": intent.goal,
            "hard_constraints": json.loads(intent.hard_constraints_json),
            "soft_preferences": json.loads(intent.soft_preferences_json),
            "max_fee": int(intent.max_fee),
            "escrow_label": intent.escrow_label,
            "deadline_iso": intent.deadline_iso,
            "status": intent.status,
            "selected_commitment_id": intent.selected_commitment_id,
            "created_at": intent.created_at,
        }

    @gl.public.view
    def get_commitment(self, commitment_id: str) -> dict:
        commitment = self._require_commitment(commitment_id)
        return {
            "intent_id": commitment.intent_id,
            "agent": str(commitment.agent),
            "plan_summary": commitment.plan_summary,
            "capability_tags": json.loads(commitment.capability_tags_json),
            "requested_fee": int(commitment.requested_fee),
            "deadline_iso": commitment.deadline_iso,
            "risk_disclosures": json.loads(commitment.risk_disclosures_json),
            "status": commitment.status,
            "trace": json.loads(commitment.trace_json),
            "created_at": commitment.created_at,
        }

    @gl.public.view
    def get_resolution(self, resolution_id: str) -> dict:
        resolution = self.resolutions[resolution_id]
        if resolution.intent_id == "":
            raise gl.UserError(f"{ERROR_EXPECTED} resolution not found")
        return {
            "intent_id": resolution.intent_id,
            "commitment_id": resolution.commitment_id,
            "outcome_bucket": resolution.outcome_bucket,
            "payout_band": resolution.payout_band,
            "reputation_delta_band": resolution.reputation_delta_band,
            "hard_constraint_failures": json.loads(resolution.hard_constraint_failures_json),
            "soft_preference_score": int(resolution.soft_preference_score),
            "misrepresentation": resolution.misrepresentation,
            "trace_refs": json.loads(resolution.trace_refs_json),
            "rationale": resolution.rationale,
            "resolved_at": resolution.resolved_at,
        }

    @gl.public.view
    def get_reputation(self, agent: Address) -> dict:
        reputation = self.reputations[agent]
        return {
            "completed_count": int(reputation.completed_count),
            "failed_count": int(reputation.failed_count),
            "misrepresentation_count": int(reputation.misrepresentation_count),
            "last_delta_band": reputation.last_delta_band,
            "domain_tags": json.loads(reputation.domain_tags_json),
        }

    def _derive_selection(self, intent: Intent, candidates_json: str) -> dict:
        prompt = f"""
You are a GenLayer validator for IntentEscrow, an autonomous agents commitment market.

TASK:
Rank commitment proposals against the user intent. Do not pick a freeform winner.
Assess hard constraints, soft preferences, fee efficiency, deadline feasibility,
agent reputation, plan clarity, and risk disclosure quality.

INTENT GOAL: {intent.goal}
HARD CONSTRAINTS JSON: {intent.hard_constraints_json}
SOFT PREFERENCES JSON: {intent.soft_preferences_json}
MAX FEE: {int(intent.max_fee)}
INTENT DEADLINE: {intent.deadline_iso}
CANDIDATE COMMITMENTS JSON: {candidates_json}

Return JSON exactly with:
{{
  "selected_commitment_id": "commitment-id",
  "ranked_commitment_ids": ["commitment-id"],
  "rejected_commitment_ids": ["commitment-id"],
  "blocking_risks": ["risk id or short reason"],
  "fee_band": "low|medium|high",
  "deadline_feasibility_band": "strong|acceptable|weak",
  "reputation_fit_band": "strong|acceptable|weak|unknown",
  "rationale": "short selection explanation"
}}
"""
        raw = gl.nondet.exec_prompt(prompt, response_format="json")
        return self._normalize_selection(raw)

    def _compare_selections(self, leader: dict, validator: dict) -> bool:
        if not isinstance(leader, dict) or not isinstance(validator, dict):
            return False
        if leader.get("selected_commitment_id") != validator.get("selected_commitment_id"):
            return False
        if leader.get("fee_band") != validator.get("fee_band"):
            return False
        if leader.get("deadline_feasibility_band") != validator.get("deadline_feasibility_band"):
            return False
        if leader.get("reputation_fit_band") != validator.get("reputation_fit_band"):
            return False
        leader_risks = self._string_set(leader.get("blocking_risks", []))
        validator_risks = self._string_set(validator.get("blocking_risks", []))
        if len(leader_risks) > 0 or len(validator_risks) > 0:
            if not self._sets_overlap_enough(leader_risks, validator_risks, 50):
                return False
        return True

    def _derive_resolution(self, intent: Intent, commitment: Commitment) -> dict:
        prompt = f"""
You are a GenLayer validator resolving IntentEscrow autonomous-agent work.

TASK:
Compare the execution trace against the original intent and accepted commitment.
Determine whether hard constraints passed, whether soft preferences were optimized,
whether the trace is valid, and whether the agent misrepresented its plan.

ORIGINAL INTENT: {intent.goal}
HARD CONSTRAINTS JSON: {intent.hard_constraints_json}
SOFT PREFERENCES JSON: {intent.soft_preferences_json}
MAX FEE: {int(intent.max_fee)}
ACCEPTED COMMITMENT PLAN: {commitment.plan_summary}
REQUESTED FEE: {int(commitment.requested_fee)}
RISK DISCLOSURES JSON: {commitment.risk_disclosures_json}
EXECUTION TRACE JSON: {commitment.trace_json}

Return JSON exactly with:
{{
  "outcome_bucket": "satisfied|partial|failed|invalid_trace|misrepresented_plan",
  "payout_band": "none|low_partial|high_partial|full",
  "reputation_delta_band": "major_negative|minor_negative|neutral|positive|strong_positive",
  "hard_constraint_failures": ["constraint id"],
  "soft_preference_score": 0-100,
  "misrepresentation": true|false,
  "trace_refs": ["artifact or trace reference"],
  "rationale": "short evidence-backed explanation"
}}
"""
        raw = gl.nondet.exec_prompt(prompt, response_format="json")
        return self._normalize_resolution(raw)

    def _compare_resolutions(self, leader: dict, validator: dict) -> bool:
        if not isinstance(leader, dict) or not isinstance(validator, dict):
            return False
        if leader.get("outcome_bucket") != validator.get("outcome_bucket"):
            return False
        if leader.get("payout_band") != validator.get("payout_band"):
            return False
        if leader.get("reputation_delta_band") != validator.get("reputation_delta_band"):
            return False
        if bool(leader.get("misrepresentation", False)) != bool(validator.get("misrepresentation", False)):
            return False
        leader_failures = self._string_set(leader.get("hard_constraint_failures", []))
        validator_failures = self._string_set(validator.get("hard_constraint_failures", []))
        if not self._sets_overlap_enough(leader_failures, validator_failures, 60):
            return False
        return True

    def _normalize_selection(self, raw: dict) -> dict:
        if not isinstance(raw, dict):
            raise gl.UserError(f"{ERROR_LLM} selection must be an object")
        selected_commitment_id = str(raw.get("selected_commitment_id", "")).strip()
        if selected_commitment_id == "":
            raise gl.UserError(f"{ERROR_LLM} selected commitment required")
        rationale = str(raw.get("rationale", "")).strip()
        if len(rationale) < 12:
            raise gl.UserError(f"{ERROR_LLM} rationale too short")
        return {
            "selected_commitment_id": selected_commitment_id,
            "ranked_commitment_ids": self._normalize_string_array(raw.get("ranked_commitment_ids", [])),
            "rejected_commitment_ids": self._normalize_string_array(raw.get("rejected_commitment_ids", [])),
            "blocking_risks": self._normalize_string_array(raw.get("blocking_risks", [])),
            "fee_band": self._allowed(raw.get("fee_band", "medium"), ["low", "medium", "high"], "medium"),
            "deadline_feasibility_band": self._allowed(raw.get("deadline_feasibility_band", "acceptable"), ["strong", "acceptable", "weak"], "acceptable"),
            "reputation_fit_band": self._allowed(raw.get("reputation_fit_band", "unknown"), ["strong", "acceptable", "weak", "unknown"], "unknown"),
            "rationale": rationale,
        }

    def _normalize_resolution(self, raw: dict) -> dict:
        if not isinstance(raw, dict):
            raise gl.UserError(f"{ERROR_LLM} resolution must be an object")
        outcome_bucket = self._allowed(raw.get("outcome_bucket", ""), [OUTCOME_SATISFIED, OUTCOME_PARTIAL, OUTCOME_FAILED, OUTCOME_INVALID_TRACE, OUTCOME_MISREPRESENTED_PLAN], "")
        if outcome_bucket == "":
            raise gl.UserError(f"{ERROR_LLM} invalid outcome_bucket")
        payout_band = self._allowed(raw.get("payout_band", ""), [PAYOUT_NONE, PAYOUT_LOW_PARTIAL, PAYOUT_HIGH_PARTIAL, PAYOUT_FULL], "")
        if payout_band == "":
            raise gl.UserError(f"{ERROR_LLM} invalid payout_band")
        reputation_delta_band = self._allowed(raw.get("reputation_delta_band", ""), [REP_MAJOR_NEGATIVE, REP_MINOR_NEGATIVE, REP_NEUTRAL, REP_POSITIVE, REP_STRONG_POSITIVE], "")
        if reputation_delta_band == "":
            raise gl.UserError(f"{ERROR_LLM} invalid reputation_delta_band")
        score = self._coerce_int(raw.get("soft_preference_score", 0))
        rationale = str(raw.get("rationale", "")).strip()
        if len(rationale) < 12:
            raise gl.UserError(f"{ERROR_LLM} rationale too short")
        return {
            "outcome_bucket": outcome_bucket,
            "payout_band": payout_band,
            "reputation_delta_band": reputation_delta_band,
            "hard_constraint_failures": self._normalize_string_array(raw.get("hard_constraint_failures", [])),
            "soft_preference_score": score,
            "misrepresentation": bool(raw.get("misrepresentation", False)),
            "trace_refs": self._normalize_string_array(raw.get("trace_refs", [])),
            "rationale": rationale,
        }

    def _store_resolution(self, commitment_id: str, resolution: dict) -> str:
        commitment = self._require_commitment(commitment_id)
        resolution_id = self._next_id("resolution", "resolutions")
        self.resolutions[resolution_id] = ResolutionPacket(
            intent_id=commitment.intent_id,
            commitment_id=commitment_id,
            outcome_bucket=resolution["outcome_bucket"],
            payout_band=resolution["payout_band"],
            reputation_delta_band=resolution["reputation_delta_band"],
            hard_constraint_failures_json=self._canonical_json(resolution["hard_constraint_failures"]),
            soft_preference_score=u256(resolution["soft_preference_score"]),
            misrepresentation=resolution["misrepresentation"],
            trace_refs_json=self._canonical_json(resolution["trace_refs"]),
            rationale=resolution["rationale"],
            resolved_at=self._now_iso(),
        )
        self.resolution_order.append(resolution_id)
        return resolution_id

    def _commitments_for_intent(self, intent_id: str) -> str:
        candidates = []
        for commitment_id in self.commitment_order:
            commitment = self.commitments[commitment_id]
            if commitment.intent_id == intent_id and commitment.status == "proposed":
                reputation = self.reputations[commitment.agent]
                candidates.append({
                    "commitment_id": commitment_id,
                    "agent": str(commitment.agent),
                    "plan_summary": commitment.plan_summary,
                    "capability_tags": json.loads(commitment.capability_tags_json),
                    "requested_fee": int(commitment.requested_fee),
                    "deadline_iso": commitment.deadline_iso,
                    "risk_disclosures": json.loads(commitment.risk_disclosures_json),
                    "reputation": {
                        "completed_count": int(reputation.completed_count),
                        "failed_count": int(reputation.failed_count),
                        "misrepresentation_count": int(reputation.misrepresentation_count),
                        "last_delta_band": reputation.last_delta_band,
                    },
                })
        return self._canonical_json(candidates)

    def _apply_reputation_delta(self, agent: Address, resolution: dict):
        reputation = self.reputations[agent]
        if resolution["outcome_bucket"] == OUTCOME_SATISFIED:
            reputation.completed_count = u256(int(reputation.completed_count) + 1)
        if resolution["outcome_bucket"] in (OUTCOME_FAILED, OUTCOME_INVALID_TRACE, OUTCOME_MISREPRESENTED_PLAN):
            reputation.failed_count = u256(int(reputation.failed_count) + 1)
        if resolution["misrepresentation"]:
            reputation.misrepresentation_count = u256(int(reputation.misrepresentation_count) + 1)
        reputation.last_delta_band = resolution["reputation_delta_band"]
        self.reputations[agent] = reputation

    def _ensure_reputation(self, agent: Address, tags: list):
        reputation = self.reputations[agent]
        if reputation.last_delta_band == "":
            self.reputations[agent] = AgentReputation(
                completed_count=u256(0),
                failed_count=u256(0),
                misrepresentation_count=u256(0),
                last_delta_band=REP_NEUTRAL,
                domain_tags_json=self._canonical_json(self._normalize_string_array(tags)),
            )

    def _require_intent(self, intent_id: str) -> Intent:
        intent = self.intents[intent_id]
        if intent.status == "":
            raise gl.UserError(f"{ERROR_EXPECTED} intent not found")
        return intent

    def _require_commitment(self, commitment_id: str) -> Commitment:
        commitment = self.commitments[commitment_id]
        if commitment.intent_id == "":
            raise gl.UserError(f"{ERROR_EXPECTED} commitment not found")
        return commitment

    def _next_id(self, prefix: str, counter_key: str) -> str:
        current = int(self.counters[counter_key]) + 1
        self.counters[counter_key] = u256(current)
        return prefix + "-" + str(current)

    def _parse_json_array(self, text: str, field_name: str) -> list:
        try:
            value = json.loads(text)
        except Exception:
            raise gl.UserError(f"{ERROR_EXPECTED} invalid {field_name}")
        if not isinstance(value, list):
            raise gl.UserError(f"{ERROR_EXPECTED} {field_name} must be an array")
        return value

    def _canonical_json(self, value) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def _normalize_string_array(self, value) -> list:
        if not isinstance(value, list):
            return []
        out = []
        for item in value:
            text = str(item).strip().lower()
            if text != "":
                out.append(text)
        return out

    def _string_set(self, items) -> list:
        normalized = self._normalize_string_array(items)
        unique = []
        for item in normalized:
            if item not in unique:
                unique.append(item)
        return unique

    def _sets_overlap_enough(self, left: list, right: list, threshold_percent: int) -> bool:
        if len(left) == 0 and len(right) == 0:
            return True
        if len(left) == 0 or len(right) == 0:
            return False
        overlap = 0
        for item in left:
            if item in right:
                overlap += 1
        smaller = len(left)
        if len(right) < smaller:
            smaller = len(right)
        return overlap * 100 >= smaller * threshold_percent

    def _allowed(self, value, allowed: list, fallback: str) -> str:
        text = str(value).strip().lower()
        if text in allowed:
            return text
        return fallback

    def _coerce_int(self, value) -> int:
        try:
            parsed = int(value)
        except Exception:
            return 0
        if parsed < 0:
            return 0
        if parsed > 100:
            return 100
        return parsed

    def _now_iso(self) -> str:
        return str(gl.block.timestamp)
