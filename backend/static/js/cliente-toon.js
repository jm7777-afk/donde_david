let toonProducts = [];
let toonCategories = [];
let toonPromos = [];
let toonCart = [];
let guiaItems = [];
let currentGuiaIndex = 0;
let activeCategoryFilter = null;
let currentSelectedModalProduct = null;
let editingCartIndex = null;
let tasaCambioBs = null;
let checkoutTaxRate = 16;
let checkoutDeliveryFee = 5;
let checkoutPackageFee = 3;
let pagoMovilConfig = {};
let googleMapsApiKey = "";
let currentDetectedMesa = null;
let isTableQrSession = false;
let lastUserOrderItems = [];
let lastUserOrderId = null;
let personalizedProducts = [];
let currentPendingOrderId = null;
let currentTrackingToken = null;
let trackingRefreshTimer = null;
let cachedTrackingProgress = null;
let isSubmittingClientOrder = false;
let clientProgressStorageError = false;
const CLIENT_PROGRESS_STORAGE_KEY = "dd-client-progress-v1";
const CLIENT_SCREEN_IDS = new Set([
  "screen-home",
  "screen-splash",
  "screen-categorias",
  "screen-menu",
  "screen-carrito",
  "screen-checkout-delivery",
  "screen-checkout-summary",
  "screen-checkout",
  "screen-tracking",
  "screen-historial",
  "screen-perfil"
]);

function getClientNetworkStatusElement() {
  return document.getElementById("client-network-status");
}

function updateClientNetworkStatus(isOnline = navigator.onLine) {
  const status = getClientNetworkStatusElement();
  if (!status) return;
  status.hidden = Boolean(isOnline && !clientProgressStorageError);
  if (!status.hidden) {
    const positionBelowHeader = () => {
      const header = document.querySelector("#app-header .universal-header");
      status.style.top = `${header?.getBoundingClientRect().bottom || 0}px`;
    };
    positionBelowHeader();
    requestAnimationFrame(positionBelowHeader);
  }
  if (!isOnline) {
    status.dataset.state = "offline";
    status.textContent = "Sin conexión. Tu carrito y formulario están guardados en este dispositivo; enviar o actualizar pedidos requiere internet.";
  } else if (clientProgressStorageError) {
    status.dataset.state = "offline";
    status.textContent = "No se pudo guardar el progreso en este dispositivo. Mantén esta página abierta para no perder el borrador.";
  }
}

function markClientNetworkFailure(error) {
  if (!navigator.onLine || error instanceof TypeError) updateClientNetworkStatus(false);
}

function getLegacyTrackingValue(key) {
  try {
    return sessionStorage.getItem(key);
  } catch (error) {
    console.warn("No se pudo leer el seguimiento de la sesión anterior.", error);
    return null;
  }
}

function setLegacyTrackingValue(key, value) {
  try {
    sessionStorage.setItem(key, value);
  } catch (error) {
    console.warn("No se pudo guardar el seguimiento temporal del pedido.", error);
  }
}

function removeLegacyTrackingValue(key) {
  try {
    sessionStorage.removeItem(key);
  } catch (error) {
    console.warn("No se pudo limpiar el seguimiento temporal del pedido.", error);
  }
}

function normalizeStoredCartItem(item) {
  const productId = Number(item?.producto_id);
  const quantity = Number(item?.cantidad);
  const unitPrice = Number(item?.precio_unitario);
  const name = typeof item?.nombre === "string" ? item.nombre.trim().slice(0, 160) : "";
  if (!Number.isInteger(productId) || productId <= 0
    || !Number.isInteger(quantity) || quantity <= 0 || quantity > 99
    || !Number.isFinite(unitPrice) || unitPrice < 0
    || !name) return null;

  const safeStringList = value => Array.isArray(value)
    ? value.filter(entry => typeof entry === "string").slice(0, 30).map(entry => entry.slice(0, 200))
    : [];
  return {
    producto_id: productId,
    nombre: name,
    precio_unitario: unitPrice,
    cantidad: quantity,
    subtotal: unitPrice * quantity,
    imagen_url: typeof item.imagen_url === "string" && /^(https:\/\/|\/static\/|\/api\/v1\/cliente\/media\/)/i.test(item.imagen_url)
      ? item.imagen_url.slice(0, 500)
      : "",
    puntos_fidelidad: Math.max(0, Number(item.puntos_fidelidad) || 0),
    opciones: safeStringList(item.opciones),
    extras: safeStringList(item.extras),
    tiempo_preparacion: Math.max(0, Number(item.tiempo_preparacion) || 15)
  };
}

function readClientProgress() {
  try {
    const raw = localStorage.getItem(CLIENT_PROGRESS_STORAGE_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw);
    return saved?.version === 1 ? saved : null;
  } catch (error) {
    clientProgressStorageError = true;
    updateClientNetworkStatus();
    console.warn("No se pudo recuperar el progreso local del cliente.", error);
    return null;
  }
}

function persistClientProgress() {
  try {
    const activeScreen = document.querySelector(".screen.active")?.id;
    const currentGPS = typeof currentCustomerGPS !== "undefined" ? currentCustomerGPS : null;
    localStorage.setItem(CLIENT_PROGRESS_STORAGE_KEY, JSON.stringify({
      version: 1,
      screen: CLIENT_SCREEN_IDS.has(activeScreen) ? activeScreen : "screen-home",
      cart: toonCart.slice(0, 80),
      checkout: {
        type: document.getElementById("checkout-type")?.value || "delivery",
        payment: document.getElementById("checkout-payment")?.value || "Efectivo",
        currency: document.getElementById("checkout-currency")?.value || "USD",
        reference: document.getElementById("checkout-payment-reference")?.value || "",
        deliveryName: document.getElementById("deliv-nombre")?.value || "",
        deliveryPhone: document.getElementById("deliv-telefono")?.value || "",
        deliveryAddress: document.getElementById("deliv-direccion")?.value || "",
        paymentMode: document.querySelector('input[name="modo_pago"]:checked')?.value || "PAGAR_ANTES",
        deliveryCoordinates: currentGPS
          && Number.isFinite(Number(currentGPS.lat))
          && Number.isFinite(Number(currentGPS.lng))
          ? { lat: Number(currentGPS.lat), lng: Number(currentGPS.lng) }
          : null
      },
      tracking: {
        orderId: currentPendingOrderId,
        token: currentTrackingToken,
        progress: cachedTrackingProgress
      }
    }));
  } catch (error) {
    clientProgressStorageError = true;
    updateClientNetworkStatus();
    console.warn("No se pudo guardar el progreso local del cliente.", error);
  }
}

function restoreClientProgress() {
  const saved = readClientProgress() || {};

  toonCart = Array.isArray(saved.cart)
    ? saved.cart.slice(0, 80).map(normalizeStoredCartItem).filter(Boolean)
    : [];

  const checkout = saved.checkout || {};
  const fields = {
    "checkout-type": ["delivery", "llevar", "mesa"].includes(checkout.type) ? checkout.type : "delivery",
    "checkout-payment": ["Pago Móvil", "Efectivo", "Punto de Venta"].includes(checkout.payment) ? checkout.payment : "Efectivo",
    "checkout-currency": ["USD", "VES"].includes(checkout.currency) ? checkout.currency : "USD",
    "checkout-payment-reference": typeof checkout.reference === "string" ? checkout.reference.slice(0, 100) : "",
    "deliv-nombre": typeof checkout.deliveryName === "string" ? checkout.deliveryName.slice(0, 160) : "",
    "deliv-telefono": typeof checkout.deliveryPhone === "string" ? checkout.deliveryPhone.slice(0, 40) : "",
    "deliv-direccion": typeof checkout.deliveryAddress === "string" ? checkout.deliveryAddress.slice(0, 500) : ""
  };
  Object.entries(fields).forEach(([id, value]) => {
    const field = document.getElementById(id);
    if (field) field.value = value;
  });

  if (["PAGAR_ANTES", "PAGAR_DESPUES"].includes(checkout.paymentMode)) {
    selectedMesaPaymentMode = checkout.paymentMode;
    const modeInput = document.querySelector(`input[name="modo_pago"][value="${selectedMesaPaymentMode}"]`);
    if (modeInput) modeInput.checked = true;
  }
  if (checkout.deliveryCoordinates
    && Number.isFinite(Number(checkout.deliveryCoordinates.lat))
    && Number.isFinite(Number(checkout.deliveryCoordinates.lng))) {
    currentCustomerGPS = {
      lat: Number(checkout.deliveryCoordinates.lat),
      lng: Number(checkout.deliveryCoordinates.lng)
    };
  }

  const tracking = saved.tracking || {};
  const orderId = Number(tracking.orderId || getLegacyTrackingValue("dd-tracking-order-id"));
  currentPendingOrderId = Number.isInteger(orderId) && orderId > 0 ? orderId : null;
  currentTrackingToken = typeof tracking.token === "string" && tracking.token
    ? tracking.token
    : getLegacyTrackingValue("dd-tracking-token");
  cachedTrackingProgress = tracking.progress && Number(tracking.progress.orderId) === currentPendingOrderId
    ? tracking.progress
    : null;

  return CLIENT_SCREEN_IDS.has(saved.screen) ? saved.screen : null;
}

function renderCachedTrackingProgress() {
  if (!cachedTrackingProgress || !currentPendingOrderId) return;
  const orderNumber = document.getElementById("track-order-num");
  const status = document.getElementById("track-order-status");
  const info = document.getElementById("track-order-info");
  const progress = document.getElementById("track-order-progress");
  if (orderNumber) orderNumber.textContent = `PEDIDO #${currentPendingOrderId}`;
  if (status) status.textContent = cachedTrackingProgress.status || "Último estado confirmado";
  if (info) {
    const updatedAt = new Date(cachedTrackingProgress.updatedAt);
    const timestamp = Number.isNaN(updatedAt.getTime()) ? "" : ` (${updatedAt.toLocaleString("es-VE")})`;
    info.textContent = `Mostrando el último progreso confirmado${timestamp}. Conéctate a internet para consultar cambios recientes.`;
  }
  if (cachedTrackingProgress.paymentStatus) {
    updateAsyncPaymentStatus(
      cachedTrackingProgress.paymentStatus,
      cachedTrackingProgress.paymentMethod,
      cachedTrackingProgress.paymentMode
    );
  }
  if (progress && Array.isArray(cachedTrackingProgress.steps)) {
    const currentIndex = Number(cachedTrackingProgress.currentIndex);
    progress.innerHTML = `<strong>Último seguimiento confirmado</strong><ol style="margin:.6rem 0 0;padding-left:1.25rem">${cachedTrackingProgress.steps.map((step, index) => `
      <li style="padding:.2rem 0;color:${index <= currentIndex ? "var(--neon-green)" : "var(--text-muted)"}">${escapeClientHtml(step)}</li>
    `).join("")}</ol>`;
  }
}

function escapeClientHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function getSafePromoMediaUrl(value) {
  const url = String(value || "").trim();
  return /^(https:\/\/|\/static\/|\/api\/v1\/cliente\/media\/)/i.test(url) && !url.startsWith("//")
    ? url
    : "/static/img/logo.png";
}

function getDeclaredAllergens(product) {
  if (!product?.alergenos) return [];
  return String(product.alergenos).split(",").map(item => item.trim()).filter(Boolean);
}
let adminConfiguredMesas = [];
let activePromoGroup = null;
let promoGroupQuantities = {};
let promoNotifAnnounced = false;

const CLIENT_EYE_OPEN_SVG = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
const CLIENT_EYE_CLOSED_SVG = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';

function toggleClientPasswordVisibility(inputId = "login-pass-input", btnId = "toggle-client-pass") {
  const input = document.getElementById(inputId);
  const btn = document.getElementById(btnId);
  if (!input || !btn) return;
  const isPass = input.type === "password";
  input.type = isPass ? "text" : "password";
  btn.innerHTML = isPass ? CLIENT_EYE_CLOSED_SVG : CLIENT_EYE_OPEN_SVG;
  btn.setAttribute("aria-pressed", String(isPass));
}

function isAdminConfiguredTable(mesaNum) {
  const parsed = Number(mesaNum);
  if (!Number.isInteger(parsed) || parsed <= 0) return false;
  if (!Array.isArray(adminConfiguredMesas) || adminConfiguredMesas.length === 0) return true;
  return adminConfiguredMesas.some(m => Number(m.numero_mesa) === parsed);
}

function applyQrMesaSession(mesaVal) {
  const cleanMesa = String(mesaVal || "").trim();
  if (!/^[1-9]\d*$/.test(cleanMesa)) return;
  currentDetectedMesa = cleanMesa;
  isTableQrSession = true;
  selectedModality = "mesa";
  try {
    localStorage.setItem("dd-current-mesa", cleanMesa);
    localStorage.setItem("dd-is-table-qr", "true");
  } catch (e) {}
  const checkoutType = document.getElementById("checkout-type");
  if (checkoutType) checkoutType.value = "mesa";
  const tableActions = document.getElementById("table-service-actions");
  if (tableActions) tableActions.style.display = "flex";
  if (document.getElementById("current-table-indicator")) {
    document.getElementById("current-table-indicator").innerText = `🍽️ MESA #${currentDetectedMesa} (CONECTADA)`;
  }
  if (document.getElementById("checkout-mesa-name")) {
    document.getElementById("checkout-mesa-name").innerText = `Mesa #${currentDetectedMesa} (QR validado)`;
  }
  if (document.getElementById("checkout-step4-mesa-label")) {
    document.getElementById("checkout-step4-mesa-label").innerText = `Mesa #${currentDetectedMesa}`;
  }
  const hdrTableBadge = document.getElementById("header-table-badge");
  if (hdrTableBadge) {
    hdrTableBadge.innerText = `🍽️ MESA #${currentDetectedMesa}`;
  }
}

async function loadPublicMesas() {
  try {
    const res = await fetch("/api/v1/cliente/mesas");
    if (!res.ok) return;
    const mesas = await res.json();
    adminConfiguredMesas = Array.isArray(mesas) ? mesas : [];
    const statusBox = document.getElementById("qr-scanner-admin-status");
    if (statusBox) {
      statusBox.textContent = adminConfiguredMesas.length
        ? `Mesas habilitadas por administración: ${adminConfiguredMesas.map(m => `#${m.numero_mesa}`).join(", ")}`
        : "No hay mesas registradas por el administrador todavía.";
    }
    if (currentDetectedMesa && adminConfiguredMesas.length > 0 && !isAdminConfiguredTable(currentDetectedMesa)) {
      const invalidNum = currentDetectedMesa;
      currentDetectedMesa = null;
      isTableQrSession = false;
      try {
        localStorage.removeItem("dd-current-mesa");
        localStorage.removeItem("dd-is-table-qr");
      } catch (e) {}
      if (document.getElementById("checkout-mesa-name")) {
        document.getElementById("checkout-mesa-name").innerText = "Escanea el QR de tu mesa";
      }
      showToast(`La Mesa #${invalidNum} no existe en las mesas cargadas por el administrador.`, "warning");
    }
  } catch (err) {
    console.warn("No se pudo cargar la lista pública de mesas:", err);
  }
}

function loadClientSavedCredentials() {
  try {
    // Limpiar cualquier contraseña heredada almacenada previamente en localStorage
    localStorage.removeItem("donde_david_client_saved_pass");
    const isRem = localStorage.getItem("donde_david_client_remember") === "true";
    const user = localStorage.getItem("donde_david_client_saved_user");
    const userInput = document.getElementById("login-username-input");
    const remCb = document.getElementById("client-remember-credentials");
    if (isRem && user && userInput) {
      userInput.value = user;
      if (remCb) remCb.checked = true;
    }
  } catch (e) {
    console.warn("No se pudo cargar el usuario recordado de cliente", e);
  }
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.add("open");
    if (id === "client-login-modal") {
      loadClientSavedCredentials();
    }
  }
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("open");
}

document.addEventListener("DOMContentLoaded", () => {
  const savedScreen = restoreClientProgress();
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("login") === "1") {
    setTimeout(() => openModal("client-login-modal"), 0);
  }
  const requestedScreen = window.location.hash === "#screen-perfil" ? "screen-perfil" : savedScreen;
  const mesaParam = urlParams.get("mesa");
  const promoParam = Number(urlParams.get("promo"));
  const productParam = Number(urlParams.get("producto"));
  if (mesaParam && /^[1-9]\d*$/.test(mesaParam)) {
    applyQrMesaSession(mesaParam);
    // Entrar directamente al menú interactivo en modo mesa QR (sin forjar sesión de usuario)
    showScreen("screen-home");
    setTimeout(() => {
      showToast(`🍽️ ¡Mesa #${currentDetectedMesa} conectada con éxito! Puedes ordenar directamente tus platos.`, "success");
    }, 250);
  } else {
    currentDetectedMesa = null;
    isTableQrSession = false;
    if (document.getElementById("checkout-mesa-name")) {
      document.getElementById("checkout-mesa-name").innerText = "Escanea el QR de tu mesa";
    }
  }
  renderToonCart();
  updateCartNavBadge();
  if (document.getElementById("checkout-type")) toggleCheckoutFields();
  renderCachedTrackingProgress();
  if (requestedScreen) showScreen(requestedScreen);
  updateClientNetworkStatus();

  document.querySelectorAll("#screen-checkout-delivery input, #screen-checkout-delivery textarea, #screen-checkout-delivery select, #screen-checkout input, #screen-checkout textarea, #screen-checkout select")
    .forEach(field => {
      const saveCheckoutProgress = () => {
        persistClientProgress();
        updateCheckoutOrderSummary();
      };
      field.addEventListener("input", saveCheckoutProgress);
      field.addEventListener("change", saveCheckoutProgress);
    });
  document.getElementById("checkout-payment-instructions")?.addEventListener("click", event => {
    const button = event.target.closest("[data-copy-value]");
    if (button) copyCheckoutValue(button.dataset.copyValue, button.dataset.copyLabel || "Dato");
  });
  window.addEventListener("offline", () => updateClientNetworkStatus(false));
  window.addEventListener("pagehide", persistClientProgress);
  window.addEventListener("resize", () => {
    if (!navigator.onLine) updateClientNetworkStatus(false);
  });
  window.addEventListener("online", () => {
    updateClientNetworkStatus(true);
    if (document.getElementById("screen-tracking")?.classList.contains("active")) {
      refreshTrackedOrder();
    }
  });

  // ⚡ PETICIONES PARALELAS Y OPTIMIZADAS (Promise.all)
  Promise.all([
    loadPublicMesas(),
    loadConfigPublica(),
    loadToonCategories(),
    loadToonProducts(),
    loadGuiaItems(),
    loadPromocionesToon()
  ]).then(() => {
    renderPromoAndComboNotifications(true);
    if (Number.isInteger(promoParam) && promoParam > 0) {
      openPromoGroupModal(promoParam);
    } else if (Number.isInteger(productParam) && productParam > 0) {
      openProductGalleryFromCard(productParam);
    }
    console.log("⚡ Carga paralela optimizada completada.");
  }).catch(err => {
    console.error("Error en peticiones iniciales:", err);
    markClientNetworkFailure(err);
  });

  new WSClient((event, data) => {
    if (["CAMBIO_ESTADO_PEDIDO", "PAGO_CONFIRMADO", "PAGO_VALIDADO", "DELIVERY_ACTUALIZADO"].includes(event)) {
      if (Number(data.pedido_id) === Number(currentPendingOrderId)) refreshTrackedOrder();
    } else if (event === "PRODUCTOS_ACTUALIZADOS" || event === "NUEVO_PRODUCTO") {
      Promise.all([loadToonProducts(), loadToonCategories()]).then(() => renderPromoAndComboNotifications(false));
      showToast("🍔 ¡Menú actualizado en tiempo real!", "info");
    } else if (event === "PROMOCIONES_ACTUALIZADAS") {
      loadPromocionesToon().then(() => {
        renderPromoAndComboNotifications(true);
        if (data?.titulo && data?.activo !== false) {
          showToast(`🔥 Promoción activa: ${data.titulo}`, "info");
        }
      });
    } else if (event === "CONFIGURACION_ACTUALIZADA") {
      loadConfigPublica().then(() => renderToonCart());
    }
  });
  updateProfileUI();
});

function showScreen(screenId) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  const target = document.getElementById(screenId);
  if (target) target.classList.add("active");
  if (target) window.scrollTo(0, 0);

  // Resalte activo en la barra inferior (.bottom-bar li a)
  document.querySelectorAll(".bottom-bar li a, .nav-item").forEach(n => n.classList.remove("active"));
  const idMap = {
    'screen-home': 'nav-link-home',
    'screen-categorias': 'nav-link-menu',
    'screen-menu': 'nav-link-menu',
    'screen-carrito': 'nav-link-cart',
    'screen-checkout-delivery': 'nav-link-cart',
    'screen-checkout-summary': 'nav-link-cart',
    'screen-checkout': 'nav-link-cart',
    'screen-historial': 'nav-link-historial',
    'screen-perfil': 'nav-link-perfil'
  };
  const targetLinkId = idMap[screenId];
  if (targetLinkId) {
    const el = document.getElementById(targetLinkId);
    if (el) el.classList.add("active");
  }

  if (screenId === "screen-historial") loadHistorialPedidos();
  if (screenId === "screen-tracking") startTrackingRefresh();
  if (screenId === "screen-perfil") loadLoyaltyPanel();
  updateCheckoutProgress(screenId);
  persistClientProgress();
  if (typeof scheduleClientTour === "function") scheduleClientTour(screenId);
}

