# IntentEscrow consensus design

## Goal

IntentEscrow is a reusable primitive for autonomous-agent commitment markets. It lets users post intents, lets agents bind themselves to plans, then uses GenLayer consensus to select commitments and resolve execution quality.

## Boundary 1: commitment selection

The leader receives:

- intent goal
- hard constraints
- soft preferences
- max fee
- deadline
- proposed commitments
- known reputation packets

The leader derives:

- selected commitment ID
- ranked commitment IDs
- rejected commitment IDs
- selection factors
- risk flags
- rationale

Validators independently rank proposals. They accept if they agree on selected commitment, or if top-ranked commitments are equivalent under the same hard constraints and risk/failure classes.

Stable comparison fields:

- selected commitment ID
- accepted top-k overlap
- blocking risk flags
- fee band
- deadline feasibility band
- reputation fit band

## Boundary 2: completion resolution

After the selected agent submits an execution trace, the leader receives:

- original intent
- accepted commitment
- execution trace
- deadline and requested fee
- prior reputation

The leader derives:

- outcome bucket
- hard constraint failure IDs
- soft preference score
- payout band
- reputation delta band
- misrepresentation flag
- trace references
- rationale

Validators independently inspect the trace and compare stable fields.

Stable comparison fields:

- same outcome bucket
- same payout band
- same reputation delta band
- enough overlap in hard constraint failures
- same misrepresentation flag
- same invalid-trace class, when applicable

## Why not strict equality?

Agent traces are messy. Two validators may describe the same failure differently. The contract compares constraint IDs, outcome buckets, payout bands, and reputation bands rather than exact prose.

## Why not schema-only validation?

A schema validator would accept any well-formed trace. IntentEscrow requires validators to judge whether the trace satisfies the intent and whether the agent honored the accepted commitment.

## Risks and mitigations

- Ambiguous intents → require structured hard constraints and soft preferences.
- Trace fabrication → require trace references and invalid-trace bucket.
- Reputation farming → track domain tags, failure counts, and misrepresentation flags.
- Collusion → store durable resolution packets so downstream apps can discount suspicious patterns.
- Over-optimization for validators → keep user hard constraints explicit and machine-readable.
