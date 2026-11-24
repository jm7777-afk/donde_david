let meseroMesas = [];
let meseroPedidos = [];
let meseroSolicitudes = [];
let selectedPedidoForSwap = null;
let tasaCambioBs = null;

function escapeMeseroHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

document.addEventListener("DOMContentLoaded", () => {
  if (!Auth.requireRole("mesero")) return;

  loadConfigPublica();
  loadMeseroData();

  new WSClient((event, data) => {
    if (event === "NUEVO_PEDIDO" || event === "CAMBIO_ESTADO_PEDIDO" || event === "PAGO_CONFIRMADO"
        || event === "SOLICITUD_MESA" || event === "SOLICITUD_MESA_ACTUALIZADA"
        || event === "MESA_ACTUALIZADA") {
      loadMeseroData();
    }
  });
});

async function loadConfigPublica() {
  try {
    const res = await fetch("/api/v1/cliente/configuraciones-publicas");
    if (!res.ok) throw new Error("No se pudo cargar la tasa de cambio.");
    const cfg = await res.json();
    const rate = Number(cfg.tasa_cambio_bs);
    tasaCambioBs = Number.isFinite(rate) && rate > 0 ? rate : null;
  } catch(error) {
    console.error("No se pudo cargar la tasa de cambio:", error);
  }
}

function formatPriceDual(usdAmount) {
  if (!Number.isFinite(tasaCambioBs) || tasaCambioBs <= 0) return `$${usdAmount.toFixed(2)}`;
  const bsAmount = (usdAmount * tasaCambioBs).toFixed(2);
  return `$${usdAmount.toFixed(2)} (Bs. ${bsAmount})`;
}

async function loadMeseroData() {
  await Promise.all([loadMesas(), loadPedidosActivos(), loadSolicitudesMesa()]);
}

async function loadMesas() {
  try {
    const res = await fetch("/api/v1/mesero/mesas", { headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("No se pudieron cargar las mesas.");
    meseroMesas = await res.json();
    renderMesas();
  } catch (err) {
    console.error("Error al cargar mesas:", err);
    showToast(err.message, "danger");
  }
}

function renderMesas() {
  const container = document.getElementById("mesero-mesas-grid");
  let html = "";
  meseroMesas.forEach(m => {
    html += `
      <div class="mesa-card-mesero ${m.estado}">
        <strong style="font-size: 1.2rem; color: #fff;">Mesa #${m.numero_mesa}</strong>
        <div style="font-size: 0.8rem; color: var(--text-muted); margin: 0.3rem 0;">${m.cliente_actual || 'Disponible'}</div>
        <span class="badge" style="background: ${m.estado === 'OCUPADA' ? 'var(--neon-red)' : m.estado === 'LIBRE' ? 'var(--neon-green)' : 'var(--gold-accent)'}; color: ${m.estado === 'PENDIENTE_LIMPIEZA' || m.estado === 'EN_LIMPIEZA' ? '#000' : '#fff'}; font-size: 0.7rem; padding: 0.2rem 0.5rem; border-radius: 6px;">
          ${escapeMeseroHtml(m.estado)}
        </span>
        ${m.estado === 'OCUPADA' ? `
          <div style="font-size: 0.78rem; color: var(--gold-accent); margin-top: 0.55rem;">
            ${m.tiempo_ocupacion_min || 0} min · ${m.pedidos_activos || 0} pedido(s) activo(s)
          </div>
        ` : ''}
        ${m.solicitudes_pendientes ? `<div style="margin-top:.55rem;color:var(--color-yellow);font-weight:800">${m.solicitudes_pendientes} solicitud(es) pendiente(s)</div>` : ''}
        ${m.estado === "PENDIENTE_LIMPIEZA" ? `<button class="btn btn-cta" style="width:100%;margin-top:.75rem" onclick="actualizarLimpiezaMesa(${m.id}, 'INICIAR')">🧹 Iniciar limpieza</button>` : ""}
        ${m.estado === "EN_LIMPIEZA" ? `<button class="btn btn-success" style="width:100%;margin-top:.75rem" onclick="actualizarLimpiezaMesa(${m.id}, 'FINALIZAR')">✅ Marcar limpia y liberar</button>` : ""}
      </div>
    `;
  });
  container.innerHTML = html;
}

async function actualizarLimpiezaMesa(mesaId, accion) {
  try {
    const response = await fetch(`/api/v1/mesero/mesas/${mesaId}/limpieza`, {
      method: "PUT",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ accion })
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "No se pudo actualizar la limpieza de la mesa.");
    showToast(accion === "INICIAR" ? "Limpieza iniciada." : `Mesa #${body.numero_mesa} limpia y disponible.`, "success");
    await loadMeseroData();
  } catch (error) {
    showToast(error.message, "danger");
  }
}

async function loadSolicitudesMesa() {
  try {
    const response = await fetch("/api/v1/mesero/solicitudes", { headers: Auth.getHeaders() });
    if (!response.ok) throw new Error("No se pudieron cargar las solicitudes de mesa.");
    meseroSolicitudes = await response.json();
    renderSolicitudesMesa();
  } catch (error) {
    console.error("Error al cargar solicitudes de mesa:", error);
    showToast(error.message, "danger");
  }
}

function renderSolicitudesMesa() {
  const container = document.getElementById("mesero-solicitudes-list");
  if (!container) return;
  if (meseroSolicitudes.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted);margin:.25rem">No hay solicitudes pendientes.</p>`;
    return;
  }
  container.innerHTML = meseroSolicitudes.map(item => {
    const label = item.tipo === "SOLICITAR_CUENTA" ? "Solicita la cuenta" : "Llama al mesero";
    const created = item.fecha_creacion ? new Date(item.fecha_creacion).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
    return `<article style="border:1px solid var(--toon-border);border-radius:10px;padding:.85rem">
      <strong>Mesa #${item.mesa} · ${label}</strong>
      ${item.nota ? `<p>${escapeMeseroHtml(item.nota)}</p>` : ""}
      <small style="display:block;color:var(--text-muted);margin:.35rem 0">${created}</small>
      <button class="btn btn-cta" onclick="resolveTableRequest(${item.id}, 'ATENDIDA')">Marcar atendida</button>
      <button class="btn btn-outline" onclick="resolveTableRequest(${item.id}, 'CANCELADA')">Descartar</button>
    </article>`;
  }).join("");
}

