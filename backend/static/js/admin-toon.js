let adminStats = null;
let adminMesas = [];
let adminInsumos = [];
let adminProducts = [];
let adminCategories = [];
let adminGuiaItems = [];
let adminPromos = [];
let editingPromoId = null;
let adminResenas = [];
let adminPublicaciones = [];
let selectedInsumoForIngreso = null;
let tasaCambioBs = null;
let currentWizardStep = 1;

function escapeAdminHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function parseProductEditorList(rawValue, kind) {
  const rows = rawValue.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  if (rows.length > 30) throw new Error("Se permiten hasta 30 elementos por producto.");
  return rows.map((row, index) => {
    const [first, second, ...rest] = row.split("|").map(value => value.trim());
    if (rest.length || !first || !second) {
      throw new Error(`Revisa la línea ${index + 1}; utiliza el formato indicado.`);
    }
    if (kind === "extras") {
      const price = Number(second);
      if (!Number.isFinite(price) || price < 0 || price > 100000) {
        throw new Error(`El precio del extra en la línea ${index + 1} debe ser válido.`);
      }
      return { nombre: first, precio: price };
    }
    if (!["imagen", "video"].includes(first.toLowerCase())) {
      throw new Error(`El tipo de contenido en la línea ${index + 1} debe ser imagen o video.`);
    }
    if (!(second.startsWith("https://") || second.startsWith("/static/uploads/"))) {
      throw new Error(`La URL multimedia en la línea ${index + 1} debe ser HTTPS o /static/uploads/.`);
    }
    return { tipo: first.toLowerCase(), url: second };
  });
}

function productEditorListValue(jsonValue, kind) {
  try {
    const values = JSON.parse(jsonValue || "[]");
    if (!Array.isArray(values)) return "";
    return values.map(item => kind === "extras"
      ? `${item.nombre} | ${item.precio}`
      : `${item.tipo} | ${item.url}`).join("\n");
  } catch (error) {
    console.error(`No se pudo leer la configuración ${kind} del producto.`, error);
    return "";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadDashboardStats();
  loadGuiaAdmin();
  loadMesas();
  loadInsumos();
  loadProducts();
  loadCategories();
  loadUsers();
  loadPromosAdmin();
  loadResenasAdmin();
  loadPublicacionesAdmin();
  loadPortalConfigsAdmin();
  const requestedTab = window.location.hash.replace(/^#tab-/, "");
  if (["dashboard", "productos", "inventario", "promociones", "publicaciones", "portal", "mesas", "categorias", "usuarios"].includes(requestedTab)) {
    switchTab(requestedTab);
  }

  new WSClient((event, data) => {
    if (event === "NUEVO_PEDIDO" || event === "PAGO_CONFIRMADO") {
      loadDashboardStats();
      loadMesas();
      loadInsumos();
    }
  });
});

function formatPriceDual(usdAmount) {
  const usd = Number(usdAmount) || 0;
  if (!Number.isFinite(tasaCambioBs) || tasaCambioBs <= 0) return `$${usd.toFixed(2)}`;
  const bsAmount = (usd * tasaCambioBs).toFixed(2);
  return `$${usd.toFixed(2)} <br><small style="color:var(--gold-accent)">(Bs. ${bsAmount})</small>`;
}

async function uploadLocalFile(event, targetInputId) {
  const file = event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  showToast("Subiendo archivo al servidor...", "info");

  try {
    const res = await fetch("/api/v1/admin/upload", {
      method: "POST",
      headers: Auth.getToken() ? { Authorization: `Bearer ${Auth.getToken()}` } : {},
      body: formData
    });
    if (!res.ok) throw new Error("Error al subir archivo");
    const data = await res.json();
    document.getElementById(targetInputId).value = data.url;
    showToast("¡Archivo guardado en el servidor con éxito!", "success");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function toggleAdminDrawer() {
  const drawer = document.getElementById("admin-sidebar-drawer");
  if (!drawer) return;

  let overlay = document.getElementById("admin-drawer-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "admin-drawer-overlay";
    overlay.className = "admin-drawer-overlay";
    overlay.setAttribute("aria-hidden", "true");
    overlay.onclick = closeAdminDrawer;
    document.body.appendChild(overlay);
  }

  drawer.classList.toggle("open");
  const isOpen = drawer.classList.contains("open");
  overlay.classList.toggle("open", isOpen);
  overlay.setAttribute("aria-hidden", String(!isOpen));
  drawer.setAttribute("aria-hidden", String(!isOpen));
  document.querySelector(".admin-menu-toggle")?.setAttribute("aria-expanded", String(isOpen));
}

function closeAdminDrawer() {
  const drawer = document.getElementById("admin-sidebar-drawer");
  const overlay = document.getElementById("admin-drawer-overlay");
  if (drawer) drawer.classList.remove("open");
  if (drawer) drawer.setAttribute("aria-hidden", "true");
  if (overlay) {
    overlay.classList.remove("open");
    overlay.setAttribute("aria-hidden", "true");
  }
  document.querySelector(".admin-menu-toggle")?.setAttribute("aria-expanded", "false");
}

document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeAdminDrawer();
});

function switchTab(tabId) {
  document.querySelectorAll(".tab-btn, .admin-sidebar-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

  const btns = Array.from(document.querySelectorAll(".tab-btn, .admin-sidebar-btn")).filter(b => b.getAttribute("onclick") && b.getAttribute("onclick").includes(tabId));
  btns.forEach(b => b.classList.add("active"));
  const content = document.getElementById(`tab-${tabId}`);
  if (content) content.classList.add("active");

  closeAdminDrawer();
}

function openModal(id) { document.getElementById(id).classList.add("open"); }
function closeModal(id) { document.getElementById(id).classList.remove("open"); }

function openAdminScreenGuide() {
  openModal("system-screen-guide-modal");
}

/* ==================== WIZARD DE CONFIGURACIÓN INICIAL ==================== */
function openWizardModal() {
  currentWizardStep = 1;
  updateWizardUI();
  openModal("wizard-modal");
}

function wizardNav(direction) {
  currentWizardStep += direction;
  if (currentWizardStep < 1) currentWizardStep = 1;
  if (currentWizardStep > 4) {
    submitWizardFinish();
    return;
  }
  updateWizardUI();
}

function updateWizardUI() {
  document.querySelectorAll(".wizard-step").forEach((s, idx) => {
    s.classList.toggle("active", idx + 1 === currentWizardStep);
  });

  const stepTitles = [
    "Paso 1 de 4: Identidad y Moneda",
    "Paso 2 de 4: Menú y Productos",
    "Paso 3 de 4: Mesas y Códigos QR",
    "Paso 4 de 4: Resumen de Usuarios"
  ];
  document.getElementById("wizard-step-title").innerText = stepTitles[currentWizardStep - 1];

  const btnPrev = document.getElementById("wiz-btn-prev");
  const btnNext = document.getElementById("wiz-btn-next");

  btnPrev.style.display = currentWizardStep === 1 ? "none" : "inline-block";
  btnNext.innerText = currentWizardStep === 4 ? "🚀 FINALIZAR Y GUARDAR CONFIGURACIÓN" : "Siguiente →";
}

async function submitWizardFinish() {
  const nombre = document.getElementById("wiz-nombre").value;
  const historia = document.getElementById("wiz-historia").value;
  const tasa = document.getElementById("wiz-tasa").value.trim();
  const whatsapp = document.getElementById("wiz-whatsapp").value;

  if (tasa && (!Number.isFinite(Number(tasa)) || Number(tasa) <= 0)) {
    showToast("La tasa manual debe ser un número mayor que cero.", "warning");
    return;
  }
  tasaCambioBs = Number(tasa) > 0 ? Number(tasa) : null;

  const items = [
    { clave: "nombre_restaurante", valor: nombre },
    { clave: "historia_restaurante", valor: historia },
    { clave: "whatsapp_contacto", valor: whatsapp }
  ];
  if (tasa) items.push({ clave: "tasa_cambio_bs", valor: tasa });

  try {
    const response = await fetch("/api/v1/admin/configuraciones/lote", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ configuraciones: items })
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "El servidor rechazó la configuración.");
    }
    showToast("Configuración inicial guardada correctamente.", "success");
    closeModal("wizard-modal");
    await loadPortalConfigsAdmin();
    loadDashboardStats();
  } catch (err) {
    showToast(`No se guardó la configuración: ${err.message}`, "danger");
  }
}

