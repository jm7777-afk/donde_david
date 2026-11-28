/* ==========================================================================
   DONDE DAVID POS - MODULO MAESTRO DE CAJA Y FACTURACION INTEGRADA
   ==========================================================================
   ESTRUCTURA MODULAR DEL ARCHIVO:
   --------------------------------------------------------------------------
   [SEC-01] Estado Global y Configuración de Divisas ($ / Bs.)
   [SEC-02] Control de NAVEGACIÓN SPA (POS, Cuentas, Postres, Deliverys, Facturas)
   [SEC-03] CATÁLOGO TOUCH Y DYN-GRID DE PRODUCTOS POS
   [SEC-04] MODAL DE PERSONALIZACIÓN DE PRODUCTOS (Remover, Extras, Notas)
   [SEC-05] TICKETING POS & CÁLCULOS DE MONTO NETO Y CAMBIO
   [SEC-06] ARQUEO Y CONTROL DE TURNO DE CAJA (Apertura / Cierre)
   [SEC-07] COLA UNIFICADA DE CUENTAS Y PAGOS POR COBRAR (Buscador por ID)
   [SEC-08] DESPACHO Y CONTROL DE SALIDA DE POSTRES
   [SEC-09] GESTIÓN DE DELIVERYS Y ASIGNACIÓN MOTORIZADA CON GPS
   [SEC-10] PASARELA DIGITAL DE COBRO (Pago Móvil 4 dígitos, Tarjeta, Zelle)
   [SEC-11] REIMPRESIÓN DE FACTURAS Y FILTRADO HISTÓRICO
   ========================================================================== */

let activeShift = null;
let pendingOrders = [];
let paidOrders = [];
let selectedOrderForPayment = null;
let allProductsPos = [];
let frequentPosProducts = [];
let posCategories = [];
let posCart = [];
let posPromos = [];
let posTipPct = 0;
let selectedSplitOrderId = null;
let lastPrintedInvoiceMeta = null;
let tasaCambioBs = null;
let tasaFuente = "";
let tasaActualizadaAt = null;
let deliveryCouriers = [];
let posTaxRate = 16;
let posDeliveryFee = 5;
let posPackageFee = 3;
let resumePaymentAfterShiftOpen = false;

let currentOrderType = 'llevar'; // llevar, mesa, delivery
let currentPaymentMethod = 'Efectivo';
let selectedCategoryFilter = null;

let currentCustomizingProduct = null;
let currentCustomizingQty = 1;

document.addEventListener("DOMContentLoaded", () => {
  if (!Auth.requireRole("caja")) return;

  loadPosConfig().catch(error => {
    console.error("No se pudo cargar la tasa de cambio:", error);
    showToast("Tasa en bolívares no disponible. Los cobros en USD siguen habilitados.", "warning");
  });
  loadShiftStatus();
  loadPendingOrders();
  loadPaidOrders();
  loadPickupOrders();
  loadPosCategories();
  loadPosProducts();
  loadPosPromos();

  document.addEventListener("keydown", evt => {
    if (evt.key === "F2") {
      evt.preventDefault();
      document.getElementById("mc-search-input")?.focus();
    } else if (evt.key === "F9") {
      const posContainer = document.getElementById("view-pos-container");
      if (posContainer && posContainer.style.display !== "none" && !isSubmittingPosFast) {
        evt.preventDefault();
        submitPosOrderFast();
      }
    }
  });
  if (window.location.hash === "#delivery") {
    setTimeout(() => switchPosMainView("deliverys"), 0);
  }

  new WSClient((event, data) => {
    if (event === "CONFIGURACION_ACTUALIZADA") {
      loadPosConfig().then(() => renderPosTicket()).catch(() => {});
    }
    if (event === "NUEVO_PEDIDO" || event === "PEDIDO_PENDIENTE_COBRO" || event === "PAGO_MOVIL_PENDIENTE"
        || event === "PAGO_CONFIRMADO" || event === "TURNO_ACTUALIZADO"
        || event === "CAMBIO_ESTADO_PEDIDO" || event === "MOVIMIENTO_CAJA") {
      loadShiftStatus();
      loadPendingOrders();
      loadPaidOrders();
      loadPickupOrders();
      if (event === "PAGO_MOVIL_PENDIENTE") {
        notifyHighPriority({
          area: "CAJA",
          title: "Pago Móvil por validar",
          message: `Pedido #${data.id || ""} requiere verificación manual de referencia.`,
          level: "critical",
          tag: `caja-pm-${data.id || ""}`,
        });
      } else if (event === "PEDIDO_PENDIENTE_COBRO") {
        notifyHighPriority({
          area: "CAJA",
          title: "Nuevo pedido pendiente de cobro",
          message: `Pedido #${data.id || ""} (${data.numero_mesa || "Mostrador"}) esperando confirmación en Caja.`,
          level: "critical",
          tag: `caja-cobro-${data.id || ""}`,
        });
      } else if (event === "NUEVO_PEDIDO") {
        notifyHighPriority({
          area: "CAJA",
          title: "Nuevo pedido recibido",
          message: `Pedido #${data.id || ""} · ${data.numero_mesa || "Mostrador"}.`,
          level: "high",
          tag: `caja-new-${data.id || ""}`,
        });
      } else if (event === "CAMBIO_ESTADO_PEDIDO" && (data.nuevo_estado === "LISTO" || data.estado_retiro === "LISTO_PARA_RETIRAR")) {
        notifyHighPriority({
          area: "CAJA",
          title: "Pedido listo para entregar / retirar",
          message: `Pedido #${data.pedido_id || ""} (${data.numero_mesa || "Mostrador"}) está listo.`,
          level: "high",
          tag: `caja-ready-${data.pedido_id || ""}`,
        });
      }
    }
  });
});

async function togglePosIva() {
  const btn = document.getElementById("pos-iva-toggle-btn");
  const nextVal = btn?.dataset?.nextIva || (posTaxRate > 0 ? "false" : "true");
  if (btn) btn.disabled = true;
  try {
    const res = await fetch("/api/v1/admin/configuraciones", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ clave: "iva_activo", valor: nextVal })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "No se pudo cambiar el estado del IVA.");
    }
    await loadPosConfig();
    renderPosTicket();
    showToast(nextVal === "true" ? "🧾 IVA habilitado en Caja POS." : "🧾 IVA deshabilitado en Caja POS.", "success");
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadPosConfig() {
  const res = await fetch("/api/v1/cliente/configuraciones-publicas");
  if (!res.ok) throw new Error("No se pudo consultar la configuración pública.");
  const cfg = await res.json();
  const rate = Number(cfg.tasa_cambio_bs);
  tasaCambioBs = Number.isFinite(rate) && rate > 0 ? rate : null;
  const ivaActivo = cfg.iva_activo !== "false" && cfg.iva_activo !== false;
  posTaxRate = ivaActivo && Number.isFinite(Number(cfg.impuesto_porcentaje)) ? Number(cfg.impuesto_porcentaje) : (ivaActivo ? 16 : 0);
  const posTaxLabel = document.getElementById("pos-tax-label");
  if (posTaxLabel) posTaxLabel.textContent = ivaActivo ? `IVA (${posTaxRate}%):` : "IVA (0% · Exento):";
  const ivaBadge = document.getElementById("pos-iva-status-badge");
  if (ivaBadge) {
    ivaBadge.textContent = ivaActivo ? `🧾 IVA: ${posTaxRate}% Activo` : "🧾 IVA: Deshabilitado (0%)";
  }
  const ivaToggleBtn = document.getElementById("pos-iva-toggle-btn");
  const currentRole = String(Auth.getUser()?.rol || "").toLowerCase();
  if (ivaToggleBtn) {
    if (["admin", "supervisor"].includes(currentRole)) {
      ivaToggleBtn.classList.remove("u-display-none");
      ivaToggleBtn.textContent = ivaActivo ? "Deshabilitar IVA" : "Habilitar IVA";
      ivaToggleBtn.dataset.nextIva = ivaActivo ? "false" : "true";
    } else {
      ivaToggleBtn.classList.add("u-display-none");
    }
  }
  posDeliveryFee = Number.isFinite(Number(cfg.costo_delivery)) ? Number(cfg.costo_delivery) : 5;
  posPackageFee = Number.isFinite(Number(cfg.costo_empaque)) ? Number(cfg.costo_empaque) : 3;
  tasaFuente = cfg.tasa_fuente || "";
  tasaActualizadaAt = cfg.tasa_actualizada_at || null;
  const vesOption = document.querySelector('#pay-currency-select option[value="VES"]');
  if (vesOption) vesOption.disabled = tasaCambioBs === null;
  const rateInfo = document.getElementById("pay-rate-info");
  const posRateInfo = document.getElementById("pos-rate-info");
  const posCurrencySelect = document.getElementById("pos-currency-select");
  const posVesOption = posCurrencySelect?.querySelector('option[value="VES"]');
  if (posVesOption) posVesOption.disabled = tasaCambioBs === null;
  const mobilePaymentButton = document.getElementById("pay-btn-Pago Móvil");
  if (mobilePaymentButton) mobilePaymentButton.disabled = tasaCambioBs === null;
  if (posRateInfo) {
    posRateInfo.textContent = tasaCambioBs
      ? `Tasa BCV ${tasaCambioBs.toFixed(4)} Bs./USD · ${tasaFuente || "fuente no identificada"}`
      : "Tasa no disponible; solo se permiten cobros en USD.";
  }
  const taxLabel = document.getElementById("pos-tax-label");
  if (taxLabel) taxLabel.textContent = ivaActivo ? `IVA (${posTaxRate}%):` : "IVA (Desactivado 0%):";
  if (rateInfo) {
    if (tasaCambioBs === null) {
      rateInfo.textContent = "Tasa no disponible; solo se permiten cobros en USD.";
    } else {
      const source = tasaFuente || "Fuente no identificada";
      const updatedAt = tasaActualizadaAt ? new Date(tasaActualizadaAt).toLocaleString("es-VE") : "fecha no disponible";
      rateInfo.textContent = `Tasa: Bs. ${tasaCambioBs.toFixed(4)}/USD · ${source} · ${updatedAt}`;
    }
  }

}

function openCashExpenseModal() {
  openModal("cash-expense-modal");
  loadCashMovements();
}

async function loadCashMovements() {
  const container = document.getElementById("cash-movements-list");
  if (!container) return;
  try {
    const response = await fetch("/api/v1/caja/movimientos", { headers: Auth.getHeaders() });
    const movements = response.status === 404 ? [] : await response.json();
    if (!response.ok && response.status !== 404) {
      throw new Error(movements.detail || "No se pudieron cargar los egresos.");
    }
    container.innerHTML = `<h4>Egresos de este turno</h4>${movements.length
      ? movements.map(item => `<div style="display:flex;justify-content:space-between;gap:.5rem;padding:.4rem 0;border-top:1px solid var(--toon-border)">
          <span>${escapeCajaHtml(item.concepto)} · ${escapeCajaHtml(item.metodo_pago)}${item.observacion ? `<small style="display:block;color:var(--text-muted)">${escapeCajaHtml(item.observacion)}</small>` : ""}</span>
          <strong>-$${Number(item.monto_usd).toFixed(2)}</strong>
        </div>`).join("")
      : `<p style="color:var(--text-muted)">${response.status === 404 ? "No hay turno activo." : "Sin egresos registrados."}</p>`}`;
  } catch (error) {
    console.error("Error al consultar egresos de caja:", error);
    container.innerHTML = `<p role="alert" style="color:var(--mc-red)">${escapeCajaHtml(error.message)}</p>`;
  }
}

async function submitCashExpense() {
  const concepto = document.getElementById("cash-expense-concept").value.trim();
  const monto = Number(document.getElementById("cash-expense-amount").value);
  const metodo = document.getElementById("cash-expense-method").value;
  const observacion = document.getElementById("cash-expense-note").value.trim();
  if (concepto.length < 3 || !Number.isFinite(monto) || monto <= 0) {
    showToast("Indica un concepto y un monto de egreso válido.", "warning");
    return;
  }
  try {
    const response = await fetch("/api/v1/caja/movimientos", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ concepto, monto_usd: monto, metodo_pago: metodo, observacion })
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "No se pudo registrar el egreso.");
    showToast("Egreso registrado en el turno actual.", "success");
    closeModal("cash-expense-modal");
    document.getElementById("cash-expense-concept").value = "";
    document.getElementById("cash-expense-amount").value = "";
    document.getElementById("cash-expense-note").value = "";
    await loadShiftStatus();
  } catch (error) {
    showToast(error.message, "danger");
  }
}

