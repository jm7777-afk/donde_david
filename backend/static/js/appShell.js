// appShell.js – Universal Header & System Component for "Donde David"
// Estética Cashea, adaptabilidad por rol y monitoreo en tiempo real

function openModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.style.display = "flex";
    el.style.opacity = "1";
    el.style.pointerEvents = "auto";
    el.classList.add("open");
  }
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.remove("open");
    el.style.opacity = "0";
    el.style.pointerEvents = "none";
    el.style.display = "none";
  }
}

function detectSystemRole() {
  const path = window.location.pathname.toLowerCase();
  if (path.includes("/gerencia/")) return "gerente";
  if (path.includes("/admin/")) return "admin";
  if (path.includes("/cocina/")) return "cocina";
  if (path.includes("/caja/")) return "caja";
  if (path.includes("/mesero/")) return "mesero";
  if (path.includes("/delivery/")) return "delivery";
  if (path.includes("/cliente/")) return "cliente";
  return "landing";
}

function renderUniversalHeader() {
  const headerEl = document.getElementById("app-header");
  if (!headerEl) return;

  const role = detectSystemRole();

  // Configuración de Insignias por Rol
  const roleBadges = {
    landing: `<span class="universal-role-badge">🍔 FAST FOOD</span>`,
    cliente: `<span class="universal-role-badge cliente" id="header-table-badge">📱 QR MESA</span>`,
    admin: `<span class="universal-role-badge admin">👑 ADMINISTRADOR</span>`,
    gerente: `<span class="universal-role-badge admin">📊 GERENCIA</span>`,
    cocina: `<span class="universal-role-badge cocina">🍳 COCINA KDS</span>`,
    caja: `<span class="universal-role-badge caja">💵 CAJA POS TOUCH</span>`,
    mesero: `<span class="universal-role-badge mesero">🤵 MESERO / SALÓN</span>`,
    delivery: `<span class="universal-role-badge delivery">🛵 REPARTIDOR</span>`
  };

  // Botón Hamburguesa Móvil Universal para Todos los Roles
  const menuToggle = role === "admin" ? "toggleAdminDrawer()" : "toggleUniversalMobileDrawer()";
  const menuButtonClass = role === "admin"
    ? "universal-mobile-hamburger-trigger admin-menu-toggle"
    : "universal-mobile-hamburger-trigger";
  let leftAction = `
    <button class="${menuButtonClass}" type="button" aria-label="Abrir menú" aria-controls="${role === "admin" ? "admin-sidebar-drawer" : "universal-mobile-drawer"}" aria-expanded="false" onclick="${menuToggle}" style="margin-right: 0.6rem;">
      <span style="font-size: 1.15rem;">☰</span> <strong style="font-size: 0.78rem;">MENÚ</strong>
    </button>
  `;

  // Acciones Rápidas Específicas por Rol
  let rightActions = "";
  if (role === "cocina") {
    rightActions = `
      <div style="display: flex; gap: 0.3rem;" title="Escala de Pantalla KDS">
        <button class="btn btn-outline" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="typeof setKDSGridScale === 'function' && setKDSGridScale('scale-sm')">🔍 80%</button>
        <button class="btn btn-outline" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="typeof setKDSGridScale === 'function' && setKDSGridScale('scale-md')">📐 100%</button>
        <button class="btn btn-outline" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="typeof setKDSGridScale === 'function' && setKDSGridScale('scale-lg')">🐘 120%</button>
      </div>
    `;
  } else if (role === "caja") {
    rightActions = ``;
  } else if (role === "cliente") {
    rightActions = `
      <a onclick="showScreen('screen-carrito')" class="universal-cart-trigger" aria-label="Ver carrito">
        🛒 <span id="nav-cart-badge-hdr" class="badge">0</span>
      </a>
    `;
  } else if (role === "landing") {
    rightActions = `
      <a href="/static/cliente/app.html?mesa=5" class="btn btn-cta" style="padding: 0.4rem 0.9rem; font-size: 0.8rem;">🔥 PEDIR AHORA</a>
      <a href="/static/cliente/app.html?login=1" class="btn btn-outline" style="padding: 0.4rem 0.9rem; font-size: 0.8rem;">👤 CLIENTES</a>
    `;
  } else if (role === "admin" || role === "gerente") {
    rightActions = `
      <button class="btn btn-outline" style="padding: 0.35rem 0.65rem; font-size: 0.78rem; border-color: var(--cyan-accent); color: var(--cyan-accent);" onclick="openAdminScreensModal()" title="Acceso directo a todas las pantallas">
        🖥️ Pantallas
      </button>
    `;
  }

  // Si el usuario autenticado es Administrador, tiene acceso directo a Pantallas en cualquier vista
  const isAdminUser = typeof Auth !== "undefined" && typeof Auth.isAdmin === "function" && Auth.isAdmin();
  if (isAdminUser && role !== "admin" && role !== "gerente") {
    rightActions = `
      <button class="btn btn-outline" style="padding: 0.35rem 0.65rem; font-size: 0.78rem; border-color: var(--cyan-accent); color: var(--cyan-accent);" onclick="openAdminScreensModal()" title="Acceso directo del Administrador a todas las pantallas">
        🖥️ Pantallas
      </button>
    ` + rightActions;
  }

  // Botón de Tema Claro/Oscuro Universal + Cerrar Sesión
  const savedTheme = typeof localStorage !== "undefined" ? (localStorage.getItem("app_theme") || "dark") : "dark";
  if (typeof document !== "undefined" && document.body) {
    document.body.classList.toggle("light-theme", savedTheme === "light");
  }
  const themeBtnHtml = `
    <button class="btn btn-outline theme-toggle-btn" type="button" style="padding: 0.35rem 0.6rem; font-size: 0.76rem;" onclick="window.toggleAppTheme()">
      <span aria-hidden="true">${savedTheme === "light" ? "🌙" : "☀️"}</span><span>${savedTheme === "light" ? "OSCURO" : "BLANCO"}</span>
    </button>
  `;

  let logoutBtn = "";
  if (isAdminUser || (role !== "landing" && role !== "cliente" && role !== "caja")) {
    logoutBtn = `
      <button class="btn btn-cta universal-header-logout" type="button" aria-label="Cerrar sesión" title="Cerrar sesión" style="padding: 0.35rem 0.75rem; font-size: 0.78rem; background: rgba(255,71,87,0.2); border: 1px solid var(--neon-red); color: var(--neon-red);" onclick="typeof Auth !== 'undefined' ? Auth.logout() : (window.location.href='/login')">
        🚪 <span>Salir</span>
      </button>
    `;
  }

  headerEl.innerHTML = `
    <header class="universal-header">
      <div class="universal-header-inner">
        <!-- Izquierda: Marca Destacada Donde David con Logo Oficial 3D Extra Grande -->
        <div class="universal-header-brand-section" style="display: flex; align-items: center;">
          ${leftAction}
          <a href="#" class="universal-brand" aria-label="Recargar página" onclick="window.location.reload(); return false;">
            <img src="/static/img/logo.png" alt="Donde David">
            <span class="universal-brand-copy">
              <strong id="header-restaurant-name">DONDE DAVID | FAST FOOD</strong>
            </span>
          </a>
        </div>

        <!-- Centro: Rol, Tasa BCV y Conexión Realtime WebSocket -->
        <div class="universal-header-status-section" style="display: flex; align-items: center; gap: 0.6rem;">
          ${roleBadges[role] || roleBadges.landing}
          
          <div class="bcv-rate-badge" title="Tasa Oficial en Bolívares">
            💵 BCV: <span id="hdr-bcv-rate">No disponible</span>
          </div>

          <div class="ws-pulse-indicator" title="Estado de Conexión en Tiempo Real Servidor">
            <span class="ws-pulse-dot"></span>
            <span style="font-size: 0.72rem;">EN VIVO</span>
          </div>
        </div>

        <!-- Derecha: Acciones, tema y salir -->
        <div class="universal-header-action-section" style="display: flex; align-items: center; gap: 0.5rem;">
          ${themeBtnHtml}
          ${rightActions}
          ${logoutBtn}
        </div>
      </div>
    </header>
  `;
  // Eliminación absoluta e inmediata de subtítulos remanentes en todas las pantallas
  headerEl.querySelectorAll(".universal-brand-copy small, .universal-brand small").forEach(el => el.remove());
  if (typeof syncThemeToggleButtons === "function") syncThemeToggleButtons();
}

