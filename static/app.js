const state = {
  matches: [],
  opportunities: [],
  opportunitiesByMatch: new Map(),
  filters: {
    country: "",
    league: "",
    team: "",
    market: "",
    search: "",
    oddsMin: null,
    oddsMax: null,
    evMin: null,
    evMax: null,
    edgeMin: null,
    edgeMax: null,
    quick: {
      only_ev: false,
      only_value: false,
      only_strong: false,
      secondary: false,
      next_matches: false,
      signal_heavy: false,
    },
  },
  summary: {},
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

function q(id) {
  return document.getElementById(id);
}

function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function normalizePercent(value) {
  const n = toNumber(value);
  if (n === null) return null;
  return n > 1 ? n : n * 100;
}

function metricText(label, value, suffix = "") {
  if (value === null || value === undefined) return `${label}: N/D`;
  return `${label}: ${value}${suffix}`;
}

function dateLabel(iso) {
  if (!iso) return "Hora no informada";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  return new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short" }).format(new Date(t));
}

function countdownLabel(iso) {
  const t = Date.parse(iso || "");
  if (Number.isNaN(t)) return "Sin countdown";
  const diff = t - Date.now();
  if (diff <= 0) return "En curso / iniciado";
  const totalMin = Math.floor(diff / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return `En ${h}h ${m}m`;
}

function inferGroup(code = "") {
  const c = code.toUpperCase();
  if (c.includes("CORNERS")) return "Corners";
  if (c.includes("CARDS")) return "Cards";
  if (c.includes("SHOTS") || c.includes("SOT")) return "Shots";
  if (c.includes("HANDICAP")) return "Handicap";
  if (c.includes("GOAL") || c.includes("BTTS") || c.includes("TOTAL")) return "Goals";
  return "1X2 / Principal";
}

function secondaryMarket(code = "", market = "") {
  return /CORNERS|CARDS|SHOTS|SOT|HANDICAP|PROP|GOALS|BTTS|TOTAL/i.test(`${code} ${market}`);
}

function normalizeSignals(raw) {
  if (Array.isArray(raw)) return raw.filter((x) => x && typeof x === "object");
  if (raw && typeof raw === "object") return [raw];
  return [];
}

function isFuture(iso) {
  const t = Date.parse(iso || "");
  return Number.isFinite(t) && t >= Date.now();
}

function parseMatch(match) {
  return {
    id: match.id || match.fixture_id,
    fixture_id: match.fixture_id || match.id,
    country: match.pais || match.country || "N/D",
    league: match.liga || match.league || "N/D",
    leagueId: match.liga_id || match.league_id || null,
    home: match.local || match.home_team_name || "Local",
    away: match.visitante || match.away_team_name || "Visitante",
    time: match.hora || match.fixture_datetime || null,
    raw: match,
  };
}

function toOpportunity(raw, match, telemetryByCode = {}) {
  if (!raw || typeof raw !== "object") return null;
  const code = String(raw.code || raw.codigo || raw.market_code || raw.mercado_codigo || raw.mercado || "N/D");
  const market = raw.mercado || raw.market_name || raw.market || code;
  const modelProb = normalizePercent(raw.probabilidad_modelo ?? raw.model_prob ?? raw.probabilidad ?? raw.prob_apuesta ?? raw.score);
  const impliedProb = normalizePercent(raw.probabilidad_implicita ?? raw.implied_prob ?? raw.fair_market_prob);
  const edge = normalizePercent(raw.edge ?? raw.edge_pct ?? raw.edge_percent);
  const ev = toNumber(raw.ev ?? raw.expected_value ?? raw.valor_esperado ?? raw.ev_principal);
  const rank = toNumber(raw.rank ?? raw.ranking ?? raw.score_rank ?? raw.rank_score ?? raw.score);
  const score = toNumber(raw.score ?? raw.signal_score ?? raw.confianza);
  const stake = toNumber(raw.stake_recomendado ?? raw.stake_sugerido_unidades ?? raw.stake_units ?? raw.stake);
  const odds = toNumber(raw.cuota ?? raw.odds ?? raw.price ?? raw.cuota_principal);
  const signals = normalizeSignals(raw.senales || raw.signals || raw.signal_components);

  const telemetry =
    telemetryByCode[code] ||
    telemetryByCode[code.toLowerCase?.() || ""] ||
    raw.telemetria ||
    raw.telemetry ||
    null;

  const valueRaw = raw.value ?? raw.es_value_bet ?? raw.is_value ?? raw.oportunidad_detectada;
  const strongRaw = raw.strong ?? raw.es_fuerte ?? raw.signal_tier === "strong_value";

  return {
    matchId: match.id,
    fixtureId: match.fixture_id,
    country: match.country,
    league: match.league,
    teams: `${match.home} vs ${match.away}`,
    home: match.home,
    away: match.away,
    time: match.time,
    code,
    market,
    group: raw.group || raw.market_group || inferGroup(code),
    pick: raw.jugada || raw.pick || raw.selection || match.raw.apuesta_principal || "N/D",
    odds,
    modelProb,
    impliedProb,
    probDiff: modelProb !== null && impliedProb !== null ? modelProb - impliedProb : null,
    edge,
    ev,
    rank,
    score,
    stake,
    value: Boolean(valueRaw),
    strong: Boolean(strongRaw),
    evPositive: ev !== null ? ev > 0 : false,
    source: raw.fuente || raw.source || raw.inclusion_reason || raw.razon_inclusion || "backend",
    includeReason: raw.razon_inclusion || raw.include_reason || raw.inclusion_reason || "No informado",
    discardReason: raw.razon_descarte || raw.discard_reason || null,
    confidence: raw.confianza || raw.intensidad || raw.intensity || null,
    timestamp: raw.timestamp || raw.vigencia || raw.updated_at || null,
    telemetry,
    signals,
    raw,
  };
}

function flattenOpportunities(match) {
  const telemetry = match.raw.telemetria_mercados || match.raw.market_telemetry || {};
  const sources = [];

  if (Array.isArray(match.raw.oportunidades_ev)) sources.push(...match.raw.oportunidades_ev);
  if (Array.isArray(match.raw.top_opportunities)) sources.push(...match.raw.top_opportunities);

  if (!sources.length && match.raw.ev_principal !== null && match.raw.ev_principal !== undefined) {
    sources.push({
      code: match.raw.mercado_principal,
      mercado: match.raw.mercado_principal,
      jugada: match.raw.apuesta_principal,
      cuota: match.raw.cuota_principal,
      model_prob: match.raw.prob_apuesta,
      implied_prob: match.raw.probabilidad_implicita_principal,
      edge: match.raw.edge_principal,
      ev: match.raw.ev_principal,
      stake_sugerido_unidades: match.raw.stake_sugerido_unidades,
      score: match.raw.confianza,
      value: match.raw.es_value_bet,
      inclusion_reason: "ev_principal",
      signal_components: match.raw.apuestas_fuertes,
    });
  }

  if (!sources.length && Array.isArray(match.raw.apuestas_fuertes)) {
    sources.push(...match.raw.apuestas_fuertes);
  }

  return sources
    .map((raw) => toOpportunity(raw, match, telemetry))
    .filter(Boolean)
    .sort((a, b) => (b.ev ?? -999) - (a.ev ?? -999) || (b.rank ?? -999) - (a.rank ?? -999) || (b.edge ?? -999) - (a.edge ?? -999));
}

function opportunityBadges(opp) {
  const tags = [];
  if (opp.evPositive) tags.push('<span class="badge ev">EV+</span>');
  tags.push(`<span class="badge ${opp.value ? "value" : "non-value"}">${opp.value ? "Value" : "No Value"}</span>`);
  if (opp.strong) tags.push('<span class="badge strong">Strong signal</span>');
  if (secondaryMarket(opp.code, opp.market)) tags.push('<span class="badge secondary">Secondary market</span>');
  return tags.join(" ");
}

function createOpportunityCard(opp) {
  const tpl = q("opportunity-template");
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".market-code").textContent = `${opp.code} · ${opp.teams}`;
  node.querySelector(".market-name").textContent = `${opp.market} (${opp.group}) · ${opp.league} · ${opp.country}`;
  node.querySelector(".card-badges").innerHTML = opportunityBadges(opp);
  node.querySelector(".play").textContent = `Pick: ${opp.pick} · ${dateLabel(opp.time)} · ${countdownLabel(opp.time)}`;
  node.querySelector(".meta").textContent = [
    metricText("Cuota", opp.odds !== null ? opp.odds.toFixed(2) : null),
    metricText("Prob modelo", opp.modelProb !== null ? opp.modelProb.toFixed(2) : null, "%"),
    metricText("Prob implícita", opp.impliedProb !== null ? opp.impliedProb.toFixed(2) : null, "%"),
    metricText("ΔProb", opp.probDiff !== null ? opp.probDiff.toFixed(2) : null, "pp"),
  ].join(" · ");

  node.querySelector(".metrics").textContent = [
    metricText("Edge", opp.edge !== null ? opp.edge.toFixed(2) : null, "%"),
    metricText("EV", opp.ev !== null ? opp.ev.toFixed(4) : null),
    metricText("Rank", opp.rank !== null ? opp.rank.toFixed(2) : null),
    metricText("Score", opp.score !== null ? opp.score.toFixed(2) : null),
    metricText("Stake", opp.stake !== null ? opp.stake.toFixed(2) : null, "u"),
  ].join(" · ");

  const trace = [
    `Fuente: ${opp.source || "N/D"}`,
    `Inclusión: ${opp.includeReason || "N/D"}`,
    opp.discardReason ? `Descarte: ${opp.discardReason}` : null,
    opp.confidence !== null ? `Confianza: ${opp.confidence}` : null,
    opp.timestamp ? `Vigencia: ${opp.timestamp}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  node.querySelector(".trace").textContent = trace;
  return node;
}

function renderOpportunityList(containerId, opportunities, emptyText) {
  const container = q(containerId);
  container.innerHTML = "";
  if (!opportunities.length) {
    container.innerHTML = `<p class="empty">${emptyText}</p>`;
    return;
  }
  opportunities.forEach((opp) => container.appendChild(createOpportunityCard(opp)));
}

function groupHierarchy(matches, opportunities) {
  const byMatch = new Map();
  opportunities.forEach((opp) => {
    if (!byMatch.has(opp.matchId)) byMatch.set(opp.matchId, []);
    byMatch.get(opp.matchId).push(opp);
  });

  const countries = new Map();
  for (const m of matches) {
    const countryKey = m.country || "N/D";
    if (!countries.has(countryKey)) countries.set(countryKey, { country: countryKey, leagues: new Map(), matches: 0, ev: 0 });
    const c = countries.get(countryKey);
    c.matches += 1;

    const leagueKey = `${m.league || "N/D"}::${m.leagueId || "0"}`;
    if (!c.leagues.has(leagueKey)) c.leagues.set(leagueKey, { league: m.league || "N/D", leagueId: m.leagueId, matches: [], markets: 0, signals: 0, value: 0, ev: 0 });
    const l = c.leagues.get(leagueKey);
    const opps = byMatch.get(m.id) || [];
    l.matches.push({ match: m, opps });
    l.markets += new Set(opps.map((x) => x.code)).size;
    l.signals += opps.reduce((acc, x) => acc + (x.signals?.length || 0), 0);
    l.value += opps.filter((x) => x.value).length;
    const evCount = opps.filter((x) => x.evPositive).length;
    l.ev += evCount;
    c.ev += evCount;
  }

  return countries;
}

function renderLeagueExplorer(matches, opportunities) {
  const root = q("league-explorer");
  root.innerHTML = "";
  const hierarchy = groupHierarchy(matches, opportunities);
  if (!hierarchy.size) {
    root.innerHTML = '<p class="empty">Sin datos por país/liga.</p>';
    return;
  }

  for (const [country, payload] of Array.from(hierarchy.entries()).sort((a, b) => a[0].localeCompare(b[0]))) {
    const countryDetails = document.createElement("details");
    countryDetails.className = "country-block";

    countryDetails.innerHTML = `<summary>${country} · Ligas: ${payload.leagues.size} · Partidos: ${payload.matches} · EV+: ${payload.ev}</summary>`;

    const leaguesWrap = document.createElement("div");
    leaguesWrap.className = "league-stack";

    for (const [, leaguePayload] of Array.from(payload.leagues.entries()).sort((a, b) => a[1].league.localeCompare(b[1].league))) {
      const leagueDetails = document.createElement("details");
      leagueDetails.className = "league-block";
      leagueDetails.innerHTML = `<summary>${leaguePayload.league} · Partidos: ${leaguePayload.matches.length} · Mercados: ${leaguePayload.markets} · Señales: ${leaguePayload.signals} · Value: ${leaguePayload.value}</summary>`;

      const list = document.createElement("div");
      list.className = "league-match-list";
      leaguePayload.matches.forEach(({ match, opps }) => {
        const item = document.createElement("article");
        item.className = "league-match-item";
        item.innerHTML = `
          <strong>${match.home} vs ${match.away}</strong>
          <span>${dateLabel(match.time)}</span>
          <span>Mercados: ${new Set(opps.map((x) => x.code)).size} · Oportunidades EV+: ${opps.filter((x) => x.evPositive).length}</span>
        `;
        list.appendChild(item);
      });
      leagueDetails.appendChild(list);
      leaguesWrap.appendChild(leagueDetails);
    }

    countryDetails.appendChild(leaguesWrap);
    root.appendChild(countryDetails);
  }
}

function renderMatchRadar(matches, opportunitiesByMatch) {
  const container = q("match-radar");
  container.innerHTML = "";
  if (!matches.length) {
    container.innerHTML = '<p class="empty">No hay partidos disponibles.</p>';
    return;
  }

  for (const m of matches) {
    const opps = opportunitiesByMatch.get(m.id) || [];
    const card = document.createElement("article");
    card.className = "match-card";

    const summary = `
      <div class="match-head">
        <strong>${m.home} vs ${m.away}</strong>
        <span>${m.league} · ${m.country}</span>
        <span>${dateLabel(m.time)} · ${countdownLabel(m.time)}</span>
        <span>Mercados: ${new Set(opps.map((x) => x.code)).size} · EV+: ${opps.filter((x) => x.evPositive).length}</span>
      </div>
    `;

    const details = document.createElement("details");
    details.open = false;
    details.innerHTML = `<summary>Abrir radar de trazabilidad</summary>`;

    const oppGrid = document.createElement("div");
    oppGrid.className = "match-opportunities";
    if (opps.length) opps.forEach((opp) => oppGrid.appendChild(createOpportunityCard(opp)));
    else oppGrid.innerHTML = '<p class="empty">Sin oportunidades cuantitativas reportadas.</p>';

    const tracePanel = document.createElement("pre");
    tracePanel.className = "trace-pre";
    tracePanel.textContent = JSON.stringify(
      {
        top_opportunities: m.raw.top_opportunities || [],
        oportunidades_ev: m.raw.oportunidades_ev || [],
        ev_principal: m.raw.ev_principal ?? null,
        telemetria_mercados: m.raw.telemetria_mercados || m.raw.market_telemetry || {},
        apuestas_fuertes: m.raw.apuestas_fuertes || [],
        raw_match: m.raw,
      },
      null,
      2,
    );

    details.append(oppGrid, tracePanel);
    card.innerHTML = summary;
    card.appendChild(details);
    container.appendChild(card);
  }
}

function applyFilters(opportunities) {
  return opportunities.filter((opp) => {
    if (state.filters.country && opp.country !== state.filters.country) return false;
    if (state.filters.league && opp.league !== state.filters.league) return false;
    if (state.filters.team && ![opp.home, opp.away].includes(state.filters.team)) return false;
    if (state.filters.market && opp.market !== state.filters.market && opp.code !== state.filters.market) return false;

    if (state.filters.search) {
      const hay = `${opp.teams} ${opp.market} ${opp.pick} ${opp.league} ${opp.country} ${opp.code}`.toLowerCase();
      if (!hay.includes(state.filters.search.toLowerCase())) return false;
    }

    if (state.filters.oddsMin !== null && (opp.odds === null || opp.odds < state.filters.oddsMin)) return false;
    if (state.filters.oddsMax !== null && (opp.odds === null || opp.odds > state.filters.oddsMax)) return false;
    if (state.filters.evMin !== null && (opp.ev === null || opp.ev < state.filters.evMin)) return false;
    if (state.filters.evMax !== null && (opp.ev === null || opp.ev > state.filters.evMax)) return false;
    if (state.filters.edgeMin !== null && (opp.edge === null || opp.edge < state.filters.edgeMin)) return false;
    if (state.filters.edgeMax !== null && (opp.edge === null || opp.edge > state.filters.edgeMax)) return false;

    const quick = state.filters.quick;
    if (quick.only_ev && !opp.evPositive) return false;
    if (quick.only_value && !opp.value) return false;
    if (quick.only_strong && !opp.strong) return false;
    if (quick.secondary && !secondaryMarket(opp.code, opp.market)) return false;
    if (quick.next_matches && !isFuture(opp.time)) return false;
    if (quick.signal_heavy && (opp.signals?.length || 0) < 2) return false;

    return true;
  });
}

function computeSummary(matches, opportunities, summaryRaw) {
  const countries = new Set(matches.map((m) => m.country).filter(Boolean));
  const leagues = new Set(matches.map((m) => `${m.league}::${m.leagueId || ""}`).filter(Boolean));
  const markets = new Set(opportunities.map((o) => o.code).filter(Boolean));
  const signals = opportunities.reduce((acc, o) => acc + (o.signals?.length || 0), 0);

  return {
    totalCountries: countries.size,
    totalLeagues: leagues.size || summaryRaw?.ligas || 0,
    totalMatches: matches.length || summaryRaw?.partidos || 0,
    totalMarkets: markets.size,
    totalSignals: signals || summaryRaw?.senales || summaryRaw?.signals || 0,
    totalEVPlus: opportunities.filter((o) => o.evPositive).length,
    totalStrong: opportunities.filter((o) => o.strong).length || summaryRaw?.strong || 0,
    totalValue: opportunities.filter((o) => o.value).length || summaryRaw?.valueBets || summaryRaw?.value_bets || 0,
  };
}

function renderKpis(summary) {
  const grid = q("kpi-grid");
  grid.innerHTML = "";
  KPI_CONFIG.forEach(([key, label]) => {
    const item = document.createElement("article");
    item.className = "kpi-card";
    item.innerHTML = `<p>${label}</p><strong>${summary[key] ?? "N/D"}</strong>`;
    grid.appendChild(item);
  });
}

function fillSelect(id, values, keep = "") {
  const el = q(id);
  const sorted = Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
  el.innerHTML = '<option value="">Todos</option>' + sorted.map((v) => `<option value="${v}">${v}</option>`).join("");
  if (keep && sorted.includes(keep)) el.value = keep;
}

function bindFilters(matches, opportunities) {
  fillSelect("filter-country", matches.map((m) => m.country), state.filters.country);
  fillSelect("filter-league", matches.map((m) => m.league), state.filters.league);
  fillSelect("filter-team", matches.flatMap((m) => [m.home, m.away]), state.filters.team);
  fillSelect("filter-market", opportunities.flatMap((o) => [o.market, o.code]), state.filters.market);
}

function renderFromState() {
  const filteredOpps = applyFilters(state.opportunities).sort((a, b) => (b.ev ?? -999) - (a.ev ?? -999) || (b.rank ?? -999) - (a.rank ?? -999) || (b.edge ?? -999) - (a.edge ?? -999));
  const allowedMatchIds = new Set(filteredOpps.map((o) => o.matchId));
  const filteredMatches = state.matches.filter((m) => allowedMatchIds.has(m.id) || !state.opportunities.length);

  renderKpis(state.summary);
  renderOpportunityList("top-opportunities", filteredOpps.slice(0, 40), "No hay oportunidades top para los filtros activos.");
  renderOpportunityList("future-opportunities", filteredOpps.filter((o) => isFuture(o.time) && o.evPositive).slice(0, 40), "No hay EV+ próximos con estos filtros.");
  renderOpportunityList("secondary-opportunities", filteredOpps.filter((o) => secondaryMarket(o.code, o.market)).slice(0, 40), "No hay mercados secundarios con valor para los filtros activos.");

  const byMatch = new Map();
  filteredOpps.forEach((opp) => {
    if (!byMatch.has(opp.matchId)) byMatch.set(opp.matchId, []);
    byMatch.get(opp.matchId).push(opp);
  });

  renderLeagueExplorer(filteredMatches, filteredOpps);
  renderMatchRadar(filteredMatches, byMatch);
}

function setRefreshState(mode, text) {
  const status = q("refresh-state");
  status.textContent = text;
  status.className = `badge status-badge ${mode}`;
}

async function fetchJson(path) {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function loadDashboardData() {
  const [partidosRes, resumenRes, fuertesRes] = await Promise.all([
    fetchJson("/panel/partidos?limit=2000"),
    fetchJson("/panel/resumen"),
    fetchJson("/panel/apuestas-fuertes?limit=1000").catch(() => ({ apuestas: [] })),
  ]);

  const matches = Array.isArray(partidosRes.partidos) ? partidosRes.partidos.map(parseMatch) : [];
  const opportunitiesByMatch = new Map();
  const allOpps = [];

  for (const m of matches) {
    const opps = flattenOpportunities(m);
    opportunitiesByMatch.set(m.id, opps);
    allOpps.push(...opps);
  }

  // Soporta apuestas fuertes sueltas si no aparecen en los partidos.
  const strong = Array.isArray(fuertesRes.apuestas) ? fuertesRes.apuestas : [];
  strong.forEach((raw, idx) => {
    const syntheticMatch = {
      id: raw.id || `strong-${idx}`,
      fixture_id: raw.id || null,
      country: raw.pais || "N/D",
      league: raw.liga || "N/D",
      leagueId: null,
      home: (raw.partido || "Local vs Visitante").split(" vs ")[0] || "Local",
      away: (raw.partido || "Local vs Visitante").split(" vs ")[1] || "Visitante",
      time: raw.hora || null,
      raw: {},
    };
    const opp = toOpportunity(raw, syntheticMatch, {});
    if (opp) {
      opp.strong = true;
      if (!allOpps.find((x) => x.fixtureId && x.fixtureId === opp.fixtureId && x.market === opp.market && x.pick === opp.pick)) {
        allOpps.push(opp);
      }
    }
  });

  return { matches, allOpps, opportunitiesByMatch, resumen: resumenRes };
}

function updateLastUpdated() {
  q("last-updated").textContent = `Última actualización: ${new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "medium" }).format(new Date())}`;
}

async function refreshDashboard() {
  const btn = q("refresh-btn");
  btn.disabled = true;
  setRefreshState("loading", "Cargando");
  try {
    const payload = await loadDashboardData();
    state.matches = payload.matches;
    state.opportunities = payload.allOpps;
    state.opportunitiesByMatch = payload.opportunitiesByMatch;
    state.summary = computeSummary(payload.matches, payload.allOpps, payload.resumen);
    bindFilters(payload.matches, payload.allOpps);
    renderFromState();
    updateLastUpdated();
    setRefreshState("ok", "Actualizado");
  } catch (err) {
    console.error(err);
    setRefreshState("error", "Error");
  } finally {
    btn.disabled = false;
  }
}

function attachFilterEvents() {
  const map = [
    ["filter-country", "country"],
    ["filter-league", "league"],
    ["filter-team", "team"],
    ["filter-market", "market"],
    ["search-input", "search"],
    ["odds-min", "oddsMin", true],
    ["odds-max", "oddsMax", true],
    ["ev-min", "evMin", true],
    ["ev-max", "evMax", true],
    ["edge-min", "edgeMin", true],
    ["edge-max", "edgeMax", true],
  ];

  map.forEach(([id, key, numeric]) => {
    q(id).addEventListener("input", (ev) => {
      state.filters[key] = numeric ? toNumber(ev.target.value) : ev.target.value;
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

  q("refresh-btn").addEventListener("click", refreshDashboard);
}

function init() {
  attachFilterEvents();
  refreshDashboard();
}

if (typeof window !== "undefined") {
  window.addEventListener("DOMContentLoaded", init);
}

if (typeof module !== "undefined") {
  module.exports = { toOpportunity, flattenOpportunities, secondaryMarket, computeSummary };
}