async function loadConfigPublica() {
  try {
    const res = await fetch("/api/v1/cliente/configuraciones-publicas");
    if (!res.ok) throw new Error("No se pudo cargar la configuración del restaurante.");
    const cfg = await res.json();
    const rate = Number(cfg.tasa_cambio_bs);
    tasaCambioBs = Number.isFinite(rate) && rate > 0 ? rate : null;
    const ivaActivo = cfg.iva_activo !== "false" && cfg.iva_activo !== false;
    const parsedTax = Number.parseFloat(cfg.impuesto_porcentaje);
    checkoutTaxRate = ivaActivo ? (Number.isFinite(parsedTax) && parsedTax >= 0 ? parsedTax : 16) : 0;
    const cartTaxLabel = document.getElementById("cart-tax-label");
    if (cartTaxLabel) {
      cartTaxLabel.textContent = ivaActivo ? `IVA (${checkoutTaxRate}%)` : "IVA (Exento 0%)";
    }
    const parsedDelivery = Number.parseFloat(cfg.costo_delivery);
    checkoutDeliveryFee = Number.isFinite(parsedDelivery) && parsedDelivery >= 0 ? parsedDelivery : 0;
    const parsedPackage = Number.parseFloat(cfg.costo_empaque);
    checkoutPackageFee = Number.isFinite(parsedPackage) && parsedPackage >= 0 ? parsedPackage : 0;
    pagoMovilConfig = {
      banco: cfg.pago_movil_banco || "",
      telefono: cfg.pago_movil_telefono || "",
      rif: cfg.pago_movil_rif || "",
      titular: cfg.pago_movil_titular || "",
    };
    googleMapsApiKey = typeof cfg.google_maps_api_key === "string" ? cfg.google_maps_api_key.trim() : "";
    const bankInfo = document.getElementById("checkout-payment-bank-details");
    if (bankInfo && pagoMovilConfig.banco && pagoMovilConfig.telefono && pagoMovilConfig.rif && pagoMovilConfig.titular) {
      bankInfo.textContent = `Banco: ${pagoMovilConfig.banco} · Teléfono: ${pagoMovilConfig.telefono} · RIF: ${pagoMovilConfig.rif} · Titular: ${pagoMovilConfig.titular}`;
    }
    const rateInfo = document.getElementById("checkout-rate-info");
    const homeRate = document.getElementById("home-bcv-rate");
    if (homeRate) {
      homeRate.textContent = tasaCambioBs
        ? `Bs. ${tasaCambioBs.toFixed(4)} / USD · ${cfg.tasa_fuente || "origen desconocido"}`
        : "Tasa no disponible";
    }
    if (rateInfo) {
      rateInfo.textContent = tasaCambioBs
        ? `Tasa: Bs. ${tasaCambioBs.toFixed(4)} por USD · ${cfg.tasa_fuente || "origen no identificado"} · ${cfg.tasa_actualizada_at || "fecha no disponible"}${cfg.tasa_respaldo === "true" ? " · usando respaldo" : ""}`
        : "Tasa BCV no disponible. Los pedidos en bolívares están deshabilitados hasta actualizarla.";
    }
    const vesOption = document.querySelector('#checkout-currency option[value="VES"]');
    if (vesOption) vesOption.disabled = tasaCambioBs === null;
    updateCheckoutPaymentFields();
  } catch (err) {
    console.error("No se pudo cargar configuración pública y tasa BCV:", err);
    markClientNetworkFailure(err);
    tasaCambioBs = null;
    const vesOption = document.querySelector('#checkout-currency option[value="VES"]');
    if (vesOption) vesOption.disabled = true;
    const rateInfo = document.getElementById("checkout-rate-info");
    if (rateInfo) rateInfo.textContent = "No se pudo consultar la tasa; los pagos en bolívares están deshabilitados.";
    const homeRate = document.getElementById("home-bcv-rate");
    if (homeRate) homeRate.textContent = "Tasa no disponible";
    updateCheckoutPaymentFields();
  }
}

function formatPriceDual(usdAmount) {
  if (!Number.isFinite(tasaCambioBs) || tasaCambioBs <= 0) return `$${usdAmount.toFixed(2)}`;
  const bsAmount = (usdAmount * tasaCambioBs).toFixed(2);
  return `$${usdAmount.toFixed(2)} <span style="font-size: 0.85rem; color: var(--gold-accent); font-weight: 700;">(Bs. ${bsAmount})</span>`;
}

async function loadPromocionesToon() {
  try {
    const res = await fetch("/api/v1/cliente/promociones");
    if (!res.ok) throw new Error(`No se pudieron cargar las promociones (HTTP ${res.status}).`);
    toonPromos = await res.json();
    if (!Array.isArray(toonPromos)) throw new Error("La respuesta de promociones no tiene el formato esperado.");
    renderPromoBanner();
    renderPromoAndComboNotifications(false);
  } catch (err) {
    console.error("Error al cargar las promociones del cliente:", err);
    markClientNetworkFailure(err);
    const container = document.getElementById("home-promo-banner-container");
    if (container) {
      container.innerHTML = `<div role="status" style="padding:1.25rem;border:1px dashed var(--toon-border);border-radius:16px;text-align:center;color:var(--text-muted)">No se pudieron cargar las promociones.</div>`;
    }
  }
}

function getActiveComboProducts() {
  const comboCatIds = new Set(
    (toonCategories || [])
      .filter(c => String(c.nombre || "").toLowerCase().includes("combo"))
      .map(c => Number(c.id))
  );
  return (toonProducts || []).filter(p =>
    p && p.activo !== false && p.disponible !== false && Number(p.stock || 0) > 0
    && (comboCatIds.has(Number(p.categoria_id)) || String(p.nombre || "").toLowerCase().includes("combo") || (Number(p.precio_promocion) > 0))
  );
}

function renderPromoAndComboNotifications(announceToast = false) {
  const container = document.getElementById("client-promo-notifications");
  if (!container) return;
  const activePromos = (toonPromos || []).filter(p => p && p.activo !== false);
  const comboItems = getActiveComboProducts();

  if (!activePromos.length && !comboItems.length) {
    container.classList.add("u-display-none");
    container.innerHTML = "";
    return;
  }

  const chips = [
    ...activePromos.map(p => {
      const gp = Number(p.precio_global);
      const priceTag = Number.isFinite(gp) && gp > 0
        ? ` · $${gp.toFixed(2)}`
        : (Number(p.descuento_pct) > 0 ? ` (-${Number(p.descuento_pct)}%)` : "");
      return `
      <button type="button" class="promo-notif-chip" onclick="openPromoGroupModal(${Number(p.id)})">
        🔥 ${escapeClientHtml(p.titulo)}${priceTag}${Array.isArray(p.productos) && p.productos.length ? ` · ${p.productos.length} prod.` : ""}
      </button>
    `;
    }),
    ...comboItems.slice(0, 4).map(item => `
      <button type="button" class="promo-notif-chip" onclick="openProductModal(${Number(item.id)})">
        🎁 ${escapeClientHtml(item.nombre)} · $${Number(item.precio_promocion || item.precio || 0).toFixed(2)}
      </button>
    `)
  ];

  container.classList.remove("u-display-none");
  container.innerHTML = `
    <div class="promo-notifications-header">
      <span>🔔 PROMOCIONES Y COMBOS ACTIVOS (${activePromos.length + comboItems.length})</span>
      <small>Toca para ver o editar</small>
    </div>
    <div class="promo-notif-chips">${chips.join("")}</div>
  `;

  if (announceToast && !promoNotifAnnounced) {
    promoNotifAnnounced = true;
    const summaryParts = [];
    if (activePromos.length) summaryParts.push(`${activePromos.length} promoción(es)`);
    if (comboItems.length) summaryParts.push(`${comboItems.length} combo(s) disponibles`);
    showToast(`🔥 Activo hoy: ${summaryParts.join(" y ")}. Toca una oferta para ver el grupo.`, "info");
  }
}

let promoCarouselTimer = null;
let promoCurrentIndex = 0;

