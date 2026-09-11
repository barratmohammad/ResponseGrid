"""Palisades-Fire-INSPIRED wildfire scenario.

ALL DATA HERE IS SIMULATED for demonstration. It is loosely inspired by the
geography of Pacific Palisades, CA but the operational figures -- unit
positions, hospital capacities, shelter counts, road closures -- are invented.
Every row carries data_source='simulated' so nothing can be mistaken for a
historical record.

The dataset is deliberately tuned so that independent specialists reach
CONFLICTING conclusions, which is what makes the merge step meaningful:
  * E-14 and E-22 are the only two engines near Palisades Dr; both the hazard
    slice (structure protection) and the evacuation slice (corridor cover) need them.
  * Westside Rec Center is the only shelter not downwind, and it is at 88% capacity.
  * GEN-3 is the single 500kW generator; St. John's needs it for surgery and
    the Sunset/PCH traffic signal cluster needs it to keep the corridor moving.
  * Closing Palisades Dr (hazard's recommendation) removes the evacuation route
    that medical is routing ambulances along.
"""
from __future__ import annotations

SCENARIO_ID = "palisades_wildfire"
SCENARIO_META = {
    "id": SCENARIO_ID,
    "name": "Palisades-Inspired Wildfire",
    "kind": "wildfire",
    "data_source": "simulated",
    "disclaimer": "Simulated operational data inspired by Pacific Palisades geography. Not historical fact.",
    "declared_at": "2026-09-11T10:42:00-07:00",
    "summary": ("Wind-driven brush fire on the north flank of Pacific Palisades. "
                "Santa Ana gusts 45-60 mph from the NE. ~2,400 structures in the "
                "threat envelope, ~11,000 residents under evacuation order or warning."),
}

# ---------------------------------------------------------------- hazards
HAZARDS = [
    {"hazard_id": "FZ-1", "name": "Temescal Ridge head", "kind": "active_fire", "acres": 320,
     "containment_pct": 0, "spread_rate_mph": 2.4, "bearing_deg": 215, "intensity": "extreme",
     "threatened_zones": "ZONE-A;ZONE-B", "structures_at_risk": 640, "notes": "Head fire running downslope toward Palisades Dr; spotting up to 0.5 mi ahead."},
    {"hazard_id": "FZ-2", "name": "Santa Ynez flank", "kind": "active_fire", "acres": 180,
     "containment_pct": 15, "spread_rate_mph": 1.1, "bearing_deg": 190, "intensity": "high",
     "threatened_zones": "ZONE-B", "structures_at_risk": 310, "notes": "Flanking run; dozer line holding on the east side."},
    {"hazard_id": "FZ-3", "name": "Rustic Canyon spot", "kind": "spot_fire", "acres": 12,
     "containment_pct": 0, "spread_rate_mph": 0.8, "bearing_deg": 205, "intensity": "moderate",
     "threatened_zones": "ZONE-C", "structures_at_risk": 95, "notes": "New spot from ember cast; unstaffed as of last report."},
    {"hazard_id": "HZ-4", "name": "Marquez Knolls ember zone", "kind": "ember_cast", "acres": 0,
     "containment_pct": 0, "spread_rate_mph": 0.0, "bearing_deg": 215, "intensity": "high",
     "threatened_zones": "ZONE-C;ZONE-D", "structures_at_risk": 420, "notes": "Dense wood-shake roofing; ember ignition risk elevated."},
]

WEATHER = [
    {"obs_id": "WX-1", "station": "Palisades RAWS", "obs_time": "2026-09-11T11:00:00-07:00",
     "wind_mph": 46, "gust_mph": 61, "wind_from_deg": 42, "temp_f": 96, "humidity_pct": 8,
     "trend": "gusts building through 16:00", "notes": "Santa Ana event; critical fire weather."},
    {"obs_id": "WX-2", "station": "Topanga RAWS", "obs_time": "2026-09-11T11:00:00-07:00",
     "wind_mph": 38, "gust_mph": 52, "wind_from_deg": 38, "temp_f": 94, "humidity_pct": 11,
     "trend": "steady", "notes": "Ridge-top exposure."},
]

