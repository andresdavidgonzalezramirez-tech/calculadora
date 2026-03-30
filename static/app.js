const state = {
  matches: [],
  opportunities: [],
  matchRadar: [],
  byFamily: {},
  countryTree: [],
  filters: {
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

const q = (id) => document.getElementById(id);
const toNumber = (v) => (v === null || v === undefined || v === "" ? null : Number.isFinite(Number(v)) ? Number(v) : null);
const isFuture = (iso) => Number.isFinite(Date.parse(iso || "")) && Date.parse(iso) >= Date.now();
const dateLabel = (iso) => (!iso ? "Hora no informada" : new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso)));
const countdownLabel = (iso) => {
  const t = Date.parse(iso || "");
  if (!Number.isFinite(t)) return "Sin countdown";
  const d = t - Date.now();
  if (d <= 0) return "En curso / iniciado";
  const min = Math.floor(d / 60000);
  return `En ${Math.floor(min / 60)}h ${min % 60}m`;
};

function normalizeOpportunity(raw) {
  const flags = raw.flags || {};
  return {
    ...raw,
    code: raw.code || "N/D",
    family: raw.family || "secondary",
    market: raw.market || raw.code || "N/D",
    pick: raw.pick || raw.jugada || "N/D",
    odds: toNumber(raw.odds),
    model_prob: toNumber(raw.model_prob),
    implied_prob: toNumber(raw.implied_prob),
    delta_prob: toNumber(raw.delta_prob),
    edge: toNumber(raw.edge),
    ev: toNumber(raw.ev),
    rank: toNumber(raw.rank),
    score: toNumber(raw.score),
    stake: toNumber(raw.stake),
    flags: {
      ev_plus: Boolean(flags.ev_plus ?? (toNumber(raw.ev) !== null && toNumber(raw.ev) > 0)),
      value: Boolean(flags.value),
      no_value: Boolean(flags.no_value),
      strong_signal: Boolean(flags.strong_signal),
      secondary_market: Boolean(flags.secondary_market),
    },
  };
}

function opportunityBadges(opp) {
  const out = [];
  if (opp.flags.ev_plus) out.push('<span class="badge ev">EV+</span>');
  if (opp.flags.value) out.push('<span class="badge value">Value</span>');
  if (opp.flags.no_value) out.push('<span class="badge non-value">No Value</span>');
  if (opp.flags.strong_signal) out.push('<span class="badge strong">Strong signal</span>');
  if (opp.flags.secondary_market) out.push('<span class="badge secondary">Secondary market</span>');
  return out.join(" ");
}

function createOpportunityCard(opp) {
  const tpl = q("opportunity-template");
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".market-code").textContent = `${opp.code} · ${opp.partido || "Partido"}`;
  node.querySelector(".market-name").textContent = `${opp.market} (${opp.family}) · ${opp.liga || "N/D"} · ${opp.pais || "N/D"}`;
  node.querySelector(".card-badges").innerHTML = opportunityBadges(opp);
  node.querySelector(".play").textContent = `Pick: ${opp.pick} · ${dateLabel(opp.hora)} · ${countdownLabel(opp.hora)}`;
  node.querySelector(".meta").textContent = `Cuota: ${opp.odds ?? "N/D"} · Prob modelo: ${opp.model_prob ?? "N/D"} · Prob implícita: ${opp.implied_prob ?? "N/D"} · ΔProb: ${opp.delta_prob ?? "N/D"}`;
  node.querySelector(".metrics").textContent = `Edge: ${opp.edge ?? "N/D"} · EV: ${opp.ev ?? "N/D"} · Rank: ${opp.rank ?? "N/D"} · Score: ${opp.score ?? "N/D"} · Stake: ${opp.stake ?? "N/D"}`;
  node.querySelector(".trace").textContent = `Fuente: ${opp.source || "N/D"} · Inclusión: ${opp.reason_inclusion || "N/D"}${opp.reason_discard ? ` · Descarte: ${opp.reason_discard}` : ""}`;
  return node;
}

function renderOpportunityList(containerId, opportunities, emptyText) {
  const container = q(containerId);
  container.innerHTML = "";
  if (!opportunities.length) return (container.innerHTML = `<p class="empty">${emptyText}</p>`);
  opportunities.forEach((o) => container.appendChild(createOpportunityCard(o)));
}

