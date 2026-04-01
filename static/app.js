const INITIAL_FILTERS = {
  country: "",
  league: "",
  team: "",
  market: "",
  family: "",
  search: "",
  oddsMin: null,
  oddsMax: null,
  evMin: null,
  evMax: null,
  edgeMin: null,
  edgeMax: null,
  quick: { only_ev: false, only_value: false, only_strong: false, secondary: false, next_matches: false, signal_heavy: false },
};

const deepClone = (value) => {
  if (typeof globalThis.structuredClone === "function") {
    return globalThis.structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
};

const state = {
  matches: [],
  opportunities: [],
  incompleteOpportunities: [],
  matchRadar: [],
  byFamily: {},
  countryTree: [],
  summary: {},
  filters: deepClone(INITIAL_FILTERS),
  ui: {
    validOnly: true,
    hideTraceability: true,
    hideEmptyFixtures: false,
    includeSecondaryWhenValidOnly: true,
  },
};

const KPI_CONFIG = [
  ["totalCountries", "Países"],
  ["totalLeagues", "Ligas"],
  ["totalMatches", "Partidos próximos"],
  ["totalMarkets", "Mercados analizados"],
  ["totalSignals", "Señales"],
  ["totalEVPlus", "Oportunidades EV+"],
  ["totalStrong", "Apuestas fuertes"],
  ["totalValue", "Value bets"],
];

const FAMILY_LABELS = {
  "1X2": "1X2",
  "Goals": "Goals",
  "BTTS": "BTTS",
  "Corners": "Corners",
  "Cards": "Cards",
  "Shots": "Shots",
  "Shots on target": "Shots on target",
  "Fouls": "Fouls",
  "Offsides": "Offsides",
  "Double chance": "Double chance",
  "Exact score": "Exact score",
  "Secondary": "Secondary",
};
const MIN_MODEL_PROBABILITY = 0.2;
const MIN_SIGNAL_DELTA = 0.02;
const MIN_ACTIONABLE_ODDS = 1.05;
const SCHEDULED_FIXTURE_STATUSES = new Set(["NS"]);
const DISPLAY_TIMEZONE = "Europe/Warsaw";

const q = (id) => document.getElementById(id);
const toNumber = (v) => (v === null || v === undefined || v === "" ? null : Number.isFinite(Number(v)) ? Number(v) : null);
const isFuture = (iso) => Number.isFinite(Date.parse(iso || "")) && Date.parse(iso) >= Date.now();
const dateLabel = (iso) => (!iso ? "Hora no informada" : new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short", timeZone: DISPLAY_TIMEZONE }).format(new Date(iso)));
const normalizeStatus = (value) => String(value || "").trim().toUpperCase();
const isRenderableFixtureStatus = (status) => SCHEDULED_FIXTURE_STATUSES.has(normalizeStatus(status));
const normalizeBasePath = (value) => {
  const raw = String(value || "").trim();
  if (!raw || raw === "/") return "";
  const withPrefix = raw.startsWith("/") ? raw : `/${raw}`;
  return withPrefix.replace(/\/+$/, "");
};
const configuredFrontendBasePath = (() => {
  if (typeof window === "undefined") return "";
  const fromConfig = window.__APP_CONFIG__?.frontendBasePath;
  const fromMeta = document.querySelector('meta[name="frontend-base-path"]')?.content;
  return normalizeBasePath(fromConfig || fromMeta || "");
})();
const apiUrl = (path) => {
  const normalizedPath = String(path || "").replace(/^\.?\//, "");
  const basePath = configuredFrontendBasePath ? `${configuredFrontendBasePath}/` : "/";
  return new URL(normalizedPath, `${window.location.origin}${basePath}`).toString();
};
const countdownLabel = (iso, status) => {
  const normalizedStatus = normalizeStatus(status);
  if (SCHEDULED_FIXTURE_STATUSES.has(normalizedStatus)) return "Próximo";
  return "";
};

function toPercent(value, digits = 1) {
  const n = toNumber(value);
  if (n === null) return null;
  const normalized = Math.abs(n) <= 1 ? n * 100 : n;
  return `${normalized.toFixed(digits)}%`;
}

function toSignedPercent(value, digits = 1) {
  const pct = toPercent(value, digits);
  if (pct === null) return null;
  return pct.startsWith("-") ? pct : `+${pct}`;
}

function fmtDecimal(value, digits = 3) {
  const n = toNumber(value);
  return n === null ? null : n.toFixed(digits);
}

function probabilityTier(prob) {
  const p = toNumber(prob);
  if (p === null) return { label: "Sin probabilidad", css: "risk-high" };
  if (p >= 0.74) return { label: "Muy alta probabilidad", css: "risk-very-high" };
  if (p >= 0.66) return { label: "Alta probabilidad", css: "risk-high" };
  if (p >= 0.58) return { label: "Probabilidad media", css: "risk-medium" };
  return { label: "Riesgo alto", css: "risk-highest" };
}

const FAMILY_ALIASES = {
  "1x2": "1X2",
  match_winner: "1X2",
  "match winner": "1X2",
  goals: "Goals",
  goal: "Goals",
  btts: "BTTS",
  corners: "Corners",
  corner: "Corners",
  cards: "Cards",
  card: "Cards",
  yellow: "Cards",
  fouls: "Fouls",
  foul: "Fouls",
  offsides: "Offsides",
  offside: "Offsides",
  shots: "Shots",
  shot: "Shots",
  shots_on_target: "Shots on target",
  shots_on_goal: "Shots on target",
  shot_on_target: "Shots on target",
  "shots on target": "Shots on target",
  "double chance": "Double chance",
  double_chance: "Double chance",
  "exact score": "Exact score",
  exact_score: "Exact score",
  secondary: "Secondary",
};

function canonicalFamily(value) {
  const key = String(value || "").trim().toLowerCase();
  if (!key) return null;
  return FAMILY_ALIASES[key] || null;
}

function classifyMarketLevel(opp) {
  const prob = toNumber(opp.model_prob ?? opp.close_probability);
  const ev = toNumber(opp.ev);
  const odds = toNumber(opp.odds);
  if (prob !== null && prob >= 0.5 && ev !== null && ev > 0) return "top_opportunity";
  if (prob !== null && prob >= 0.4) return "mercado_util";
  if (odds !== null) return "mercado_detectado";
  return "descartado";
}

function inferFamily(raw = {}) {
  const mapped = canonicalFamily(raw.family || raw.family_key || raw.familyName);
  if (mapped) return mapped;
  const token = [
    raw.family,
    raw.code,
    raw.market,
    raw.market_code,
    raw.marketCode,
    raw.market_name,
    raw.marketName,
    raw.label,
    raw.play,
    raw.pick,
    raw.jugada,
  ].map((v) => String(v || "").toUpperCase()).join(" ");

  if (["DOUBLE CHANCE", "DOBLE OPORTUNIDAD", " DC_", " DC "].some((k) => token.includes(k))) return "Double chance";
  if (["SHOTS ON TARGET", "SOT", "TIROS A PUERTA", "PUERTA"].some((k) => token.includes(k))) return "Shots on target";
  if (["CORNER", "CORNERS", "ESQUINA", "SAQUES DE ESQUINA"].some((k) => token.includes(k))) return "Corners";
  if (["CARD", "CARDS", "TARJET", "BOOKING", "YELLOW", "AMARILLA", "AMONEST", "ROJA"].some((k) => token.includes(k))) return "Cards";
  if (["SHOT", "SHOTS", "TIROS", "REMATES"].some((k) => token.includes(k))) return "Shots";
  if (["FOUL", "FOULS", "FALTAS"].some((k) => token.includes(k))) return "Fouls";
  if (["OFFSIDE", "OFFSIDES", "FUERA DE JUEGO"].some((k) => token.includes(k))) return "Offsides";
  if (["BTTS", "AMBOS MARCAN", "BOTH TEAMS TO SCORE"].some((k) => token.includes(k))) return "BTTS";
  if (["1X2", "DRAW", "EMPATE"].some((k) => token.includes(k))) return "1X2";
  if (["EXACT SCORE", "EXACT_SCORE", "MARCADOR EXACTO", "CORRECT SCORE"].some((k) => token.includes(k))) return "Exact score";
  if (["TEAM", "MARCARA", "SCORE YES", "GOLES EQUIPO", "GOALS", "GOLES", "OVER", "UNDER", "TOTAL"].some((k) => token.includes(k))) return "Goals";
  return "Secondary";
}

function isCompleteOpportunity(opp) {
  if (opp.market_complete === true) return true;
  const required = [opp.odds, opp.model_prob, opp.implied_prob, opp.edge, opp.ev];
  return required.every((value) => toNumber(value) !== null);
}

function normalizeOpportunity(raw) {
  const flags = raw.flags || {};
  const family = inferFamily(raw);
  const odds = toNumber(raw.odds ?? raw.cuota);
  const modelProb = toNumber(raw.model_prob ?? raw.prob_modelo ?? raw.probModelo);
  const impliedProb = toNumber(raw.implied_prob ?? raw.prob_implicita ?? raw.probImplicita);
  const deltaProb = toNumber(raw.delta_prob);
  const edge = toNumber(raw.edge);
  const ev = toNumber(raw.ev);
  const closeProbability = toNumber(raw.close_probability ?? raw.closeProb ?? raw.probabilidad_cierre);

  const computedDelta = deltaProb ?? ((modelProb !== null && impliedProb !== null) ? modelProb - impliedProb : null);
  const computedEv = (modelProb !== null && odds !== null) ? ((modelProb * odds) - 1) : ev;
  const edgePrice = toNumber(raw.edge_price ?? ((modelProb !== null && odds !== null && odds > 1) ? (modelProb - (1 / odds)) : null));
  const isValidSignal = Boolean(
    raw.is_valid_signal ?? (computedDelta !== null && Math.abs(computedDelta) >= MIN_SIGNAL_DELTA)
  );
  const mathHide = (
    computedEv === null || computedEv <= 0
    || edgePrice === null || edgePrice <= 0
    || !isValidSignal
    || odds === null || odds <= MIN_ACTIONABLE_ODDS
    || String(raw.calibration_status || "").toLowerCase() !== "ready"
    || String(raw.readiness || "").toLowerCase() !== "ready"
    || raw.anomaly_flag === true
    || String(raw.family_priority || "").toLowerCase() !== "core"
  );

  const normalized = {
    ...raw,
    fixture_id: raw.fixture_id ?? raw.fixtureId ?? null,
    code: raw.code || raw.market_code || raw.marketCode || "N/D",
    family,
    market: raw.market || raw.market_name || raw.marketName || raw.code || "N/D",
    pick: raw.pick || raw.play || raw.jugada || "N/D",
    odds,
    model_prob: modelProb,
    implied_prob: impliedProb,
    delta_prob: computedDelta,
    close_probability: modelProb !== null ? (closeProbability ?? modelProb) : null,
    edge,
    ev: computedEv,
    edge_price: edgePrice,
    rank: toNumber(raw.rank),
    score: toNumber(raw.score),
    stake: toNumber(raw.stake),
    source: raw.source || "N/D",
    reason_inclusion: raw.reason_inclusion || raw.inclusion_reason || "N/D",
    reason_discard: raw.reason_discard || raw.discard_reason || null,
    completeness_reason: raw.completeness_reason || null,
    market_complete: raw.market_complete === true,
    flags: {
      ev_plus: Boolean(flags.ev_plus ?? (ev !== null && ev > 0)),
      value: Boolean(flags.value),
      no_value: Boolean(flags.no_value),
      strong_signal: Boolean(flags.strong_signal),
      secondary_market: Boolean(flags.secondary_market ?? ["Corners", "Cards", "Shots", "Secondary"].includes(family)),
    },
    pick_status: raw.pick_status || (raw.publish_allowed ? "publishable_core" : "traceable_only"),
  };
  normalized.market_complete = isCompleteOpportunity(normalized);
  normalized.market_level = raw.market_level || classifyMarketLevel(normalized);
  normalized.publish_allowed = raw.publish_allowed === true && !mathHide;
  normalized.visible_en_panel = normalized.publish_allowed;
  normalized.visibility_allowed = normalized.publish_allowed;
  normalized.recomendado = normalized.publish_allowed;
  normalized.arbitrage = raw.arbitrage === true;
  normalized.publishable = normalized.publish_allowed;
  normalized.label = raw.label || (normalized.arbitrage ? "Arbitraje detectado" : normalized.recomendado ? "Pick calculado" : normalized.market_complete ? "Mercado detectado" : "Pricing incompleto");
  if (!normalized.publishable && normalized.model_prob !== null && normalized.model_prob < MIN_MODEL_PROBABILITY) {
    normalized.reason_discard = normalized.reason_discard || `below_min_model_probability_${Math.round(MIN_MODEL_PROBABILITY * 100)}`;
  }
  return normalized;
}

function opportunityBadges(opp) {
  const out = [];
  out.push(`<span class="badge">${opp.label || "Mercado detectado"}</span>`);
  if (opp.flags.ev_plus) out.push('<span class="badge ev">EV+</span>');
  if (opp.flags.value) out.push('<span class="badge value">Value</span>');
  if (opp.flags.no_value) out.push('<span class="badge non-value">No Value</span>');
  if (opp.flags.strong_signal) out.push('<span class="badge strong">Strong signal</span>');
  if (opp.flags.secondary_market) out.push('<span class="badge secondary">Secondary market</span>');
  if (!opp.market_complete) out.push('<span class="badge incomplete">Sin pricing completo</span>');
  return out.join(" ");
}

function createOpportunityCard(opp) {
  const tpl = q("opportunity-template");
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".market-code").textContent = `${opp.code} · ${opp.partido || "Partido"}`;
  node.querySelector(".market-name").textContent = `${opp.market} (${opp.family}) · ${opp.liga || "N/D"} · ${opp.pais || "N/D"}`;
  node.querySelector(".card-badges").innerHTML = opportunityBadges(opp);
  node.querySelector(".play").textContent = `Pick: ${opp.pick} · ${dateLabel(opp.hora)} · ${countdownLabel(opp.hora, opp.fixture_status_current || opp.estado)}`;

  const oddsLabel = fmtDecimal(opp.odds, 2) || "N/D";
  const modelLabel = toPercent(opp.model_prob, 1);
  const closeLabel = toPercent(opp.close_probability, 1) || "N/D";
  const impliedLabel = toPercent(opp.implied_prob, 1) || "N/D";
  const deltaLabel = toSignedPercent(opp.delta_prob, 1) || "N/D";
  const edgeLabel = toSignedPercent(opp.edge, 1) || "N/D";
  const evLabel = fmtDecimal(opp.ev, 3) || "N/D";
  const tier = probabilityTier(opp.model_prob);

  node.querySelector(".meta").innerHTML = `
    <div class="probability-main">
      <span class="probability-number">${closeLabel}</span>
      <span class="probability-tier ${tier.css}">${tier.label}</span>
    </div>
    <div class="probability-sub">${modelLabel ? `Prob modelo: <strong>${modelLabel}</strong> · ` : ""}Prob implícita: ${impliedLabel} · ΔProb: ${deltaLabel}</div>
  `;
  node.querySelector(".metrics").innerHTML = `<span class="metric metric-odds">Cuota <strong>${oddsLabel}</strong></span> · Riesgo: ${tier.label} · Edge: ${edgeLabel} · EV: ${evLabel} · Stake: ${opp.stake ?? "N/D"}`;

  const traceNotes = [];
  if (!opp.market_complete) traceNotes.push(opp.completeness_reason || "mercado_detectado_sin_pricing_completo");
  if (opp.reason_discard) traceNotes.push(`Descarte: ${opp.reason_discard}`);
  const traceNode = node.querySelector(".trace");
  traceNode.textContent = `Fuente: ${opp.source || "N/D"} · Inclusión: ${opp.reason_inclusion || "N/D"}${traceNotes.length ? ` · ${traceNotes.join(" · ")}` : ""}`;
  traceNode.hidden = state.ui.hideTraceability;
  return node;
}

function renderOpportunityList(containerId, opportunities, emptyText) {
  const container = q(containerId);
  container.innerHTML = "";
  const safeRows = opportunities.filter((o) => {
    if (state.ui.validOnly) {
      const allowed = state.ui.includeSecondaryWhenValidOnly
        ? new Set(["publishable_core", "publishable_secondary"])
        : new Set(["publishable_core"]);
      return allowed.has(String(o.pick_status || ""));
    }
    return o.visibility_allowed === true && o.publish_allowed === true;
  });
  if (!safeRows.length) {
    if (emptyText) container.innerHTML = `<p class="empty">${emptyText}</p>`;
    return;
  }
  safeRows.forEach((o) => container.appendChild(createOpportunityCard(o)));
}

function applyFilters(opps, options = {}) {
  const cfg = {
    respectFamily: true,
    relaxNumeric: false,
    relaxQuick: false,
    ...options,
  };

  return opps.filter((o) => {
    if (state.filters.country && o.pais !== state.filters.country) return false;
    if (state.filters.league && o.liga !== state.filters.league) return false;
    if (state.filters.team && !(o.partido || "").includes(state.filters.team)) return false;
    if (state.filters.market && o.market !== state.filters.market && o.code !== state.filters.market) return false;
    if (cfg.respectFamily && state.filters.family && o.family !== state.filters.family) return false;
    if (state.filters.search) {
      const hay = `${o.partido} ${o.market} ${o.pick} ${o.code} ${o.pais} ${o.liga} ${o.family}`.toLowerCase();
      if (!hay.includes(state.filters.search.toLowerCase())) return false;
    }

    if (!cfg.relaxNumeric) {
      if (state.filters.oddsMin !== null && (o.odds === null || o.odds < state.filters.oddsMin)) return false;
      if (state.filters.oddsMax !== null && (o.odds === null || o.odds > state.filters.oddsMax)) return false;
      if (state.filters.evMin !== null && (o.ev === null || o.ev < state.filters.evMin)) return false;
      if (state.filters.evMax !== null && (o.ev === null || o.ev > state.filters.evMax)) return false;
      if (state.filters.edgeMin !== null && (o.edge === null || o.edge * 100 < state.filters.edgeMin)) return false;
      if (state.filters.edgeMax !== null && (o.edge === null || o.edge * 100 > state.filters.edgeMax)) return false;
    }

    if (!cfg.relaxQuick) {
      const quick = state.filters.quick;
      if (quick.secondary && !o.flags.secondary_market) return false;
      if (quick.next_matches && !isFuture(o.hora)) return false;
      if (quick.signal_heavy && (toNumber(o.rank) === null || toNumber(o.rank) < 2)) return false;
    }

    return true;
  }).sort((a, b) =>
    (b.close_probability ?? b.model_prob ?? -999) - (a.close_probability ?? a.model_prob ?? -999)
    || (b.model_prob ?? -999) - (a.model_prob ?? -999)
    || (b.score ?? b.rank ?? -999) - (a.score ?? a.rank ?? -999)
    || (b.edge ?? -999) - (a.edge ?? -999)
    || ((a.odds ?? 99) - (b.odds ?? 99))
  );
}

function selectSectionWithFallback(primaryRows, fallbackRows, relaxedRows, opts = {}) {
  if (state.filters.family) return { rows: primaryRows, notice: primaryRows.length ? null : (opts.emptyNotice || null) };
  if (primaryRows.length) return { rows: primaryRows, notice: null };
  if (fallbackRows.length) return { rows: fallbackRows, notice: opts.familyNotice || "No hay resultados para esta familia con los filtros activos. Mostrando oportunidades generales." };
  if (relaxedRows.length) return { rows: relaxedRows, notice: "Filtros demasiado restrictivos. Se relajaron EV/edge/quick para evitar panel vacío." };
  return { rows: [], notice: opts.emptyNotice || null };
}

function renderFilterNotices(messages) {
  const container = q("filter-notices");
  if (!container) return;
  const uniq = Array.from(new Set(messages.filter(Boolean)));
  if (!uniq.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = uniq.map((m) => `<p class="filter-notice">${m}</p>`).join("");
}

function renderKpis(summary) {
  const grid = q("kpi-grid");
  grid.innerHTML = "";
  KPI_CONFIG.forEach(([k, label]) => {
    const el = document.createElement("article");
    el.className = "kpi-card";
    el.innerHTML = `<p>${label}</p><strong>${summary[k] ?? "N/D"}</strong>`;
    grid.appendChild(el);
  });
}

function fillSelect(id, values, keep = "") {
  const el = q(id);
  const sorted = Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
  el.innerHTML = '<option value="">Todos</option>' + sorted.map((v) => `<option value="${v}">${v}</option>`).join("");
  if (keep && sorted.includes(keep)) el.value = keep;
}

function renderLeagueExplorer(tree) {
  const root = q("league-explorer");
  root.innerHTML = "";
  if (!tree.length) return (root.innerHTML = '<p class="empty">Sin datos por país/liga.</p>');
  tree.forEach((country) => {
    const d = document.createElement("details");
    d.className = "country-block";
    d.innerHTML = `<summary>${country.pais} · Ligas: ${(country.ligas || []).length} · Partidos: ${country.partidos} · EV+: ${country.ev_plus} · Value: ${country.value_bets}</summary>`;
    const stack = document.createElement("div");
    stack.className = "league-stack";
    (country.ligas || []).forEach((league) => {
      const l = document.createElement("article");
      l.className = "league-match-item";
      l.innerHTML = `<strong>${league.liga}</strong><span>Partidos: ${league.partidos} · EV+: ${league.ev_plus} · Value: ${league.value_bets}</span>`;
      stack.appendChild(l);
    });
    d.appendChild(stack);
    root.appendChild(d);
  });
}

function hasActionablePick(opp) {
  if (!opp) return false;
  if (state.ui.validOnly) return opp.publishable === true || opp.publish_allowed === true;
  return opp.odds !== null;
}

function passesUiVisibility(opp) {
  if (!hasActionablePick(opp)) return false;
  if (state.ui.hideEmptyFixtures && !opp.publishable && !opp.publish_allowed) return false;
  return true;
}

function renderMatchRadar(radarRows) {
  const container = q("match-radar");
  container.innerHTML = "";
  if (!radarRows.length) return (container.innerHTML = '<p class="empty">No hay radar por partido.</p>');
  radarRows.forEach((row) => {
    const card = document.createElement("article");
    card.className = "match-card";
    const included = (row.oportunidades_incluidas || []).map(normalizeOpportunity).filter(passesUiVisibility);
    const excluded = (row.oportunidades_excluidas || []).map(normalizeOpportunity).filter((o) => !state.ui.validOnly && passesUiVisibility(o));
    if (state.ui.hideEmptyFixtures && !included.length) return;
    card.innerHTML = `<div class="match-head"><strong>${row.equipos?.local || "Local"} vs ${row.equipos?.visitante || "Visitante"}</strong><span>${row.liga || "N/D"} · ${row.pais || "N/D"}</span><span>${dateLabel(row.hora)} · ${countdownLabel(row.hora, row.fixture_status_current || row.estado)}</span><span>Familias: ${(row.familias_detectadas || []).join(", ") || "N/D"}</span></div>`;

    if (!state.ui.hideTraceability) {
      const details = document.createElement("details");
      details.innerHTML = `<summary>Trazabilidad: incluidos, descartes y telemetría</summary>`;
      const grid = document.createElement("div");
      grid.className = "match-opportunities";
      included.forEach((o) => grid.appendChild(createOpportunityCard(o)));
      excluded.forEach((o) => grid.appendChild(createOpportunityCard(o)));
      if (!included.length && !excluded.length) grid.innerHTML = '<p class="empty">Sin mercados evaluados.</p>';
      const trace = document.createElement("pre");
      trace.className = "trace-pre";
      trace.textContent = JSON.stringify(row, null, 2);
      details.append(grid, trace);
      card.appendChild(details);
    }
    container.appendChild(card);
  });
}

function flattenTelemetry(payload) {
  const telemetry = payload.market_telemetry || payload.telemetria_mercados || {};
  const rows = [];
  Object.entries(telemetry || {}).forEach(([fixtureId, marketMap]) => {
    Object.values(marketMap || {}).forEach((row) => rows.push(normalizeOpportunity({ ...row, fixture_id: Number(fixtureId), source: row.source || "market_telemetry" })));
  });
  return rows;
}

function flattenFamilies(payload) {
  const families = payload.families || {};
  const rows = [];
  Object.entries(families).forEach(([family, items]) => {
    const canonical = canonicalFamily(family) || inferFamily({ family });
    (items || []).forEach((row) => {
      rows.push(normalizeOpportunity({
        ...row,
        family: canonicalFamily(row.family) || canonical || inferFamily({ ...row, family }),
        market: row.market || row.mercado || row.code || family,
        pick: row.pick || row.jugada || "N/D",
        source: row.source || "families",
      }));
    });
  });
  return rows;
}

function withFixtureContext(opps, matchMap) {
  return opps.map((opp) => {
    if (opp.partido && opp.pais && opp.liga) return opp;
    const m = matchMap.get(Number(opp.fixture_id));
    if (!m) return opp;
    return {
      ...opp,
      pais: opp.pais || m.pais,
      liga: opp.liga || m.liga,
      partido: opp.partido || `${m.local || "Local"} vs ${m.visitante || "Visitante"}`,
      hora: opp.hora || m.hora,
      fixture_status_current: opp.fixture_status_current || m.fixture_status_current || m.estado,
    };
  });
}

function dedupeOpportunities(opps) {
  const map = new Map();
  opps.forEach((opp) => {
    const key = `${opp.fixture_id || "na"}:${opp.code}:${opp.pick || "na"}`;
    const prev = map.get(key);
    if (!prev) {
      map.set(key, opp);
      return;
    }
    const prevScore = (prev.market_complete ? 5 : 0) + (prev.ev ?? -999) + (prev.flags?.value ? 0.2 : 0) + (prev.flags?.strong_signal ? 0.2 : 0);
    const currScore = (opp.market_complete ? 5 : 0) + (opp.ev ?? -999) + (opp.flags?.value ? 0.2 : 0) + (opp.flags?.strong_signal ? 0.2 : 0);
    if (currScore >= prevScore) map.set(key, opp);
  });
  return Array.from(map.values());
}

function buildUnifiedOpportunities(payload) {
  const matchMap = new Map((payload.partidos || []).map((m) => [Number(m.fixture_id), m]));
  const prioritized = [...flattenTelemetry(payload)];

  const unified = dedupeOpportunities(withFixtureContext(prioritized, matchMap));
  return {
    complete: unified.filter((o) => o.publishable),
    incomplete: unified.filter((o) => !o.publishable),
  };
}

function getFamilyDataset(family, strictDataset, baseDataset) {
  const strictFamily = strictDataset.filter((o) => o.family === family);
  if (strictFamily.length) return { rows: strictFamily.slice(0, 40), notice: null };
  return { rows: [], notice: null };
}

function getIncompleteFamilyDataset(family) {
  const filtered = applyFilters(state.incompleteOpportunities, { respectFamily: false, relaxNumeric: true, relaxQuick: true })
    .filter((o) => o.family === family);
  if (!filtered.length) return { rows: [], notice: null };
  return {
    rows: filtered.slice(0, 30),
    notice: `Se detectaron mercados ${FAMILY_LABELS[family]} sin pricing/modelo completo. Se muestran separados para evitar mezclar calidad de señal.`,
  };
}

function bindFilters() {
  [["filter-country", "country"], ["filter-league", "league"], ["filter-team", "team"], ["filter-market", "market"], ["filter-family", "family"], ["search-input", "search"], ["odds-min", "oddsMin", true], ["odds-max", "oddsMax", true], ["ev-min", "evMin", true], ["ev-max", "evMax", true], ["edge-min", "edgeMin", true], ["edge-max", "edgeMax", true]].forEach(([id, key, n]) => {
    q(id).addEventListener("input", (e) => {
      state.filters[key] = n ? toNumber(e.target.value) : e.target.value;
      renderFromState();
    });
  });

  document.querySelectorAll(".quick-filter").forEach((btn) => {
    btn.addEventListener("click", () => {
      const k = btn.dataset.filter;
      state.filters.quick[k] = !state.filters.quick[k];
      btn.classList.toggle("active", state.filters.quick[k]);
      renderFromState();
    });
  });

  q("reset-filters-btn")?.addEventListener("click", () => {
    state.filters = deepClone(INITIAL_FILTERS);
    ["filter-country", "filter-league", "filter-team", "filter-market", "filter-family", "search-input", "odds-min", "odds-max", "ev-min", "ev-max", "edge-min", "edge-max"].forEach((id) => {
      if (q(id)) q(id).value = "";
    });
    document.querySelectorAll(".quick-filter").forEach((btn) => btn.classList.remove("active"));
    renderFromState();
  });

  q("refresh-btn").addEventListener("click", refreshDashboard);
  q("toggle-valid-only")?.addEventListener("click", () => {
    state.ui.validOnly = !state.ui.validOnly;
    syncToggleButtons();
    renderFromState();
  });
  q("toggle-hide-trace")?.addEventListener("click", () => {
    state.ui.hideTraceability = !state.ui.hideTraceability;
    syncToggleButtons();
    renderFromState();
  });
  q("toggle-hide-empty-fixtures")?.addEventListener("click", () => {
    state.ui.hideEmptyFixtures = !state.ui.hideEmptyFixtures;
    syncToggleButtons();
    renderFromState();
  });
  q("cleanup-old-records")?.addEventListener("click", async () => {
    try {
      const res = await fetch(apiUrl("panel/cleanup-old-records?keep_recent_hours=24"), { method: "POST" });
      if (!res.ok) throw new Error(`cleanup failed ${res.status}`);
      await refreshDashboard();
    } catch (e) {
      console.error("cleanup-old-records failed", e);
      setRefreshState("error", "Error limpieza");
    }
  });
}

function syncToggleButtons() {
  const setLabel = (id, enabledText, disabledText, isEnabled) => {
    const el = q(id);
    if (!el) return;
    el.textContent = isEnabled ? enabledText : disabledText;
    el.classList.toggle("active", isEnabled);
  };
  setLabel("toggle-valid-only", "Mostrar todo", "Mostrar solo apuestas válidas", state.ui.validOnly);
  setLabel("toggle-hide-trace", "Mostrar trazabilidad", "Ocultar trazabilidad", state.ui.hideTraceability);
  setLabel("toggle-hide-empty-fixtures", "Mostrar partidos sin picks", "Ocultar partidos sin picks", state.ui.hideEmptyFixtures);
}

function populateFamilySelector() {
  const selector = q("filter-family");
  if (!selector) return;
  const values = new Set(["1X2", "Goals", "BTTS", "Corners", "Cards", "Shots", "Shots on target", "Fouls", "Offsides", "Double chance", "Exact score", "Secondary"]);
  [...state.opportunities, ...state.incompleteOpportunities].forEach((opp) => {
    if (opp.family) values.add(opp.family);
  });
  const sorted = Array.from(values).sort((a, b) => (FAMILY_LABELS[a] || a).localeCompare(FAMILY_LABELS[b] || b));
  selector.innerHTML = '<option value="">Todas</option>' + sorted.map((value) => `<option value="${value}">${FAMILY_LABELS[value] || value}</option>`).join("");
  if (state.filters.family && sorted.includes(state.filters.family)) {
    selector.value = state.filters.family;
  }
}

function renderFromState() {
  const familyFilterActive = Boolean(state.filters.family);
  const strict = applyFilters(state.opportunities, { respectFamily: true });
  const base = applyFilters(state.opportunities, { respectFamily: false });
  const relaxed = applyFilters(state.opportunities, { respectFamily: false, relaxNumeric: true, relaxQuick: true });
  const notices = [];
  const strictFixtureIds = new Set(strict.map((o) => Number(o.fixture_id)).filter(Number.isFinite));

  const topSection = selectSectionWithFallback(
    strict,
    familyFilterActive ? [] : base,
    familyFilterActive ? [] : relaxed,
    {
    familyNotice: "No hay resultados para la familia seleccionada con los filtros actuales. Mostrando oportunidades generales.",
    emptyNotice: familyFilterActive ? "No hay oportunidades top para la familia seleccionada con los filtros activos." : null,
  });
  if (topSection.notice) notices.push(topSection.notice);
  renderOpportunityList("top-opportunities", topSection.rows.slice(0, 50), "Hay mercados disponibles pero no cumplen filtros de valor");

  const strictFuture = strict.filter((o) => (o.model_prob ?? 0) >= MIN_MODEL_PROBABILITY && isFuture(o.hora));
  const baseFuture = base.filter((o) => (o.model_prob ?? 0) >= MIN_MODEL_PROBABILITY && isFuture(o.hora));
  const relaxedFuture = relaxed.filter((o) => (o.model_prob ?? 0) >= MIN_MODEL_PROBABILITY && isFuture(o.hora));
  const futureSection = selectSectionWithFallback(
    strictFuture,
    familyFilterActive ? [] : baseFuture,
    familyFilterActive ? [] : relaxedFuture,
    {
    familyNotice: "No hay EV+ próximos para esta familia. Mostrando EV+ generales.",
    emptyNotice: familyFilterActive ? "No hay EV+ próximos para la familia seleccionada con los filtros activos." : null,
  });
  if (futureSection.notice) notices.push(futureSection.notice);
  renderOpportunityList("future-opportunities", futureSection.rows.slice(0, 50), "Hay mercados disponibles pero no cumplen filtros de valor");

  const strictSecondary = strict.filter((o) => o.flags.secondary_market || o.family === "Secondary");
  const baseSecondary = base.filter((o) => o.flags.secondary_market || o.family === "Secondary");
  const relaxedSecondary = relaxed.filter((o) => o.flags.secondary_market || o.family === "Secondary");
  const secondarySection = selectSectionWithFallback(
    strictSecondary,
    familyFilterActive ? [] : baseSecondary,
    familyFilterActive ? [] : relaxedSecondary,
    {
    familyNotice: "No hay mercados secundarios para esta familia. Mostrando secundarios generales.",
    emptyNotice: familyFilterActive ? "No hay mercados secundarios para la familia seleccionada con los filtros activos." : null,
  });
  if (secondarySection.notice) notices.push(secondarySection.notice);
  renderOpportunityList("secondary-opportunities", secondarySection.rows.slice(0, 50), "No hay secundarios con valor.");

  const familySections = [
    ["1X2", "family-1x2", "family-1x2-incomplete", "Sin 1X2 para filtros activos."],
    ["Double chance", "family-double-chance", "family-double-chance-incomplete", "Sin double chance para filtros activos."],
    ["Goals", "family-goals", "family-goals-incomplete", "Sin goals para filtros activos."],
    ["BTTS", "family-btts", "family-btts-incomplete", "Sin BTTS para filtros activos."],
    ["Corners", "family-corners", "family-corners-incomplete", "Hay mercados disponibles pero no cumplen filtros de valor"],
    ["Cards", "family-cards", "family-cards-incomplete", "Hay mercados disponibles pero no cumplen filtros de valor"],
    ["Shots", "family-shots", "family-shots-incomplete", "Sin shots para filtros activos."],
    ["Shots on target", "family-shots-on-target", "family-shots-on-target-incomplete", "Sin shots on target para filtros activos."],
    ["Fouls", "family-fouls", "family-fouls-incomplete", "Sin fouls para filtros activos."],
    ["Offsides", "family-offsides", "family-offsides-incomplete", "Sin offsides para filtros activos."],
    ["Secondary", "family-secondary", "family-secondary-incomplete", "Sin secondary para filtros activos."],
  ];

  familySections.forEach(([family, target, incompleteTarget, empty]) => {
    const result = getFamilyDataset(family, strict, base);
    if (result.notice && (!state.filters.family || state.filters.family === family)) notices.push(result.notice);
    const familyBucket = state.byFamily[family.toLowerCase()] || state.byFamily[family] || [];
    const finalEmpty = familyBucket.length
      ? "Hay mercados detectados con odds válidas pendientes de pricing completo"
      : empty;
    renderOpportunityList(target, result.rows, finalEmpty);

    const incomplete = getIncompleteFamilyDataset(family);
    if (incomplete.notice && (!state.filters.family || state.filters.family === family)) notices.push(incomplete.notice);
    renderOpportunityList(incompleteTarget, incomplete.rows, "No hay mercados detectados sin métricas completas para esta familia.");
  });

  renderFilterNotices(notices);
  renderKpis(state.summary);
  renderLeagueExplorer(state.countryTree.filter((country) => {
    const leagues = (country.ligas || []).filter((league) => (league.partidos || 0) > 0);
    return leagues.length > 0;
  }));
  const filteredRadar = state.matchRadar.filter((row) => {
    if (!strictFixtureIds.size) return !state.ui.hideEmptyFixtures;
    return strictFixtureIds.has(Number(row.fixture_id));
  });
  renderMatchRadar(filteredRadar);
}

function setRefreshState(mode, text) {
  const status = q("refresh-state");
  status.className = `badge status-badge ${mode}`;
  status.textContent = text;
}

async function fetchJson(path) {
  const url = apiUrl(path);
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

function computeSummary(payload) {
  const s = payload.summary || {};
  return {
    totalCountries: s.total_paises ?? 0,
    totalLeagues: s.total_ligas ?? 0,
    totalMatches: s.total_partidos_proximos ?? 0,
    totalMarkets: s.total_mercados_analizados ?? 0,
    totalSignals: s.total_senales ?? 0,
    totalEVPlus: s.total_oportunidades_ev_plus ?? 0,
    totalStrong: s.total_apuestas_fuertes ?? 0,
    totalValue: s.total_value_bets ?? 0,
  };
}

function populateSelectors() {
  fillSelect("filter-country", state.opportunities.map((o) => o.pais), state.filters.country);
  fillSelect("filter-league", state.opportunities.map((o) => o.liga), state.filters.league);
  fillSelect("filter-team", state.opportunities.flatMap((o) => (o.partido || "").split(" vs ")), state.filters.team);
  fillSelect("filter-market", [...state.opportunities, ...state.incompleteOpportunities].flatMap((o) => [o.market, o.code]), state.filters.market);
  populateFamilySelector();
}

async function refreshDashboard() {
  const btn = q("refresh-btn");
  btn.disabled = true;
  setRefreshState("loading", "Cargando");
  try {
    const errorNode = q("dashboard-error");
    if (errorNode) {
      errorNode.hidden = true;
      errorNode.textContent = "";
    }
    const params = new URLSearchParams(window.location.search);
    const selectedRunId = params.get("run_id");
    const query = selectedRunId ? `?limit=3000&run_id=${encodeURIComponent(selectedRunId)}` : "?limit=3000";
    const payload = await fetchJson(`panel/dashboard${query}`);
    state.matches = Array.isArray(payload.partidos) ? payload.partidos : [];
    const filteredPayload = {
      ...payload,
      partidos: state.matches,
      match_radar: Array.isArray(payload.match_radar) ? payload.match_radar : [],
      oportunidades_ev: Array.isArray(payload.oportunidades_ev) ? payload.oportunidades_ev : [],
    };
    const unified = buildUnifiedOpportunities(filteredPayload);
    state.opportunities = unified.complete;
    state.incompleteOpportunities = unified.incomplete;
    state.matchRadar = filteredPayload.match_radar;
    state.byFamily = payload.families || {};
    state.countryTree = payload.paises || [];
    state.summary = computeSummary(payload);
    const debug = payload.debug || {};
    const debugNode = q("debug-run");
    if (debugNode) {
      debugNode.textContent = `run_id=${debug.run_id ?? "N/D"} · fixtures_total=${debug.fixtures_total ?? 0} · processed=${debug.processed ?? 0} · skipped=${debug.skipped ?? 0} · dashboard_read=${debug.fixtures_visible ?? 0}`;
    }
    populateSelectors();
    syncToggleButtons();
    renderFromState();
    q("last-updated").textContent = `Última actualización: ${dateLabel(payload.generated_at || new Date().toISOString())}`;
    setRefreshState("ok", "Actualizado");
  } catch (e) {
    console.error("refreshDashboard failed", e);
    const errorNode = q("dashboard-error");
    if (errorNode) {
      errorNode.hidden = false;
      errorNode.textContent = `No se pudo cargar /panel/dashboard (${String(e?.message || "error desconocido")}).`;
    }
    setRefreshState("error", "Error");
  } finally {
    btn.disabled = false;
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("DOMContentLoaded", () => {
    bindFilters();
    syncToggleButtons();
    refreshDashboard();
  });
}
