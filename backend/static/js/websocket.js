class WSClient {
  constructor(onEventCallback) {
    this.onEventCallback = onEventCallback;
    this.socket = null;
    this.reconnectTimer = null;
    this.connect();
  }

  connect() {
    const token = localStorage.getItem("token");
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    this.socket = new WebSocket(wsUrl);

    this.socket.onopen = () => {
      console.log("🟢 Conexión WebSocket establecida con el servidor.");
      this.socket.send(JSON.stringify({ token }));
    };

    this.socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (this.onEventCallback) {
          this.onEventCallback(payload.event, payload.data || {});
        }
      } catch (e) {
        console.error("Error al procesar mensaje WebSocket:", e);
      }
    };

    this.socket.onclose = (event) => {
      if ([4401, 4403, 4408].includes(event.code)) {
        console.warn("WebSocket rechazado: inicia sesión con una cuenta de personal.");
        return;
      }
      console.warn("🔴 Conexión WebSocket cerrada. Reintentando en 3 segundos...");
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };

    this.socket.onerror = (err) => {
      console.error("Error WebSocket:", err);
    };
  }
}

function escapeNotificationHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[ch]);
}

function showToast(message, type = "info", durationMs = 4000, isHighPriority = false) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }

  const iconMap = {
    success: "✅",
    danger: "🚨",
    warning: "⚠️",
    info: "🔔"
  };

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}${isHighPriority ? " toast-priority" : ""}`;
  toast.innerHTML = `
    <div style="display:flex; align-items:center; gap:0.6rem;">
      <span style="font-size:1.1rem;">${iconMap[type] || "🔔"}</span>
      <span style="font-weight:700;">${escapeNotificationHtml(message)}</span>
    </div>
    <span style="cursor:pointer; font-weight:900; opacity:0.7; font-size:1.2rem; padding-left:0.5rem;" onclick="this.parentElement.remove()">&times;</span>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-10px)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => { if (toast.parentNode) toast.remove(); }, 300);
    }
  }, durationMs);
}

const _priorityAlertRecentTags = new Map();
let _priorityAlertSeq = 0;

function playOperationalAlertSound(level = "high") {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const tones = level === "critical" ? [880, 1174.66, 1318.51] : [783.99, 987.77];
    tones.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = level === "critical" ? "triangle" : "sine";
      const start = ctx.currentTime + idx * 0.11;
      osc.frequency.setValueAtTime(freq, start);
      gain.gain.setValueAtTime(0.24, start);
      gain.gain.exponentialRampToValueAtTime(0.001, start + 0.25);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(start);
      osc.stop(start + 0.26);
    });
    if (navigator.vibrate) {
      navigator.vibrate(level === "critical" ? [200, 80, 200] : [140]);
    }
  } catch (err) {
    console.debug("Audio de notificación no disponible:", err);
  }
}

function ensurePriorityAlertsMount() {
  let region = document.getElementById("priority-alerts-region");
  if (region) return region;
  region = document.createElement("section");
  region.id = "priority-alerts-region";
  region.className = "priority-alerts-region";
  region.setAttribute("role", "region");
  region.setAttribute("aria-label", "Notificaciones de alta prioridad");
  region.innerHTML = `<div id="priority-alerts-list"></div>`;

  const header = document.getElementById("app-header");
  if (header && header.parentNode) {
    header.parentNode.insertBefore(region, header.nextSibling);
  } else {
    document.body.insertBefore(region, document.body.firstChild);
  }
  return region;
}

function acknowledgePriorityAlert(alertId) {
  const el = document.getElementById(alertId);
  if (el) el.remove();
}

function notifyHighPriority({
  area = "SISTEMA",
  title = "Alerta operativa",
  message = "",
  level = "high",
  tag = null
} = {}) {
  const now = Date.now();
  if (tag) {
    const prevTs = _priorityAlertRecentTags.get(tag) || 0;
    if (now - prevTs < 1500) return;
    _priorityAlertRecentTags.set(tag, now);
  }

  ensurePriorityAlertsMount();
  const list = document.getElementById("priority-alerts-list");
  if (!list) return;

  playOperationalAlertSound(level);
  showToast(`[${area}] ${title}: ${message}`, level === "critical" ? "danger" : "warning", 7000, true);

  const alertId = `priority-alert-${++_priorityAlertSeq}`;
  const card = document.createElement("div");
  card.id = alertId;
  card.className = `priority-alert-card${level === "critical" ? " is-critical" : ""}`;
  card.setAttribute("role", "alert");
  card.setAttribute("aria-live", "assertive");
  const timeText = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  card.innerHTML = `
    <div>
      <div>
        <span class="priority-alert-badge">${escapeNotificationHtml(area)} · ALTA PRIORIDAD</span>
        <strong>${escapeNotificationHtml(title)}</strong>
        <small style="opacity:0.75;margin-left:0.4rem;">${escapeNotificationHtml(timeText)}</small>
      </div>
      <div style="font-size:0.86rem;margin-top:0.2rem;opacity:0.95;">${escapeNotificationHtml(message)}</div>
    </div>
    <div class="priority-alert-actions">
      <button type="button" class="priority-alert-ack-btn" onclick="acknowledgePriorityAlert('${alertId}')">✓ Entendido</button>
    </div>
  `;
  list.insertBefore(card, list.firstChild);
  while (list.children.length > 5) {
    list.removeChild(list.lastChild);
  }

  if (typeof Notification !== "undefined" && Notification.permission === "granted" && document.hidden) {
    try {
      new Notification(`[${area}] ${title}`, { body: message, tag: tag || alertId });
    } catch (e) {}
  }
}
