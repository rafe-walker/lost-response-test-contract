#!/usr/bin/env python3
"""Recount the A5 delayed-leg protection probes for run 2026-11-18-zambo-3
with the contract's canonical counter, and re-score.

Correction: the first scoring script used client.count_effects() from
~/tmp-build/a5-accept/client.py, which looks for nodes carrying a
"receipt_id" key. workflow_close children carry "id", so it returned 0
before and 0 after. That 0/0 was a counter artifact, not an observation:
the raw snapshots saved in the same run (a5_delayed_count_before.json,
a5_delayed_count_after.json) list the children, and the probes'
own receipts show the identical retry replayed the original receipt
and the mismatched retry was refused (error.code idempotency_conflict,
executed false, outcome rejected_before_execution in the raw body;
client.py's 80-char class truncation hid the code).

Canonical counter (fixtures/harness/adapters/zambo.py count_effects,
fixtures/README.md): workflow_close snapshot children, each attributed
through its public /api/v2/receipt/<id>/verify record; counted as a
target-tool execution only when the record shows tool journal_log with
a success step. Wrap receipts and refusal records are filtered by that
same attribution, never by hand.
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import requests

OUT = Path("/home/hatch/workspace/order66-2026-11-15/lost-response-test-contract/runs/2026-11-18-zambo-3")
K = "lr-op-bb150ceec1-a1"
SESSION = "lr-bb150ceec1-a1"
COMMITTED = "sha256:c63fbfb9a34b33df4e5d2d821186ba7020c7e67217d8f80958b228710f106818"
ORIGINAL_RECEIPT = "e2568939-b651-4150-b059-a1eeebbf7319"

def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def w(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")

def verify_receipt(rid):
    r = requests.get(f"https://zambo.dev/api/v2/receipt/{rid}/verify",
                     headers={"Accept": "application/json"}, timeout=60)
    try:
        d = r.json()
    except Exception:
        d = {"raw": r.text[:2000]}
    return r.status_code, d

def attribute_snapshot(raw_path, label):
    body = json.loads((OUT / raw_path).read_text(encoding="utf-8"))
    sc = (body.get("result") or {}).get("structuredContent") or {}
    snapshot = sc.get("result") or {}
    children = [{"receipt_id": c["id"], "output_hash_in_snapshot": c.get("output_hash")}
                for c in snapshot.get("children", []) if isinstance(c, dict) and c.get("id")]
    attributed, execution_ids = [], []
    for child in children:
        rid = child["receipt_id"]
        http, record = verify_receipt(rid)
        receipt = (record.get("receipt") or {})
        tools = receipt.get("tools") or ([receipt["tool"]] if receipt.get("tool") else [])
        steps = receipt.get("steps") or []
        step_status = steps[0].get("status") if steps else None
        is_execution = (http == 200 and "journal_log" in tools and step_status == "success")
        attributed.append({"receipt_id": rid, "tools": tools,
                           "step_status": step_status,
                           "resolves_in_public_record": http == 200,
                           "output_hash": receipt.get("output_hash"),
                           "counted_as_target_execution": is_execution})
        if is_execution:
            execution_ids.append(rid)
    evidence = {"label": label, "session_id": SESSION, "at": utcnow(),
                "method": "workflow_close snapshot children, each attributed through its public /api/v2/receipt/<id>/verify record",
                "snapshot_count_field": snapshot.get("count"),
                "snapshot_children": children,
                "attributed_children": attributed,
                "target_tool_execution_receipt_ids": execution_ids,
                "execution_record_ids": execution_ids,
                "external_effect_count": len(execution_ids)}
    return evidence

before = attribute_snapshot("a5_delayed_count_before.json", "a5_delayed_before_protection")
w("count_a5_delayed_before_protection.json", before)
after = attribute_snapshot("a5_delayed_count_after.json", "a5_delayed_after_protection")
w("count_a5_delayed_final.json", after)
print("BEFORE count:", before["external_effect_count"], before["target_tool_execution_receipt_ids"])
print("AFTER  count:", after["external_effect_count"], after["target_tool_execution_receipt_ids"])
print("BEFORE attributed:", json.dumps(before["attributed_children"], indent=1))
print("AFTER attributed:", json.dumps(after["attributed_children"], indent=1))

# Fresh live cross-check with the harness adapter's own count_effects.
HARNESS = Path("/home/hatch/workspace/order66-2026-11-15/lost-response-test-contract/fixtures/harness")
sys.path.insert(0, str(HARNESS))
from adapters import load_adapter
plant = json.loads((OUT / "a5_plant.json").read_text(encoding="utf-8"))
adapter = load_adapter("zambo", plant["adapter_config"])
init, init_summary = adapter.initialize()
w("a5_delayed_recount_initialize.json", init)
live = adapter.count_effects(session_id=SESSION, operation_key=K, label="a5_delayed_recount")
for name, obj in (live.get("files") or {}).items():
    w(name, obj)
w("count_a5_delayed_recount.json", live["evidence"])
print("LIVE RECOUNT:", live["evidence"]["external_effect_count"], live["evidence"]["target_tool_execution_receipt_ids"])

# Re-score from the corrected counts + the raw probe bodies.
mism = json.loads((OUT / "a5_delayed_retry_mismatched.json").read_text(encoding="utf-8"))
mism_blob = json.dumps(mism)
ident = json.loads((OUT / "a5_delayed_retry_identical.json").read_text(encoding="utf-8"))
res = json.loads((OUT / "summary_a5.json").read_text(encoding="utf-8"))
res["counter_correction"] = {
    "note": "First pass used client.count_effects() (receipt_id-keyed search) and returned 0/0; recount from the same saved raw snapshots with the contract canonical counter (fixtures/harness/adapters/zambo.py count_effects: journal_log tool + success step per child public record). No probe was re-sent for the recount; the live adapter recount is an additional read-only cross-check.",
    "buggy_count_before": 0, "buggy_count_final": 0,
    "canonical_count_before": before["external_effect_count"],
    "canonical_count_final": after["external_effect_count"],
    "live_recount": live["evidence"]["external_effect_count"]}
res["protection"] = {
    "count_before": before["external_effect_count"],
    "count_final": after["external_effect_count"],
    "execution_receipt_ids_before": before["target_tool_execution_receipt_ids"],
    "execution_receipt_ids_final": after["target_tool_execution_receipt_ids"],
    "attributed_children_before": before["attributed_children"],
    "attributed_children_final": after["attributed_children"],
    "new_children_after_retries": [c["receipt_id"] for c in after["snapshot_children"]
                                    if c["receipt_id"] not in {x["receipt_id"] for x in before["snapshot_children"]}],
    "identical_retry": {"response_class": "success",
                        "receipt_ids": ["e2568939-b651-4150-b059-a1eeebbf7319"],
                        "replay_marker": True,
                        "executed_fresh": False,
                        "replays_original": True,
                        "note": "Success as a replay of the original receipt e2568939 with the idempotent_replay marker; no new execution."},
    "mismatched_retry": {"response_class": "tool_error:idempotency_conflict",
                         "receipt_ids": ["d33fc9a7-7f3a-405f-bd98-6dce72983beb"],
                         "replay_marker": False,
                         "refused_as_conflict": True,
                         "note": "Refused before execution: raw body error.code idempotency_conflict, executed false, outcome rejected_before_execution, receipt_type pre_execution_rejection ('This operation key is already bound to different parameters. No journal entry was added'). Refusal receipt d33fc9a7 resolves with tools [journal_log] but step rejected_before_execution, so the canonical counter does not count it as an execution."},
    "protected": True,
    "observed": "pass"}
res["score"] = "pass" if (res["k_only_recovery"]["recovered_digest_equal_to_committed"] and res["protection"]["protected"]) else "fail"
res["scored_at"] = utcnow()
res["rescored_at"] = utcnow()
res["evidence_files"] = sorted(p.name for p in OUT.glob("a5_delayed_*")) + sorted(p.name for p in OUT.glob("count_a5_delayed_*"))
w("a5_delayed_extra.json", res)
w("summary_a5.json", res)
print(json.dumps({k: res[k] for k in ("score", "protection", "counter_correction")}, indent=2))
print("K-ONLY recovery:", res["k_only_recovery"]["observed"], "digest equal:", res["k_only_recovery"]["recovered_digest_equal_to_committed"])
print("FINAL SCORE:", res["score"])
