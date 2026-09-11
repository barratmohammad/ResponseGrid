export const specialists = [
  {
    id: "hazard",
    name: "Hazard intelligence",
    short: "Hazard",
    activity: "Modeling fire behavior & spread",
  },
  {
    id: "evacuation",
    name: "Evacuation + traffic",
    short: "Traffic",
    activity: "Evaluating evacuation corridors",
  },
  {
    id: "medical",
    name: "Medical + shelter",
    short: "Medical",
    activity: "Matching care & shelter capacity",
  },
  {
    id: "infrastructure",
    name: "Infrastructure + utilities",
    short: "Utilities",
    activity: "Assessing critical infrastructure",
  },
  {
    id: "logistics",
    name: "Logistics + resources",
    short: "Logistics",
    activity: "Resolving resource allocation",
  },
] as const;
export type AgentId = (typeof specialists)[number]["id"];
export type Mode = "parallel" | "sequential";
export type Agent = {
  id: AgentId;
  status: string;
  activity: string;
  queries: number;
  started?: number;
  elapsed?: number;
  db?: string;
  released?: boolean;
  releaseFailed?: boolean;
  runId?: string;
  retries: number;
};
export type Plan = {
  priority_actions: string[];
  conflicts: { title: string; description: string; resolution: string }[];
  risks: string[];
};
export type IncidentEvent = {
  ts: string | number;
  run_id: string;
  seq: number;
  event_type: string;
  agent_id?: string;
  message: string;
  payload: Record<string, any>;
};
export type RunRecord = {
  id: string;
  mode: Mode;
  duration: number;
  scenario: string;
  parent?: string;
  mock: boolean;
  config?: string;
  modelCalls?: number;
};
export type State = {
  runId?: string;
  mode: Mode;
  status: string;
  agents: Agent[];
  events: IncidentEvent[];
  seen: Set<string>;
  plan?: Plan;
  previousPlan?: Plan;
  revision: number;
  condition?: { type: string; target: string };
  started?: number;
  ended?: number;
  duration?: number;
  queries: number;
  modelCalls?: number;
  scenario?: string;
  parent?: string;
  config?: string;
  history: RunRecord[];
  error?: string;
};
export const initialState = (): State => ({
  mode: "parallel",
  status: "idle",
  agents: specialists.map((s) => ({
    id: s.id,
    status: "IDLE",
    activity: "Awaiting deployment",
    queries: 0,
    retries: 0,
  })),
  events: [],
  seen: new Set(),
  revision: 0,
  queries: 0,
  history: [],
});
const line = (x: any): string =>
  typeof x === "string"
    ? x
    : String(
        x?.action ?? x?.description ?? x?.recommendation ?? x?.title ?? "",
      );
