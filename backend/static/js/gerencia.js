if (!Auth.requireRole("gerente")) {
  // Redirigido a /login por falta de privilegios
} else {
  loadManagerDashboard();
  window.setInterval(loadManagerDashboard, 60000);
}

async function loadManagerDashboard() {
  const error = document.getElementById("manager-error");
  error.hidden = true;
  try {
    const response = await fetch("/api/v1/gerencia/dashboard", { headers: Auth.getHeaders() });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.detail || "No se pudo cargar el panel de gerencia.");
    }
    const dashboard = await response.json();
    const values = {
      "manager-sales-today": `$${Number(dashboard.ventas_hoy).toFixed(2)}`,
      "manager-sales-yesterday": `$${Number(dashboard.ventas_ayer).toFixed(2)}`,
      "manager-kitchen-orders": dashboard.pedidos_cocina,
      "manager-overdue-orders": dashboard.pedidos_atrasados,
      "manager-deliveries": dashboard.delivery_activos,
      "manager-tables": dashboard.mesas_ocupadas,
      "manager-critical-inputs": dashboard.insumos_criticos,
      "manager-unavailable-products": dashboard.productos_no_disponibles,
      "manager-shift": dashboard.turno_activo
        ? `#${dashboard.turno_activo.numero} · $${Number(dashboard.turno_activo.ventas).toFixed(2)}`
        : "Sin turno",
    };
    Object.entries(values).forEach(([id, value]) => {
      document.getElementById(id).textContent = String(value);
    });
    const timestamp = new Date(dashboard.fecha_consulta);
    document.getElementById("manager-updated").textContent = `Última actualización: ${timestamp.toLocaleString()}`;
    renderManagerOverdueOrders(dashboard.pedidos_atrasados_detalle || []);
  } catch (requestError) {
    error.textContent = requestError.message;
    error.hidden = false;
  }
}

function renderManagerOverdueOrders(orders) {
  const container = document.getElementById("manager-overdue-list");
  if (orders.length === 0) {
    container.textContent = "No hay pedidos atrasados.";
    return;
  }
  container.replaceChildren(...orders.map(order => {
    const item = document.createElement("div");
    item.className = "manager-alert";
    item.textContent = `Pedido #${order.id} · ${order.numero_mesa} · ${order.minutos_transcurridos} min`;
    return item;
  }));
}
