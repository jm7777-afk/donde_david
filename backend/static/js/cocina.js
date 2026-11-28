let kdsOrders = [];
let timerInterval = null;
let kdsModeFilter = "todos";
let kdsSearchTerm = "";
let kdsLayoutMode = "kanban";
let kdsSoundEnabled = true;
let kdsWakeLockSentinel = null;
const updatingKdsOrderIds = new Set();
const updatingKdsItemIds = new Set();

function escapeKdsHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[ch]);
}

document.addEventListener("DOMContentLoaded", () => {
  // Check auth
  if (!Auth.requireRole("cocina")) return;

  loadKDSOrders();

  // Listen to WebSocket events
  new WSClient((event, data) => {
    if (event === "NUEVO_PEDIDO" || event === "PAGO_CONFIRMADO" || (event === "PAGO_VALIDADO" && data.aprobado !== false)) {
      playChimeSound();
      notifyHighPriority({
        area: "COCINA",
        title: "Nueva comanda para preparar",
        message: `Pedido #${data.id || data.pedido_id || ""} · ${data.numero_mesa || "Caja"}.`,
        level: "critical",
        tag: `cocina-new-${data.id || data.pedido_id || ""}`,
      });
      loadKDSOrders();
    } else if (event === "CAMBIO_ESTADO_PEDIDO") {
      if (data.nuevo_estado === "CANCELADO") {
        notifyHighPriority({
          area: "COCINA",
          title: "Comanda cancelada",
          message: `Pedido #${data.pedido_id || ""} fue cancelado.`,
          level: "high",
          tag: `cocina-cancel-${data.pedido_id || ""}`,
        });
      }
      loadKDSOrders();
    }
  });

  // Start live timers update every 5 seconds
  timerInterval = setInterval(renderKDSOrders, 5000);
});

async function loadKDSOrders() {
  try {
    const params = new URLSearchParams();
    if (kdsModeFilter !== "todos") params.set("tipo", kdsModeFilter);
    const res = await fetch(`/api/v1/cocina/pedidos?${params}`, {
      headers: Auth.getHeaders()
    });
    if (!res.ok) throw new Error("Error al cargar pedidos de cocina");
    kdsOrders = await res.json();
    renderKDSOrders();
  } catch (err) {
    console.error(err);
    showToast(err.message, "danger");
  }
}

