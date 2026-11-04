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
    imagen_url: typeof item.imagen_url === "string" && /^(https:\/\/|\/static\/)/i.test(item.imagen_url)
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
  return /^(https:\/\/|\/static\/)/i.test(url) && !url.startsWith("//")
    ? url
    : "/static/img/logo.png";
}

function getDeclaredAllergens(product) {
  if (!product?.alergenos) return [];
  return String(product.alergenos).split(",").map(item => item.trim()).filter(Boolean);
}
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("open");
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
  if (mesaParam && /^[1-9]\d*$/.test(mesaParam)) {
    currentDetectedMesa = mesaParam;
    isTableQrSession = true;
    const checkoutType = document.getElementById("checkout-type");
    if (checkoutType) checkoutType.value = "mesa";
    const tableActions = document.getElementById("table-service-actions");
    if (tableActions) tableActions.style.display = "flex";
    if (document.getElementById("current-table-indicator")) {
      document.getElementById("current-table-indicator").innerText = `📱 QR MESA #${currentDetectedMesa}`;
    }
    if (document.getElementById("checkout-mesa-name")) {
      document.getElementById("checkout-mesa-name").innerText = `Mesa #${currentDetectedMesa}`;
    }
  } else {
    currentDetectedMesa = "1";
  }
  renderToonCart();
  updateCartNavBadge();
  if (document.getElementById("checkout-type")) toggleCheckoutFields();
  renderCachedTrackingProgress();
  if (requestedScreen) showScreen(requestedScreen);
  updateClientNetworkStatus();

  document.querySelectorAll("#screen-checkout input, #screen-checkout textarea, #screen-checkout select")
    .forEach(field => {
      field.addEventListener("input", persistClientProgress);
      field.addEventListener("change", persistClientProgress);
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
    loadConfigPublica(),
    loadToonCategories(),
    loadToonProducts(),
    loadGuiaItems(),
    loadPromocionesToon()
  ]).then(() => {
    console.log("⚡ Carga paralela optimizada completada.");
  }).catch(err => {
    console.error("Error en peticiones iniciales:", err);
    markClientNetworkFailure(err);
  });

  new WSClient((event, data) => {
    if (["CAMBIO_ESTADO_PEDIDO", "PAGO_CONFIRMADO", "DELIVERY_ACTUALIZADO"].includes(event)) {
      if (Number(data.pedido_id) === Number(currentPendingOrderId)) refreshTrackedOrder();
    } else if (event === "PRODUCTOS_ACTUALIZADOS" || event === "NUEVO_PRODUCTO") {
      loadToonProducts();
      loadToonCategories();
      showToast("🍔 ¡Menú actualizado en tiempo real!", "info");
    }
  });
  updateProfileUI();
});

function showScreen(screenId) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  const target = document.getElementById(screenId);
  if (target) target.classList.add("active");

  // Resalte activo en la barra inferior (.bottom-bar li a)
  document.querySelectorAll(".bottom-bar li a, .nav-item").forEach(n => n.classList.remove("active"));
  const idMap = {
    'screen-home': 'nav-link-home',
    'screen-categorias': 'nav-link-menu',
    'screen-menu': 'nav-link-menu',
    'screen-carrito': 'nav-link-cart',
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
    checkoutTaxRate = Number.parseFloat(cfg.impuesto_porcentaje) || 16;
    checkoutDeliveryFee = Number.parseFloat(cfg.costo_delivery) || 0;
    checkoutPackageFee = Number.parseFloat(cfg.costo_empaque) || 0;
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
  } catch (err) {
    console.error("Error al cargar las promociones del cliente:", err);
    markClientNetworkFailure(err);
    const container = document.getElementById("home-promo-banner-container");
    if (container) {
      container.innerHTML = `<div role="status" style="padding:1.25rem;border:1px dashed var(--toon-border);border-radius:16px;text-align:center;color:var(--text-muted)">No se pudieron cargar las promociones.</div>`;
    }
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
            🔥 PROMO DE LA CASA ${Number(p.descuento_pct) ? `(-${Number(p.descuento_pct)}% OFF)` : ''}
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
  if (toonProducts && toonProducts.length > 0) {
    openProductModal(toonProducts[0].id);
  } else {
    showScreen("screen-menu");
  }
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

  const html = renderProductCards(list);
  const featured = document.getElementById("home-featured-grid");
  const menu = document.getElementById("menu-products-grid");
  if (featured) featured.innerHTML = html;
  if (menu) menu.innerHTML = html;
}

