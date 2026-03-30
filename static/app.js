async function fetchJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Error ${response.status} en ${path}`);
  }
  return response.json();
}

function render(id, data) {
  const node = document.getElementById(id);
  node.textContent = JSON.stringify(data, null, 2);
}

async function initPanel() {
  try {
    const [resumen, apuestas, partidos] = await Promise.all([
      fetchJson("/panel/resumen"),
      fetchJson("/panel/apuestas-fuertes"),
      fetchJson("/panel/partidos"),
    ]);

    render("resumen", resumen);
    render("apuestas", apuestas);
    render("partidos", partidos);
  } catch (error) {
    render("resumen", { error: String(error) });
    render("apuestas", { error: String(error) });
    render("partidos", { error: String(error) });
  }
}

initPanel();
