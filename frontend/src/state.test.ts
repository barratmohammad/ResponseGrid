import test from "node:test";
import assert from "node:assert/strict";
import {
  initialState,
  reduceEvent,
  benchmark,
  normalizePlan,
  type IncidentEvent,
} from "./state";
const event = (
  seq: number,
  event_type: string,
  payload = {},
  agent_id?: string,
  run_id = "run-1",
): IncidentEvent => ({
  seq,
  event_type,
  payload,
  agent_id,
  run_id,
  ts: new Date(1000 * seq).toISOString(),
  message: event_type,
});
test("replayed SSE events do not double-count queries", () => {
  let s = reduceEvent(initialState(), event(1, "run_started"));
  const e = event(2, "agent_query", {}, "hazard");
  s = reduceEvent(s, e);
  assert.equal(reduceEvent(s, e).queries, 1);
  assert.equal(
    reduceEvent(s, event(3, "agent_query", {}, "hazard", "stale-run")).queries,
    1,
  );
});
test("agent failure preserves other specialists and retry count", () => {
  let s = reduceEvent(initialState(), event(1, "run_started"));
  s = reduceEvent(s, event(2, "error", { retrying: true }, "hazard"));
  assert.equal(s.agents[0].status, "RETRYING");
  assert.equal(s.agents[0].retries, 1);
  assert.equal(s.agents[1].status, "IDLE");
  assert.equal(s.status, "running");
});
test("plan revision retains previous actions for deltas", () => {
  let s = reduceEvent(initialState(), event(1, "run_started"));
  s = reduceEvent(s, event(2, "plan_updated", { priority_actions: ["PCH"] }));
  s = reduceEvent(
    s,
    event(3, "plan_updated", { priority_actions: ["Sunset"] }),
  );
  assert.equal(s.previousPlan?.priority_actions[0], "PCH");
  assert.equal(s.plan?.priority_actions[0], "Sunset");
});
test("benchmark excludes synthetic runs, partial reruns and unmatched scenarios", () => {
  const p = {
    id: "p",
    mode: "parallel" as const,
    duration: 8,
    scenario: "palisades",
    mock: false,
  };
  const q = { ...p, id: "s", mode: "sequential" as const, duration: 32 };
  assert.equal(benchmark([{ ...p, mock: true }, q]), undefined);
  assert.equal(benchmark([p, { ...q, parent: "p" }]), undefined);
  assert.equal(benchmark([p, { ...q, scenario: "other" }]), undefined);
  assert.equal(benchmark([p, q])?.ratio, 4);
  assert.equal(benchmark([p, q])?.reduction, 75);
});
test("structured commander actions become readable text", () => {
  assert.deepEqual(
    normalizePlan({
      priority_actions: [{ action: "Evacuate" }],
      resource_conflicts: [
        { resource: "G-01", description: "Contention", resolution: "Hospital" },
      ],
    })?.priority_actions,
    ["Evacuate"],
  );
});
test("real backend epoch timestamps and merge summary preserve the actual plan", () => {
  let s = reduceEvent(initialState(), {
    ...event(1, "run_started", {
      execution_mode: "sequential",
      scenario: "palisades_wildfire",
      config_version: "v1",
    }),
    ts: 1789140000,
  });
  assert.equal(s.started, 1789140000000);
  assert.equal(s.mode, "sequential");
  s = reduceEvent(
    s,
    event(2, "plan_updated", {
      plan: {
        immediate_actions: [{ action: "Protect hospital" }],
        unresolved_risks: ["Power loss"],
      },
    }),
  );
  s = reduceEvent(
    s,
    event(3, "merge_completed", {
      incident_status: "critical",
      conflicts: 1,
      degraded_agents: [],
    }),
  );
  assert.equal(s.plan?.priority_actions[0], "Protect hospital");
  assert.equal(s.revision, 1);
});
test("database cleanup failure stays visible and records backend query counts", () => {
  let s = reduceEvent(initialState(), event(1, "run_started"));
  s = reduceEvent(
    s,
    event(2, "db_created", { database_id: "db-real" }, "hazard"),
  );
  s = reduceEvent(
    s,
    event(3, "db_destroyed", { deleted: false, query_count: 7 }, "hazard"),
  );
  assert.equal(s.queries, 7);
  assert.equal(s.agents[0].released, false);
  assert.equal(s.agents[0].releaseFailed, true);
});
test("real degraded-agent state is not presented as complete", () => {
  let s = reduceEvent(initialState(), event(1, "run_started"));
  s = reduceEvent(
    s,
    event(2, "agent_completed", { state: "DEGRADED" }, "hazard"),
  );
  assert.equal(s.agents[0].status, "DEGRADED");
  assert.equal(s.agents[0].elapsed, undefined);
});