function filterMenuProducts() {
  const query = (document.getElementById("menu-search-input")?.value || "").trim().toLocaleLowerCase();
  const filtered = toonProducts.filter(product => {
    const category = toonCategories.find(item => item.id === product.categoria_id)?.nombre || "";
    return `${product.nombre} ${product.descripcion || ""} ${category}`
      .toLocaleLowerCase().includes(query);
  });
  const container = document.getElementById("menu-products-grid");
  if (container) container.innerHTML = renderProductCards(filtered);
}

function renderProductCards(products) {
  return products.map(product => {
    const rawImage = String(product.imagen_url || "");
    const image = /^(https:\/\/|\/static\/)/i.test(rawImage)
      ? escapeClientHtml(rawImage)
      : "/static/img/logo.png";
    const allergens = getDeclaredAllergens(product);
    const regularPrice = Number(product.precio) || 0;
    const promoPrice = Number(product.precio_promocion) > 0 ? Number(product.precio_promocion) : null;
    const displayedPrice = promoPrice || regularPrice;
    return `
      <div class="product-toon-card" onclick="openProductModal(${Number(product.id)})">
        <div class="product-img-container">
          <img src="${image}" alt="${escapeClientHtml(product.nombre)}" loading="lazy">
          <span class="product-badge">🔥 TOON</span>
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
  const addButton = document.getElementById("modal-add-to-cart-btn");
  if (addButton) addButton.textContent = "🛒 AGREGAR AL CARRITO";
  document.getElementById("modal-qty-val").innerText = "1";
  const productImage = String(currentSelectedModalProduct.imagen_url || "");
  document.getElementById("modal-product-img").src = /^(https:\/\/|\/static\/)/i.test(productImage)
    ? productImage
    : "/static/img/logo.png";
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
    mediaContainer.innerHTML = media.map(item => {
      if (!item || typeof item.url !== "string") return "";
      const url = escapeClientHtml(item.url);
      return item.tipo === "video"
        ? `<video src="${url}" controls playsinline preload="metadata" style="width:100%;max-height:260px;border-radius:12px;margin:.4rem 0"></video>`
        : item.tipo === "imagen"
          ? `<img src="${url}" alt="${escapeClientHtml(currentSelectedModalProduct.nombre)}" loading="lazy" style="width:100%;max-height:260px;object-fit:cover;border-radius:12px;margin:.4rem 0">`
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
          <span>✔️ Con ${ing}</span>
          <input type="checkbox" class="dyn-ing-check" data-name="${ing}" checked>
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
  if (editingItem && editingItem.producto_id === currentSelectedModalProduct.id) {
    currentModalQty = editingItem.cantidad;
    document.getElementById("modal-qty-val").innerText = String(currentModalQty);
    const removedIngredients = editingItem.opciones
      .filter(option => option.startsWith("Sin "))
      .map(option => option.slice(4));
    document.querySelectorAll(".dyn-ing-check").forEach(checkbox => {
      checkbox.checked = !removedIngredients.includes(checkbox.dataset.name);
    });
    document.querySelectorAll(".dyn-extra-check").forEach(checkbox => {
      checkbox.checked = editingItem.extras.includes(checkbox.dataset.name);
    });
    const note = editingItem.opciones.find(option => option.startsWith("Nota: "));
    const notesInput = document.getElementById("modal-product-notes");
    if (notesInput) notesInput.value = note ? note.slice(6) : "";
    if (addButton) addButton.textContent = "💾 GUARDAR CAMBIOS";
  }

  if (mediaContainer) mediaContainer.hidden = !mediaContainer.innerHTML.trim();
  document.getElementById("product-detail-modal").classList.add("open");
}

function closeProductModal() {
  document.getElementById("product-detail-modal").classList.remove("open");
  editingCartIndex = null;
  const addButton = document.getElementById("modal-add-to-cart-btn");
  if (addButton) addButton.textContent = "🛒 AGREGAR AL CARRITO";
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

  // Registrar ingredientes removidos (desmarcados)
  document.querySelectorAll(".dyn-ing-check:not(:checked)").forEach(cb => {
    const ingName = cb.getAttribute("data-name");
    opts.push(`Sin ${ingName}`);
  });

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

  const basePrice = Number(currentSelectedModalProduct.precio_promocion) > 0
    ? Number(currentSelectedModalProduct.precio_promocion)
    : Number(currentSelectedModalProduct.precio) || 0;
  const unitPrice = basePrice + extraPrice;

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
  if (Number.isInteger(editingCartIndex) && toonCart[editingCartIndex]) {
    toonCart[editingCartIndex] = cartItem;
    editingCartIndex = null;
  } else {
    toonCart.push(cartItem);
  }

  updateCartNavBadge();
  closeProductModal();
  showToast(wasEditing
    ? `Pedido actualizado: ${cartItem.nombre}.`
    : `¡Agregado al carrito: ${cartItem.nombre}!`, "success");
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
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 3rem 1rem;">🛒 Tu carrito de compras está vacío.<br><button class="btn-gold" style="margin-top: 1rem;" onclick="showScreen('screen-home')">IR AL MENÚ</button></div>`;
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
    const image = /^(https:\/\/|\/static\/)/i.test(item.imagen_url || "")
      ? escapeClientHtml(item.imagen_url)
      : "/static/img/logo.png";
    const customizations = [...item.opciones, ...(item.extras || []).map(extra => `Extra: ${extra}`)];
    html += `
      <article class="client-cart-item">
        <img class="client-cart-item-image" src="${image}" alt="" loading="lazy">
        <div class="client-cart-item-content">
          <div class="client-cart-item-heading">
            <strong>${escapeClientHtml(item.nombre)}</strong>
            <span class="client-cart-item-price">${formatPriceDual(item.subtotal)}</span>
          </div>
          ${customizations.length ? `<ul class="client-cart-item-options">${customizations.map(option => `<li>${escapeClientHtml(option)}</li>`).join("")}</ul>` : '<small class="client-cart-item-options">Preparación estándar</small>'}
          <div class="client-cart-item-actions">
            <div class="client-cart-quantity" aria-label="Cantidad">
              <button type="button" aria-label="Disminuir cantidad" onclick="adjustToonCartQuantity(${idx}, -1)">−</button>
              <strong>${item.cantidad}</strong>
              <button type="button" aria-label="Aumentar cantidad" onclick="adjustToonCartQuantity(${idx}, 1)">+</button>
            </div>
            <button type="button" class="client-cart-action" onclick="editToonCartItem(${idx})">Editar</button>
            <button type="button" class="client-cart-action remove" onclick="removeToonCartItem(${idx})">Quitar</button>
          </div>
        </div>
      </article>
    `;
  });

  const tax = subtotal * (checkoutTaxRate / 100);
  const isDelivery = document.getElementById("checkout-type").value === "delivery";
  const isLlevar = document.getElementById("checkout-type").value === "llevar";
  const delivCost = isDelivery ? checkoutDeliveryFee : 0.0;
  const empaqueCost = isLlevar ? checkoutPackageFee : 0.0;
  const total = subtotal + tax + delivCost + empaqueCost;

  container.innerHTML = html;
  document.getElementById("cart-subtotal").innerHTML = formatPriceDual(subtotal);
  document.getElementById("cart-tax").innerHTML = formatPriceDual(tax);
  if (document.getElementById("cart-delivery-cost")) document.getElementById("cart-delivery-cost").innerHTML = formatPriceDual(delivCost);
  if (document.getElementById("cart-empaque-cost")) document.getElementById("cart-empaque-cost").innerHTML = formatPriceDual(empaqueCost);
  document.getElementById("cart-total").innerHTML = formatPriceDual(total);
  updateCheckoutOrderSummary();
}

