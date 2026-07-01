# IntentEscrow

IntentEscrow is a standalone GenLayer Intelligent Contract primitive for autonomous-agent commitment markets.

A user posts an intent. Agents submit commitment plans. GenLayer consensus selects the best commitment and later resolves whether the execution trace satisfied the original intent and the agent's own plan. The contract updates payout eligibility and agent reputation as durable state.

## Submission summary

Most escrow contracts lock value around deterministic conditions. IntentEscrow locks value around autonomous agency: agents make comparable promises, promises become market positions, execution traces are resolved against commitments, and reputation changes future access to work.

This is not a full app and not a thin LLM wrapper. It is a reusable coordination primitive for apps that delegate goals to autonomous agents.

## Why this is not generic “AI decides X”

IntentEscrow separates two consensus boundaries:

1. **Commitment selection** — validators rank proposed agent plans against hard constraints, soft preferences, fee, deadline feasibility, risk disclosure, and reputation fit.
2. **Completion resolution** — validators compare an execution trace against both the original intent and the accepted commitment.

The contract stores stable semantic packets, not freeform prose: selected commitment, outcome bucket, constraint failures, payout band, reputation delta band, misrepresentation flag, trace references, and rationale.

## Contract flow

1. `create_intent(...)`
   - user stores goal, hard constraints, soft preferences, max fee, escrow label, and deadline
2. `propose_commitment(...)`
   - agent stores a plan, requested fee, deadline, risk disclosures, and capability tags
3. `select_commitment(...)`
   - GenLayer validators rank proposals and store the selected commitment
4. `submit_execution_trace(...)`
   - selected agent submits trace artifacts and completion notes
5. `resolve_execution(...)`
   - GenLayer validators resolve outcome, payout band, and reputation delta
6. View methods expose intent, commitment, resolution, and reputation state.

## Stored resolution packet

Each completion resolution stores:

- `outcome_bucket`: `satisfied`, `partial`, `failed`, `invalid_trace`, or `misrepresented_plan`
- `payout_band`: `none`, `low_partial`, `high_partial`, or `full`
- `reputation_delta_band`: `major_negative`, `minor_negative`, `neutral`, `positive`, or `strong_positive`
- `hard_constraint_failures`: IDs of failed hard constraints
- `soft_preference_score`: coarse 0–100 optimization score
- `misrepresentation`: whether the agent materially deviated from its commitment
- `trace_refs`: compact references to trace artifacts
- `rationale`: short evidence-backed explanation

## Repository layout

- `contracts/intent_escrow.py` — standalone GenLayer Intelligent Contract
- `tests/test_contract_static.py` — static submission-quality checks
- `tests/test_fixture_semantics.py` — fixture and semantic packet checks
- `scripts/check.sh` — local validation runner
- `scripts/deploy.sh` — deployment helper
- `docs/consensus-design.md` — consensus/equivalence model
- `docs/examples.md` — reusable examples
- `docs/deployment.md` — deployment prep notes

## Local validation

```bash
python3.12 -m venv .venv312
. .venv312/bin/activate
pip install pytest genvm-linter
./scripts/check.sh
```

## Deployment prep

Deployment requires a configured GenLayer CLI account/network. See `docs/deployment.md`.

```bash
genlayer network list
genlayer network set studionet
./scripts/deploy.sh studionet
```

Always inspect receipt and trace. Transaction accepted/finalized is not enough; verify execution success.
