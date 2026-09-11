import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDown,
  ArrowRight,
  Check,
  ChevronDown,
  Clock3,
  Database,
  Flame,
  GitMerge,
  HeartPulse,
  Layers,
  Play,
  Plus,
  Radio,
  RotateCcw,
  Route,
  Shield,
  Truck,
  X,
  Zap,
  AlertTriangle,
  WifiOff,
  Maximize2,
} from "lucide-react";
import { useIncident } from "./useIncident";
import {
  benchmark,
  eventTime,
  running,
  specialists,
  type State,
} from "./state";
import { IncidentMap } from "./IncidentMap";
import type { Injection } from "./adapter";
const icons = [Flame, Route, HeartPulse, Zap, Truck];
const seconds = (n?: number) => (n == null ? "—" : `${n.toFixed(1)}s`);
const clock = (n: number) =>
  `${Math.floor(n / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(n % 60)
    .toString()
    .padStart(2, "0")}`;
function AgentGrid({ state, now }: { state: State; now: number }) {
  return (
    <aside className="agents-panel">
      <div className="section-heading">
        <span>SPECIALIST NETWORK</span>
        <span className="count">05</span>
      </div>
      <div
        className={`architecture ${state.status === "running" ? "executing" : ""} ${state.status === "merging" ? "merging" : ""}`}
      >
        <div className="source-node">
          <Layers size={12} />{" "}
          {state.mode === "sequential"
            ? "SEQUENTIAL EXECUTION"
            : "PARALLEL ORCHESTRATION"}
        </div>
        <svg viewBox="0 0 240 42">
          <path d="M120 0 V12 M24 37 V12 H216 V37 M72 37 V12 M120 37 V12 M168 37 V12" />
          {[24, 72, 120, 168, 216].map((x) => (
            <circle key={x} cx={x} cy="37" r="3" />
          ))}
        </svg>
      </div>
      <div className="agent-list">
        {state.agents.map((a, i) => {
          const Icon = icons[i];
          const on = running(a.status);
          const done = a.status === "COMPLETE";
          return (
            <article
              key={a.id}
              className={`agent-card ${on ? "working" : ""} ${done ? "done" : ""} ${["FAILED", "DEGRADED"].includes(a.status) ? "failed" : ""}`}
            >
              <div className="agent-title">
                <span className="agent-icon">
                  <Icon size={16} />
                </span>
                <h3>{specialists[i].name}</h3>
                <span className="agent-index">0{i + 1}</span>
              </div>
              <div className="agent-readout">
                <span
                  className={`agent-status ${on ? "cyan" : ""} ${done ? "green" : ""}`}
                >
                  <i />
                  {a.status === "COMPLETE" ? "READY" : a.status}
                </span>
                <span className="agent-time">
                  {seconds(
                    a.elapsed ??
                      (a.started && on ? (now - a.started) / 1000 : undefined),
                  )}
                </span>
              </div>
              <p>{a.activity}</p>
              <div className="agent-bottom">
                <span title={a.db}>
                  <Database size={10} />
                  {a.db
                    ? a.releaseFailed
                      ? "DB RELEASE FAILED"
                      : a.released
                        ? "TASK DB RELEASED"
                        : "HOTDATA · ISOLATED"
                    : "TASK DB · STANDBY"}
                </span>
                <span>{a.queries.toString().padStart(2, "0")} queries</span>
              </div>
              <div className="agent-progress">
                <span style={{ width: done ? "100%" : on ? "55%" : "0%" }} />
              </div>
            </article>
          );
        })}
      </div>
      <div className={`convergence ${state.plan ? "resolved" : ""}`}>
        <GitMerge size={15} />
        <span>
          {state.status === "merging"
            ? "MERGING RECOMMENDATIONS"
            : state.plan
              ? "ONE COORDINATED RESPONSE"
              : "5 SPECIALISTS. ONE RESPONSE."}
        </span>
        {state.plan && <Check size={13} />}
      </div>
    </aside>
  );
}
function CommandPanel({ state }: { state: State }) {
  return (
    <aside className="command-panel">
      <div className="section-heading">
        <span>INCIDENT COMMAND</span>
        <GitMerge size={15} />
      </div>
      <div className="command-title">
        <span className={`command-symbol ${state.plan ? "resolved" : ""}`}>
          <Shield size={22} />
        </span>
        <div>
          <h2>
            {state.status === "merging"
              ? "Coordinating response"
              : state.plan
                ? "Coordinated plan"
                : "Awaiting intelligence"}
          </h2>
          <p>
            {state.plan
              ? "Specialist findings, unified."
              : "Five perspectives. One plan."}
          </p>
        </div>
      </div>
      {!state.plan ? (
        <div className="command-empty">
          <div className="merge-visual">
            {[0, 1, 2, 3, 4].map((n) => (
              <i
                key={n}
                className={state.agents[n].status === "COMPLETE" ? "ready" : ""}
              />
            ))}
            <div />
            <GitMerge size={28} />
          </div>
          <h3>
            {state.status === "merging"
              ? "Merging specialist recommendations"
              : state.status === "idle"
                ? "Ready when it matters."
                : "Building the operating picture."}
          </h3>
          <p>
            {state.status === "idle"
              ? "Initiate a response to deploy the specialist network."
              : "Recommendations arrive here as the specialists converge."}
          </p>
          <span className="empty-tag">
            {state.agents.filter((a) => a.status === "COMPLETE").length} / 5
            SPECIALISTS READY
          </span>
        </div>
      ) : (
        <div className="plan-content" key={state.revision}>
          <div className="plan-status">
            <i />
            {state.previousPlan === state.plan
              ? "REASSESSING · PREVIOUS PLAN"
              : state.previousPlan
                ? "PLAN UPDATED"
                : "COORDINATED PLAN READY"}
            <span>REV {state.revision.toString().padStart(2, "0")}</span>
          </div>
          <div className="subheading">
            PRIORITY ACTIONS{" "}
            <span>
              {state.plan.priority_actions.length.toString().padStart(2, "0")}
            </span>
          </div>
          <ol className="priority-list">
            {state.plan.priority_actions.map((action, i) => {
              const old = state.previousPlan?.priority_actions[i];
              return (
                <li
                  key={`${i}-${action}`}
                  className={old && old !== action ? "changed" : ""}
                >
                  <span className="priority-number">0{i + 1}</span>
                  <div>
                    {old && old !== action && <del>{old}</del>}
                    <p>{action}</p>
                    {old && old !== action && (
                      <small>UPDATED RECOMMENDATION</small>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
          {state.plan.conflicts.length > 0 && (
            <>
              <div className="subheading">
                RESOURCE CONFLICTS <AlertTriangle size={12} />
              </div>
              {state.plan.conflicts.slice(0, 2).map((c, i) => (
                <div className="conflict-card" key={i}>
                  <h3>{c.title}</h3>
                  <p>{c.description}</p>
                  <div>
                    <GitMerge size={13} />
                    <span>
                      {c.resolution ||
                        "Resolution pending from Incident Command."}
                    </span>
                  </div>
                </div>
              ))}
            </>
          )}
          <div className="subheading">CRITICAL RISKS</div>
          <ul className="risks">
            {state.plan.risks.slice(0, 3).map((r, i) => (
              <li key={i}>
                <span /> {r}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="command-footer">
        <Shield size={12} /> HUMAN COMMAND RETAINS AUTHORITY
      </div>
    </aside>
  );
}
const eventOptions = [
  {
    type: "road_blocked",
    title: "Road blocked",
    description: "Recalculate evacuation & logistics",
    target: "Pacific Coast Highway",
    icon: Route,
  },
  {
    type: "wind_shift",
    title: "Wind shift",
    description: "Reassess spread & evacuation zones",
    target: "Onshore wind reversal · Zone D",
    icon: Activity,
  },
  {
    type: "shelter_full",
    title: "Shelter capacity reached",
    description: "Redistribute displaced residents",
    target: "Westside Rec Center",
    icon: HeartPulse,
  },
  {
    type: "hospital_power_loss",
    title: "Hospital power loss",
    description: "Prioritize care & backup power",
    target: "St. John’s Medical Center",
    icon: Zap,
  },
  {
    type: "infrastructure_failure",
    title: "Utility failure",
    description: "Reallocate infrastructure support",
    target: "Communications relay · Zones B / C",
    icon: Radio,
  },
  {
    type: "new_hazard_zone",
    title: "New hazard zone",
    description: "Expand the coordinated response",
    target: "Rustic Canyon spot fire",
    icon: Flame,
  },
];
function InjectionModal({
  close,
  inject,
  busy,
}: {
  close: () => void;
  inject: (body: Injection) => Promise<void>;
  busy: boolean;
}) {
  const [selected, setSelected] = useState(eventOptions[0]);
  const [target, setTarget] = useState(selected.target);
  const [error, setError] = useState("");
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="injection-modal"
      onCancel={(e) => {
        if (busy) e.preventDefault();
        else close();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) close();
      }}
    >
      <div className="modal-top">
        <span className="eyebrow">LIVE SCENARIO CONTROL</span>
        <button
          aria-label="Close event injection"
          onClick={close}
          disabled={busy}
        >
          <X size={18} />
        </button>
      </div>
      <h2>Change the incident.</h2>
      <p>Introduce a disruption. Watch the response adapt.</p>
      <div className="event-options">
        {eventOptions.map((o) => (
          <button
            key={o.type}
            className={selected.type === o.type ? "selected" : ""}
            onClick={() => {
              setSelected(o);
              setTarget(o.target);
            }}
            disabled={busy}
          >
            <o.icon size={19} />
            <span>
              <strong>{o.title}</strong>
              <small>{o.description}</small>
            </span>
            {selected.type === o.type && <Check size={15} />}
          </button>
        ))}
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await inject({ event_type: selected.type, target: target.trim() });
            close();
          } catch (err) {
            setError((err as Error).message);
          }
        }}
      >
        <label htmlFor="event-target">AFFECTED LOCATION / CONDITION</label>
        <input
          id="event-target"
          value={target}
          readOnly
          maxLength={200}
          required
          disabled={busy}
        />
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        <div className="modal-footer">
          <span>
            <Radio size={12} /> Affected specialists will reassess
          </span>
          <button className="primary" disabled={busy || !target.trim()}>
            {busy ? "Injecting condition…" : "Inject into incident"}
            <ArrowRight size={16} />
          </button>
        </div>
      </form>
    </dialog>
  );
}
function Telemetry({
  state,
  now,
  mock,
}: {
  state: State;
  now: number;
  mock: boolean;
}) {
  const b = benchmark(state.history);
  const [history, setHistory] = useState(false);
  const elapsed =
    state.duration ??
    (state.started ? ((state.ended ?? now) - state.started) / 1000 : undefined);
  const completed = state.agents.filter(
    (a) => a.elapsed != null && a.runId === state.runId,
  );
  const slowest = completed.reduce<(typeof completed)[number] | undefined>(
    (x, a) => (!x || a.elapsed! > x.elapsed! ? a : x),
    undefined,
  );
  return (
    <section className="telemetry-row">
      <div className="benchmark-panel">
        <div className="section-heading">
          <span>EXECUTION BENCHMARK</span>
          <span className="muted">
            {mock ? "REAL MEASUREMENTS ONLY" : "MEASURED WALL TIME"}
          </span>
        </div>
        <div className="benchmark-body">
          <div>
            <span className="eyebrow">SEQUENTIAL</span>
            <strong>{seconds(b?.sequential)}</strong>
            <div className="benchmark-track">
              <i style={{ width: b ? "100%" : "0%" }} />
            </div>
          </div>
          <div className="parallel-metric">
            <span className="eyebrow">RESPONSEGRID</span>
            <strong>{seconds(b?.parallel)}</strong>
            <div className="benchmark-track">
              <i
                style={{
                  width: b
                    ? `${Math.min(100, (b.parallel / b.sequential) * 100)}%`
                    : "0%",
                }}
              />
            </div>
          </div>
          <div className="speedup">
            {b ? (
              <>
                <strong>
                  {b.ratio.toFixed(1)}
                  <small>×</small>
                </strong>
                <span>{b.ratio >= 1 ? "FASTER" : "RELATIVE SPEED"}</span>
                <p>
                  {Math.abs(b.reduction).toFixed(0)}%{" "}
                  {b.reduction >= 0 ? "less" : "more"} response time
                </p>
              </>
            ) : (
              <>
                <span className="waiting-dash">—</span>
                <p>
                  Run both modes
                  <br />
                  to compare performance.
                </p>
              </>
            )}
          </div>
        </div>
      </div>
      <div className="live-system">
        <div className="section-heading">
          <span>LIVE TELEMETRY</span>
          <i className="status-dot" />
        </div>
        <div className="system-metrics">
          <div>
            <strong>
              {state.agents.filter((a) => running(a.status)).length}
              <small>/ 5</small>
            </strong>
            <span>ACTIVE AGENTS</span>
          </div>
          <div>
            <strong>{state.queries}</strong>
            <span>QUERIES</span>
          </div>
          <div>
            <strong>{seconds(elapsed)}</strong>
            <span>RUNTIME</span>
          </div>
          <div>
            <strong>{state.modelCalls ?? "—"}</strong>
            <span>MODEL CALLS</span>
          </div>
        </div>
        <div className="system-bottom">
          <span>
            {mock
              ? "DEVELOPMENT EVENTS"
              : `${state.agents.reduce((n, a) => n + a.retries, 0)} RETRIES`}
          </span>
          <button onClick={() => setHistory(!history)} aria-expanded={history}>
            Run history <ChevronDown size={12} />
          </button>
        </div>
        {history && (
          <div className="history-popover">
            <div className="section-heading">
              SESSION RUN HISTORY
              <button
                aria-label="Close run history"
                onClick={() => setHistory(false)}
              >
                <X size={14} />
              </button>
            </div>
            {state.history.length ? (
              state.history.map((r, i) => (
                <div key={r.id}>
                  <span>
                    {String(i + 1).padStart(2, "0")} · {r.mode}{" "}
                    {r.mock ? "[DEV]" : ""}
                  </span>
                  <b>{seconds(r.duration)}</b>
                </div>
              ))
            ) : (
              <p>No completed runs in this session.</p>
            )}
          </div>
        )}
      </div>
      <div className="performance-panel">
        <div className="section-heading">
          <span>AGENT PERFORMANCE</span>
          <Activity size={14} />
        </div>
        <div className="performance-bars">
          {state.agents.map((a, i) => (
            <div key={a.id}>
              <span>{specialists[i].short}</span>
              <div>
                <i
                  className={slowest?.id === a.id ? "critical" : ""}
                  style={{
                    width: `${a.elapsed && slowest?.elapsed ? (a.elapsed / slowest.elapsed) * 100 : 0}%`,
                  }}
                />
              </div>
              <b>{seconds(a.elapsed)}</b>
            </div>
          ))}
        </div>
        <div className="critical-path">
          {slowest ? (
            <>
              <span className="amber-dot" />
              {specialists.find((s) => s.id === slowest.id)?.short} is the
              slowest completed specialist
              {state.duration
                ? ` · ${Math.round((slowest.elapsed! / state.duration) * 100)}% of run`
                : ""}
            </>
          ) : (
            <>
              <Clock3 size={11} /> Critical path identified after execution
            </>
          )}
        </div>
      </div>
    </section>
  );
}
export default function App() {
  const { state, link, busy, start, inject, reset, retry, isMock } =
    useIncident();
  const [modal, setModal] = useState(false);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(t);
  }, []);
  const active = ["running", "initializing", "merging"].includes(state.status);
  const canStart = !active && !busy && link === "connected";
  const elapsed = state.started
    ? ((state.ended ?? now) - state.started) / 1000
    : 0;
  return (
    <div className="app">
      <header className="topbar">
        <a
          className="brand"
          href="/command"
          aria-label="ResponseGrid command center"
        >
          <span className="brand-mark">
            <i />
            <i />
            <i />
            <i />
          </span>
          RESPONSE<span>GRID</span>
        </a>
        <div className="header-divider" />
        <span className="header-context">INCIDENT COMMAND</span>
        <div className="header-right">
          <span className="simulation">SIMULATION</span>
          <span className={`incident-status ${active ? "active" : ""}`}>
            <i />
            {active
              ? "INCIDENT ACTIVE"
              : state.plan
                ? "RESPONSE READY"
                : "SYSTEM STANDBY"}
          </span>
          <span className="severity">SEV–1</span>
          <span className="header-timer">
            {clock(elapsed)}
            <small> ELAPSED</small>
          </span>
        </div>
      </header>
      <section className="incident-bar">
        <div>
          <span className="eyebrow">
            INCIDENT 001 <span>/</span> WILDFIRE RESPONSE
          </span>
          <h1>
            Pacific Palisades wildfire
            <span className="incident-tag">LOS ANGELES COUNTY, CA</span>
          </h1>
        </div>
        <div className="run-controls">
          <button
            onClick={reset}
            title="Reset the frontend demo. Server-side runs continue to completion."
            disabled={busy}
          >
            <RotateCcw size={13} />
            <span>Reset demo</span>
          </button>
          <button onClick={() => start("sequential")} disabled={!canStart}>
            <Layers size={13} />
            <span>Run sequential</span>
          </button>
          <button
            className="run-parallel"
            onClick={() => start("parallel")}
            disabled={!canStart}
          >
            <Play size={12} />
            <span>Run ResponseGrid</span>
          </button>
          <button
            className="inject-button"
            onClick={() => setModal(true)}
            disabled={!state.plan || active || busy}
          >
            <Plus size={15} />
            Inject event
          </button>
        </div>
      </section>
      {(link === "disconnected" || link === "reconnecting" || state.error) && (
        <div className="connection-banner" role="status">
          <WifiOff size={14} />
          <strong>COMMAND LINK DEGRADED</strong>
          <span>
            {state.error ??
              (link === "reconnecting"
                ? "Reconnecting to the event stream…"
                : "Backend unavailable. Start the API to connect.")}
          </span>
          <button onClick={retry}>Retry connection</button>
        </div>
      )}
      {isMock && (
        <div className="dev-banner">
          <span />
          DEVELOPMENT PREVIEW · SYNTHETIC EVENTS & TELEMETRY · NOT A LIVE
          BACKEND RUN
        </div>
      )}
      <main className="workspace">
        <AgentGrid state={state} now={now} />
        <div className="map-column">
          <IncidentMap state={state} />
          {state.status === "idle" && (
            <div className="opening-card">
              <span className="opening-kicker">
                <Radio size={13} /> EMERGENCY SIMULATION READY
              </span>
              <h2>
                One incident.
                <br />
                Every perspective.
              </h2>
              <p>
                Deploy five AI specialists.
                <br />
                Converge on one coordinated response.
              </p>
              <button
                className="primary"
                onClick={() => start("parallel")}
                disabled={busy || link !== "connected"}
              >
                {busy ? "Connecting to command…" : "Initiate response"}
                <ArrowRight size={17} />
              </button>
              <button
                className="baseline-link"
                disabled={busy || link !== "connected"}
                onClick={() => start("sequential")}
              >
                Run sequential baseline <ArrowRight size={12} />
              </button>
            </div>
          )}
          <div className="map-bottom">
            <span>
              <i className="status-dot" />{" "}
              {state.status === "idle"
                ? "SCENARIO LOADED"
                : "INCIDENT OPERATING PICTURE"}
            </span>
            <span>
              {state.mode === "parallel"
                ? "PARALLEL INTELLIGENCE"
                : "SEQUENTIAL BASELINE"}
            </span>
          </div>
        </div>
        <CommandPanel state={state} />
      </main>
      <section className="timeline">
        <div className="timeline-label">
          <Radio size={14} />
          <span>
            INCIDENT
            <br />
            TIMELINE
          </span>
        </div>
        <div className="timeline-events" aria-live="polite">
          {state.events.length ? (
            state.events
              .filter(
                (e) =>
                  !["agent_query", "metric_updated", "agent_update"].includes(
                    e.event_type,
                  ),
              )
              .slice(-4)
              .map((e) => (
                <div className="timeline-event" key={`${e.run_id}-${e.seq}`}>
                  <span>
                    {new Date(eventTime(e.ts)).toLocaleTimeString("en-US", {
                      hour12: false,
                    })}
                    <i />
                  </span>
                  <p>{e.message || e.event_type.replaceAll("_", " ")}</p>
                </div>
              ))
          ) : (
            <div className="timeline-standby">
              <span>—</span> Awaiting incident initialization. All systems
              standing by.
            </div>
          )}
        </div>
      </section>
      <Telemetry state={state} now={now} mock={isMock} />
      <footer className="footer">
        <span>
          <span className={`status-dot ${link !== "connected" ? "off" : ""}`} />
          {isMock
            ? "DEVELOPMENT ADAPTER"
            : link === "connected"
              ? "COMMAND LINK CONNECTED"
              : "CONNECTING TO RESPONSEGRID"}
          <i />
          ROCKETRIDE × HOTDATA
        </span>
        <span>
          Parallel intelligence for emergency response.
          <span className="footer-version">RG / 01</span>
        </span>
      </footer>
      {modal && (
        <InjectionModal
          close={() => setModal(false)}
          inject={inject}
          busy={busy}
        />
      )}
    </div>
  );
}