function removeToonCartItem(idx) {
  toonCart.splice(idx, 1);
  updateCartNavBadge();
  renderToonCart();
}

function adjustToonCartQuantity(index, amount) {
  const item = toonCart[index];
  if (!item) return;
  item.cantidad = Math.max(1, Math.min(99, item.cantidad + amount));
  item.subtotal = item.precio_unitario * item.cantidad;
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

  if (type === "mesa") {
    sectionMesa.style.display = "block";
    sectionDelivery.style.display = "none";
    if (deliveryRow) deliveryRow.style.display = "none";
    if (empaqueRow) empaqueRow.style.display = "none";
  } else if (type === "delivery") {
    sectionMesa.style.display = "none";
    sectionDelivery.style.display = "block";
    if (deliveryRow) deliveryRow.style.display = "flex";
    if (empaqueRow) empaqueRow.style.display = "none";
    setTimeout(() => initDeliveryInteractiveMap(), 150);
  } else {
    sectionMesa.style.display = "none";
    sectionDelivery.style.display = "none";
    if (deliveryRow) deliveryRow.style.display = "none";
    if (empaqueRow) empaqueRow.style.display = "flex";
  }
  renderToonCart();
  updateCheckoutAmountHint();
  updateCheckoutPaymentFields();
}

function updateCheckoutPaymentFields() {
  const method = document.getElementById("checkout-payment")?.value || "Efectivo";
  const selectedMode = document.querySelector('input[name="modo_pago"]:checked')?.value || "PAGAR_ANTES";
  selectedMesaPaymentMode = selectedMode;
  const deferredPayment = document.getElementById("checkout-type")?.value === "mesa" && selectedMode === "PAGAR_DESPUES";
  const currencyGroup = document.getElementById("checkout-currency-group");
  const referenceGroup = document.getElementById("checkout-payment-reference-group");
  const currencySelect = document.getElementById("checkout-currency");
  const referenceInput = document.getElementById("checkout-payment-reference");
  const bankInfo = document.getElementById("checkout-payment-bank-details");
  const methodGroup = document.getElementById("checkout-payment-method-group");
  const instructions = document.getElementById("checkout-payment-instructions");
  if (!currencyGroup || !referenceGroup || !currencySelect || !referenceInput) return;

  const isMobilePay = method === "Pago Móvil";
  const bankDetailsConfigured = Boolean(pagoMovilConfig.banco && pagoMovilConfig.telefono && pagoMovilConfig.rif && pagoMovilConfig.titular);
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
  const subtotal = toonCart.reduce((sum, item) => sum + item.subtotal, 0);
  const orderType = document.getElementById("checkout-type")?.value || "mesa";
  const extra = orderType === "delivery" ? checkoutDeliveryFee : (orderType === "llevar" ? checkoutPackageFee : 0);
  const total = Math.round((subtotal * (1 + checkoutTaxRate / 100) + extra) * 100) / 100;
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
  const subtotal = toonCart.reduce((sum, item) => sum + item.subtotal, 0);
  const tax = Math.round(subtotal * checkoutTaxRate / 100 * 100) / 100;
  const type = document.getElementById("checkout-type")?.value || "mesa";
  const deliveryFee = type === "delivery" ? checkoutDeliveryFee : 0;
  const packageFee = type === "llevar" ? checkoutPackageFee : 0;
  const total = Math.round((subtotal + tax + deliveryFee + packageFee) * 100) / 100;
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
    "checkout-summary-tax": tax,
    "checkout-summary-delivery": deliveryFee,
    "checkout-summary-package": packageFee,
    "checkout-summary-total": total,
  };
  Object.entries(values).forEach(([id, value]) => {
    const element = document.getElementById(id);
    if (element) element.innerHTML = formatPriceDual(value);
  });
  const deliveryRow = document.getElementById("checkout-summary-delivery-row");
  const packageRow = document.getElementById("checkout-summary-package-row");
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

  let mesaName = `Mesa ${currentDetectedMesa || 1}`;
  let delivNombre = null;
  let delivTel = null;
  let delivDir = null;
  const deliveryCoordinates = orderType === "delivery" ? currentCustomerGPS : null;

  if (orderType === "delivery") {
    delivNombre = document.getElementById("deliv-nombre").value;
    delivTel = document.getElementById("deliv-telefono").value;
    delivDir = document.getElementById("deliv-direccion").value;

    if (!delivNombre || !delivDir || !delivTel) {
      showToast("Por favor completa los datos obligatorios de entrega para Delivery.", "danger");
      return;
    }
    mesaName = "Delivery";
  }

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
    detalles: toonCart.map(item => ({
      producto_id: item.producto_id,
      cantidad: item.cantidad,
      personalizaciones: { opciones: item.opciones, extras: item.extras || [] }
    }))
  };

  if (!navigator.onLine) {
    updateClientNetworkStatus(false);
    showToast("No hay conexión. El pedido permanece guardado en este dispositivo; vuelve a enviarlo cuando recuperes internet.", "warning");
    return;
  }

  isSubmittingClientOrder = true;
  const submitButton = document.querySelector('#screen-checkout button[onclick="submitFinalOrder()"]');
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.setAttribute("aria-busy", "true");
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
    }
  }
}

