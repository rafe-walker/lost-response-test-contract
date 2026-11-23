# Lost-Response Test Contract

A neutral, shared test contract for one narrow failure case in agent-to-tool
systems: a mutating tool call commits its external effect, the response is
lost before the caller receives it, and the caller retries.

This repository is the canonical home for the contract text, the fixtures,
the execution instructions, and the recorded results. It belongs to no
single implementation. The public discussion lives in the MCP issue thread
that raised the case (modelcontextprotocol/modelcontextprotocol issue
#3394); this repository is where the test itself is kept.

## The three properties, kept separate

The contract scores three properties independently. A system can pass one
and fail another, and the results are recorded that way.

1. **Effect count.** Under same-operation retries after a lost response,
   the external effect happens exactly once.
2. **Authorization binding.** A retry whose action or parameters no longer
   match the original authorization, under the same operation identity, is
   rejected and produces no effect.
3. **Outcome recovery.** The caller can recover the original committed
   outcome, with digest equality against the original committed result as
   the evidence that the original record was recovered rather than the
   operation re-executed.

## Neutrality rule

The same contract, equivalent failure conditions, and independently
recorded results for both systems. Neither side changes its implementation
to satisfy the test before the contract is established. If either
implementation fails an assertion, the failure is reported as observed.
Scores are recorded per assertion, per system, with raw outputs linked.
There is no aggregate score.

## Status

Draft, under joint review. The assertion set in CONTRACT.md is the
starting text, open for joint revision before any run counts. Results go
in RESULTS.md.

Check the evidence shape yourself: every attempt the Zambo adapter runs
leaves a public, recomputable receipt. One worked-example job from
November 19, 2026: the [BTC live_price receipt](https://zambo.dev/run/e53423b0-1de0-44da-b862-19e0eed7fb68)
[![receipt check](https://zambo.dev/api/receipt/e53423b0-1de0-44da-b862-19e0eed7fb68/badge.svg?ref=badge)](https://zambo.dev/run/e53423b0-1de0-44da-b862-19e0eed7fb68),
and the [handover](https://zambo.dev/handover/97c9ef52-d3bd-44b3-bfeb-7f5886572f7f)
binding its five steps (three live prices, one honestly recorded
failure, one zero-result search). Any receipt can be rechecked at
https://zambo.dev/verify/.

## Run the harness

The runnable fixture harness lives in fixtures/harness/. It runs
assertions A1 to A5 against any MCP endpoint, with the fault injector,
the shared external effect counter defined in fixtures/README.md, and
raw outputs per run.

```bash
cd fixtures/harness
pip install -r requirements.txt
python3 lost_response.py --config config.zambo.json --out ../../runs/my-run
```

Configuration (in the config JSON): the top-level keys select the
adapter (`adapter`, `system_name`, and `a5_delay_hours`, the A5
delay, 24 by default); the adapter's own knobs live under
`adapter_config`. For the Zambo adapter they are `endpoint` (the MCP
endpoint to test), `public_base` (where the system's durable public
record lives), `tool` (the target mutating tool), `args_template`
(the arguments A, with `{K}` for the stable operation identity and
`{SESSION}` for the fresh run-scoped session identity), and
`mismatch` (the one parameter A2 changes, and its altered value).
The delayed A5 leg runs later against a planted run:

```bash
python3 lost_response.py --delayed-leg ../../runs/my-run/a5_plant.json
```

Full harness documentation, including the target tool choice for
Zambo and how each assertion is executed and scored, is in
fixtures/harness/README.md. Recorded runs and their raw outputs are
in runs/, scored in RESULTS.md.

## Run it against your system

The harness driver owns the scoring; everything system-specific
lives behind an adapter interface in fixtures/harness/adapters/.
An adapter implements five operations: open the run, execute an
attempt (including the dropped-response attempt), read the shared
external effect counter from the system's durable public record,
resolve a record by its server-issued id with a digest check, and
attempt recovery holding only the operation identity K.

To run the contract against another implementation:

1. Copy fixtures/harness/adapters/stub.py to
   fixtures/harness/adapters/<your_system>.py and implement the
   five operations against your system. The stub is a template: it
   describes no real system's behavior. The contract for each
   operation is in fixtures/harness/adapters/base.py, and the full
   guide is fixtures/harness/adapters/README.md.
2. Write a config JSON (fixtures/harness/config.example.json is the
   template) naming your adapter and carrying its settings under
   `adapter_config`.
3. Run it:

   ```bash
   cd fixtures/harness
   pip install -r requirements.txt
   python3 lost_response.py --config <your config>.json --out ../../runs/<run-dir>
   ```

   At or after the A5 delay (24 hours by default), run the delayed
   leg against the plant the run wrote:

   ```bash
   python3 lost_response.py --delayed-leg ../../runs/<run-dir>/a5_plant.json
   ```

4. Publish the run back in the same form the recorded runs use:
   the pinned versions (the contract and harness commit the run was
   executed against, and the adapter's name and version or commit),
   the full run directory of raw outputs, the external effect
   counts with the identifier lists they were counted from, and the
   caller-visible outcome of every retry and recovery path, as
   returned. Add one row per assertion to RESULTS.md: pass, fail,
   or unproven, evidence linked, no aggregate score.

The contract remains a draft, ready to freeze on both parties'
confirmation; runs published before the freeze are recorded as
observed, under the same rules as the runs already in RESULTS.md.

## Changelog

- 2026-11-16: The harness was refactored behind an adapter
  interface (fixtures/harness/adapters/): the driver owns the
  scoring, and each system under test is reached through an adapter
  implementing five documented operations. The Zambo adapter is the
  original harness behavior, moved unchanged; a stub adapter is
  provided as the template for a new system, with a "Run it against
  your system" guide in this README and in
  fixtures/harness/adapters/README.md. A reproduction run through
  the adapter (runs/2026-11-16-zambo-2/) is recorded in RESULTS.md.
- 2026-11-16: Yared Mengistu reviewed assertions A1 to A5 and agreed
  with the assertions and the scoring model. Four clarifications from
  that review are incorporated in CONTRACT.md: a common external effect
  counter for A1, K-only recovery for A3, retention semantics for A5,
  and historical baselines preserved separately from jointly executed
  results. The contract is ready to freeze on both parties'
  confirmation.
