"""The five specialists + the incident commander.

Instructions are deliberately short and reusable: RocketRide LLM nodes have no
system_prompt field, so the agent's `instructions` array IS the system prompt,
and every token here is paid on every wave. Structure is requested in prose and
then enforced server-side with pydantic (no LLM node exposes a JSON schema).
"""
from __future__ import annotations
from dataclasses import dataclass, field

SHARED_RULES = (
    "You are one specialist inside an emergency incident-command system. "
    "Your data lives in your OWN database; query it with SQL before answering. "
    "Tables are addressed as default.main.<table>. The SQL surface is READ-ONLY. "
    "All data is SIMULATED for an exercise. "
    "Answer with ONE JSON object and nothing else: no prose, no code fences. "
    "Be terse: short strings, no restating the question, at most 5 items per list. "
    "Cite the row ids you relied on."
)


@dataclass(frozen=True)
class Agent:
    id: str
    label: str
    domain: str
    tables: tuple[str, ...]
    instructions: tuple[str, ...]
    schema_hint: str

    def agent_instructions(self) -> list[str]:
        return [SHARED_RULES, *self.instructions, f"Return exactly this JSON shape: {self.schema_hint}"]


AGENTS: dict[str, Agent] = {}


def _add(a: Agent) -> Agent:
    AGENTS[a.id] = a
    return a


_add(Agent(
    id="hazard", label="FIRE / HAZARD", domain="hazard intelligence",
    tables=("hazards", "weather", "zones"),
    instructions=(
        "Own active hazard zones, fire spread and direction, wind and weather, "
        "threatened areas, and immediate hazard priorities.",
        "Query hazards for spread_rate_mph/bearing_deg/containment, weather for wind, "
        "and zones for who is threatened. Rank by structures_at_risk and spread rate.",
    ),
    schema_hint=('{"active_zones":[{"hazard_id":"","name":"","severity":"extreme|high|moderate|low",'
                 '"spread":"","threatens":""}],"wind":{"from_deg":0,"gust_mph":0,"effect":""},'
                 '"priority_actions":[{"action":"","why":"","hazard_id":""}],'
                 '"zones_to_evacuate_first":[""],"cited_ids":[""],"confidence":"high|medium|low"}'),
))

_add(Agent(
    id="evacuation", label="EVACUATION + TRAFFIC", domain="evacuation and traffic",
    tables=("routes", "zones", "weather", "facilities"),
    instructions=(
        "Own evacuation zones, road status, closures, congestion, routing, "
        "bottlenecks and alternate corridors.",
        "Compare current_flow_vph against capacity_vph to find bottlenecks. Note any route "
        "that is the ONLY egress for a zone, and which shelters routes can reach.",
    ),
    schema_hint=('{"bottlenecks":[{"route_id":"","utilization_pct":0,"issue":""}],'
                 '"recommended_routes":[{"zone_id":"","route_id":"","to_facility":"","note":""}],'
                 '"closures":[{"route_id":"","reason":""}],'
                 '"single_points_of_failure":[{"route_id":"","zone_id":"","risk":""}],'
                 '"priority_actions":[{"action":"","why":""}],"cited_ids":[""],"confidence":"high|medium|low"}'),
))

_add(Agent(
    id="medical", label="MEDICAL + SHELTER", domain="medical and sheltering",
    tables=("facilities", "zones", "resources"),
    instructions=(
        "Own hospitals, emergency capacity, ambulances, shelters and shelter capacity, "
        "vulnerable populations, and evacuation destination constraints.",
        "Sum available beds and shelter headroom against zones.vulnerable_residents. "
        "Flag any facility above 85% occupancy and any care facility needing transport.",
    ),
    schema_hint=('{"hospital_status":[{"facility_id":"","available":0,"concern":""}],'
                 '"shelter_plan":[{"facility_id":"","available":0,"assign_zones":"","note":""}],'
                 '"vulnerable_population":[{"zone_id":"","count":0,"need":""}],'
                 '"transport_needs":[{"facility_id":"","units_needed":0,"kind":""}],'
                 '"priority_actions":[{"action":"","why":""}],"cited_ids":[""],"confidence":"high|medium|low"}'),
))

