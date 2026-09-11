"""Hotdata client.

Hand-rolled over httpx rather than the official SDK because:
  * the published SDK (0.10.0) lags the live spec (no `if_not_exists`), and
  * it does not retry on 429/Retry-After, which this workload needs.

Hard facts this encodes (verified against the live API):
  * SQL is READ-ONLY. Writes go only through the /loads endpoint.
  * The first load into a new table must be mode=replace.
  * Inline `data` is CSV-only, comma-separated, <= 2 MiB.
  * Concurrent writes to ONE table return 409 RESOURCE_LOCKED -> single batched writer.
  * Idle workspaces cold-start for 10-20s, so the first call gets a long timeout.
"""
from __future__ import annotations
import asyncio, csv, io, time
from typing import Any, Iterable, Sequence
import httpx

from config import HOTDATA_API_KEY, HOTDATA_API_URL, HOTDATA_WORKSPACE_ID

INLINE_LIMIT = 2 * 1024 * 1024


class HotdataError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, trace_id: str | None = None):
        self.status, self.code, self.message, self.trace_id = status, code, message, trace_id
        super().__init__(f"[{status} {code}] {message}" + (f" (trace {trace_id})" if trace_id else ""))


def rows_to_csv(rows: Sequence[dict], columns: Sequence[str] | None = None) -> str:
    """Serialise dicts to comma-separated CSV with a header. Hotdata infers types."""
    rows = list(rows)
    if not rows:
        return ""
    cols = list(columns or rows[0].keys())
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})
    return buf.getvalue()