function formatPriceDual(usdAmount) {
  const amount = Number(usdAmount) || 0;
  if (!Number.isFinite(tasaCambioBs) || tasaCambioBs <= 0) return `$${amount.toFixed(2)}`;
  const bsAmount = (amount * tasaCambioBs).toFixed(2);
  return `$${amount.toFixed(2)} <span style="font-size: 0.8rem; color: var(--mc-yellow);">(Bs. ${bsAmount})</span>`;
}

function escapeCajaHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function switchPosMainView(viewName) {
  document.getElementById("view-pos-container").style.display = viewName === 'pos' ? 'grid' : 'none';
  document.getElementById("view-queue-container").style.display = viewName === 'queue' ? 'block' : 'none';
  document.getElementById("view-history-container").style.display = viewName === 'history' ? 'block' : 'none';
  
  if (document.getElementById("view-postres-container")) {
    document.getElementById("view-postres-container").style.display = viewName === 'postres' ? 'block' : 'none';
  }
  if (document.getElementById("view-app-payments-container")) {
    document.getElementById("view-app-payments-container").style.display = viewName === 'app-payments' ? 'block' : 'none';
  }
  if (document.getElementById("view-deliverys-container")) {
    document.getElementById("view-deliverys-container").style.display = viewName === 'deliverys' ? 'block' : 'none';
  }
  if (document.getElementById("view-pickup-container")) {
    document.getElementById("view-pickup-container").style.display = viewName === 'pickup' ? 'block' : 'none';
  }

  if (document.getElementById("view-btn-pos")) document.getElementById("view-btn-pos").classList.toggle("active", viewName === 'pos');
  if (document.getElementById("view-btn-postres")) document.getElementById("view-btn-postres").classList.toggle("active", viewName === 'postres');
  if (document.getElementById("view-btn-app-payments")) document.getElementById("view-btn-app-payments").classList.toggle("active", viewName === 'app-payments');
  if (document.getElementById("view-btn-deliverys")) document.getElementById("view-btn-deliverys").classList.toggle("active", viewName === 'deliverys');
  if (document.getElementById("view-btn-pickup")) document.getElementById("view-btn-pickup").classList.toggle("active", viewName === 'pickup');
  if (document.getElementById("view-btn-queue")) document.getElementById("view-btn-queue").classList.toggle("active", viewName === 'queue');
  if (document.getElementById("view-btn-history")) document.getElementById("view-btn-history").classList.toggle("active", viewName === 'history');

  if (viewName === 'postres') {
    renderDessertPrepQueue();
  } else if (viewName === 'app-payments') {
    renderAppPaymentsQueue();
  } else if (viewName === 'deliverys') {
    renderDeliverysQueue();
  } else if (viewName === 'pickup') {
    loadPickupOrders();
  }
}

function switchTab(tabName) {
  const viewByTab = {
    pos: "pos",
    pendientes: "queue",
    postres: "postres",
    deliverys: "deliverys",
    facturas: "history",
    retiros: "pickup",
    pagos: "app-payments",
  };
  const view = viewByTab[tabName];
  if (view) switchPosMainView(view);
}

async function loadPickupOrders() {
  const container = document.getElementById("pickup-orders-list");
  if (!container) return;
  try {
    const response = await fetch("/api/v1/caja/pedidos-retiro", { headers: Auth.getHeaders() });
    if (!response.ok) throw new Error("No se pudieron cargar los pedidos de retiro.");
    const orders = await response.json();
    const count = document.getElementById("pickup-count");
    if (count) count.textContent = `${orders.length} listo(s)`;
    if (orders.length === 0) {
      container.innerHTML = `<div style="grid-column:1/-1;padding:2rem;text-align:center;color:var(--text-muted)">No hay pedidos listos para retirar.</div>`;
      return;
    }
    container.innerHTML = orders.map(order => `
      <article style="background:var(--toon-card);border:1px solid var(--toon-border);border-radius:16px;padding:1rem">
        <h3 style="margin-top:0">Pedido #${order.id}</h3>
        <p><strong>${escapeCajaHtml(order.nombre_factura || "Cliente")}</strong> · ${escapeCajaHtml(order.numero_mesa)}</p>
        <p>Total: ${formatPriceDual(order.total)}</p>
        <label for="pickup-code-${order.id}">Código de retiro del cliente</label>
        <input id="pickup-code-${order.id}" class="form-control" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" aria-label="Código de retiro del pedido ${order.id}">
        <button class="btn btn-cta" style="width:100%;margin-top:.65rem" onclick="confirmPickupOrder(${order.id})">Confirmar entrega</button>
      </article>
    `).join("");
  } catch (error) {
    console.error("Error en cola de retiros:", error);
    showToast(error.message, "danger");
  }
}

async function confirmPickupOrder(orderId) {
  const input = document.getElementById(`pickup-code-${orderId}`);
  const code = input?.value.trim();
  if (!/^[0-9]{6}$/.test(code || "")) {
    showToast("Ingresa el código de retiro de seis dígitos.", "warning");
    return;
  }
  try {
    const response = await fetch(`/api/v1/caja/pedidos/${orderId}/confirmar-retiro`, {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ codigo_retiro: code })
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "No se pudo confirmar el retiro.");
    showToast(body.mensaje, "success");
    await loadPickupOrders();
    await loadPaidOrders();
  } catch (error) {
    showToast(error.message, "danger");
  }
}

const confirmingMobilePaymentIds = new Set();
let isSubmittingPosFast = false;
let isClosingShift = false;
let isSubmittingPayment = false;

function renderAppPaymentsQueue() {
  const container = document.getElementById("app-payments-grid-list");
  const validationOrders = pendingOrders.filter(o => o.estado_pago === "PENDIENTE_VALIDACION");

  const appPaymentsBtn = document.getElementById("view-btn-app-payments");
  if (appPaymentsBtn) {
    appPaymentsBtn.textContent = `📱 PAGOS MÓVILES (${validationOrders.length})`;
  }

  if (document.getElementById("app-payments-count")) {
    document.getElementById("app-payments-count").innerText = `${validationOrders.length} pagos móviles por validar`;
  }

  if (!container) return;

  if (validationOrders.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 2rem;">No hay pagos pendientes por confirmar en la caja.</div>`;
    return;
  }

  container.innerHTML = validationOrders.map(o => {
    return `
      <div class="card fade-in" style="background: var(--toon-card); border: 2px solid var(--cyan-accent); border-radius: var(--radius-md); padding: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <span class="badge" style="background: var(--cyan-accent); color: #000; font-weight: 900; font-size: 0.85rem;">
            📱 PAGO MÓVIL #${o.id}
          </span>
          <strong style="color: var(--gold-accent); font-size: 1.25rem; font-weight: 900;">Bs. ${parseFloat(o.monto_pago || 0).toFixed(2)}</strong>
        </div>

        <p style="font-size: 0.9rem; color: #fff; margin-bottom: 0.3rem;"><strong>Cliente:</strong> ${escapeCajaHtml(o.nombre_cliente_delivery || o.nombre_factura || o.numero_mesa || 'Cliente')}</p>
        ${o.direccion_delivery ? `<p style="font-size: 0.85rem; color: var(--cyan-accent); margin-bottom: 0.4rem;">📍 ${escapeCajaHtml(o.direccion_delivery)}</p>` : ''}
        
        <div style="background: rgba(255,255,255,0.05); border: 1px solid var(--toon-border); border-radius: 10px; padding: 0.65rem; margin-bottom: 0.85rem;">
          <div>Referencia: <strong>${escapeCajaHtml(o.referencia_pago || "Sin referencia")}</strong></div>
          <div>Total base: $${Number(o.total).toFixed(2)} · Tasa aplicada: Bs. ${Number(o.tasa_cambio_pago || 0).toFixed(4)}/USD</div>
        </div>

        <div style="display:flex; gap:.5rem">
          <button class="btn btn-cta" style="flex:1" onclick="confirmMobilePayment(${o.id}, true)">✓ Confirmar pago</button>
          <button class="btn btn-outline" style="flex:1" onclick="confirmMobilePayment(${o.id}, false)">Rechazar</button>
        </div>
      </div>
    `;
  }).join('');
}

async function confirmMobilePayment(orderId, approved) {
  if (confirmingMobilePaymentIds.has(orderId)) return;
  const observation = approved ? "" : (prompt("Motivo del rechazo (opcional):") || "");
  confirmingMobilePaymentIds.add(orderId);
  try {
    const response = await fetch(`/api/v1/caja/pedidos/${orderId}/confirmar-pago`, {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ aprobado: approved, observacion: observation })
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "No se pudo validar el pago.");
    }
    const result = await response.json();
    showToast(result.mensaje, approved ? "success" : "warning");
    await loadPendingOrders();
    await loadPaidOrders();
  } catch (error) {
    showToast(error.message, "danger");
  } finally {
    confirmingMobilePaymentIds.delete(orderId);
  }
}

// ==================== BÚSQUEDA DE CLIENTES REGISTRADOS POR ID O NOMBRE EN CAJA ====================
let selectedCustomerPos = null;
let lastSearchedCustomersPos = [];

async function searchCustomerPosLive() {
  const query = document.getElementById("pos-customer-search-input")?.value.trim();
  const dropdown = document.getElementById("pos-customer-results-dropdown");
  if (!dropdown) return;

  if (!query || query.length < 1) {
    dropdown.style.display = "none";
    dropdown.innerHTML = "";
    lastSearchedCustomersPos = [];
    return;
  }

  try {
    const res = await fetch(`/api/v1/caja/clientes/buscar?q=${encodeURIComponent(query)}`, { headers: Auth.getHeaders() });
    if (!res.ok) return;
    const clients = await res.json();
    lastSearchedCustomersPos = Array.isArray(clients) ? clients : [];

    if (lastSearchedCustomersPos.length === 0) {
      dropdown.innerHTML = `<div style="padding: 0.6rem; font-size: 0.8rem; color: var(--text-muted); text-align: center;">No se encontró ningún cliente con '${escapeCajaHtml(query)}'</div>`;
      dropdown.style.display = "block";
      return;
    }

    dropdown.innerHTML = lastSearchedCustomersPos.map(c => `
      <div style="padding: 0.65rem 0.85rem; border-bottom: 1px solid var(--toon-border); cursor: pointer; display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03);" onclick="selectCustomerPosById(${Number(c.id)})">
        <div>
          <strong style="color: #fff; font-size: 0.88rem; display: block;">${escapeCajaHtml(c.nombre_completo)}</strong>
          <small style="color: var(--cyan-accent); font-weight: 800;">🆔 ${escapeCajaHtml(c.codigo_cliente)} • ${escapeCajaHtml(c.email)}</small>
        </div>
        <span style="font-size: 0.78rem; background: rgba(255,188,13,0.2); color: var(--gold-accent); padding: 0.2rem 0.55rem; border-radius: 12px; font-weight: 900;">${Number(c.puntos_fidelidad || 0)} Pts 🏆</span>
      </div>
    `).join('');
    dropdown.style.display = "block";
  } catch(e) {
    console.error("Error al buscar clientes:", e);
  }
}

function selectCustomerPosById(customerId) {
  const match = lastSearchedCustomersPos.find(c => Number(c.id) === Number(customerId));
  if (!match) return;
  selectCustomerForPos(
    match.id,
    match.nombre_completo,
    match.codigo_cliente,
    match.puntos_fidelidad,
    match.telefono
  );
}