function renderPromoBanner() {
  const container = document.getElementById("home-promo-banner-container");
  if (!container) return;

  const list = toonPromos.filter(promo => promo && promo.activo !== false);
  if (!list.length) {
    container.innerHTML = `<div role="status" style="padding:1.25rem;border:1px dashed var(--toon-border);border-radius:16px;text-align:center;color:var(--text-muted)">No hay promociones activas por ahora.</div>`;
    if (promoCarouselTimer) {
      clearInterval(promoCarouselTimer);
      promoCarouselTimer = null;
    }
    return;
  }

  if (promoCurrentIndex >= list.length) promoCurrentIndex = 0;
  const p = list[promoCurrentIndex];
  const mediaUrl = getSafePromoMediaUrl(p.banner_url);
  const isVideo = /\.(mp4|webm)(?:$|[?#])/i.test(mediaUrl);
  const safeTitle = escapeClientHtml(p.titulo);
  const safeDescription = escapeClientHtml(p.descripcion || "");
  const safeCoupon = escapeClientHtml(p.codigo_cupon || "DAVID");

  // Puntos indicadores deslizantes
  let dotsHtml = list.map((_, idx) => `
    <span class="carousel-dot ${idx === promoCurrentIndex ? 'active' : ''}" onclick="event.stopPropagation(); setCarouselSlide(${idx})" style="width: ${idx === promoCurrentIndex ? '22px' : '8px'}; height: 8px; border-radius: 10px; background: ${idx === promoCurrentIndex ? 'var(--gold-accent)' : 'rgba(255,255,255,0.4)'}; cursor: pointer; transition: all 0.3s ease; display: inline-block;"></span>
  `).join('');

  container.innerHTML = `
    <div style="position: relative; border-radius: 20px; overflow: hidden; height: 260px; border: 2px solid var(--gold-accent); box-shadow: 0 12px 35px rgba(255,183,3,0.35); cursor: pointer;" onclick="handleCarouselClick(${Number(p.id) || 0})">
      
      <!-- Fondo Multimedia Foto o Video HD -->
      ${isVideo ? `
        <video src="${escapeClientHtml(mediaUrl)}" autoplay loop muted playsinline style="width: 100%; height: 100%; object-fit: cover; filter: brightness(0.85);"></video>
      ` : `
        <img src="${escapeClientHtml(mediaUrl)}" style="width: 100%; height: 100%; object-fit: cover; filter: brightness(0.85); transition: transform 0.6s ease;" alt="${safeTitle}">
      `}

      <!-- Capa de Información y Controles -->
      <div style="position: absolute; inset: 0; padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between; background: linear-gradient(0deg, rgba(8,12,20,0.92) 0%, rgba(8,12,20,0.2) 50%, rgba(0,0,0,0.4) 100%);">
        
        <!-- Badge de Descuento / Cupón Editable Admin -->
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.78rem; font-weight: 900; background: var(--neon-red); color: #fff; padding: 0.3rem 0.85rem; border-radius: 20px; box-shadow: 0 4px 15px rgba(255,71,87,0.4);">
            ${Number(p.precio_global) > 0 ? `🔥 COMBO $${Number(p.precio_global).toFixed(2)}` : `🔥 PROMO DE LA CASA ${Number(p.descuento_pct) ? `(-${Number(p.descuento_pct)}% OFF)` : ''}`}
          </span>
          <span style="font-size: 0.78rem; background: rgba(0,0,0,0.7); backdrop-filter: blur(8px); border: 1px solid var(--cyan-accent); color: var(--cyan-accent); padding: 0.3rem 0.75rem; border-radius: 20px; font-weight: 900;">
            CÓDIGO: ${safeCoupon}
          </span>
        </div>

        <!-- Flechas de Navegación Manual -->
        <button onclick="event.stopPropagation(); prevCarouselSlide(${list.length})" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); background: rgba(0,0,0,0.65); color: var(--gold-accent); border: 1px solid var(--gold-accent); width: 34px; height: 34px; border-radius: 50%; cursor: pointer; font-size: 1.2rem; font-weight: 900; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(6px); z-index: 10;">‹</button>
        <button onclick="event.stopPropagation(); nextCarouselSlide(${list.length})" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: rgba(0,0,0,0.65); color: var(--gold-accent); border: 1px solid var(--gold-accent); width: 34px; height: 34px; border-radius: 50%; cursor: pointer; font-size: 1.2rem; font-weight: 900; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(6px); z-index: 10;">›</button>

        <!-- Detalles del Banner y Puntos Indicadores -->
        <div>
          <h3 style="font-size: 1.45rem; font-weight: 900; color: #fff; margin: 0 0 0.2rem 0; text-shadow: 0 3px 10px rgba(0,0,0,0.9); line-height: 1.1;">
            ${safeTitle}
          </h3>
          <p style="font-size: 0.85rem; color: #cbd5e1; margin: 0 0 0.65rem 0; font-weight: 600; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-shadow: 0 2px 6px rgba(0,0,0,0.9);">
            ${safeDescription}
          </p>

          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; gap: 0.4rem; align-items: center;">
              ${dotsHtml}
            </div>
            <button class="btn-gold" style="padding: 0.45rem 1rem; font-size: 0.82rem; font-weight: 900; display: flex; align-items: center; gap: 0.4rem; box-shadow: 0 4px 15px rgba(255,188,13,0.4);">
              <span>🛒 PEDIR ESTA PROMO</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  // Iniciar timer deslizante automático cada 4 segundos
  if (list.length > 1 && !promoCarouselTimer) {
    promoCarouselTimer = setInterval(() => {
      promoCurrentIndex = (promoCurrentIndex + 1) % list.length;
      renderPromoBanner();
    }, 4000);
  } else if (list.length < 2 && promoCarouselTimer) {
    clearInterval(promoCarouselTimer);
    promoCarouselTimer = null;
  }
}

function setCarouselSlide(index) {
  promoCurrentIndex = index;
  renderPromoBanner();
}

function nextCarouselSlide(maxLen) {
  promoCurrentIndex = (promoCurrentIndex + 1) % maxLen;
  renderPromoBanner();
}

function prevCarouselSlide(maxLen) {
  promoCurrentIndex = (promoCurrentIndex - 1 + maxLen) % maxLen;
  renderPromoBanner();
}

function handleCarouselClick(promoId) {
  openPromoGroupModal(promoId);
}

let promoBundleQty = 1;
let promoBundleCustomizations = {};
let editingPromoProductId = null;

function _promoHasGlobalPrice(promo) {
  return Boolean(promo && Number(promo.precio_global) > 0 && Array.isArray(promo.productos) && promo.productos.length > 0);
}

function _getActivePromoProducts(promo) {
  if (!promo) return [];
  if (Array.isArray(promo.productos) && promo.productos.length) {
    return promo.productos.map(lp => (toonProducts || []).find(tp => Number(tp.id) === Number(lp.id)) || lp);
  }
  return _promoHasGlobalPrice(promo) ? [] : getActiveComboProducts().slice(0, 4);
}

function _computePromoBundleAllocations(promo, products, qty, customizationsMap) {
  const safeQty = Math.max(1, Number(qty) || 1);
  const globalUnit = Number(promo.precio_global) || 0;
  const targetBaseTotal = Math.round(globalUnit * safeQty * 100) / 100;
  const baseRows = products.map(p => {
    const pid = Number(p.id);
    const baseUnit = Number(p.precio_promocion) > 0 ? Number(p.precio_promocion) : (Number(p.precio) || 0);
    const custom = customizationsMap[pid] || { opciones: [], extras: [], extraPrice: 0 };
    return {
      product: p,
      pid,
      baseRegularSub: baseUnit * safeQty,
      custom
    };
  });
  const totalBaseRegular = baseRows.reduce((sum, r) => sum + r.baseRegularSub, 0);
  let runningAlloc = 0;
  return baseRows.map((row, idx) => {
    let allocBase = 0;
    if (idx === baseRows.length - 1) {
      allocBase = Math.round((targetBaseTotal - runningAlloc) * 100) / 100;
    } else if (totalBaseRegular > 0) {
      allocBase = Math.round((targetBaseTotal * (row.baseRegularSub / totalBaseRegular)) * 100) / 100;
    } else {
      allocBase = Math.round((targetBaseTotal / baseRows.length) * 100) / 100;
    }
    runningAlloc += allocBase;
    const extraTotal = Math.round((Number(row.custom.extraPrice) || 0) * safeQty * 100) / 100;
    const lineSubtotal = Math.round((allocBase + extraTotal) * 100) / 100;
    return {
      ...row,
      allocBase,
      extraTotal,
      lineSubtotal,
      unitPrice: Math.round((lineSubtotal / safeQty) * 100) / 100
    };
  });
}

function updatePromoModalPricingSummary() {
  const pricingBar = document.getElementById("promo-bundle-pricing-bar");
  const globalPriceEl = document.getElementById("promo-modal-global-price");
  const regularSumEl = document.getElementById("promo-modal-regular-sum");
  const bundleQtyEl = document.getElementById("promo-bundle-qty-val");
  const addAllBtn = document.getElementById("promo-add-all-btn");

  const hasGlobal = _promoHasGlobalPrice(activePromoGroup);
  if (pricingBar) pricingBar.hidden = !hasGlobal;
  if (!activePromoGroup || !hasGlobal) {
    if (addAllBtn) addAllBtn.textContent = "🛒 AGREGAR GRUPO AL CARRITO";
    return;
  }

  const products = _getActivePromoProducts(activePromoGroup);
  const globalUnit = Number(activePromoGroup.precio_global) || 0;
  const regularUnitSum = products.reduce((sum, p) => sum + (Number(p.precio_promocion) > 0 ? Number(p.precio_promocion) : (Number(p.precio) || 0)), 0);
  const extrasTotal = products.reduce((sum, p) => sum + ((Number(promoBundleCustomizations[Number(p.id)]?.extraPrice) || 0) * promoBundleQty), 0);
  const bundleTotal = Math.round((globalUnit * promoBundleQty + extrasTotal) * 100) / 100;
  const regularTotal = Math.round((regularUnitSum * promoBundleQty + extrasTotal) * 100) / 100;

  if (globalPriceEl) {
    globalPriceEl.textContent = `Precio Global: $${bundleTotal.toFixed(2)} USD${extrasTotal > 0 ? ` (incluye $${extrasTotal.toFixed(2)} extras)` : ""}`;
  }
  if (regularSumEl) {
    regularSumEl.textContent = regularTotal > bundleTotal ? `Individual: $${regularTotal.toFixed(2)} USD` : "";
  }
  if (bundleQtyEl) bundleQtyEl.textContent = String(promoBundleQty);
  if (addAllBtn) addAllBtn.textContent = `🛒 AGREGAR PROMO ($${bundleTotal.toFixed(2)})`;
}

function adjustPromoBundleQty(delta) {
  promoBundleQty = Math.max(1, Math.min(20, promoBundleQty + delta));
  updatePromoModalPricingSummary();
  if (activePromoGroup) {
    renderPromoGroupProductsList(_getActivePromoProducts(activePromoGroup));
  }
}

function openPromoGroupModal(promoId) {
  const promo = (toonPromos || []).find(item => Number(item.id) === Number(promoId))
    || (toonPromos || [])[0];
  if (!promo) {
    showScreen("screen-menu");
    return;
  }
  activePromoGroup = promo;
  promoGroupQuantities = {};
  promoBundleQty = 1;
  promoBundleCustomizations = {};
  editingPromoProductId = null;

  const banner = document.getElementById("promo-modal-banner");
  const discount = document.getElementById("promo-modal-discount");
  const title = document.getElementById("promo-modal-title");
  const desc = document.getElementById("promo-modal-desc");
  const coupon = document.getElementById("promo-modal-coupon");
  const listEl = document.getElementById("promo-group-products-list");
  const addAllBtn = document.getElementById("promo-add-all-btn");

  const hasGlobal = _promoHasGlobalPrice(promo);
  if (banner) banner.src = getSafePromoMediaUrl(promo.banner_url);
  if (discount) {
    discount.textContent = hasGlobal
      ? `🔥 COMBO $${Number(promo.precio_global).toFixed(2)}`
      : (Number(promo.descuento_pct) > 0 ? `🔥 -${Number(promo.descuento_pct)}% OFF` : "🔥 PROMO ACTIVA");
  }
  if (title) title.textContent = promo.titulo || "Promoción Donde David";
  if (desc) desc.textContent = promo.descripcion || "Personaliza y agrega los productos de esta promoción.";
  if (coupon) coupon.textContent = promo.codigo_cupon ? `Código: ${promo.codigo_cupon}` : "";

  const groupProducts = _getActivePromoProducts(promo);

  if (!groupProducts.length) {
    if (listEl) {
      listEl.innerHTML = `<div style="text-align:center;color:var(--text-muted);padding:1rem;">Esta promoción aún no tiene productos asignados.</div>`;
    }
    if (addAllBtn) addAllBtn.style.display = "none";
    updatePromoModalPricingSummary();
    openModal("promo-products-modal");
    return;
  }

  groupProducts.forEach(p => {
    promoGroupQuantities[Number(p.id)] = 1;
  });
  if (addAllBtn) addAllBtn.style.display = "block";
  renderPromoGroupProductsList(groupProducts);
  updatePromoModalPricingSummary();
  openModal("promo-products-modal");
}

function renderPromoGroupProductsList(groupProducts) {
  const listEl = document.getElementById("promo-group-products-list");
  if (!listEl) return;
  const hasGlobal = _promoHasGlobalPrice(activePromoGroup);
  listEl.innerHTML = groupProducts.map(p => {
    const pid = Number(p.id);
    const qty = promoGroupQuantities[pid] || 1;
    const price = Number(p.precio_promocion || p.precio || 0);
    const imgUrl = getSafePromoMediaUrl(p.imagen_url);
    const available = p.disponible !== false && Number(p.stock || 0) >= (hasGlobal ? promoBundleQty : 1);
    const custom = promoBundleCustomizations[pid];
    const customLabel = custom && custom.opciones?.length
      ? custom.opciones.join(" · ")
      : "";
    return `
      <div class="promo-group-item-card">
        <div class="promo-group-item-left">
          <img class="promo-group-item-img" src="${escapeClientHtml(imgUrl)}" alt="${escapeClientHtml(p.nombre)}">
          <div>
            <strong>${escapeClientHtml(p.nombre)}</strong>
            <div style="font-size:0.82rem;color:var(--gold-accent);font-weight:800;">
              ${hasGlobal ? `Incluido en combo (×${promoBundleQty}) · Ref. $${price.toFixed(2)}` : `$${price.toFixed(2)}`}
            </div>
            ${customLabel ? `<small class="promo-group-item-custom">${escapeClientHtml(customLabel)}</small>` : ""}
            ${available ? "" : `<small style="color:var(--neon-red);font-weight:700;">Sin stock suficiente</small>`}
          </div>
        </div>
        <div class="promo-group-item-actions">
          ${hasGlobal ? "" : `
            <button type="button" class="btn btn-outline" style="padding:0.25rem 0.55rem;" onclick="adjustPromoGroupItemQty(${pid}, -1)">-</button>
            <strong id="promo-item-qty-${pid}">${qty}</strong>
            <button type="button" class="btn btn-outline" style="padding:0.25rem 0.55rem;" onclick="adjustPromoGroupItemQty(${pid}, 1)">+</button>
          `}
          <button type="button" class="btn btn-outline" style="padding:0.35rem 0.65rem;font-size:0.78rem;" onclick="editPromoGroupProduct(${pid})" ${available ? "" : "disabled"}>✏️ Editar</button>
          ${hasGlobal ? "" : `<button type="button" class="btn-gold" style="padding:0.35rem 0.7rem;font-size:0.78rem;" onclick="addSinglePromoGroupItem(${pid})" ${available ? "" : "disabled"}>+ Agregar</button>`}
        </div>
      </div>
    `;
  }).join("");
}

function adjustPromoGroupItemQty(productId, delta) {
  const pid = Number(productId);
  const current = promoGroupQuantities[pid] || 1;
  const next = Math.max(0, Math.min(20, current + delta));
  promoGroupQuantities[pid] = next;
  const qtyEl = document.getElementById(`promo-item-qty-${pid}`);
  if (qtyEl) qtyEl.textContent = String(next);
}

function editPromoGroupProduct(productId) {
  editingPromoProductId = Number(productId);
  closeModal("promo-products-modal");
  openProductModal(Number(productId));
}

function _pushPromoProductToCart(product, quantity, overrideCustom = null) {
  if (!product || quantity <= 0) return false;
  if (product.disponible === false || Number(product.stock || 0) < quantity) return false;
  const basePrice = Number(product.precio_promocion || product.precio || 0);
  const extraPrice = Number(overrideCustom?.extraPrice || 0);
  const unitPrice = Math.round((basePrice + extraPrice) * 100) / 100;
  toonCart.push({
    producto_id: Number(product.id),
    nombre: product.nombre,
    precio_unitario: unitPrice,
    cantidad: quantity,
    subtotal: Math.round(unitPrice * quantity * 100) / 100,
    imagen_url: product.imagen_url,
    puntos_fidelidad: Math.max(0, Number(product.puntos_fidelidad) || 0),
    tiempo_preparacion: Math.max(0, Number(product.tiempo_preparacion) || 15),
    opciones: overrideCustom?.opciones ? [...overrideCustom.opciones] : [],
    extras: overrideCustom?.extras ? [...overrideCustom.extras] : [],
    observaciones: activePromoGroup?.codigo_cupon ? `Promo ${activePromoGroup.codigo_cupon}` : ""
  });
  return true;
}

function addSinglePromoGroupItem(productId) {
  const pid = Number(productId);
  const qty = Math.max(1, promoGroupQuantities[pid] || 1);
  const promoList = (activePromoGroup?.productos || []).map(lp => (toonProducts || []).find(tp => Number(tp.id) === Number(lp.id)) || lp);
  const product = (toonProducts || []).find(p => Number(p.id) === pid) || promoList.find(p => Number(p.id) === pid);
  if (!product || !_pushPromoProductToCart(product, qty, promoBundleCustomizations[pid] || null)) {
    showToast("Este producto no tiene existencias disponibles.", "warning");
    return;
  }
  updateCartNavBadge();
  renderToonCart();
  showToast(`🛒 ${qty}x ${product.nombre} agregado al carrito.`, "success");
}

function addAllPromoGroupToCart() {
  if (!activePromoGroup) return;
  const products = _getActivePromoProducts(activePromoGroup);
  if (_promoHasGlobalPrice(activePromoGroup)) {
    const unavailable = products.find(p => p.disponible === false || Number(p.stock || 0) < promoBundleQty);
    if (!products.length || unavailable) {
      showToast(
        unavailable
          ? `"${unavailable.nombre}" no tiene existencias suficientes para el combo.`
          : "Esta promoción no tiene productos asignados.",
        "warning"
      );
      return;
    }
    const seq = Date.now() + Math.floor(Math.random() * 1000);
    const allocations = _computePromoBundleAllocations(activePromoGroup, products, promoBundleQty, promoBundleCustomizations);
    allocations.forEach(alloc => {
      const p = alloc.product;
      toonCart.push({
        producto_id: alloc.pid,
        nombre: p.nombre,
        precio_unitario: alloc.unitPrice,
        cantidad: promoBundleQty,
        subtotal: alloc.lineSubtotal,
        imagen_url: p.imagen_url || "",
        puntos_fidelidad: Math.max(0, Number(p.puntos_fidelidad) || 0),
        tiempo_preparacion: Math.max(0, Number(p.tiempo_preparacion) || 15),
        opciones: alloc.custom.opciones ? [...alloc.custom.opciones] : [],
        extras: alloc.custom.extras ? [...alloc.custom.extras] : [],
        promo_id: Number(activePromoGroup.id),
        promo_titulo: activePromoGroup.titulo || "Combo Promocional",
        promo_bundle_seq: seq,
        promo_extra_unit: Number(alloc.custom.extraPrice) || 0,
        promo_base_share_subtotal: alloc.allocBase,
        observaciones: `Promo ${activePromoGroup.titulo || activePromoGroup.codigo_cupon || ""}`.trim()
      });
    });
    updateCartNavBadge();
    renderToonCart();
    closeModal("promo-products-modal");
    showToast(`🔥 Combo "${activePromoGroup.titulo}" agregado al carrito (×${promoBundleQty}).`, "success");
    return;
  }

  let addedCount = 0;
  products.forEach(p => {
    const qty = Number(promoGroupQuantities[Number(p.id)] ?? 1);
    if (qty > 0 && _pushPromoProductToCart(p, qty, promoBundleCustomizations[Number(p.id)] || null)) {
      addedCount += qty;
    }
  });
  if (!addedCount) {
    showToast("Selecciona al menos 1 producto disponible del grupo para agregar.", "warning");
    return;
  }
  updateCartNavBadge();
  renderToonCart();
  closeModal("promo-products-modal");
  showToast(`🔥 Grupo de promoción agregado al carrito (${addedCount} artículo(s)).`, "success");
}

function renderPhotoCategories() {
  const container = document.getElementById("home-categories-grid");
  if (!container) return;

  const catIcons = {
    "Hamburguesas": "🍔",
    "Hot Dogs": "🌭",
    "Papas": "🍟",
    "Bebidas": "🥤",
    "Postres": "🍰",
    "Alitas": "🍗",
    "Combos": "🎁"
  };

  const isAllActive = !activeCategoryFilter;

  let html = `
    <div style="display: flex; gap: 0.55rem; overflow-x: auto; padding-bottom: 0.35rem; -webkit-overflow-scrolling: touch; scrollbar-width: none;">
      <div class="cat-pill-item ${isAllActive ? 'active' : ''}" style="background: ${isAllActive ? 'var(--gold-gradient)' : 'rgba(255,255,255,0.05)'}; color: ${isAllActive ? '#000000' : 'var(--text-muted)'}; border: 1px solid ${isAllActive ? 'var(--gold-accent)' : 'var(--toon-border)'}; padding: 0.45rem 0.95rem; border-radius: 25px; font-weight: 800; font-size: 0.8rem; white-space: nowrap; cursor: pointer; display: flex; align-items: center; gap: 0.4rem; transition: all 0.2s ease;" onclick="filterCategoryToon(null)">
        <span>🔥</span>
        <span>TODOS</span>
      </div>
  `;

  toonCategories.forEach(c => {
    const icon = catIcons[c.nombre] || "🍽️";
    const isActive = activeCategoryFilter === c.id;
    html += `
      <div class="cat-pill-item ${isActive ? 'active' : ''}" style="background: ${isActive ? 'var(--gold-gradient)' : 'rgba(255,255,255,0.05)'}; color: ${isActive ? '#000000' : 'var(--text-muted)'}; border: 1px solid ${isActive ? 'var(--gold-accent)' : 'var(--toon-border)'}; padding: 0.45rem 0.95rem; border-radius: 25px; font-weight: 800; font-size: 0.8rem; white-space: nowrap; cursor: pointer; display: flex; align-items: center; gap: 0.4rem; transition: all 0.2s ease;" onclick="filterCategoryToon(${c.id})">
        <span>${icon}</span>
        <span>${c.nombre.toUpperCase()}</span>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
  
  if (document.getElementById("full-categories-grid")) {
    document.getElementById("full-categories-grid").innerHTML = html;
  }
}

let clientMenuModeFilter = "todos";
let clientFavorites = new Set();
let appliedCouponData = null;
let selectedTipMode = "none";

async function loadClientFavorites() {
  if (typeof Auth === "undefined" || !Auth.isAuthenticated || !Auth.isAuthenticated()) {
    clientFavorites = new Set();
    return;
  }
  try {
    const res = await fetch("/api/v1/cliente/favoritos", { headers: Auth.getHeaders() });
    if (res.ok) {
      const ids = await res.json();
      clientFavorites = new Set(Array.isArray(ids) ? ids.map(Number) : []);
      if (typeof renderToonProducts === "function" && Array.isArray(toonProducts) && toonProducts.length) {
        renderToonProducts();
      }
    }
  } catch (err) {
    console.warn("No se pudieron cargar favoritos:", err);
  }
}

async function toggleFavoriteProduct(prodId, evt) {
  if (evt) evt.stopPropagation();
  const pid = Number(prodId);
  if (typeof Auth === "undefined" || !Auth.isAuthenticated || !Auth.isAuthenticated()) {
    showToast("Inicia sesión como cliente para guardar tus favoritos.", "warning");
    openModal("client-login-modal");
    return;
  }
  const isFav = clientFavorites.has(pid);
  try {
    const res = await fetch(`/api/v1/cliente/favoritos/${pid}`, {
      method: isFav ? "DELETE" : "POST",
      headers: Auth.getHeaders()
    });
    if (!res.ok) throw new Error("No se pudo actualizar favoritos.");
    if (isFav) clientFavorites.delete(pid);
    else clientFavorites.add(pid);
    renderToonProducts();
    filterMenuProducts();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function setMenuModeFilter(mode) {
  clientMenuModeFilter = mode || "todos";
  document.querySelectorAll("#menu-filter-pills .menu-filter-pill").forEach(btn => {
    btn.classList.toggle("is-active", btn.getAttribute("data-menu-filter") === clientMenuModeFilter);
  });
  filterMenuProducts();
}

function _applyModeFilter(list) {
  if (clientMenuModeFilter === "promo") {
    return list.filter(p => Number(p.precio_promocion) > 0);
  }
  if (clientMenuModeFilter === "favoritos") {
    return list.filter(p => clientFavorites.has(Number(p.id)));
  }
  return list;
}

function filterCategoryToon(catId) {
  activeCategoryFilter = catId;
  renderPhotoCategories();
  renderToonProducts();
}

function renderToonProducts() {
  let list = toonProducts;
  if (activeCategoryFilter) {
    list = toonProducts.filter(p => p.categoria_id === activeCategoryFilter);
  }

  const featured = document.getElementById("home-featured-grid");
  const menu = document.getElementById("menu-products-grid");
  if (featured) featured.innerHTML = renderProductCards(list);
  if (menu) menu.innerHTML = renderProductCards(_applyModeFilter(list));
}

function filterMenuProducts() {
  const query = (document.getElementById("menu-search-input")?.value || "").trim().toLocaleLowerCase();
  const base = _applyModeFilter(toonProducts);
  const filtered = base.filter(product => {
    const category = toonCategories.find(item => item.id === product.categoria_id)?.nombre || "";
    return `${product.nombre} ${product.descripcion || ""} ${category}`
      .toLocaleLowerCase().includes(query);
  });
  const container = document.getElementById("menu-products-grid");
  if (container) {
    container.innerHTML = filtered.length
      ? renderProductCards(filtered)
      : `<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:1.5rem;">No hay productos que coincidan con este filtro.</div>`;
  }
}

function _getProductGalleryItems(product) {
  if (!product) return [{ tipo: "imagen", url: "/static/img/logo.png" }];
  const rawMain = String(product.imagen_url || "").trim();
  const mainUrl = /^(https:\/\/|\/static\/|\/api\/v1\/cliente\/media\/)/i.test(rawMain)
    ? rawMain
    : "/static/img/logo.png";
  const items = [{ tipo: "imagen", url: mainUrl }];
  try {
    const parsed = JSON.parse(product.media_json || "[]");
    if (Array.isArray(parsed)) {
      parsed.forEach(entry => {
        if (!entry || typeof entry.url !== "string") return;
        const cleanUrl = entry.url.trim();
        if (!/^(https:\/\/|\/static\/|\/api\/v1\/cliente\/media\/)/i.test(cleanUrl)) return;
        const tipo = entry.tipo === "video" ? "video" : "imagen";
        if (!items.some(existing => existing.url === cleanUrl && existing.tipo === tipo)) {
          items.push({ tipo, url: cleanUrl });
        }
      });
    }
  } catch (err) {}
  return items;
}

let dishLightboxItems = [];
let dishLightboxIndex = 0;
let dishLightboxProduct = null;
let modalActiveHeroIndex = 0;

function renderProductCards(products) {
  return products.map(product => {
    const pid = Number(product.id);
    const galleryItems = _getProductGalleryItems(product);
    const image = escapeClientHtml(galleryItems[0].url);
    const extraCount = Math.max(0, galleryItems.length - 1);
    const allergens = getDeclaredAllergens(product);
    const regularPrice = Number(product.precio) || 0;
    const promoPrice = Number(product.precio_promocion) > 0 ? Number(product.precio_promocion) : null;
    const displayedPrice = promoPrice || regularPrice;
    const isFav = clientFavorites.has(pid);
    return `
      <div class="product-toon-card" onclick="openProductModal(${pid})">
        <div class="product-img-container" onclick="event.stopPropagation(); openProductGalleryFromCard(${pid})" title="Toca la imagen para ver las fotos y detalles del plato">
          <button type="button" class="product-fav-btn ${isFav ? "is-fav" : ""}" aria-label="Favorito" onclick="toggleFavoriteProduct(${pid}, event)">${isFav ? "❤️" : "🤍"}</button>
          <img src="${image}" alt="${escapeClientHtml(product.nombre)}" loading="lazy" onerror="this.onerror=null;this.src='/static/img/logo.png';">
          <span class="product-badge">${promoPrice ? "🔥 PROMO" : "🔥 TOON"}</span>
          <span class="product-gallery-pill">${extraCount > 0 ? `📸 ${galleryItems.length} fotos` : "🔍 Ver plato"}</span>
        </div>
        <div class="product-info">
          <div class="product-title">${escapeClientHtml(product.nombre)}</div>
          <div class="product-desc">${escapeClientHtml(product.descripcion || '')}</div>
          ${allergens.length ? `<small class="product-allergens">Alérgenos declarados: ${allergens.map(escapeClientHtml).join(", ")}</small>` : ''}
          ${Number(product.tiempo_preparacion) > 0 ? `<small class="product-preparation-time">Preparación estimada: ${Number(product.tiempo_preparacion)} min</small>` : ''}
          ${Number(product.puntos_fidelidad) > 0 ? `<small style="display:block;color:var(--cyan-accent);margin:.35rem 0">🎁 ${Number(product.puntos_fidelidad)} puntos por unidad al pagar</small>` : ''}
          <div class="product-price-bar">
            <span class="product-price">${promoPrice ? `<del>${formatPriceDual(regularPrice)}</del> ` : ""}${formatPriceDual(displayedPrice)}</span>
            <button class="btn-gold" style="padding: 0.4rem 0.75rem; font-size: 0.75rem;">➕ DETALLES</button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function getProductExtras(product) {
  try {
    const extras = JSON.parse(product.extras_json || "[]");
    return Array.isArray(extras)
      ? extras.filter(extra => extra && typeof extra.nombre === "string" && Number.isFinite(Number(extra.precio)) && Number(extra.precio) >= 0)
      : [];
  } catch (error) {
    console.error(`Configuración de extras inválida para el producto ${product.id}.`, error);
    return [];
  }
}

function openProductModal(prodId) {
  currentSelectedModalProduct = toonProducts.find(p => p.id === prodId);
  if (!currentSelectedModalProduct) return;

  currentModalQty = 1;
  modalActiveHeroIndex = 0;
  const addButton = document.getElementById("modal-add-to-cart-btn");
  if (addButton) addButton.textContent = "🛒 AGREGAR AL CARRITO";
  document.getElementById("modal-qty-val").innerText = "1";
  const galleryItems = _getProductGalleryItems(currentSelectedModalProduct);
  const modalImgEl = document.getElementById("modal-product-img");
  modalImgEl.onerror = () => { modalImgEl.onerror = null; modalImgEl.src = "/static/img/logo.png"; };
  modalImgEl.src = galleryItems[0].url;
  const zoomBadge = document.getElementById("modal-hero-zoom-badge");
  if (zoomBadge) {
    zoomBadge.textContent = galleryItems.length > 1
      ? `📸 Ver galería (${galleryItems.length})`
      : "🔍 Toca para ampliar";
  }
  const thumbStrip = document.getElementById("modal-product-thumb-strip");
  if (thumbStrip) {
    if (galleryItems.length > 1) {
      thumbStrip.hidden = false;
      thumbStrip.innerHTML = galleryItems.map((item, idx) => `
        <button type="button" class="dish-thumb-btn ${idx === 0 ? "is-active" : ""}" onclick="selectModalHeroSlide(${idx})" aria-label="Ver media ${idx + 1}">
          ${item.tipo === "video" ? "🎥 Video" : `<img src="${escapeClientHtml(item.url)}" alt="" onerror="this.onerror=null;this.src='/static/img/logo.png';">`}
        </button>
      `).join("");
    } else {
      thumbStrip.hidden = true;
      thumbStrip.innerHTML = "";
    }
  }
  document.getElementById("modal-product-title").innerText = currentSelectedModalProduct.nombre;
  const modalPrice = Number(currentSelectedModalProduct.precio_promocion) > 0
    ? Number(currentSelectedModalProduct.precio_promocion)
    : Number(currentSelectedModalProduct.precio) || 0;
  document.getElementById("modal-product-price").innerHTML = formatPriceDual(modalPrice);
  document.getElementById("modal-product-desc").innerText = currentSelectedModalProduct.descripcion || '';
  const loyaltyInfo = document.getElementById("modal-product-loyalty");
  if (loyaltyInfo) {
    const points = Math.max(0, Number(currentSelectedModalProduct.puntos_fidelidad) || 0);
    loyaltyInfo.textContent = points ? `🎁 Acumula ${points} puntos por unidad al confirmar el pago.` : "Este plato no acumula puntos.";
  }
  const mediaContainer = document.getElementById("modal-product-media");
  if (mediaContainer) {
    let media = [];
    try {
      const parsedMedia = JSON.parse(currentSelectedModalProduct.media_json || "[]");
      if (Array.isArray(parsedMedia)) media = parsedMedia;
    } catch (error) {
      console.error(`Contenido multimedia inválido para el producto ${currentSelectedModalProduct.id}.`, error);
    }
    mediaContainer.innerHTML = media.map((item, idx) => {
      if (!item || typeof item.url !== "string") return "";
      const url = escapeClientHtml(item.url);
      return item.tipo === "video"
        ? `<video src="${url}" controls playsinline preload="metadata" style="width:100%;max-height:260px;border-radius:12px;margin:.4rem 0"></video>`
        : item.tipo === "imagen"
          ? `<img src="${url}" alt="${escapeClientHtml(currentSelectedModalProduct.nombre)}" loading="lazy" onclick="openDishLightbox(${idx + 1})" onerror="this.onerror=null;this.src='/static/img/logo.png';" style="width:100%;max-height:260px;object-fit:cover;border-radius:12px;margin:.4rem 0;cursor:zoom-in;">`
          : "";
    }).join("");
  }
  const allergenInfo = document.getElementById("modal-product-allergens");
  if (allergenInfo) {
    const declared = getDeclaredAllergens(currentSelectedModalProduct);
    allergenInfo.textContent = declared.length
      ? `Alérgenos declarados: ${declared.join(", ")}. Puede existir contaminación cruzada. Consulta al restaurante si tienes una alergia.`
      : "El restaurante no ha declarado alérgenos para este producto. Consulta al personal si tienes una alergia.";
    allergenInfo.style.display = "block";
  }
  if (document.getElementById("modal-product-notes")) document.getElementById("modal-product-notes").value = "";
  const masterConTodoCheck = document.getElementById("modal-con-todo-check");
  if (masterConTodoCheck) masterConTodoCheck.checked = true;

  // 1. Renderizar Todos los Ingredientes del Producto (para remover / mantener)
  const ingContainer = document.getElementById("modal-ingredients-list");
  let defaultIngredients = ["Carne 150g", "Queso Cheddar", "Tomate", "Cebolla Morada", "Pepinillos", "Salsa Especial"];
  if (currentSelectedModalProduct.ingredientes_json) {
    try {
      const parsed = JSON.parse(currentSelectedModalProduct.ingredientes_json);
      if (Array.isArray(parsed) && parsed.length > 0) defaultIngredients = parsed;
    } catch(e){}
  } else if (currentSelectedModalProduct.descripcion) {
    const splitDesc = currentSelectedModalProduct.descripcion.split(/[,+]/).map(s => s.trim()).filter(s => s.length > 2);
    if (splitDesc.length > 1) defaultIngredients = splitDesc;
  }

  if (ingContainer) {
    let ingHtml = "";
    defaultIngredients.forEach((ing, i) => {
      ingHtml += `
        <label class="ing-toggle-item">
          <span>✔️ Con ${escapeClientHtml(ing)}</span>
          <input type="checkbox" class="dyn-ing-check" data-name="${escapeClientHtml(ing)}" checked onchange="handleIngredientChange()">
        </label>
      `;
    });
    ingContainer.innerHTML = ingHtml;
  }

  // 2. Renderizar Extras Recomendados Dinámicos según la Categoría del Producto
  const extContainer = document.getElementById("modal-extras-list");
  const catExtras = getProductExtras(currentSelectedModalProduct);
  if (extContainer) {
    let extHtml = catExtras.length ? "" : '<small style="color:var(--text-muted)">No hay extras configurados para este plato.</small>';
    catExtras.forEach(ext => {
      const price = Number(ext.precio);
      const priceTxt = price > 0 ? `(${formatPriceDual(price)})` : '(GRATIS)';
      extHtml += `
        <label class="extra-item-row">
          <span>➕ ${escapeClientHtml(ext.nombre)} <small style="color: var(--gold-accent); font-weight:800;">${priceTxt}</small></span>
          <input type="checkbox" class="dyn-extra-check" data-name="${escapeClientHtml(ext.nombre)}" data-price="${price}">
        </label>
      `;
    });
    extContainer.innerHTML = extHtml;
  }

  const editingItem = Number.isInteger(editingCartIndex) ? toonCart[editingCartIndex] : null;
  const promoCustomItem = editingPromoProductId === currentSelectedModalProduct.id
    ? (promoBundleCustomizations[Number(currentSelectedModalProduct.id)] || null)
    : null;
  const activePrefill = (editingItem && editingItem.producto_id === currentSelectedModalProduct.id)
    ? editingItem
    : promoCustomItem;
  if (activePrefill) {
    if (editingItem && editingItem.producto_id === currentSelectedModalProduct.id) {
      currentModalQty = editingItem.cantidad;
      document.getElementById("modal-qty-val").innerText = String(currentModalQty);
    }
    const removedIngredients = (activePrefill.opciones || [])
      .filter(option => option.startsWith("Sin "))
      .map(option => option.slice(4));
    document.querySelectorAll(".dyn-ing-check").forEach(checkbox => {
      checkbox.checked = !removedIngredients.includes(checkbox.dataset.name);
    });
    document.querySelectorAll(".dyn-extra-check").forEach(checkbox => {
      checkbox.checked = (activePrefill.extras || []).includes(checkbox.dataset.name);
    });
    const note = (activePrefill.opciones || []).find(option => option.startsWith("Nota: "));
    const notesInput = document.getElementById("modal-product-notes");
    if (notesInput) notesInput.value = note ? note.slice(6) : "";
    if (addButton) {
      addButton.textContent = promoCustomItem ? "💾 GUARDAR EN PROMO" : "💾 GUARDAR CAMBIOS";
    }
  }

  if (mediaContainer) mediaContainer.hidden = !mediaContainer.innerHTML.trim();
  document.getElementById("product-detail-modal").classList.add("open");
}

function selectModalHeroSlide(index) {
  if (!currentSelectedModalProduct) return;
  const gallery = _getProductGalleryItems(currentSelectedModalProduct);
  const item = gallery[index];
  if (!item) return;
  if (item.tipo === "video") {
    openDishLightbox(index);
    return;
  }
  modalActiveHeroIndex = index;
  const modalImgEl = document.getElementById("modal-product-img");
  if (modalImgEl) modalImgEl.src = item.url;
  document.querySelectorAll("#modal-product-thumb-strip .dish-thumb-btn").forEach((btn, idx) => {
    btn.classList.toggle("is-active", idx === index);
  });
}

function openProductGalleryFromCard(prodId) {
  const product = (toonProducts || []).find(p => Number(p.id) === Number(prodId));
  if (!product) return;
  openDishLightbox(0, product);
}

function openDishLightbox(startIndex = null, productOverride = null) {
  const targetProduct = productOverride || currentSelectedModalProduct;
  if (!targetProduct) return;
  dishLightboxProduct = targetProduct;
  dishLightboxItems = _getProductGalleryItems(targetProduct);
  const initialIndex = Number.isInteger(startIndex) ? startIndex : modalActiveHeroIndex;
  dishLightboxIndex = Math.max(0, Math.min(dishLightboxItems.length - 1, initialIndex || 0));

  const titleEl = document.getElementById("dish-lightbox-title");
  const priceEl = document.getElementById("dish-lightbox-price");
  const descEl = document.getElementById("dish-lightbox-desc");
  const metaEl = document.getElementById("dish-lightbox-meta");
  if (titleEl) titleEl.textContent = targetProduct.nombre || "Platillo";
  const effectivePrice = Number(targetProduct.precio_promocion) > 0
    ? Number(targetProduct.precio_promocion)
    : Number(targetProduct.precio) || 0;
  if (priceEl) priceEl.innerHTML = formatPriceDual(effectivePrice);
  if (descEl) descEl.textContent = targetProduct.descripcion || "Preparado al instante en Donde David.";

  if (metaEl) {
    let ingredients = [];
    try {
      const parsed = JSON.parse(targetProduct.ingredientes_json || "[]");
      if (Array.isArray(parsed)) ingredients = parsed.filter(Boolean);
    } catch (e) {}
    const allergens = getDeclaredAllergens(targetProduct);
    metaEl.innerHTML = `
      <div>⏱️ Preparación estimada: <strong>${Number(targetProduct.tiempo_preparacion) || 15} min</strong></div>
      ${Number(targetProduct.puntos_fidelidad) > 0 ? `<div>🎁 Acumula <strong>${Number(targetProduct.puntos_fidelidad)} pts</strong> por unidad</div>` : ""}
      ${ingredients.length ? `<div><strong>Ingredientes:</strong><div class="dish-lightbox-ing-chips">${ingredients.map(ing => `<span class="dish-lightbox-ing-chip">${escapeClientHtml(ing)}</span>`).join("")}</div></div>` : ""}
      ${allergens.length ? `<div>⚠️ Alérgenos: <strong>${allergens.map(escapeClientHtml).join(", ")}</strong></div>` : ""}
    `;
  }

  renderDishLightboxSlide();
  const modal = document.getElementById("product-gallery-lightbox");
  if (modal) modal.classList.add("open");
}

function renderDishLightboxSlide() {
  const canvas = document.getElementById("dish-lightbox-canvas");
  const counter = document.getElementById("dish-lightbox-counter");
  const thumbs = document.getElementById("dish-lightbox-thumbs");
  const prevBtn = document.getElementById("dish-lightbox-prev");
  const nextBtn = document.getElementById("dish-lightbox-next");
  if (!canvas || !dishLightboxItems.length) return;

  const item = dishLightboxItems[dishLightboxIndex] || dishLightboxItems[0];
  const safeUrl = escapeClientHtml(item.url);
  canvas.innerHTML = item.tipo === "video"
    ? `<video src="${safeUrl}" controls autoplay playsinline></video>`
    : `<img src="${safeUrl}" alt="${escapeClientHtml(dishLightboxProduct?.nombre || "Plato")}" onerror="this.onerror=null;this.src='/static/img/logo.png';">`;

  if (counter) counter.textContent = `${dishLightboxIndex + 1} / ${dishLightboxItems.length}`;
  const hasMultiple = dishLightboxItems.length > 1;
  if (prevBtn) prevBtn.hidden = !hasMultiple;
  if (nextBtn) nextBtn.hidden = !hasMultiple;
  if (thumbs) {
    thumbs.innerHTML = hasMultiple
      ? dishLightboxItems.map((entry, idx) => `
          <button type="button" class="dish-thumb-btn ${idx === dishLightboxIndex ? "is-active" : ""}" onclick="selectDishLightboxSlide(${idx})" aria-label="Foto ${idx + 1}">
            ${entry.tipo === "video" ? "🎥 Video" : `<img src="${escapeClientHtml(entry.url)}" alt="" onerror="this.onerror=null;this.src='/static/img/logo.png';">`}
          </button>
        `).join("")
      : "";
  }
}

function stepDishLightbox(delta) {
  if (!dishLightboxItems.length) return;
  dishLightboxIndex = (dishLightboxIndex + delta + dishLightboxItems.length) % dishLightboxItems.length;
  renderDishLightboxSlide();
}

function selectDishLightboxSlide(index) {
  if (!dishLightboxItems[index]) return;
  dishLightboxIndex = index;
  renderDishLightboxSlide();
}

function closeDishLightbox() {
  const modal = document.getElementById("product-gallery-lightbox");
  if (modal) modal.classList.remove("open");
}

function orderFromDishLightbox() {
  const prod = dishLightboxProduct;
  closeDishLightbox();
  if (prod && (!currentSelectedModalProduct || Number(currentSelectedModalProduct.id) !== Number(prod.id))) {
    openProductModal(Number(prod.id));
  } else if (prod) {
    document.getElementById("product-detail-modal")?.classList.add("open");
  }
}

function closeProductModal() {
  document.getElementById("product-detail-modal").classList.remove("open");
  editingCartIndex = null;
  const reopenPromo = editingPromoProductId !== null && Boolean(activePromoGroup);
  editingPromoProductId = null;
  const addButton = document.getElementById("modal-add-to-cart-btn");
  if (addButton) addButton.textContent = "🛒 AGREGAR AL CARRITO";
  if (reopenPromo) {
    openModal("promo-products-modal");
  }
}

function toggleConTodoIngredients(isConTodo) {
  document.querySelectorAll(".dyn-ing-check").forEach(cb => {
    cb.checked = Boolean(isConTodo);
  });
}

function handleIngredientChange() {
  const allChecks = Array.from(document.querySelectorAll(".dyn-ing-check"));
  const allChecked = allChecks.length > 0 && allChecks.every(cb => cb.checked);
  const masterCheck = document.getElementById("modal-con-todo-check");
  if (masterCheck) masterCheck.checked = allChecked;
}

function adjustModalQty(val) {
  currentModalQty = Math.max(1, currentModalQty + val);
  document.getElementById("modal-qty-val").innerText = currentModalQty;
}

function addModalProductToCart() {
  if (!currentSelectedModalProduct) return;
  const wasEditing = Number.isInteger(editingCartIndex);

  let extraPrice = 0.0;
  let opts = [];
  const selectedExtras = [];

  // Registrar estado de ingredientes: ¡Con Todo! o ingredientes específicos removidos
  const masterCheck = document.getElementById("modal-con-todo-check");
  const uncheckedIngs = Array.from(document.querySelectorAll(".dyn-ing-check:not(:checked)"));
  if (masterCheck && masterCheck.checked && uncheckedIngs.length === 0) {
    opts.push("🔥 ¡CON TODO!");
  } else {
    uncheckedIngs.forEach(cb => {
      const ingName = cb.getAttribute("data-name");
      opts.push(`Sin ${ingName}`);
    });
  }

  // Registrar extras agregados (marcados)
  document.querySelectorAll(".dyn-extra-check:checked").forEach(cb => {
    const extName = cb.getAttribute("data-name");
    const price = parseFloat(cb.getAttribute("data-price")) || 0.0;
    opts.push(`+ ${extName}`);
    selectedExtras.push(extName);
    extraPrice += price;
  });

  const notesInput = document.getElementById("modal-product-notes");
  if (notesInput && notesInput.value.trim() !== "") {
    opts.push(`Nota: ${notesInput.value.trim()}`);
  }

  if (editingPromoProductId === Number(currentSelectedModalProduct.id) && activePromoGroup) {
    promoBundleCustomizations[Number(currentSelectedModalProduct.id)] = {
      opciones: opts,
      extras: selectedExtras,
      extraPrice: Math.round(extraPrice * 100) / 100
    };
    editingPromoProductId = null;
    document.getElementById("product-detail-modal").classList.remove("open");
    const addButton = document.getElementById("modal-add-to-cart-btn");
    if (addButton) addButton.textContent = "🛒 AGREGAR AL CARRITO";
    renderPromoGroupProductsList(_getActivePromoProducts(activePromoGroup));
    updatePromoModalPricingSummary();
    openModal("promo-products-modal");
    showToast(`Personalización aplicada en combo: ${currentSelectedModalProduct.nombre}.`, "success");
    return;
  }

  const basePrice = Number(currentSelectedModalProduct.precio_promocion) > 0
    ? Number(currentSelectedModalProduct.precio_promocion)
    : Number(currentSelectedModalProduct.precio) || 0;
  const unitPrice = basePrice + extraPrice;

  const existingCartItem = (Number.isInteger(editingCartIndex) && toonCart[editingCartIndex]) ? toonCart[editingCartIndex] : null;
  if (existingCartItem && existingCartItem.promo_bundle_seq) {
    const keptQty = existingCartItem.cantidad;
    const baseShare = Number(existingCartItem.promo_base_share_subtotal || 0);
    const updatedSub = Math.round((baseShare + extraPrice * keptQty) * 100) / 100;
    toonCart[editingCartIndex] = {
      ...existingCartItem,
      precio_unitario: Math.round((updatedSub / keptQty) * 100) / 100,
      subtotal: updatedSub,
      opciones: opts,
      extras: selectedExtras,
      promo_extra_unit: Math.round(extraPrice * 100) / 100
    };
    editingCartIndex = null;
  } else {
    const cartItem = {
      producto_id: currentSelectedModalProduct.id,
      nombre: currentSelectedModalProduct.nombre,
      imagen_url: currentSelectedModalProduct.imagen_url || "",
      precio_unitario: unitPrice,
      cantidad: currentModalQty,
      subtotal: unitPrice * currentModalQty,
      puntos_fidelidad: Math.max(0, Number(currentSelectedModalProduct.puntos_fidelidad) || 0),
      opciones: opts,
      extras: selectedExtras,
      tiempo_preparacion: Number(currentSelectedModalProduct.tiempo_preparacion) || 15
    };
    if (existingCartItem) {
      toonCart[editingCartIndex] = cartItem;
      editingCartIndex = null;
    } else {
      toonCart.push(cartItem);
    }
  }

  updateCartNavBadge();
  closeProductModal();
  showToast(wasEditing
    ? `Pedido actualizado: ${currentSelectedModalProduct.nombre}.`
    : `¡Agregado al carrito: ${currentSelectedModalProduct.nombre}!`, "success");
  renderToonCart();
}

function updateCartNavBadge() {
  const totalCount = toonCart.reduce((sum, item) => sum + item.cantidad, 0);
  const totalSum = toonCart.reduce((sum, item) => sum + item.subtotal, 0);

  const cartCount = document.getElementById("client-cart-count");
  if (cartCount) cartCount.textContent = `${totalCount} ${totalCount === 1 ? "artículo" : "artículos"}`;
  const badgeEl = document.getElementById("nav-cart-badge");
  if (badgeEl) badgeEl.innerText = totalCount;

  // Carrito Flotante de Alta Visibilidad
  const floatWidget = document.getElementById("floating-cart-btn");
  if (floatWidget) {
    if (totalCount > 0) {
      floatWidget.style.display = "flex";
      floatWidget.innerHTML = `
        <div style="display:flex; align-items:center; gap:0.6rem;">
          <span style="font-size:1.25rem;">🛒</span>
          <span>VER MI PEDIDO</span>
          <span class="floating-cart-badge">${totalCount} ${totalCount === 1 ? 'ítem' : 'ítems'}</span>
        </div>
        <div style="font-size:1.15rem; font-weight:900; color:#fff; text-shadow:0 1px 3px rgba(0,0,0,0.6);">$${totalSum.toFixed(2)}</div>
      `;
    } else {
      floatWidget.style.display = "none";
    }
  }
  persistClientProgress();
}

function renderToonCart() {
  const container = document.getElementById("toon-cart-items");
  if (toonCart.length === 0) {
    container.innerHTML = `
      <div class="dd-empty-state">
        <span class="dd-empty-icon">🛒</span>
        <h3 class="dd-empty-title">Tu carrito está vacío</h3>
        <p class="dd-empty-sub">Explora nuestras hamburguesas, combos y promociones para armar tu pedido.</p>
        <button class="btn-gold" onclick="showScreen('screen-home')">🍔 IR AL MENÚ</button>
      </div>
    `;
    document.getElementById("cart-subtotal").innerText = "$0.00 (Bs. 0.00)";
    document.getElementById("cart-tax").innerText = "$0.00 (Bs. 0.00)";
    document.getElementById("cart-total").innerText = "$0.00 (Bs. 0.00)";
    updateCheckoutOrderSummary();
    return;
  }

  let subtotal = 0.0;
  let html = "";
  toonCart.forEach((item, idx) => {
    subtotal += item.subtotal;
    const image = /^(https:\/\/|\/static\/|\/api\/v1\/cliente\/media\/)/i.test(item.imagen_url || "")
      ? escapeClientHtml(item.imagen_url)
      : "/static/img/logo.png";
    const customizations = [...item.opciones, ...(item.extras || []).map(extra => `Extra: ${extra}`)];
    html += `
      <article class="client-cart-item">
        <img class="client-cart-item-image" src="${image}" alt="" loading="lazy" onerror="this.onerror=null;this.src='/static/img/logo.png';">
        <div class="client-cart-item-content">
          <div class="client-cart-item-heading">
            <strong>${escapeClientHtml(item.nombre)}</strong>
            <span class="client-cart-item-price">${formatPriceDual(item.subtotal)}</span>
          </div>
          ${item.promo_bundle_seq ? `<span class="client-cart-promo-badge">🎁 ${escapeClientHtml(item.promo_titulo || "Combo")}</span>` : ""}
          ${customizations.length ? `<ul class="client-cart-item-options">${customizations.map(option => `<li>${escapeClientHtml(option)}</li>`).join("")}</ul>` : '<small class="client-cart-item-options">Preparación estándar</small>'}
          <div class="client-cart-item-actions">
            <div class="client-cart-quantity" aria-label="Cantidad">
              <button type="button" aria-label="Disminuir cantidad" onclick="adjustToonCartQuantity(${idx}, -1)">−</button>
              <strong>${item.cantidad}</strong>
              <button type="button" aria-label="Aumentar cantidad" onclick="adjustToonCartQuantity(${idx}, 1)">+</button>
            </div>
            <button type="button" class="client-cart-action" onclick="editToonCartItem(${idx})">Editar</button>
            <button type="button" class="client-cart-action remove" onclick="removeToonCartItem(${idx})">${item.promo_bundle_seq ? "Quitar combo" : "Quitar"}</button>
          </div>
        </div>
      </article>
    `;
  });

  const snap = computeCartPricingSnapshot();
  const discountRow = document.getElementById("cart-discount-row");
  const discountVal = document.getElementById("cart-discount");
  const tipRow = document.getElementById("cart-tip-row");
  const tipVal = document.getElementById("cart-tip");
  if (discountRow) discountRow.style.display = snap.couponDiscount > 0 ? "flex" : "none";
  if (discountVal) discountVal.innerHTML = `-${formatPriceDual(snap.couponDiscount)}`;
  if (tipRow) tipRow.style.display = snap.tipAmount > 0 ? "flex" : "none";
  if (tipVal) tipVal.innerHTML = formatPriceDual(snap.tipAmount);

  container.innerHTML = html;
  document.getElementById("cart-subtotal").innerHTML = formatPriceDual(snap.rawSubtotal);
  document.getElementById("cart-tax").innerHTML = formatPriceDual(snap.tax);
  if (document.getElementById("cart-delivery-cost")) document.getElementById("cart-delivery-cost").innerHTML = formatPriceDual(snap.delivCost);
  if (document.getElementById("cart-empaque-cost")) document.getElementById("cart-empaque-cost").innerHTML = formatPriceDual(snap.empaqueCost);
  document.getElementById("cart-total").innerHTML = formatPriceDual(snap.total);
  renderCartUpsell();
  updateCheckoutOrderSummary();
}

function computeCartPricingSnapshot() {
  const rawSubtotal = Math.round(toonCart.reduce((sum, item) => sum + Number(item.subtotal || 0), 0) * 100) / 100;
  let couponDiscount = 0;
  if (appliedCouponData && Number(appliedCouponData.descuento_pct) > 0) {
    const allowedPids = new Set((appliedCouponData.producto_ids || []).map(Number));
    const eligibleSum = toonCart.reduce((sum, item) => {
      if (item.promo_bundle_seq) return sum;
      if (allowedPids.size && !allowedPids.has(Number(item.producto_id))) return sum;
      return sum + Number(item.subtotal || 0);
    }, 0);
    couponDiscount = Math.round(eligibleSum * (Number(appliedCouponData.descuento_pct) / 100) * 100) / 100;
  }
  const netSubtotal = Math.round(Math.max(0, rawSubtotal - couponDiscount) * 100) / 100;
  const tax = Math.round(netSubtotal * (checkoutTaxRate / 100) * 100) / 100;
  const type = document.getElementById("checkout-type")?.value || "mesa";
  const delivCost = type === "delivery" ? checkoutDeliveryFee : 0.0;
  const empaqueCost = type === "llevar" ? checkoutPackageFee : 0.0;
  let tipAmount = 0.0;
  if (selectedTipMode === "5pct") tipAmount = Math.round(netSubtotal * 0.05 * 100) / 100;
  else if (selectedTipMode === "10pct") tipAmount = Math.round(netSubtotal * 0.10 * 100) / 100;
  else if (selectedTipMode === "2usd") tipAmount = 2.0;
  const total = Math.round((netSubtotal + tax + delivCost + empaqueCost + tipAmount) * 100) / 100;
  return { rawSubtotal, couponDiscount, netSubtotal, tax, delivCost, empaqueCost, tipAmount, total };
}

function setCheckoutTipMode(mode) {
  selectedTipMode = mode || "none";
  document.querySelectorAll("#cart-tip-pills .tip-pill-btn").forEach(btn => {
    btn.classList.toggle("is-active", btn.getAttribute("data-tip-mode") === selectedTipMode);
  });
  renderToonCart();
  updateCheckoutAmountHint();
}

async function applyCheckoutCoupon() {
  const input = document.getElementById("checkout-coupon-code");
  const statusEl = document.getElementById("checkout-coupon-status");
  const code = (input?.value || "").trim();
  if (!code) {
    appliedCouponData = null;
    if (statusEl) statusEl.textContent = "";
    renderToonCart();
    updateCheckoutAmountHint();
    return;
  }
  try {
    const res = await fetch("/api/v1/cliente/cupones/validar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        codigo_cupon: code,
        producto_ids: toonCart.map(item => Number(item.producto_id))
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Cupón inválido.");
    appliedCouponData = data;
    if (statusEl) {
      statusEl.textContent = `✅ Cupón ${data.codigo_cupon} aplicado (-${Number(data.descuento_pct)}% OFF)`;
    }
    showToast(`🎟️ Cupón ${data.codigo_cupon} aplicado (-${Number(data.descuento_pct)}%).`, "success");
  } catch (err) {
    appliedCouponData = null;
    if (statusEl) statusEl.textContent = `❌ ${err.message}`;
    showToast(err.message, "warning");
  }
  renderToonCart();
  updateCheckoutAmountHint();
}

function renderCartUpsell() {
  const section = document.getElementById("cart-upsell-section");
  const grid = document.getElementById("cart-upsell-grid");
  if (!section || !grid) return;
  if (!toonCart.length || !Array.isArray(toonProducts) || !toonProducts.length) {
    section.hidden = true;
    grid.innerHTML = "";
    return;
  }
  const inCartIds = new Set(toonCart.map(i => Number(i.producto_id)));
  const complementKeywords = ["bebida", "refresco", "papa", "postre", "malteada", "teque", "jugo"];
  const complementCatIds = new Set(
    (toonCategories || [])
      .filter(c => complementKeywords.some(k => String(c.nombre || "").toLowerCase().includes(k)))
      .map(c => Number(c.id))
  );
  const candidates = toonProducts.filter(p =>
    p && p.activo !== false && p.disponible !== false && Number(p.stock || 0) > 0
    && !inCartIds.has(Number(p.id))
    && (complementCatIds.has(Number(p.categoria_id)) || complementKeywords.some(k => String(p.nombre || "").toLowerCase().includes(k)))
  );
  const picks = (candidates.length ? candidates : toonProducts.filter(p => !inCartIds.has(Number(p.id)) && Number(p.stock || 0) > 0)).slice(0, 4);
  if (!picks.length) {
    section.hidden = true;
    grid.innerHTML = "";
    return;
  }
  section.hidden = false;
  grid.innerHTML = picks.map(p => {
    const price = Number(p.precio_promocion || p.precio || 0);
    const img = getSafePromoMediaUrl(p.imagen_url);
    return `
      <div class="cart-upsell-card">
        <img src="${escapeClientHtml(img)}" alt="${escapeClientHtml(p.nombre)}" onerror="this.onerror=null;this.src='/static/img/logo.png';">
        <strong style="font-size:0.82rem;">${escapeClientHtml(p.nombre)}</strong>
        <span style="color:var(--gold-accent);font-weight:900;font-size:0.82rem;">$${price.toFixed(2)}</span>
        <button type="button" class="btn-gold" style="padding:0.3rem 0.5rem;font-size:0.75rem;" onclick="addUpsellProduct(${Number(p.id)})">+ Agregar</button>
      </div>
    `;
  }).join("");
}

function addUpsellProduct(prodId) {
  const prod = toonProducts.find(p => Number(p.id) === Number(prodId));
  if (!prod || prod.disponible === false || Number(prod.stock || 0) <= 0) return;
  const price = Number(prod.precio_promocion || prod.precio || 0);
  toonCart.push({
    producto_id: Number(prod.id),
    nombre: prod.nombre,
    imagen_url: prod.imagen_url || "",
    precio_unitario: price,
    cantidad: 1,
    subtotal: price,
    puntos_fidelidad: Math.max(0, Number(prod.puntos_fidelidad) || 0),
    opciones: [],
    extras: [],
    tiempo_preparacion: Number(prod.tiempo_preparacion) || 15
  });
  updateCartNavBadge();
  renderToonCart();
  showToast(`➕ ${prod.nombre} agregado al pedido.`, "success");
}

function removeToonCartItem(idx) {
  const target = toonCart[idx];
  if (!target) return;
  if (target.promo_bundle_seq) {
    toonCart = toonCart.filter(item => item.promo_bundle_seq !== target.promo_bundle_seq);
    showToast("Combo promocional eliminado del carrito.", "info");
  } else {
    toonCart.splice(idx, 1);
  }
  updateCartNavBadge();
  renderToonCart();
}

function _recalculatePromoBundleInCart(seq, nextQty) {
  const bundleItems = toonCart.filter(item => item.promo_bundle_seq === seq);
  if (!bundleItems.length) return;
  const promoId = Number(bundleItems[0].promo_id);
  const promo = (toonPromos || []).find(p => Number(p.id) === promoId);
  if (promo && Number(promo.precio_global) > 0) {
    const customsMap = {};
    const resolvedProducts = [];
    bundleItems.forEach(item => {
      const prod = (toonProducts || []).find(p => Number(p.id) === Number(item.producto_id))
        || { id: item.producto_id, nombre: item.nombre, precio: item.precio_unitario };
      resolvedProducts.push(prod);
      customsMap[Number(item.producto_id)] = {
        opciones: item.opciones || [],
        extras: item.extras || [],
        extraPrice: Number(item.promo_extra_unit || 0)
      };
    });
    const allocs = _computePromoBundleAllocations(promo, resolvedProducts, nextQty, customsMap);
    bundleItems.forEach((item, i) => {
      const alloc = allocs[i];
      item.cantidad = nextQty;
      item.promo_base_share_subtotal = alloc.allocBase;
      item.subtotal = alloc.lineSubtotal;
      item.precio_unitario = alloc.unitPrice;
    });
  } else {
    bundleItems.forEach(item => {
      const prevQty = Math.max(1, Number(item.cantidad) || 1);
      const baseUnit = Number(item.promo_base_share_subtotal || 0) / prevQty;
      const newBase = Math.round(baseUnit * nextQty * 100) / 100;
      const extraUnit = Number(item.promo_extra_unit || 0);
      item.cantidad = nextQty;
      item.promo_base_share_subtotal = newBase;
      item.subtotal = Math.round((newBase + extraUnit * nextQty) * 100) / 100;
      item.precio_unitario = Math.round((item.subtotal / nextQty) * 100) / 100;
    });
  }
}

function adjustToonCartQuantity(index, amount) {
  const item = toonCart[index];
  if (!item) return;
  if (item.promo_bundle_seq) {
    const nextQty = Math.max(1, Math.min(20, item.cantidad + amount));
    _recalculatePromoBundleInCart(item.promo_bundle_seq, nextQty);
  } else {
    item.cantidad = Math.max(1, Math.min(99, item.cantidad + amount));
    item.subtotal = item.precio_unitario * item.cantidad;
  }
  updateCartNavBadge();
  renderToonCart();
}

function editToonCartItem(index) {
  const item = toonCart[index];
  if (!item) return;
  const product = toonProducts.find(candidate => candidate.id === item.producto_id);
  if (!product || !product.activo || !product.disponible) {
    showToast("Este producto ya no está disponible para editar; puedes quitarlo del pedido.", "warning");
    return;
  }
  editingCartIndex = index;
  openProductModal(item.producto_id);
}

function toggleCheckoutFields() {
  const type = document.getElementById("checkout-type").value;
  const sectionMesa = document.getElementById("section-checkout-mesa");
  const sectionDelivery = document.getElementById("section-checkout-delivery");
  const deliveryRow = document.getElementById("cart-delivery-row");
  const empaqueRow = document.getElementById("cart-empaque-row");
  const takeawayNote = document.getElementById("checkout-takeaway-note");
  const deliveryFields = [
    document.getElementById("deliv-nombre"),
    document.getElementById("deliv-telefono"),
    document.getElementById("deliv-direccion")
  ].filter(Boolean);
  deliveryFields.forEach(field => {
    field.required = type === "delivery";
  });

  if (type === "mesa") {
    sectionMesa.style.display = "block";
    sectionDelivery.style.display = "none";
    if (takeawayNote) takeawayNote.hidden = true;
    if (deliveryRow) deliveryRow.style.display = "none";
    if (empaqueRow) empaqueRow.style.display = "none";
  } else if (type === "delivery") {
    sectionMesa.style.display = "none";
    sectionDelivery.style.display = "block";
    if (takeawayNote) takeawayNote.hidden = true;
    if (deliveryRow) deliveryRow.style.display = "flex";
    if (empaqueRow) empaqueRow.style.display = "none";
    setTimeout(() => initDeliveryInteractiveMap(), 150);
  } else {
    sectionMesa.style.display = "none";
    sectionDelivery.style.display = "none";
    if (takeawayNote) takeawayNote.hidden = false;
    if (deliveryRow) deliveryRow.style.display = "none";
    if (empaqueRow) empaqueRow.style.display = "flex";
  }
  renderToonCart();
  updateCheckoutAmountHint();
  updateCheckoutPaymentFields();
  updateCheckoutOrderSummary();
}

function syncMesaPaymentMode(mode) {
  const normalized = mode === "PAGAR_DESPUES" ? "PAGAR_DESPUES" : "PAGAR_ANTES";
  selectedMesaPaymentMode = normalized;
  document.querySelectorAll('input[name="modo_pago"], input[name="modo_pago_step4"]').forEach(radio => {
    radio.checked = radio.value === normalized;
  });
  updateCheckoutOrderSummary();
  updateCheckoutPaymentFields();
}

function updateCheckoutPaymentFields() {
  const method = document.getElementById("checkout-payment")?.value || "Efectivo";
  const selectedMode = document.querySelector('input[name="modo_pago"]:checked')?.value || selectedMesaPaymentMode || "PAGAR_ANTES";
  selectedMesaPaymentMode = selectedMode;
  const orderType = document.getElementById("checkout-type")?.value;
  const deferredPayment = orderType === "mesa" && selectedMode === "PAGAR_DESPUES";
  const step4MesaCard = document.getElementById("checkout-step4-mesa-mode");
  const step4MesaLabel = document.getElementById("checkout-step4-mesa-label");
  if (step4MesaCard) {
    step4MesaCard.classList.toggle("u-display-none", orderType !== "mesa");
  }
  if (step4MesaLabel) {
    step4MesaLabel.textContent = currentDetectedMesa ? `Mesa #${currentDetectedMesa}` : "Sin mesa asignada";
  }
  document.querySelectorAll('input[name="modo_pago_step4"]').forEach(radio => {
    radio.checked = radio.value === selectedMode;
  });
  const currencyGroup = document.getElementById("checkout-currency-group");
  const referenceGroup = document.getElementById("checkout-payment-reference-group");
  const currencySelect = document.getElementById("checkout-currency");
  const referenceInput = document.getElementById("checkout-payment-reference");
  const bankInfo = document.getElementById("checkout-payment-bank-details");
  const methodGroup = document.getElementById("checkout-payment-method-group");
  const instructions = document.getElementById("checkout-payment-instructions");
  const submitButton = document.querySelector('#screen-checkout button[onclick="submitFinalOrder()"]');
  if (!currencyGroup || !referenceGroup || !currencySelect || !referenceInput) return;

  const isMobilePay = method === "Pago Móvil";
  const bankDetailsConfigured = Boolean(pagoMovilConfig.banco && pagoMovilConfig.telefono && pagoMovilConfig.rif && pagoMovilConfig.titular);
  if (submitButton) {
    submitButton.textContent = deferredPayment
      ? "CONFIRMAR CUENTA ABIERTA · ENVIAR PEDIDO →"
      : isMobilePay
        ? "REGISTRAR REFERENCIA · IR A SEGUIMIENTO →"
        : "ENVIAR PEDIDO · PAGAR EN CAJA →";
    submitButton.setAttribute("aria-describedby", "checkout-payment-hint");
  }
  referenceGroup.style.display = !deferredPayment && isMobilePay ? "block" : "none";
  if (bankInfo) {
    bankInfo.hidden = true;
    if (isMobilePay && !bankDetailsConfigured) {
      bankInfo.textContent = "Pago Móvil no está disponible: el restaurante aún no configuró los datos bancarios.";
    }
  }
  currencyGroup.style.display = !deferredPayment && method !== "Punto de Venta" ? "block" : "none";
  if (isMobilePay) currencySelect.value = "VES";
  if (method === "Punto de Venta") currencySelect.value = "USD";
  currencySelect.disabled = deferredPayment || isMobilePay || method === "Punto de Venta";
  referenceInput.required = !deferredPayment && isMobilePay;
  const methodSelect = document.getElementById("checkout-payment");
  if (methodSelect) methodSelect.disabled = deferredPayment;
  if (methodGroup) methodGroup.style.display = deferredPayment ? "none" : "block";
  if (instructions) instructions.hidden = deferredPayment;
  if (deferredPayment) {
    if (bankInfo) bankInfo.style.display = "none";
    const hint = document.getElementById("checkout-payment-hint");
    if (hint) hint.textContent = "Cuenta abierta en esta mesa. El pedido pasa a cocina; al finalizar, paga con Caja.";
    return;
  }
  updateCheckoutAmountHint();
}

function updateCheckoutAmountHint() {
  const hint = document.getElementById("checkout-payment-hint");
  if (!hint) return;
  const method = document.getElementById("checkout-payment")?.value || "Efectivo";
  const currency = document.getElementById("checkout-currency")?.value || "USD";
  const snap = computeCartPricingSnapshot();
  const total = snap.total;
  updateCheckoutOrderSummary();
  const paymentInstructions = document.getElementById("checkout-payment-instructions");
  if (paymentInstructions) paymentInstructions.hidden = method !== "Pago Móvil";
  if (method === "Pago Móvil") {
    const required = Number.isFinite(tasaCambioBs) ? (total * tasaCambioBs).toFixed(2) : null;
    hint.textContent = required
      ? `Envía Bs. ${required}, copia la referencia que te entrega tu banco e ingrésala aquí. Caja verificará manualmente antes de liberar el pedido a cocina.`
      : "La tasa BCV no está disponible; Pago Móvil no puede calcularse ahora.";
    renderMobilePaymentInstructions(required);
    return;
  }
  renderMobilePaymentInstructions(null);
  if (method === "Punto de Venta") {
    hint.textContent = "Paga en el punto de venta de Caja. El pedido solo pasará a cocina después de que el personal confirme el cobro.";
    return;
  }
  hint.textContent = currency === "VES" && Number.isFinite(tasaCambioBs)
    ? `Paga en Caja: ${currency === "VES" ? `Bs. ${(total * tasaCambioBs).toFixed(2)}` : `$${total.toFixed(2)}`}. El pedido pasa a cocina cuando Caja confirme el efectivo.`
    : "Paga en Caja al retirar o antes de preparar. El pedido pasa a cocina cuando Caja confirme el efectivo.";
}

function renderMobilePaymentInstructions(amountInBolivares) {
  const container = document.getElementById("checkout-payment-instructions");
  if (!container) return;
  const bank = pagoMovilConfig.banco;
  const details = [
    ["Banco", bank],
    ["Teléfono", pagoMovilConfig.telefono],
    ["RIF", pagoMovilConfig.rif],
    ["Titular", pagoMovilConfig.titular],
  ];
  const rateInfo = document.getElementById("checkout-rate-info")?.textContent || "";
  container.innerHTML = `
    <h3>Pago Móvil: pasos sencillos</h3>
    ${bank && pagoMovilConfig.telefono && pagoMovilConfig.rif && pagoMovilConfig.titular
      ? ""
      : '<p class="checkout-payment-warning">El restaurante aún no ha configurado todos los datos de Pago Móvil. Selecciona otra forma de pago o consulta con Caja.</p>'}
    <ol>
      <li>Copia los datos y realiza la transferencia desde tu banco.</li>
      <li>Envía el monto exacto indicado abajo.</li>
      <li>Escribe el número de referencia en el campo siguiente.</li>
      <li>Caja verificará el pago manualmente antes de enviarlo a cocina.</li>
    </ol>
    <div class="checkout-copy-list">
      ${details.map(([label, value]) => `
        <div class="checkout-copy-row"><span><small>${label}</small><strong>${escapeClientHtml(value || "No configurado")}</strong></span>
          ${value ? `<button type="button" data-copy-value="${escapeClientHtml(value)}" data-copy-label="${label}">Copiar</button>` : ""}
        </div>
      `).join("")}
      <div class="checkout-copy-row amount"><span><small>Monto exacto a enviar</small><strong>${amountInBolivares ? `Bs. ${amountInBolivares}` : "Tasa no disponible"}</strong></span>
        ${amountInBolivares ? `<button type="button" data-copy-value="${amountInBolivares}" data-copy-label="Monto">Copiar</button>` : ""}
      </div>
    </div>
    <small class="checkout-rate-note">${escapeClientHtml(rateInfo)}</small>
  `;
}

async function copyCheckoutValue(value, label) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(String(value));
    } else {
      const input = document.createElement("textarea");
      input.value = String(value);
      input.setAttribute("readonly", "");
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.appendChild(input);
      input.select();
      const copied = document.execCommand("copy");
      input.remove();
      if (!copied) throw new Error("El navegador no permitió copiar el dato.");
    }
    showToast(`${label} copiado.`, "success");
  } catch (error) {
    console.error("No se pudo copiar el dato de Pago Móvil.", error);
    showToast("No se pudo copiar. Mantén presionado el dato para seleccionarlo.", "warning");
  }
}

function updateCheckoutOrderSummary() {
  const snap = computeCartPricingSnapshot();
  const subtotal = snap.rawSubtotal;
  const tax = snap.tax;
  const type = document.getElementById("checkout-type")?.value || "mesa";
  const deliveryFee = snap.delivCost;
  const packageFee = snap.empaqueCost;
  const total = snap.total;
  const destinationSummary = document.getElementById("checkout-summary-destination");
  if (destinationSummary) {
    const destination = type === "mesa"
      ? `🍽️ Pedido en mesa · ${document.getElementById("checkout-mesa-name")?.textContent.trim() || `Mesa #${currentDetectedMesa || 1}`}`
      : type === "delivery"
        ? `🛵 Delivery · ${document.getElementById("deliv-direccion")?.value.trim() || "Dirección pendiente"}`
        : "🛍️ Retiro en mostrador";
    const paymentMode = document.querySelector('input[name="modo_pago"]:checked')?.value;
    destinationSummary.innerHTML = `<strong>${escapeClientHtml(destination)}</strong>${
      type === "delivery" && document.getElementById("deliv-nombre")?.value.trim()
        ? `<small>Recibe: ${escapeClientHtml(document.getElementById("deliv-nombre").value.trim())}</small>`
        : ""
    }${
      type === "mesa" && paymentMode === "PAGAR_DESPUES"
        ? "<small>Cuenta abierta: pagarás en Caja al finalizar.</small>"
        : ""
    }`;
  }
  const cartSummary = document.getElementById("checkout-cart-items");
  if (cartSummary) {
    cartSummary.innerHTML = toonCart.length
      ? toonCart.map(item => `<div class="checkout-item-row"><span>${escapeClientHtml(item.nombre)} × ${item.cantidad}</span><strong>${formatPriceDual(item.subtotal)}</strong></div>`).join("")
      : '<p class="checkout-empty-cart">No hay productos en el pedido.</p>';
  }
  const earnedPoints = toonCart.reduce(
    (sum, item) => sum + (Math.max(0, Number(item.puntos_fidelidad) || 0) * item.cantidad),
    0
  );
  const values = {
    "checkout-summary-subtotal": subtotal,
    "checkout-summary-discount": snap.couponDiscount,
    "checkout-summary-tax": tax,
    "checkout-summary-delivery": deliveryFee,
    "checkout-summary-package": packageFee,
    "checkout-summary-tip": snap.tipAmount,
    "checkout-summary-total": total,
  };
  Object.entries(values).forEach(([id, value]) => {
    const element = document.getElementById(id);
    if (element) {
      element.innerHTML = id === "checkout-summary-discount" ? `-${formatPriceDual(value)}` : formatPriceDual(value);
    }
  });
  const discountRow = document.getElementById("checkout-summary-discount-row");
  const tipRow = document.getElementById("checkout-summary-tip-row");
  const deliveryRow = document.getElementById("checkout-summary-delivery-row");
  const packageRow = document.getElementById("checkout-summary-package-row");
  if (discountRow) discountRow.style.display = snap.couponDiscount > 0 ? "flex" : "none";
  if (tipRow) tipRow.style.display = snap.tipAmount > 0 ? "flex" : "none";
  if (deliveryRow) deliveryRow.style.display = deliveryFee > 0 ? "flex" : "none";
  if (packageRow) packageRow.style.display = packageFee > 0 ? "flex" : "none";
  const pointsSummary = document.getElementById("checkout-summary-points");
  if (pointsSummary) {
    pointsSummary.textContent = `Puntos estimados al pagar: ${earnedPoints}${earnedPoints ? " (se acreditan cuando Caja confirma el pago)" : ""}`;
  }
}

async function submitFinalOrder() {
  if (isSubmittingClientOrder) return;
  if (toonCart.length === 0) {
    showToast("Tu carrito está vacío. Agrega productos primero.", "warning");
    return;
  }

  const orderType = document.getElementById("checkout-type").value;
  if (!validateCheckoutDelivery()) {
    showScreen("screen-checkout-delivery");
    return;
  }
  const selectedModoPago = orderType === "mesa"
    ? (document.querySelector('input[name="modo_pago"]:checked')?.value || "PAGAR_ANTES")
    : "PAGAR_ANTES";
  const deferredPayment = orderType === "mesa" && selectedModoPago === "PAGAR_DESPUES";
  const paymentMethod = deferredPayment ? null : document.getElementById("checkout-payment").value;
  const paymentCurrency = deferredPayment ? "USD" : document.getElementById("checkout-currency").value;
  const paymentReference = deferredPayment ? "" : document.getElementById("checkout-payment-reference").value.trim();

  if (!deferredPayment && paymentMethod === "Pago Móvil" && (!paymentReference || !Number.isFinite(tasaCambioBs))) {
    showToast("Pago Móvil requiere una tasa BCV disponible y la referencia de la operación.", "warning");
    return;
  }
  if (!deferredPayment && paymentMethod === "Pago Móvil" && !(pagoMovilConfig.banco && pagoMovilConfig.telefono && pagoMovilConfig.rif && pagoMovilConfig.titular)) {
    showToast("Pago Móvil no está configurado por el restaurante. Elige otro método o consulta con caja.", "warning");
    return;
  }

  if (orderType === "mesa" && !currentDetectedMesa) {
    showToast("Escanea el código QR de una mesa registrada antes de enviar tu pedido.", "warning");
    openQrScannerModal();
    return;
  }

  let mesaName = currentDetectedMesa ? `Mesa ${currentDetectedMesa}` : "Mostrador";
  let delivNombre = null;
  let delivTel = null;
  let delivDir = null;
  const deliveryCoordinates = orderType === "delivery" ? currentCustomerGPS : null;

  if (orderType === "delivery") {
    delivNombre = document.getElementById("deliv-nombre").value.trim();
    delivTel = document.getElementById("deliv-telefono").value.trim();
    delivDir = document.getElementById("deliv-direccion").value.trim();

    if (!delivNombre || !delivDir || !delivTel) {
      showToast("Por favor completa los datos obligatorios de entrega para Delivery.", "danger");
      return;
    }
    mesaName = "Delivery";
  }

  const promoCounts = new Map();
  const seenBundleSeqs = new Set();
  toonCart.forEach(item => {
    if (item.promo_id && item.promo_bundle_seq && !seenBundleSeqs.has(item.promo_bundle_seq)) {
      seenBundleSeqs.add(item.promo_bundle_seq);
      promoCounts.set(
        Number(item.promo_id),
        (promoCounts.get(Number(item.promo_id)) || 0) + Math.max(1, Number(item.cantidad) || 1)
      );
    }
  });
  const promocionesPayload = Array.from(promoCounts.entries()).map(([promocion_id, cantidad]) => ({
    promocion_id,
    cantidad
  }));

  const pricingSnap = computeCartPricingSnapshot();
  const payload = {
    numero_mesa: mesaName,
    tipo: orderType,
    modo_pago: selectedModoPago,
    nombre_cliente_delivery: delivNombre,
    telefono_delivery: delivTel,
    direccion_delivery: delivDir,
    delivery_lat: deliveryCoordinates ? Number(deliveryCoordinates.lat) : null,
    delivery_lng: deliveryCoordinates ? Number(deliveryCoordinates.lng) : null,
    metodo_pago: paymentMethod,
    moneda_pago: paymentCurrency,
    referencia_pago: paymentMethod === "Pago Móvil" ? paymentReference : null,
    codigo_cupon: appliedCouponData?.codigo_cupon || null,
    propina: pricingSnap.tipAmount,
    detalles: toonCart.map(item => ({
      producto_id: item.producto_id,
      cantidad: item.cantidad,
      personalizaciones: { opciones: item.opciones, extras: item.extras || [] }
    })),
    promociones: promocionesPayload
  };

  if (!navigator.onLine) {
    updateClientNetworkStatus(false);
    showToast("No hay conexión. El pedido permanece guardado en este dispositivo; vuelve a enviarlo cuando recuperes internet.", "warning");
    return;
  }

  isSubmittingClientOrder = true;
  const submitButton = document.querySelector('#screen-checkout button[onclick="submitFinalOrder()"]');
  const originalSubmitLabel = submitButton?.textContent;
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.setAttribute("aria-busy", "true");
    submitButton.textContent = "Registrando pedido…";
  }
  try {
    const res = await fetch("/api/v1/cliente/pedidos", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "Error al registrar el pedido");
    }
    const order = await res.json();

    const prepEstimateMinutes = Math.max(0, ...toonCart.map(item => item.tiempo_preparacion || 0));
    currentPendingOrderId = order.id;
    currentTrackingToken = order.token_seguimiento || null;
    setLegacyTrackingValue("dd-tracking-order-id", String(order.id));
    if (currentTrackingToken) {
      setLegacyTrackingValue("dd-tracking-token", currentTrackingToken);
    } else {
      removeLegacyTrackingValue("dd-tracking-token");
    }
    cachedTrackingProgress = null;
    toonCart = [];
    appliedCouponData = null;
    selectedTipMode = "none";
    const couponInputEl = document.getElementById("checkout-coupon-code");
    const couponStatusEl = document.getElementById("checkout-coupon-status");
    if (couponInputEl) couponInputEl.value = "";
    if (couponStatusEl) couponStatusEl.textContent = "";
    document.querySelectorAll("#cart-tip-pills .tip-pill-btn").forEach(btn => {
      btn.classList.toggle("is-active", btn.getAttribute("data-tip-mode") === "none");
    });
    updateCartNavBadge();

    document.getElementById("track-order-num").innerText = `PEDIDO #${order.id}`;
    const waitingForCashier = order.estado_pago === "PENDIENTE" && order.modo_pago !== "PAGAR_DESPUES";
    document.getElementById("track-order-status").innerText = order.estado_pago === "PENDIENTE_VALIDACION"
      ? "PAGO MÓVIL PENDIENTE DE VALIDACIÓN"
      : waitingForCashier
        ? "PENDIENTE DE COBRO EN CAJA"
        : (order.modo_pago === "PAGAR_DESPUES" ? "CUENTA ABIERTA EN MESA" : "RECIBIDO EN COCINA");
    const preparationNotice = prepEstimateMinutes
      ? ` Preparación estimada: ${prepEstimateMinutes} min; no incluye el traslado.`
      : "";
    document.getElementById("track-order-info").innerText = order.estado_pago === "PENDIENTE_VALIDACION"
      ? `Referencia ${order.referencia_pago} recibida. Caja validará el pago antes de liberar el pedido. Total: Bs. ${Number(order.monto_pago).toFixed(2)}.${preparationNotice}`
      : waitingForCashier
        ? `Tu pedido está en la cola de Caja. Cocina lo recibirá después de confirmar el pago${order.metodo_pago === "Punto de Venta" ? " en el terminal" : " en efectivo"}.${preparationNotice}`
      : order.tipo === "llevar"
        ? `Pedido para retirar en mostrador. Código de seguridad: ${order.codigo_retiro}. Muéstralo en caja al recibirlo.${preparationNotice}`
        : `${order.tipo === "delivery" ? `Entrega solicitada en: ${order.direccion_delivery}` : `Procesando para ${order.numero_mesa}`}.${preparationNotice}`;
    updateAsyncPaymentStatus(order.estado_pago, order.metodo_pago, order.modo_pago);

    showToast("¡Pedido emitido! Sigue el estado y el pago desde esta pantalla.", "success");
    showScreen("screen-tracking");
  } catch (err) {
    if (!navigator.onLine || err instanceof TypeError) {
      updateClientNetworkStatus(false);
      showToast("Se interrumpió la conexión y no podemos confirmar si el servidor recibió el pedido. Conservé el borrador; revisa «Pedidos» antes de reenviarlo para evitar duplicados.", "warning");
    } else {
      showToast(err.message, "danger");
    }
  } finally {
    isSubmittingClientOrder = false;
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.removeAttribute("aria-busy");
      if (originalSubmitLabel) submitButton.textContent = originalSubmitLabel;
    }
  }
}

