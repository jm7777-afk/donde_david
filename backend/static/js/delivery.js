function escapeDeliveryText(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function getDeliveryStage(status) {
  if (status === "EN_CAMINO") return 3;
  if (status === "RECOGIDO") return 2;
  if (status === "ASIGNADO") return 1;
  return 0;
}

let courierLocationWatchId = null;
let courierLocationOrderId = null;
let lastCourierPositionSentAt = 0;
let courierLocationWarningShown = false;

document.addEventListener("DOMContentLoaded", () => {
  if (!Auth.requireRole("repartidor")) return;
  loadCourierOrders();
  new WSClient((event) => {
    if (event === "DELIVERY_ACTUALIZADO" || event === "CAMBIO_ESTADO_PEDIDO") loadCourierOrders();
  });
});

async function loadCourierOrders() {
  const container = document.getElementById("courier-orders");
  container.innerHTML = '<div class="delivery-empty">Cargando tus pedidos…</div>';
  try {
    const response = await fetch("/api/v1/delivery/mis-pedidos", { headers: Auth.getHeaders() });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "No se pudieron cargar los pedidos.");
    }
    const orders = await response.json();
    const activeRoute = orders.find(order => order.estado_delivery === "EN_CAMINO");
    if (activeRoute) {
      startCourierLocationSharing(activeRoute.id);
    } else {
      stopCourierLocationSharing();
    }
    const assigned = orders.filter(order => order.estado_delivery === "ASIGNADO").length;
    const route = orders.filter(order => ["RECOGIDO", "EN_CAMINO"].includes(order.estado_delivery)).length;
    const open = orders.filter(order => order.estado_delivery !== "ENTREGADO").length;
    document.getElementById("courier-count-assigned").textContent = String(assigned);
    document.getElementById("courier-count-route").textContent = String(route);
    document.getElementById("courier-count-open").textContent = String(open);
    if (!orders.length) {
      container.innerHTML = '<div class="delivery-empty">No tienes entregas asignadas.</div>';
      return;
    }
    container.innerHTML = orders.map(order => {
      let lat = Number.isFinite(Number(order.delivery_lat)) ? Number(order.delivery_lat) : null;
      let lng = Number.isFinite(Number(order.delivery_lng)) ? Number(order.delivery_lng) : null;
      if ((lat === null || lng === null) && order.direccion_delivery) {
        const coordMatch = String(order.direccion_delivery).match(/(-?\d{1,3}\.\d{3,})\s*,\s*(-?\d{1,3}\.\d{3,})/);
        if (coordMatch) {
          lat = parseFloat(coordMatch[1]);
          lng = parseFloat(coordMatch[2]);
        }
      }
      const hasCoords = lat !== null && lng !== null && Number.isFinite(lat) && Number.isFinite(lng);
      const cleanAddr = String(order.direccion_delivery || "")
        .replace(/📍|🌐|✅|GPS:?|Lat:?|Lng:?|\(https?:\/\/[^)]+\)/gi, "")
        .trim();
      const mapsUrl = hasCoords
        ? `https://www.google.com/maps?q=${lat},${lng}`
        : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(cleanAddr || "Valencia")}`;
      const dirUrl = hasCoords
        ? `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`
        : mapsUrl;
      const elapsedMinutes = order.fecha_creacion
        ? Math.max(0, Math.floor((Date.now() - new Date(order.fecha_creacion).getTime()) / 60000))
        : null;
      const canPickup = order.estado_delivery === "ASIGNADO" && order.estado === "LISTO";
      const canStartRoute = order.estado_delivery === "RECOGIDO";
      const canDeliver = order.estado_delivery === "EN_CAMINO";
      const currentStage = getDeliveryStage(order.estado_delivery);
      const details = (order.detalles || []).map(item => {
        let extras = [];
        try {
          const personalizations = JSON.parse(item.personalizaciones || "{}");
          extras = Array.isArray(personalizations.extras) ? personalizations.extras : [];
        } catch (error) {
          console.error(`Personalizaciones inválidas para el detalle ${item.id}.`, error);
        }
        return `<li><strong>${escapeDeliveryText(item.cantidad)} × ${escapeDeliveryText(item.producto?.nombre || "Producto")}</strong>${extras.length ? `<small style="display:block;color:var(--text-muted)">Extras: ${extras.map(escapeDeliveryText).join(", ")}</small>` : ""}</li>`;
      }).join("");
      return `<article class="delivery-card">
        <div style="display:flex; justify-content:space-between; gap:.75rem; align-items:center">
          <h2 style="margin:0">Pedido #${escapeDeliveryText(order.id)}</h2>
          <strong class="delivery-state">${escapeDeliveryText(order.estado_delivery || "PENDIENTE")}</strong>
        </div>
        <div class="delivery-progress" role="img" aria-label="Progreso de entrega">
          ${[1, 2, 3].map(stage => `<span class="${currentStage >= stage ? "active" : ""}"></span>`).join("")}
        </div>
        ${elapsedMinutes !== null ? `<p><strong>Tiempo transcurrido:</strong> ${elapsedMinutes} min · sin estimación de traslado en tiempo real</p>` : ""}
        <p><strong>Cliente:</strong> ${escapeDeliveryText(order.nombre_cliente_delivery || "Cliente")}</p>
        <p><strong>Teléfono:</strong> ${order.telefono_delivery ? `<a href="tel:${escapeDeliveryText(order.telefono_delivery)}">${escapeDeliveryText(order.telefono_delivery)}</a>` : "No indicado"}</p>
        <p><strong>Dirección:</strong> ${escapeDeliveryText(order.direccion_delivery || "Sin dirección")}</p>
        ${(hasCoords || cleanAddr) ? `
          <div style="display:flex;gap:0.4rem;flex-wrap:wrap;margin:0.5rem 0;">
            <a class="btn btn-outline" href="${mapsUrl}" target="_blank" rel="noopener noreferrer">📍 Ver punto en Google Maps</a>
            <a class="btn btn-cta" href="${dirUrl}" target="_blank" rel="noopener noreferrer">🧭 Iniciar navegación GPS</a>
          </div>
        ` : '<p role="status" style="color:var(--neon-red)">Falta la dirección de entrega.</p>'}
        <ul>${details}</ul>
        <div class="delivery-actions">
          ${canPickup ? `<button class="btn btn-cta" onclick="updateCourierStatus(${order.id}, 'RECOGIDO')">Confirmar recogida</button>` : ""}
          ${canStartRoute ? `<button class="btn btn-cta" onclick="updateCourierStatus(${order.id}, 'EN_CAMINO')">Iniciar entrega</button>` : ""}
          ${canDeliver ? `<label style="flex-basis:100%">Código de entrega del cliente
            <input id="delivery-otp-${order.id}" class="form-control" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" placeholder="6 dígitos">
          </label><button class="btn btn-cta" onclick="confirmCourierDelivery(${order.id})">Confirmar entrega</button>` : ""}
        </div>
      </article>`;
    }).join("");
  } catch (error) {
    container.innerHTML = `<div class="delivery-empty" role="alert">${escapeDeliveryText(error.message)}</div>`;
  }
}

function stopCourierLocationSharing() {
  if (courierLocationWatchId !== null && navigator.geolocation) {
    navigator.geolocation.clearWatch(courierLocationWatchId);
  }
  courierLocationWatchId = null;
  courierLocationOrderId = null;
  const status = document.getElementById("courier-location-status");
  if (status) status.textContent = "La ubicación en vivo se activa al iniciar una entrega.";
}

function startCourierLocationSharing(orderId) {
  if (courierLocationWatchId !== null && courierLocationOrderId === orderId) return;
  stopCourierLocationSharing();
  const status = document.getElementById("courier-location-status");
  if (!navigator.geolocation) {
    if (status) status.textContent = "Este dispositivo no permite compartir ubicación. Mantén actualizada la dirección del cliente.";
    return;
  }

  courierLocationOrderId = orderId;
  courierLocationWarningShown = false;
  if (status) status.textContent = "Solicitando ubicación del dispositivo para compartirla durante esta entrega…";
  courierLocationWatchId = navigator.geolocation.watchPosition(async position => {
    const now = Date.now();
    if (now - lastCourierPositionSentAt < 10000) return;
    lastCourierPositionSentAt = now;
    try {
      const response = await fetch(`/api/v1/delivery/pedidos/${orderId}/ubicacion`, {
        method: "POST",
        headers: Auth.getHeaders(),
        body: JSON.stringify({
          lat: position.coords.latitude,
          lng: position.coords.longitude
        })
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "No se pudo actualizar la ubicación.");
      }
      if (status) status.textContent = "🟢 Compartiendo tu ubicación con el cliente cada pocos segundos.";
    } catch (error) {
      console.error("No se pudo compartir la ubicación del repartidor:", error);
      if (!courierLocationWarningShown) {
        showToast(error.message, "warning");
        courierLocationWarningShown = true;
      }
    }
  }, error => {
    console.warn("El navegador no pudo obtener la ubicación del repartidor:", error.message);
    if (!courierLocationWarningShown) {
      showToast("Activa el GPS y permite la ubicación para que el cliente pueda seguir la entrega.", "warning");
      courierLocationWarningShown = true;
    }
    if (status) status.textContent = "Ubicación no disponible. Revisa el permiso de GPS del navegador.";
  }, {
    enableHighAccuracy: true,
    maximumAge: 5000,
    timeout: 15000
  });
}

window.addEventListener("beforeunload", stopCourierLocationSharing);

async function updateCourierStatus(orderId, estado) {
  try {
    const response = await fetch(`/api/v1/delivery/pedidos/${orderId}/estado`, {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ estado })
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "No se pudo actualizar el pedido.");
    }
    showToast(estado === "RECOGIDO" ? "Pedido recogido." : "Ruta iniciada.", "success");
    await loadCourierOrders();
  } catch (error) {
    showToast(error.message, "danger");
  }
}

async function confirmCourierDelivery(orderId) {
  const codeInput = document.getElementById(`delivery-otp-${orderId}`);
  const code = codeInput?.value.trim() || "";
  if (!/^\d{6}$/.test(code)) {
    showToast("El código de entrega debe tener 6 dígitos.", "warning");
    return;
  }
  try {
    const response = await fetch(`/api/v1/delivery/pedidos/${orderId}/entregar`, {
      method: "POST",
      headers: Auth.getHeaders(),
      body: JSON.stringify({ codigo_otp: code })
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "No se pudo confirmar la entrega.");
    }
    showToast(`Pedido #${orderId} entregado.`, "success");
    await loadCourierOrders();
  } catch (error) {
    showToast(error.message, "danger");
  }
}