function selectCustomerForPos(id, name, code, points, telefono = null) {
  const cleanPhone = telefono && telefono !== "Sin teléfono" ? String(telefono).trim() : null;
  selectedCustomerPos = { id, name, nombre: name, code, points, telefono: cleanPhone };
  if (document.getElementById("pos-customer-search-input")) {
    document.getElementById("pos-customer-search-input").value = `${name} (${code})`;
  }
  if (currentOrderType !== "mesa" && document.getElementById("pos-mesa-input")) {
    document.getElementById("pos-mesa-input").value = `${name} (${code})`;
  }
  if (document.getElementById("pay-nombre-input") && !document.getElementById("pay-nombre-input").value.trim()) {
    document.getElementById("pay-nombre-input").value = name;
  }
  if (document.getElementById("pos-delivery-name") && !document.getElementById("pos-delivery-name").value.trim()) {
    document.getElementById("pos-delivery-name").value = name;
  }
  if (cleanPhone && document.getElementById("pos-delivery-phone") && !document.getElementById("pos-delivery-phone").value.trim()) {
    document.getElementById("pos-delivery-phone").value = cleanPhone;
  }
  const dropdown = document.getElementById("pos-customer-results-dropdown");
  if (dropdown) dropdown.style.display = "none";
  showToast(`👤 Cliente Seleccionado: ${name} (${code}) - ${points} Pts`, "success");
}

async function renderDeliverysQueue() {
  const container = document.getElementById("deliverys-grid-list");
  if (!container) return;
  container.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:2rem">Cargando entregas…</div>';
  let deliveryOrders;
  try {
    const [ordersResponse, couriersResponse] = await Promise.all([
      fetch("/api/v1/delivery/despacho/pedidos", { headers: Auth.getHeaders() }),
      fetch("/api/v1/delivery/despacho/repartidores", { headers: Auth.getHeaders() })
    ]);
    if (!ordersResponse.ok || !couriersResponse.ok) throw new Error("No se pudo cargar despacho o repartidores.");
    deliveryOrders = await ordersResponse.json();
    deliveryCouriers = await couriersResponse.json();
  } catch (error) {
    container.innerHTML = `<div role="alert" style="grid-column:1/-1;color:var(--neon-red)">${error.message}</div>`;
    return;
  }
  if (document.getElementById("deliverys-count")) {
    document.getElementById("deliverys-count").innerText = `${deliveryOrders.length} Envíos Delivery Activos`;
  }

  if (deliveryOrders.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--color-text-secondary); padding: 2rem;">No hay envíos delivery activos en este turno.</div>`;
    return;
  }

  container.innerHTML = deliveryOrders.map(o => {
    const hasGps = o.delivery_lat !== null && o.delivery_lat !== undefined && o.delivery_lng !== null && o.delivery_lng !== undefined && Number.isFinite(Number(o.delivery_lat)) && Number.isFinite(Number(o.delivery_lng));
    const mapsUrl = hasGps ? `https://www.google.com/maps?q=${o.delivery_lat},${o.delivery_lng}` : `https://maps.google.com/?q=${encodeURIComponent(o.direccion_delivery || "")}`;
    const assignedCourier = deliveryCouriers.find(c => c.id === o.repartidor_id);
    const courierOptions = deliveryCouriers.map(c =>
      `<option value="${Number(c.id)}" ${c.id === o.repartidor_id ? "selected" : ""}>${escapeCajaHtml(c.nombre)}</option>`
    ).join("");
    const paymentLabel = o.estado_pago === "PAGADO" ? "Pago confirmado" : "Pendiente de cobro en caja";
    const clientName = o.nombre_cliente_delivery || o.nombre_factura || "Cliente Delivery";
    const phone = o.telefono_delivery || "Sin teléfono";
    const address = o.direccion_delivery || "Sin dirección";

    return `
      <div class="card fade-in" style="background: var(--toon-card); border: 1.5px solid var(--cyan-accent); border-radius: var(--radius-md); padding: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <span class="badge" style="background: var(--cyan-accent); color: #000; font-weight: 900;">🛵 Delivery #${Number(o.id)}</span>
          <strong style="color: var(--gold-accent); font-size: 1.25rem;">$${parseFloat(o.total).toFixed(2)}</strong>
        </div>
        <p style="font-size: 0.9rem; color: #fff; margin-bottom: 0.3rem;"><strong>Cliente:</strong> ${escapeCajaHtml(clientName)}</p>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.4rem;"><strong>Teléfono:</strong> ${escapeCajaHtml(phone)}</p>
        
        <div style="background: rgba(0,245,212,0.06); border: 1px solid var(--cyan-accent); border-radius: 10px; padding: 0.75rem; margin-bottom: 0.85rem;">
          <div style="font-size: 0.78rem; color: var(--cyan-accent); font-weight: 800; margin-bottom: 0.2rem;">📍 UBICACIÓN Y GPS RECIBIDOS EN CAJA:</div>
          <div style="font-size: 0.88rem; color: #fff; word-break: break-all;">${escapeCajaHtml(address)}</div>
        </div>

        <div style="margin-bottom:.7rem"><strong>Estado de entrega:</strong> ${escapeCajaHtml(o.estado_delivery || "PENDIENTE")} · ${paymentLabel}</div>
        ${assignedCourier ? `<div style="margin-bottom:.7rem"><strong>Repartidor:</strong> ${escapeCajaHtml(assignedCourier.nombre)}</div>` : ""}
        <div style="display:flex;gap:.5rem;flex-wrap:wrap">
          <a href="${mapsUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-outline">🗺️ Abrir mapa</a>
          ${o.estado_pago === "PAGADO" && deliveryCouriers.length && ["PENDIENTE", "ASIGNADO"].includes(o.estado_delivery || "PENDIENTE")
            ? `<select id="courier-${o.id}" class="form-control" style="flex:1;min-width:160px">${courierOptions || '<option value="">Selecciona repartidor</option>'}</select><button class="btn btn-cta" onclick="assignDeliveryOrder(${o.id})">${assignedCourier ? "Guardar asignación" : "Asignar"}</button>`
            : o.estado_pago === "PAGADO"
              ? assignedCourier
                ? `<span class="badge">Repartidor en ruta: ${escapeCajaHtml(o.estado_delivery)}</span>`
                : `<a class="btn btn-outline" href="/static/admin/index.html#tab-usuarios">Crear usuario con rol Repartidor</a>`
              : `<button class="btn btn-outline" onclick="openPayModal(${o.id})">Cobrar antes de asignar</button>`}
        </div>
      </div>
    `;
  }).join('');
}

async function assignDeliveryOrder(orderId) {
  const courierId = Number(document.getElementById(`courier-${orderId}`)?.value);
  if (!courierId) {
    showToast("Selecciona un repartidor activo.", "warning");
    return;
  }
  try {
    const response = await fetch(`/api/v1/delivery/despacho/pedidos/${orderId}/asignar`, {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ repartidor_id: courierId })
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "No se pudo asignar el pedido.");
    }
    showToast(`Pedido #${orderId} asignado.`, "success");
    await renderDeliverysQueue();
  } catch (error) {
    showToast(error.message, "danger");
  }
}

let dispatchedDessertIds = new Set(JSON.parse(localStorage.getItem("dispatched_desserts") || "[]"));

function toggleDessertDispatched(itemId) {
  if (dispatchedDessertIds.has(itemId)) {
    dispatchedDessertIds.delete(itemId);
    showToast("🍰 Postre marcado como PENDIENTE", "info");
  } else {
    dispatchedDessertIds.add(itemId);
    showToast("✅ Postre marcado como DESPACHADO por la Cajera", "success");
  }
  localStorage.setItem("dispatched_desserts", JSON.stringify(Array.from(dispatchedDessertIds)));
  renderDessertPrepQueue();
}