function renderKDSOrders() {
  const container = document.getElementById("kds-grid");
  if (!container) return;

  const searchTerm = kdsSearchTerm.trim().toLocaleLowerCase();
  const visibleOrders = kdsOrders.filter(order => {
    if (!searchTerm) return true;
    return String(order.id).includes(searchTerm)
      || String(order.numero_mesa || "").toLocaleLowerCase().includes(searchTerm)
      || order.detalles.some(detail => String(detail.producto?.nombre || "").toLocaleLowerCase().includes(searchTerm));
  });
  const countEl = document.getElementById("kds-order-count");
  if (countEl) {
    countEl.innerText = `Comandas visibles: ${visibleOrders.length} / ${kdsOrders.length}`;
  }

  const alldayEl = document.getElementById("kds-allday-summary");
  if (alldayEl) {
    const countsByItem = new Map();
    visibleOrders.filter(o => o.estado !== "LISTO").forEach(o => {
      (o.detalles || []).forEach(d => {
        if (d.estado === "LISTO") return;
        const name = d.producto?.nombre || "Producto";
        countsByItem.set(name, (countsByItem.get(name) || 0) + (Number(d.cantidad) || 0));
      });
    });
    if (countsByItem.size) {
      alldayEl.hidden = false;
      alldayEl.innerHTML = `<strong style="color:var(--gold-accent);font-size:0.8rem;">🔥 RESUMEN EN COLA:</strong>`
        + Array.from(countsByItem.entries())
          .sort((a, b) => b[1] - a[1])
          .map(([name, qty]) => `<span class="kds-allday-chip">${qty}× ${escapeKdsHtml(name)}</span>`)
          .join("");
    } else {
      alldayEl.hidden = true;
      alldayEl.innerHTML = "";
    }
  }

  if (visibleOrders.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 4rem; color: var(--color-text-secondary);">
        <span style="font-size: 3.5rem;">✨</span>
        <h2 style="margin-top: 1rem; color: #FFFFFF; font-weight: 800;">${kdsOrders.length ? "No hay resultados para este filtro" : "No hay comandas pendientes"}</h2>
        <p style="color: var(--color-text-secondary);">${kdsOrders.length ? "Prueba otra modalidad o búsqueda." : "¡Excelente trabajo! La cocina está al día."}</p>
      </div>
    `;
    return;
  }

  // Clasificación en 3 columnas KDS
  const pendientes = visibleOrders.filter(o => o.estado === "PENDIENTE" || o.estado === "COBRADO");
  const preparando = visibleOrders.filter(o => o.estado === "EN_PREPARACION");
  const listos = visibleOrders.filter(o => o.estado === "LISTO");

  function buildColumnHtml(title, icon, ordersList, bgBadge, nextStatus, nextBtnLabel, btnClass) {
    let orderCardsHtml = "";
    if (ordersList.length === 0) {
      orderCardsHtml = `<div style="text-align: center; padding: 2rem; color: var(--color-text-secondary); font-size: 0.85rem; border: 1px dashed var(--color-border); border-radius: var(--radius-sm);">Sin comandas</div>`;
    } else {
      ordersList.forEach(order => {
        const elapsedMinutes = getElapsedMinutes(order.fecha_creacion);
        const isUrgent = elapsedMinutes >= 15;
        const slaClass = isUrgent ? "timer-badge timer-urgent" : elapsedMinutes >= 8 ? "timer-badge sla-warn" : "timer-badge sla-ok";
        const urgentBorder = isUrgent ? 'urgent' : '';
        const modeRaw = String(order.tipo || "mesa").toLowerCase();
        const modeTag = modeRaw === "delivery" ? "🛵 Delivery" : modeRaw === "llevar" ? "🛍️ Para llevar" : "🍽️ Mesa";

        let itemsHtml = "";
        order.detalles.forEach(d => {
          let customText = "";
          // Muestra de Ingredientes Base del Producto
          if (d.producto && d.producto.ingredientes_json) {
            try {
              const ingList = typeof d.producto.ingredientes_json === 'string' 
                ? JSON.parse(d.producto.ingredientes_json) 
                : d.producto.ingredientes_json;
              if (Array.isArray(ingList) && ingList.length > 0) {
                customText += `<br><small style="color: #94A3B8; font-size: 0.78rem;">🥩 <em>Ingredientes: ${ingList.map(escapeKdsHtml).join(', ')}</em></small>`;
              } else if (typeof ingList === 'string' && ingList.trim()) {
                customText += `<br><small style="color: #94A3B8; font-size: 0.78rem;">🥩 <em>Ingredientes: ${escapeKdsHtml(ingList)}</em></small>`;
              }
            } catch(e) {
              if (typeof d.producto.ingredientes_json === 'string' && d.producto.ingredientes_json.trim()) {
                customText += `<br><small style="color: #94A3B8; font-size: 0.78rem;">🥩 <em>Ingredientes: ${escapeKdsHtml(d.producto.ingredientes_json)}</em></small>`;
              }
            }
          }
          if (d.personalizaciones) {
            try {
              const parsed = JSON.parse(d.personalizaciones);
              if (parsed.opciones && parsed.opciones.length > 0) {
                customText += `<br><small style="color: var(--brand-orange); font-weight: 800;">✨ Modificaciones: ${parsed.opciones.map(escapeKdsHtml).join(', ')}</small>`;
              }
            } catch(e) {}
          }
          if (d.observaciones) {
            customText += `<br><small style="color: var(--brand-red); font-weight: 800;">⚠️ Nota Cliente: ${escapeKdsHtml(d.observaciones)}</small>`;
          }

          itemsHtml += `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.45rem 0; border-bottom: 1px dashed rgba(226, 232, 240, 0.15);">
              <div>
                <strong style="color: #FFFFFF; font-size: 0.95rem;">${Number(d.cantidad) || 0}x ${escapeKdsHtml(d.producto ? d.producto.nombre : 'Producto')}</strong>
                ${customText}
              </div>
              <button class="btn btn-outline" style="min-height: 32px; padding: 0.2rem 0.5rem; font-size: 0.72rem;" onclick="updateItemStatus(${Number(d.id)}, '${d.estado === 'LISTO' ? 'PENDIENTE' : 'LISTO'}')">
                ${d.estado === 'LISTO' ? '✅ Listo' : '⏳ Pendiente'}
              </button>
            </div>
          `;
        });

        orderCardsHtml += `
          <div class="kds-card status-${escapeKdsHtml(order.estado)} ${urgentBorder}" data-kds-mode="${escapeKdsHtml(modeRaw)}" style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.4rem;">
              <div>
                <h3 style="font-size: 1.15rem; font-weight: 800; color: #FFFFFF; margin: 0 0 0.25rem;">#${Number(order.id)} - ${escapeKdsHtml(order.numero_mesa)}</h3>
                <span class="kds-mode-pill">${modeTag}</span>
              </div>
              <div style="display:flex;align-items:center;gap:0.35rem;">
                <button type="button" class="btn btn-outline" style="padding:0.2rem 0.45rem;font-size:0.74rem;" onclick="printKdsComanda(${Number(order.id)})" title="Imprimir comanda">🖨️</button>
                <span class="${slaClass}" aria-label="${isUrgent ? "Comanda urgente" : "Tiempo transcurrido"}">⏱️ ${isUrgent ? "URGENTE · " : ""}${elapsedMinutes} min</span>
              </div>
            </div>

            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: var(--radius-sm); margin: 0.5rem 0;">
              ${itemsHtml}
            </div>

            ${nextStatus ? `
              <button class="btn ${btnClass}" style="width: 100%; margin-top: auto;" onclick="updateOrderStatus(${order.id}, '${nextStatus}')">
                ${nextBtnLabel}
              </button>
            ` : `
              <div style="text-align: center; font-size: 0.8rem; color: var(--color-success); font-weight: 800; padding: 0.4rem; background: rgba(34, 197, 94, 0.1); border-radius: 8px;">
                ${order.tipo === "llevar" ? "📦 LISTO PARA RETIRAR · Validación en caja" : order.tipo === "delivery" ? "🛵 LISTO PARA DESPACHO" : "✅ LISTO · ESPERANDO MESERO"}
              </div>
            `}
          </div>
        `;
      });
    }

    return `
      <div style="background: rgba(7, 26, 61, 0.6); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 1rem; display: flex; flex-direction: column;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 2px solid var(--color-border); padding-bottom: 0.6rem;">
          <h2 style="font-size: 1.1rem; font-weight: 900; color: #FFFFFF; display: flex; align-items: center; gap: 0.5rem;">
            <span>${icon}</span> <span>${title}</span>
          </h2>
          <span style="background: ${bgBadge}; color: #000; font-weight: 900; font-size: 0.8rem; padding: 0.2rem 0.65rem; border-radius: 20px;">${ordersList.length}</span>
        </div>
        <div>
          ${orderCardsHtml}
        </div>
      </div>
    `;
  }

  if (kdsLayoutMode === "compact") {
    const allCardsHtml = [
      buildColumnHtml("RECIBIDOS", "📥", pendientes, "var(--color-yellow)", "EN_PREPARACION", "🔥 INICIAR PREPARACIÓN", "btn-cta"),
      buildColumnHtml("PREPARANDO", "👨‍🍳", preparando, "var(--color-primary)", "LISTO", "✅ MARCAR PEDIDO LISTO", "btn-success"),
      buildColumnHtml("LISTOS", "🏁", listos, "var(--color-success)", null, null, null)
    ].join("");
    container.innerHTML = `<div class="kds-compact-grid">${allCardsHtml}</div>`;
    return;
  }

  const htmlHtml = `
    <div class="kds-columns-layout" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.25rem;">
      ${buildColumnHtml("RECIBIDOS", "📥", pendientes, "var(--color-yellow)", "EN_PREPARACION", "🔥 INICIAR PREPARACIÓN", "btn-cta")}
      ${buildColumnHtml("PREPARANDO", "👨‍🍳", preparando, "var(--color-primary)", "LISTO", "✅ MARCAR PEDIDO LISTO", "btn-success")}
      ${buildColumnHtml("LISTOS", "🏁", listos, "var(--color-success)", null, null, null)}
    </div>
  `;

  container.innerHTML = htmlHtml;
}

function setKDSModeFilter(value) {
  kdsModeFilter = value;
  loadKDSOrders();
}

function setKDSSearch(value) {
  kdsSearchTerm = value;
  renderKDSOrders();
}

function toggleKDSLayout() {
  kdsLayoutMode = kdsLayoutMode === "kanban" ? "compact" : "kanban";
  const btn = document.getElementById("kds-layout-btn");
  if (btn) btn.textContent = kdsLayoutMode === "kanban" ? "🧱 Kanban" : "📋 Compacta";
  renderKDSOrders();
}

function toggleKDSSound() {
  kdsSoundEnabled = !kdsSoundEnabled;
  const btn = document.getElementById("kds-sound-btn");
  if (btn) btn.textContent = kdsSoundEnabled ? "🔊 Alarma ON" : "🔇 Silencio";
  if (kdsSoundEnabled) playChimeSound();
}

async function toggleKDSFullscreenWake() {
  const btn = document.getElementById("kds-wakelock-btn");
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }
  } catch (err) {}
  try {
    if ("wakeLock" in navigator && !kdsWakeLockSentinel) {
      kdsWakeLockSentinel = await navigator.wakeLock.request("screen");
    }
  } catch (err) {}
  if (btn) btn.textContent = document.fullscreenElement ? "🗗 Salir Pantalla" : "🖥️ Pantalla";
}

function printKdsComanda(orderId) {
  const order = kdsOrders.find(o => Number(o.id) === Number(orderId));
  if (!order || typeof window.printThermalDocument !== "function") return;
  const rows = (order.detalles || []).map(d => `
    <div class="dd-thermal-row"><span><strong>${Number(d.cantidad) || 1}x</strong> ${escapeKdsHtml(d.producto?.nombre || "Producto")}</span></div>
    ${d.observaciones ? `<div style="font-size:10px;">Nota: ${escapeKdsHtml(d.observaciones)}</div>` : ""}
  `).join("");
  window.printThermalDocument(
    `<div class="dd-thermal-row"><span>Comanda #${order.id}</span><span>${escapeKdsHtml(order.numero_mesa)}</span></div><hr>${rows}`,
    `COMANDA COCINA #${order.id}`
  );
}

