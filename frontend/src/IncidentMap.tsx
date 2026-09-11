import { useState } from "react";
import {
  Layers,
  Minus,
  Plus,
  Navigation,
  LocateFixed,
  Flame,
  Route,
  Hospital,
  RadioTower,
} from "lucide-react";
import type { State } from "./state";
const streets = Array.from({ length: 22 }, (_, i) => {
  const y = 280 + i * 12;
  return (
    <path
      key={i}
      d={`M ${350 - i * 7} ${y} L ${590 + i * 4} ${y - 85} L 880 ${y + 10}`}
    />
  );
});
const cross = Array.from({ length: 25 }, (_, i) => (
  <path key={i} d={`M ${280 + i * 24} 220 L ${380 + i * 19} 560`} />
));
const contour = Array.from({ length: 16 }, (_, i) => (
  <path
    key={i}
    d={`M ${-90 + i * 7} ${160 + i * 12} C 160 ${-80 + i * 12},180 ${270 + i * 9},320 ${100 + i * 14} S 530 ${120 + i * 8},620 ${10 + i * 11} S 840 ${60 + i * 15},1020 ${-60 + i * 15}`}
  />
));
export function IncidentMap({ state }: { state: State }) {
  const [zoom, setZoom] = useState(1);
  const [layerMenu, setLayerMenu] = useState(false);
  const [layers, setLayers] = useState({
    hazards: true,
    routes: true,
    facilities: true,
  });
  const active = state.status !== "idle";
  const blocked = state.condition?.type === "road_blocked";
  const rerouted =
    blocked && !!state.previousPlan && state.plan !== state.previousPlan;
  const wind =
    state.condition?.type === "wind_shift" ||
    state.condition?.type === "new_hazard_zone";
  return (
    <section className="map-panel" aria-label="Incident map">
      <div className="map-heading">
        <div>
          <span className="eyebrow">LIVE OPERATING PICTURE</span>
          <h2>
            Pacific Palisades <span>/ CA</span>
          </h2>
        </div>
        <span className="map-sim">SIMULATED GEOGRAPHY</span>
      </div>
      <svg
        className="map-svg"
        viewBox="0 0 1000 650"
        role="img"
        aria-label={`Schematic Pacific Palisades wildfire map${blocked ? ", Pacific Coast Highway blocked" : ""}`}
      >
        <defs>
          <pattern
            id="grid"
            width="40"
            height="40"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 40 0 H 0 V 40"
              fill="none"
              stroke="#819299"
              strokeWidth=".5"
              opacity=".12"
            />
          </pattern>
          <pattern
            id="hatch"
            width="7"
            height="7"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(35)"
          >
            <line
              x1="0"
              y1="0"
              x2="0"
              y2="7"
              stroke="#e7ab5f"
              strokeWidth="1"
              opacity=".2"
            />
          </pattern>
          <radialGradient id="fire">
            <stop stopColor="#f4713f" stopOpacity=".5" />
            <stop offset="1" stopColor="#c13f29" stopOpacity=".1" />
          </radialGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="8" />
          </filter>
          <linearGradient id="ocean" x2="1" y2="1">
            <stop stopColor="#0c2029" />
            <stop offset="1" stopColor="#101921" />
          </linearGradient>
        </defs>
        <rect width="1000" height="650" fill="#141e24" />
        <g
          transform={`translate(${500 - 500 * zoom} ${325 - 325 * zoom}) scale(${zoom})`}
        >
          <g
            className="contours"
            fill="none"
            stroke="#748d84"
            strokeWidth="1"
            opacity=".14"
          >
            {contour}
          </g>
          <g stroke="#718287" strokeWidth="1" opacity=".15" fill="none">
            {streets}
            {cross}
          </g>
          <path
            d="M0 330 Q120 355 218 440 Q300 502 420 515 Q550 530 620 598 L690 650 H0Z"
            fill="url(#ocean)"
          />
          <path
            d="M0 330 Q120 355 218 440 Q300 502 420 515 Q550 530 620 598 L690 650"
            fill="none"
            stroke="#47606b"
            strokeWidth="2"
          />
          <path
            d="M0 350 Q120 375 208 452 Q295 518 419 533 Q545 548 606 610 L650 650"
            fill="none"
            stroke="#2b434e"
            strokeWidth="1"
          />
          <rect width="1000" height="650" fill="url(#grid)" />
          <g className="road-base" fill="none" strokeLinecap="round">
            <path d="M40 337 Q160 356 240 429 T420 493 Q510 501 578 554 T700 630" />
            <path d="M230 426 L330 375 L430 395 L512 363 L603 399 L718 347 L940 412" />
            <path d="M432 395 L395 314 L448 226 L480 155" />
            <path d="M600 398 L589 301 L660 218 L674 85" />
            <path d="M720 350 L770 245 L850 166" />
          </g>
          {layers.hazards && (
            <g className={active ? "hazard active" : "hazard"}>
              <path
                d="M210 157 L300 136 L366 172 L438 161 L493 229 L480 319 L412 360 L318 338 L243 289Z"
                fill="url(#hatch)"
                stroke="#b18a50"
                strokeWidth="1"
                strokeDasharray="5 5"
              />
              <path
                className="fire-glow"
                d="M235 173 L284 157 L318 177 L354 168 L382 199 L419 187 L459 235 L435 259 L449 289 L398 302 L367 323 L322 300 L289 309 L275 263 L237 245 L252 215Z"
                fill="#e65d37"
                filter="url(#glow)"
                opacity=".23"
              />
              <path
                className="fire-shape"
                d={
                  wind
                    ? "M235 173 L284 157 L318 177 L354 168 L382 199 L440 177 L496 227 L525 286 L489 336 L419 352 L367 323 L322 300 L289 309 L275 263 L237 245 L252 215Z"
                    : "M235 173 L284 157 L318 177 L354 168 L382 199 L419 187 L459 235 L435 259 L449 289 L398 302 L367 323 L322 300 L289 309 L275 263 L237 245 L252 215Z"
                }
                fill="url(#fire)"
                stroke="#ef7951"
                strokeWidth="2"
              />
              <path
                d="M288 197 L330 209 L353 199 L391 225 L413 252 L369 281 L319 263 L301 237Z"
                fill="#e3643e"
                opacity=".13"
                stroke="#f0794d"
                strokeWidth=".8"
              />
              <circle cx="350" cy="238" r="4" fill="#ff9c73" />
              <text x="350" y="225" textAnchor="middle" className="hot-label">
                ACTIVE FIRE PERIMETER
              </text>
              <text x="349" y="347" textAnchor="middle" className="zone-label">
                ZONE-A / B · EVACUATION
              </text>
            </g>
          )}
          {layers.routes && (
            <g fill="none" strokeLinecap="round">
              <path
                d="M40 337 Q160 356 240 429 T420 493 Q510 501 578 554 T700 630"
                stroke={blocked ? "#f37960" : "#d7aa63"}
                strokeWidth="3"
                className={blocked ? "blocked-route" : ""}
              />
              <path
                id="evacRoute"
                d={
                  rerouted
                    ? "M330 375 L430 395 L512 363 L603 399 L718 347 L770 245"
                    : "M430 395 L512 363 L603 399 L718 347 L940 412"
                }
                stroke="#62bbc6"
                strokeWidth="3"
                className={active ? "flow-route" : ""}
              />
              {active && (
                <circle r="4" fill="#b8f4f4">
                  <animateMotion dur="6s" repeatCount="indefinite">
                    <mpath href="#evacRoute" />
                  </animateMotion>
                </circle>
              )}
              <path
                d="M600 398 L589 301 L660 218"
                stroke="#6e9eac"
                strokeWidth="2"
                strokeDasharray="5 8"
              />
            </g>
          )}
          <g className="map-place">
            <text x="525" y="464">
              PACIFIC PALISADES
            </text>
            <text x="760" y="288">
              BRENTWOOD
            </text>
            <text x="759" y="545">
              SANTA MONICA
            </text>
            <text x="91" y="275">
              TOPANGA
            </text>
            <text x="510" y="142" className="terrain-label">
              SANTA MONICA MOUNTAINS
            </text>
            <text
              x="187"
              y="568"
              className="ocean-label"
              transform="rotate(16 187 568)"
            >
              PACIFIC OCEAN
            </text>
          </g>
          <g className="road-label">
            <text x="307" y="456" transform="rotate(21 307 456)">
              PACIFIC COAST HWY
            </text>
            <text x="660" y="377" transform="rotate(-23 660 377)">
              SUNSET BLVD
            </text>
            <text x="601" y="281" transform="rotate(-53 601 281)">
              MANDEVILLE
            </text>
          </g>
          {layers.facilities && (
            <g className="facilities">
              <g transform="translate(743 430)">
                <rect x="-14" y="-14" width="28" height="28" rx="5" />
                <path d="M-6 0 H6 M0 -6 V6" />
                <text x="23" y="0">
                  ST. JOHN’S
                </text>
                <text x="23" y="15" className="facility-sub">
                  MEDICAL CENTER
                </text>
              </g>
              <g transform="translate(547 335)">
                <rect x="-13" y="-13" width="26" height="26" rx="5" />
                <path d="M-7 2 L0 -5 L7 2 M-5 0 V7 H5 V0" />
                <text x="22" y="-1">
                  WESTSIDE REC CENTER
                </text>
              </g>
              <g transform="translate(839 371)">
                <rect x="-12" y="-12" width="24" height="24" rx="5" />
                <path d="M-6 2 L0 -4 L6 2 M-4 0 V6 H4 V0" />
                <text x="19" y="-2">
                  SANTA MONICA COLLEGE
                </text>
              </g>
              <g transform="translate(454 364)">
                <rect x="-11" y="-11" width="22" height="22" rx="4" />
                <path d="M-5 0 H5 M0 -5 V5" />
                <text x="17" y="3">
                  STAGING 01
                </text>
              </g>
            </g>
          )}
          {blocked && (
            <g className="map-impact" transform="translate(270 450)">
              <circle r="27" fill="#e06a4f" opacity=".12" />
              <circle r="16" fill="#30201e" stroke="#f1846d" />
              <path
                d="M-5 -5 L5 5 M-5 5 L5 -5"
                stroke="#f1846d"
                strokeWidth="2"
              />
              <text
                x="-4"
                y="-38"
                textAnchor="middle"
                fill="#ffab94"
                fontSize="12"
              >
                ROAD CLOSED
              </text>
            </g>
          )}
          {state.condition && !blocked && (
            <g
              className="map-impact"
              transform={`translate(${wind ? "450 270" : state.condition.type === "hospital_power_loss" ? "743 430" : state.condition.type === "infrastructure_failure" ? "600 300" : "547 335"})`}
            >
              <circle
                r="33"
                fill="none"
                stroke="#e8ac68"
                strokeDasharray="4 4"
              />
              <circle r="42" fill="#e8ac68" opacity=".08" />
            </g>
          )}
        </g>
      </svg>
      <div className="map-compass">
        <Navigation size={20} />
        <span>N</span>
      </div>
      <div className="map-tools">
        <button
          aria-label="Zoom in"
          onClick={() => setZoom((z) => Math.min(1.6, z + 0.2))}
        >
          <Plus size={16} />
        </button>
        <button
          aria-label="Zoom out"
          onClick={() => setZoom((z) => Math.max(0.8, z - 0.2))}
        >
          <Minus size={16} />
        </button>
        <button aria-label="Reset map view" onClick={() => setZoom(1)}>
          <LocateFixed size={16} />
        </button>
        <button
          aria-label="Map layers"
          aria-expanded={layerMenu}
          onClick={() => setLayerMenu(!layerMenu)}
        >
          <Layers size={16} />
        </button>
      </div>
      {layerMenu && (
        <div className="layer-menu">
          {(Object.keys(layers) as (keyof typeof layers)[]).map((k) => (
            <label key={k}>
              <input
                type="checkbox"
                checked={layers[k]}
                onChange={() => setLayers((l) => ({ ...l, [k]: !l[k] }))}
              />
              {k}
            </label>
          ))}
        </div>
      )}
      <div className="map-legend">
        <span>
          <i className="key-fire" />
          Hazard
        </span>
        <span>
          <i className="key-route" />
          Evacuation
        </span>
        <span>
          <i className="key-congested" />
          Congested
        </span>
        <span>
          <Hospital size={11} />
          Care / shelter
        </span>
      </div>
      <div className="map-coordinate">
        34.0454° N · 118.5265° W <b>SCHEMATIC / NOT FOR NAVIGATION</b>
      </div>
      <div className="map-scale">
        <span />1 km <small>APPROX.</small>
      </div>
      {state.condition && (
        <div
          className="condition-banner"
          key={`${state.runId}-${state.condition.type}`}
        >
          <RadioTower size={15} />
          <div>
            <span>NEW INCIDENT CONDITION</span>
            <strong>
              {state.condition.target} ·{" "}
              {state.condition.type.replaceAll("_", " ")}
            </strong>
          </div>
        </div>
      )}
    </section>
  );
}