function renderDessertPrepQueue() {
  const container = document.getElementById("postres-grid-list");
  if (!container) return;

  const dessertItems = [];
  pendingOrders.concat(paidOrders).forEach(order => {
    if (!order.detalles) return;
    order.detalles.forEach(d => {
      const prodName = (d.producto ? d.producto.nombre : (d.nombre || '')).toLowerCase();
      const catName = (d.producto && d.producto.categoria ? d.producto.categoria.nombre : '').toLowerCase();
      const isDessert = catName.includes("postre") || 
                        prodName.includes("postre") || 
                        prodName.includes("helado") || 
                        prodName.includes("malteada") || 
                        prodName.includes("torta") || 
                        prodName.includes("pie") || 
                        prodName.includes("marquesa") || 
                        prodName.includes("brownie") || 
                        prodName.includes("sundae");

      if (isDessert) {
        dessertItems.push({ order, item: d });
      }
    });
  });

  if (document.getElementById("postres-queue-count")) {
    const pendingCount = dessertItems.filter(i => !dispatchedDessertIds.has(i.item.id)).length;
    document.getElementById("postres-queue-count").innerText = `${pendingCount} Postres Pendientes (${dessertItems.length} Total)`;
  }

  if (dessertItems.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--color-text-secondary); border: 1px dashed var(--color-border); border-radius: var(--radius-md);">
        <span style="font-size: 3rem;">🍰</span>
        <h3 style="color: #fff; margin-top: 0.5rem;">No hay postres solicitados actualmente</h3>
        <p style="font-size: 0.85rem;">Todos los postres de comandas activas han sido controlados por la cajera.</p>
      </div>
    `;
    return;
  }

  let html = "";
  dessertItems.forEach(({ order, item }) => {
    const isDispatched = dispatchedDessertIds.has(item.id);
    const prodName = item.producto ? item.producto.nombre : 'Postre';

    html += `
      <div class="card fade-in" style="background: var(--toon-card); border: 2px solid ${isDispatched ? 'var(--color-success)' : 'var(--gold-accent)'}; border-radius: var(--radius-md); padding: 1.25rem; opacity: ${isDispatched ? '0.75' : '1'};">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <strong style="color: var(--gold-accent); font-size: 1.1rem;">🍰 Comanda #${order.id} - ${order.numero_mesa}</strong>
          <span class="badge" style="background: ${isDispatched ? 'var(--color-success)' : 'var(--gold-accent)'}; color: #000; font-weight: 900; font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 6px;">
            ${isDispatched ? '✅ DESPACHADO' : '⏳ POR DESPACHAR'}
          </span>
        </div>
        <div style="font-size: 1.15rem; font-weight: 900; color: #fff; margin-bottom: 0.5rem;">
          ${item.cantidad}x ${prodName}
        </div>
        <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.75rem;">
          <strong>Cliente / Destino:</strong> ${order.nombre_cliente_delivery || order.nombre_factura || 'Comensal'} (${order.tipo})
        </p>
        ${item.observaciones ? `<div style="font-size: 0.8rem; color: var(--neon-red); font-weight: 700; margin-bottom: 0.75rem;">⚠️ Nota: ${item.observaciones}</div>` : ''}
        
        <button class="btn ${isDispatched ? 'btn-outline' : 'btn-cta'}" style="width: 100%; min-height: 40px; font-size: 0.88rem; font-weight: 900;" onclick="toggleDessertDispatched(${item.id})">
          ${isDispatched ? '🔄 DESMARCAR Y VOLVER A PENDIENTE' : '🍰 MARCAR POSTRE DESPACHADO EN CAJA'}
        </button>
      </div>
    `;
  });

  container.innerHTML = html;
}

async function loadPosCategories() {
  try {
    const res = await fetch("/api/v1/cliente/categorias");
    if (res.ok) {
      posCategories = await res.json();
    }
  } catch (err) {
    console.error(err);
  }

  if (!posCategories || posCategories.length === 0) {
    posCategories = [
      { id: 1, nombre: "Hamburguesas" },
      { id: 2, nombre: "Hot Dogs" },
      { id: 3, nombre: "Papas" },
      { id: 4, nombre: "Bebidas" },
      { id: 6, nombre: "Postres" }
    ];
  }

  renderPosCategorySidebar();
}

function renderPosCategorySidebar() {
  const container = document.getElementById("mc-cat-sidebar");
  if (!container) return;

  const catIcons = {
    "Hamburguesas": "🍔",
    "Hot Dogs": "🌭",
    "Papas": "🍟",
    "Bebidas": "🥤",
    "Alitas": "🍗",
    "Postres": "🍦",
    "Combos": "🎁",
    "Extras": "🧀"
  };

  let html = `
    <div class="mc-cat-btn ${selectedCategoryFilter === null ? 'active' : ''}" onclick="filterCategoryPos(null)">
      <span class="icon">🔥</span>
      <span>TODOS</span>
    </div>
    <div class="mc-cat-btn ${selectedCategoryFilter === '__COMBOS__' ? 'active' : ''}" onclick="filterCategoryPos('__COMBOS__')">
      <span class="icon">🎁</span>
      <span>COMBOS</span>
    </div>
  `;

  posCategories.forEach(c => {
    const icon = catIcons[c.nombre] || "🍔";
    html += `
      <div class="mc-cat-btn ${selectedCategoryFilter === c.id ? 'active' : ''}" onclick="filterCategoryPos(${c.id})">
        <span class="icon">${icon}</span>
        <span>${c.nombre.toUpperCase()}</span>
      </div>
    `;
  });

  container.innerHTML = html;
}

function filterCategoryPos(catId) {
  selectedCategoryFilter = catId;
  renderPosCategorySidebar();
  renderPosTouchProducts();
  
  const catObj = posCategories.find(c => c.id === catId);
  const label = document.getElementById("mc-cat-title-label");
  if (label) {
    label.innerText = catId === "__COMBOS__"
      ? "Combos y Promociones de Precio Global"
      : (catObj ? `Categoría: ${catObj.nombre}` : "Mostrando Menú Completo");
  }
}

async function loadPosPromos() {
  try {
    const res = await fetch("/api/v1/cliente/promociones");
    if (res.ok) {
      const all = await res.json();
      posPromos = Array.isArray(all) ? all.filter(p => p && Number(p.precio_global) > 0 && Array.isArray(p.productos) && p.productos.length) : [];
      if (selectedCategoryFilter === "__COMBOS__") renderPosTouchProducts();
    }
  } catch (err) {
    console.warn("No se pudieron cargar promos POS:", err);
  }
}

function addPosPromoBundle(promoId) {
  const promo = posPromos.find(p => Number(p.id) === Number(promoId));
  if (!promo) return;
  const products = promo.productos.map(lp => allProductsPos.find(ap => Number(ap.id) === Number(lp.id)) || lp);
  const missing = products.find(p => !p.disponible || Number(p.stock || 0) < 1);
  if (missing) {
    showToast(`"${missing.nombre}" no tiene stock suficiente para este combo.`, "warning");
    return;
  }
  const seq = Date.now() + Math.floor(Math.random() * 1000);
  const globalTarget = Number(promo.precio_global);
  const baseSum = products.reduce((s, p) => s + Number(p.precio_promocion || p.precio || 0), 0);
  let running = 0;
  products.forEach((p, idx) => {
    const reg = Number(p.precio_promocion || p.precio || 0);
    const alloc = idx === products.length - 1
      ? Math.round((globalTarget - running) * 100) / 100
      : Math.round((baseSum > 0 ? globalTarget * (reg / baseSum) : globalTarget / products.length) * 100) / 100;
    running += alloc;
    posCart.push({
      producto_id: Number(p.id),
      nombre: `${p.nombre} (${promo.titulo})`,
      precio_unitario: alloc,
      cantidad: 1,
      subtotal: alloc,
      opciones: [],
      extras: [],
      observaciones: `Combo ${promo.titulo}`,
      promo_id: Number(promo.id),
      promo_bundle_seq: seq
    });
  });
  renderPosTicket();
  showToast(`🎁 Combo "${promo.titulo}" agregado ($${globalTarget.toFixed(2)}).`, "success");
}

async function loadPosProducts() {
  try {
    const res = await fetch("/api/v1/cliente/productos");
    if (!res.ok) throw new Error("No se pudo cargar el catálogo real de productos.");
    allProductsPos = await res.json();
  } catch (err) {
    console.error(err);
    allProductsPos = [];
    showToast(err.message, "danger");
  }
  renderPosTouchProducts();
  loadFrequentPosProducts();
}

function filterProductsPos() {
  const query = document.getElementById("mc-search-input").value.toLowerCase();
  renderPosTouchProducts(query);
}

function renderPosTouchProducts(query = "") {
  const container = document.getElementById("mc-products-touch-grid");
  if (!container) return;

  if (selectedCategoryFilter === "__COMBOS__") {
    const comboCards = (posPromos || []).filter(p => !query || String(p.titulo || "").toLowerCase().includes(query)).map(p => {
      const img = p.banner_url || "/static/img/logo.png";
      return `
        <div class="mc-product-touch-card" onclick="addPosPromoBundle(${Number(p.id)})" style="cursor:pointer;">
          <img src="${escapeCajaHtml(img)}" alt="${escapeCajaHtml(p.titulo)}" onerror="this.onerror=null;this.src='/static/img/logo.png';">
          <div class="mc-product-title">🎁 ${escapeCajaHtml(p.titulo)}</div>
          <div class="mc-product-price">${formatPriceDual(Number(p.precio_global))}</div>
          <small style="color:var(--cyan-accent);font-size:0.72rem;font-weight:700;">${p.productos.length} productos · Precio global</small>
        </div>
      `;
    }).join("");
    container.innerHTML = comboCards || `<p style="grid-column:1/-1;color:var(--text-muted)">No hay combos de precio global configurados.</p>`;
    return;
  }

  let filtered = allProductsPos;
  if (selectedCategoryFilter !== null) {
    filtered = filtered.filter(p => p.categoria_id === selectedCategoryFilter);
  }

  if (query) {
    filtered = filtered.filter(p => p.nombre.toLowerCase().includes(query));
  }

  let html = "";
  filtered.forEach(p => {
    const img = p.imagen_url || "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500";
    const price = p.precio_promocion || p.precio;
    html += `
      <div class="mc-product-touch-card" data-product-id="${p.id}" style="position: relative; cursor: pointer;">
        <img src="${img}" alt="${p.nombre}" onerror="this.onerror=null;this.src='/static/img/logo.png';">
        <div class="mc-product-title">${p.nombre}</div>
        <div class="mc-product-price">${formatPriceDual(price)}</div>
        <button type="button" data-customize-product="${p.id}" aria-label="Personalizar ${escapeCajaHtml(p.nombre)}" style="position: absolute; top: 6px; right: 6px; background: var(--gold-accent); color: #000; border: 0; border-radius: 12px; font-size: 0.72rem; padding: 0.2rem 0.5rem; font-weight: 900; z-index: 2; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.5);" title="Personalizar Ingredientes">
          ⚙️ Personalizar
        </button>
      </div>
    `;
  });

  container.innerHTML = html || `<p style="grid-column:1/-1;color:var(--text-muted)">No hay productos disponibles para vender.</p>`;
  container.querySelectorAll(".mc-product-touch-card").forEach(card => {
    const productId = card.dataset.productId;
    card.addEventListener("click", () => addPosItemDirect(productId));
    const customizeButton = card.querySelector("[data-customize-product]");
    if (customizeButton) {
      customizeButton.addEventListener("click", event => {
        event.stopPropagation();
        addPosItem(productId);
      });
    }
  });
}

async function loadFrequentPosProducts() {
  const section = document.getElementById("pos-frequent-products");
  const container = document.getElementById("pos-frequent-products-list");
  if (!section || !container) return;
  try {
    const response = await fetch("/api/v1/caja/productos-frecuentes", { headers: Auth.getHeaders() });
    if (!response.ok) throw new Error("No se pudieron cargar los productos frecuentes.");
    frequentPosProducts = await response.json();
    const availableProducts = frequentPosProducts
      .map(item => ({ item, product: allProductsPos.find(product => product.id === item.id) }))
      .filter(entry => entry.product);
    section.style.display = availableProducts.length ? "block" : "none";
    container.replaceChildren(...availableProducts.map(({ item, product }) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "mc-mode-btn";
      button.textContent = `${product.nombre} · ${item.unidades_vendidas} ventas`;
      button.addEventListener("click", () => addPosItemDirect(product.id));
      return button;
    }));
  } catch (error) {
    console.error(error);
    section.style.display = "none";
  }
}

// ⚡ ADICIÓN ULTRA RÁPIDA DE 1-CLIC DIRECTO AL TICKET DE CAJA (SIN MODALES NI ESPERAS)
function addPosItemDirect(prodId) {
  const p = allProductsPos.find(item => String(item.id) === String(prodId));
  if (!p) {
    showToast("Producto no encontrado", "warning");
    return;
  }

  const basePrice = p.precio_promocion || p.precio;

  const existing = posCart.find(i => i.producto_id === p.id && (!i.opciones || i.opciones.length === 0) && !i.observaciones);
  if (existing) {
    existing.cantidad += 1;
    existing.subtotal = existing.cantidad * existing.precio_unitario;
  } else {
    posCart.push({
      producto_id: p.id,
      nombre: p.nombre,
      precio_unitario: basePrice,
      cantidad: 1,
      subtotal: basePrice,
      opciones: [],
      observaciones: ""
    });
  }

  renderPosCart();
  showToast(`⚡ +1 ${p.nombre} al ticket`, "success");
}

/* ==================== MCDONALD'S CUSTOMIZATION MODAL ==================== */
let editingPosItemIndex = null;

function addPosItem(prodId) {
  const p = allProductsPos.find(item => String(item.id) === String(prodId));
  if (!p) {
    showToast("No se pudo cargar el producto para personalizarlo.", "danger");
    return;
  }

  editingPosItemIndex = null;
  currentCustomizingProduct = p;
  currentCustomizingQty = 1;
  renderPosCustomization(p, [], [], "");
  openModal("pos-customization-modal");
}

function parsePosProductList(value) {
  if (!value) return [];
  try {
    const parsed = typeof value === "string" ? JSON.parse(value) : value;
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error("La configuración de personalización del producto no es válida.", error);
    return [];
  }
}

function renderPosCustomization(product, selectedOptions, selectedExtras, notes) {
  document.getElementById("pos-cust-title").textContent = `🛠️ PERSONALIZAR: ${product.nombre}`;
  document.getElementById("pos-cust-desc").textContent = product.descripcion || "";
  document.getElementById("pos-cust-img").src = product.imagen_url || "";
  document.getElementById("pos-cust-price").innerHTML = formatPriceDual(product.precio_promocion || product.precio || 0);
  document.getElementById("pos-cust-qty").textContent = String(currentCustomizingQty);
  document.getElementById("pos-cust-notes").value = notes || "";

  const ingredients = parsePosProductList(product.ingredientes_json)
    .filter(ingredient => typeof ingredient === "string");
  let html = "";
  if (ingredients.length) {
    html += `<div style="font-weight:800;color:var(--gold-accent);font-size:.85rem;margin-bottom:.4rem">❌ REMOVER INGREDIENTES</div>`;
    html += ingredients.map(ingredient => {
      const option = `Sin ${ingredient}`;
      const checked = selectedOptions.includes(option) ? "checked" : "";
      return `<label style="display:flex;align-items:center;justify-content:space-between;font-size:.8rem;margin-bottom:.4rem;cursor:pointer;color:#fff">
        <span>${escapeCajaHtml(option)}</span><input type="checkbox" class="pos-dyn-ing-no" value="${escapeCajaHtml(option)}" ${checked}>
      </label>`;
    }).join("");
  }

  const extras = parsePosProductList(product.extras_json).filter(extra =>
    extra && typeof extra.nombre === "string" && Number.isFinite(Number(extra.precio)) && Number(extra.precio) >= 0
  );
  if (extras.length) {
    html += `<div style="font-weight:800;color:var(--gold-accent);font-size:.85rem;margin:.8rem 0 .4rem">🧀 EXTRAS OPCIONALES</div>`;
    html += extras.map(extra => {
      const checked = selectedExtras.includes(extra.nombre) ? "checked" : "";
      return `<label style="display:flex;align-items:center;justify-content:space-between;font-size:.8rem;margin-bottom:.4rem;cursor:pointer;color:#fff">
        <span>${escapeCajaHtml(extra.nombre)} (+${formatPriceDual(Number(extra.precio))})</span>
        <input type="checkbox" class="pos-dyn-extra" value="${escapeCajaHtml(extra.nombre)}" ${checked}>
      </label>`;
    }).join("");
  } else {
    html += `<p style="color:var(--text-muted);font-size:.8rem">Este producto no tiene extras configurados.</p>`;
  }
  document.getElementById("pos-cust-ingredients-container").innerHTML = html;
}

function openEditTicketItemModal(idx) {
  const item = posCart[idx];
  if (!item) {
    showToast("El producto ya no está en el ticket. Actualiza el pedido e inténtalo de nuevo.", "warning");
    return;
  }

  editingPosItemIndex = idx;
  const p = allProductsPos.find(prod => String(prod.id) === String(item.producto_id));
  if (!p) {
    showToast("No se pudo cargar la configuración actual del producto.", "danger");
    return;
  }
  currentCustomizingProduct = p;
  currentCustomizingQty = item.cantidad;
  renderPosCustomization(p, item.opciones || [], item.extras || [], item.observaciones || "");
  openModal("pos-customization-modal");
}

function adjustPosCustQty(delta) {
  currentCustomizingQty = Math.max(1, currentCustomizingQty + delta);
  document.getElementById("pos-cust-qty").innerText = currentCustomizingQty;
}

function confirmAddPosCustomizedItem() {
  if (!currentCustomizingProduct) return;

  const basePrice = currentCustomizingProduct.precio_promocion || currentCustomizingProduct.precio || 0;
  let opts = [];
  const selectedExtras = [];

  document.querySelectorAll(".pos-dyn-ing-no:checked").forEach(cb => {
    opts.push(cb.value);
  });
  document.querySelectorAll(".pos-dyn-extra:checked").forEach(input => selectedExtras.push(input.value));
  const configuredExtras = parsePosProductList(currentCustomizingProduct.extras_json);
    const configuredPrices = new Map(configuredExtras.map(extra => [extra.nombre, Number(extra.precio)]));
  if (selectedExtras.some(name => !configuredPrices.has(name))) {
    showToast("Uno de los extras ya no está disponible. Actualiza el menú e inténtalo de nuevo.", "danger");
    return;
  }
  const extraPrice = selectedExtras.reduce((sum, name) => sum + configuredPrices.get(name), 0);

  const notes = document.getElementById("pos-cust-notes")?.value.trim();
  const unitPrice = basePrice + extraPrice;

  if (editingPosItemIndex !== null && posCart[editingPosItemIndex]) {
    posCart[editingPosItemIndex].cantidad = currentCustomizingQty;
    posCart[editingPosItemIndex].precio_unitario = unitPrice;
    posCart[editingPosItemIndex].subtotal = unitPrice * currentCustomizingQty;
    posCart[editingPosItemIndex].opciones = opts;
    posCart[editingPosItemIndex].extras = selectedExtras;
    posCart[editingPosItemIndex].observaciones = notes;
    editingPosItemIndex = null;
  } else {
    posCart.push({
      producto_id: currentCustomizingProduct.id,
      nombre: currentCustomizingProduct.nombre,
      precio_unitario: unitPrice,
      cantidad: currentCustomizingQty,
      subtotal: unitPrice * currentCustomizingQty,
      opciones: opts,
      extras: selectedExtras,
      observaciones: notes
    });
  }

  closeModal("pos-customization-modal");
  renderPosTicket();
  showToast("⚙️ Personalización guardada en el ticket", "success");
}

function renderPosCart() {
  renderPosTicket();
}

/* ==================== ACTIVE TICKET & CART LOGIC ==================== */
function setPosOrderType(type) {
  currentOrderType = type;
  document.getElementById("type-btn-llevar").classList.toggle("active", type === 'llevar');
  document.getElementById("type-btn-mesa").classList.toggle("active", type === 'mesa');
  document.getElementById("type-btn-delivery").classList.toggle("active", type === 'delivery');

  const mesaInput = document.getElementById("pos-mesa-input");
  if (type === 'llevar') mesaInput.value = "Mostrador";
  else if (type === 'delivery') mesaInput.value = "Delivery A Domicilio";
  else mesaInput.value = "Mesa 1";
  document.getElementById("pos-delivery-details").hidden = type !== "delivery";

  renderPosTicket();
}

function setPosPaymentMethod(method) {
  if (method === "Pago Móvil" && tasaCambioBs === null) {
    showToast("Pago Móvil requiere una tasa BCV válida para cobrar en bolívares.", "warning");
    return;
  }
  currentPaymentMethod = method === "Tarjeta" ? "Punto de Venta" : method;
  document.getElementById("pay-btn-Efectivo").classList.toggle("active", method === 'Efectivo');
  document.getElementById("pay-btn-Tarjeta").classList.toggle("active", method === 'Tarjeta' || method === "Punto de Venta");
  document.getElementById("pay-btn-Pago Móvil").classList.toggle("active", method === 'Pago Móvil');
  if (method === "Pago Móvil" && tasaCambioBs !== null) {
    document.getElementById("pos-currency-select").value = "VES";
  }
  calcPosChange();
}

function updatePosItemQty(idx, delta) {
  posCart[idx].cantidad += delta;
  if (posCart[idx].cantidad <= 0) {
    posCart.splice(idx, 1);
  } else {
    posCart[idx].subtotal = posCart[idx].cantidad * posCart[idx].precio_unitario;
  }
  renderPosTicket();
}

function removePosItem(idx) {
  posCart.splice(idx, 1);
  renderPosTicket();
}

function clearPosCart() {
  posCart = [];
  renderPosTicket();
}

function renderPosTicket() {
  const container = document.getElementById("pos-ticket-items-list");
  if (posCart.length === 0) {
    if (container) container.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size: 0.8rem; padding: 2rem 0;">Toca productos a la izquierda para armar el pedido presencial.</p>`;
    if (document.getElementById("pos-subtotal")) document.getElementById("pos-subtotal").innerHTML = "$0.00";
    if (document.getElementById("pos-tax")) document.getElementById("pos-tax").innerHTML = "$0.00";
    if (document.getElementById("pos-extra")) document.getElementById("pos-extra").innerHTML = "$0.00";
    if (document.getElementById("pos-total")) document.getElementById("pos-total").innerHTML = "$0.00";
    if (document.getElementById("pos-received-input")) document.getElementById("pos-received-input").value = "";
    if (document.getElementById("pos-change-lbl")) document.getElementById("pos-change-lbl").textContent = "Cambio: $0.00";
    return;
  }

  let subtotal = 0.0;
  let html = "";
  posCart.forEach((item, idx) => {
    subtotal += item.subtotal;
    html += `
      <div class="mc-ticket-row" style="background: rgba(255,255,255,0.03); border: 1px solid var(--toon-border); border-radius: 8px; padding: 0.5rem; margin-bottom: 0.4rem;">
        <div style="flex: 1;">
          <strong style="color: #fff; font-size: 0.88rem;">${item.nombre}</strong><br>
          ${item.opciones && item.opciones.length > 0 ? `<small style="color: var(--gold-accent); font-weight: 800; display: block; margin: 0.15rem 0;">⚙️ ${item.opciones.join(', ')}</small>` : ''}
          <small style="color: var(--text-muted);">${formatPriceDual(item.precio_unitario)} x ${item.cantidad}</small><br>
          <button style="background: rgba(0,245,212,0.1); border: 1px solid var(--cyan-accent); color: var(--cyan-accent); border-radius: 6px; font-size: 0.72rem; padding: 0.15rem 0.45rem; font-weight: 800; margin-top: 0.25rem; cursor: pointer;" onclick="openEditTicketItemModal(${idx})">🛠️ Personalizar / Nota</button>
        </div>
        <div style="display: flex; align-items: center; gap: 0.35rem;">
          <button style="background: rgba(255,255,255,0.1); border: none; color: #fff; border-radius: 4px; padding: 0.15rem 0.45rem; cursor: pointer; font-weight: bold;" onclick="updatePosItemQty(${idx}, -1)">-</button>
          <strong style="font-size: 0.95rem; color: #fff;">${item.cantidad}</strong>
          <button style="background: rgba(255,255,255,0.1); border: none; color: #fff; border-radius: 4px; padding: 0.15rem 0.45rem; cursor: pointer; font-weight: bold;" onclick="updatePosItemQty(${idx}, 1)">+</button>
          <button style="background: transparent; border: none; color: var(--neon-red); font-size: 1.2rem; cursor: pointer; margin-left: 0.2rem;" onclick="removePosItem(${idx})">&times;</button>
        </div>
      </div>
    `;
  });

  const tax = subtotal * (posTaxRate / 100);
  const extraFee = getPosExtraFee();
  const tipAmount = Math.round(subtotal * (posTipPct / 100) * 100) / 100;
  const total = subtotal + tax + extraFee + tipAmount;

  if (container) container.innerHTML = html;
  if (document.getElementById("pos-subtotal")) document.getElementById("pos-subtotal").innerHTML = formatPriceDual(subtotal);
  if (document.getElementById("pos-tax")) document.getElementById("pos-tax").innerHTML = formatPriceDual(tax);
  if (document.getElementById("pos-extra")) document.getElementById("pos-extra").innerHTML = formatPriceDual(extraFee);
  if (document.getElementById("pos-tip-display")) document.getElementById("pos-tip-display").innerHTML = formatPriceDual(tipAmount);
  if (document.getElementById("pos-total")) document.getElementById("pos-total").innerHTML = formatPriceDual(total);

  calcPosChange();
}

