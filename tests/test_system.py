import os
import sys
from uuid import uuid4
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from backend.app.main import app

@pytest.fixture
def client():
    app.state.limiter.reset()
    with TestClient(app) as test_client:
        yield test_client

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data

def test_readiness_check(client):
    response = client.get("/ready")
    assert response.status_code in [200, 503]
    data = response.json()
    assert data["status"] == ("ready" if response.status_code == 200 else "degraded")

def test_unauthorized_admin_access_fails(client):
    # Cliente no autenticado intentando acceder a usuarios del admin
    response = client.get("/api/v1/admin/usuarios")
    assert response.status_code in [401, 403]

def test_cashier_cannot_access_admin_routes(client):
    login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "caja",
        "password": "caja123"
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/v1/admin/usuarios", headers=headers)
    assert response.status_code == 403

def test_websocket_rejects_unauthenticated_connections(client):
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("{}")
        with pytest.raises(WebSocketDisconnect) as exc:
            websocket.receive_text()
    assert exc.value.code == 4401

def test_public_categories(client):
    response = client.get("/api/v1/cliente/categorias")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_public_products(client):
    response = client.get("/api/v1/cliente/productos")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_public_brand_and_footer_copy_can_be_configured(client):
    public_config = client.get("/api/v1/cliente/configuraciones-publicas")
    assert public_config.status_code == 200
    assert public_config.json()["nombre_restaurante"] == "DONDE DAVID | FAST FOOD"
    assert public_config.json()["direccion_restaurante"] == "📍 Valencia • Sede Principal"

    login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "admin",
        "password": "admin123"
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    updated = client.post("/api/v1/admin/configuraciones/lote", headers=headers, json={
        "configuraciones": [
            {"clave": "nombre_restaurante", "valor": "DONDE DAVID | FAST FOOD TEST"},
            {"clave": "landing_titulo", "valor": "Sabor recién hecho"},
            {"clave": "footer_inicio_texto", "valor": "Inicio actualizado"},
        ],
    })
    assert updated.status_code == 200, updated.text

    saved_config = client.get("/api/v1/cliente/configuraciones-publicas").json()
    assert saved_config["nombre_restaurante"] == "DONDE DAVID | FAST FOOD TEST"
    assert saved_config["landing_titulo"] == "Sabor recién hecho"
    assert saved_config["footer_inicio_texto"] == "Inicio actualizado"

    invalid = client.post("/api/v1/admin/configuraciones/lote", headers=headers, json={
        "configuraciones": [{"clave": "landing_descripcion", "valor": "x" * 301}],
    })
    assert invalid.status_code == 422
    assert client.get("/api/v1/cliente/configuraciones-publicas").json()["landing_descripcion"] == (
        saved_config["landing_descripcion"]
    )

def test_login_demo_admin(client):
    response = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["usuario"]["rol"] == "admin"

def test_manager_dashboard_is_read_only_and_role_protected(client):
    admin_login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "admin",
        "password": "admin123"
    })
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    assert client.get("/api/v1/gerencia/dashboard", headers=admin_headers).status_code == 403

    manager_username = f"mgr_{uuid4().hex[:12]}"
    created = client.post("/api/v1/admin/usuarios", headers=admin_headers, json={
        "nombre": "Gerente",
        "apellido": "Pruebas",
        "email": f"{manager_username}@example.com",
        "telefono": "0000000000",
        "nombre_usuario": manager_username,
        "password": "gerente-pruebas-123",
        "rol": "gerente",
        "activo": True,
    })
    assert created.status_code == 200, created.text

    manager_login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": manager_username,
        "password": "gerente-pruebas-123"
    })
    assert manager_login.status_code == 200
    manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}
    dashboard = client.get("/api/v1/gerencia/dashboard", headers=manager_headers)
    assert dashboard.status_code == 200
    assert {"ventas_hoy", "pedidos_cocina", "insumos_criticos"} <= dashboard.json().keys()
    assert client.get("/api/v1/admin/usuarios", headers=manager_headers).status_code == 403

def test_pos_rejects_unavailable_product_and_records_paid_timestamp(client):
    admin_login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "admin",
        "password": "admin123"
    })
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    categories = client.get("/api/v1/admin/categorias", headers=admin_headers).json()
    suffix = uuid4().hex[:12]
    product = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"Producto POS {suffix}",
        "categoria_id": categories[0]["id"],
        "precio": 2,
        "stock": 2,
        "disponible": False,
    })
    assert product.status_code == 200
    product_id = product.json()["id"]

    cashier_login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "caja",
        "password": "caja123"
    })
    assert cashier_login.status_code == 200
    cashier_headers = {"Authorization": f"Bearer {cashier_login.json()['access_token']}"}
    order_payload = {
        "numero_mesa": "Mostrador",
        "tipo": "llevar",
        "metodo_pago": "Efectivo",
        "monto_recibido": 10,
        "detalles": [{"producto_id": product_id, "cantidad": 1}],
    }
    active_shift = client.get("/api/v1/caja/turno-activo", headers=cashier_headers)
    if active_shift.status_code == 404:
        opened = client.post("/api/v1/caja/abrir-turno", headers=cashier_headers, json={"monto_apertura": 0})
        assert opened.status_code == 200
    unavailable = client.post("/api/v1/caja/crear-y-cobrar-rapido", headers=cashier_headers, json=order_payload)
    assert unavailable.status_code == 404

    assert client.put(f"/api/v1/admin/productos/{product_id}", headers=admin_headers, json={
        "disponible": True,
    }).status_code == 200
    paid = client.post("/api/v1/caja/crear-y-cobrar-rapido", headers=cashier_headers, json=order_payload)
    assert paid.status_code == 200
    order_id = paid.json()["pedido_id"]
    orders = client.get("/api/v1/caja/pedidos-cobrados", headers=cashier_headers)
    stored_order = next(order for order in orders.json() if order["id"] == order_id)
    assert stored_order["estado_pago"] == "PAGADO"
    assert stored_order["fecha_pago"] is not None
    frequent = client.get("/api/v1/caja/productos-frecuentes", headers=cashier_headers)
    assert frequent.status_code == 200
    assert any(item["id"] == product_id for item in frequent.json())