async function loadDashboardStats() {
  try {
    const res = await fetch("/api/v1/admin/dashboard-stats", { headers: Auth.getHeaders() });
    if (res.ok) {
      adminStats = await res.json();
      
      const vHoy = Number(adminStats.ventas_hoy ?? 0);
      const vSemana = Number(adminStats.ventas_semana ?? 0);
      const vMes = Number(adminStats.ventas_mes ?? 0);
      const vTotal = Number(adminStats.total_ventas ?? 0);
      const montoCaja = Number(adminStats.monto_caja ?? 0);

      if (document.getElementById("stat-sales-today")) {
        document.getElementById("stat-sales-today").innerHTML = formatPriceDual(vHoy);
      }
      if (document.getElementById("stat-sales-week")) {
        document.getElementById("stat-sales-week").innerHTML = formatPriceDual(vSemana);
      }
      if (document.getElementById("stat-sales-month")) {
        document.getElementById("stat-sales-month").innerHTML = formatPriceDual(vMes);
      }
      if (document.getElementById("stat-sales-total")) {
        document.getElementById("stat-sales-total").innerHTML = formatPriceDual(vTotal);
      }
      if (document.getElementById("stat-pct-week")) {
        document.getElementById("stat-pct-week").innerText = `${adminStats.pct_crecimiento_semanal || "N/D"} vs semana anterior`;
      }
      if (document.getElementById("stat-pct-month")) {
        document.getElementById("stat-pct-month").innerText = `${adminStats.pct_crecimiento_mensual || "N/D"} vs mes anterior`;
      }
      if (document.getElementById("stat-caja")) {
        document.getElementById("stat-caja").innerText = `$${montoCaja.toFixed(2)}`;
      }

      if (document.getElementById("stat-critical")) document.getElementById("stat-critical").innerText = `${adminStats.stock_critico} insumos`;
      if (document.getElementById("stat-cocina")) document.getElementById("stat-cocina").innerText = `${adminStats.pedidos_cocina} pedidos`;
      if (document.getElementById("stat-mesas")) document.getElementById("stat-mesas").innerText = `${adminStats.mesas_ocupadas || 0} / ${adminStats.total_mesas || 0}`;

      if (adminStats.desglose_canales) {
        if (document.getElementById("pct-canal-mesa")) document.getElementById("pct-canal-mesa").innerText = `${adminStats.desglose_canales.pct_mesa}%`;
        if (document.getElementById("pct-canal-delivery")) document.getElementById("pct-canal-delivery").innerText = `${adminStats.desglose_canales.pct_delivery}%`;
        if (document.getElementById("pct-canal-llevar")) document.getElementById("pct-canal-llevar").innerText = `${adminStats.desglose_canales.pct_llevar}%`;
        ["mesa", "delivery", "llevar"].forEach(channel => {
          const bar = document.getElementById(`bar-canal-${channel}`);
          const value = Number(adminStats.desglose_canales[`pct_${channel}`] || 0);
          if (bar) bar.style.width = `${Math.max(0, Math.min(100, value))}%`;
        });
      }

      let topHtml = "";
      if (adminStats.top_productos && adminStats.top_productos.length > 0) {
        adminStats.top_productos.forEach((p, idx) => {
          topHtml += `
            <div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--toon-border);">
              <span><strong>#${idx + 1} ${p.nombre}</strong> (${p.unidades} unidades vendidas)</span>
              <strong style="color: var(--gold-accent);">${formatPriceDual(p.total)}</strong>
            </div>
          `;
        });
      }
      if (document.getElementById("top-products-container")) {
        document.getElementById("top-products-container").innerHTML = topHtml;
      }
    }
  } catch (err) {
    console.error(err);
  }
}

/* ==================== PUBLICACIONES WEB ADMIN ==================== */
async function loadPublicacionesAdmin() {
  try {
    const res = await fetch("/api/v1/admin/publicaciones", { headers: Auth.getHeaders() });
    if (res.ok) {
      adminPublicaciones = await res.json();
      renderPublicacionesAdmin();
    }
  } catch (err) {
    console.error(err);
  }
}