function setPosTipPct(pct) {
  posTipPct = Number(pct) || 0;
  renderPosTicket();
}

function getPosCurrentTotalDue() {
  const subtotal = posCart.reduce((sum, item) => sum + item.subtotal, 0);
  const tax = subtotal * (posTaxRate / 100);
  const extraFee = getPosExtraFee();
  const tipAmount = Math.round(subtotal * (posTipPct / 100) * 100) / 100;
  return subtotal + tax + extraFee + tipAmount;
}

function setPosExactCash() {
  const total = getPosCurrentTotalDue();
  const currency = document.getElementById("pos-currency-select")?.value || "USD";
  const due = currency === "VES" && tasaCambioBs ? total * tasaCambioBs : total;
  const input = document.getElementById("pos-received-input");
  if (input) {
    input.value = due.toFixed(2);
    calcPosChange();
  }
}

function setPosQuickCash(billAmount) {
  const input = document.getElementById("pos-received-input");
  if (input) {
    input.value = Number(billAmount).toFixed(2);
    calcPosChange();
  }
}

function calcPosChange() {
  const total = getPosCurrentTotalDue();

  const currency = document.getElementById("pos-currency-select")?.value || "USD";
  const received = Number.parseFloat(document.getElementById("pos-received-input")?.value || "0");
  const receivedLabel = document.getElementById("pos-received-label");
  const changeLabel = document.getElementById("pos-change-lbl");
  if (receivedLabel) receivedLabel.textContent = `Monto recibido (${currency === "VES" ? "Bs." : "USD"}):`;
  if (currency === "VES" && (!Number.isFinite(tasaCambioBs) || tasaCambioBs <= 0)) {
    if (changeLabel) changeLabel.textContent = "Tasa BCV no disponible";
    return;
  }
  const totalDue = currency === "VES" ? total * tasaCambioBs : total;
  const change = Math.max(0, (Number.isFinite(received) ? received : 0) - totalDue);
  const changeText = currency === "VES"
    ? `Bs. ${change.toFixed(2)} ($${(change / tasaCambioBs).toFixed(2)})`
    : `$${change.toFixed(2)}${tasaCambioBs ? ` (Bs. ${(change * tasaCambioBs).toFixed(2)})` : ""}`;
  if (changeLabel) changeLabel.textContent = `Cambio: ${changeText}`;
}

function getPosExtraFee() {
  if (currentOrderType === "llevar") return posPackageFee;
  if (currentOrderType === "delivery") return posDeliveryFee;
  return 0;
}

