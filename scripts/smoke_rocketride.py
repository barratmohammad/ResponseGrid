"""Step-0 spine proof for RocketRide: connect -> validate -> use -> send -> status -> terminate.
Uses a webhook->response pipe so it needs NO model key: this isolates engine reachability."""
import asyncio, os, json, sys, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from rocketride import RocketRideClient

PIPE = {"components": [
    {"id": "in", "provider": "webhook",
     "config": {"type": "webhook", "mode": "Source", "hideForm": True, "parameters": {}}},
    {"id": "out", "provider": "response_text", "config": {"laneName": "text"},
     "input": [{"lane": "text", "from": "in"}]},
], "version": 1}

async def run():
    events = []
    def on_event(e):
        events.append(e.get("event") if isinstance(e, dict) else str(e))
    c = RocketRideClient(uri=os.environ["ROCKETRIDE_URI"], auth=os.environ["ROCKETRIDE_AUTH"],
                         on_event=on_event, on_connect_error=lambda m: print("  CONNECT ERROR:", m))
    print(f">>> connecting to {os.environ['ROCKETRIDE_URI']}", flush=True)
    await c.connect()
    print("    connected:", c.is_connected(), c.get_connection_info(), flush=True)
    try:
        print(">>> validate(pipeline)", flush=True)
        try:
            v = await c.validate(pipeline=PIPE, source="in")
            print("    ->", json.dumps(v, default=str)[:500], flush=True)
        except Exception as ex:
            print("    validate raised:", repr(ex)[:300], flush=True)

        print(">>> use(pipeline=..., threads=4, trace=summary)", flush=True)
        r = await c.use(pipeline=PIPE, source="in", threads=4, pipelineTraceLevel="summary")
        print("    ->", json.dumps(r, default=str)[:500], flush=True)
        token = r.get("token")
        if not token:
            print("!! no token returned"); return
        await c.set_events(token, ["TASK", "SUMMARY", "FLOW", "OUTPUT", "SSE"])
        print(">>> send()", flush=True)
        out = await c.send(token, "ResponseGrid spine check",
                           objinfo={"name": "in.txt"}, mimetype="text/plain")
        print("    ->", json.dumps(out, default=str)[:700], flush=True)
        st = await c.get_task_status(token)
        d = st if isinstance(st, dict) else getattr(st, "__dict__", {})
        print(">>> task status")
        print("    ", json.dumps({k: d.get(k) for k in
              ("state", "completed", "startTime", "endTime", "exitCode", "exitMessage")}, default=str)[:400])
        print("     tokens:", json.dumps(d.get("tokens"), default=str)[:400])
        print("     errors:", json.dumps(d.get("errors"), default=str)[:300])
        await c.terminate(token)
        print(">>> events:", events[:15])
    finally:
        await c.disconnect()
    print("\n=== ROCKETRIDE SPINE OK ===")

async def main():
    try:
        await asyncio.wait_for(run(), timeout=120)
    except asyncio.TimeoutError:
        print("!! TIMED OUT after 120s"); sys.exit(1)

asyncio.run(main())