function cleanHeaderSubtitles() {
  document.querySelectorAll(".universal-brand-copy small, .universal-brand small, .universal-header small, #header-restaurant-name + small, #app-header small").forEach(el => el.remove());
}
if (typeof document !== "undefined") {
  cleanHeaderSubtitles();
  document.addEventListener("DOMContentLoaded", cleanHeaderSubtitles);
  window.addEventListener("load", cleanHeaderSubtitles);
}

// Invalidador automático de caches obsoletos en el cliente
if (typeof window !== "undefined" && "caches" in window) {
  caches.keys().then(names => {
    names.forEach(name => {
      if (name.startsWith("donde-david-pwa-") && name !== "donde-david-pwa-v36") {
        caches.delete(name);
      }
    });
  }).catch(() => {});
}

async function updateHeaderBcvRate() {
  const el = document.getElementById("hdr-bcv-rate");
  try {
    const res = await fetch("/api/v1/cliente/configuraciones-publicas");
    if (res.ok) {
      const cfg = await res.json();
      const brandName = String(cfg.nombre_restaurante || "DONDE DAVID | FAST FOOD").trim();
      const brandEl = document.getElementById("header-restaurant-name");
      if (brandEl) brandEl.textContent = brandName;
      const brandLink = document.querySelector(".universal-brand");
      if (brandLink) brandLink.setAttribute("aria-label", `${brandName}. Recargar página`);
      if (detectSystemRole() === "landing") {
        document.title = brandName;
        const ogTitle = document.querySelector('meta[property="og:title"]');
        if (ogTitle) ogTitle.setAttribute("content", brandName);
      }
      const rateValue = Number(cfg.tasa_cambio_bs);
      if (Number.isFinite(rateValue) && rateValue > 0) {
        if (el) el.innerText = `Bs. ${rateValue.toFixed(2)}/$`;
        if (typeof tasaCambioBs !== "undefined") tasaCambioBs = rateValue;
      } else if (el) {
        el.innerText = "No disponible";
        if (typeof tasaCambioBs !== "undefined") tasaCambioBs = null;
      }
    } else if (el) {
      el.innerText = "No disponible";
    }
  } catch (err) {
    console.error(err);
    if (el) el.innerText = "No disponible";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  renderUniversalHeader();
  createGlobalLoaderDOM();
  updateHeaderBcvRate();

  if (typeof WSClient !== "undefined") {
    try {
      new WSClient((event, data) => {
        if (event === "CONFIGURACION_ACTUALIZADA" || event === "TURNO_ACTUALIZADO") {
          updateHeaderBcvRate();
        }
      });
    } catch(e){}
  }
});

