"""Create the PERMANENT telemetry database. Idempotent -- safe on every startup.

  * No expires_at  => it is never auto-deleted and accumulates across all runs.
  * if_not_exists  => re-running returns the existing DB (created=false) and
                      changes nothing.
  * key[]/sorted_by[] are declared HERE because there is no ALTER path in Hotdata.
  * Each table is seeded with one mode=replace load, because the first load into
    a new table must be `replace` before appends are accepted.
  * A bm25 index on agent_runs.note gives us full-text search over telemetry.

Writes TELEMETRY_DB_ID / TELEMETRY_CONNECTION_ID back into .env.
"""
import asyncio, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import config
from hotdata import HotdataClient, HotdataError
import telemetry as T


def put_env(key: str, value: str) -> None:
    p = ROOT / ".env"
    txt = p.read_text()
    if re.search(rf"^{key}=.*$", txt, re.M):
        txt = re.sub(rf"^{key}=.*$", f"{key}={value}", txt, flags=re.M)
    else:
        txt += f"\n{key}={value}\n"
    p.write_text(txt)


SEED = {
    "runs": {"run_id": "seed", "parent_run_id": "", "scenario": "seed", "execution_mode": "seed",
             "config_version": "seed", "started_at": "1970-01-01T00:00:00Z",
             "ended_at": "1970-01-01T00:00:00Z", "duration_ms": 0, "merge_duration_ms": 0,
             "model_calls": 0, "input_tokens": 0, "output_tokens": 0, "est_cost_usd": 0.0,
             "agents_ok": 0, "agents_failed": 0, "injected_event": "", "status": "seed",
             "notes": "schema seed row"},
    "agent_runs": {"run_id": "seed", "agent": "seed", "execution_mode": "seed",
                   "config_version": "seed", "started_at": "1970-01-01T00:00:00Z",
                   "ended_at": "1970-01-01T00:00:00Z", "duration_ms": 0, "model": "seed",
                   "model_calls": 0, "waves": 0, "input_tokens": 0, "output_tokens": 0,
                   "est_cost_usd": 0.0, "hotdata_db_id": "", "query_count": 0,
                   "query_ms_total": 0, "retries": 0, "status": "seed",
                   "note": "schema seed row"},
    "agent_queries": {"run_id": "seed", "agent": "seed", "seq": 0, "database_id": "",
                      "sql_text": "SELECT 1", "sql_hash": "", "execution_time_ms": 0,
                      "server_processing_ms": 0, "bytes_scanned": 0, "rows_scanned": 0,
                      "rows_returned": 0, "ok": 1},
}

COLTYPES = T.COLTYPES


async def main() -> int:
    hd = HotdataClient()
    try:
        print(f"warming workspace... {round(await hd.warm(), 1)} ms")
        db = await hd.create_db(config.TELEMETRY_DB_NAME,
                                expires_at=None,          # PERMANENT
                                schemas=T.TELEMETRY_SCHEMAS,
                                if_not_exists=True,
                                default_schema=T.SCHEMA)
        dbid, conn = db["id"], db.get("default_connection_id", "")
        created = db.get("created")
        print(f"database   : {dbid}")
        print(f"created    : {created}   (false/absent => reused, nothing destroyed)")
        print(f"connection : {conn}")
        print(f"expires_at : {db.get('expires_at')!r}  (None/empty => never expires)")
        put_env("TELEMETRY_DB_ID", dbid)
        put_env("TELEMETRY_CONNECTION_ID", conn)

        existing = {}
        for t in T.TABLE_COLS:
            try:
                rows = await hd.query_dicts(dbid, f"SELECT count(*) AS n FROM {T.SCHEMA}.{t}")
                existing[t] = int(rows[0]["n"]) if rows else 0
            except HotdataError:
                existing[t] = -1   # table not materialised yet

        for t, cols in T.TABLE_COLS.items():
            if existing.get(t, -1) > 0:
                print(f"  {t:14} already has {existing[t]} row(s) -- left untouched")
                continue
            r = await hd.load_rows(dbid, t, [SEED[t]], schema=T.SCHEMA, mode="replace",
                                   columns=COLTYPES[t], idempotency_key=f"seed-{t}")
            print(f"  {t:14} seeded (mode=replace) -> {r.get('row_count')} row")

        if conn:
            try:
                r = await hd.build_index(conn, "agent_runs", ["note"],
                                        index_name="agent_runs_note_bm25",
                                        schema=T.SCHEMA, index_type="bm25")
                print(f"  bm25 index on agent_runs.note -> {r.get('status', 'ok')}")
            except HotdataError as e:
                print(f"  bm25 index: {e.code} ({'already exists' if e.status == 409 else e.message[:90]})")

        n = await hd.query_dicts(dbid, f"SELECT count(*) AS runs FROM {T.SCHEMA}.runs")
        print(f"\nOK. {T.SCHEMA}.runs currently holds {n[0]['runs']} row(s).")
        print("TELEMETRY_DB_ID written to .env")
        return 0
    finally:
        await hd.aclose()


sys.exit(asyncio.run(main()))