function openOtpModal(orderId, code) {
  const modal = document.getElementById("otp-modal");
  if (!modal) return;
  currentPendingOrderId = orderId;
  const simLabel = document.getElementById("otp-simulated-code");
  const codeInput = document.getElementById("otp-input-code");
  if (simLabel) simLabel.innerText = `Código sim enviado por WhatsApp: ${code}`;
  if (codeInput) codeInput.value = code || "";
  modal.classList.add("open");
}

async function submitOtpVerification() {
  const codeInput = document.getElementById("otp-input-code")?.value;
  if (!codeInput) {
    showToast("Ingresa el código OTP de 6 dígitos", "warning");
    return;
  }

  try {
    const headers = { ...Auth.getHeaders() };
    if (activeTrackingOrder?.token_seguimiento) {
      headers["X-Order-Tracking-Token"] = activeTrackingOrder.token_seguimiento;
    }
    const res = await fetch("/api/v1/cliente/pedidos/verificar-otp", {
      method: "POST",
      headers,
      body: JSON.stringify({
        pedido_id: currentPendingOrderId,
        codigo_otp: codeInput
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Código OTP incorrecto");
    }

    showToast("✅ Teléfono verificado con éxito por OTP", "success");
    document.getElementById("otp-modal")?.classList.remove("open");
    showScreen("screen-tracking");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

let clientHistoryOrdersCache = [];

async function loadHistorialPedidos() {
  try {
    const res = await fetch("/api/v1/cliente/pedidos/historial", {
      headers: Auth.getHeaders()
    });
    if (!res.ok) return;
    const pedidos = await res.json();
    clientHistoryOrdersCache = Array.isArray(pedidos) ? pedidos : [];
    
    let html = "";
    if (!clientHistoryOrdersCache.length) {
      html = `<p style="color: var(--text-muted); text-align: center;">No tienes pedidos anteriores registrados.</p>`;
    } else {
      clientHistoryOrdersCache.forEach(p => {
        const isActive = !["ENTREGADO", "CANCELADO"].includes(p.estado);
        html += `
          <div style="background: var(--toon-card); border: 1px solid var(--toon-border); padding: 1rem; border-radius: var(--radius-sm); margin-bottom: 0.85rem;">
            <div style="display: flex; justify-content: space-between; font-weight: 800;">
              <span>PEDIDO #${p.id} (${escapeClientHtml(p.numero_mesa)})</span>
              <span>${formatPriceDual(p.total)}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.3rem;">Estado: <strong style="color: var(--neon-green);">${escapeClientHtml(p.estado_delivery || p.estado)}</strong></div>
            <div class="historial-actions-row">
              ${isActive ? `<button type="button" class="btn-gold" onclick="trackOrderById(${Number(p.id)})">📍 Seguir pedido</button>` : ""}
              ${Array.isArray(p.detalles) && p.detalles.length ? `<button type="button" class="btn btn-outline" onclick="reorderHistoryOrder(${Number(p.id)})">⚡ Volver a pedir</button>` : ""}
            </div>
          </div>
        `;
      });
    }
    document.getElementById("historial-orders-list").innerHTML = html;
  } catch (err) {
    console.error(err);
  }
}

function reorderHistoryOrder(orderId) {
  const order = clientHistoryOrdersCache.find(o => Number(o.id) === Number(orderId));
  if (!order || !Array.isArray(order.detalles) || !order.detalles.length) return;
  let added = 0;
  order.detalles.forEach(d => {
    const product = (toonProducts || []).find(p => Number(p.id) === Number(d.producto_id));
    if (!product || product.activo === false || product.disponible === false || Number(product.stock || 0) < Number(d.cantidad || 1)) {
      return;
    }
    const price = Number(product.precio_promocion || product.precio || 0);
    toonCart.push({
      producto_id: product.id,
      nombre: product.nombre,
      imagen_url: product.imagen_url || "",
      precio_unitario: price,
      cantidad: Number(d.cantidad || 1),
      subtotal: Math.round(price * Number(d.cantidad || 1) * 100) / 100,
      puntos_fidelidad: Math.max(0, Number(product.puntos_fidelidad) || 0),
      opciones: [],
      extras: [],
      tiempo_preparacion: Number(product.tiempo_preparacion) || 15
    });
    added += Number(d.cantidad || 1);
  });
  if (!added) {
    showToast("Ninguno de los productos de ese pedido está disponible ahora.", "warning");
    return;
  }
  updateCartNavBadge();
  renderToonCart();
  showScreen("screen-carrito");
  showToast(`⚡ Se cargaron ${added} producto(s) del pedido #${orderId} al carrito.`, "success");
}

function trackOrderById(orderId) {
  currentPendingOrderId = Number(orderId);
  currentTrackingToken = null;
  setLegacyTrackingValue("dd-tracking-order-id", String(currentPendingOrderId));
  removeLegacyTrackingValue("dd-tracking-token");
  cachedTrackingProgress = null;
  persistClientProgress();
  showScreen("screen-tracking");
}

function startTrackingRefresh() {
  if (!currentPendingOrderId) {
    const savedTracking = readClientProgress()?.tracking || {};
    const savedOrderId = Number(savedTracking.orderId || getLegacyTrackingValue("dd-tracking-order-id"));
    currentPendingOrderId = Number.isInteger(savedOrderId) && savedOrderId > 0 ? savedOrderId : null;
    currentTrackingToken = savedTracking.token || getLegacyTrackingValue("dd-tracking-token");
  }
  renderCachedTrackingProgress();
  if (trackingRefreshTimer) clearInterval(trackingRefreshTimer);
  refreshTrackedOrder();
  trackingRefreshTimer = setInterval(() => {
    if (document.getElementById("screen-tracking")?.classList.contains("active")) {
      refreshTrackedOrder();
    }
  }, 15000);
}

function updateAsyncPaymentStatus(paymentStatus, paymentMethod, paymentMode) {
  const statusElement = document.getElementById("track-async-payment-status");
  if (!statusElement) return;

  const pendingText = paymentStatus === "PENDIENTE_VALIDACION"
    ? {
      state: "pending",
      title: "Pago Móvil enviado · esperando validación",
      detail: "Caja comprobará la referencia manualmente. No vuelvas a transferir; esta pantalla se actualizará cuando validen el pago."
    }
    : paymentStatus === "PENDIENTE" && paymentMode !== "PAGAR_DESPUES"
      ? {
        state: "pending",
        title: "Pedido recibido · esperando confirmación de Caja",
        detail: `${paymentMethod === "Punto de Venta" ? "Paga en el terminal de Caja." : "Paga en Caja."} El pedido pasará a cocina cuando el personal confirme el cobro.`
      }
      : paymentMode === "PAGAR_DESPUES" && paymentStatus !== "PAGADO"
        ? {
          state: "open",
          title: "Cuenta abierta · pedido enviado a cocina",
          detail: "Disfruta tu pedido y paga en Caja al finalizar."
        }
        : paymentStatus === "PAGADO"
          ? {
            state: "complete",
            title: "Pago confirmado",
            detail: "El restaurante recibió la confirmación del pago."
          }
          : paymentStatus === "RECHAZADO"
            ? {
              state: "error",
              title: "Pago no validado",
              detail: "Contacta a Caja antes de volver a pagar. No realices otra transferencia sin confirmar el estado de esta operación."
            }
            : null;

  statusElement.hidden = !pendingText;
  statusElement.dataset.state = pendingText?.state || "";
  statusElement.innerHTML = pendingText
    ? `<strong>${escapeClientHtml(pendingText.title)}</strong><span>${escapeClientHtml(pendingText.detail)}</span>`
    : "";
}

async function refreshTrackedOrder() {
  if (!currentPendingOrderId) {
    const status = document.getElementById("track-order-status");
    if (status) status.textContent = "No hay un pedido seleccionado";
    const info = document.getElementById("track-order-info");
    if (info) info.textContent = "Inicia sesión y selecciona un pedido de tu historial para consultar su estado.";
    return;
  }

  try {
    const headers = { ...Auth.getHeaders() };
    if (currentTrackingToken) headers["X-Order-Tracking-Token"] = currentTrackingToken;
    const response = await fetch(`/api/v1/cliente/pedidos/${currentPendingOrderId}/seguimiento`, { headers });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "No se pudo consultar el pedido.");

    document.getElementById("track-order-num").textContent = `PEDIDO #${result.id}`;
    const statusLabels = {
      PAGO_PENDIENTE: "Pago pendiente de validación",
      PENDIENTE: "Pedido recibido",
      COBRADO: "Pago confirmado",
      EN_PREPARACION: "En preparación",
      LISTO: "Listo",
      ENTREGADO: "Entregado",
      CANCELADO: "Cancelado"
    };
    const deliveryLabels = {
      PENDIENTE: "Esperando asignación de repartidor",
      ASIGNADO: "Repartidor asignado",
      RECOGIDO: "Pedido recogido por el repartidor",
      EN_CAMINO: "Repartidor en camino",
      ENTREGADO: "Pedido entregado"
    };
    const state = result.tipo === "delivery" && result.estado_delivery
      && result.estado_pago === "PAGADO"
      ? deliveryLabels[result.estado_delivery] || result.estado_delivery
      : result.tipo === "delivery" && ["PENDIENTE_VALIDACION", "RECHAZADO"].includes(result.estado_pago)
        ? (result.estado_pago === "RECHAZADO" ? "Pago rechazado" : "Pago pendiente de validación")
      : result.estado_pago === "PENDIENTE_VALIDACION"
        ? "Pago Móvil pendiente de validación"
      : result.estado_pago === "PENDIENTE" && result.modo_pago !== "PAGAR_DESPUES"
        ? "Pendiente de cobro en Caja"
      : result.modo_pago === "PAGAR_DESPUES" && result.estado_pago !== "PAGADO"
        ? "Cuenta abierta · pedido en cocina"
      : statusLabels[result.estado] || result.estado;
    document.getElementById("track-order-status").textContent = state;
    updateAsyncPaymentStatus(result.estado_pago, result.metodo_pago, result.modo_pago);
    const paymentStatus = result.estado_pago === "PENDIENTE"
      ? "pendiente de confirmación en Caja"
      : result.estado_pago === "PENDIENTE_VALIDACION"
        ? "en verificación manual por Caja"
        : result.estado_pago;
    document.getElementById("track-order-info").textContent = result.tipo === "delivery"
      ? `Entrega a: ${result.direccion_delivery || "dirección registrada"}. Pago ${paymentStatus}. Repartidor: ${result.repartidor_nombre || "pendiente de asignación"}${result.repartidor_telefono ? ` · ${result.repartidor_telefono}` : ""}.`
      : `Modalidad: ${result.tipo === "mesa" ? result.numero_mesa : result.tipo}. Pago ${paymentStatus}.`;

    const deliveryCode = document.getElementById("track-delivery-code");
    const deliveryCodeValue = document.getElementById("track-delivery-code-value");
    if (deliveryCode && deliveryCodeValue) {
      deliveryCode.hidden = !result.codigo_otp;
      deliveryCodeValue.textContent = result.codigo_otp || "";
    }

    const mapContainer = document.getElementById("track-order-map");
    if (mapContainer) {
      const riderLat = Number(result.repartidor_lat);
      const riderLng = Number(result.repartidor_lng);
      const hasRiderLocation = result.repartidor_lat !== null
        && result.repartidor_lat !== undefined
        && result.repartidor_lng !== null
        && result.repartidor_lng !== undefined
        && Number.isFinite(riderLat)
        && Number.isFinite(riderLng);
      const destinationLat = Number(result.delivery_lat);
      const destinationLng = Number(result.delivery_lng);
      if (result.tipo === "delivery" && hasRiderLocation) {
        const points = [[riderLat, riderLng]];
        if (
          result.delivery_lat !== null
          && result.delivery_lat !== undefined
          && result.delivery_lng !== null
          && result.delivery_lng !== undefined
          && Number.isFinite(destinationLat)
          && Number.isFinite(destinationLng)
        ) {
          points.push([destinationLat, destinationLng]);
        }
        const latitudes = points.map(point => point[0]);
        const longitudes = points.map(point => point[1]);
        const pad = 0.006;
        const bbox = [
          Math.min(...longitudes) - pad,
          Math.min(...latitudes) - pad,
          Math.max(...longitudes) + pad,
          Math.max(...latitudes) + pad
        ].map(value => value.toFixed(6)).join(",");
        const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${riderLat.toFixed(6)},${riderLng.toFixed(6)}`;
        const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${riderLat},${riderLng}`)}`;
        mapContainer.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem;margin-bottom:.5rem"><strong>🛵 Repartidor en ruta</strong><small style="color:var(--neon-green)">Ubicación actualizada</small></div><iframe title="Ubicación en vivo del repartidor" src="${mapUrl}" loading="lazy" referrerpolicy="no-referrer" style="width:100%;height:240px;border:0;border-radius:12px"></iframe><a class="btn btn-outline" style="display:inline-flex;margin-top:.5rem" href="${directionsUrl}" target="_blank" rel="noopener noreferrer">Abrir ubicación en Google Maps</a></div>`;
      } else if (result.tipo === "delivery" && result.estado_delivery === "EN_CAMINO") {
        mapContainer.innerHTML = '<p role="status" style="color:var(--text-muted)">El repartidor está en camino. Esperando la primera actualización de ubicación del dispositivo.</p>';
      } else {
        mapContainer.innerHTML = "";
      }
    }

    const progress = document.getElementById("track-order-progress");
    const visualStepper = document.getElementById("track-visual-stepper");
    if (visualStepper) {
      const visualStages = [
        { key: "recibido", label: "1. Recibido" },
        { key: "cocina", label: "2. Cocina" },
        { key: "listo", label: result.tipo === "delivery" ? "3. En Ruta" : "3. Listo" },
        { key: "entregado", label: "4. Entregado" }
      ];
      let activeStage = 0;
      if (result.estado === "EN_PREPARACION" || result.estado === "COBRADO") activeStage = 1;
      if (result.estado === "LISTO" || result.estado_delivery === "RECOGIDO" || result.estado_delivery === "EN_CAMINO") activeStage = 2;
      if (result.estado === "ENTREGADO") activeStage = 3;
      visualStepper.innerHTML = visualStages.map((s, idx) => `
        <div class="tracking-step-chip ${idx < activeStage ? "is-done" : idx === activeStage ? "is-current" : ""}">${s.label}</div>
      `).join("");
    }
    if (progress) {
      const deliveryStates = ["PENDIENTE", "ASIGNADO", "RECOGIDO", "EN_CAMINO", "ENTREGADO"];
      const kitchenStates = ["PAGO_PENDIENTE", "PENDIENTE", "COBRADO", "EN_PREPARACION", "LISTO", "ENTREGADO"];
      const steps = result.tipo === "delivery" && result.estado_pago === "PAGADO"
        ? deliveryStates
        : kitchenStates;
      const currentState = result.tipo === "delivery" && result.estado_pago === "PAGADO" && result.estado_delivery
        ? result.estado_delivery
        : result.estado;
      const currentIndex = steps.indexOf(currentState);
      progress.innerHTML = `<strong>Seguimiento</strong><ol style="margin:.6rem 0 0;padding-left:1.25rem">${steps.map((step, index) => `
        <li style="padding:.2rem 0;color:${index <= currentIndex ? "var(--neon-green)" : "var(--text-muted)"}">${escapeClientHtml(statusLabels[step] || deliveryLabels[step] || step)}</li>
      `).join("")}</ol>`;
      cachedTrackingProgress = {
        orderId: currentPendingOrderId,
        status: state,
        paymentStatus: result.estado_pago,
        paymentMethod: result.metodo_pago,
        paymentMode: result.modo_pago,
        steps: steps.map(step => statusLabels[step] || deliveryLabels[step] || step),
        currentIndex,
        updatedAt: new Date().toISOString()
      };
      persistClientProgress();
    }
    } catch (error) {
      const info = document.getElementById("track-order-info");
      if (!navigator.onLine || error instanceof TypeError) {
        updateClientNetworkStatus(false);
        renderCachedTrackingProgress();
        if (info && !cachedTrackingProgress) {
          info.textContent = "No hay conexión. El seguimiento volverá a actualizarse cuando recuperes internet.";
        }
      } else if (info) {
        info.textContent = error.message;
      }
    }
}

async function loadToonCategories() {
  try {
    const res = await fetch("/api/v1/cliente/categorias");
    if (res.ok) {
      toonCategories = await res.json();
      renderPhotoCategories();
    }
  } catch (err) {
    console.error("Error al cargar categorías:", err);
    markClientNetworkFailure(err);
  }
}

async function loadToonProducts() {
  try {
    const res = await fetch("/api/v1/cliente/productos");
    if (res.ok) {
      toonProducts = await res.json();
      renderToonProducts();
    }
  } catch (err) {
    console.error("Error al cargar productos:", err);
    markClientNetworkFailure(err);
  }
}

async function loadGuiaItems() {
  try {
    const res = await fetch("/api/v1/cliente/guia?tipo=cliente");
    if (res.ok) {
      guiaItems = await res.json();
    }
  } catch (err) {
    console.error("Error al cargar guía:", err);
    markClientNetworkFailure(err);
  }
}

/* ==================== FLUJO DE MODALIDAD, MAPA Y PASARELA DE PAGO CLIENTE (ESTILO CASHEA) ==================== */
let selectedModality = 'mesa';
let selectedMesaPaymentMode = 'PAGAR_ANTES';
let leafletMap = null;
let leafletMarker = null;
let googleMap = null;
let googleMapMarker = null;
let googleMapsApiPromise = null;
let selectedDeliveryCoords = null;
let currentRatingStars = 5;

function openOrderModalityModal() {
  openModal("order-modality-modal");
}

function updateCheckoutProgress(screenId = document.querySelector(".screen.active")?.id) {
  const activeStep = {
    "screen-carrito": 1,
    "screen-checkout-delivery": 2,
    "screen-checkout-summary": 3,
    "screen-checkout": 4,
    "screen-tracking": 5
  }[screenId];
  if (!activeStep) return;

  document.querySelectorAll(".checkout-progress [data-checkout-progress]").forEach(step => {
    const stepNumber = Number(step.dataset.checkoutProgress);
    step.classList.toggle("is-complete", stepNumber < activeStep);
    step.classList.toggle("is-current", stepNumber === activeStep);
    if (stepNumber === activeStep) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
  });
}

function startCheckoutFlow() {
  if (!toonCart.length) {
    showToast("Agrega productos al carrito antes de continuar.", "warning");
    return;
  }
  const preferredModality = isTableQrSession && currentDetectedMesa
    ? "mesa"
    : (document.getElementById("checkout-type")?.value || "delivery");
  enterCheckout(preferredModality);
}

function validateCheckoutDelivery() {
  const type = document.getElementById("checkout-type")?.value;
  if (!["mesa", "delivery", "llevar"].includes(type)) {
    showToast("Selecciona cómo recibirás tu pedido.", "warning");
    return false;
  }
  if (type === "mesa") {
    if (!currentDetectedMesa || !isAdminConfiguredTable(currentDetectedMesa)) {
      showToast("Escanea el código QR de una mesa registrada por el restaurante.", "warning");
      openQrScannerModal();
      return false;
    }
  }
  if (type === "delivery") {
    const deliveryFields = [
      document.getElementById("deliv-nombre"),
      document.getElementById("deliv-telefono"),
      document.getElementById("deliv-direccion")
    ].filter(Boolean);
    const firstInvalidField = deliveryFields.find(field => !field.value.trim());
    if (firstInvalidField) {
      if (document.querySelector(".screen.active")?.id !== "screen-checkout-delivery") {
        showScreen("screen-checkout-delivery");
      }
      firstInvalidField.reportValidity();
      showToast("Completa los datos de contacto y entrega para continuar.", "warning");
      return false;
    }
  }
  return true;
}

function continueToOrderSummary() {
  if (!toonCart.length) {
    showToast("Tu carrito está vacío. Agrega productos antes de continuar.", "warning");
    showScreen("screen-carrito");
    return;
  }
  if (!validateCheckoutDelivery()) return;
  updateCheckoutOrderSummary();
  showScreen("screen-checkout-summary");
}

function continueToPayment() {
  if (!toonCart.length) {
    showToast("Tu carrito está vacío. Agrega productos antes de continuar.", "warning");
    showScreen("screen-carrito");
    return;
  }
  if (!validateCheckoutDelivery()) {
    showScreen("screen-checkout-delivery");
    return;
  }
  updateCheckoutOrderSummary();
  updateCheckoutPaymentFields();
  showScreen("screen-checkout");
}

function selectOrderModality(modality) {
  selectedModality = modality;
  closeModal("order-modality-modal");

  if (modality === "mesa") {
    selectedMesaPaymentMode = "PAGAR_ANTES";
    if (!currentDetectedMesa) {
      showToast("Por favor escanea el código QR de tu mesa", "info");
      openQrScannerModal();
      return;
    }
    enterCheckout(modality);
  } else if (modality === "llevar") {
    selectedMesaPaymentMode = "PAGAR_ANTES";
    enterCheckout(modality);
  } else if (modality === "delivery") {
    const u = Auth.getUser();
    if (!u) {
      showToast("Puedes continuar como invitado; inicia sesión si quieres acumular puntos.", "info");
    }
    enterCheckout(modality);
  }
}

function enterCheckout(modality) {
  selectedModality = modality;
  const typeSelect = document.getElementById("checkout-type");
  if (typeSelect) typeSelect.value = modality;
  if (modality === "mesa") {
    const modeInput = document.querySelector(`input[name="modo_pago"][value="${selectedMesaPaymentMode}"]`);
    if (modeInput) modeInput.checked = true;
  }
  if (modality === "delivery") {
    const user = Auth.getUser();
    if (user) {
      const name = document.getElementById("deliv-nombre");
      const phone = document.getElementById("deliv-telefono");
      if (name && !name.value) name.value = `${user.nombre || ""} ${user.apellido || ""}`.trim();
      if (phone && !phone.value) phone.value = user.telefono || "";
    }
  }
  showScreen("screen-checkout-delivery");
  toggleCheckoutFields();
}

function chooseMesaPaymentMode(mode) {
  selectedMesaPaymentMode = mode;
  closeModal("mesa-payment-option-modal");
  const modeInput = document.querySelector(`input[name="modo_pago"][value="${mode}"]`);
  if (modeInput) modeInput.checked = true;
  enterCheckout(selectedModality);
}

function openDeliveryMapModal() {
  openModal("delivery-map-modal");
  setTimeout(() => {
    initDeliveryLocationMap();
  }, 300);
}

function initDeliveryLocationMap() {
  const container = document.getElementById("leaflet-map-container");
  if (!container) return;
  if (googleMapsApiKey) {
    loadGoogleMapsApi()
      .then(() => initGoogleDeliveryMap(container))
      .catch(error => {
        console.error("No se pudo cargar Google Maps; se mostrará el mapa alternativo.", error);
        showToast("Google Maps no está disponible. Se usará el mapa alternativo.", "warning");
        initLeafletDeliveryMap(container);
      });
    return;
  }
  initLeafletDeliveryMap(container);
}

function loadGoogleMapsApi() {
  if (window.google?.maps) return Promise.resolve();
  if (googleMapsApiPromise) return googleMapsApiPromise;

  googleMapsApiPromise = new Promise((resolve, reject) => {
    const callbackName = `googleMapsReady${Date.now()}`;
    const script = document.createElement("script");
    window[callbackName] = () => {
      delete window[callbackName];
      resolve();
    };
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(googleMapsApiKey)}&callback=${callbackName}`;
    script.async = true;
    script.onerror = () => {
      delete window[callbackName];
      googleMapsApiPromise = null;
      reject(new Error("No se pudo cargar la API de Google Maps."));
    };
    document.head.appendChild(script);
  });
  return googleMapsApiPromise;
}

function initGoogleDeliveryMap(container) {
  const initialPosition = selectedDeliveryCoords || { lat: 10.4806, lng: -66.9036 };
  if (!googleMap) {
    googleMap = new google.maps.Map(container, { center: initialPosition, zoom: 14 });
    googleMapMarker = new google.maps.Marker({
      position: initialPosition,
      map: googleMap,
      draggable: true,
    });
    googleMap.addListener("click", event => {
      googleMapMarker.setPosition(event.latLng);
      updateCustomerDeliveryLocation(event.latLng.lat(), event.latLng.lng());
    });
    googleMapMarker.addListener("dragend", event => {
      updateCustomerDeliveryLocation(event.latLng.lat(), event.latLng.lng());
    });
  } else {
    googleMap.setCenter(initialPosition);
    googleMapMarker.setPosition(initialPosition);
  }
  if (selectedDeliveryCoords) updateCustomerDeliveryLocation(initialPosition.lat, initialPosition.lng);
}

function initLeafletDeliveryMap(container = document.getElementById("leaflet-map-container")) {
  if (!container || typeof L === "undefined") {
    showToast("No se pudo cargar el mapa. Puedes continuar ingresando la dirección manualmente.", "warning");
    return;
  }
  const initialPosition = selectedDeliveryCoords || { lat: 10.4806, lng: -66.9036 };
  if (leafletMap) {
    leafletMap.setView([initialPosition.lat, initialPosition.lng], 14);
    if (leafletMarker) leafletMarker.setLatLng([initialPosition.lat, initialPosition.lng]);
    setTimeout(() => leafletMap.invalidateSize(), 100);
    return;
  }
  container.replaceChildren();
  leafletMap = L.map(container).setView([initialPosition.lat, initialPosition.lng], 14);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap"
  }).addTo(leafletMap);

  leafletMarker = L.marker([initialPosition.lat, initialPosition.lng], { draggable: true }).addTo(leafletMap);

  leafletMarker.on("dragend", function (e) {
    const latlng = e.target.getLatLng();
    updateCustomerDeliveryLocation(latlng.lat, latlng.lng);
  });
  leafletMap.on("click", event => {
    leafletMarker.setLatLng(event.latlng);
    updateCustomerDeliveryLocation(event.latlng.lat, event.latlng.lng);
  });
  if (selectedDeliveryCoords) updateCustomerDeliveryLocation(initialPosition.lat, initialPosition.lng);
}

function updateCustomerDeliveryLocation(lat, lng) {
  const numLat = Number(lat);
  const numLng = Number(lng);
  selectedDeliveryCoords = { lat: numLat, lng: numLng };
  currentCustomerGPS = { ...selectedDeliveryCoords };
  const mapAddress = document.getElementById("map-address-input");
  if (mapAddress && !mapAddress.value.trim()) mapAddress.value = "Punto seleccionado en el mapa";
  const mapsUrl = `https://www.google.com/maps?q=${selectedDeliveryCoords.lat.toFixed(6)},${selectedDeliveryCoords.lng.toFixed(6)}`;
  const badge = document.getElementById("gps-status-badge");
  if (badge) {
    badge.style.display = "block";
    badge.innerHTML = `📍 Ubicación seleccionada · ${selectedDeliveryCoords.lat.toFixed(6)}, ${selectedDeliveryCoords.lng.toFixed(6)} · <a href="${mapsUrl}" target="_blank" rel="noopener noreferrer" style="color:var(--gold-accent);font-weight:800">Ver en Google Maps</a>`;
  }
  persistClientProgress();
}

function confirmDeliveryMapLocation() {
  const address = document.getElementById("map-address-input")?.value.trim() || "";
  if (!address && !selectedDeliveryCoords) {
    showToast("Selecciona un punto en el mapa o escribe una dirección.", "warning");
    return;
  }
  const coordinates = selectedDeliveryCoords
    ? `GPS: ${selectedDeliveryCoords.lat.toFixed(6)}, ${selectedDeliveryCoords.lng.toFixed(6)}`
    : "";
  const addr = [address, coordinates].filter(Boolean).join(" · ");
  const addressInput = document.getElementById("deliv-direccion");
  if (addressInput) addressInput.value = addr;
  closeModal("delivery-map-modal");
  enterCheckout("delivery");
}

let currentCustomerGPS = null;
let deliveryMap = null;
let deliveryMarker = null;

function initDeliveryInteractiveMap(initialLat = 10.4806, initialLng = -66.9036) {
  const container = document.getElementById("delivery-google-map");
  if (!container || typeof L === "undefined") return;

  if (deliveryMap) {
    deliveryMap.setView([initialLat, initialLng], 15);
    if (deliveryMarker) deliveryMarker.setLatLng([initialLat, initialLng]);
    setTimeout(() => deliveryMap.invalidateSize(), 300);
    return;
  }

  deliveryMap = L.map('delivery-google-map').setView([initialLat, initialLng], 15);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© Google Maps / OpenStreetMap'
  }).addTo(deliveryMap);

  const customIcon = L.divIcon({
    className: 'custom-gps-pin',
    html: '<div style="font-size: 2.4rem; filter: drop-shadow(0 4px 10px rgba(0,0,0,0.7)); transform: translate(-50%, -100%);">📍</div>',
    iconSize: [36, 36],
    iconAnchor: [18, 36]
  });

  deliveryMarker = L.marker([initialLat, initialLng], { draggable: true, icon: customIcon }).addTo(deliveryMap);

  function updateAddressFromMarker(lat, lng) {
    const numLat = parseFloat(lat);
    const numLng = parseFloat(lng);
    currentCustomerGPS = { lat: numLat, lng: numLng };
    selectedDeliveryCoords = { lat: numLat, lng: numLng };
    const mapsUrl = `https://www.google.com/maps?q=${numLat.toFixed(6)},${numLng.toFixed(6)}`;
    
    const input = document.getElementById("deliv-direccion");
    if (input && (!input.value.trim() || input.value.startsWith("Ubicación GPS") || input.value.startsWith("📍"))) {
      input.value = `Ubicación GPS seleccionada (${numLat.toFixed(5)}, ${numLng.toFixed(5)})`;
    }

    const badge = document.getElementById("gps-status-badge");
    if (badge) {
      badge.style.display = "block";
      badge.innerHTML = `🌐 <strong>GPS Google Maps:</strong> ${numLat.toFixed(6)}, ${numLng.toFixed(6)} • <a href="${mapsUrl}" target="_blank" rel="noopener noreferrer" style="color: var(--gold-accent); text-decoration: underline; font-weight: 800;">📍 Abrir en Google Maps</a>`;
    }
    persistClientProgress();
  }

  deliveryMarker.on('dragend', function (e) {
    const latLng = e.target.getLatLng();
    updateAddressFromMarker(latLng.lat, latLng.lng);
  });

  deliveryMap.on('click', function (e) {
    deliveryMarker.setLatLng(e.latlng);
    updateAddressFromMarker(e.latlng.lat, e.latlng.lng);
  });

  updateAddressFromMarker(initialLat, initialLng);
  setTimeout(() => deliveryMap.invalidateSize(), 300);
}

function getDeviceGPSLocation() {
  if (!navigator.geolocation) {
    showToast("Tu navegador o celular no soporta geolocalización GPS", "warning");
    return;
  }

  showToast("📡 Obteniendo tu ubicación actual...", "info");

  navigator.geolocation.getCurrentPosition(
    (position) => {
      const lat = parseFloat(position.coords.latitude);
      const lng = parseFloat(position.coords.longitude);
      currentCustomerGPS = { lat, lng };
      selectedDeliveryCoords = { lat, lng };
      updateCustomerDeliveryLocation(lat, lng);

      const dirInput = document.getElementById("deliv-direccion");
      if (dirInput && (!dirInput.value.trim() || dirInput.value.startsWith("Ubicación GPS") || dirInput.value.startsWith("📍"))) {
        dirInput.value = `Ubicación GPS actual (${lat.toFixed(5)}, ${lng.toFixed(5)})`;
      }

      const mapsUrl = `https://www.google.com/maps?q=${lat.toFixed(6)},${lng.toFixed(6)}`;
      const badge = document.getElementById("gps-status-badge");
      if (badge) {
        badge.style.display = "block";
        badge.innerHTML = `✅ <strong>Ubicación GPS obtenida:</strong> ${lat.toFixed(6)}, ${lng.toFixed(6)} • <a href="${mapsUrl}" target="_blank" rel="noopener noreferrer" style="color: var(--gold-accent); text-decoration: underline; font-weight: 800;">📍 Abrir en Google Maps</a>`;
      }

      if (leafletMap && leafletMarker) {
        leafletMap.setView([Number(lat), Number(lng)], 16);
        leafletMarker.setLatLng([Number(lat), Number(lng)]);
      }
      if (googleMap && googleMapMarker) {
        const point = { lat: Number(lat), lng: Number(lng) };
        googleMap.setCenter(point);
        googleMap.setZoom(16);
        googleMapMarker.setPosition(point);
      }

      showToast("📍 ¡Ubicación obtenida exitosamente!", "success");
    },
    (error) => {
      let errMsg = "No se pudo obtener la ubicación GPS.";
      if (error.code === error.PERMISSION_DENIED) {
        errMsg = "Permiso de ubicación denegado en tu celular.";
      }
      showToast(errMsg, "danger");
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
  );
}

function openServiceRatingModal() {
  setRatingStars(5);
  openModal("service-rating-modal");
}

function setRatingStars(count) {
  currentRatingStars = count;
  const stars = document.querySelectorAll("#star-rating-picker span");
  stars.forEach((s, idx) => {
    s.style.opacity = idx < count ? "1" : "0.3";
  });
}

async function submitServiceRating() {
  const comment = document.getElementById("rating-comment-input")?.value.trim() || "Excelente atención y comida deliciosa";
  const u = Auth.getUser();
  const name = u ? `${u.nombre} ${u.apellido}` : "Cliente Satisfecho";

  try {
    let saved = false;
    if (currentPendingOrderId) {
      const hdrs = { ...Auth.getHeaders(), "Content-Type": "application/json" };
      if (currentTrackingToken) hdrs["X-Order-Tracking-Token"] = currentTrackingToken;
      const orderRes = await fetch(`/api/v1/cliente/pedidos/${currentPendingOrderId}/resena`, {
        method: "POST",
        headers: hdrs,
        body: JSON.stringify({
          nombre_cliente: name,
          comentario: comment,
          estrellas: currentRatingStars
        })
      });
      if (orderRes.ok) saved = true;
    }
    if (!saved) {
      await fetch("/api/v1/cliente/resenas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nombre_cliente: name,
          comentario: comment,
          estrellas: currentRatingStars
        })
      });
    }
    showToast("🌟 ¡Gracias por calificar nuestro servicio!", "success");
    closeModal("service-rating-modal");
    showScreen("screen-tracking");
  } catch (e) {
    closeModal("service-rating-modal");
    showScreen("screen-tracking");
  }
}

