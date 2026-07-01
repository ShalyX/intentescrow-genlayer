# IntentEscrow examples

## 1. Shopping agent

Intent: "Find and reserve a GPU under 600 USDC equivalent, delivery under 5 days, seller reputation above 4.5, max agent fee 30."

Agents submit commitment plans with search strategy, fee, deadline, and risk disclosures. The selected agent submits receipt/order trace references. Resolution checks budget, delivery estimate, seller reputation, and plan deviations.

## 2. Code-fixing agent

Intent: "Fix issue #42 without changing public API, add regression tests, max fee 50."

Commitments describe patch strategy and test plan. Execution trace includes PR link, test output, and diff summary. Resolution checks issue relevance, test coverage, API stability, and whether the plan was misrepresented.

## 3. Research agent

Intent: "Find the three strongest primary sources for claim X and summarize disagreement points."

Commitments disclose source strategy. Execution trace includes source links and summaries. Resolution checks source quality, contradiction handling, and completeness against the requested research scope.

## 4. DAO operations

Intent: "Prepare a governance proposal draft from forum discussion, include tradeoffs, and submit before Friday."

Commitments include governance-process knowledge and timeline. Trace includes draft, forum link, and submission proof. Resolution checks deadline, required sections, and whether the agent followed governance rules.
