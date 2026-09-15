# WS-D: tool-description and schema changes the other streams have to make

D11 fixes an ambiguous tool boundary by adding a cue to the question AND by making the
tool descriptions say where the boundary runs. WS-D owns only `benchmarks/` and
`benchmarks_en/`, so the description side is listed here instead of edited.

Checked against `STAR-Bench-Web@df8c0cb` (`src/features/agent.py`) on 2026-09-16.

## Already done on the platform branch (no action, listed so the data side can rely on it)

| # | Tool | What the description now says | Data issue it settles |
|---|---|---|---|
| 1 | `detect_smurfing_network` | "Only the counterparty count in that one direction is considered; for accounts that collect from many and then forward to a few, use `detect_aml_patterns` with `pattern_type='funnel'`." | L1-003 |
| 2 | `detect_aml_patterns` | funnel is defined by `min_inflow` distinct senders and 1..`max_outflow` receivers; no tool says "mule account" any more | L1-003 |
| 3 | `get_statistics` | lists the distinct sender and receiver account counts, the bank counts and the total amount | L1-005 (b): st_gs_004, st_gs_016, st_gs_033, st_gs_036 keep their gold |
| 4 | `get_account_profile` | "counting the transactions it sends and the transactions it receives ... total/outbound/inbound counts" | L1-009: st_gap_037 keeps `get_account_profile` alone |
| 5 | `detect_monitoring_alerts` | R003 is "Repeated Identical Amounts: accounts that send the same amount (2,000,000 KRW or more) at least 3 times" | L1-008, D18 |
| 6 | `get_aml_glossary`, `lookup_fiu_reference_types` | the catalog is English, the 13 glossary terms are listed, there are no Korean entries | L3-011 |

## Still needed

| # | Owner | Change | Why |
|---|---|---|---|
| 7 | WS-C (`_experiments/scripts/tools_kr.py`) | The Korean schema must carry the same R003 wording as the platform: `정액거래패턴` becomes `동일 금액 반복 송금` (the rule counts repeated identical amounts, it does not test a round number). Every other rule label must match `RULE_NAMES` too. | L1-008; D16 requires the KR schema to be structurally identical to `agent.TOOLS` |
| 8 | WS-A (system prompt, D08) | State the D10 rule once: "A request for the definition or the comparison of a term the AML glossary holds is answered with `get_aml_glossary`; any other conceptual explanation is answered without a tool." The 13 terms are already in the tool description. | L6-009: the glossary cases and the abstention cases contradicted each other |
| 9 | WS-A (`detect_aml_patterns`) | Keep the sentence that says HOFINET's transfer graph is acyclic, so `ring` and `layering` return nothing (D06). 40 single-turn gold calls return an empty result by construction: 17 ring, 11 layering and **12 funnel**. The funnel case is new: only 414 accounts both send and receive, none of them forwards to 3 or fewer counterparties, and the largest inflow among accounts with 6 or fewer outgoing counterparties is 5, so the default `min_inflow=10, max_outflow=3` can never match. Either lower the defaults (`min_inflow=5, max_outflow=5` does match) or state in the description that funnel returns nothing on HOFINET. WS-D did not pin funnel parameters into the gold because D06 rebuilds this tool. | D06, WS-D gold-call execution |
| 10 | WS-B (scoring) | `expected.alternatives` is now used by 16 single-turn cases (8 abstention cases from D10, `st_gl_006`, and 7 more in the clarification pass). The scorer already supports it; the data linter checks the shape. | D10, D19 |

## Wording rules the data now follows (for the multi-turn stream to mirror)

* CTR cases say `구조화(structuring)` / "structuring below the reporting threshold"; the HOFINET
  fraud type 3 is always `분할 거래(유형3)` / "split transaction (type 3)". Never "분할거래" for CTR.
* Funnel questions state "many incoming counterparties, few outgoing"; smurfing questions state a
  counterparty threshold in one direction.
* Monitoring-rule questions name the rule or its alert ("모니터링 규칙", "R003", "알림").
* `query_transactions` questions say "SQL로" / "with SQL" when a dedicated tool could also answer.
* Account ids are the real 16-digit HOFINET ids; fund type 4 never appears in a fraud question;
  amounts are among the 48 values HOFINET holds.