// Carga rápida optimizada sin bloqueos artificiales
(function initPageReloadLoader() {
  if (typeof document === "undefined") return;

  function dismissLoader() {
    hideGlobalLoader();
  }

  if (document.readyState === "complete") {
    dismissLoader();
  } else {
    window.addEventListener("load", dismissLoader);
    document.addEventListener("DOMContentLoaded", dismissLoader);
    setTimeout(dismissLoader, 300);
  }
})();

// ==================== UNIVERSAL LOADER SYSTEM API ====================
function createGlobalLoaderDOM() {
  if (document.getElementById("global-loader-backdrop")) return;

  const backdrop = document.createElement("div");
  backdrop.id = "global-loader-backdrop";
  backdrop.className = "global-loader-backdrop";
  backdrop.innerHTML = `
    <div class="global-loader-spinner-box">
      <div style="position: relative; width: 100px; height: 100px; display: flex; align-items: center; justify-content: center; margin-bottom: 0.25rem;">
        <div class="spinner-ring-neon"></div>
        <img src="/static/img/logo.png" alt="Donde David" style="position: absolute; width: 68px; height: auto; object-fit: contain; filter: drop-shadow(0 0 14px rgba(255,183,3,0.8)); animation: logoPulse 1.4s ease-in-out infinite alternate;">
      </div>
      <div style="text-align: center;">
        <div class="global-loader-text" id="global-loader-msg">PROCESANDO SOLICITUD EN VIVO...</div>
        <div class="global-loader-subtext">
          <span style="color: var(--cyan-accent); font-weight: 800;">DONDE DAVID POS</span> • ESTADO DE OPERACIÓN EN CURSO
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);
}

function showGlobalLoader(message = "PROCESANDO SOLICITUD...") {
  createGlobalLoaderDOM();
  const el = document.getElementById("global-loader-backdrop");
  const msgEl = document.getElementById("global-loader-msg");
  if (msgEl) msgEl.innerText = message;
  if (el) {
    el.style.display = "flex";
    el.style.opacity = "1";
    el.style.pointerEvents = "auto";
    el.style.zIndex = "999999";
    el.classList.add("open");
  }
}

function hideGlobalLoader() {
  const el = document.getElementById("global-loader-backdrop");
  if (el) {
    el.classList.remove("open");
    el.style.opacity = "0";
    el.style.pointerEvents = "none";
    el.style.display = "none";
  }
}



// ==================== UNIVERSAL MOBILE DRAWER SYSTEM ====================
function createUniversalMobileDrawerDOM() {
  if (document.getElementById("universal-mobile-drawer")) return;

  const role = detectSystemRole();
  if (role === "admin") return;

  let roleItems = "";
  if (role === "caja") {
    roleItems = `
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof switchTab==='function') switchTab('pos');">🖥️ POS Touch Grid</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof switchTab==='function') switchTab('pendientes');">🧾 Cuentas y Cobros</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof switchTab==='function') switchTab('postres');">🍰 Preparación Postres</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof switchTab==='function') switchTab('deliverys');">🛵 Deliverys y Entregas</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof switchTab==='function') switchTab('facturas');">📄 Consulta de Facturas</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof openModal==='function') openModal('open-shift-modal');">🟢 Apertura / Cierre Turno</div>
    `;
  } else if (role === "cliente") {
    roleItems = `
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof showScreen==='function') showScreen('screen-menu');">🍔 Menú Fast Food QR</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof showScreen==='function') showScreen('screen-carrito');">🛒 Mi Carrito de Compras</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof showScreen==='function') showScreen('screen-historial');">📋 Mis Pedidos Activos</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof showScreen==='function') showScreen('screen-tracking');">📍 Seguimiento de pedido</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof openModal==='function') openModal('service-rating-modal');">⭐ Calificar Servicio</div>
    `;
  } else if (role === "cocina") {
    roleItems = `
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof loadCocinaComandas==='function') loadCocinaComandas();">🍳 Actualizar Comandas</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof setKDSGridScale==='function') setKDSGridScale('scale-sm');">🔍 Escala KDS 80%</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof setKDSGridScale==='function') setKDSGridScale('scale-md');">📐 Escala KDS 100%</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof setKDSGridScale==='function') setKDSGridScale('scale-lg');">🐘 Escala KDS 120%</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof openModal==='function') openModal('cocina-guide-modal');">📜 Guía KDS Cocina</div>
    `;
  } else if (role === "mesero") {
    roleItems = `
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof loadMeseroData==='function') loadMeseroData();">🍽️ Actualizar Mesas Salón</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof openModal==='function') openModal('mesero-guide-modal');">❓ Guía de Meseros</div>
    `;
  } else if (role === "delivery") {
    roleItems = `
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); if (typeof loadCourierOrders==='function') loadCourierOrders();">🛵 Actualizar mis entregas</div>
    `;
  } else if (role === "gerente") {
    roleItems = `
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); loadManagerDashboard();">📊 Actualizar indicadores</div>
    `;
  } else {
    roleItems = `
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); window.location.href='/static/cliente/app.html?mesa=5';">🔥 Ver Menú y Pedir</div>
      <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); window.location.href='/static/cliente/app.html?login=1';">👤 Acceso de Clientes</div>
    `;
  }

  const backdrop = document.createElement("div");
  backdrop.id = "universal-mobile-overlay";
  backdrop.className = "universal-mobile-drawer-overlay";
  backdrop.onclick = closeUniversalMobileDrawer;

  const drawer = document.createElement("div");
  drawer.id = "universal-mobile-drawer";
  drawer.className = "universal-mobile-drawer-card";
  drawer.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem; border-bottom: 1px solid var(--toon-border); padding-bottom: 0.85rem;">
      <div style="display: flex; align-items: center; gap: 0.6rem;">
        <a href="#" aria-label="Recargar página" onclick="window.location.reload(); return false;">
          <img src="/static/img/logo.png" alt="Donde David" style="height: 42px; width: auto; object-fit: contain;">
        </a>
        <span style="font-weight: 900; font-family: var(--font-display); color: var(--gold-accent); font-size: 0.95rem;">MENÚ MÓVIL</span>
      </div>
      <button onclick="closeUniversalMobileDrawer()" style="background: transparent; border: none; color: #fff; font-size: 1.6rem; cursor: pointer;">&times;</button>
    </div>

    <div style="flex: 1;">
      <div style="font-size: 0.72rem; font-weight: 900; text-transform: uppercase; color: var(--cyan-accent); letter-spacing: 1px; margin-bottom: 0.6rem;">OPCIONES DEL MÓDULO</div>
      ${roleItems}
      ${(typeof Auth !== "undefined" && typeof Auth.isAdmin === "function" && Auth.isAdmin()) ? `
        <div style="font-size: 0.72rem; font-weight: 900; text-transform: uppercase; color: var(--gold-accent); letter-spacing: 1px; margin: 1.25rem 0 0.6rem 0;">PANTALLAS DEL SISTEMA (ADMIN)</div>
        <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); window.location.href='/static/admin/index.html';">⚙️ Panel Administrador</div>
        <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); window.location.href='/static/caja/panel.html';">💰 Caja POS / Cobro</div>
        <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); window.location.href='/static/cocina/monitor.html';">👨‍🍳 Monitor KDS Cocina</div>
        <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); window.location.href='/static/mesero/panel.html';">🍽️ Meseros & Salón</div>
        <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); window.location.href='/static/delivery/panel.html';">🛵 Despacho Delivery</div>
        <div class="drawer-nav-item" onclick="closeUniversalMobileDrawer(); window.location.href='/static/gerencia/panel.html';">📈 Panel de Gerencia</div>
      ` : ''}
    </div>

    <div style="border-top: 1px solid var(--toon-border); padding-top: 1rem; margin-top: 1rem;">
      <div class="drawer-nav-item" style="color: var(--neon-red); border-color: rgba(255,71,87,0.3);" onclick="closeUniversalMobileDrawer(); if (typeof Auth!=='undefined') Auth.logout(); else window.location.href='/login';">🚪 Cerrar Sesión / Salir</div>
    </div>
  `;

  document.body.appendChild(backdrop);
  document.body.appendChild(drawer);
}

