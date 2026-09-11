"""Telemetry: buffer in memory, flush ONCE per run as one batched append per table.

Why batched and single-writer: Hotdata serialises writes to a table and returns
409 RESOURCE_LOCKED to a second concurrent writer (measured upstream: 8
simultaneous appends, 1 landed without retries). Five agents writing their own
rows live would thrash. So agents never write -- the orchestrator does, once.

The database is PERMANENT (created with no expires_at) and accumulates across
every run of the day, which is what the cross-session queries need.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any

import config
from hotdata import HotdataClient

ROOT = Path(__file__).resolve().parents[1]
BUFFER_FILE = ROOT / "telemetry_buffer.jsonl"
SCHEMA = config.TELEMETRY_SCHEMA

# Column order is fixed: every append must carry the table's full column set.
RUNS_COLS = ["run_id", "parent_run_id", "scenario", "execution_mode", "config_version",
             "started_at", "ended_at", "duration_ms", "merge_duration_ms", "model_calls",
             "input_tokens", "output_tokens", "est_cost_usd", "agents_ok", "agents_failed",
             "injected_event", "status", "notes"]

AGENT_RUNS_COLS = ["run_id", "agent", "execution_mode", "config_version", "started_at",
                   "ended_at", "duration_ms", "model", "model_calls", "waves",
                   "input_tokens", "output_tokens", "est_cost_usd", "hotdata_db_id",
                   "query_count", "query_ms_total", "retries", "status", "note"]

AGENT_QUERIES_COLS = ["run_id", "agent", "seq", "database_id", "sql_text", "sql_hash",
                      "execution_time_ms", "server_processing_ms", "bytes_scanned",
                      "rows_scanned", "rows_returned", "ok"]

TABLE_COLS = {"runs": RUNS_COLS, "agent_runs": AGENT_RUNS_COLS, "agent_queries": AGENT_QUERIES_COLS}

TELEMETRY_SCHEMAS = [{
    "name": SCHEMA,
    "tables": [
        # key + sorted_by can ONLY be declared at create time -- there is no ALTER.
        {"name": "runs", "key": ["run_id"], "sorted_by": [{"column": "started_at"}]},
        {"name": "agent_runs", "key": ["run_id", "agent"], "sorted_by": [{"column": "started_at"}]},
        {"name": "agent_queries", "key": ["run_id", "agent", "seq"],
         "sorted_by": [{"column": "run_id"}]},
    ],
}]


def _norm(row: dict, cols: list[str]) -> dict:
    """Full column set, every time: a column omitted from an append is refused."""
    return {c: ("" if row.get(c) is None else row.get(c)) for c in cols}


class TelemetryStore:
    def __init__(self, hd: HotdataClient, database_id: str = ""):
        self.hd = hd
        self.database_id = database_id or config.TELEMETRY_DB_ID
        self._buf: dict[str, list[dict]] = {t: [] for t in TABLE_COLS}

    # ---------------- buffering ----------------
    def add(self, table: str, row: dict) -> None:
        self._buf[table].append(_norm(row, TABLE_COLS[table]))
        try:  # crash safety: survive a process death mid-run
            with BUFFER_FILE.open("a") as f:
                f.write(json.dumps({"table": table, "row": row, "ts": time.time()}, default=str) + "\n")
        except Exception:
            pass

    def add_queries(self, run_id: str, agent: str, entries: list[dict], start_seq: int = 0) -> int:
        for i, e in enumerate(entries):
            self.add("agent_queries", {
                "run_id": run_id, "agent": agent, "seq": start_seq + i,
                "database_id": e.get("database_id", ""), "sql_text": (e.get("sql_text") or "")[:400],
                "sql_hash": e.get("sql_hash", ""),
                "execution_time_ms": e.get("execution_time_ms", 0),
                "server_processing_ms": e.get("server_processing_ms", 0),
                "bytes_scanned": e.get("bytes_scanned", 0),
                "rows_scanned": e.get("rows_scanned", 0),
                "rows_returned": e.get("rows_returned", 0),
                "ok": e.get("ok", 1),
            })
        return start_seq + len(entries)

    def pending(self) -> dict[str, int]:
        return {t: len(v) for t, v in self._buf.items() if v}

    # ---------------- flush ----------------
    async def flush(self) -> dict[str, Any]:
        """One batched append per table, from this single writer."""
        if not self.database_id:
            return {"flushed": False, "reason": "TELEMETRY_DB_ID not set"}
        out: dict[str, Any] = {"flushed": True, "tables": {}}
        for table, rows in self._buf.items():
            if not rows:
                continue
            try:
                r = await self.hd.load_rows(
                    self.database_id, table, rows, schema=SCHEMA, mode="append",
                    columns=None,
                    idempotency_key=f"{table}-{int(time.time()*1000)}-{len(rows)}")
                out["tables"][table] = {"sent": len(rows), "table_total": r.get("row_count")}
                self._buf[table] = []
            except Exception as e:
                out["tables"][table] = {"sent": 0, "error": str(e)[:200]}
                out["flushed"] = False
        return out

    # ---------------- live queries (the demo surface) ----------------
    async def q(self, sql: str) -> list[dict]:
        if not self.database_id:
            return []
        return await self.hd.query_dicts(self.database_id, sql)

    async def summary(self) -> dict:
        mode = await self.q(f"""
            SELECT execution_mode,
                   count(*)                        AS runs,
                   round(avg(duration_ms))         AS avg_ms,
                   min(duration_ms)                AS best_ms,
                   round(avg(est_cost_usd), 5)     AS avg_cost_usd,
                   round(avg(model_calls), 1)      AS avg_model_calls
            FROM {SCHEMA}.runs
            WHERE status = 'complete'
            GROUP BY 1 ORDER BY 1""")
        by = {r["execution_mode"]: r for r in mode}
        par, seq = by.get("parallel"), by.get("sequential")
        speedup = None
        if par and seq and par.get("avg_ms"):
            speedup = round(float(seq["avg_ms"]) / float(par["avg_ms"]), 2)
        totals = await self.q(f"""
            SELECT count(*) AS total_runs, sum(model_calls) AS model_calls,
                   sum(input_tokens) AS input_tokens, sum(output_tokens) AS output_tokens,
                   round(sum(est_cost_usd), 4) AS total_cost_usd
            FROM {SCHEMA}.runs""")
        return {"by_mode": mode, "measured_speedup": speedup,
                "totals": totals[0] if totals else {}}

    async def agents(self) -> list[dict]:
        return await self.q(f"""
            SELECT agent, execution_mode,
                   count(*)                    AS runs,
                   round(avg(duration_ms))     AS avg_ms,
                   max(duration_ms)            AS worst_ms,
                   round(avg(query_count), 1)  AS avg_queries,
                   round(avg(est_cost_usd), 6) AS avg_cost_usd,
                   sum(retries)                AS retries,
                   sum(CASE WHEN status <> 'ok' THEN 1 ELSE 0 END) AS failures
            FROM {SCHEMA}.agent_runs
            GROUP BY 1, 2 ORDER BY avg_ms DESC""")

    async def bottleneck(self) -> list[dict]:
        """Which agent is the critical path, and how often -- across every parallel run."""
        return await self.q(f"""
            WITH ranked AS (
              SELECT run_id, agent, duration_ms,
                     row_number() OVER (PARTITION BY run_id ORDER BY duration_ms DESC) AS rk
              FROM {SCHEMA}.agent_runs WHERE execution_mode = 'parallel'
            )
            SELECT agent,
                   count(*)                AS times_critical_path,
                   round(avg(duration_ms)) AS avg_ms_when_critical
            FROM ranked WHERE rk = 1
            GROUP BY 1 ORDER BY times_critical_path DESC""")

    async def query_profile(self) -> list[dict]:
        return await self.q(f"""
            SELECT agent,
                   count(*)                                              AS queries,
                   round(avg(execution_time_ms))                         AS avg_ms,
                   round(approx_percentile_cont(execution_time_ms, 0.5)) AS p50_ms,
                   round(approx_percentile_cont(execution_time_ms, 0.95))AS p95_ms,
                   sum(bytes_scanned)                                    AS bytes_scanned
            FROM {SCHEMA}.agent_queries
            GROUP BY 1 ORDER BY queries DESC""")

    async def config_compare(self) -> list[dict]:
        """Before/after an optimisation: the telemetry-driven improvement story."""
        return await self.q(f"""
            SELECT config_version, execution_mode, count(*) AS runs,
                   round(avg(duration_ms)) AS avg_ms,
                   round(avg(est_cost_usd), 5) AS avg_cost_usd
            FROM {SCHEMA}.runs WHERE status = 'complete'
            GROUP BY 1, 2 ORDER BY config_version, execution_mode""")

    async def recent_runs(self, limit: int = 25) -> list[dict]:
        return await self.q(f"""
            SELECT run_id, scenario, execution_mode, config_version, duration_ms,
                   model_calls, est_cost_usd, agents_ok, agents_failed,
                   injected_event, status, started_at
            FROM {SCHEMA}.runs ORDER BY started_at DESC LIMIT {int(limit)}""")

    async def search_notes(self, text: str, limit: int = 10) -> list[dict]:
        """Full-text over agent notes via the bm25 index built at bootstrap."""
        safe = text.replace("'", "''")
        return await self.q(
            f"SELECT run_id, agent, status, note, score "
            f"FROM bm25_search('{SCHEMA}.agent_runs', 'note', '{safe}', {int(limit)}) "
            f"ORDER BY score DESC")
