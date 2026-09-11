"""Step-0 spine proof for Hotdata: create -> load -> query -> query-runs -> delete."""
import os, sys, time, json, httpx
from dotenv import load_dotenv
load_dotenv()

API = os.environ["HOTDATA_API_URL"].rstrip("/")
H = {"Authorization": f"Bearer {os.environ['HOTDATA_API_KEY']}",
     "X-Workspace-Id": os.environ["HOTDATA_WORKSPACE_ID"],
     "Content-Type": "application/json"}

def step(msg): print(f"\n>>> {msg}", flush=True)
db_id = None
t0 = time.time()
with httpx.Client(timeout=60.0) as c:   # 60s: absorbs the 10-20s cold start
    step("warm workspace (cold start can take 10-20s)")
    r = c.get(f"{API}/workspaces", headers=H)
    print(f"    workspaces -> {r.status_code} in {time.time()-t0:.1f}s")
    r.raise_for_status()

    step("create database with declared schema+table (key + sorted_by fixed at create)")
    body = {"name": f"rg-smoke-{int(time.time())}", "expires_at": "1h",
            "schemas": [{"name": "main", "tables": [
                {"name": "units", "key": ["unit_id"], "sorted_by": [{"column": "unit_id"}]}]}]}
    r = c.post(f"{API}/databases", headers=H, json=body)
    print(f"    POST /databases -> {r.status_code}")
    if r.status_code >= 400: print("   ", r.text[:600]); sys.exit(1)
    d = r.json(); db_id = d["id"]
    print("   ", json.dumps({k: d.get(k) for k in
          ("id","created","default_catalog","default_schema","default_connection_id","expires_at")}, indent=2))

    DBH = {**H, "X-Database-Id": db_id}

    step("load inline CSV (mode=replace, first load into a new table)")
    csv = "unit_id,kind,status,crew\nE-101,engine,available,4\nE-102,engine,committed,4\nA-7,ambulance,available,2\n"
    r = c.post(f"{API}/databases/{db_id}/schemas/main/tables/units/loads", headers=H,
               json={"mode": "replace", "data": csv, "format": "csv",
                     "idempotency_key": f"smoke-{int(time.time())}"})
    print(f"    load -> {r.status_code} {r.text[:300]}")
    if r.status_code >= 400: sys.exit(1)

    step("query it back (note: rows are arrays, columns named separately)")
    r = c.post(f"{API}/query", headers=DBH,
               json={"sql": "SELECT kind, count(*) AS n, sum(crew) AS crew FROM default.main.units GROUP BY 1 ORDER BY 1"})
    print(f"    query -> {r.status_code}")
    if r.status_code >= 400: print("   ", r.text[:600]); sys.exit(1)
    q = r.json()
    print("    columns:", q["columns"], " rows:", q["rows"])
    print(f"    execution_time_ms={q.get('execution_time_ms')} total_row_count={q.get('total_row_count')}")

    step("append a second batch (proves accumulation for telemetry)")
    r = c.post(f"{API}/databases/{db_id}/schemas/main/tables/units/loads", headers=H,
               json={"mode": "append", "data": "unit_id,kind,status,crew\nT-3,tender,available,3\n",
                     "format": "csv", "idempotency_key": f"smoke-app-{int(time.time())}"})
    print(f"    append -> {r.status_code} rows-in-table-after={r.json().get('row_count') if r.status_code<400 else '?'}")

    step("GET /query-runs (the free per-query telemetry surface)")
    r = c.get(f"{API}/query-runs", headers=DBH)
    print(f"    query-runs -> {r.status_code}")
    if r.status_code < 400:
        runs = r.json()
        items = runs.get("query_runs") or runs.get("items") or runs.get("data") or []
        print(f"    {len(items)} run(s); first keys: {sorted(items[0].keys()) if items else 'n/a'}")
        if items:
            f = items[0]
            print("    sample:", json.dumps({k: f.get(k) for k in
                  ("status","execution_time_ms","server_processing_ms","bytes_scanned","rows_scanned","sql_hash")}))
    else: print("   ", r.text[:300])

    step("DELETE database (explicit teardown, not relying on TTL)")
    r = c.delete(f"{API}/databases/{db_id}", headers=H)
    print(f"    delete -> {r.status_code}")
    r2 = c.get(f"{API}/databases/{db_id}", headers=H)
    print(f"    confirm gone -> {r2.status_code}")

print(f"\n=== HOTDATA SPINE OK ({time.time()-t0:.1f}s total) ===")