_add(Agent(
    id="infrastructure", label="INFRASTRUCTURE + UTILITIES", domain="infrastructure and utilities",
    tables=("utilities", "facilities", "zones"),
    instructions=(
        "Own power, water, communications, critical infrastructure, utility failures "
        "and restoration priorities.",
        "Follow the depends_on column to find cascading failures. Flag assets on backup "
        "power with a short restore_eta_hours, and any facility whose backup_hours is low.",
    ),
    schema_hint=('{"outages":[{"asset_id":"","status":"","customers_affected":0,"impact":""}],'
                 '"cascade_risks":[{"asset_id":"","depends_on":"","consequence":""}],'
                 '"restoration_priority":[{"asset_id":"","rank":0,"why":""}],'
                 '"power_needs":[{"facility_id":"","kw_needed":0,"hours_remaining":0}],'
                 '"priority_actions":[{"action":"","why":""}],"cited_ids":[""],"confidence":"high|medium|low"}'),
))

_add(Agent(
    id="logistics", label="LOGISTICS + RESOURCES", domain="logistics and resources",
    tables=("resources", "facilities"),
    instructions=(
        "Own crews, vehicles, generators, water, fuel, supplies, resource conflicts "
        "and allocation.",
        "Query default.main.resources first, then default.main.facilities. Count "
        "available units by kind. Identify any single resource that more than one "
        "need requires -- that is a conflict and you must report it explicitly.",
    ),
    schema_hint=('{"available":[{"kind":"","count":0,"ids":""}],'
                 '"allocations":[{"resource_id":"","assign_to":"","why":""}],'
                 '"conflicts":[{"resource_id":"","contenders":"","recommendation":""}],'
                 '"shortfalls":[{"need":"","have":0,"required":0}],'
                 '"priority_actions":[{"action":"","why":""}],"cited_ids":[""],"confidence":"high|medium|low"}'),
))

COMMANDER_ID = "incident_commander"

COMMANDER_INSTRUCTIONS = [
    "You are the Incident Commander of an emergency response system. You receive JSON "
    "findings from five specialists: hazard, evacuation, medical, infrastructure, logistics.",
    "Merge them into ONE coordinated plan. Your job is coordination, not restating them.",
    "Find CONFLICTS where two domains need the same scarce resource or recommend opposing "
    "actions, and resolve each with an explicit call and a reason.",
    "Rank immediate actions by life-safety first, then containment, then property.",
    "If a specialist is missing or unparseable, proceed with the rest and list it in "
    "degraded_agents. Never invent findings for a missing specialist.",
    "All data is SIMULATED for an exercise. Reply with ONE JSON object, no prose, no fences. "
    "Be terse: at most 6 immediate_actions, one short sentence each.",
    'Return exactly: {"incident_status":"critical|severe|elevated|stable",'
    '"executive_summary":"2-3 sentences","immediate_actions":[{"rank":0,"action":"","owner":"","why":""}],'
    '"evacuation_actions":[""],"medical_actions":[""],"infrastructure_actions":[""],'
    '"logistics_actions":[""],"resource_conflicts":[{"resource":"","contenders":"","resolution":"","rationale":""}],'
    '"critical_dependencies":[{"depends_on":"","blocks":""}],"unresolved_risks":[""],'
    '"agent_consensus":"aligned|minor_conflicts|major_conflicts"}',
]

ORDER = ["hazard", "evacuation", "medical", "infrastructure", "logistics"]

# Which domains an injected condition actually invalidates. Deterministic on purpose:
# no LLM call is needed to decide scope, and the partial rerun is provably cheaper.
INJECTION_IMPACT: dict[str, list[str]] = {
    "road_blocked":           ["evacuation", "logistics"],
    "hospital_power_loss":    ["medical", "infrastructure"],
    "shelter_full":           ["medical", "evacuation"],
    "wind_shift":             ["hazard", "evacuation"],
    "infrastructure_failure": ["infrastructure", "logistics"],
    "new_hazard_zone":        ["hazard", "evacuation", "medical"],
}