async function submitClientUserRegistration() {
  const nombre = document.getElementById("reg-nombre")?.value;
  const apellido = document.getElementById("reg-apellido")?.value;
  const email = document.getElementById("reg-email")?.value;
  const tel = document.getElementById("reg-tel")?.value;
  const username = document.getElementById("reg-username")?.value;
  const pass = document.getElementById("reg-pass")?.value;

  if (!nombre || !email || !username || !pass) {
    showToast("Por favor completa los campos obligatorios de registro.", "warning");
    return;
  }

  try {
    const res = await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nombre: nombre,
        apellido: apellido || "",
        email: email,
        telefono: tel || "",
        nombre_usuario: username,
        password: pass
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Error al registrar cliente");
    }

    const data = await res.json();
    if (data.access_token) {
      Auth.setAuth(data.access_token, data.usuario);
    }

    showToast("🎉 ¡Registro completado con éxito! Ganaste 50 Puntos de Bienvenida 🏆", "success");
    closeModal("client-register-modal");
    updateProfileUI();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function updateProfileUI() {
  const u = Auth.getUser();
  const actionsContainer = document.getElementById("profile-actions-container");
  const homeLoginAction = document.getElementById("home-login-action");
  const homeRegisterAction = document.getElementById("home-register-action");

  if (u) {
    if (homeLoginAction) homeLoginAction.style.display = "none";
    if (homeRegisterAction) homeRegisterAction.style.display = "none";
    const clientCode = `CLI-${String(u.id).padStart(4, '0')}`;
    if (document.getElementById("profile-name")) document.getElementById("profile-name").innerText = `${u.nombre} ${u.apellido || ''}`;
    if (document.getElementById("profile-email")) document.getElementById("profile-email").innerHTML = `<span style="color: var(--cyan-accent); font-weight: 900; background: rgba(0,245,212,0.1); padding: 0.2rem 0.65rem; border-radius: 14px; border: 1px solid var(--cyan-accent); font-size: 0.82rem; display: inline-block; margin-bottom: 0.3rem;">🆔 CÓDIGO CLIENTE: ${clientCode}</span><br><span style="font-size: 0.8rem;">${u.email}</span>`;
    if (document.getElementById("profile-points-display")) document.getElementById("profile-points-display").innerText = `${u.puntos_fidelidad || 0} Puntos 🏆`;
    if (document.getElementById("profile-avatar")) {
      const initials = (u.nombre[0] + (u.apellido ? u.apellido[0] : '')).toUpperCase();
      document.getElementById("profile-avatar").innerText = initials;
    }
    if (document.getElementById("home-welcome-subtitle")) {
      document.getElementById("home-welcome-subtitle").innerText = `👋 Hola, ${u.nombre} (${clientCode}). Tienes ${u.puntos_fidelidad || 0} puntos.`;
    }

    if (actionsContainer) {
      actionsContainer.innerHTML = `
        <button class="btn-gold" style="width: 100%; font-size: 1rem;" onclick="showScreen('screen-historial')">
          📋 VER MI HISTORIAL COMPLETO DE PEDIDOS
        </button>
        <button class="btn-gold" style="width: 100%; background: rgba(255, 71, 87, 0.2); color: var(--neon-red); border: 1px solid var(--neon-red);" onclick="Auth.logout()">
          🚪 Cerrar Sesión
        </button>
      `;
    }

    initSmartRecommendationsAlgorithm();
    loadLoyaltyPanel();
  } else {
    if (homeLoginAction) homeLoginAction.style.display = "";
    if (homeRegisterAction) homeRegisterAction.style.display = "";
    const welcome = document.getElementById("home-welcome-subtitle");
    if (welcome) welcome.textContent = "🎁 Pide como invitado o inicia sesión para ganar puntos";
    if (actionsContainer) {
      actionsContainer.innerHTML = `
        <button class="btn-gold" style="width: 100%; font-size: 1rem;" onclick="openModal('client-login-modal')">
          🔑 INICIAR SESIÓN EN MI CUENTA
        </button>
        <button class="btn-gold" style="width: 100%; background: linear-gradient(135deg, #00f5d4, #00b4d8); color: #000;" onclick="openModal('client-register-modal')">
          📝 REGISTRARME COMO NUEVO CLIENTE (+50 PTS)
        </button>
      `;
    }
  }
}

const loyaltyRewards = [
  { name: "Bebida Gratis", cost: 50 },
  { name: "Papas Gratis", cost: 100 },
  { name: "Descuento 10%", cost: 150 }
];

async function loadLoyaltyPanel() {
  const historyContainer = document.getElementById("loyalty-history");
  const rewardsContainer = document.getElementById("loyalty-rewards");
  const progress = document.getElementById("loyalty-progress");
  if (!historyContainer || !rewardsContainer || !progress) return;

  if (!Auth.getUser()) {
    progress.textContent = "Inicia sesión para consultar tus puntos y canjear recompensas.";
    rewardsContainer.innerHTML = "";
    historyContainer.innerHTML = "";
    return;
  }

  historyContainer.innerHTML = '<small style="color:var(--text-muted)">Cargando movimientos…</small>';
  try {
    const response = await fetch("/api/v1/cliente/puntos/historial", { headers: Auth.getHeaders() });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "No se pudo cargar el historial de puntos.");
    }
    const data = await response.json();
    const points = Number(data.puntos_actuales) || 0;
    const nextReward = loyaltyRewards.find(reward => points < reward.cost);
    if (nextReward) {
      const floor = loyaltyRewards
        .filter(reward => reward.cost <= points)
        .reduce((highest, reward) => Math.max(highest, reward.cost), 0);
      const progressPercent = Math.min(100, Math.round(
        ((points - floor) / (nextReward.cost - floor)) * 100
      ));
      progress.innerHTML = `<strong>${points} puntos</strong> · te faltan ${nextReward.cost - points} para ${escapeClientHtml(nextReward.name)}<div role="progressbar" aria-valuenow="${progressPercent}" aria-valuemin="0" aria-valuemax="100" style="height:8px;margin-top:.5rem;border-radius:8px;background:var(--toon-border);overflow:hidden"><span style="display:block;width:${progressPercent}%;height:100%;background:var(--gold-accent)"></span></div>`;
    } else {
      progress.innerHTML = `<strong>${points} puntos</strong> · ya puedes canjear todas las recompensas disponibles.`;
    }
    const pointsDisplay = document.getElementById("profile-points-display");
    if (pointsDisplay) pointsDisplay.textContent = `${points} Puntos 🏆`;
    rewardsContainer.innerHTML = loyaltyRewards.map(reward => `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.55rem;border:1px solid var(--toon-border);border-radius:10px">
        <span>${escapeClientHtml(reward.name)} · ${reward.cost} pts</span>
        <button class="btn-gold" type="button" ${points < reward.cost ? "disabled" : ""} onclick="redeemLoyaltyReward('${escapeClientHtml(reward.name)}')">Canjear</button>
      </div>
    `).join("");
    const history = Array.isArray(data.historial) ? data.historial : [];
    historyContainer.innerHTML = history.length
      ? `<h4 style="margin:.25rem 0">Movimientos recientes</h4>${history.slice(0, 10).map(item => {
        const date = new Date(item.fecha);
        const dateText = Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
        const pointsText = `${Number(item.puntos) > 0 ? "+" : ""}${Number(item.puntos) || 0}`;
        return `<div style="display:flex;justify-content:space-between;gap:.5rem;font-size:.83rem;border-bottom:1px solid var(--toon-border);padding:.35rem 0"><span>${escapeClientHtml(item.concepto)}<small style="display:block;color:var(--text-muted)">${escapeClientHtml(dateText)}</small></span><strong>${escapeClientHtml(pointsText)}</strong></div>`;
      }).join("")}`
      : '<small style="color:var(--text-muted)">Aún no tienes movimientos de puntos.</small>';
  } catch (error) {
    historyContainer.innerHTML = `<small role="alert" style="color:var(--neon-red)">${escapeClientHtml(error.message)}</small>`;
    console.error("No se pudo cargar el historial de fidelidad.", error);
  }
}