function toggleUniversalMobileDrawer() {
  createUniversalMobileDrawerDOM();
  const overlay = document.getElementById("universal-mobile-overlay");
  const drawer = document.getElementById("universal-mobile-drawer");
  if (overlay && drawer) {
    overlay.classList.toggle("open");
    drawer.classList.toggle("open");
  }
}

function closeUniversalMobileDrawer() {
  const overlay = document.getElementById("universal-mobile-overlay");
  const drawer = document.getElementById("universal-mobile-drawer");
  if (overlay) overlay.classList.remove("open");
  if (drawer) drawer.classList.remove("open");
}

function openAdminScreensModal() {
  let modal = document.getElementById("admin-screens-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "admin-screens-modal";
    modal.className = "product-modal-backdrop";
    modal.onclick = (e) => {
      if (e.target === modal) closeAdminScreensModal();
    };
    modal.innerHTML = `
      <div class="product-modal-card admin-screens-card">
        <div class="admin-screens-header">
          <h3 class="admin-screens-title">
            <span>🖥️</span> PANTALLAS DEL SISTEMA
          </h3>
          <button class="modal-close-btn" onclick="closeAdminScreensModal()" aria-label="Cerrar modal">&times;</button>
        </div>
        <p class="admin-screens-desc">
          Acceso rápido del Administrador a todos los paneles y pantallas del restaurante:
        </p>
        <div class="admin-screens-grid">
          <a href="/static/admin/index.html" class="admin-screens-link">
            <span>⚙️</span> <span>Administración</span>
          </a>
          <a href="/static/caja/panel.html" class="admin-screens-link">
            <span>💰</span> <span>Caja POS Touch</span>
          </a>
          <a href="/static/cocina/monitor.html" class="admin-screens-link">
            <span>👨‍🍳</span> <span>Monitor Cocina KDS</span>
          </a>
          <a href="/static/mesero/panel.html" class="admin-screens-link">
            <span>🍽️</span> <span>Meseros & Salón</span>
          </a>
          <a href="/static/delivery/panel.html" class="admin-screens-link">
            <span>🛵</span> <span>Despacho Delivery</span>
          </a>
          <a href="/static/gerencia/panel.html" class="admin-screens-link">
            <span>📈</span> <span>Panel de Gerencia</span>
          </a>
          <a href="/static/cliente/app.html" class="admin-screens-link">
            <span>📱</span> <span>Menú Clientes (PWA)</span>
          </a>
          <a href="/static/index.html" class="admin-screens-link">
            <span>🌐</span> <span>Portada Web Oficial</span>
          </a>
          <a href="/static/turnos/pantalla.html" class="admin-screens-link">
            <span>📺</span> <span>Pantalla Turnos TV</span>
          </a>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }
  modal.classList.add("open");
}

function closeAdminScreensModal() {
  const modal = document.getElementById("admin-screens-modal");
  if (modal) modal.classList.remove("open");
}

window.toggleAppTheme = function toggleAppTheme() {
  if (typeof toggleThemeMode === "function") {
    toggleThemeMode();
    return;
  }
  const isLight = document.body.classList.toggle("light-theme");
  try { localStorage.setItem("app_theme", isLight ? "light" : "dark"); } catch {}
  document.querySelectorAll(".theme-toggle-btn").forEach(btn => {
    btn.innerHTML = `<span aria-hidden="true">${isLight ? "🌙" : "☀️"}</span><span>${isLight ? "OSCURO" : "BLANCO"}</span>`;
  });
};

window.showConfirmModal = function showConfirmModal({
  title = "Confirmar acción",
  message = "¿Estás seguro de continuar?",
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  danger = false
} = {}) {
  return new Promise(resolve => {
    const backdrop = document.createElement("div");
    backdrop.className = "dd-confirm-backdrop";
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-modal", "true");
    const safeTitle = String(title).replace(/[&<>"']/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[m]));
    const safeMsg = String(message).replace(/[&<>"']/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[m]));
    backdrop.innerHTML = `
      <div class="dd-confirm-card">
        <h4 class="dd-confirm-title">${safeTitle}</h4>
        <p class="dd-confirm-msg">${safeMsg}</p>
        <div class="dd-confirm-actions">
          <button type="button" class="btn btn-outline" id="dd-confirm-cancel">${cancelLabel}</button>
          <button type="button" class="${danger ? "btn-gold" : "btn btn-cta"}" id="dd-confirm-ok">${confirmLabel}</button>
        </div>
      </div>
    `;
    const cleanup = answer => {
      document.removeEventListener("keydown", onKey);
      backdrop.remove();
      resolve(answer);
    };
    const onKey = evt => {
      if (evt.key === "Escape") cleanup(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.appendChild(backdrop);
    backdrop.querySelector("#dd-confirm-cancel")?.addEventListener("click", () => cleanup(false));
    backdrop.querySelector("#dd-confirm-ok")?.addEventListener("click", () => cleanup(true));
  });
};

window.printThermalDocument = function printThermalDocument(innerHtml, title = "Donde David") {
  let root = document.getElementById("dd-print-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "dd-print-root";
    root.className = "dd-print-only";
    document.body.appendChild(root);
  }
  root.innerHTML = `<div class="dd-thermal-head"><strong>DONDE DAVID</strong><br><small>${String(title).replace(/</g, "&lt;")}</small></div>${innerHtml}`;
  window.print();
};

// Fetch Interceptor optimizado: Carga ultra-rápida sin parpadeos ni bloqueos en consultas GET
if (typeof window !== "undefined" && window.fetch) {
  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    const url = args[0] ? args[0].toString() : "";
    const options = args[1] || {};
    const method = (options.method || "GET").toUpperCase();
    
    // Solo mostrar loader si una operación de guardado/mutación demora más de 400ms
    let timer = null;
    if (method !== "GET" && !url.includes("/health") && !url.includes("/websocket")) {
      timer = setTimeout(() => {
        showGlobalLoader("GUARDANDO...");
      }, 400);
    }
    
    try {
      const response = await originalFetch.apply(this, args);
      return response;
    } finally {
      if (timer) clearTimeout(timer);
      hideGlobalLoader();
    }
  };
}
