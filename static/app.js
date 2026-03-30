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

function inferGroup(code = "") {
  if (code.includes("CORNERS")) return "Corners";
  if (code.includes("CARDS")) return "Tarjetas";
  if (code.includes("SHOTS") || code.includes("SOT")) return "Tiros";
  if (code.includes("HANDICAP")) return "Handicap";
  if (code.includes("PROP")) return "Props";
  return "Mercado";
}

function toOpportunity(raw, match, telemetryByCode = {}) {
  if (!raw || typeof raw !== "object") return null;
  const code = String(raw.code || raw.codigo || raw.market_code || raw.marketCode || raw.mercado_codigo || raw.mercado || "N/A");
  const telemetry = telemetryByCode[code] || telemetryByCode[code.toLowerCase()] || raw.telemetry || raw.telemetria || null;

  const modelProb = normalizePercent(raw.probabilidad_modelo ?? raw.model_prob ?? raw.modelProbability ?? raw.probabilidad ?? raw.prob_apuesta ?? raw.score ?? raw.probabilidad_modelo_pct);
  const impliedProb = normalizePercent(raw.probabilidad_implicita ?? raw.implied_prob ?? raw.impliedProbability ?? raw.fair_market_prob);
  const edge = normalizePercent(raw.edge ?? raw.edge_pct ?? raw.edge_percent);
  const ev = toNumber(raw.ev ?? raw.expected_value ?? raw.valor_esperado ?? raw.ev_principal);
  const rank = toNumber(raw.rank ?? raw.ranking ?? raw.score_rank ?? raw.rank_score ?? raw.score);
  const stake = toNumber(raw.stake_recomendado ?? raw.stake_sugerido_unidades ?? raw.stake_units ?? raw.stake);

  const includeReason = raw.razon_inclusion || raw.include_reason || raw.inclusion_reason || raw.signal_label || raw.motivo || "Sin motivo reportado";
  const discardReason = raw.razon_descarte || raw.discard_reason || raw.exclusion_reason || null;

  const valueFlag = raw.value ?? raw.es_value_bet ?? raw.is_value ?? raw.oportunidad_detectada;

  return {
    matchId: match.fixture_id || match.id,
    partido: `${match.local || "Local"} vs ${match.visitante || "Visitante"}`,
    hora: match.hora || null,
    liga: match.liga || "",
    code,
    group: raw.group || raw.market_group || inferGroup(code),
    market: raw.mercado || raw.market_name || code,
    jugada: raw.jugada || raw.pick || raw.selection || match.apuesta_principal || "N/D",
    cuota: toNumber(raw.cuota ?? raw.odds ?? raw.price ?? raw.cuota_principal),
    modelProb,
    impliedProb,
    edge,
    ev,
    rank,
    stake,
    value: Boolean(valueFlag),
    includeReason,
    discardReason,
    telemetry,
    signals: raw.senales || raw.signals || raw.signal_components || null,
  };
}

function flattenOpportunities(match) {
  const telemetry = match.telemetria_mercados || match.market_telemetry || {};
  const sources = [];

  if (Array.isArray(match.oportunidades_ev)) sources.push(...match.oportunidades_ev);
  if (Array.isArray(match.top_opportunities)) sources.push(...match.top_opportunities);

  if (!sources.length && match.ev_principal !== null && match.ev_principal !== undefined) {
    sources.push({
      code: match.mercado_principal,
      mercado: match.mercado_principal,
      jugada: match.apuesta_principal,
      cuota: match.cuota_principal,
      model_prob: match.prob_apuesta,
      implied_prob: match.probabilidad_implicita_principal,
      edge: match.edge_principal,
      ev: match.ev_principal,
      stake_sugerido_unidades: match.stake_sugerido_unidades,
      score: match.confianza,
      value: match.es_value_bet,
      inclusion_reason: "ev_principal",
      signal_components: match.apuestas_fuertes,
    });
  }

  if (!sources.length && Array.isArray(match.apuestas_fuertes)) {
    // Solo fallback cuando no hay oportunidades_ev/top_opportunities/ev_principal.
    sources.push(...match.apuestas_fuertes);
  }

  return sources
    .map((raw) => toOpportunity(raw, match, telemetry))
    .filter(Boolean)
    .sort((a, b) => {
      const evA = a.ev ?? -999;
      const evB = b.ev ?? -999;
      if (evB !== evA) return evB - evA;
      const rankA = a.rank ?? -999;
      const rankB = b.rank ?? -999;
      return rankB - rankA;
    });
}