async function redeemLoyaltyReward(rewardName) {
  try {
    const response = await fetch(`/api/v1/cliente/puntos/canjear?recompensa=${encodeURIComponent(rewardName)}`, {
      method: "POST",
      headers: Auth.getHeaders()
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "No se pudo canjear la recompensa.");
    showToast(`${result.mensaje}. Puntos restantes: ${result.puntos_restantes}.`, "success");
    await loadLoyaltyPanel();
  } catch (error) {
    showToast(error.message || "No se pudo canjear la recompensa.", "danger");
  }
}

async function submitClientLogin() {
  const username = document.getElementById("login-username-input")?.value?.trim();
  const pass = document.getElementById("login-pass-input")?.value;
  const rememberCb = document.getElementById("client-remember-credentials");

  if (!username || !pass) {
    showToast("Ingresa tu usuario y contraseña", "warning");
    return;
  }

  // Guardar o limpiar solo el nombre de usuario (nunca la contraseña) según checkbox
  try {
    localStorage.removeItem("donde_david_client_saved_pass");
    if (rememberCb && rememberCb.checked) {
      localStorage.setItem("donde_david_client_saved_user", username);
      localStorage.setItem("donde_david_client_remember", "true");
    } else {
      localStorage.removeItem("donde_david_client_saved_user");
      localStorage.removeItem("donde_david_client_remember");
    }
  } catch (err) {
    console.warn("No se pudo guardar la preferencia de recordar usuario", err);
  }

  try {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre_usuario: username, password: pass })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Credenciales incorrectas");
    }

    const data = await res.json();
    Auth.setAuth(data.access_token, data.usuario);

    showToast(`🔑 ¡Bienvenido de nuevo, ${data.usuario.nombre}!`, "success");
    closeModal("client-login-modal");
    updateProfileUI();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function initSmartRecommendationsAlgorithm() {
  const u = Auth.getUser();
  if (!u) return;

  try {
    const res = await fetch("/api/v1/cliente/personalizacion", {
      headers: Auth.getHeaders()
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "No se pudo cargar tu personalización.");
    }
    const data = await res.json();
    personalizedProducts = data.recomendaciones || [];
    lastUserOrderItems = data.ultima_orden?.items || [];
    lastUserOrderId = data.ultima_orden?.id || null;
    const welcome = document.getElementById("home-welcome-subtitle");
    if (welcome && data.ultima_orden) {
      welcome.textContent = `${data.saludo} Tu pedido #${data.ultima_orden.id} está listo para repetir. Tienes ${data.puntos_fidelidad} puntos.`;
    }

    const summaryText = lastUserOrderItems
      .map(item => `${item.cantidad}x ${item.nombre}`)
      .join(" + ");
    const homeReorderBox = document.getElementById("reorder-algorithm-container");
    const profileReorderBox = document.getElementById("profile-reorder-container");
    [homeReorderBox, profileReorderBox].forEach(box => {
      if (box) box.style.display = lastUserOrderItems.length ? "block" : "none";
    });
    const summary = document.getElementById("reorder-items-summary");
    const profileSummary = document.getElementById("profile-reorder-summary");
    if (summary) summary.textContent = summaryText;
    if (profileSummary) profileSummary.textContent = summaryText;
    const orderNumber = document.getElementById("reorder-price-val");
    const profileOrderNumber = document.getElementById("profile-reorder-price-val");
    if (orderNumber) orderNumber.textContent = String(lastUserOrderId || "");
    if (profileOrderNumber) profileOrderNumber.textContent = String(lastUserOrderId || "");

    renderSmartRecommendations(personalizedProducts);
  } catch (error) {
    console.error("Error al cargar personalización:", error);
  }
}

