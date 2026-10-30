import os
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app


@pytest.fixture
def client():
    app.state.limiter.reset()
    with TestClient(app) as test_client:
        yield test_client


def _login(client, username, password):
    response = client.post("/api/v1/auth/login", json={
        "nombre_usuario": username,
        "password": password,
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_table_requests_are_idempotent_and_staff_can_resolve(client):
    created = client.post("/api/v1/cliente/solicitudes-mesa", json={
        "numero_mesa": 1,
        "tipo": "LLAMAR_MESERO",
        "nota": "Por favor",
    })
    assert created.status_code == 201, created.text
    repeated = client.post("/api/v1/cliente/solicitudes-mesa", json={
        "numero_mesa": 1,
        "tipo": "LLAMAR_MESERO",
    })
    assert repeated.status_code == 201
    assert repeated.json()["id"] == created.json()["id"]

    staff_headers = _login(client, "admin", "admin123")
    pending = client.get("/api/v1/mesero/solicitudes", headers=staff_headers)
    assert pending.status_code == 200
    assert any(item["id"] == created.json()["id"] for item in pending.json())
    resolved = client.put(
        f"/api/v1/mesero/solicitudes/{created.json()['id']}/estado",
        headers=staff_headers,
        json={"estado": "ATENDIDA"},
    )
    assert resolved.status_code == 200


def test_customer_personalization_is_authenticated_and_returns_real_data(client):
    headers = _login(client, "javier", "javier123")
    response = client.get("/api/v1/cliente/personalizacion", headers=headers)
    assert response.status_code == 200
    result = response.json()
    assert result["saludo"].startswith("¡Hola, ")
    assert isinstance(result["recomendaciones"], list)
    if result["ultima_orden"]:
        assert result["ultima_orden"]["items"]

    assert client.get("/api/v1/cliente/personalizacion").status_code == 401


def test_new_customer_has_no_synthetic_purchase_history(client):
    suffix = uuid4().hex[:12]
    username = f"cliente_qa_{suffix}"
    registration = client.post("/api/v1/auth/register", json={
        "nombre": "Cliente",
        "apellido": "QA",
        "email": f"{username}@example.com",
        "telefono": "04120000000",
        "nombre_usuario": username,
        "password": "ContraseñaSegura123",
    })
    assert registration.status_code == 200, registration.text

    login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": username,
        "password": "ContraseñaSegura123",
    })
    assert login.status_code == 200, login.text
    user = login.json()["usuario"]
    assert user["puntos_fidelidad"] == 50
    assert user["pedidos_count"] == 0
    assert user["total_gastado"] == 0


def test_admin_dashboard_uses_real_empty_values_and_qr_uses_request_origin(client):
    headers = _login(client, "admin", "admin123")
    legacy_panel = client.get("/static/admin/panel.html")
    assert legacy_panel.status_code == 200
    assert 'url=/static/admin/index.html' in legacy_panel.text

    dashboard = client.get("/api/v1/admin/dashboard-stats", headers=headers)
    assert dashboard.status_code == 200
    result = dashboard.json()
    assert result["total_ventas"] >= 0
    percentages = result["desglose_canales"]
    assert all(0 <= percentages[key] <= 100 for key in ("pct_mesa", "pct_delivery", "pct_llevar"))
    assert sum(percentages[key] for key in ("pct_mesa", "pct_delivery", "pct_llevar")) in {0, 100}

    qr = client.get("/api/v1/admin/mesas/1/qr", headers=headers)
    assert qr.status_code == 200
    assert qr.json()["url_acceso"].startswith("http://testserver/")
    assert "localhost:8000" not in qr.json()["url_acceso"]


def test_pickup_requires_kitchen_ready_state_and_customer_code(client):
    user_headers = _login(client, "javier", "javier123")
    products = client.get("/api/v1/cliente/productos").json()
    product = next(item for item in products if item["stock"] > 0)
    created = client.post("/api/v1/cliente/pedidos", headers=user_headers, json={
        "numero_mesa": "Mostrador",
        "tipo": "llevar",
        "modo_pago": "PAGAR_ANTES",
        "metodo_pago": "Efectivo",
        "detalles": [{"producto_id": product["id"], "cantidad": 1}],
    })
    assert created.status_code == 201, created.text
    order = created.json()
    assert len(order["codigo_retiro"]) == 6

    staff_headers = _login(client, "admin", "admin123")
    early = client.post(
        f"/api/v1/caja/pedidos/{order['id']}/confirmar-retiro",
        headers=staff_headers,
        json={"codigo_retiro": order["codigo_retiro"]},
    )
    assert early.status_code == 409
    ready = client.put(
        f"/api/v1/cocina/pedidos/{order['id']}/estado?estado=LISTO",
        headers=staff_headers,
    )
    assert ready.status_code == 200
    pickup_queue = client.get("/api/v1/caja/pedidos-retiro", headers=staff_headers)
    assert any(item["id"] == order["id"] for item in pickup_queue.json())
    assert all("codigo_retiro" not in item for item in pickup_queue.json())

    invalid_code = "000000" if order["codigo_retiro"] != "000000" else "999999"
    invalid = client.post(
        f"/api/v1/caja/pedidos/{order['id']}/confirmar-retiro",
        headers=staff_headers,
        json={"codigo_retiro": invalid_code},
    )
    assert invalid.status_code == 422
    confirmed = client.post(
        f"/api/v1/caja/pedidos/{order['id']}/confirmar-retiro",
        headers=staff_headers,
        json={"codigo_retiro": order["codigo_retiro"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["estado_retiro"] == "RETIRADO"


def test_cash_expense_is_deducted_and_arqueo_is_saved(client):
    headers = _login(client, "caja", "caja123")
    shift_response = client.get("/api/v1/caja/turno-activo", headers=headers)
    if shift_response.status_code == 404:
        opened = client.post("/api/v1/caja/abrir-turno", headers=headers, json={"monto_apertura": 100})
        assert opened.status_code == 200, opened.text
        shift_response = client.get("/api/v1/caja/turno-activo", headers=headers)
    assert shift_response.status_code == 200
    before = shift_response.json()

    expense = client.post("/api/v1/caja/movimientos", headers=headers, json={
        "concepto": "Compra de hielo",
        "monto_usd": 1,
        "metodo_pago": "Efectivo",
    })
    assert expense.status_code == 201, expense.text
    after = client.get("/api/v1/caja/turno-activo", headers=headers).json()
    assert after["efectivo_esperado"] == round(before["efectivo_esperado"] - 1, 2)

    closing = client.post("/api/v1/caja/cerrar-turno", headers=headers, json={
        "monto_cierre": after["efectivo_esperado"],
        "arqueo": [
            {"metodo_pago": "Efectivo", "contado_usd": after["esperado_por_metodo"]["Efectivo"]},
            {"metodo_pago": "Pago Móvil", "contado_usd": after["esperado_por_metodo"]["Pago Móvil"]},
            {"metodo_pago": "Punto de Venta", "contado_usd": after["esperado_por_metodo"]["Punto de Venta"]},
        ],
    })
    assert closing.status_code == 200, closing.text
    assert len(closing.json()["arqueo"]) == 3
    assert closing.json()["diferencia"] == 0
