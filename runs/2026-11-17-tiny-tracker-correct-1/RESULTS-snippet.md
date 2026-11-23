Run 409891e807 against http://127.0.0.1:47310/mcp (tool create_ticket), started 2026-11-17T02:13:28.514342Z.

| Assertion | Outcome | Evidence |
|---|---|---|
| A1 | pass | external effect count for the logical operation is exactly 1 |
| A2 | pass | mismatched retry produced no new effect and was explicitly refused |
| A3 | unproven | contract pass condition is the K-only leg: no committed digest exists, so K-only recovery cannot be scored; run-id leg scored fail separately in the evidence |
| A4 | pass | every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state |
| A5 | unproven | scored by score_a5 (PR 3) from the archived observations, no re-run. Recovery: unproven (no committed digest was recorded at plant time to compare against; the K lookup answered 404 and the run-id lookup of T-1 answered HTTP 200 with no digest, diagnostic only). Retry protection: unproven (no recorded before/after counts or delayed retry records in the form score_a5 reads). Overall: unproven; this replaces the earlier fail under the superseded inline rule. Beside it, not a score: a K-only replay at +24 h (a5_supplementary_konly.json) held (replayed: true, count 1 to 1) |
