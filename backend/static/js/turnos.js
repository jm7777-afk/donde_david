let turnosKnownReadyIds = new Set();
let turnosSoundEnabled = false;
let turnosFirstLoad = true;

function toggleTurnosSound() {
  turnosSoundEnabled = !turnosSoundEnabled;
  const btn = document.getElementById("turnos-sound-btn");
  if (btn) btn.textContent = turnosSoundEnabled ? "🔔 Sonido ON" : "🔇 Sonido OFF";
  if (turnosSoundEnabled) playTurnosChime();
}

function playTurnosChime() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(660, ctx.currentTime);
    osc.frequency.setValueAtTime(880, ctx.currentTime + 0.14);
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.36);
  } catch (err) {}
}

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
    const newlyReadyIds = new Set();
    let hasNewReady = false;
    readyList.forEach(item => {
      if (!turnosFirstLoad && !turnosKnownReadyIds.has(item.id)) {
        newlyReadyIds.add(item.id);
        hasNewReady = true;
      }
    });
    turnosKnownReadyIds = new Set(readyList.map(item => item.id));
    turnosFirstLoad = false;
    if (hasNewReady && turnosSoundEnabled) playTurnosChime();

    if (readyContainer) {
      readyContainer.innerHTML = readyList.length
        ? readyList.map(item => `
            <article class="turnos-ticket-card ready ${newlyReadyIds.has(item.id) ? "is-just-ready" : ""}">
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