ZONES = [
    {"zone_id": "ZONE-A", "name": "Temescal / Palisades Highlands", "population": 3100,
     "households": 1180, "status": "mandatory_evacuation", "pct_evacuated": 62,
     "vulnerable_residents": 140, "downwind": 1, "notes": "Single-access canyon community."},
    {"zone_id": "ZONE-B", "name": "Santa Ynez / Via de la Paz", "population": 2600,
     "households": 1010, "status": "mandatory_evacuation", "pct_evacuated": 45,
     "vulnerable_residents": 210, "downwind": 1, "notes": "Two assisted-living facilities."},
    {"zone_id": "ZONE-C", "name": "Marquez Knolls", "population": 2900,
     "households": 1090, "status": "evacuation_warning", "pct_evacuated": 12,
     "vulnerable_residents": 95, "downwind": 1, "notes": "Wood-shake roofs; ember exposure."},
    {"zone_id": "ZONE-D", "name": "Alphabet Streets", "population": 2400,
     "households": 980, "status": "evacuation_warning", "pct_evacuated": 5,
     "vulnerable_residents": 160, "downwind": 0, "notes": "Elementary school in session."},
]

# ---------------------------------------------------------------- routes
ROUTES = [
    {"route_id": "RT-PCH-S", "name": "Pacific Coast Hwy southbound", "kind": "highway",
     "lanes": 3, "capacity_vph": 4800, "current_flow_vph": 4350, "status": "open",
     "congestion": "heavy", "serves_zones": "ZONE-A;ZONE-B;ZONE-C;ZONE-D",
     "notes": "Primary egress. At 91% of capacity."},
    {"route_id": "RT-PALDR", "name": "Palisades Dr", "kind": "arterial",
     "lanes": 2, "capacity_vph": 1800, "current_flow_vph": 1620, "status": "open",
     "congestion": "heavy", "serves_zones": "ZONE-A",
     "notes": "ONLY route out of the Highlands. Fire is 0.4 mi upslope."},
    {"route_id": "RT-SUNSET", "name": "Sunset Blvd eastbound", "kind": "arterial",
     "lanes": 2, "capacity_vph": 2000, "current_flow_vph": 1450, "status": "open",
     "congestion": "moderate", "serves_zones": "ZONE-B;ZONE-D",
     "notes": "Signals at Sunset/PCH depend on grid power."},
    {"route_id": "RT-CHAUT", "name": "Chautauqua Blvd", "kind": "arterial",
     "lanes": 2, "capacity_vph": 1600, "current_flow_vph": 980, "status": "open",
     "congestion": "light", "serves_zones": "ZONE-D", "notes": "Underused alternate to PCH."},
    {"route_id": "RT-TOPANGA", "name": "Topanga Canyon Blvd", "kind": "highway",
     "lanes": 2, "capacity_vph": 1700, "current_flow_vph": 0, "status": "closed",
     "congestion": "none", "serves_zones": "ZONE-A",
     "notes": "CLOSED - fire crossed the roadway at mile 4.2."},
    {"route_id": "RT-MARQ", "name": "Marquez Ave", "kind": "local",
     "lanes": 2, "capacity_vph": 900, "current_flow_vph": 410, "status": "open",
     "congestion": "light", "serves_zones": "ZONE-C", "notes": "Feeds Sunset; narrow, parked cars both sides."},
]