function openOtpModal(orderId, code) {
  currentPendingOrderId = orderId;
  document.getElementById("otp-simulated-code").innerText = `Código sim enviado por WhatsApp: ${code}`;
  document.getElementById("otp-input-code").value = code;
  document.getElementById("otp-modal").classList.add("open");
}

async function submitOtpVerification() {
  const codeInput = document.getElementById("otp-input-code").value;
  if (!codeInput) {
    showToast("Ingresa el código OTP de 6 dígitos", "warning");
    return;
  }

  try {
    const res = await fetch("/api/v1/cliente/pedidos/verificar-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
    document.getElementById("otp-modal").classList.remove("open");
    showScreen("screen-tracking");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function loadHistorialPedidos() {
  try {
    const res = await fetch("/api/v1/cliente/pedidos/historial", {
      headers: Auth.getHeaders()
    });
    if (!res.ok) return;
    const pedidos = await res.json();
    
    let html = "";
    if (!pedidos || pedidos.length === 0) {
      html = `<p style="color: var(--text-muted); text-align: center;">No tienes pedidos anteriores registrados.</p>`;
    } else {
      pedidos.forEach(p => {
        const isActive = !["ENTREGADO", "CANCELADO"].includes(p.estado);
        html += `
          <div style="background: var(--toon-card); border: 1px solid var(--toon-border); padding: 1rem; border-radius: var(--radius-sm); margin-bottom: 0.85rem;">
            <div style="display: flex; justify-content: space-between; font-weight: 800;">
              <span>PEDIDO #${p.id} (${escapeClientHtml(p.numero_mesa)})</span>
              <span>${formatPriceDual(p.total)}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.3rem;">Estado: <strong style="color: var(--neon-green);">${escapeClientHtml(p.estado_delivery || p.estado)}</strong></div>
            ${isActive ? `<button class="btn-gold" style="margin-top:.65rem;width:100%" onclick="trackOrderById(${Number(p.id)})">📍 Seguir pedido</button>` : ""}
          </div>
        `;
      });
    }
    document.getElementById("historial-orders-list").innerHTML = html;
  } catch (err) {
    console.error(err);
  }
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
    openDeliveryMapModal();
  }
}

function enterCheckout(modality) {
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
  showScreen("screen-checkout");
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
  selectedDeliveryCoords = { lat: Number(lat), lng: Number(lng) };
  currentCustomerGPS = { ...selectedDeliveryCoords };
  const mapAddress = document.getElementById("map-address-input");
  if (mapAddress && !mapAddress.value.trim()) mapAddress.value = "Punto seleccionado en el mapa";
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${selectedDeliveryCoords.lat},${selectedDeliveryCoords.lng}`;
  const badge = document.getElementById("gps-status-badge");
  if (badge) {
    badge.style.display = "block";
    badge.innerHTML = `📍 Ubicación seleccionada · ${selectedDeliveryCoords.lat.toFixed(6)}, ${selectedDeliveryCoords.lng.toFixed(6)} · <a href="${mapsUrl}" target="_blank" rel="noopener noreferrer" style="color:var(--gold-accent);font-weight:800">Ver ruta</a>`;
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
    const mapsUrl = `https://maps.google.com/?q=${parseFloat(lat).toFixed(6)},${parseFloat(lng).toFixed(6)}`;
    const textVal = `📍 GPS: Lat ${parseFloat(lat).toFixed(6)}, Lng ${parseFloat(lng).toFixed(6)} (${mapsUrl})`;
    
    const input = document.getElementById("deliv-direccion");
    if (input) input.value = textVal;

    const badge = document.getElementById("gps-status-badge");
    if (badge) {
      badge.style.display = "block";
      badge.innerHTML = `🌐 <strong>GPS Google Maps:</strong> Lat ${parseFloat(lat).toFixed(6)}, Lng ${parseFloat(lng).toFixed(6)} • <a href="${mapsUrl}" target="_blank" style="color: var(--gold-accent); text-decoration: underline; font-weight: 800;">Probar en Google Maps</a>`;
    }
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
      const lat = position.coords.latitude.toFixed(6);
      const lng = position.coords.longitude.toFixed(6);
      updateCustomerDeliveryLocation(lat, lng);

      const dirInput = document.getElementById("deliv-direccion");
      if (dirInput) {
        dirInput.value = `Ubicación GPS: ${lat}, ${lng}`;
      }

      const badge = document.getElementById("gps-status-badge");
      if (badge) {
        badge.style.display = "block";
        badge.innerHTML = `✅ <strong>Ubicación GPS obtenida:</strong> ${lat}, ${lng}`;
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
  const comment = document.getElementById("rating-comment-input")?.value || "Excelente atención y comida deliciosa";
  const u = Auth.getUser();
  const name = u ? `${u.nombre} ${u.apellido}` : "Cliente Satisfecho";

  try {
    await fetch("/api/v1/cliente/resenas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nombre_cliente: name,
        comentario: comment,
        estrellas: currentRatingStars
      })
    });
    showToast("🌟 ¡Gracias por calificar nuestro servicio!", "success");
    closeModal("service-rating-modal");
    showScreen("screen-tracking");
  } catch(e) {
    closeModal("service-rating-modal");
    showScreen("screen-tracking");
  }
}