async function submitPosOrderFast() {
  if (isSubmittingPosFast) return;
  if (posCart.length === 0) {
    showToast("Toca al menos 1 producto para armar el pedido presencial.", "warning");
    return;
  }

  const subtotal = posCart.reduce((sum, item) => sum + item.subtotal, 0);
  const tax = subtotal * (posTaxRate / 100);
  const extraFee = getPosExtraFee();
  const tipAmount = Math.round(subtotal * (posTipPct / 100) * 100) / 100;
  const total = subtotal + tax + extraFee + tipAmount;
  const currency = document.getElementById("pos-currency-select")?.value || "USD";
  if (currentPaymentMethod === "Pago Móvil" && currency !== "VES") {
    showToast("Pago Móvil debe cobrarse en bolívares.", "warning");
    return;
  }
  if (currency === "VES" && tasaCambioBs === null) {
    showToast("No hay una tasa BCV válida para cobrar en bolívares.", "warning");
    return;
  }
  const totalDue = currency === "VES" ? total * tasaCambioBs : total;
  const selectedCustomerName = selectedCustomerPos ? (selectedCustomerPos.nombre || selectedCustomerPos.name || "") : "";
  const selectedCustomerPhone = selectedCustomerPos?.telefono || "";
  const mesa = document.getElementById("pos-mesa-input")?.value || "Mostrador";
  const deliveryName = document.getElementById("pos-delivery-name")?.value.trim() || selectedCustomerName;
  const deliveryAddress = document.getElementById("pos-delivery-address")?.value.trim() || "";
  const deliveryPhone = document.getElementById("pos-delivery-phone")?.value.trim() || selectedCustomerPhone;
  const received = Number.parseFloat(document.getElementById("pos-received-input")?.value || "0");
  if (currentOrderType === "delivery" && (!deliveryName || !deliveryAddress || !deliveryPhone)) {
    showToast("Para crear un delivery indica nombre, dirección y teléfono de contacto.", "warning");
    return;
  }
  if (!Number.isFinite(received) || received < totalDue) {
    showToast(`El monto recibido debe ser al menos ${currency === "VES" ? "Bs. " : "$"}${totalDue.toFixed(2)}.`, "warning");
    return;
  }

  const posPromoMap = new Map();
  const seenSeqs = new Set();
  posCart.forEach(item => {
    if (item.promo_id && item.promo_bundle_seq && !seenSeqs.has(item.promo_bundle_seq)) {
      seenSeqs.add(item.promo_bundle_seq);
      posPromoMap.set(Number(item.promo_id), (posPromoMap.get(Number(item.promo_id)) || 0) + 1);
    }
  });
  const payload = {
    numero_mesa: mesa,
    tipo: currentOrderType,
    metodo_pago: currentPaymentMethod,
    moneda_pago: currency,
    cliente_id: selectedCustomerPos ? Number(selectedCustomerPos.id) : null,
    monto_recibido: received,
    propina: tipAmount,
    nit_cliente: document.getElementById("pay-nit-input")?.value.trim() || "CF",
    nombre_factura: currentOrderType === "delivery"
      ? deliveryName
      : document.getElementById("pay-nombre-input")?.value.trim()
        || (selectedCustomerName || "Consumidor Final"),
    nombre_cliente_delivery: currentOrderType === "delivery"
      ? deliveryName
      : (selectedCustomerName || "Cliente Presencial"),
    telefono_delivery: currentOrderType === "delivery"
      ? deliveryPhone
      : (selectedCustomerPhone || null),
    direccion_delivery: currentOrderType === "delivery" ? deliveryAddress : null,
    detalles: posCart.map(item => ({
      producto_id: item.producto_id,
      cantidad: item.cantidad,
      personalizaciones: {
        opciones: item.opciones.filter(option => !String(option).startsWith("Nota: ")),
        extras: item.extras || [],
      },
      observaciones: item.observaciones || null,
    })),
    promociones: Array.from(posPromoMap.entries()).map(([promocion_id, cantidad]) => ({ promocion_id, cantidad }))
  };

  isSubmittingPosFast = true;
  const submitBtn = document.querySelector('button[onclick="submitPosOrderFast()"]');
  if (submitBtn) submitBtn.disabled = true;
  try {
    const res = await fetch("/api/v1/caja/crear-y-cobrar-rapido", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "Error al registrar comanda en caja");
    }
    const result = await res.json();
    posCart = [];
    renderPosTicket();
    const changeCurrency = result.moneda_pago === "VES" ? "Bs. " : "$";
    const deliveryCode = result.codigo_otp ? ` Código de entrega: ${result.codigo_otp}.` : "";
    const pickupCode = result.codigo_retiro ? ` Código de retiro: ${result.codigo_retiro}.` : "";
    showToast(`Factura ${result.factura_numero} emitida. Cambio: ${changeCurrency}${Number(result.cambio).toFixed(2)}.${deliveryCode}${pickupCode}`, "success");
    await Promise.all([loadShiftStatus(), loadPendingOrders(), loadPaidOrders(), loadPickupOrders()]);
    viewReceipt(result.pedido_id);
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    isSubmittingPosFast = false;
    if (submitBtn) submitBtn.disabled = false;
  }
}

/* ==================== SHIFT & QUEUE LOADERS ==================== */
async function loadShiftStatus() {
  try {
    const res = await fetch("/api/v1/caja/turno-activo", { headers: Auth.getHeaders() });
    if (res.ok) {
      activeShift = await res.json();
      renderShiftBar(true);
    } else {
      activeShift = null;
      renderShiftBar(false);
    }
  } catch (err) {
    activeShift = null;
    renderShiftBar(false);
  }
}

function renderShiftBar(isOpen) {
  const labelNumber = document.getElementById("shift-number-label");
  const labelSales = document.getElementById("shift-sales-label");
  const actionsContainer = document.getElementById("shift-actions");

  if (isOpen && activeShift) {
    labelNumber.innerText = `Turno #${activeShift.numero_turno} Activo`;
    labelSales.innerHTML = `Ventas: ${formatPriceDual(activeShift.total_ventas)} (${activeShift.total_pedidos} cobrados) · Efectivo esperado: $${Number(activeShift.efectivo_esperado || activeShift.monto_apertura).toFixed(2)}`;
    actionsContainer.innerHTML = `
      <button class="btn-gold" style="background: var(--mc-red); color: #fff; border-color: var(--mc-red); font-size: 0.75rem;" onclick="submitCerrarTurno()">🔴 CERRAR TURNO</button>
      <button class="btn-gold" style="font-size:0.75rem" onclick="openCashExpenseModal()">➖ REGISTRAR EGRESO</button>
      <button class="btn btn-outline" style="font-size:0.75rem" onclick="printCorteX()">📊 CORTE X</button>
    `;
  } else {
    labelNumber.innerText = "Caja: CERRADA";
    labelSales.innerText = "Debe abrir turno";
    actionsContainer.innerHTML = `
      <button class="btn-gold" style="font-size: 0.75rem;" onclick="openModal('open-shift-modal')">🟢 ABRIR TURNO DE CAJA</button>
    `;
  }
}

async function loadPendingOrders() {
  try {
    const res = await fetch("/api/v1/caja/pedidos-pendientes", { headers: Auth.getHeaders() });
    if (res.ok) {
      pendingOrders = await res.json();
      renderPendingOrders();
      renderAppPaymentsQueue();
      renderDeliverysQueue();
    }
  } catch (err) {
    console.error(err);
  }
}

let currentQueueSearchQuery = "";

function searchPosQueueLive() {
  const input = document.getElementById("pos-queue-search-input");
  if (input) {
    currentQueueSearchQuery = input.value.trim().toLowerCase();
  }
  renderPendingOrders();
}