function renderSmartRecommendations(products = personalizedProducts) {
  const recomGrid = document.getElementById("smart-recommendations-grid");
  const recomBox = document.getElementById("smart-recommendations-container");
  const profileRecomGrid = document.getElementById("profile-smart-recommendations-grid");
  const profileRecomBox = document.getElementById("profile-smart-recommendations-container");

  const suggested = (products || []).filter(product => Number(product.stock) > 0).slice(0, 3);
  if (suggested.length === 0) {
    if (recomBox) recomBox.style.display = "none";
    if (profileRecomBox) profileRecomBox.style.display = "none";
    return;
  }

  let html = "";
  suggested.forEach(p => {
    const imageUrl = /^(https?:\/\/|\/static\/)/i.test(String(p.imagen_url || ""))
      ? escapeClientHtml(p.imagen_url)
      : "/static/img/logo.png";
    const price = Number(p.precio);
    html += `
      <div style="min-width: 200px; max-width: 220px; background: var(--toon-card); border: 1px solid var(--toon-border); border-radius: 14px; padding: 0.85rem; flex-shrink: 0; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
        <img src="${imageUrl}" style="width: 100%; height: 95px; object-fit: cover; border-radius: 10px; margin-bottom: 0.5rem;" alt="${escapeClientHtml(p.nombre)}">
        <div style="font-weight: 800; font-size: 0.85rem; color: #fff; line-height: 1.2; height: 2.2rem; overflow: hidden;">${escapeClientHtml(p.nombre)}</div>
        <small style="color:var(--text-muted)">${escapeClientHtml(p.motivo || "")}</small>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
          <span style="font-weight: 900; color: var(--gold-accent); font-size: 0.95rem;">$${Number.isFinite(price) ? price.toFixed(2) : "0.00"}</span>
          <button class="btn-gold" style="padding: 0.25rem 0.65rem; font-size: 0.75rem;" onclick="addQuickProductToCart(${p.id})">⚡ Agregar</button>
        </div>
      </div>
    `;
  });

  if (recomGrid && recomBox) {
    recomGrid.innerHTML = html;
    recomBox.style.display = "block";
  }
  if (profileRecomGrid && profileRecomBox) {
    profileRecomGrid.innerHTML = html;
    profileRecomBox.style.display = "block";
  }
}