function renderPublicacionesAdmin() {
  const tbody = document.getElementById("publicaciones-tbody");
  if (!tbody) return;

  let html = "";
  if (adminPublicaciones.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No hay publicaciones creadas. Agrega una nueva.</td></tr>`;
    return;
  }

  adminPublicaciones.forEach(p => {
    const img = p.imagen_url || "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500";
    html += `
      <tr style="border-bottom: 1px solid var(--toon-border);">
        <td style="padding: 0.75rem;"><img src="${img}" style="width: 50px; height: 50px; border-radius: 8px; object-fit: cover;"></td>
        <td style="padding: 0.75rem; font-weight: 700; color: #fff;">${p.titulo}</td>
        <td style="padding: 0.75rem; color: var(--text-muted); font-size: 0.85rem;">${p.contenido}</td>
        <td style="padding: 0.75rem;"><span class="badge" style="background: var(--gold-accent); color: #000; font-weight: 800;">${p.autor}</span></td>
        <td style="padding: 0.75rem;"><button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem; background: var(--neon-red); color: #fff;" onclick="deletePublicacion(${p.id})">🗑️ Eliminar</button></td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

async function submitCreatePublicacion() {
  const payload = {
    titulo: document.getElementById("pub-titulo").value,
    contenido: document.getElementById("pub-contenido").value,
    imagen_url: document.getElementById("pub-img").value || "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500",
    autor: "Donde David Admin"
  };

  if (!payload.titulo || !payload.contenido) {
    showToast("Ingresa título y contenido para el anuncio", "warning");
    return;
  }

  try {
    const res = await fetch("/api/v1/admin/publicaciones", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Error al publicar");
    showToast("Publicación publicada en la Web Pública con éxito", "success");
    closeModal("add-publicacion-modal");
    loadPublicacionesAdmin();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function deletePublicacion(id) {
  if (!confirm("¿Eliminar esta publicación de la web pública?")) return;
  try {
    const res = await fetch(`/api/v1/admin/publicaciones/${id}`, { method: "DELETE", headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("Error al eliminar");
    showToast("Publicación eliminada", "success");
    loadPublicacionesAdmin();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

/* ==================== PRODUCTOS E INGREDIENTES EDITABLES ==================== */
async function loadProducts() {
  try {
    const res = await fetch("/api/v1/admin/productos", { headers: Auth.getHeaders() });
    if (res.ok) {
      adminProducts = await res.json();
      renderProducts();
    }
  } catch (err) {
    console.error(err);
  }
}

function renderProducts() {
  const tbody = document.getElementById("products-tbody");
  if (!tbody) return;

  const query = (document.getElementById("products-search")?.value || "").trim().toLocaleLowerCase();
  const sortBy = document.getElementById("products-sort")?.value || "category-name";
  const categoriesById = new Map(adminCategories.map(category => [category.id, category.nombre]));
  const products = adminProducts.filter(product => {
    const categoryName = categoriesById.get(product.categoria_id) || product.categoria?.nombre || "";
    return `${product.nombre} ${categoryName}`.toLocaleLowerCase().includes(query);
  });
  products.sort((left, right) => {
    if (sortBy === "newest") return right.id - left.id;
    if (sortBy === "name") return left.nombre.localeCompare(right.nombre, "es", { sensitivity: "base" });
    const categorySort = (categoriesById.get(left.categoria_id) || left.categoria?.nombre || "")
      .localeCompare(categoriesById.get(right.categoria_id) || right.categoria?.nombre || "", "es", { sensitivity: "base" });
    return categorySort || left.nombre.localeCompare(right.nombre, "es", { sensitivity: "base" });
  });
  if (!products.length) {
    tbody.innerHTML = '<tr><td colspan="10" style="padding:1rem;text-align:center;color:var(--text-muted)">No hay productos que coincidan con la búsqueda.</td></tr>';
    return;
  }

  tbody.innerHTML = products.map(p => {
    const img = escapeAdminHtml(p.imagen_url || "/static/img/logo.png");
    let ingsStr = "";
    if (p.ingredientes_json) {
      try {
        const arr = JSON.parse(p.ingredientes_json);
        ingsStr = Array.isArray(arr) ? arr.join(", ") : "Configuración inválida";
      } catch(error) {
        console.error(`Ingredientes inválidos para producto ${p.id}.`, error);
        ingsStr = "Configuración inválida";
      }
    } else {
      ingsStr = "Estándar";
    }
    const category = categoriesById.get(p.categoria_id) || p.categoria?.nombre || "Sin categoría";

    return `
      <tr style="border-bottom: 1px solid var(--toon-border);">
        <td style="padding: 0.75rem;"><img src="${img}" alt="" loading="lazy" style="width: 44px; height: 44px; border-radius: 8px; object-fit: cover;"></td>
        <td style="padding: 0.75rem;">${escapeAdminHtml(category)}</td>
        <td style="padding: 0.75rem; font-weight: 700; color: #fff;">${escapeAdminHtml(p.nombre)}</td>
        <td style="padding: 0.75rem; font-weight: 900;">${formatPriceDual(p.precio)}</td>
        <td style="padding: 0.75rem; font-size: 0.8rem; color: var(--text-muted);">${escapeAdminHtml(ingsStr)}</td>
        <td style="padding: 0.75rem; font-size: 0.8rem;">${escapeAdminHtml(p.alergenos || "Sin declarar")}</td>
        <td style="padding: 0.75rem;">🎁 ${Number(p.puntos_fidelidad) || 0}</td>
        <td style="padding: 0.75rem;">${p.disponible ? "Disponible" : "No disponible"}</td>
        <td style="padding: 0.75rem;">${p.stock}</td>
        <td style="padding: 0.75rem; display: flex; gap: 0.4rem;">
          <button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="openEditProductModal(${p.id})">✏️ Editar</button>
          <button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem; background: var(--neon-red); color: #fff;" onclick="deleteProducto(${p.id})">🗑️</button>
        </td>
      </tr>
    `;
  }).join("");
}

function openEditProductModal(prodId) {
  const p = adminProducts.find(item => item.id === prodId);
  if (!p) return;

  document.getElementById("edit-prod-id").value = p.id;
  document.getElementById("edit-prod-name").value = p.nombre;
  document.getElementById("edit-prod-desc").value = p.descripcion || '';
  document.getElementById("edit-prod-price").value = p.precio;
  document.getElementById("edit-prod-price-promo").value = p.precio_promocion || '';
  document.getElementById("edit-prod-points").value = Number(p.puntos_fidelidad) || 0;
  document.getElementById("edit-prod-tiempo-preparacion").value = p.tiempo_preparacion || 15;
  document.getElementById("edit-prod-img").value = p.imagen_url || '';
  document.getElementById("edit-prod-alergenos").value = p.alergenos || '';
  document.getElementById("edit-prod-disponible").checked = p.disponible !== false;
  document.getElementById("edit-prod-extras").value = productEditorListValue(p.extras_json, "extras");
  document.getElementById("edit-prod-media").value = productEditorListValue(p.media_json, "media");

  let ingsStr = "";
  if (p.ingredientes_json) {
    try {
      const arr = JSON.parse(p.ingredientes_json);
      ingsStr = arr.join(", ");
    } catch(e) { ingsStr = p.ingredientes_json; }
  }
  document.getElementById("edit-prod-ingredientes").value = ingsStr;

  const select = document.getElementById("edit-prod-cat-select");
  let opts = "";
  adminCategories.forEach(c => {
    opts += `<option value="${c.id}" ${c.id === p.categoria_id ? 'selected' : ''}>${c.nombre}</option>`;
  });
  select.innerHTML = opts;

  openModal("edit-product-modal");
}

async function submitUpdateProduct() {
  const prodId = document.getElementById("edit-prod-id").value;
  const ingsInput = document.getElementById("edit-prod-ingredientes").value;
  let ingsArr = ingsInput.split(",").map(i => i.trim()).filter(i => i.length > 0);

  let extras;
  let media;
  try {
    extras = parseProductEditorList(document.getElementById("edit-prod-extras").value, "extras");
    media = parseProductEditorList(document.getElementById("edit-prod-media").value, "media");
  } catch (error) {
    showToast(error.message, "warning");
    return;
  }
  const payload = {
    nombre: document.getElementById("edit-prod-name").value,
    descripcion: document.getElementById("edit-prod-desc").value,
    precio: parseFloat(document.getElementById("edit-prod-price").value),
    precio_promocion: parseFloat(document.getElementById("edit-prod-price-promo").value) || null,
    puntos_fidelidad: parseInt(document.getElementById("edit-prod-points").value, 10) || 0,
    tiempo_preparacion: parseInt(document.getElementById("edit-prod-tiempo-preparacion").value, 10),
    categoria_id: parseInt(document.getElementById("edit-prod-cat-select").value),
    imagen_url: document.getElementById("edit-prod-img").value,
    ingredientes_json: JSON.stringify(ingsArr),
    extras_json: JSON.stringify(extras),
    media_json: JSON.stringify(media),
    alergenos: document.getElementById("edit-prod-alergenos").value.trim() || null,
    disponible: document.getElementById("edit-prod-disponible").checked
  };

  try {
    const res = await fetch(`/api/v1/admin/productos/${prodId}`, {
      method: "PUT",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const result = await res.json();
      throw new Error(result.detail || "Error al actualizar producto");
    }
    showToast("Producto e ingredientes actualizados con éxito", "success");
    closeModal("edit-product-modal");
    loadProducts();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

/* ==================== PROMOCIONES ADMIN ("BOOM! PROMO DEL DIA") ==================== */
async function loadPromosAdmin() {
  try {
    const res = await fetch("/api/v1/admin/promociones", { headers: Auth.getHeaders() });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "No se pudieron cargar las promociones.");
    }
    adminPromos = await res.json();
    renderPromosAdmin();
  } catch (err) {
    console.error("Error al cargar las promociones:", err);
    showToast(err.message || "No se pudieron cargar las promociones.", "danger");
  }
}

function renderPromosAdmin() {
  const tbody = document.getElementById("promos-tbody");
  if (!tbody) return;

  let html = "";
  adminPromos.forEach(p => {
    const rawImage = String(p.banner_url || "");
    const img = /^(https:\/\/|\/static\/)/i.test(rawImage) ? rawImage : "/static/img/logo.png";
    html += `
      <tr style="border-bottom: 1px solid var(--toon-border);">
        <td style="padding: 0.75rem;"><img src="${escapeAdminHtml(img)}" alt="${escapeAdminHtml(p.titulo)}" style="width: 60px; height: 40px; border-radius: 6px; object-fit: cover;"></td>
        <td style="padding: 0.75rem; font-weight: 800; color: #fff;">${escapeAdminHtml(p.titulo)}</td>
        <td style="padding: 0.75rem; color: var(--text-muted); font-size: 0.85rem;">${escapeAdminHtml(p.descripcion || "")}</td>
        <td style="padding: 0.75rem; font-weight: 900; color: var(--gold-accent);">${Number(p.descuento_pct) || 0}% OFF</td>
        <td style="padding: 0.75rem;"><span class="badge" style="background: var(--cyan-accent); color: #000; font-weight: 800;">${escapeAdminHtml(p.codigo_cupon || "Sin código")}</span></td>
        <td style="padding: 0.75rem; white-space:nowrap;">
          <span class="badge" style="background:${p.activo ? "var(--neon-green)" : "var(--text-muted)"};color:#000">${p.activo ? "Activa" : "Oculta"}</span>
          <button class="btn btn-outline" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="openEditPromo(${Number(p.id)})">✏️ Editar</button>
          <button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem; background: var(--neon-red); color: #fff;" onclick="deletePromo(${Number(p.id)})">🗑️ Eliminar</button>
        </td>
      </tr>
    `;
  });
  tbody.innerHTML = html || `<tr><td colspan="6" style="padding:1rem;text-align:center;color:var(--text-muted)">No hay promociones. Crea una para publicarla en ambos carruseles.</td></tr>`;
}

function openNewPromoModal() {
  editingPromoId = null;
  document.getElementById("promo-modal-title").textContent = "🔥 NUEVA PROMOCIÓN";
  document.getElementById("promo-submit-btn").textContent = "GUARDAR PROMOCIÓN";
  document.getElementById("promo-titulo").value = "";
  document.getElementById("promo-desc").value = "";
  document.getElementById("promo-pct").value = "0";
  document.getElementById("promo-codigo").value = "";
  document.getElementById("promo-img").value = "";
  document.getElementById("promo-activo").checked = true;
  openModal("promo-modal");
}

function openEditPromo(id) {
  const promo = adminPromos.find(item => Number(item.id) === Number(id));
  if (!promo) {
    showToast("No se encontró la promoción que deseas editar.", "danger");
    return;
  }
  editingPromoId = Number(promo.id);
  document.getElementById("promo-modal-title").textContent = `✏️ EDITAR PROMOCIÓN #${promo.id}`;
  document.getElementById("promo-submit-btn").textContent = "GUARDAR CAMBIOS";
  document.getElementById("promo-titulo").value = promo.titulo || "";
  document.getElementById("promo-desc").value = promo.descripcion || "";
  document.getElementById("promo-pct").value = String(Number(promo.descuento_pct) || 0);
  document.getElementById("promo-codigo").value = promo.codigo_cupon || "";
  document.getElementById("promo-img").value = promo.banner_url || "";
  document.getElementById("promo-activo").checked = Boolean(promo.activo);
  openModal("promo-modal");
}

async function submitCreatePromo() {
  const title = document.getElementById("promo-titulo").value.trim();
  const discount = Number(document.getElementById("promo-pct").value);
  if (!title || !Number.isFinite(discount) || discount < 0 || discount > 100) {
    showToast("Indica un título y un descuento válido entre 0 y 100%.", "warning");
    return;
  }
  const payload = {
    titulo: title,
    descripcion: document.getElementById("promo-desc").value.trim(),
    descuento_pct: discount,
    codigo_cupon: document.getElementById("promo-codigo").value.trim(),
    banner_url: document.getElementById("promo-img").value.trim(),
    activo: document.getElementById("promo-activo").checked
  };

  try {
    const isEditing = editingPromoId !== null;
    const endpoint = isEditing
      ? `/api/v1/admin/promociones/${editingPromoId}`
      : "/api/v1/admin/promociones";
    const res = await fetch(endpoint, {
      method: isEditing ? "PUT" : "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "Error al guardar promoción.");
    }
    editingPromoId = null;
    showToast("Promoción guardada y sincronizada en los carruseles Home y Landing.", "success");
    closeModal("promo-modal");
    await loadPromosAdmin();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function deletePromo(id) {
  if (!confirm("¿Eliminar esta promoción?")) return;
  try {
    const res = await fetch(`/api/v1/admin/promociones/${id}`, { method: "DELETE", headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("Error al eliminar");
    showToast("Promoción eliminada", "success");
    loadPromosAdmin();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

/* ==================== PORTAL CONFIGS & HISTORIA & TASA BS ==================== */
async function loadPortalConfigsAdmin() {
  try {
    const res = await fetch("/api/v1/cliente/configuraciones-publicas");
    if (res.ok) {
      const cfg = await res.json();
      const rate = Number(cfg.tasa_cambio_bs);
      tasaCambioBs = Number.isFinite(rate) && rate > 0 ? rate : null;
      if (document.getElementById("cfg-tasa-cambio")) {
        document.getElementById("cfg-tasa-cambio").value = tasaCambioBs === null ? "" : tasaCambioBs;
      }
      if (document.getElementById("cfg-nombre-restaurante")) document.getElementById("cfg-nombre-restaurante").value = cfg.nombre_restaurante || "DONDE DAVID | FAST FOOD";
      if (document.getElementById("cfg-direccion-restaurante")) document.getElementById("cfg-direccion-restaurante").value = cfg.direccion_restaurante || "";
      if (document.getElementById("cfg-landing-titulo")) document.getElementById("cfg-landing-titulo").value = cfg.landing_titulo || "";
      if (document.getElementById("cfg-landing-descripcion")) document.getElementById("cfg-landing-descripcion").value = cfg.landing_descripcion || "";
      if (document.getElementById("cfg-historia")) document.getElementById("cfg-historia").value = cfg.historia_restaurante || '';
      if (document.getElementById("cfg-footer-enlaces-titulo")) document.getElementById("cfg-footer-enlaces-titulo").value = cfg.footer_enlaces_titulo || "";
      if (document.getElementById("cfg-footer-inicio-texto")) document.getElementById("cfg-footer-inicio-texto").value = cfg.footer_inicio_texto || "";
      if (document.getElementById("cfg-footer-menu-texto")) document.getElementById("cfg-footer-menu-texto").value = cfg.footer_menu_texto || "";
      if (document.getElementById("cfg-footer-puntos-texto")) document.getElementById("cfg-footer-puntos-texto").value = cfg.footer_puntos_texto || "";
      if (document.getElementById("cfg-footer-atencion-titulo")) document.getElementById("cfg-footer-atencion-titulo").value = cfg.footer_atencion_titulo || "";
      if (document.getElementById("cfg-horario-atencion")) document.getElementById("cfg-horario-atencion").value = cfg.horario_atencion || "";
      if (document.getElementById("cfg-servicio-restaurante")) document.getElementById("cfg-servicio-restaurante").value = cfg.servicio_restaurante || "";
      if (document.getElementById("cfg-medios-pago-texto")) document.getElementById("cfg-medios-pago-texto").value = cfg.medios_pago_texto || "";
      if (document.getElementById("cfg-whatsapp")) document.getElementById("cfg-whatsapp").value = cfg.whatsapp_contacto || '';
      if (document.getElementById("cfg-instagram")) document.getElementById("cfg-instagram").value = cfg.instagram_link || '';
      if (document.getElementById("cfg-tiktok")) document.getElementById("cfg-tiktok").value = cfg.tiktok_link || '';
      if (document.getElementById("cfg-costo-delivery")) document.getElementById("cfg-costo-delivery").value = cfg.costo_delivery || '5.00';
      if (document.getElementById("cfg-costo-empaque")) document.getElementById("cfg-costo-empaque").value = cfg.costo_empaque || '3.00';
      if (document.getElementById("cfg-pm-banco")) document.getElementById("cfg-pm-banco").value = cfg.pago_movil_banco || '';
      if (document.getElementById("cfg-pm-telefono")) document.getElementById("cfg-pm-telefono").value = cfg.pago_movil_telefono || '';
      if (document.getElementById("cfg-pm-rif")) document.getElementById("cfg-pm-rif").value = cfg.pago_movil_rif || '';
      if (document.getElementById("cfg-pm-titular")) document.getElementById("cfg-pm-titular").value = cfg.pago_movil_titular || '';
      if (document.getElementById("cfg-google-maps-api-key")) document.getElementById("cfg-google-maps-api-key").value = cfg.google_maps_api_key || '';
      const rateStatus = document.getElementById("cfg-tasa-status");
      if (rateStatus) {
        rateStatus.textContent = cfg.tasa_cambio_bs
          ? `Origen: ${cfg.tasa_fuente || "no identificado"} · Actualizada: ${cfg.tasa_actualizada_at || "fecha no disponible"} · Estado: ${cfg.tasa_estado || "manual"}${cfg.tasa_respaldo === "true" ? " (respaldo)" : ""}`
          : "No hay una tasa válida. Consulta el feed o guarda un valor manual revisado.";
      }
    }
  } catch (err) {
    showToast(`No se pudo cargar la configuración: ${err.message}`, "danger");
  }
}

async function submitSavePortalConfigs() {
  const tasaVal = document.getElementById("cfg-tasa-cambio").value.trim();
  if (tasaVal && (!Number.isFinite(Number(tasaVal)) || Number(tasaVal) <= 0)) {
    showToast("La tasa debe ser un número mayor que cero.", "warning");
    return;
  }

  const items = [
    { clave: "nombre_restaurante", valor: document.getElementById("cfg-nombre-restaurante").value.trim() },
    { clave: "direccion_restaurante", valor: document.getElementById("cfg-direccion-restaurante").value.trim() },
    { clave: "landing_titulo", valor: document.getElementById("cfg-landing-titulo").value.trim() },
    { clave: "landing_descripcion", valor: document.getElementById("cfg-landing-descripcion").value.trim() },
    { clave: "historia_restaurante", valor: document.getElementById("cfg-historia").value },
    { clave: "footer_enlaces_titulo", valor: document.getElementById("cfg-footer-enlaces-titulo").value.trim() },
    { clave: "footer_inicio_texto", valor: document.getElementById("cfg-footer-inicio-texto").value.trim() },
    { clave: "footer_menu_texto", valor: document.getElementById("cfg-footer-menu-texto").value.trim() },
    { clave: "footer_puntos_texto", valor: document.getElementById("cfg-footer-puntos-texto").value.trim() },
    { clave: "footer_atencion_titulo", valor: document.getElementById("cfg-footer-atencion-titulo").value.trim() },
    { clave: "horario_atencion", valor: document.getElementById("cfg-horario-atencion").value.trim() },
    { clave: "servicio_restaurante", valor: document.getElementById("cfg-servicio-restaurante").value.trim() },
    { clave: "medios_pago_texto", valor: document.getElementById("cfg-medios-pago-texto").value.trim() },
    { clave: "whatsapp_contacto", valor: document.getElementById("cfg-whatsapp").value },
    { clave: "instagram_link", valor: document.getElementById("cfg-instagram").value },
    { clave: "tiktok_link", valor: document.getElementById("cfg-tiktok").value },
    { clave: "costo_delivery", valor: document.getElementById("cfg-costo-delivery").value },
    { clave: "costo_empaque", valor: document.getElementById("cfg-costo-empaque").value },
    { clave: "pago_movil_banco", valor: document.getElementById("cfg-pm-banco").value.trim() },
    { clave: "pago_movil_telefono", valor: document.getElementById("cfg-pm-telefono").value.trim() },
    { clave: "pago_movil_rif", valor: document.getElementById("cfg-pm-rif").value.trim() },
    { clave: "pago_movil_titular", valor: document.getElementById("cfg-pm-titular").value.trim() },
    { clave: "google_maps_api_key", valor: document.getElementById("cfg-google-maps-api-key").value.trim() }
  ];
  if (tasaVal) items.unshift({ clave: "tasa_cambio_bs", valor: tasaVal });

  try {
    const response = await fetch("/api/v1/admin/configuraciones/lote", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ configuraciones: items })
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "El servidor rechazó la configuración.");
    }
    if (tasaVal) {
      tasaCambioBs = Number(tasaVal);
      showToast(`Configuración guardada. Tasa manual: Bs. ${tasaCambioBs.toFixed(4)}/USD.`, "success");
    } else {
      showToast("Configuración guardada sin cambiar la tasa de referencia.", "success");
    }
    await loadPortalConfigsAdmin();
    loadProducts();
  } catch (err) {
    showToast(`No se guardaron los cambios: ${err.message}`, "danger");
  }
}

async function refreshBcvRate() {
  const status = document.getElementById("cfg-tasa-status");
  if (status) status.textContent = "Consultando proveedor de tasa oficial…";
  try {
    const response = await fetch("/api/v1/admin/tasa-bcv/actualizar", {
      method: "POST",
      headers: Auth.getHeaders()
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "No se pudo obtener la tasa.");
    }
    const data = await response.json();
    tasaCambioBs = Number(data.tasa_cambio_bs);
    document.getElementById("cfg-tasa-cambio").value = tasaCambioBs.toFixed(4);
    if (status) status.textContent = `Origen: ${data.tasa_fuente} · Actualizada: ${data.tasa_actualizada_at}`;
    showToast(`Tasa actualizada: Bs. ${tasaCambioBs.toFixed(4)}/USD`, "success");
    loadProducts();
  } catch (err) {
    await loadPortalConfigsAdmin();
    showToast(`No se actualizó la tasa; se conserva la última guardada. ${err.message}`, "warning");
  }
}

/* ==================== RESEÑAS ADMIN ==================== */
async function loadResenasAdmin() {
  try {
    const res = await fetch("/api/v1/admin/resenas", { headers: Auth.getHeaders() });
    if (res.ok) {
      adminResenas = await res.json();
      renderResenasAdmin();
    }
  } catch (err) {
    console.error(err);
  }
}

function renderResenasAdmin() {
  const tbody = document.getElementById("resenas-tbody");
  if (!tbody) return;

  let html = "";
  adminResenas.forEach(r => {
    html += `
      <tr style="border-bottom: 1px solid var(--toon-border);">
        <td style="padding: 0.75rem; font-weight: 700; color: #fff;">${r.nombre_cliente}</td>
        <td style="padding: 0.75rem; color: var(--gold-accent); font-size: 1.1rem;">${'⭐'.repeat(Math.min(5, Math.max(1, parseInt(r.estrellas) || 5)))}</td>
        <td style="padding: 0.75rem; color: var(--text-muted); font-size: 0.85rem;">"${r.comentario}"</td>
        <td style="padding: 0.75rem;"><button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem; background: var(--neon-red); color: #fff;" onclick="deleteResena(${r.id})">🗑️ Eliminar</button></td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

async function submitCreateResena() {
  const payload = {
    nombre_cliente: document.getElementById("res-nombre").value,
    comentario: document.getElementById("res-comentario").value,
    estrellas: parseInt(document.getElementById("res-estrellas").value) || 5
  };

  try {
    const res = await fetch("/api/v1/admin/resenas", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Error al guardar reseña");
    showToast("Reseña publicada en el portal web", "success");
    closeModal("resena-modal");
    loadResenasAdmin();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function deleteResena(id) {
  if (!confirm("¿Eliminar esta reseña?")) return;
  try {
    const res = await fetch(`/api/v1/admin/resenas/${id}`, { method: "DELETE", headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("Error al eliminar");
    showToast("Reseña eliminada", "success");
    loadResenasAdmin();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

/* ==================== GUÍA & CARRUSEL ADMIN ==================== */
async function loadGuiaAdmin() {
  try {
    const res = await fetch("/api/v1/admin/guia", { headers: Auth.getHeaders() });
    if (res.ok) {
      adminGuiaItems = await res.json();
      renderGuiaAdmin();
    }
  } catch (err) {
    console.error(err);
  }
}

function renderGuiaAdmin() {
  const tbody = document.getElementById("guia-tbody");
  if (!tbody) return;

  if (adminGuiaItems.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No hay diapositivas en la guía. Agrega una nueva.</td></tr>`;
    return;
  }

  let html = "";
  adminGuiaItems.forEach(g => {
    const isVideo = g.tipo_media === "video" || g.media_url.endsWith(".mp4");
    const mediaPreview = isVideo ? `<video src="${g.media_url}" style="width: 60px; height: 44px; border-radius: 6px; object-fit: cover;" autoplay muted loop></video>` : `<img src="${g.media_url}" style="width: 60px; height: 44px; border-radius: 6px; object-fit: cover;">`;

    html += `
      <tr style="border-bottom: 1px solid var(--toon-border);">
        <td style="padding: 0.75rem;">${mediaPreview}</td>
        <td style="padding: 0.75rem; font-weight: 700; color: #fff;">${g.titulo}</td>
        <td style="padding: 0.75rem; color: var(--text-muted); font-size: 0.85rem;">${g.descripcion || ''}</td>
        <td style="padding: 0.75rem;"><span class="badge" style="background: var(--gold-accent); color: #000; font-size: 0.75rem; font-weight: 800;">${g.tipo_vista}</span></td>
        <td style="padding: 0.75rem;"><button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem; background: var(--neon-red); color: #fff;" onclick="deleteGuiaItem(${g.id})">🗑️ Eliminar</button></td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

async function submitCreateGuia() {
  const payload = {
    titulo: document.getElementById("guia-titulo").value,
    descripcion: document.getElementById("guia-desc").value,
    media_url: document.getElementById("guia-media-url").value,
    tipo_media: document.getElementById("guia-tipo-media").value,
    tipo_vista: document.getElementById("guia-tipo-vista").value,
    orden: adminGuiaItems.length + 1
  };

  if (!payload.titulo || !payload.media_url) {
    showToast("Completa los campos obligatorios", "warning");
    return;
  }

  try {
    const res = await fetch("/api/v1/admin/guia", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Error al guardar diapositiva");
    showToast("Diapositiva agregada al carrusel con éxito", "success");
    closeModal("add-guia-modal");
    loadGuiaAdmin();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function deleteGuiaItem(id) {
  if (!confirm("¿Deseas eliminar esta diapositiva del carrusel guía?")) return;
  try {
    const res = await fetch(`/api/v1/admin/guia/${id}`, { method: "DELETE", headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("Error al eliminar");
    showToast("Diapositiva eliminada del carrusel", "success");
    loadGuiaAdmin();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function loadMesas() {
  try {
    const res = await fetch("/api/v1/admin/mesas", { headers: Auth.getHeaders() });
    if (res.ok) {
      adminMesas = await res.json();
      renderMesas();
    }
  } catch (err) {
    console.error(err);
  }
}

function renderMesas() {
  const container = document.getElementById("admin-mesas-grid");
  let html = "";
  adminMesas.forEach(m => {
    html += `
      <div class="mesa-card ${m.estado}">
        <div style="font-size: 1.2rem; font-weight: 900; color: #fff;">Mesa #${m.numero_mesa}</div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin: 0.3rem 0;">Estado: ${m.estado}</div>
        <div style="display: flex; gap: 0.4rem; justify-content: center; margin-top: 0.75rem;">
          <button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.7rem;" onclick="viewQrMesa(${m.numero_mesa})">📱 QR</button>
          <button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.7rem; background: var(--neon-red); color: #fff;" onclick="deleteMesa(${m.numero_mesa})">🗑️</button>
        </div>
      </div>
    `;
  });
  container.innerHTML = html;
}

async function viewQrMesa(numMesa) {
  try {
    const res = await fetch(`/api/v1/admin/mesas/${numMesa}/qr`, { headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("Error al obtener QR");
    const data = await res.json();
    document.getElementById("qr-modal-title").innerText = `CÓDIGO QR MESA #${data.numero_mesa}`;
    document.getElementById("qr-modal-img").src = data.qr_image_url;
    document.getElementById("qr-modal-url").innerText = data.url_acceso;
    openModal("qr-modal");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function submitCreateMesa() {
  const num = parseInt(document.getElementById("new-mesa-num").value);
  const cap = parseInt(document.getElementById("new-mesa-cap").value) || 4;

  if (!num) {
    showToast("Ingresa un número de mesa válido", "warning");
    return;
  }

  try {
    const res = await fetch("/api/v1/admin/mesas", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ numero_mesa: num, capacidad: cap })
    });
    if (!res.ok) throw new Error("Error al crear mesa");
    showToast(`Mesa #${num} creada exitosamente`, "success");
    closeModal("add-mesa-modal");
    loadMesas();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function deleteMesa(numMesa) {
  if (!confirm(`¿Eliminar la Mesa #${numMesa}?`)) return;
  try {
    const res = await fetch(`/api/v1/admin/mesas/${numMesa}`, { method: "DELETE", headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("Error al eliminar la mesa");
    showToast(`Mesa #${numMesa} eliminada`, "success");
    loadMesas();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function loadInsumos() {
  try {
    const res = await fetch("/api/v1/admin/insumos", { headers: Auth.getHeaders() });
    if (res.ok) {
      adminInsumos = await res.json();
      renderInsumos();
    }
  } catch (err) {
    console.error(err);
  }
}

function renderInsumos() {
  const tbody = document.getElementById("insumos-tbody");
  let html = "";
  adminInsumos.forEach(i => {
    const isCrit = i.estado === "CRITICO";
    html += `
      <tr style="border-bottom: 1px solid var(--toon-border);">
        <td style="padding: 0.75rem; font-weight: 700; color: #fff;">${i.nombre}</td>
        <td style="padding: 0.75rem; font-size: 1.1rem; font-weight: 900; color: ${isCrit ? 'var(--neon-red)' : 'var(--neon-green)'};">${i.stock_actual} ${i.unidad_medida}</td>
        <td style="padding: 0.75rem; color: var(--text-muted);">${i.stock_minimo} ${i.unidad_medida}</td>
        <td style="padding: 0.75rem;">${i.unidad_medida}</td>
        <td style="padding: 0.75rem;"><span class="badge" style="background: ${isCrit ? 'var(--neon-red)' : 'var(--neon-green)'}; color: #fff; padding: 0.2rem 0.5rem; border-radius: 6px;">${i.estado}</span></td>
        <td style="padding: 0.75rem;"><button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="openIngresoInsumoModal(${i.id})">📥 Ingreso Stock</button></td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

function openIngresoInsumoModal(insumoId) {
  selectedInsumoForIngreso = adminInsumos.find(i => i.id === insumoId);
  if (!selectedInsumoForIngreso) return;

  document.getElementById("ingreso-insumo-title").innerText = `Insumo: ${selectedInsumoForIngreso.nombre} (Stock Actual: ${selectedInsumoForIngreso.stock_actual} ${selectedInsumoForIngreso.unidad_medida})`;
  document.getElementById("ingreso-cant-input").value = "";
  openModal("ingreso-insumo-modal");
}

async function submitIngresoInsumo() {
  if (!selectedInsumoForIngreso) return;
  const cant = parseFloat(document.getElementById("ingreso-cant-input").value);
  if (!cant || cant <= 0) {
    showToast("Ingresa una cantidad mayor a 0", "warning");
    return;
  }

  try {
    const res = await fetch(`/api/v1/admin/insumos/${selectedInsumoForIngreso.id}/ingreso`, {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ cantidad: cant })
    });
    if (!res.ok) throw new Error("Error al ingresar stock");
    showToast(`+${cant} ${selectedInsumoForIngreso.unidad_medida} añadidos a ${selectedInsumoForIngreso.nombre}`, "success");
    closeModal("ingreso-insumo-modal");
    loadInsumos();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function submitCreateInsumo() {
  const payload = {
    nombre: document.getElementById("ins-nombre").value,
    stock_actual: parseFloat(document.getElementById("ins-stock").value) || 0.0,
    stock_minimo: parseFloat(document.getElementById("ins-min").value) || 5.0,
    unidad_medida: document.getElementById("ins-unidad").value || "kg"
  };

  try {
    const res = await fetch("/api/v1/admin/insumos", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Error al crear insumo");
    showToast("Insumo registrado correctamente", "success");
    closeModal("add-insumo-modal");
    loadInsumos();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function openProductModal() {
  const select = document.getElementById("prod-cat-select");
  let opts = "";
  adminCategories.forEach(c => {
    opts += `<option value="${c.id}">${c.nombre}</option>`;
  });
  select.innerHTML = opts;
  document.getElementById("prod-extras").value = "";
  document.getElementById("prod-media").value = "";
  document.getElementById("prod-points").value = "0";
  openModal("product-modal");
}

async function submitCreateProduct() {
  const ingsInput = document.getElementById("prod-ingredientes").value;
  let ingsArr = ingsInput.split(",").map(i => i.trim()).filter(i => i.length > 0);
  let extras;
  let media;
  try {
    extras = parseProductEditorList(document.getElementById("prod-extras").value, "extras");
    media = parseProductEditorList(document.getElementById("prod-media").value, "media");
  } catch (error) {
    showToast(error.message, "warning");
    return;
  }

  const payload = {
    nombre: document.getElementById("prod-name").value,
    categoria_id: parseInt(document.getElementById("prod-cat-select").value),
    descripcion: document.getElementById("prod-desc").value,
    precio: parseFloat(document.getElementById("prod-price").value),
    puntos_fidelidad: parseInt(document.getElementById("prod-points").value, 10) || 0,
    tiempo_preparacion: parseInt(document.getElementById("prod-tiempo-preparacion").value, 10),
    imagen_url: document.getElementById("prod-img").value || "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500",
    ingredientes_json: JSON.stringify(ingsArr),
    extras_json: JSON.stringify(extras),
    media_json: JSON.stringify(media),
    alergenos: document.getElementById("prod-alergenos").value.trim() || null,
    disponible: document.getElementById("prod-disponible").checked
  };

  try {
    const res = await fetch("/api/v1/admin/productos", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const result = await res.json();
      throw new Error(result.detail || "Error al crear producto");
    }
    showToast("Producto guardado correctamente en el catálogo", "success");
    closeModal("product-modal");
    loadProducts();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function deleteProducto(id) {
  if (!confirm("¿Eliminar este producto del catálogo?")) return;
  try {
    const res = await fetch(`/api/v1/admin/productos/${id}`, { method: "DELETE", headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("Error al eliminar producto");
    showToast("Producto eliminado", "success");
    loadProducts();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function loadCategories() {
  try {
    const res = await fetch("/api/v1/admin/categorias", { headers: Auth.getHeaders() });
    if (res.ok) {
      adminCategories = await res.json();
      renderCategories();
      renderProducts();
    }
  } catch (err) {
    console.error(err);
  }
}

function renderCategories() {
  const tbody = document.getElementById("categories-tbody");
  let html = "";
  adminCategories.forEach(c => {
    const img = c.imagen_url || "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500";
    html += `
      <tr style="border-bottom: 1px solid var(--toon-border);">
        <td style="padding: 0.75rem;"><img src="${img}" style="width: 44px; height: 44px; border-radius: 8px; object-fit: cover;"></td>
        <td style="padding: 0.75rem; font-weight: 700; color: #fff;">${c.nombre}</td>
        <td style="padding: 0.75rem; color: var(--text-muted);">${c.descripcion || ''}</td>
        <td style="padding: 0.75rem;"><button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem; background: var(--neon-red); color: #fff;" onclick="deleteCategoria(${c.id})">🗑️ Eliminar</button></td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

async function submitCreateCategory() {
  const payload = {
    nombre: document.getElementById("cat-name").value,
    descripcion: document.getElementById("cat-desc").value,
    imagen_url: document.getElementById("cat-img").value || "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500"
  };

  try {
    const res = await fetch("/api/v1/admin/categorias", {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Error al crear categoría");
    showToast("Categoría guardada correctamente en el servidor", "success");
    closeModal("category-modal");
    loadCategories();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function deleteCategoria(id) {
  if (!confirm("¿Eliminar esta categoría?")) return;
  try {
    const res = await fetch(`/api/v1/admin/categorias/${id}`, { method: "DELETE", headers: Auth.getHeaders() });
    if (!res.ok) throw new Error("Error al eliminar categoría");
    showToast("Categoría eliminada", "success");
    loadCategories();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

let currentLoadedUsers = [];
let activeUserTypeFilter = 'all';

function filterUsersType(type) {
  activeUserTypeFilter = type;
  renderUsers(currentLoadedUsers);
}

async function loadUsers() {
  try {
    const res = await fetch("/api/v1/admin/usuarios", { headers: Auth.getHeaders() });
    if (res.ok) {
      currentLoadedUsers = await res.json();
      renderUsers(currentLoadedUsers);
    }
  } catch (err) {
    console.error(err);
  }
}

function renderUsers(users) {
  const tbody = document.getElementById("users-tbody");
  if (!tbody) return;

  let filtered = users;
  if (activeUserTypeFilter === 'staff') {
    filtered = users.filter(u => u.rol !== 'cliente');
  } else if (activeUserTypeFilter === 'cliente') {
    filtered = users.filter(u => u.rol === 'cliente');
  }

  let html = "";
  filtered.forEach(u => {
    const roleBadges = {
      'admin': '<span class="badge" style="background: var(--neon-red); color: #fff; font-weight: 800; padding: 0.2rem 0.5rem; border-radius: 6px;">👑 Admin</span>',
      'gerente': '<span class="badge" style="background: #6366f1; color: #fff; font-weight: 800; padding: 0.2rem 0.5rem; border-radius: 6px;">📊 Gerente · lectura</span>',
      'caja': '<span class="badge" style="background: #38bdf8; color: #000; font-weight: 800; padding: 0.2rem 0.5rem; border-radius: 6px;">💵 Caja</span>',
      'cocina': '<span class="badge" style="background: var(--gold-accent); color: #000; font-weight: 800; padding: 0.2rem 0.5rem; border-radius: 6px;">🍳 Cocina</span>',
      'mesero': '<span class="badge" style="background: #a855f7; color: #fff; font-weight: 800; padding: 0.2rem 0.5rem; border-radius: 6px;">🤵 Mesero</span>',
      'repartidor': '<span class="badge" style="background: #0ea5e9; color: #fff; font-weight: 800; padding: 0.2rem 0.5rem; border-radius: 6px;">🛵 Repartidor</span>',
      'cliente': '<span class="badge" style="background: rgba(255,255,255,0.1); color: #fff; font-weight: 800; padding: 0.2rem 0.5rem; border-radius: 6px;">📱 Cliente</span>'
    };
    const roleBadge = roleBadges[u.rol] || `<span class="badge">${u.rol}</span>`;

    html += `
      <tr style="border-bottom: 1px solid var(--toon-border);">
        <td style="padding: 0.75rem; font-weight: 700; color: #fff;">${u.nombre} ${u.apellido}</td>
        <td style="padding: 0.75rem;"><code>${u.nombre_usuario}</code></td>
        <td style="padding: 0.75rem; color: var(--text-muted);">${u.email}</td>
        <td style="padding: 0.75rem;">${u.telefono || '-'}</td>
        <td style="padding: 0.75rem;">${roleBadge}</td>
        <td style="padding: 0.75rem;">${u.activo ? '<span style="color: var(--neon-green); font-weight: 800;">🟢 Activo</span>' : '<span style="color: var(--neon-red); font-weight: 800;">🔴 Inactivo</span>'}</td>
        <td style="padding: 0.75rem; display: flex; gap: 0.4rem;">
          <button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="openEditUserModal(${u.id})">✏️ Editar</button>
          <button class="btn-gold" style="padding: 0.3rem 0.6rem; font-size: 0.75rem; background: ${u.activo ? 'var(--neon-red)' : 'var(--neon-green)'}; color: #fff;" onclick="toggleUserActive(${u.id}, ${!u.activo})">
            ${u.activo ? '🚫 Desactivar' : '✅ Activar'}
          </button>
        </td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

function openCreateUserModal() {
  document.getElementById("user-modal-title").innerText = "👤 CREAR NUEVO USUARIO / PERSONAL";
  document.getElementById("user-edit-id").value = "";
  document.getElementById("user-nombre").value = "";
  document.getElementById("user-apellido").value = "";
  document.getElementById("user-username").value = "";
  document.getElementById("user-username").disabled = false;
  document.getElementById("user-email").value = "";
  document.getElementById("user-telefono").value = "";
  document.getElementById("user-rol").value = "mesero";
  document.getElementById("user-password").value = "";
  document.getElementById("user-pwd-label").innerText = "Contraseña";
  document.getElementById("user-password").required = true;
  openModal("user-modal");
}

function openEditUserModal(userId) {
  const u = currentLoadedUsers.find(x => x.id === userId);
  if (!u) return;
  document.getElementById("user-modal-title").innerText = `✏️ EDITAR USUARIO #${u.id} (${u.nombre_usuario})`;
  document.getElementById("user-edit-id").value = u.id;
  document.getElementById("user-nombre").value = u.nombre || "";
  document.getElementById("user-apellido").value = u.apellido || "";
  document.getElementById("user-username").value = u.nombre_usuario || "";
  document.getElementById("user-username").disabled = true;
  document.getElementById("user-email").value = u.email || "";
  document.getElementById("user-telefono").value = u.telefono || "";
  document.getElementById("user-rol").value = u.rol || "mesero";
  document.getElementById("user-password").value = "";
  document.getElementById("user-pwd-label").innerText = "Nueva Contraseña (dejar en blanco para conservar actual)";
  document.getElementById("user-password").required = false;
  openModal("user-modal");
}

async function submitUserForm() {
  const editId = document.getElementById("user-edit-id").value;
  const isEdit = !!editId;

  const payload = {
    nombre: document.getElementById("user-nombre").value,
    apellido: document.getElementById("user-apellido").value,
    email: document.getElementById("user-email").value,
    telefono: document.getElementById("user-telefono").value,
    nombre_usuario: document.getElementById("user-username").value,
    rol: document.getElementById("user-rol").value
  };

  const pwd = document.getElementById("user-password").value;
  if (pwd && pwd.trim()) {
    payload.password = pwd.trim();
  }

  if (!isEdit && (!pwd || !pwd.trim())) {
    showToast("Por favor ingresa una contraseña para el usuario", "warning");
    return;
  }

  try {
    const url = isEdit ? `/api/v1/admin/usuarios/${editId}` : "/api/v1/admin/usuarios";
    const method = isEdit ? "PUT" : "POST";
    const res = await fetch(url, {
      method: method,
      headers: Auth.getHeaders(),
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Error al guardar usuario");
    }

    showToast(isEdit ? "Usuario actualizado correctamente" : "Usuario creado con éxito", "success");
    closeModal("user-modal");
    loadUsers();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function toggleUserActive(userId, newActive) {
  try {
    const res = await fetch(`/api/v1/admin/usuarios/${userId}`, {
      method: "PUT",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ activo: newActive })
    });
    if (!res.ok) throw new Error("Error al cambiar estado del usuario");
    showToast(`Usuario ${newActive ? 'activado' : 'desactivado'} con éxito`, "info");
    loadUsers();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

/* ==================== NAVEGACIÓN TÁCTIL Y FILTROS ==================== */
let touchStartX = 0;
let touchEndX = 0;

document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("admin-main-container");
  if (container) {
    container.addEventListener("touchstart", e => {
      touchStartX = e.changedTouches[0].screenX;
    }, false);

    container.addEventListener("touchend", e => {
      touchEndX = e.changedTouches[0].screenX;
      handleAdminSwipe();
    }, false);
  }
});

function handleAdminSwipe() {
  const diff = touchEndX - touchStartX;
  const tabs = ["dashboard", "productos", "inventario", "promociones", "publicaciones", "portal", "mesas", "categorias", "usuarios"];
  const activeBtn = document.querySelector(".admin-sidebar-btn.active");
  if (!activeBtn) return;
  
  const onclickAttr = activeBtn.getAttribute("onclick");
  if (!onclickAttr) return;
  
  const match = onclickAttr.match(/'([^']+)'/);
  if (!match) return;
  
  const currentTab = match[1];
  let idx = tabs.indexOf(currentTab);
  
  if (diff < -80 && idx < tabs.length - 1) {
    switchTab(tabs[idx + 1]);
  } else if (diff > 80 && idx > 0) {
    switchTab(tabs[idx - 1]);
  }
}

function applyAdminMetricFilters() {
  const cat = document.getElementById("filter-metrics-category")?.value || "todas";
  const pay = document.getElementById("filter-metrics-payment")?.value || "todos";
  showToast(`📊 Filtro aplicado: Categoría [${cat.toUpperCase()}], Pago [${pay.toUpperCase()}]`, "info");
  loadDashboardStats();
}

async function openRealtimeOpsModal() {
  openModal("realtime-ops-modal");
  
  if (document.getElementById("modal-ops-mesas")) {
    document.getElementById("modal-ops-mesas").innerText = `${adminStats?.mesas_ocupadas || 0} / ${adminStats?.total_mesas || 0} Mesas`;
  }
  if (document.getElementById("modal-ops-caja")) {
    document.getElementById("modal-ops-caja").innerText = `$${Number(adminStats?.monto_caja || 0).toFixed(2)}`;
  }

  const container = document.getElementById("modal-ops-orders-list");
  if (!container) return;

  try {
    const res = await fetch("/api/v1/cocina/pedidos", { headers: Auth.getHeaders() });
    if (res.ok) {
      const orders = await res.json();
      if (!orders || orders.length === 0) {
        container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 1rem;">No hay comandas activas en este momento.</div>`;
        return;
      }

      let html = "";
      orders.forEach(o => {
        const createdAt = new Date(o.fecha_creacion).getTime();
        const elapsedMin = Number.isFinite(createdAt) ? Math.max(0, Math.floor((Date.now() - createdAt) / 60000)) : 0;
        const isUrgent = elapsedMin >= 15;

        html += `
          <div style="background: rgba(255,255,255,0.04); border: 1px solid ${isUrgent ? 'var(--neon-red)' : 'var(--toon-border)'}; border-radius: 8px; padding: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <strong style="color: #fff; font-size: 0.95rem;">Comanda #${o.id} - ${o.numero_mesa}</strong>
              <div style="font-size: 0.78rem; color: var(--text-muted);">Estado: <strong style="color: var(--cyan-accent);">${o.estado}</strong></div>
            </div>
            <div style="text-align: right;">
              <span class="badge" style="background: ${isUrgent ? 'var(--neon-red)' : 'rgba(255,255,255,0.1)'}; color: #fff; font-size: 0.75rem;">⏱️ ${elapsedMin} min</span>
            </div>
          </div>
        `;
      });
      container.innerHTML = html;
    }
  } catch(e) {
    console.error("No se pudieron cargar las operaciones actuales:", e);
    container.innerHTML = `<div role="alert" style="text-align: center; color: var(--neon-red); padding: 1rem;">No se pudieron cargar las operaciones. Intenta actualizar el panel.</div>`;
  }
}
