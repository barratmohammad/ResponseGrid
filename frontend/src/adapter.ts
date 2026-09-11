import { type IncidentEvent, type Mode, specialists } from "./state";
export const isMock =
  import.meta.env?.DEV && import.meta.env?.VITE_USE_MOCK_DATA === "true";
export type Injection = {
  event_type: string;
  target: string;
  description?: string;
};
export const eventTypes = [
  "run_started",
  "scenario_loaded",
  "db_created",
  "agent_started",
  "agent_query",
  "agent_update",
  "agent_completed",
  "db_destroyed",
  "merge_started",
  "conflict_detected",
  "plan_updated",
  "merge_completed",
  "metric_updated",
  "incident_injected",
  "run_completed",
  "error",
];
async function request(path: string, body?: unknown) {
  const response = await fetch(`/api${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(45000),
  });
  if (!response.ok)
    throw new Error(
      `Command link returned ${response.status}. Check the backend and retry.`,
    );
  return response.json();
}
const mockRuns = new Map<
  string,
  { mode: Mode; injection?: Injection; parent?: string }
>();
export const adapter = {
  async health() {
    return isMock ? { status: "development" } : request("/health");
  },
  async scenarios() {
    return isMock
      ? [{ id: "palisades", name: "Pacific Palisades Wildfire" }]
      : request("/scenarios");
  },
  async start(mode: Mode, scenario_id: string) {
    if (!isMock)
      return request("/runs", { execution_mode: mode, scenario: scenario_id });
    const run_id = crypto.randomUUID();
    mockRuns.set(run_id, { mode });
    return { run_id };
  },
  async inject(id: string, body: Injection) {
    if (!isMock) {
      const result = await request(`/runs/${id}/inject`, {
        type: body.event_type,
        payload: { target: body.target },
      });
      if (result.run_id) return result;
      for (let i = 0; i < 30; i++) {
        const data = await request("/runs");
        const child = (data.runs ?? []).findLast(
          (r: any) =>
            r.parent_run_id === id && r.injected_event === body.event_type,
        );
        if (child) return child;
        await new Promise((resolve) => setTimeout(resolve, 350));
      }
      throw new Error(
        "Event accepted, but its child run is not available yet. Check the backend before injecting again.",
      );
    }
    const run_id = crypto.randomUUID();
    mockRuns.set(run_id, { mode: "parallel", injection: body, parent: id });
    return { run_id };
  },
  async snapshot(id: string) {
    return request(`/runs/${id}`);
  },
  async telemetry() {
    return request("/telemetry/runs");
  },
  subscribe(
    id: string,
    onEvent: (e: IncidentEvent) => void,
    onLink: (s: string) => void,
  ) {
    if (isMock) return mockStream(id, onEvent, onLink);
    const stream = new EventSource(`/api/runs/${id}/events`);
    let disposed = false;
    const receive = (raw: MessageEvent) => {
      if (typeof raw.data !== "string") return;
      try {
        const data = JSON.parse(raw.data);
        if (
          !data ||
          typeof data !== "object" ||
          !data.event_type ||
          !Number.isFinite(data.seq)
        )
          throw Error("Malformed event");
        onEvent({ ...data, payload: data.payload ?? {} });
      } catch {
        onLink("Invalid event received — awaiting valid data");
      }
    };
    stream.onopen = () => onLink("connected");
    stream.onmessage = receive;
    eventTypes.forEach((type) =>
      stream.addEventListener(type, receive as EventListener),
    );
    stream.onerror = (event) => {
      if ("data" in event) return;
      if (!disposed) onLink("reconnecting");
    };
    return () => {
      disposed = true;
      stream.close();
    };
  },
};
const impact: Record<string, string[]> = {
  road_blocked: ["evacuation", "logistics"],
  wind_shift: ["hazard", "evacuation"],
  shelter_full: ["medical", "evacuation"],
  hospital_power_loss: ["medical", "infrastructure"],
  infrastructure_failure: ["infrastructure", "logistics"],
  new_hazard_zone: ["hazard", "evacuation", "medical"],
};
function mockStream(
  id: string,
  emit: (e: IncidentEvent) => void,
  link: (s: string) => void,
) {
  const run = mockRuns.get(id)!;
  let seq = 0;
  const timers: ReturnType<typeof setTimeout>[] = [];
  const begin = Date.now();
  link("connected");
  const at = (
    ms: number,
    type: string,
    payload: Record<string, any> = {},
    agent_id?: string,
    message = "",
  ) => {
    timers.push(
      setTimeout(
        () =>
          emit({
            ts: new Date().toISOString(),
            run_id: id,
            seq: ++seq,
            event_type: type,
            agent_id,
            message,
            payload,
          }),
        ms,
      ),
    );
  };
  at(50, "run_started", { mode: run.mode }, undefined, "Incident initialized");
  if (run.injection)
    at(
      80,
      "incident_injected",
      run.injection,
      undefined,
      `${run.injection.target}: ${run.injection.event_type.replaceAll("_", " ")}`,
    );
  const selected = specialists.filter(
    (s) =>
      !run.injection ||
      (
        impact[run.injection.event_type] ?? specialists.map((s) => s.id)
      ).includes(s.id),
  );
  let finish = 0;
  let cursor = 300;
  selected.forEach((s, i) => {
    const start = run.mode === "sequential" ? cursor : 300;
    const duration = [2300, 3900, 2900, 2100, 3200][i];
    cursor = start + duration + 100;
    finish = Math.max(finish, start + duration);
    at(
      start,
      "db_created",
      { database_id: `dev_${s.id}_${id.slice(0, 4)}` },
      s.id,
      "Isolated development database created",
    );
    at(start + 130, "agent_started", {}, s.id, s.activity);
    for (let j = 1; j <= 3; j++)
      at(
        start + 300 + j * 450,
        "agent_query",
        { query_count: j },
        s.id,
        [
          "Reading incident observations",
          "Cross-checking response constraints",
          "Evaluating specialist recommendations",
        ][j - 1],
      );
    at(
      start + duration,
      "agent_completed",
      { duration_s: (duration - 130) / 1000, query_count: 3 },
      s.id,
      "Recommendation ready",
    );
    at(
      start + duration + 100,
      "db_destroyed",
      {},
      s.id,
      "Task database released",
    );
  });
  at(
    finish + 150,
    "merge_started",
    {},
    undefined,
    "Merging specialist recommendations",
  );
  const change = run.injection;
  const action =
    change?.event_type === "road_blocked"
      ? "Redirect evacuation through Sunset → Mandeville."
      : change?.event_type === "wind_shift"
        ? "Expand evacuation warning northeast of Zone A."
        : change?.event_type === "shelter_full"
          ? "Redirect arrivals to Shelter Alpha."
          : change?.event_type === "hospital_power_loss"
            ? "Prioritize mobile power for hospital critical care."
            : change?.event_type === "infrastructure_failure"
              ? "Isolate the affected utility and dispatch a repair team."
              : change
                ? "Expand the exclusion zone and stage medical support."
                : "Evacuate Zone A via Pacific Coast Highway.";
  at(
    finish + 850,
    "plan_updated",
    {
      plan: {
        priority_actions: [
          action,
          "Stage two response crews at the eastern perimeter.",
          "Move reserve generator GEN-5 to Westside Rec Center.",
        ],
        conflicts: [
          {
            title: "Generator contention",
            description:
              "Hospital and Westside Rec Center request the same mobile unit.",
            resolution:
              "Prioritize hospital critical care. Route reserve GEN-5 to the shelter.",
          },
        ],
        risks: [
          "Wind-driven spread toward residential Zone A.",
          "Limited outbound capacity on coastal corridors.",
        ],
      },
    },
    undefined,
    change ? "Coordinated response updated" : "Coordinated response generated",
  );
  at(finish + 900, "metric_updated", { model_calls: selected.length + 1 });
  timers.push(
    setTimeout(
      () =>
        emit({
          ts: new Date().toISOString(),
          run_id: id,
          seq: ++seq,
          event_type: "run_completed",
          message: "Development preview complete — not a measured backend run",
          payload: {
            duration_s: (Date.now() - begin) / 1000,
            parent_run_id: run.parent,
          },
        }),
      finish + 1000,
    ),
  );
  return () => timers.forEach(clearTimeout);
}