export function normalizePlan(p: any): Plan | undefined {
  if (
    !p ||
    typeof p !== "object" ||
    ![
      "immediate_actions",
      "priority_actions",
      "actions",
      "unresolved_risks",
      "critical_risks",
      "risks",
    ].some((k) => Array.isArray(p[k]))
  )
    return;
  return {
    priority_actions: (
      p.immediate_actions ??
      p.priority_actions ??
      p.actions ??
      []
    ).map(line),
    conflicts: (p.resource_conflicts ?? p.conflicts ?? []).map((x: any) => ({
      title: x.title ?? x.resource ?? "Resource conflict",
      description: line(x.description ?? x.contenders ?? x),
      resolution: line(x.resolution ?? x.responsegrid_resolution ?? ""),
    })),
    risks: (p.unresolved_risks ?? p.critical_risks ?? p.risks ?? []).map(line),
  };
}
export function reduceEvent(
  state: State,
  e: IncidentEvent,
  mock = false,
): State {
  const key = `${e.run_id}:${e.seq}`;
  if (state.seen.has(key) || (state.runId && e.run_id !== state.runId))
    return state;
  const s = {
    ...state,
    seen: new Set(state.seen).add(key),
    events: [...state.events, e].slice(-80),
    agents: state.agents.map((a) => ({ ...a })),
  };
  const p = e.payload ?? {};
  const id =
    (
      { traffic: "evacuation", utilities: "infrastructure" } as Record<
        string,
        string
      >
    )[e.agent_id ?? ""] ?? e.agent_id;
  const a = s.agents.find((a) => a.id === id);
  const ts = eventTime(e.ts);
  if (e.event_type === "run_started") {
    s.runId = e.run_id;
    s.status = "running";
    s.started = ts;
    s.mode = p.execution_mode ?? p.mode ?? s.mode;
    s.scenario = p.scenario ?? p.scenario_id ?? s.scenario;
    s.parent = p.parent_run_id || undefined;
    s.config = p.config_version;
    s.modelCalls = undefined;
  }
  if (a) {
    if (e.message) a.activity = e.message;
    switch (e.event_type) {
      case "db_created":
        a.runId = e.run_id;
        a.queries = 0;
        a.retries = 0;
        a.releaseFailed = false;
        a.db = p.database_id ?? p.db_id;
        a.released = false;
        a.status = "DB CREATED";
        break;
      case "agent_started":
        a.runId = e.run_id;
        a.status = "ANALYZING";
        a.started = ts;
        a.elapsed = undefined;
        break;
      case "agent_query":
        a.status = "QUERYING";
        a.queries = p.query_count ?? a.queries + 1;
        break;
      case "agent_update":
        a.status = String(p.state ?? p.status ?? "ANALYZING")
          .toUpperCase()
          .replaceAll("_", " ");
        if (p.query_count != null) a.queries = p.query_count;
        break;
      case "agent_completed":
        a.status = String(p.state ?? p.status ?? "COMPLETE").toUpperCase();
        a.elapsed =
          p.duration_ms != null
            ? p.duration_ms / 1000
            : (p.duration_s ?? p.elapsed_s);
        if (p.query_count != null) a.queries = p.query_count;
        break;
      case "db_destroyed":
        a.released = p.deleted !== false;
        a.releaseFailed = p.deleted === false;
        if (p.query_count != null) a.queries = p.query_count;
        break;
      case "error":
        a.status = p.retrying ? "RETRYING" : "FAILED";
        if (p.retrying) a.retries++;
        break;
    }
  }
  switch (e.event_type) {
    case "merge_started":
      s.status = "merging";
      break;
    case "merge_completed":
    case "plan_updated": {
      const plan = normalizePlan(p.plan ?? p);
      if (plan) {
        s.previousPlan = s.plan ?? s.previousPlan;
        s.plan = plan;
        s.revision++;
      }
      break;
    }
    case "incident_injected":
      s.condition = {
        type: p.kind ?? p.event_type ?? p.type ?? "",
        target: p.target ?? p.detail?.target ?? e.message,
      };
      break;
    case "metric_updated":
      s.modelCalls = p.model_calls ?? s.modelCalls;
      break;
    case "run_completed":
      for (const agent of s.agents) {
        const ms = p.per_agent_ms?.[agent.id];
        if (typeof ms === "number" && ms > 0) agent.elapsed = ms / 1000;
      }
      s.status = p.status ?? "complete";
      s.ended = ts;
      s.duration =
        p.duration_ms != null
          ? p.duration_ms / 1000
          : (p.duration_s ??
            p.total_runtime_s ??
            (s.started ? (ts - s.started) / 1000 : undefined));
      if (s.duration != null && s.status === "complete")
        s.history = [
          ...s.history,
          {
            id: e.run_id,
            mode: s.mode,
            duration: s.duration,
            scenario:
              s.scenario ?? p.scenario_id ?? p.scenario ?? "palisades_wildfire",
            parent: s.parent ?? p.parent_run_id,
            mock,
            config: s.config ?? p.config_version,
          },
        ];
      break;
    case "error":
      if (!a) {
        s.error = e.message;
        s.status = "failed";
      }
      break;
  }
  if (e.event_type === "agent_query" && a) a.runId = e.run_id;
  s.queries = s.agents
    .filter((a) => a.runId === s.runId)
    .reduce((n, a) => n + a.queries, 0);
  return s;
}
export const running = (s: string) =>
  [
    "ANALYZING",
    "QUERYING",
    "INITIALIZING",
    "RETRYING",
    "DB CREATED",
    "RECALCULATING",
  ].includes(s);
export function benchmark(history: RunRecord[]) {
  const real = history.filter((r) => !r.mock && !r.parent && r.duration > 0);
  const parallel = real.findLast((r) => r.mode === "parallel");
  const sequential = real.findLast(
    (r) =>
      r.mode === "sequential" &&
      r.scenario === parallel?.scenario &&
      r.config === parallel?.config,
  );
  return parallel && sequential
    ? {
        parallel: parallel.duration,
        sequential: sequential.duration,
        ratio: sequential.duration / parallel.duration,
        reduction:
          ((sequential.duration - parallel.duration) / sequential.duration) *
          100,
      }
    : undefined;
}

export function normalizeHistory(data: any): RunRecord[] {
  const raw = Array.isArray(data) ? data : (data?.runs ?? data?.rows ?? []);
  const rows = raw.map((r: any) =>
    Array.isArray(r) && Array.isArray(data.columns)
      ? Object.fromEntries(
          data.columns.map((c: any, i: number) => [
            typeof c === "string" ? c : c.name,
            r[i],
          ]),
        )
      : r,
  );
  return rows
    .sort(
      (a: any, b: any) =>
        Date.parse(a.started_at ?? "") - Date.parse(b.started_at ?? ""),
    )
    .filter(
      (r: any) =>
        r?.run_id &&
        ["parallel", "sequential"].includes(r.execution_mode ?? r.mode) &&
        Number(r.duration_ms) > 0 &&
        ["complete", "completed", "success", "ok"].includes(r.status),
    )
    .map((r: any) => ({
      id: r.run_id,
      mode: r.execution_mode ?? r.mode,
      duration: Number(r.duration_ms) / 1000,
      scenario: r.scenario ?? r.scenario_id,
      parent: r.parent_run_id || r.injected_event || undefined,
      mock: false,
      config: r.config_version,
      modelCalls: r.model_calls,
    }));
}

export function eventTime(ts: string | number) {
  return typeof ts === "number" ? (ts < 1e12 ? ts * 1000 : ts) : Date.parse(ts);
}