function createOpportunityCard(opp) {
  const tpl = document.getElementById("opportunity-template");
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".market-code").textContent = opp.code;
  node.querySelector(".market-group").textContent = `${opp.group} · ${opp.partido}`;
  node.querySelector(".play").textContent = `${opp.market} → ${opp.jugada}`;

  node.querySelector(".meta").innerHTML = [
    metricText("Cuota", opp.cuota?.toFixed?.(2) ?? opp.cuota),
    metricText("Prob. modelo", opp.modelProb !== null ? opp.modelProb.toFixed(2) : null, "%"),
    metricText("Prob. implícita", opp.impliedProb !== null ? opp.impliedProb.toFixed(2) : null, "%"),
  ].join(" · ");

  node.querySelector(".metrics").innerHTML = [
    metricText("Edge", opp.edge !== null ? opp.edge.toFixed(2) : null, "%"),
    metricText("EV", opp.ev !== null ? opp.ev.toFixed(4) : null),
    metricText("Rank", opp.rank !== null ? opp.rank.toFixed(2) : null),
    metricText("Stake", opp.stake !== null ? opp.stake.toFixed(2) : null, "u"),
    `<span class="badge ${opp.value ? "value" : "non-value"}">${opp.value ? "Value" : "No value"}</span>`,
  ].join(" · ");

  const discard = opp.discardReason ? ` · descarte: ${opp.discardReason}` : "";
  node.querySelector(".reason").textContent = `Inclusión: ${opp.includeReason}${discard}`;

  return node;
}

function renderOpportunityList(containerId, opportunities, emptyText) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  if (!opportunities.length) {
    container.innerHTML = `<p class="empty">${emptyText}</p>`;
    return;
  }
  opportunities.forEach((opp) => container.appendChild(createOpportunityCard(opp)));
}

function renderMatchRadar(matches, opportunitiesByMatch) {
  const container = document.getElementById("match-radar");
  container.innerHTML = "";

  if (!matches.length) {
    container.innerHTML = '<p class="empty">No hay partidos disponibles.</p>';
    return;
  }

  for (const match of matches) {
    const opps = opportunitiesByMatch.get(match.id || match.fixture_id) || [];
    const card = document.createElement("article");
    card.className = "match-card";

    const head = document.createElement("div");
    head.className = "match-head";
    head.innerHTML = `
      <strong>${match.local || "Local"} vs ${match.visitante || "Visitante"}</strong>
      <span>${match.liga || ""} · ${match.hora || "sin hora"}</span>
      <span>Oportunidades: ${opps.length}</span>
    `;

    const grid = document.createElement("div");
    grid.className = "match-opportunities";
    opps.forEach((opp) => grid.appendChild(createOpportunityCard(opp)));
    if (!opps.length) grid.innerHTML = '<p class="empty">Sin oportunidades cuantitativas reportadas.</p>';

    const details = document.createElement("details");
    details.innerHTML = `
      <summary>Detalle de cálculo y trazabilidad</summary>
      <pre>${JSON.stringify({
        top_opportunities: match.top_opportunities || [],
        oportunidades_ev: match.oportunidades_ev || [],
        market_telemetry: match.market_telemetry || match.telemetria_mercados || {},
        apuestas_fuertes: match.apuestas_fuertes || [],
      }, null, 2)}</pre>
    `;

    card.append(head, grid, details);
    container.appendChild(card);
  }
}

function isFuture(iso) {
  if (!iso) return false;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return false;
  return t >= Date.now();
}

function secondaryMarket(code = "") {
  return /CORNERS|CARDS|SHOTS|SOT|HANDICAP|PROP/.test(code);
}

async function fetchJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`Error ${response.status} en ${path}`);
  return response.json();
}

async function loadDashboardData() {
  const [partidosRes, resumenRes] = await Promise.all([
    fetchJson("/panel/partidos?limit=1000"),
    fetchJson("/panel/resumen"),
  ]);
  const matches = Array.isArray(partidosRes.partidos) ? partidosRes.partidos : [];
  return { matches, resumen: resumenRes };
}

function renderDashboard(payload) {
  const { matches, resumen } = payload;
  const allOpps = [];
  const map = new Map();

  for (const match of matches) {
    const opps = flattenOpportunities(match);
    map.set(match.id || match.fixture_id, opps);
    allOpps.push(...opps);
  }

  allOpps.sort((a, b) => (b.ev ?? -999) - (a.ev ?? -999) || (b.rank ?? -999) - (a.rank ?? -999));

  renderOpportunityList("top-opportunities", allOpps.slice(0, 30), "No hay oportunidades EV+ para hoy.");
  renderOpportunityList("future-opportunities", allOpps.filter((o) => isFuture(o.hora)).slice(0, 30), "No hay oportunidades futuras EV+.");
  renderOpportunityList("secondary-opportunities", allOpps.filter((o) => secondaryMarket(o.code)).slice(0, 30), "No hay mercados secundarios con EV+ disponibles.");
  renderMatchRadar(matches, map);

  document.getElementById("status").textContent = `Partidos: ${matches.length} · Señales: ${resumen?.senales ?? "N/D"} · Value bets: ${resumen?.valueBets ?? resumen?.value_bets ?? "N/D"}`;
}

async function initPanel() {
  const status = document.getElementById("status");
  try {
    const payload = await loadDashboardData();
    renderDashboard(payload);
  } catch (error) {
    status.textContent = `Error cargando panel: ${String(error)}`;
  }
}

if (typeof window !== "undefined") {
  initPanel();
}

if (typeof module !== "undefined") {
  module.exports = { toOpportunity, flattenOpportunities, renderDashboard, secondaryMarket };
}