function renderPendingOrders() {
  const queueButton = document.getElementById("view-btn-queue");
  if (queueButton) {
    queueButton.textContent = `🧾 CUENTAS Y PAGOS POR COBRAR (${pendingOrders.length})`;
  }

  const container = document.getElementById("pending-orders-list");
  if (!container) return;

  let queueOrders = pendingOrders;

  // Filtrar con la barra de búsqueda en tiempo real por ID (#104), Código cliente (CLI-XXXX) o Nombre
  if (currentQueueSearchQuery && currentQueueSearchQuery.length > 0) {
    const q = currentQueueSearchQuery.replace("#", "").replace("cli-", "").trim();
    queueOrders = queueOrders.filter(o => {
      const matchId = String(o.id) === q || String(o.id).includes(q);
      const matchMesa = (o.numero_mesa || '').toLowerCase().includes(q);
      const matchCliente = (o.nombre_cliente_delivery || o.nombre_factura || '').toLowerCase().includes(q);
      const matchMetodo = (o.metodo_pago || '').toLowerCase().includes(q);
      const matchCliCode = (o.usuario_id ? `cli-${String(o.usuario_id).padStart(4, '0')}` : '').includes(q);
      return matchId || matchMesa || matchCliente || matchMetodo || matchCliCode;
    });
  }

  if (document.getElementById("pending-count")) {
    document.getElementById("pending-count").innerText = `${queueOrders.length} En Espera`;
  }

  if (queueOrders.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem; background: var(--toon-card); border-radius: var(--radius-md);">
        <span style="font-size: 2.5rem;">🔎</span>
        <h3 style="color: #fff; margin-top: 0.5rem;">No hay cuentas o pagos pendientes que coincidan</h3>
        <p style="font-size: 0.85rem;">Intenta buscar por otro ID (#104), código de cliente o nombre.</p>
      </div>
    `;
    return;
  }

  let html = "";
  queueOrders.forEach(o => {
    const isPagoMovil = o.metodo_pago && o.metodo_pago.includes("Pago Móvil");
    const isCuentaAbierta = o.modo_pago === "PAGAR_DESPUES";

    // Formatear Lista de Productos Detallados con Precios
    let itemsHtml = "";
    if (o.detalles && o.detalles.length > 0) {
      itemsHtml = o.detalles.map(d => {
        const prodName = d.producto ? d.producto.nombre : (d.nombre || 'Producto');
        const opts = d.personalizaciones ? (typeof d.personalizaciones === 'string' ? d.personalizaciones : JSON.stringify(d.personalizaciones)) : '';
        return `
          <div style="display: flex; justify-content: space-between; font-size: 0.83rem; margin-bottom: 0.25rem;">
            <span style="color: #fff;"><strong>${d.cantidad}x</strong> ${prodName} ${opts ? `<small style="color: var(--gold-accent);">(${opts})</small>` : ''}</span>
            <span style="color: var(--gold-accent); font-weight: 800;">$${(parseFloat(d.subtotal || (d.precio_unitario * d.cantidad))).toFixed(2)}</span>
          </div>
        `;
      }).join('');
    } else {
      itemsHtml = `<span style="font-size: 0.8rem; color: var(--text-muted);">Sin detalles de renglones.</span>`;
    }

    const clientCode = o.usuario_id ? `CLI-${String(o.usuario_id).padStart(4, '0')}` : 'CLIENTE CASUAL';
    const clientName = escapeCajaHtml(o.nombre_cliente_delivery || o.nombre_factura || 'Consumidor Final');

    html += `
      <div class="card fade-in" style="background: var(--toon-card); border: 2px solid ${isPagoMovil ? 'var(--cyan-accent)' : 'var(--gold-accent)'}; border-radius: var(--radius-md); padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <!-- Cabecera de la Tarjeta con ID destacado y Badge -->
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
            <div>
              <div style="font-size: 1.3rem; font-weight: 900; color: #fff; font-family: var(--font-display);">
                ID #${o.id} <span style="font-size: 0.95rem; color: var(--gold-accent);">(${escapeCajaHtml(o.numero_mesa)})</span>
              </div>
              <small style="color: var(--cyan-accent); font-size: 0.75rem; font-weight: 800;">👤 ${clientName} • <span style="color: var(--gold-accent);">${clientCode}</span></small>
            </div>
            <span class="badge" style="background: ${isCuentaAbierta ? 'var(--cyan-accent)' : 'var(--gold-gradient)'}; color: #000; font-weight: 900; font-size: 0.72rem; padding: 0.25rem 0.55rem; border-radius: 6px;">
              ${isCuentaAbierta ? '🧾 CUENTA ABIERTA' : (isPagoMovil ? '📱 REFERENCIA POR VALIDAR' : '⚡ POR COBRAR')}
            </span>
          </div>

          <!-- Bloque de Detalle de Productos -->
          <div style="background: rgba(0,0,0,0.3); border: 1px dashed var(--toon-border); border-radius: 8px; padding: 0.75rem; margin-bottom: 0.85rem; max-height: 140px; overflow-y: auto;">
            <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 800; text-transform: uppercase; margin-bottom: 0.35rem; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 0.25rem;">
              📦 DETALLE DEL PEDIDO (${o.detalles ? o.detalles.length : 0} ITEMS):
            </div>
            ${itemsHtml}
          </div>

          <!-- Método de Pago / Referencia -->
          <div style="background: rgba(0,245,212,0.06); border: 1px solid var(--cyan-accent); border-radius: 8px; padding: 0.5rem 0.75rem; margin-bottom: 0.85rem;">
            <small style="color: var(--cyan-accent); font-weight: 800; display: block; font-size: 0.72rem;">FORMA DE PAGO SELECCIONADA:</small>
            <div style="font-size: 0.88rem; font-weight: 900; color: #fff;">${escapeCajaHtml(o.metodo_pago || 'Confirmación en Caja POS')}</div>
          </div>
        </div>

        <!-- Pie de la Tarjeta con Total Dual y Botón de Cobro -->
        <div style="border-top: 1px solid var(--toon-border); padding-top: 0.75rem; margin-top: 0.5rem; display: flex; justify-content: space-between; align-items: center; gap: 0.5rem;">
          <div>
            <small style="color: var(--text-muted); font-size: 0.7rem; font-weight: 800; display: block;">TOTAL NETO:</small>
            <div style="font-size: 1.25rem; font-weight: 900; color: var(--gold-accent); line-height: 1;">${formatPriceDual(o.total)}</div>
          </div>
          ${o.estado_pago === "PENDIENTE_VALIDACION"
            ? `<button class="btn btn-outline" style="padding: 0.6rem 1.1rem; font-size: 0.88rem; font-weight: 900;" onclick="switchPosMainView('app-payments')">📱 Validar Pago Móvil</button>`
            : `<div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
                ${o.estado_pago === "PENDIENTE" ? `<button type="button" class="btn btn-outline" style="padding:0.55rem 0.7rem;font-size:0.78rem;font-weight:800;" onclick="openSplitBillModal(${o.id})">⚖️ Dividir</button>` : ""}
                <button class="btn btn-cta" style="padding: 0.6rem 1.1rem; font-size: 0.88rem; font-weight: 900;" onclick="openPayModal(${o.id})">💳 COBRAR #${o.id}</button>
              </div>`}
        </div>
      </div>
    `;
  });
  container.innerHTML = html;
}

async function loadPaidOrders() {
  try {
    const res = await fetch("/api/v1/caja/pedidos-cobrados", { headers: Auth.getHeaders() });
    if (res.ok) {
      paidOrders = await res.json();
      renderPaidOrders();
      renderDeliverysQueue();
    }
  } catch (err) {
    console.error(err);
  }
}

let currentHistoryPaymentFilter = "ALL";

function filterPaidOrdersByPaymentMethod() {
  const select = document.getElementById("pos-history-payment-filter");
  if (select) {
    currentHistoryPaymentFilter = select.value;
  }
  renderPaidOrders();
}

function renderPaidOrders() {
  const tbody = document.getElementById("paid-orders-tbody");
  if (!tbody) return;

  let filtered = paidOrders;
  if (currentHistoryPaymentFilter !== "ALL") {
    filtered = paidOrders.filter(o => {
      const method = (o.metodo_pago || "").toLowerCase();
      const target = currentHistoryPaymentFilter.toLowerCase();
      return method.includes(target);
    });
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No hay facturas emitidas con el filtro '${escapeCajaHtml(currentHistoryPaymentFilter)}'.</td></tr>`;
    return;
  }

  let html = "";
  filtered.forEach(o => {
    const facNum = o.factura_numero || `FAC-DD-${o.id}`;
    html += `
      <tr style="border-bottom: 1px solid var(--toon-border);">
        <td style="padding: 0.75rem;"><strong style="color: var(--mc-yellow);">${facNum}</strong></td>
        <td style="padding: 0.75rem;">${escapeCajaHtml(o.numero_mesa)}</td>
        <td style="padding: 0.75rem;"><span class="badge" style="background: rgba(255,255,255,0.1); color: var(--gold-accent); font-weight: 800;">${o.metodo_pago || 'Efectivo'}</span></td>
        <td style="padding: 0.75rem; font-weight: 900;">${formatPriceDual(o.total)}</td>
        <td style="padding: 0.75rem;"><button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="viewReceipt(${o.id})">📄 FACTURA TICKET</button></td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}



async function submitAbrirTurno() {
  const rawAmount = document.getElementById("monto-apertura-input").value.trim();
  const monto = Number(rawAmount);
  if (!rawAmount || !Number.isFinite(monto) || monto < 0) {
    showToast("Ingresa un monto inicial válido en USD equivalente.", "warning");
    return;
  }
  try {
    const res = await fetch("/api/v1/caja/abrir-turno", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ monto_apertura: monto })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Error al abrir turno");
    }
    showToast("🟢 Turno de caja abierto correctamente", "success");
    closeModal("open-shift-modal");
    await loadShiftStatus();
    if (resumePaymentAfterShiftOpen && selectedOrderForPayment) {
      resumePaymentAfterShiftOpen = false;
      openPayModal(selectedOrderForPayment.id);
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function submitCerrarTurno() {
  if (!activeShift) return;
  const expected = activeShift.esperado_por_metodo || {};
  document.getElementById("shift-cash-expected").textContent =
    `Esperado: efectivo $${Number(expected["Efectivo"] ?? activeShift.efectivo_esperado ?? 0).toFixed(2)} · pago móvil $${Number(expected["Pago Móvil"] || 0).toFixed(2)} · punto de venta $${Number(expected["Punto de Venta"] || 0).toFixed(2)}.`;
  document.getElementById("monto-cierre-input").value =
    Math.max(0, Number(expected["Efectivo"] ?? activeShift.efectivo_esperado ?? 0)).toFixed(2);
  document.getElementById("cierre-movil-input").value = Math.max(0, Number(expected["Pago Móvil"] || 0)).toFixed(2);
  document.getElementById("cierre-pos-input").value = Math.max(0, Number(expected["Punto de Venta"] || 0)).toFixed(2);
  openModal("close-shift-modal");
}

async function confirmarCerrarTurno() {
  if (isClosingShift) return;
  const rawAmount = document.getElementById("monto-cierre-input").value.trim();
  const amount = Number(rawAmount);
  const mobileAmount = Number(document.getElementById("cierre-movil-input").value);
  const posAmount = Number(document.getElementById("cierre-pos-input").value);
  if (!rawAmount || !Number.isFinite(amount) || amount < 0
      || !Number.isFinite(mobileAmount) || mobileAmount < 0
      || !Number.isFinite(posAmount) || posAmount < 0) {
    showToast("Ingresa montos contados válidos para cada método de pago.", "warning");
    return;
  }
  isClosingShift = true;
  const closeBtn = document.querySelector('button[onclick="confirmarCerrarTurno()"]');
  if (closeBtn) closeBtn.disabled = true;
  try {
    const res = await fetch("/api/v1/caja/cerrar-turno", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({
        monto_cierre: amount,
        arqueo: [
          { metodo_pago: "Efectivo", contado_usd: amount },
          { metodo_pago: "Pago Móvil", contado_usd: mobileAmount },
          { metodo_pago: "Punto de Venta", contado_usd: posAmount }
        ]
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Error al cerrar turno");
    }
    const closedShift = await res.json();
    showToast(`Turno cerrado. Diferencia de caja: $${Number(closedShift.diferencia || 0).toFixed(2)} USD.`, "success");
    closeModal("close-shift-modal");
    await loadShiftStatus();
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    isClosingShift = false;
    if (closeBtn) closeBtn.disabled = false;
  }
}

function openPayModal(orderId) {
  closeModal("pos-customization-modal");

  if (typeof orderId === "object" && orderId !== null) {
    selectedOrderForPayment = orderId;
  } else {
    selectedOrderForPayment = pendingOrders.find(o => String(o.id) === String(orderId) || o.id == orderId);
    if (!selectedOrderForPayment) {
      selectedOrderForPayment = paidOrders.find(o => String(o.id) === String(orderId) || o.id == orderId);
    }
  }

  if (!selectedOrderForPayment) {
    showToast(`No se ubican detalles del pedido. Cargando datos...`, "warning");
    return;
  }

  if (document.getElementById("pay-order-id")) document.getElementById("pay-order-id").innerText = `#${selectedOrderForPayment.id}`;
  if (document.getElementById("pay-order-mesa")) document.getElementById("pay-order-mesa").innerText = selectedOrderForPayment.numero_mesa || "Mostrador";
  if (document.getElementById("pay-order-total")) document.getElementById("pay-order-total").innerHTML = formatPriceDual(selectedOrderForPayment.total);
  const methodSelect = document.getElementById("pay-method-select");
  if (methodSelect && ["Efectivo", "Punto de Venta"].includes(selectedOrderForPayment.metodo_pago)) {
    methodSelect.value = selectedOrderForPayment.metodo_pago;
  } else if (methodSelect) {
    methodSelect.value = "Efectivo";
  }
  const currencySelect = document.getElementById("pay-currency-select");
  if (currencySelect) currencySelect.value = "USD";
  const mixedCheck = document.getElementById("pay-mixed-toggle");
  if (mixedCheck) mixedCheck.checked = false;
  toggleMixedPaymentUI();
  updatePaymentCurrencyAmount();
  openModal("payment-modal");
}

function toggleMixedPaymentUI() {
  const checked = Boolean(document.getElementById("pay-mixed-toggle")?.checked);
  const box = document.getElementById("pay-mixed-box");
  if (box) box.hidden = !checked;
  if (checked && selectedOrderForPayment) {
    const half = Math.round((Number(selectedOrderForPayment.total || 0) / 2) * 100) / 100;
    const a1 = document.getElementById("pay-mix-amount-1");
    if (a1) a1.value = half.toFixed(2);
    syncMixedPaymentSecond();
  }
}

function syncMixedPaymentSecond() {
  if (!selectedOrderForPayment) return;
  const total = Number(selectedOrderForPayment.total || 0);
  const a1 = Number.parseFloat(document.getElementById("pay-mix-amount-1")?.value || "0") || 0;
  const rem = Math.max(0, Math.round((total - a1) * 100) / 100);
  const a2 = document.getElementById("pay-mix-amount-2");
  if (a2) a2.value = rem.toFixed(2);
}

function openPaymentModal(orderId) {
  openPayModal(orderId);
}

function updatePaymentCurrencyAmount() {
  if (!selectedOrderForPayment) return;
  const currency = document.getElementById("pay-currency-select")?.value || "USD";
  const receivedInput = document.getElementById("pay-received-input");
  if (receivedInput) {
    const total = currency === "VES" && tasaCambioBs !== null
      ? Number(selectedOrderForPayment.total) * tasaCambioBs
      : Number(selectedOrderForPayment.total);
    receivedInput.value = total.toFixed(2);
  }
  calculateChange();
}

function calculateChange() {
  if (!selectedOrderForPayment) return;
  const received = parseFloat(document.getElementById("pay-received-input").value) || 0;
  const currency = document.getElementById("pay-currency-select")?.value || "USD";
  const rate = tasaCambioBs || 0;
  if (currency === "VES" && rate === 0) {
    document.getElementById("pay-change-display").textContent = "No hay tasa disponible para cobrar en Bs.";
    return;
  }
  const total = currency === "VES" ? selectedOrderForPayment.total * rate : selectedOrderForPayment.total;
  const change = Math.max(0, received - total);
  const label = currency === "VES" ? `Bs. ${change.toFixed(2)}` : `$${change.toFixed(2)}`;
  document.getElementById("pay-change-display").innerHTML = rate > 0
    ? `${label} (${currency === "VES" ? "$" + (change / rate).toFixed(2) : "Bs. " + (change * rate).toFixed(2)})`
    : label;
  const receivedLabel = document.getElementById("pay-received-label");
  if (receivedLabel) receivedLabel.textContent = `Monto recibido (${currency === "VES" ? "Bs." : "USD"})`;
}

async function submitPayment() {
  if (!selectedOrderForPayment || isSubmittingPayment) return;

  const method = document.getElementById("pay-method-select").value;
  const currency = document.getElementById("pay-currency-select").value;
  const received = parseFloat(document.getElementById("pay-received-input").value) || 0;
  const nit = document.getElementById("pay-nit-input").value || "CF";
  const nombre = document.getElementById("pay-nombre-input").value || "Consumidor Final";

  isSubmittingPayment = true;
  const payBtn = document.querySelector('#payment-modal button[onclick="submitPayment()"]');
  if (payBtn) payBtn.disabled = true;
  try {
    if (currency === "VES") {
      try {
        await loadPosConfig();
      } catch (error) {
        showToast(error.message, "danger");
        return;
      }
      if (tasaCambioBs === null) {
        showToast("No hay una tasa BCV válida para cobrar en bolívares.", "warning");
        return;
      }
    }
    const isMixed = Boolean(document.getElementById("pay-mixed-toggle")?.checked);
    let pagosMixtosPayload = null;
    if (isMixed) {
      const m1 = document.getElementById("pay-mix-method-1").value;
      const a1 = Number.parseFloat(document.getElementById("pay-mix-amount-1").value) || 0;
      const m2 = document.getElementById("pay-mix-method-2").value;
      const a2 = Number.parseFloat(document.getElementById("pay-mix-amount-2").value) || 0;
      if (a1 <= 0 || a2 <= 0) {
        showToast("En pago mixto ambos montos deben ser mayores a 0.", "warning");
        return;
      }
      pagosMixtosPayload = [
        { metodo_pago: m1, monto_usd: Math.round(a1 * 100) / 100, moneda: "USD" },
        { metodo_pago: m2, monto_usd: Math.round(a2 * 100) / 100, moneda: "USD" }
      ];
    }

    const totalDue = currency === "VES" ? selectedOrderForPayment.total * tasaCambioBs : selectedOrderForPayment.total;
    if (!isMixed && received < totalDue) {
      showToast(`El monto recibido debe ser al menos ${currency === "VES" ? "Bs. " : "$"}${totalDue.toFixed(2)}`, "warning");
      return;
    }

    const res = await fetch(`/api/v1/caja/pedidos/${selectedOrderForPayment.id}/cobrar`, {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({
        metodo_pago: isMixed ? "Pago Mixto" : method,
        monto_recibido: isMixed ? selectedOrderForPayment.total : received,
        moneda_pago: isMixed ? "USD" : currency,
        nit_cliente: nit,
        nombre_factura: nombre,
        pagos_mixtos: pagosMixtosPayload
      })
    });

    if (!res.ok) {
      const err = await res.json();
      const detail = typeof err.detail === "string" ? err.detail : "Error al procesar el cobro.";
      if (res.status === 403) {
        throw new Error("Tu sesión no tiene permiso para cobrar. Inicia sesión con una cuenta de Caja, supervisor o administrador.");
      }
      if (res.status === 409 && detail.toLowerCase().includes("turno de caja")) {
        resumePaymentAfterShiftOpen = true;
        closeModal("payment-modal");
        openModal("open-shift-modal");
        showToast("La caja no tiene un turno abierto. Abre el turno para continuar con este cobro.", "warning");
        return;
      }
      throw new Error(detail);
    }

    const data = await res.json();
    const changeLabel = currency === "VES" ? `Bs. ${data.cambio.toFixed(2)}` : `$${data.cambio.toFixed(2)}`;
    showToast(data.repetido
      ? `Este cobro ya estaba confirmado (${data.factura_numero}); no se registró otra venta.`
      : `✅ Factura emitida ${data.factura_numero} (Cambio: ${changeLabel})`, "success");
    
    loadShiftStatus();
    loadPendingOrders();
    loadPaidOrders();
    closeModal("payment-modal");
    viewReceipt(selectedOrderForPayment.id);
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    isSubmittingPayment = false;
    if (payBtn) payBtn.disabled = false;
  }
}

async function viewReceipt(orderId) {
  try {
    const res = await fetch(`/api/v1/caja/pedidos/${orderId}/factura`, { headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("Error al obtener la factura");
    const fac = await res.json();
    const invoiceRateValue = Number(fac.tasa_cambio_pago) || tasaCambioBs;
    const invoiceHasRate = Number.isFinite(invoiceRateValue) && invoiceRateValue > 0;
    const invoiceCurrency = fac.moneda_pago === "VES" ? "VES" : "USD";
    const currencyLabel = invoiceCurrency === "VES" ? "Bs. " : "$";
    const dualAmount = amount => invoiceHasRate
      ? `$${Number(amount).toFixed(2)} (Bs. ${(Number(amount) * invoiceRateValue).toFixed(2)})`
      : `$${Number(amount).toFixed(2)}`;

    let itemsHtml = "";
    fac.detalles.forEach(d => {
      itemsHtml += `
        <tr>
          <td>${escapeCajaHtml(d.cantidad)}x ${escapeCajaHtml(d.producto)}</td>
          <td style="text-align: right;">${dualAmount(d.subtotal)}</td>
        </tr>
      `;
    });

    const ticketHtml = `
      <div class="factura-header">
        <h2 style="margin: 0; font-size: 1.2rem;">${escapeCajaHtml(fac.restaurante)}</h2>
        <div style="font-size: 0.8rem;">NIT: ${escapeCajaHtml(fac.nit_emisor)}${invoiceHasRate ? ` | Tasa aplicada: Bs. ${invoiceRateValue.toFixed(4)}/USD` : ""}</div>
        <div style="font-weight: bold; margin-top: 0.5rem;">FACTURA: ${escapeCajaHtml(fac.factura_numero)}</div>
        <div style="font-size: 0.75rem; color: #555;">${escapeCajaHtml(String(fac.fecha).substring(0, 19))}</div>
      </div>
      <div style="font-size: 0.8rem; margin-bottom: 0.5rem;">
        <div><strong>CLIENTE:</strong> ${escapeCajaHtml(fac.nombre_factura)}</div>
        <div><strong>NIT:</strong> ${escapeCajaHtml(fac.nit_cliente)}</div>
        <div><strong>UBICACIÓN:</strong> ${escapeCajaHtml(fac.numero_mesa)}</div>
        ${fac.direccion_delivery ? `<div><strong>DIRECCIÓN:</strong> ${escapeCajaHtml(fac.direccion_delivery)}</div>` : ''}
      </div>
      <table class="factura-items">
        <thead>
          <tr style="border-bottom: 1px solid #000;">
            <th>DESCRIPCIÓN</th>
            <th style="text-align: right;">TOTAL</th>
          </tr>
        </thead>
        <tbody>
          ${itemsHtml}
        </tbody>
      </table>
      <div style="border-top: 1px dashed #000; padding-top: 0.5rem; font-size: 0.85rem;">
        <div style="display: flex; justify-content: space-between;"><span>Subtotal:</span><span>${dualAmount(fac.subtotal)}</span></div>
        <div style="display: flex; justify-content: space-between; font-size: 1.1rem; font-weight: bold; margin-top: 0.3rem;" class="factura-total-row">
          <span>TOTAL COMPRA:</span><span>${dualAmount(fac.total)}</span>
        </div>
      </div>
      <div style="font-size: 0.8rem; margin-top: 0.5rem;">
        <div>Método de Pago: ${escapeCajaHtml(fac.metodo_pago)}</div>
        <div>Monto recibido: ${currencyLabel}${Number(fac.monto_recibido).toFixed(2)}</div>
        <div>Cambio entregado: ${currencyLabel}${Number(fac.cambio).toFixed(2)}${invoiceHasRate ? ` (${invoiceCurrency === "VES" ? "$" + (Number(fac.cambio) / invoiceRateValue).toFixed(2) : "Bs. " + (Number(fac.cambio) * invoiceRateValue).toFixed(2)})` : ""}</div>
      </div>
      <div style="text-align: center; margin-top: 1rem; font-size: 0.75rem; font-style: italic;">
        ¡Gracias por su compra en Donde David!
      </div>
    `;

    closeModal("pos-customization-modal");
    closeModal("payment-modal");
    lastPrintedInvoiceMeta = fac;
    document.getElementById("factura-ticket-content").innerHTML = ticketHtml;
    openModal("receipt-modal");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function printCurrentFacturaThermal() {
  const ticketEl = document.getElementById("factura-ticket-content");
  if (!ticketEl || typeof window.printThermalDocument !== "function") {
    window.print();
    return;
  }
  window.printThermalDocument(ticketEl.innerHTML, lastPrintedInvoiceMeta?.factura_numero || "Ticket Caja");
}

async function printCorteX() {
  try {
    const res = await fetch("/api/v1/caja/corte-x", { headers: Auth.getHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "No se pudo generar Corte X.");
    const rows = Object.entries(data.esperado_por_metodo || {}).map(([k, v]) => `
      <div class="dd-thermal-row"><span>${escapeCajaHtml(k)}:</span><strong>$${Number(v).toFixed(2)}</strong></div>
    `).join("");
    const html = `
      <div class="dd-thermal-row"><span>Turno:</span><strong>#${data.numero_turno}</strong></div>
      <div class="dd-thermal-row"><span>Pedidos pagados:</span><strong>${data.total_pedidos}</strong></div>
      <div class="dd-thermal-row"><span>Ventas totales:</span><strong>$${Number(data.total_ventas).toFixed(2)}</strong></div>
      <div class="dd-thermal-row"><span>Propinas:</span><strong>$${Number(data.total_propinas).toFixed(2)}</strong></div>
      <div class="dd-thermal-row"><span>Egresos:</span><strong>-$${Number(data.total_egresos).toFixed(2)}</strong></div>
      <div class="dd-thermal-total">${rows}</div>
    `;
    if (typeof window.printThermalDocument === "function") {
      window.printThermalDocument(html, `CORTE X PARCIAL · TURNO #${data.numero_turno}`);
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function openSplitBillModal(orderId) {
  const order = pendingOrders.find(o => Number(o.id) === Number(orderId));
  if (!order) return;
  selectedSplitOrderId = Number(order.id);
  document.getElementById("split-order-id-label").textContent = String(order.id);
  document.getElementById("split-mode-select").value = "igual";
  document.getElementById("split-parts-input").value = "2";
  const itemsList = document.getElementById("split-items-list");
  if (itemsList) {
    itemsList.innerHTML = (order.detalles || []).map(d => `
      <label class="pos-split-item-row">
        <span><strong>${Number(d.cantidad) || 1}x</strong> ${escapeCajaHtml(d.producto?.nombre || d.nombre || "Producto")}</span>
        <span>
          <strong style="margin-right:0.5rem;">$${Number(d.subtotal || 0).toFixed(2)}</strong>
          <input type="checkbox" class="split-detail-checkbox" value="${Number(d.id)}">
        </span>
      </label>
    `).join("");
  }
  toggleSplitModeFields();
  openModal("split-bill-modal");
}

function toggleSplitModeFields() {
  const mode = document.getElementById("split-mode-select")?.value || "igual";
  const equalEl = document.getElementById("split-equal-fields");
  const itemsEl = document.getElementById("split-items-fields");
  if (equalEl) equalEl.style.display = mode === "igual" ? "block" : "none";
  if (itemsEl) itemsEl.style.display = mode === "items" ? "block" : "none";
}

async function submitSplitBill() {
  if (!selectedSplitOrderId) return;
  const mode = document.getElementById("split-mode-select")?.value || "igual";
  const payload = mode === "igual"
    ? { modo: "igual", partes: parseInt(document.getElementById("split-parts-input")?.value || "2", 10) }
    : {
        modo: "items",
        detalle_ids: Array.from(document.querySelectorAll(".split-detail-checkbox:checked")).map(cb => Number(cb.value))
      };
  try {
    const res = await fetch(`/api/v1/caja/pedidos/${selectedSplitOrderId}/dividir`, {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "No se pudo dividir la cuenta.");
    showToast(data.mensaje || "Cuenta dividida exitosamente.", "success");
    closeModal("split-bill-modal");
    await loadPendingOrders();
  } catch (err) {
    showToast(err.message, "danger");
  }
}
