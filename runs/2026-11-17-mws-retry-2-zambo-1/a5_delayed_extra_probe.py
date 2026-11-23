#!/usr/bin/env python3
"""Supplementary A5 delayed legs for run 2026-11-17-mws-retry-2-zambo-1.

Mirrors runs/2026-11-17-zambo-2/a5_delayed_extra_probe.py procedure:
with a fresh client, full recover_by_key on K (direct lookup
GET /api/v2/receipt/<K>/verify, then continuity_get_recent with K
as the only identifier), then protection probes: enumerate the
effect count, send the identical delayed retry and the
modified-parameter delayed retry (action
lost_response_probe_altered) with the original session, enumerate
again. Raw outputs are saved individually; the combined record is
a5_delayed_extra.json.

Transport: python requests, Accept: application/json ONLY (via the
harness adapter). No payment is ever made; a payment_required
response is recorded as an observed response class.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[2] / "fixtures" / "harness"
sys.path.insert(0, str(HARNESS))

from adapters import load_adapter  # noqa: E402

OUT = Path(__file__).resolve().parent
K = "lr-op-d99166563b-a1"
SESSION = "lr-d99166563b-a1"
COMMITTED = "sha256:b57197d5333af492c73260784de351c587545b6837ddab98500386714d931b87"
ORIGINAL_RECEIPT = "2e9ebf1f-5743-48de-a34b-5b3584c4c102"


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def norm(d):
    return d.lower() if d else None


def main():
    plant = json.loads((OUT / "a5_plant.json").read_text(encoding="utf-8"))
    assert plant["K"] == K and plant["committed_digest"] == COMMITTED
    assert plant["session_id"] == SESSION
    acfg = plant["adapter_config"]
    adapter = load_adapter("zambo", acfg)

    init, init_summary = adapter.initialize()
    write("a5_delayed_extra_initialize.json", init)

    # --- Step 2: K-only recovery, fresh client holding only K ---
    recovery = adapter.recover_by_key(operation_key=K)
    rename = {
        "a3_konly_run_lookup.json": "a5_delayed_konly_run_lookup.json",
        "a3_konly_continuity_get_recent.json": "a5_delayed_konly_continuity_get_recent.json",
    }
    for orig, new in rename.items():
        if orig in (recovery.get("files") or {}):
            write(new, recovery["files"][orig])
    lookup = recovery["files"]["a3_konly_run_lookup.json"]
    cont = recovery["files"].get("a3_konly_continuity_get_recent.json") or {}
    cont_blob = json.dumps(cont.get("body") or cont)
    direct_digest = (lookup.get("digests") or {}).get("output_hash")
    cont_has_digest = norm(COMMITTED) in cont_blob.lower() or COMMITTED.removeprefix("sha256:") in cont_blob.lower()
    cont_has_receipt = ORIGINAL_RECEIPT in cont_blob
    recovered_equal = bool(
        (direct_digest and norm(direct_digest) == norm(COMMITTED))
        or cont_has_digest
    )
    k_only = {
        "attempts": recovery["attempts"],
        "observed": "pass" if recovered_equal else "fail",
        "recovered_digest_equal_to_committed": recovered_equal,
        "direct_lookup_http_status": lookup.get("http_status"),
        "direct_lookup_digests": lookup.get("digests"),
        "continuity_response_class": cont.get("response_class"),
        "continuity_has_committed_digest": cont_has_digest,
        "continuity_has_original_receipt_id": cont_has_receipt,
        "score_basis": "pass only if a K-only attempt returns the committed outcome with digest equal to committed digest",
    }

    # --- Step 3: protection probes ---
    before = adapter.count_effects(session_id=SESSION, operation_key=K, label="a5_delayed_before_protection")
    for name, obj in (before.get("files") or {}).items():
        write(name, obj)
    write("count_a5_delayed_before_protection.json", before["evidence"])
    count_before = before["evidence"]["external_effect_count"]
    ids_before = before["evidence"].get("target_tool_execution_receipt_ids") or []

    identical = adapter.execute(session_id=SESSION, operation_key=K, drop_response=False)
    write("a5_delayed_retry_identical.json", {
        "label": "a5_delayed_retry_identical", "at": utcnow(), "session_id": SESSION, "K": K,
        "arguments_sent": identical["arguments_sent"], "call": identical["call"]})

    mismatched = adapter.execute(session_id=SESSION, operation_key=K, mismatched=True, drop_response=False)
    write("a5_delayed_retry_mismatched.json", {
        "label": "a5_delayed_retry_mismatched", "at": utcnow(), "session_id": SESSION, "K": K,
        "arguments_sent": mismatched["arguments_sent"], "call": mismatched["call"]})

    final = adapter.count_effects(session_id=SESSION, operation_key=K, label="a5_delayed_after_protection")
    for name, obj in (final.get("files") or {}).items():
        write(name, obj)
    write("count_a5_delayed_final.json", final["evidence"])
    count_final = final["evidence"]["external_effect_count"]
    ids_final = final["evidence"].get("target_tool_execution_receipt_ids") or []

    ident_class = identical["call"].get("response_class")
    ident_ids = identical["call"].get("receipt_ids") or []
    mism_class = mismatched["call"].get("response_class")
    mism_ids = mismatched["call"].get("receipt_ids") or []
    mism_blob = json.dumps(mismatched["call"].get("body") or {}).lower()
    ident_body_blob = json.dumps(identical["call"].get("body") or {})
    identical_ok = bool(
        (ident_ids and all(i == ORIGINAL_RECEIPT for i in ident_ids))
        or ident_class in ("payment_required",)
        or (ident_class and ident_class.startswith("tool_error"))
        or "idempotent_replay" in ident_body_blob
    )
    if ident_class == "success":
        identical_ok = bool("idempotent_replay" in ident_body_blob and ORIGINAL_RECEIPT in ident_body_blob and count_final == count_before)
    mismatched_ok = bool(
        ("conflict" in mism_blob)
        or (mism_class and ("conflict" in mism_class or mism_class.startswith("tool_error")))
    )
    if mism_class == "payment_required":
        mismatched_ok = False
    protected = bool(count_before == 1 and count_final == 1 and identical_ok and mismatched_ok)

    protection = {
        "count_before": count_before,
        "count_final": count_final,
        "execution_receipt_ids_before": ids_before,
        "execution_receipt_ids_final": ids_final,
        "identical_retry": {"receipt_ids": ident_ids, "response_class": ident_class},
        "mismatched_retry": {"altered_value": "lost_response_probe_altered", "mismatched_field": "action", "receipt_ids": mism_ids, "response_class": mism_class},
        "protected": protected,
    }

    extra = {
        "K": K,
        "assertion": "A5",
        "committed_digest": COMMITTED,
        "extra_legs_run_at_note": "timestamps inside raw files",
        "initialize": init_summary,
        "k_only_recovery": k_only,
        "protection": protection,
        "session_id": SESSION,
    }
    write("a5_delayed_extra.json", extra)
    print(json.dumps(extra, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
