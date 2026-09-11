"""Validation for model output.

No RocketRide LLM node exposes a JSON schema, so structure is requested in the
prompt and enforced HERE. Models are permissive on purpose: a specialist that
returns a usable-but-imperfect object should not fail the run. Anything
unparseable degrades that one agent and the commander merges the rest.
"""
from __future__ import annotations
import json, re
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def extract_json(text: Any) -> dict | None:
    """Pull one JSON object out of model output: fenced, bare, or prose-wrapped."""
    if isinstance(text, dict):
        return text
    if isinstance(text, list):
        for item in reversed(text):
            got = extract_json(item)
            if got:
                return got
        return None
    if not isinstance(text, str):
        return None
    s = text.strip()
    m = _FENCE.search(s)
    if m:
        s = m.group(1).strip()
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except Exception:
        pass
    start = s.find("{")
    while start != -1:                       # scan for the first balanced object
        depth, instr, esc = 0, False, False
        for i in range(start, len(s)):
            ch = s[i]
            if instr:
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == '"': instr = False
                continue
            if ch == '"': instr = True
            elif ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        v = json.loads(s[start:i + 1])
                        if isinstance(v, dict):
                            return v
                    except Exception:
                        break
        start = s.find("{", start + 1)
    return None


class Loose(BaseModel):
    """Keep whatever the model sent; validate only the fields we rely on."""
    model_config = ConfigDict(extra="allow")


class SpecialistResult(Loose):
    priority_actions: list[Any] = Field(default_factory=list)
    cited_ids: list[Any] = Field(default_factory=list)
    confidence: str = "medium"


class ImmediateAction(Loose):
    rank: int = 0
    action: str = ""
    owner: str = ""
    why: str = ""


class ResourceConflict(Loose):
    resource: str = ""
    contenders: str = ""
    resolution: str = ""
    rationale: str = ""


class IncidentCommandPlan(Loose):
    incident_status: str = "unknown"
    executive_summary: str = ""
    immediate_actions: list[ImmediateAction] = Field(default_factory=list)
    evacuation_actions: list[Any] = Field(default_factory=list)
    medical_actions: list[Any] = Field(default_factory=list)
    infrastructure_actions: list[Any] = Field(default_factory=list)
    logistics_actions: list[Any] = Field(default_factory=list)
    resource_conflicts: list[ResourceConflict] = Field(default_factory=list)
    critical_dependencies: list[Any] = Field(default_factory=list)
    unresolved_risks: list[Any] = Field(default_factory=list)
    agent_consensus: str = "unknown"
    degraded_agents: list[str] = Field(default_factory=list)
    generated_at: str = ""


def validate_specialist(raw: Any) -> tuple[SpecialistResult | None, str]:
    obj = extract_json(raw)
    if obj is None:
        return None, "no JSON object found in response"
    try:
        return SpecialistResult.model_validate(obj), ""
    except Exception as e:
        return None, str(e)[:200]


def validate_plan(raw: Any) -> tuple[IncidentCommandPlan | None, str]:
    obj = extract_json(raw)
    if obj is None:
        return None, "no JSON object found in response"
    try:
        return IncidentCommandPlan.model_validate(obj), ""
    except Exception as e:
        return None, str(e)[:200]