class HotdataClient:
    def __init__(self, api_url: str = HOTDATA_API_URL, api_key: str = HOTDATA_API_KEY,
                 workspace_id: str = HOTDATA_WORKSPACE_ID):
        self.api_url = api_url.rstrip("/")
        self._base = {"Authorization": f"Bearer {api_key}",
                      "X-Workspace-Id": workspace_id,
                      "Content-Type": "application/json"}
        # 90s: absorbs cold start and a slow first analytical query.
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0))
        self.query_log: list[dict] = []   # drained by the telemetry store

    async def aclose(self):
        await self._client.aclose()

    # ---------------- transport ----------------
    async def _req(self, method: str, path: str, *, db: str | None = None,
                   json: Any = None, params: dict | None = None,
                   retries: int = 4, retry_409: bool = True) -> tuple[int, Any]:
        headers = dict(self._base)
        if db:
            headers["X-Database-Id"] = db
        url = f"{self.api_url}{path}"
        delay = 0.5
        for attempt in range(retries + 1):
            r = await self._client.request(method, url, headers=headers, json=json, params=params)
            if r.status_code in (429, 503) or (r.status_code == 409 and retry_409):
                if attempt >= retries:
                    break
                wait = float(r.headers.get("Retry-After") or delay)
                await asyncio.sleep(min(wait, 8.0))
                delay = min(delay * 2, 8.0)
                continue
            break
        if r.status_code >= 400:
            code, msg = "HTTP_ERROR", r.text[:400]
            try:
                err = r.json().get("error")
                if isinstance(err, dict):
                    code, msg = err.get("code") or code, err.get("message") or msg
                elif isinstance(err, str):
                    code = msg = err
            except Exception:
                pass
            raise HotdataError(r.status_code, code, msg, r.headers.get("X-Trace-Id"))
        if r.status_code == 204 or not r.content:
            return r.status_code, None
        return r.status_code, r.json()

    # ---------------- lifecycle ----------------
    async def warm(self) -> float:
        """Pre-warm the workspace. Idle workers scale to zero and cost 10-20s on first hit."""
        t0 = time.perf_counter()
        await self._req("GET", "/workspaces")
        return (time.perf_counter() - t0) * 1000

    async def create_db(self, name: str, *, expires_at: str | None = None,
                        schemas: list[dict] | None = None, if_not_exists: bool = False,
                        default_schema: str | None = None) -> dict:
        """Create a database. Omit expires_at for a permanent one (the telemetry DB).

        key[]/sorted_by[]/partition_by[] can ONLY be declared here -- there is no ALTER.
        """
        body: dict[str, Any] = {"name": name}
        if expires_at:
            body["expires_at"] = expires_at
        if schemas:
            body["schemas"] = schemas
        if if_not_exists:
            body["if_not_exists"] = True
        if default_schema:
            body["default_schema"] = default_schema
        _, d = await self._req("POST", "/databases", json=body)
        return d

    async def delete_db(self, database_id: str) -> bool:
        try:
            await self._req("DELETE", f"/databases/{database_id}", retry_409=False)
            return True
        except HotdataError as e:
            if e.status in (403, 404):
                return False
            raise

    async def list_dbs(self, search: str | None = None, limit: int = 100) -> list[dict]:
        params = {"limit": limit}
        if search:
            params["search"] = search
        _, d = await self._req("GET", "/databases", params=params)
        return (d or {}).get("databases") or (d or {}).get("items") or []

    # ---------------- writes ----------------
    async def load_csv(self, database_id: str, table: str, csv_text: str, *,
                       schema: str = "main", mode: str = "replace",
                       columns: dict | None = None, idempotency_key: str | None = None,
                       key: list[str] | None = None) -> dict:
        if not csv_text.strip():
            return {"row_count": 0, "skipped": True}
        size = len(csv_text.encode())
        if size > INLINE_LIMIT:
            raise HotdataError(413, "INLINE_DATA_TOO_LARGE",
                               f"{size}B exceeds the 2 MiB inline limit; use an upload session")
        body: dict[str, Any] = {"mode": mode, "data": csv_text, "format": "csv"}
        if columns:
            body["columns"] = columns
        if key:
            body["key"] = key
        if idempotency_key:
            body["idempotency_key"] = idempotency_key
        # An append must never be blind-retried: a retry re-stages and rows land twice.
        _, d = await self._req(
            "POST", f"/databases/{database_id}/schemas/{schema}/tables/{table}/loads",
            json=body, retry_409=bool(idempotency_key))
        return d or {}

    async def load_rows(self, database_id: str, table: str, rows: Sequence[dict], **kw) -> dict:
        return await self.load_csv(database_id, table, rows_to_csv(rows), **kw)

    async def build_index(self, connection_id: str, table: str, columns: list[str], *,
                          index_name: str, schema: str = "main", index_type: str = "bm25",
                          embedding_provider_id: str | None = None) -> dict:
        body: dict[str, Any] = {"index_name": index_name, "columns": columns,
                                "index_type": index_type}
        if embedding_provider_id:
            body["embedding_provider_id"] = embedding_provider_id
        _, d = await self._req(
            "POST", f"/connections/{connection_id}/tables/{schema}/{table}/indexes", json=body)
        return d or {}

    # ---------------- reads ----------------
    async def query(self, database_id: str, sql: str, *, agent: str | None = None,
                    run_id: str | None = None, default_schema: str | None = None) -> dict:
        body: dict[str, Any] = {"sql": sql}
        if default_schema:
            body["default_schema"] = default_schema
        t0 = time.perf_counter()
        _, d = await self._req("POST", "/query", db=database_id, json=body)
        wall = (time.perf_counter() - t0) * 1000
        d = d or {}
        self.query_log.append({
            "run_id": run_id or "", "agent": agent or "", "sql_text": sql[:500],
            "sql_hash": "", "execution_time_ms": d.get("execution_time_ms") or 0,
            "server_processing_ms": 0, "wall_ms": round(wall, 1),
            "bytes_scanned": 0, "rows_scanned": 0,
            "rows_returned": d.get("total_row_count") or 0, "ok": 1,
            "database_id": database_id,
        })
        return d

    async def query_dicts(self, database_id: str, sql: str, **kw) -> list[dict]:
        """rows come back as arrays; zip them with `columns` into dicts."""
        d = await self.query(database_id, sql, **kw)
        cols = d.get("columns") or []
        return [dict(zip(cols, row)) for row in (d.get("rows") or [])]

    async def query_runs(self, database_id: str, limit: int = 200) -> list[dict]:
        """Hotdata's own per-query telemetry. Snapshot this BEFORE destroying a task DB."""
        try:
            _, d = await self._req("GET", "/query-runs", db=database_id, params={"limit": limit})
        except HotdataError:
            return []
        d = d or {}
        return d.get("query_runs") or d.get("items") or d.get("data") or []

    async def usage(self) -> dict:
        try:
            _, d = await self._req("GET", "/usage")
            return d or {}
        except HotdataError:
            return {}

    def drain_query_log(self) -> list[dict]:
        out, self.query_log = self.query_log, []
        return out
