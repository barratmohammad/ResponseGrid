// Serverless port of provider-plugin.ts, which is Vite dev-server middleware and
// therefore does not exist in a production build. Same upstreams, same shapes.
// Read-only. The in-memory cache is replaced by s-maxage, since instances are not shared.

type Req = { method?: string; query: Record<string, string | string[] | undefined> };
type Res = {
  status: (code: number) => Res;
  setHeader: (key: string, value: string) => void;
  end: (body: string) => void;
};

const POINT = "34.066,-118.537";
const BBOX = { minLat: 34, maxLat: 34.14, minLon: -118.63, maxLon: -118.43 };

const UPSTREAM: Record<string, string> = {
  weather: `https://api.weather.gov/alerts/active?point=${POINT}`,
  closures: "https://cwwp2.dot.ca.gov/data/d7/lcs/lcsStatusD07.json",
};

function connections() {
  const env = process.env;
  return {
    twilio:
      env.TWILIO_ACCOUNT_SID && env.TWILIO_AUTH_TOKEN
        ? "Credentials present · not verified"
        : "Credentials required",
    smsSender: !!env.TWILIO_MESSAGING_SERVICE_SID,
    dispatch: "Agency integration required",
    utility: "Utility integration required",
    satellite: "USGS archive imagery; live feed not connected",
  };
}

function mapWeather(payload: any, fetchedAt: string) {
  return {
    fetchedAt,
    source: "National Weather Service",
    items: (payload.features ?? []).map((f: any) => ({ id: f.id, ...f.properties })),
  };
}

function mapClosures(payload: any, fetchedAt: string) {
  const items = (payload.data ?? [])
    .map((r: any) => r.lcs)
    .filter((r: any) => {
      const b = r?.location?.begin;
      if (!b) return false;
      const lat = +b.beginLatitude;
      const lon = +b.beginLongitude;
      return lat >= BBOX.minLat && lat <= BBOX.maxLat && lon >= BBOX.minLon && lon <= BBOX.maxLon;
    })
    .map((r: any) => {
      const c = r.closure;
      const t = c.closureTimestamp;
      const ended = c.code1098?.isCode1098 === "true" || c.code1022?.isCode1022 === "true";
      return {
        id: r.index,
        road: r.location.begin.beginRoute,
        location: r.location.begin.beginLocationName,
        direction: r.location.travelFlowDirection,
        type: c.typeOfClosure,
        work: c.typeOfWork,
        lanes: c.lanesClosed,
        status: ended
          ? "Reported ended"
          : c.code1097?.isCode1097 === "true"
            ? "Reported active"
            : "Scheduled / not confirmed active",
        start: t.closureStartDate + " " + t.closureStartTime,
        end: t.closureEndDate + " " + t.closureEndTime,
        updated: r.recordTimestamp.recordDate + " " + r.recordTimestamp.recordTime,
        coordinates: [+r.location.begin.beginLongitude, +r.location.begin.beginLatitude],
      };
    })
    .sort(
      (a: any, b: any) =>
        Number(b.status === "Reported active") - Number(a.status === "Reported active") ||
        Number(a.status === "Reported ended") - Number(b.status === "Reported ended"),
    );
  return { fetchedAt, source: "Caltrans District 7 LCS", items };
}

export default async function handler(req: Req, res: Res) {
  res.setHeader("Content-Type", "application/json");

  if (req.method !== "GET") {
    res.status(405).end(JSON.stringify({ error: "Read-only provider bridge" }));
    return;
  }

  const raw = req.query.feed;
  const feed = Array.isArray(raw) ? raw[0] : raw;

  if (feed === "connections") {
    res.setHeader("Cache-Control", "no-store");
    res.end(JSON.stringify(connections()));
    return;
  }

  const url = feed ? UPSTREAM[feed] : undefined;
  if (!url) {
    res.setHeader("Cache-Control", "no-store");
    res.status(404).end(JSON.stringify({ error: "Unknown provider" }));
    return;
  }

  try {
    const upstream = await fetch(url, {
      headers: {
        "User-Agent": "ResponseGrid incident demo (barrat@barratmohammad.com)",
        Accept: "application/json",
      },
      signal: AbortSignal.timeout(18000),
    });
    if (!upstream.ok) throw new Error(`Provider HTTP ${upstream.status}`);
    const payload = await upstream.json();
    const fetchedAt = new Date().toISOString();
    const data = feed === "weather" ? mapWeather(payload, fetchedAt) : mapClosures(payload, fetchedAt);
    res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate=120");
    res.end(JSON.stringify(data));
  } catch (e) {
    res.setHeader("Cache-Control", "no-store");
    res
      .status(502)
      .end(
        JSON.stringify({
          error: e instanceof Error ? e.message : "Provider unavailable",
          source: url,
        }),
      );
  }
}
