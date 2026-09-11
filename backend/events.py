"""Event bus -> SSE. One queue per subscriber, plus a replay buffer so a UI that
connects late still renders the whole run."""
from __future__ import annotations
import asyncio, json, time
from typing import Any

EVENT_TYPES = [
    "run_started", "scenario_loaded", "db_created", "agent_started", "agent_query",
    "agent_update", "agent_completed", "db_destroyed", "merge_started",
    "conflict_detected", "plan_updated", "merge_completed", "metric_updated",
    "run_completed", "incident_injected", "error",
]

AGENT_STATES = ["IDLE", "DATABASE_CREATED", "ANALYZING", "QUERYING",
                "RECOMMENDATION_READY", "COMPLETE", "DEGRADED"]


class EventBus:
    def __init__(self, max_replay: int = 2000):
        self._subs: dict[str, list[asyncio.Queue]] = {}
        self._replay: dict[str, list[dict]] = {}
        self._seq: dict[str, int] = {}
        self.max_replay = max_replay

    def emit(self, run_id: str, event_type: str, message: str,
             agent_id: str | None = None, payload: dict[str, Any] | None = None) -> dict:
        self._seq[run_id] = self._seq.get(run_id, 0) + 1
        ev = {"ts": round(time.time(), 3), "run_id": run_id, "seq": self._seq[run_id],
              "event_type": event_type, "agent_id": agent_id,
              "message": message, "payload": payload or {}}
        buf = self._replay.setdefault(run_id, [])
        buf.append(ev)
        if len(buf) > self.max_replay:
            del buf[: len(buf) - self.max_replay]
        for q in list(self._subs.get(run_id, [])):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                pass
        return ev

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        for ev in self._replay.get(run_id, []):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                break
        self._subs.setdefault(run_id, []).append(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        try:
            self._subs.get(run_id, []).remove(q)
        except ValueError:
            pass

    def history(self, run_id: str) -> list[dict]:
        return list(self._replay.get(run_id, []))


BUS = EventBus()


def sse(ev: dict) -> str:
    return f"event: {ev['event_type']}\ndata: {json.dumps(ev, default=str)}\n\n"