# ---------------------------------------------------------------- facilities
FACILITIES = [
    {"facility_id": "HOSP-1", "name": "St. John's Medical Center", "kind": "hospital",
     "capacity": 260, "current_occupancy": 231, "available": 29, "er_status": "diversion_risk",
     "power_source": "grid", "backup_hours": 8, "zone": "OUTSIDE",
     "notes": "Nearest trauma center. 4 ORs active; needs 500kW to keep all running."},
    {"facility_id": "HOSP-2", "name": "UCLA Santa Monica", "kind": "hospital",
     "capacity": 340, "current_occupancy": 268, "available": 72, "er_status": "open",
     "power_source": "grid", "backup_hours": 24, "zone": "OUTSIDE",
     "notes": "22 min transport from ZONE-B via PCH."},
    {"facility_id": "SHLT-1", "name": "Westside Rec Center", "kind": "shelter",
     "capacity": 800, "current_occupancy": 704, "available": 96, "er_status": "n/a",
     "power_source": "grid", "backup_hours": 4, "zone": "OUTSIDE",
     "notes": "ONLY shelter not downwind of the fire. 88% full."},
    {"facility_id": "SHLT-2", "name": "Palisades Charter HS", "kind": "shelter",
     "capacity": 600, "current_occupancy": 180, "available": 420, "er_status": "n/a",
     "power_source": "grid", "backup_hours": 2, "zone": "ZONE-D",
     "notes": "Downwind of HZ-4 ember zone. Viable only while winds hold from NE."},
    {"facility_id": "SHLT-3", "name": "Santa Monica College", "kind": "shelter",
     "capacity": 1200, "current_occupancy": 95, "available": 1105, "er_status": "n/a",
     "power_source": "grid", "backup_hours": 12, "zone": "OUTSIDE",
     "notes": "Large and safe but 28 min from ZONE-A via congested PCH."},
    {"facility_id": "CARE-1", "name": "Sunrise Assisted Living", "kind": "care_facility",
     "capacity": 90, "current_occupancy": 84, "available": 6, "er_status": "n/a",
     "power_source": "grid", "backup_hours": 6, "zone": "ZONE-B",
     "notes": "84 non-ambulatory residents. Requires 12 ambulance trips or 3 bus lifts."},
    {"facility_id": "SCHOOL-1", "name": "Marquez Elementary", "kind": "school",
     "capacity": 420, "current_occupancy": 380, "available": 40, "er_status": "n/a",
     "power_source": "grid", "backup_hours": 0, "zone": "ZONE-D",
     "notes": "380 students in session; needs 8 buses to relocate."},
]

# ---------------------------------------------------------------- utilities
UTILITIES = [
    {"asset_id": "PWR-1", "name": "Palisades Substation 12kV", "kind": "power",
     "status": "de_energized", "customers_affected": 4200, "restore_eta_hours": 0,
     "depends_on": "", "zone": "ZONE-A;ZONE-B",
     "notes": "Proactively de-energized for firefighter safety. Will not restore during the event."},
    {"asset_id": "PWR-2", "name": "Sunset/PCH signal cluster", "kind": "power",
     "status": "on_backup", "customers_affected": 0, "restore_eta_hours": 3,
     "depends_on": "GEN-3", "zone": "ZONE-D",
     "notes": "14 signalized intersections. Battery backup exhausted in ~3h; needs GEN-3."},
    {"asset_id": "WTR-1", "name": "Palisades Reservoir / Zone 4 mains", "kind": "water",
     "status": "degraded", "customers_affected": 3100, "restore_eta_hours": 6,
     "depends_on": "PWR-1", "zone": "ZONE-A",
     "notes": "Booster pumps lost with PWR-1. Hydrant pressure falling; 40% of nominal."},
    {"asset_id": "COM-1", "name": "Cell site LA-4471", "kind": "communications",
     "status": "on_backup", "customers_affected": 6800, "restore_eta_hours": 5,
     "depends_on": "", "zone": "ZONE-B;ZONE-C",
     "notes": "Generator fuel for ~5h. Loss degrades wireless emergency alerts in two zones."},
    {"asset_id": "COM-2", "name": "Public safety repeater Topanga", "kind": "communications",
     "status": "operational", "customers_affected": 0, "restore_eta_hours": 0,
     "depends_on": "", "zone": "ZONE-A", "notes": "Primary fireground comms. Single point of failure."},
]