def test_admin_product_availability_and_allergens_persist(client, monkeypatch):
    from backend.app.api import admin as admin_api

    broadcasts = []

    async def record_broadcast(event_type, data):
        broadcasts.append((event_type, data))

    monkeypatch.setattr(admin_api.ws_manager, "broadcast", record_broadcast)
    login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "admin",
        "password": "admin123"
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    suffix = uuid4().hex[:12]
    category = client.post("/api/v1/admin/categorias", headers=headers, json={
        "nombre": f"Categoría de pruebas {suffix}",
    })
    assert category.status_code == 200
    product = client.post("/api/v1/admin/productos", headers=headers, json={
        "nombre": f"Producto de pruebas {suffix}",
        "categoria_id": category.json()["id"],
        "precio": 4.5,
        "stock": 5,
        "alergenos": "leche, gluten",
        "disponible": True,
    })
    assert product.status_code == 200
    product_id = product.json()["id"]
    updated = client.put(f"/api/v1/admin/productos/{product_id}", headers=headers, json={
        "alergenos": "leche",
        "disponible": False,
    })
    assert updated.status_code == 200
    stored = next(item for item in client.get("/api/v1/admin/productos", headers=headers).json()
                  if item["id"] == product_id)
    assert stored["alergenos"] == "leche"
    assert stored["disponible"] is False
    available = client.put(f"/api/v1/admin/productos/{product_id}", headers=headers, json={
        "disponible": True,
    })
    assert available.status_code == 200
    assert any(item["id"] == product_id for item in client.get("/api/v1/cliente/productos").json())
    category_delete = client.delete(
        f"/api/v1/admin/categorias/{category.json()['id']}", headers=headers
    )
    assert category_delete.status_code == 409
    assert "producto(s) asociado(s)" in category_delete.json()["detail"]
    archived = client.delete(f"/api/v1/admin/productos/{product_id}", headers=headers)
    assert archived.status_code == 200
    archived_product = next(item for item in client.get("/api/v1/admin/productos", headers=headers).json()
                            if item["id"] == product_id)
    assert archived_product["activo"] is False
    public_products = client.get("/api/v1/cliente/productos")
    assert all(item["id"] != product_id for item in public_products.json())
    settings = client.post("/api/v1/admin/configuraciones/lote", headers=headers, json={
        "configuraciones": [{"clave": f"test_setting_{suffix}", "valor": "enabled"}],
    })
    assert settings.status_code == 200
    assert [event for event, _ in broadcasts] == [
        "PRODUCTOS_ACTUALIZADOS",
        "PRODUCTOS_ACTUALIZADOS",
        "PRODUCTOS_ACTUALIZADOS",
        "PRODUCTOS_ACTUALIZADOS",
        "PRODUCTOS_ACTUALIZADOS",
        "CONFIGURACION_ACTUALIZADA",
    ]

def test_kitchen_filter_and_table_summary_shape(client):
    login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "admin",
        "password": "admin123"
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    filtered_orders = client.get("/api/v1/cocina/pedidos?tipo=delivery", headers=headers)
    assert filtered_orders.status_code == 200
    assert all(order["tipo"] == "delivery" for order in filtered_orders.json())
    assert client.get("/api/v1/cocina/pedidos?tipo=unknown", headers=headers).status_code == 422

    tables = client.get("/api/v1/mesero/mesas", headers=headers)
    assert tables.status_code == 200
    assert all(
        {"numero_mesa", "estado", "tiempo_ocupacion_min", "pedidos_activos"} <= table.keys()
        for table in tables.json()
    )

def test_cash_shift_summary_returns_cash_only_expectation(client):
    login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "caja",
        "password": "caja123"
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    active = client.get("/api/v1/caja/turno-activo", headers=headers)
    if active.status_code == 404:
        opened = client.post("/api/v1/caja/abrir-turno", headers=headers, json={"monto_apertura": 25})
        assert opened.status_code == 200
    response = client.get("/api/v1/caja/turno-activo", headers=headers)
    assert response.status_code == 200
    summary = response.json()
    assert summary["efectivo_esperado"] >= summary["monto_apertura"]

def test_rbac_client_forbidden_on_caja(client):
    # Login como cliente normal
    login_res = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "javier",
        "password": "javier123"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    # Intentar acceder a caja con token de cliente
    caja_res = client.get("/api/v1/caja/turno-activo", headers={"Authorization": f"Bearer {token}"})
    assert caja_res.status_code == 403
