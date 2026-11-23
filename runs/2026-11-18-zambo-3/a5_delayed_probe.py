#!/usr/bin/env python3
"""A5 delayed leg for run 2026-11-18-zambo-3.

Fresh client throughout; python requests, Accept: application/json ONLY,
endpoint https://zambo.dev/mcp. Uses the working client from the
acceptance run at ~/tmp-build/a5-accept/client.py.
Plant: K lr-op-bb150ceec1-a1, session lr-bb150ceec1-a1, committed receipt
e2568939-b651-4150-b059-a1eeebbf7319, committed digest
sha256:c63fbfb9a34b33df4e5d2d821186ba7020c7e67217d8f80958b228710f106818,
due 2026-11-19T18:38:16Z.
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import requests

sys.path.insert(0, "/home/hatch/tmp-build/a5-accept")
from client import initialize, call_tool, op_args, count_effects, rpc

OUT = Path("/home/hatch/workspace/order66-2026-11-15/lost-response-test-contract/runs/2026-11-18-zambo-3")
K = "lr-op-bb150ceec1-a1"
SESSION = "lr-bb150ceec1-a1"
COMMITTED = "sha256:c63fbfb9a34b33df4e5d2d821186ba7020c7e67217d8f80958b228710f106818"
ORIGINAL_RECEIPT = "e2568939-b651-4150-b059-a1eeebbf7319"
DUE = "2026-11-19T18:38:16.846509Z"

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

res = {"run": "2026-11-18-zambo-3", "assertion": "A5", "K": K,
       "session_id": SESSION, "committed_receipt_id": ORIGINAL_RECEIPT,
       "committed_digest": COMMITTED, "due_at": DUE,
       "delayed_leg_run_at": utcnow(), "endpoint": "https://zambo.dev/mcp",
       "system_name": "Zambo production"}
assert datetime.now(timezone.utc).isoformat() > "2026-11-19T18:38:16+00:00", "too early"

# 1. Fresh initialize
st, init = initialize()
w("a5_delayed_initialize.json", {"http": st, "body": init})
res["initialize_http"] = st

# 2a. K-only recovery: direct public-record lookup by K
http_lookup, lookup = verify_receipt(K)
w("a5_delayed_konly_run_lookup.json", {"http_status": http_lookup, "body": lookup})
rec = lookup.get("receipt") or {}
served_digest = rec.get("output_hash")
commitment = lookup.get("commitment") or {}
direct_digest_equal = bool(served_digest and served_digest.lower() == COMMITTED.lower())
res["k_only_recovery"] = {"direct_lookup": {
    "http_status": http_lookup,
    "digests": {"output_hash": served_digest,
                "input_hash": rec.get("input_hash")},
    "commitment": commitment,
    "digest_equal_to_committed": direct_digest_equal}}

# 2b. K-only recovery: continuity_get_recent with K as only identifier
cont = call_tool("continuity_get_recent", {"_session_id": K})
w("a5_delayed_konly_continuity_get_recent.json", cont["body"])
cblob = json.dumps(cont["body"])
cont_has_receipt = ORIGINAL_RECEIPT in cblob
cont_has_digest = COMMITTED in cblob or COMMITTED.removeprefix("sha256:") in cblob
res["k_only_recovery"]["continuity_fresh_client"] = {
    "response_class": cont["class"],
    "returned_committed_outcome": bool(cont_has_receipt and cont_has_digest),
    "has_original_receipt_id": cont_has_receipt,
    "has_committed_digest": cont_has_digest}
recovered_equal = bool(direct_digest_equal or cont_has_digest)
res["k_only_recovery"]["recovered_digest_equal_to_committed"] = recovered_equal
res["k_only_recovery"]["observed"] = "pass" if recovered_equal else "fail"

# 2c. Run-id leg: resolve committed receipt id directly
http_runid, runid = verify_receipt(ORIGINAL_RECEIPT)
w("a5_delayed_runid_receipt.json", {"http_status": http_runid, "body": runid})
runid_rec = runid.get("receipt") or {}
runid_digest = runid_rec.get("output_hash")
res["k_only_recovery"]["run_id_leg"] = {
    "http_status": http_runid,
    "digest_served": runid_digest,
    "digest_equal": bool(runid_digest and runid_digest.lower() == COMMITTED.lower()),
    "verification_status": runid.get("verification_status") or runid_rec.get("verification_status")}

# 3. Protection probes
before = count_effects(SESSION, K)
w("a5_delayed_count_before.json", before["body"])
w("count_a5_delayed_before_protection.json",
   {"external_effect_count": before["count"],
    "target_tool_execution_receipt_ids": sorted(before["targets"]),
    "targets": before["targets"], "http": before["http"]})
count_before = before["count"]
ids_before = sorted(before["targets"])

ident = call_tool("journal_log", op_args(SESSION, K))
w("a5_delayed_retry_identical.json", ident["body"])
res_ident = {"class": ident["class"], "receipt_ids": ident["receipt_ids"],
             "replay_marker": ident["replay"]}

mism = call_tool("journal_log", op_args(SESSION, K, altered=True))
w("a5_delayed_retry_mismatched.json", mism["body"])
res_mism = {"class": mism["class"], "receipt_ids": mism["receipt_ids"],
            "replay_marker": mism["replay"]}

after = count_effects(SESSION, K)
w("a5_delayed_count_after.json", after["body"])
w("count_a5_delayed_final.json",
   {"external_effect_count": after["count"],
    "target_tool_execution_receipt_ids": sorted(after["targets"]),
    "targets": after["targets"], "http": after["http"]})
count_final = after["count"]
ids_final = sorted(after["targets"])

# Resolve any new children receipts to check whether they are executions
new_ids = [i for i in ids_final if i not in ids_before]
new_child_tools = {}
for rid in new_ids:
    t, h, d = None, None, None
    try:
        hs, dd = verify_receipt(rid)
        rr = dd.get("receipt") or {}
        t, h = rr.get("tools"), rr.get("output_hash")
        w(f"a5_delayed_new_child_{rid}.json", {"http_status": hs, "body": dd})
    except Exception as e:
        new_child_tools[rid] = {"error": str(e)}
    else:
        new_child_tools[rid] = {"tools": t, "output_hash": h}
# Also resolve the mismatched retry's receipt (refusal record check)
mism_receipt_tools = {}
for rid in (mism["receipt_ids"] or []):
    hs, dd = verify_receipt(rid)
    rr = dd.get("receipt") or {}
    mism_receipt_tools[rid] = {"tools": rr.get("tools"),
                               "output_hash": rr.get("output_hash"),
                               "step": (dd.get("receipt") or {}).get("step")}
    w(f"a5_delayed_mismatched_receipt_{rid}.json", {"http_status": hs, "body": dd})

ident_executed_fresh = bool(ident["receipt_ids"] and ident["receipt_ids"] != [ORIGINAL_RECEIPT] and not ident["replay"])
ident_ok = bool(ident["replay"] and ident["receipt_ids"] == [ORIGINAL_RECEIPT])
mism_ok = bool("idempotency_conflict" in (mism["class"] or "") and not new_ids)
protected = bool(count_before == 1 and count_final == 1 and ident_ok and mism_ok)

res["protection"] = {
    "count_before": count_before, "count_final": count_final,
    "execution_receipt_ids_before": ids_before,
    "execution_receipt_ids_final": ids_final,
    "new_children_after_retries": new_ids,
    "new_children_tools": new_child_tools,
    "identical_retry": {"response_class": ident["class"],
                        "receipt_ids": ident["receipt_ids"],
                        "replay_marker": ident["replay"],
                        "executed_fresh": ident_executed_fresh,
                        "replays_original": ident_ok},
    "mismatched_retry": {"response_class": mism["class"],
                         "receipt_ids": mism["receipt_ids"],
                         "replay_marker": mism["replay"],
                         "receipt_tools": mism_receipt_tools,
                         "refused_as_conflict": "idempotency_conflict" in (mism["class"] or "")},
    "protected": protected,
    "observed": "pass" if protected else "fail"}

score = "pass" if (recovered_equal and protected) else "fail"
res["score"] = score
res["score_basis"] = ("Pass only if K-only recovery after the delay returns the committed "
    "outcome with digest equal to the committed digest AND the operation identity stayed "
    "protected during the window (neither delayed retry executes; effect count stays 1; "
    "identical retry replays; modified-parameter retry is refused as a conflict).")
res["scored_at"] = utcnow()
res["evidence_files"] = sorted(p.name for p in OUT.glob("a5_delayed_*")) + sorted(p.name for p in OUT.glob("count_a5_delayed_*"))
w("a5_delayed_extra.json", res)
w("summary_a5.json", res)
print(json.dumps(res, indent=2))