function addQuickProductToCart(prodId) {
  const p = toonProducts.find(item => Number(item.id) === Number(prodId))
    || personalizedProducts.find(item => Number(item.id) === Number(prodId));
  if (!p) return;
  if (Number(p.stock) < 1) {
    showToast("Este producto no tiene existencias disponibles.", "warning");
    return;
  }
  const price = Number(p.precio_promocion || p.precio || 0);

  toonCart.push({
    producto_id: p.id,
    nombre: p.nombre,
    precio_unitario: price,
    cantidad: 1,
    subtotal: price,
    puntos_fidelidad: Math.max(0, Number(p.puntos_fidelidad) || 0),
    opciones: [],
    extras: [],
    tiempo_preparacion: Number(p.tiempo_preparacion) || 15
  });
  updateCartNavBadge();
  showToast(`⚡ ${p.nombre} agregado al carrito`, "success");
}

async function repeatLastOrderOneClick() {
  if (!lastUserOrderItems || lastUserOrderItems.length === 0) {
    showToast("Todavía no tienes pedidos anteriores para repetir.", "info");
    return;
  }

  if (toonProducts.length === 0) await loadToonProducts();
  const items = [];
  for (const previousItem of lastUserOrderItems) {
    const product = toonProducts.find(item => item.id === previousItem.producto_id);
    if (!product || !product.activo || !product.disponible || product.stock < previousItem.cantidad) {
      showToast(`${previousItem.nombre} ya no está disponible en la cantidad solicitada. No se agregó ningún artículo.`, "warning");
      return;
    }
    let options = [];
    let extras = [];
    if (previousItem.personalizaciones) {
      try {
        const parsed = JSON.parse(previousItem.personalizaciones);
        options = Array.isArray(parsed.opciones) ? parsed.opciones : [];
        extras = Array.isArray(parsed.extras) ? parsed.extras : [];
      } catch (error) {
        console.warn("No se pudieron recuperar las opciones del pedido anterior.", error);
      }
    }
    const currentExtras = getProductExtras(product);
    if (extras.some(name => !currentExtras.some(extra => extra.nombre === name))) {
      showToast(`${previousItem.nombre} ya no tiene todos los extras del pedido anterior. No se agregó ningún artículo.`, "warning");
      return;
    }
    const extraPrice = extras.reduce((total, name) => total + Number(currentExtras.find(extra => extra.nombre === name).precio), 0);
    const price = Number(product.precio_promocion || product.precio || 0) + extraPrice;
    items.push({
      producto_id: product.id,
      nombre: product.nombre,
      imagen_url: product.imagen_url || "",
      precio_unitario: price,
      cantidad: previousItem.cantidad,
      subtotal: price * previousItem.cantidad,
      puntos_fidelidad: Math.max(0, Number(product.puntos_fidelidad) || 0),
      opciones: options,
      extras,
      tiempo_preparacion: Number(product.tiempo_preparacion) || 15
    });
  }
  toonCart.push(...items);
  updateCartNavBadge();
  showToast(`Pedido #${lastUserOrderId} cargado. Revisa precios y modalidad antes de confirmar.`, "success");
  openOrderModalityModal();
}

async function sendTableServiceRequest(type) {
  if (!isTableQrSession || !currentDetectedMesa) {
    showToast("Abre el menú con el QR de tu mesa para solicitar atención.", "warning");
    return;
  }
  try {
    const response = await fetch("/api/v1/cliente/solicitudes-mesa", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...Auth.getHeaders() },
      body: JSON.stringify({
        numero_mesa: Number(currentDetectedMesa),
        pedido_id: currentPendingOrderId || null,
        tipo
      })
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "No se pudo enviar la solicitud.");
    showToast(body.mensaje || "Solicitud enviada al equipo de sala.", "success");
  } catch (error) {
    showToast(error.message || "No se pudo enviar la solicitud.", "danger");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadClientFavorites();
  const homeCarousel = document.getElementById("home-promo-banner-container");
  if (homeCarousel) {
    let homeTouchStartX = 0;
    homeCarousel.addEventListener("touchstart", e => {
      homeTouchStartX = e.changedTouches?.[0]?.clientX || 0;
    }, { passive: true });
    homeCarousel.addEventListener("touchend", e => {
      const activeList = (toonPromos || []).filter(p => p && p.activo !== false);
      if (activeList.length < 2) return;
      const delta = (e.changedTouches?.[0]?.clientX || 0) - homeTouchStartX;
      if (Math.abs(delta) < 40) return;
      if (delta < 0) nextCarouselSlide(activeList.length);
      else prevCarouselSlide(activeList.length);
    }, { passive: true });
  }
  const lightboxStage = document.getElementById("dish-lightbox-stage");
  if (lightboxStage) {
    let lbStartX = 0;
    lightboxStage.addEventListener("touchstart", e => {
      lbStartX = e.changedTouches?.[0]?.clientX || 0;
    }, { passive: true });
    lightboxStage.addEventListener("touchend", e => {
      const delta = (e.changedTouches?.[0]?.clientX || 0) - lbStartX;
      if (Math.abs(delta) < 35) return;
      stepDishLightbox(delta < 0 ? 1 : -1);
    }, { passive: true });
  }
  document.addEventListener("keydown", e => {
    const lb = document.getElementById("product-gallery-lightbox");
    if (!lb || !lb.classList.contains("open")) return;
    if (e.key === "Escape") closeDishLightbox();
    else if (e.key === "ArrowRight") stepDishLightbox(1);
    else if (e.key === "ArrowLeft") stepDishLightbox(-1);
  });
});