# ---------------------------------------------------------------- resources
RESOURCES = [
    {"resource_id": "E-14", "name": "Engine 14", "kind": "engine", "crew": 4,
     "status": "available", "assigned_to": "", "location": "Palisades Dr / Vereda",
     "capability": "structure_protection", "notes": "One of only 2 engines within 5 min of Palisades Dr."},
    {"resource_id": "E-22", "name": "Engine 22", "kind": "engine", "crew": 4,
     "status": "available", "assigned_to": "", "location": "Palisades Dr / Chastain",
     "capability": "structure_protection", "notes": "Second of the 2 engines near Palisades Dr."},
    {"resource_id": "E-69", "name": "Engine 69", "kind": "engine", "crew": 4,
     "status": "committed", "assigned_to": "FZ-1", "location": "Temescal Ridge",
     "capability": "structure_protection", "notes": "On the head fire."},
    {"resource_id": "CR-8", "name": "Hand Crew 8", "kind": "hand_crew", "crew": 18,
     "status": "committed", "assigned_to": "FZ-2", "location": "Santa Ynez flank",
     "capability": "line_construction", "notes": "Cutting direct line."},
    {"resource_id": "DZ-2", "name": "Dozer 2", "kind": "dozer", "crew": 2,
     "status": "available", "assigned_to": "", "location": "Staging - Will Rogers",
     "capability": "line_construction", "notes": "Can cut line on FZ-3 or widen the FZ-2 line."},
    {"resource_id": "AMB-3", "name": "Ambulance 3", "kind": "ambulance", "crew": 2,
     "status": "available", "assigned_to": "", "location": "Sunset / Swarthmore",
     "capability": "als_transport", "notes": "Routes to St. John's via Palisades Dr today."},
    {"resource_id": "AMB-7", "name": "Ambulance 7", "kind": "ambulance", "crew": 2,
     "status": "available", "assigned_to": "", "location": "PCH / Chautauqua",
     "capability": "als_transport", "notes": "Available for CARE-1 lift."},
    {"resource_id": "BUS-1", "name": "Transit bus group A", "kind": "bus", "crew": 3,
     "status": "available", "assigned_to": "", "location": "Staging - Will Rogers",
     "capability": "mass_transport", "notes": "3 buses. SCHOOL-1 needs 8; CARE-1 needs 3."},
    {"resource_id": "GEN-3", "name": "Generator 500kW", "kind": "generator", "crew": 1,
     "status": "available", "assigned_to": "", "location": "Staging - Will Rogers",
     "capability": "power_500kw", "notes": "ONLY 500kW unit. HOSP-1 and PWR-2 both require it."},
    {"resource_id": "GEN-5", "name": "Generator 60kW", "kind": "generator", "crew": 1,
     "status": "available", "assigned_to": "", "location": "Staging - Will Rogers",
     "capability": "power_60kw", "notes": "Too small for HOSP-1 surgical load."},
    {"resource_id": "WT-1", "name": "Water tender 1", "kind": "water_tender", "crew": 2,
     "status": "available", "assigned_to": "", "location": "Staging - Will Rogers",
     "capability": "water_supply", "notes": "Critical while WTR-1 hydrant pressure is degraded."},
    {"resource_id": "AIR-1", "name": "Helitanker 1", "kind": "aircraft", "crew": 3,
     "status": "grounded", "assigned_to": "", "location": "Van Nuys",
     "capability": "aerial_suppression", "notes": "GROUNDED - gusts exceed 55 mph limit."},
]

TABLES = {
    "hazards": HAZARDS, "weather": WEATHER, "zones": ZONES, "routes": ROUTES,
    "facilities": FACILITIES, "utilities": UTILITIES, "resources": RESOURCES,
}


def _tag(rows: list[dict]) -> list[dict]:
    return [{**r, "data_source": "simulated"} for r in rows]


def slice_for(agent_id: str, overrides: dict | None = None) -> dict[str, list[dict]]:
    """Return ONLY the tables this specialist needs.

    Cost control: each agent's database holds its own slice, so no agent is ever
    sent the whole dataset and no LLM call carries irrelevant rows.
    """
    t = {k: [dict(r) for r in v] for k, v in TABLES.items()}
    if overrides:
        for table, patches in overrides.items():
            for patch in patches:
                key = next(iter(patch))
                for row in t.get(table, []):
                    if row.get(key) == patch[key]:
                        row.update(patch)
    sel = {
        "hazard":        ["hazards", "weather", "zones"],
        "evacuation":    ["routes", "zones", "weather", "facilities"],
        "medical":       ["facilities", "zones", "resources"],
        "infrastructure":["utilities", "facilities", "zones"],
        "logistics":     ["resources", "hazards", "facilities", "utilities"],
    }[agent_id]
    out = {name: _tag(t[name]) for name in sel}
    if agent_id == "evacuation":
        out["facilities"] = [r for r in out["facilities"] if r["kind"] in ("shelter", "care_facility", "school")]
    if agent_id == "logistics":
        out["facilities"] = [r for r in out["facilities"] if r["kind"] in ("hospital", "shelter")]
        out["utilities"] = [r for r in out["utilities"] if r["kind"] in ("power", "water")]
    return out
