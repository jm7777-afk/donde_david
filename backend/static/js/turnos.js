function escapeTurnosHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function updateTurnosClock() {
  const clockEl = document.getElementById("turnos-clock");
  if (clockEl) {
    clockEl.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
}

async function loadTurnosBoard() {
  try {
    const res = await fetch("/api/v1/cliente/turnos");
    if (!res.ok) return;
    const data = await res.json();
    const prepList = Array.isArray(data.preparando) ? data.preparando : [];
    const readyList = Array.isArray(data.listos) ? data.listos : [];

    const prepCount = document.getElementById("turnos-prep-count");
    const readyCount = document.getElementById("turnos-ready-count");
    if (prepCount) prepCount.textContent = String(prepList.length);
    if (readyCount) readyCount.textContent = String(readyList.length);

    const prepContainer = document.getElementById("turnos-prep-list");
    if (prepContainer) {
      prepContainer.innerHTML = prepList.length
        ? prepList.map(item => `
            <article class="turnos-ticket-card">
              <span class="turnos-ticket-code">${escapeTurnosHtml(item.codigo_visual)}</span>
              <span class="turnos-ticket-client">${escapeTurnosHtml(item.cliente)}</span>
            </article>
          `).join("")
        : `<div class="turnos-empty-msg">Sin pedidos en preparación ahora mismo.</div>`;
    }

    const readyContainer = document.getElementById("turnos-ready-list");
    if (readyContainer) {
      readyContainer.innerHTML = readyList.length
        ? readyList.map(item => `
            <article class="turnos-ticket-card ready">
              <span class="turnos-ticket-code">${escapeTurnosHtml(item.codigo_visual)}</span>
              <span class="turnos-ticket-client">${escapeTurnosHtml(item.cliente)}</span>
            </article>
          `).join("")
        : `<div class="turnos-empty-msg">Los pedidos listos aparecerán aquí automáticamente.</div>`;
    }
  } catch (err) {
    console.warn("Error actualizando tablero de turnos:", err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  updateTurnosClock();
  loadTurnosBoard();
  setInterval(updateTurnosClock, 1000);
  setInterval(loadTurnosBoard, 4000);
});