function applyFilters(opps) {
  return opps.filter((o) => {
    if (state.filters.country && o.pais !== state.filters.country) return false;
    if (state.filters.league && o.liga !== state.filters.league) return false;
    if (state.filters.team && !(o.partido || "").includes(state.filters.team)) return false;
    if (state.filters.market && o.market !== state.filters.market && o.code !== state.filters.market) return false;
    if (state.filters.family && o.family !== state.filters.family) return false;
    if (state.filters.search) {
      const hay = `${o.partido} ${o.market} ${o.pick} ${o.code} ${o.pais} ${o.liga} ${o.family}`.toLowerCase();
      if (!hay.includes(state.filters.search.toLowerCase())) return false;
    }
    if (state.filters.oddsMin !== null && (o.odds === null || o.odds < state.filters.oddsMin)) return false;
    if (state.filters.oddsMax !== null && (o.odds === null || o.odds > state.filters.oddsMax)) return false;
    if (state.filters.evMin !== null && (o.ev === null || o.ev < state.filters.evMin)) return false;
    if (state.filters.evMax !== null && (o.ev === null || o.ev > state.filters.evMax)) return false;
    if (state.filters.edgeMin !== null && (o.edge === null || o.edge * 100 < state.filters.edgeMin)) return false;
    if (state.filters.edgeMax !== null && (o.edge === null || o.edge * 100 > state.filters.edgeMax)) return false;

    const quick = state.filters.quick;
    if (quick.only_ev && !o.flags.ev_plus) return false;
    if (quick.only_value && !o.flags.value) return false;
    if (quick.only_strong && !o.flags.strong_signal) return false;
    if (quick.secondary && !o.flags.secondary_market) return false;
    if (quick.next_matches && !isFuture(o.hora)) return false;
    if (quick.signal_heavy && (toNumber(o.rank) === null || toNumber(o.rank) < 2)) return false;
    return true;
  }).sort((a, b) => (b.ev ?? -999) - (a.ev ?? -999) || (b.rank ?? b.score ?? -999) - (a.rank ?? a.score ?? -999) || (b.edge ?? -999) - (a.edge ?? -999));
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

function renderMatchRadar(radarRows) {
  const container = q("match-radar");
  container.innerHTML = "";
  if (!radarRows.length) return (container.innerHTML = '<p class="empty">No hay radar por partido.</p>');
  radarRows.forEach((row) => {
    const card = document.createElement("article");
    card.className = "match-card";
    const included = (row.oportunidades_incluidas || []).map(normalizeOpportunity);
    const excluded = (row.oportunidades_excluidas || []).map(normalizeOpportunity);
    card.innerHTML = `<div class="match-head"><strong>${row.equipos?.local || "Local"} vs ${row.equipos?.visitante || "Visitante"}</strong><span>${row.liga || "N/D"} · ${row.pais || "N/D"}</span><span>${dateLabel(row.hora)} · ${countdownLabel(row.hora)}</span><span>Familias: ${(row.familias_detectadas || []).join(", ") || "N/D"}</span></div>`;

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
    container.appendChild(card);
  });
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

  q("refresh-btn").addEventListener("click", refreshDashboard);
}

function renderFromState() {
  const filtered = applyFilters(state.opportunities);
  renderKpis(state.summary);
  renderOpportunityList("top-opportunities", filtered.slice(0, 50), "No hay oportunidades top para filtros activos.");
  renderOpportunityList("future-opportunities", filtered.filter((o) => o.flags.ev_plus && isFuture(o.hora)).slice(0, 50), "No hay EV+ próximos.");
  renderOpportunityList("secondary-opportunities", filtered.filter((o) => o.flags.secondary_market).slice(0, 50), "No hay secundarios con valor.");
  renderOpportunityList("family-1x2", filtered.filter((o) => o.family === "1x2").slice(0, 40), "Sin 1X2 para filtros activos.");
  renderOpportunityList("family-goals", filtered.filter((o) => o.family === "goals").slice(0, 40), "Sin goals para filtros activos.");
  renderOpportunityList("family-btts", filtered.filter((o) => o.family === "btts").slice(0, 40), "Sin BTTS para filtros activos.");
  renderOpportunityList("family-corners", filtered.filter((o) => o.family === "corners").slice(0, 40), "Sin corners para filtros activos.");
  renderOpportunityList("family-cards", filtered.filter((o) => o.family === "cards").slice(0, 40), "Sin cards para filtros activos.");
  renderOpportunityList("family-shots", filtered.filter((o) => o.family === "shots").slice(0, 40), "Sin shots para filtros activos.");

  renderLeagueExplorer(state.countryTree);
  renderMatchRadar(state.matchRadar);
}

function setRefreshState(mode, text) {
  const status = q("refresh-state");
  status.className = `badge status-badge ${mode}`;
  status.textContent = text;
}

async function fetchJson(path) {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
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
  fillSelect("filter-market", state.opportunities.flatMap((o) => [o.market, o.code]), state.filters.market);
}

async function refreshDashboard() {
  const btn = q("refresh-btn");
  btn.disabled = true;
  setRefreshState("loading", "Cargando");
  try {
    const payload = await fetchJson("/panel/dashboard?limit=3000");
    state.matches = payload.partidos || [];
    state.opportunities = (payload.top_opportunities || []).map(normalizeOpportunity);
    state.matchRadar = payload.match_radar || [];
    state.byFamily = payload.top_by_family || {};
    state.countryTree = payload.paises || [];
    state.summary = computeSummary(payload);
    populateSelectors();
    renderFromState();
    q("last-updated").textContent = `Última actualización: ${dateLabel(payload.generated_at || new Date().toISOString())}`;
    setRefreshState("ok", "Actualizado");
  } catch (e) {
    console.error(e);
    setRefreshState("error", "Error");
  } finally {
    btn.disabled = false;
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("DOMContentLoaded", () => {
    bindFilters();
    refreshDashboard();
  });
}
