# APC adapter contribution — review branch

This contribution adds an APC Enterprise adapter and a synthetic test-provider fixture to the lost-response harness.

## Scope

- `fixtures/harness/adapters/apc.py` maps the harness to APC's production REST API.
- `fixtures/harness/config.apc.example.json` contains placeholders only.
- `fixtures/apc-test-provider/` provides an independently countable synthetic effect ledger for isolated tests.

The adapter requires a separate durable effect counter. It does not count APC response bodies, APC invocation IDs, APC database rows, or APC event-chain records as external effects. The provider fixture is synthetic only and must never be connected to a live payment, commerce, customer, or other real provider.

## Test status

The adapter passed a local **mock-interface software check** against a simulated APC REST endpoint and the synthetic provider. That is not an APC product result. A1–A4 have not been run against the deployed APC product; A5 requires a real 24-hour delayed run. No certification or independent assessment is claimed.