async function resolveTableRequest(requestId, estado) {
  try {
    const response = await fetch(`/api/v1/mesero/solicitudes/${requestId}/estado`, {
      method: "PUT",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ estado })
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "No se pudo actualizar la solicitud.");
    await loadMeseroData();
  } catch (error) {
    showToast(error.message, "danger");
  }
}

async function loadPedidosActivos() {
  try {
    const res = await fetch("/api/v1/mesero/pedidos-activos", { headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("No se pudieron cargar los pedidos activos.");
    meseroPedidos = await res.json();
    renderPedidosActivos();
  } catch (err) {
    console.error("Error al cargar pedidos mesero:", err);
    showToast(err.message, "danger");
  }
}

function renderPedidosActivos() {
  const container = document.getElementById("mesero-pedidos-list");
  if (meseroPedidos.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); text-align: center; padding: 2rem; background: var(--toon-card); border-radius: var(--radius-md); grid-column: 1 / -1;">No hay pedidos pendientes de entrega en mesa.</div>`;
    return;
  }

  let html = "";
  meseroPedidos.forEach(p => {
    // Separa bebidas de comida
    const bebidas = [];
    const comidas = [];

    p.detalles.forEach(d => {
      const prodName = d.producto ? d.producto.nombre : '';
      const catName = (d.producto && d.producto.categoria) ? d.producto.categoria.nombre.toLowerCase() : '';
      
      if (catName.includes("bebida") || prodName.toLowerCase().includes("refresco") || prodName.toLowerCase().includes("jugo") || prodName.toLowerCase().includes("agua") || prodName.toLowerCase().includes("cerveza")) {
        bebidas.push(`${d.cantidad}x ${prodName}`);
      } else {
        comidas.push(`${d.cantidad}x ${prodName}`);
      }
    });

    const isListo = p.estado === "LISTO";
    const hasFreeTable = meseroMesas.some(table => table.estado === "LIBRE");
    const elapsedMinutes = p.fecha_creacion
      ? Math.max(0, Math.floor((Date.now() - new Date(p.fecha_creacion).getTime()) / 60000))
      : 0;

    html += `
      <div style="background: var(--toon-card); border: 1px solid ${isListo ? 'var(--neon-green)' : 'var(--toon-border)'}; border-radius: var(--radius-md); padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="font-size: 1.2rem; color: #fff;">#${p.id} - ${escapeMeseroHtml(p.numero_mesa)}</strong>
            <span class="badge" style="background: ${isListo ? 'var(--neon-green)' : 'var(--gold-accent)'}; color: #000; font-size: 0.75rem; font-weight: 800; padding: 0.2rem 0.6rem; border-radius: 6px;">
              ${escapeMeseroHtml(p.estado)}
            </span>
          </div>
          <div style="font-size: 0.78rem; color: ${elapsedMinutes >= 15 ? 'var(--neon-red)' : 'var(--text-muted)'}; font-weight: 800; margin-top: 0.35rem;">
            ${elapsedMinutes >= 15 ? 'Prioridad · ' : ''}${elapsedMinutes} min transcurridos
          </div>
          <div style="font-size: 0.85rem; color: #fff; margin-top: 0.3rem;">Cliente: <strong>${p.nombre_factura || p.nombre_cliente_delivery || 'Comensal'}</strong></div>
          <div style="font-size: 0.85rem; color: var(--gold-accent); font-weight: 800;">Total: ${formatPriceDual(p.total)}</div>
          
          <!-- Bloque de Destacado de BEBIDAS para Entregas Rápidas en Mesa -->
          ${bebidas.length > 0 ? `
            <div style="background: rgba(0,245,212,0.1); border: 1px solid var(--cyan-accent); border-radius: 8px; padding: 0.5rem 0.75rem; margin: 0.6rem 0;">
              <strong style="color: var(--cyan-accent); font-size: 0.78rem; display: block;">🥤 BEBIDAS (ENTREGA INMEDIATA):</strong>
              <div style="color: #fff; font-size: 0.82rem; font-weight: 700;">${bebidas.join(', ')}</div>
            </div>
          ` : ''}

          <p style="font-size: 0.85rem; color: var(--text-muted); margin: 0.4rem 0;"><strong>🍽️ Platos:</strong> ${comidas.join(', ') || 'Sin comida'}</p>
        </div>

        <div style="display: flex; flex-wrap:wrap; gap: 0.5rem; margin-top: 1rem; border-top: 1px dashed var(--toon-border); padding-top: 0.75rem;">
          <button class="btn-gold" ${hasFreeTable ? "" : "disabled"} style="flex: 1; min-width:9rem; padding: 0.4rem 0.6rem; font-size: 0.75rem; background: transparent; border: 1px solid var(--gold-accent); color: var(--gold-accent);" onclick="openCambiarMesaModal(${p.id})">🔄 Cambiar Mesa</button>
          ${isListo ? `<button class="btn-gold" style="flex: 1; min-width:9rem; padding: 0.4rem 0.6rem; font-size: 0.75rem;" onclick="marcarPedidoEntregado(${p.id})">✅ Entregado</button>` : `<span style="flex:1;align-self:center;color:var(--text-muted);font-size:.8rem">Esperando a que cocina termine</span>`}
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

function openCambiarMesaModal(pedidoId) {
  selectedPedidoForSwap = meseroPedidos.find(p => p.id === pedidoId);
  if (!selectedPedidoForSwap) return;
  if (!meseroMesas.some(table => table.estado === "LIBRE")) {
    showToast("No hay mesas libres para reasignar este pedido.", "warning");
    return;
  }

  document.getElementById("swap-order-label").innerText = `Reasignar Pedido #${pedidoId} (Actualmente en ${selectedPedidoForSwap.numero_mesa})`;
  
  const select = document.getElementById("swap-nueva-mesa-select");
  let opts = "";
  meseroMesas.forEach(m => {
    if (m.estado === "LIBRE") {
      opts += `<option value="${m.numero_mesa}">Mesa #${m.numero_mesa} (Disponible)</option>`;
    }
  });
  select.innerHTML = opts;

  openModal("cambiar-mesa-modal");
}

async function submitCambiarMesa() {
  if (!selectedPedidoForSwap) return;
  const nuevaMesa = parseInt(document.getElementById("swap-nueva-mesa-select").value);

  try {
    const res = await fetch(`/api/v1/mesero/pedidos/${selectedPedidoForSwap.id}/cambiar-mesa`, {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ nueva_mesa: nuevaMesa })
    });

    if (!res.ok) throw new Error("Error al reasignar mesa");
    const data = await res.json();
    showToast(data.mensaje, "success");
    closeModal("cambiar-mesa-modal");
    loadMeseroData();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function marcarPedidoEntregado(pedidoId) {
  try {
    const res = await fetch(`/api/v1/mesero/pedidos/${pedidoId}/marcar-entregado`, {
      method: "POST",
      headers: Auth.getHeaders()
    });
    if (!res.ok) throw new Error("Error al actualizar estado");
    showToast(`Pedido #${pedidoId} entregado a la mesa`, "success");
    loadMeseroData();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function openModal(id) { document.getElementById(id).classList.add("open"); }
function closeModal(id) { document.getElementById(id).classList.remove("open"); }