function getElapsedMinutes(dateStr) {
  if (!dateStr) return 0;
  const created = new Date(dateStr);
  const now = new Date();
  const diffMs = now - created;
  return Math.max(0, Math.floor(diffMs / 60000));
}

async function updateOrderStatus(orderId, newStatus) {
  if (updatingKdsOrderIds.has(orderId)) return;
  updatingKdsOrderIds.add(orderId);
  try {
    const res = await fetch(`/api/v1/cocina/pedidos/${orderId}/estado?estado=${encodeURIComponent(newStatus)}`, {
      method: "PUT",
      headers: Auth.getHeaders()
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Error al actualizar el estado");
    }
    showToast(`Comanda #${orderId} actualizada a ${newStatus}`, "success");
    await loadKDSOrders();
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    updatingKdsOrderIds.delete(orderId);
  }
}

async function updateItemStatus(itemId, newStatus) {
  if (updatingKdsItemIds.has(itemId)) return;
  updatingKdsItemIds.add(itemId);
  try {
    const res = await fetch(`/api/v1/cocina/detalles/${itemId}/estado?estado=${encodeURIComponent(newStatus)}`, {
      method: "PUT",
      headers: Auth.getHeaders()
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Error al actualizar estado del ítem");
    }
    await loadKDSOrders();
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    updatingKdsItemIds.delete(itemId);
  }
}

// Synthesize audio chime alert for new incoming orders
function playChimeSound() {
  if (!kdsSoundEnabled) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.setValueAtTime(880, ctx.currentTime + 0.15); // A5

    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch (e) {
    console.log("Audio notice blocked or unsupported.");
  }
}

function setKDSGridScale(scaleClass) {
  const grid = document.getElementById("kds-grid");
  if (!grid) return;
  grid.classList.remove("scale-sm", "scale-md", "scale-lg");
  grid.classList.add(scaleClass);
  showToast(`📐 Escala de pantalla KDS fijada`, "info");
}