/* ==================== GUSTICOS VALENCIA INPIRED FUNCTIONS ==================== */
function sendChatbotMessage() {
  const input = document.getElementById("chat-input-msg");
  const container = document.getElementById("chat-messages-container");
  if (!input || !container) return;

  const msg = input.value.trim();
  if (!msg) return;

  const userDiv = document.createElement("div");
  userDiv.style.cssText = "background: var(--gold-gradient); color: #000; font-weight: 800; padding: 0.65rem 0.85rem; border-radius: 12px; font-size: 0.82rem; align-self: flex-end; max-width: 85%; box-shadow: 0 4px 12px rgba(255,188,13,0.3);";
  userDiv.innerText = msg;
  container.appendChild(userDiv);

  input.value = "";
  container.scrollTop = container.scrollHeight;

  setTimeout(() => {
    let reply = "¡Excelente consulta! Te recomendamos probar nuestra famosa **Hamburguesa Doble Toon** con Tocino o consultar nuestras promociones especiales.";
    const lower = msg.toLowerCase();

    if (lower.includes("promo") || lower.includes("oferta") || lower.includes("combo")) {
      reply = "🔥 ¡Nuestra mejor promo es el **COMBO EXPLOSIVO TOON**! Incluye 2 Hamburguesas + Papas Fritas + 2 Refrescos por solo **$15.00**.";
    } else if (lower.includes("horario") || lower.includes("abierto")) {
      reply = "🕒 Estamos abiertos todos los días de **11:00 AM a 11:00 PM**. Pedidos QR en mesa y Delivery en vivo.";
    } else if (lower.includes("pago") || lower.includes("banco") || lower.includes("zelle")) {
      reply = "💳 Aceptamos Pago Móvil (Banesco/Mercantil), Efectivo ($/Bs), Tarjetas de Crédito/Débito y Zelle.";
    } else if (lower.includes("pedido") || lower.includes("mi orden") || lower.includes("donde viene")) {
      reply = `📋 Tu pedido actual registrado está en proceso. Puedes revisar el estado en vivo desde la pestaña de **Pedidos**.`;
    }

    const botDiv = document.createElement("div");
    botDiv.style.cssText = "background: rgba(255,255,255,0.06); padding: 0.75rem; border-radius: 12px; font-size: 0.85rem; color: #fff; align-self: flex-start; border: 1px solid var(--toon-border); max-width: 88%;";
    botDiv.innerHTML = `🤖 ${reply}`;
    container.appendChild(botDiv);
    container.scrollTop = container.scrollHeight;
  }, 600);
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
  const username = document.getElementById("login-username-input")?.value;
  const pass = document.getElementById("login-pass-input")?.value;

  if (!username || !pass) {
    showToast("Ingresa tu usuario y contraseña", "warning");
    return;
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
