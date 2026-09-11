import { useCallback, useEffect, useRef, useState } from "react";
import { adapter, isMock, type Injection } from "./adapter";
import {
  initialState,
  reduceEvent,
  normalizeHistory,
  type Mode,
} from "./state";
export function useIncident() {
  const [state, setState] = useState(initialState);
  const [link, setLink] = useState("connecting");
  const [busy, setBusy] = useState(false);
  const [scenario, setScenario] = useState("palisades_wildfire");
  const stop = useRef<() => void>(() => {});
  const generation = useRef(0);
  const refreshHistory = useCallback(async () => {
    if (isMock) return;
    try {
      const rows = normalizeHistory(await adapter.telemetry());
      setState((s) => ({
        ...s,
        history: [
          ...new Map([...s.history, ...rows].map((r) => [r.id, r])).values(),
        ],
        modelCalls:
          rows.find((r) => r.id === s.runId)?.modelCalls ?? s.modelCalls,
      }));
    } catch {
      /* Current-run event telemetry remains available. */
    }
  }, []);
  const connect = useCallback(async () => {
    setLink("connecting");
    try {
      const health = await adapter.health();
      if (health.ok === false)
        throw new Error(health.blocker ?? "Backend dependency unavailable.");
      setLink("connected");
      setState((s) => ({ ...s, error: undefined }));
      const result = await adapter.scenarios();
      const rows = Array.isArray(result) ? result : result.scenarios;
      if (rows?.length) setScenario(rows[0].id ?? rows[0].scenario_id);
      void refreshHistory();
    } catch (e) {
      setLink("disconnected");
      setState((s) => ({ ...s, error: (e as Error).message }));
    }
  }, []);
  useEffect(() => {
    void connect();
    return () => {
      generation.current++;
      stop.current();
    };
  }, [connect]);
  const watch = (id: string) => {
    stop.current();
    stop.current = adapter.subscribe(
      id,
      (e) => {
        setState((s) => reduceEvent(s, e, isMock));
        if (e.event_type === "run_completed") {
          stop.current();
          void refreshHistory();
        }
      },
      setLink,
    );
  };
  const start = async (mode: Mode) => {
    if (busy) return;
    setBusy(true);
    const token = ++generation.current;
    stop.current();
    try {
      const result = await adapter.start(mode, scenario);
      if (token !== generation.current) return;
      const id = result.run_id ?? result.id;
      if (!id) throw Error("Backend did not return a run ID.");
      setState((s) => ({
        ...initialState(),
        history: s.history,
        runId: id,
        mode,
        status: "initializing",
      }));
      watch(id);
    } catch (e) {
      setState((s) => ({ ...s, error: (e as Error).message }));
      setLink("disconnected");
    } finally {
      if (token === generation.current) setBusy(false);
    }
  };
  const inject = async (body: Injection) => {
    if (!state.runId || busy) return;
    setBusy(true);
    const token = ++generation.current;
    try {
      const result = await adapter.inject(state.runId, body);
      if (token !== generation.current) return;
      const id = result.run_id ?? result.id ?? state.runId;
      setState((s) => ({
        ...s,
        runId: id,
        status: "running",
        condition: { type: body.event_type, target: body.target },
        previousPlan: s.plan,
        started: undefined,
        ended: undefined,
        duration: undefined,
        error: undefined,
      }));
      watch(id);
    } catch (e) {
      setState((s) => ({ ...s, error: (e as Error).message }));
      throw e;
    } finally {
      if (token === generation.current) setBusy(false);
    }
  };
  const reset = () => {
    generation.current++;
    stop.current();
    setBusy(false);
    setState(initialState());
  };
  const retry = async () => {
    await connect();
    if (state.runId && !["complete", "failed"].includes(state.status))
      watch(state.runId);
  };
  return { state, link, busy, start, inject, reset, retry, isMock };
}
