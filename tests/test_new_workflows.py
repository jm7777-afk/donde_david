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


def test_admin_promotions_publish_to_both_carousels_and_can_be_cleared(client):
    admin_headers = _login(client, "admin", "admin123")
    suffix = uuid4().hex[:12]
    created = client.post("/api/v1/admin/promociones", headers=admin_headers, json={
        "titulo": f"Promo QA {suffix}",
        "descripcion": "Promoción de prueba",
        "descuento_pct": 15,
        "codigo_cupon": f"QA{suffix}",
        "banner_url": "/static/uploads/promo-qa.jpg",
        "activo": True,
    })
    assert created.status_code == 200, created.text
    promotion_id = created.json()["id"]
    try:
        public_promotions = client.get("/api/v1/cliente/promociones").json()
        assert any(promo["id"] == promotion_id for promo in public_promotions)

        updated = client.put(
            f"/api/v1/admin/promociones/{promotion_id}",
            headers=admin_headers,
            json={
                "titulo": f"Promo QA {suffix}",
                "descripcion": "Promoción editada",
                "descuento_pct": 0,
                "codigo_cupon": "",
                "banner_url": "",
                "activo": False,
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["banner_url"] == ""
        assert updated.json()["activo"] is False
        assert all(
            promo["id"] != promotion_id
            for promo in client.get("/api/v1/cliente/promociones").json()
        )
    finally:
        deleted = client.delete(
            f"/api/v1/admin/promociones/{promotion_id}", headers=admin_headers
        )
        assert deleted.status_code == 200, deleted.text


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


def test_guest_order_tracking_requires_opaque_token(client):
    products = client.get("/api/v1/cliente/productos").json()
    product = next(item for item in products if item["stock"] > 0)
    created = client.post("/api/v1/cliente/pedidos", json={
        "numero_mesa": "Mostrador",
        "tipo": "llevar",
        "detalles": [{"producto_id": product["id"], "cantidad": 1}],
    })
    assert created.status_code == 201, created.text
    order = created.json()
    token = order["token_seguimiento"]
    assert len(token) >= 32

    tracking_url = f"/api/v1/cliente/pedidos/{order['id']}/seguimiento"
    assert client.get(tracking_url).status_code == 404
    invalid = client.get(tracking_url, headers={"X-Order-Tracking-Token": "invalid"})
    assert invalid.status_code == 404

    tracked = client.get(tracking_url, headers={"X-Order-Tracking-Token": token})
    assert tracked.status_code == 200
    assert tracked.json()["estado"] == order["estado"]
    assert "token_seguimiento" not in tracked.json()


def test_product_loyalty_points_are_credited_only_after_payment(client):
    admin_headers = _login(client, "admin", "admin123")
    customer_headers = _login(client, "javier", "javier123")
    cashier_headers = _login(client, "caja", "caja123")
    categories = client.get("/api/v1/admin/categorias", headers=admin_headers).json()
    suffix = uuid4().hex[:12]
    product_response = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"Plato con puntos {suffix}",
        "categoria_id": categories[0]["id"],
        "precio": 8,
        "stock": 10,
        "puntos_fidelidad": 7,
    })
    assert product_response.status_code == 200, product_response.text
    product = product_response.json()
    assert product["puntos_fidelidad"] == 7

    before = client.get("/api/v1/cliente/personalizacion", headers=customer_headers).json()
    created = client.post("/api/v1/cliente/pedidos", headers=customer_headers, json={
        "numero_mesa": "Mostrador",
        "tipo": "llevar",
        "metodo_pago": "Efectivo",
        "detalles": [{"producto_id": product["id"], "cantidad": 3}],
    })
    assert created.status_code == 201, created.text
    order = created.json()
    assert order["detalles"][0]["puntos_fidelidad_unitarios"] == 7
    while_pending = client.get(
        "/api/v1/cliente/personalizacion", headers=customer_headers
    ).json()
    assert (while_pending["ultima_orden"] or {}).get("id") == (
        (before["ultima_orden"] or {}).get("id")
    )
    assert client.get("/api/v1/cliente/personalizacion", headers=customer_headers).json()[
        "puntos_fidelidad"
    ] == before["puntos_fidelidad"]
    updated_product = client.put(
        f"/api/v1/admin/productos/{product['id']}",
        headers=admin_headers,
        json={"puntos_fidelidad": 0},
    )
    assert updated_product.status_code == 200, updated_product.text
    assert updated_product.json()["puntos_fidelidad"] == 0

    active_shift = client.get("/api/v1/caja/turno-activo", headers=cashier_headers)
    if active_shift.status_code == 404:
        opened = client.post("/api/v1/caja/abrir-turno", headers=cashier_headers, json={"monto_apertura": 0})
        assert opened.status_code == 200, opened.text
    paid = client.post(
        f"/api/v1/caja/pedidos/{order['id']}/cobrar",
        headers=cashier_headers,
        json={
            "metodo_pago": "Efectivo",
            "monto_recibido": order["total"],
            "moneda_pago": "USD",
        },
    )
    assert paid.status_code == 200, paid.text
    after = client.get("/api/v1/cliente/personalizacion", headers=customer_headers).json()
    assert after["puntos_fidelidad"] == before["puntos_fidelidad"] + 21
    assert after["ultima_orden"]["id"] == order["id"]
    history = client.get("/api/v1/cliente/puntos/historial", headers=customer_headers).json()["historial"]
    assert sum(entry["puntos"] for entry in history if entry["concepto"] == f"Pedido #{order['id']}") == 21

    duplicate_payment = client.post(
        f"/api/v1/caja/pedidos/{order['id']}/cobrar",
        headers=cashier_headers,
        json={
            "metodo_pago": "Efectivo",
            "monto_recibido": order["total"],
            "moneda_pago": "USD",
        },
    )
    assert duplicate_payment.status_code == 400
    assert client.get("/api/v1/cliente/personalizacion", headers=customer_headers).json()[
        "puntos_fidelidad"
    ] == before["puntos_fidelidad"] + 21


def test_delivery_dispatch_list_hides_otp_without_response_validation_error(client):
    admin_headers = _login(client, "admin", "admin123")
    customer_headers = _login(client, "javier", "javier123")
    product = next(item for item in client.get("/api/v1/cliente/productos").json() if item["stock"] > 0)
    created = client.post("/api/v1/cliente/pedidos", headers=customer_headers, json={
        "numero_mesa": "Delivery QA",
        "tipo": "delivery",
        "metodo_pago": "Efectivo",
        "nombre_cliente_delivery": "Cliente QA",
        "telefono_delivery": "04120000000",
        "direccion_delivery": "Av. de prueba",
        "detalles": [{"producto_id": product["id"], "cantidad": 1}],
    })
    assert created.status_code == 201, created.text

    dispatched = client.get("/api/v1/delivery/despacho/pedidos", headers=admin_headers)
    assert dispatched.status_code == 200, dispatched.text
    order = next(item for item in dispatched.json() if item["id"] == created.json()["id"])
    assert "codigo_otp" not in order, "Dispatch responses must never expose the delivery OTP."


def test_delivery_courier_location_is_private_and_available_during_route(client):
    admin_headers = _login(client, "admin", "admin123")
    customer_headers = _login(client, "javier", "javier123")
    cashier_headers = _login(client, "caja", "caja123")
    courier_login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "delivery1",
        "password": "delivery123",
    })
    assert courier_login.status_code == 200, courier_login.text
    courier_headers = {"Authorization": f"Bearer {courier_login.json()['access_token']}"}
    categories = client.get("/api/v1/admin/categorias", headers=admin_headers).json()
    suffix = uuid4().hex[:12]
    product_response = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"Delivery tracking {suffix}",
        "categoria_id": categories[0]["id"],
        "precio": 5,
        "stock": 5,
        "puntos_fidelidad": 2,
    })
    assert product_response.status_code == 200, product_response.text
    created = client.post("/api/v1/cliente/pedidos", headers=customer_headers, json={
        "numero_mesa": "Delivery",
        "tipo": "delivery",
        "metodo_pago": "Efectivo",
        "nombre_cliente_delivery": "Cliente QA",
        "telefono_delivery": "04120000000",
        "direccion_delivery": "Av. de prueba",
        "delivery_lat": 10.48,
        "delivery_lng": -66.90,
        "detalles": [{"producto_id": product_response.json()["id"], "cantidad": 1}],
    })
    assert created.status_code == 201, created.text
    order = created.json()

    active_shift = client.get("/api/v1/caja/turno-activo", headers=cashier_headers)
    if active_shift.status_code == 404:
        opened = client.post("/api/v1/caja/abrir-turno", headers=cashier_headers, json={"monto_apertura": 0})
        assert opened.status_code == 200, opened.text
    paid = client.post(
        f"/api/v1/caja/pedidos/{order['id']}/cobrar",
        headers=cashier_headers,
        json={
            "metodo_pago": "Efectivo",
            "monto_recibido": order["total"],
            "moneda_pago": "USD",
        },
    )
    assert paid.status_code == 200, paid.text
    assigned = client.post(
        f"/api/v1/delivery/despacho/pedidos/{order['id']}/asignar",
        headers=admin_headers,
        json={"repartidor_id": courier_login.json()["usuario"]["id"]},
    )
    assert assigned.status_code == 200, assigned.text
    courier_orders = client.get("/api/v1/delivery/mis-pedidos", headers=courier_headers)
    assert courier_orders.status_code == 200, courier_orders.text
    courier_order = next(item for item in courier_orders.json() if item["id"] == order["id"])
    assert "codigo_otp" not in courier_order, "Courier order lists must not expose the delivery OTP."
    assert client.post(
        f"/api/v1/delivery/pedidos/{order['id']}/ubicacion",
        headers=courier_headers,
        json={"lat": 10.49, "lng": -66.91},
    ).status_code == 409
    assert client.put(
        f"/api/v1/cocina/pedidos/{order['id']}/estado?estado=LISTO",
        headers=admin_headers,
    ).status_code == 200
    picked_up = client.post(
        f"/api/v1/delivery/pedidos/{order['id']}/estado",
        headers=courier_headers,
        json={"estado": "RECOGIDO"},
    )
    assert picked_up.status_code == 200, picked_up.text
    en_route = client.post(
        f"/api/v1/delivery/pedidos/{order['id']}/estado",
        headers=courier_headers,
        json={"estado": "EN_CAMINO"},
    )
    assert en_route.status_code == 200, en_route.text
    location = client.post(
        f"/api/v1/delivery/pedidos/{order['id']}/ubicacion",
        headers=courier_headers,
        json={"lat": 10.49, "lng": -66.91},
    )
    assert location.status_code == 200, location.text

    tracking_url = f"/api/v1/cliente/pedidos/{order['id']}/seguimiento"
    assert client.get(tracking_url).status_code == 404
    tracking = client.get(tracking_url, headers={
        **customer_headers,
        "X-Order-Tracking-Token": order["token_seguimiento"],
    })
    assert tracking.status_code == 200, tracking.text
    result = tracking.json()
    assert result["repartidor_lat"] == 10.49
    assert result["repartidor_lng"] == -66.91
    assert result["repartidor_nombre"]
    assert order["codigo_otp"] is None
    assert len(result["codigo_otp"]) == 6


def test_pos_uses_server_configured_extra_prices_fees_and_currency(client, monkeypatch):
    from backend.app.api import caja as caja_api

    monkeypatch.setattr(caja_api, "get_bcv_rate", lambda db: {"tasa_cambio_bs": 50.0})
    admin_headers = _login(client, "admin", "admin123")
    cashier_headers = _login(client, "caja", "caja123")
    categories = client.get("/api/v1/admin/categorias", headers=admin_headers).json()
    suffix = uuid4().hex[:12]
    product_response = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"POS extras {suffix}",
        "categoria_id": categories[0]["id"],
        "precio": 10,
        "stock": 5,
        "puntos_fidelidad": 4,
        "extras_json": '[{"nombre":"Queso extra","precio":1.25}]',
    })
    assert product_response.status_code == 200, product_response.text
    product_id = product_response.json()["id"]

    active_shift = client.get("/api/v1/caja/turno-activo", headers=cashier_headers)
    if active_shift.status_code == 404:
        opened = client.post("/api/v1/caja/abrir-turno", headers=cashier_headers, json={"monto_apertura": 0})
        assert opened.status_code == 200, opened.text

    config = client.get("/api/v1/cliente/configuraciones-publicas").json()
    customer_headers = _login(client, "javier", "javier123")
    points_before = client.get(
        "/api/v1/cliente/personalizacion", headers=customer_headers
    ).json()["puntos_fidelidad"]
    customer = client.get(
        "/api/v1/caja/clientes/buscar?q=javier", headers=cashier_headers
    ).json()[0]
    subtotal = 11.25
    expected_total = round(
        subtotal
        + round(subtotal * (float(config["impuesto_porcentaje"]) / 100), 2)
        + float(config["costo_empaque"]),
        2,
    )
    payload = {
        "numero_mesa": "Mostrador",
        "tipo": "llevar",
        "cliente_id": customer["id"],
        "metodo_pago": "Efectivo",
        "monto_recibido": 100,
        "detalles": [{
            "producto_id": product_id,
            "cantidad": 1,
            "personalizaciones": {"extras": ["Queso extra"]},
        }],
    }
    paid = client.post("/api/v1/caja/crear-y-cobrar-rapido", headers=cashier_headers, json=payload)
    assert paid.status_code == 200, paid.text
    assert paid.json()["total"] == expected_total
    bolivars_payload = {
        **payload,
        "metodo_pago": "Pago Móvil",
        "moneda_pago": "VES",
        "monto_recibido": round(expected_total * 50, 2) + 5,
    }
    bolivars_paid = client.post(
        "/api/v1/caja/crear-y-cobrar-rapido",
        headers=cashier_headers,
        json=bolivars_payload,
    )
    assert bolivars_paid.status_code == 200, bolivars_paid.text
    assert bolivars_paid.json()["monto_pago"] == round(expected_total * 50, 2)
    assert bolivars_paid.json()["tasa_cambio_pago"] == 50
    assert bolivars_paid.json()["cambio"] == 5
    assert client.get(
        "/api/v1/cliente/personalizacion", headers=customer_headers
    ).json()["puntos_fidelidad"] == points_before + 8

    payload["detalles"][0]["personalizaciones"]["extras"] = ["Extra no configurado"]
    invalid_extra = client.post("/api/v1/caja/crear-y-cobrar-rapido", headers=cashier_headers, json=payload)
    assert invalid_extra.status_code == 422


def test_table_is_not_released_until_cleaning_after_payment(client):
    admin_headers = _login(client, "admin", "admin123")
    customer_headers = _login(client, "javier", "javier123")
    cashier_headers = _login(client, "caja", "caja123")
    table_response = client.get("/api/v1/mesero/mesas", headers=admin_headers)
    assert table_response.status_code == 200, table_response.text
    available_table = next((table for table in table_response.json() if table["estado"] == "LIBRE"), None)
    if available_table is None:
        raise AssertionError("El entorno de pruebas necesita al menos una mesa libre.")

    products = client.get("/api/v1/cliente/productos").json()
    product = next(item for item in products if item["stock"] > 0)
    created = client.post("/api/v1/cliente/pedidos", headers=customer_headers, json={
        "numero_mesa": f"Mesa {available_table['numero_mesa']}",
        "tipo": "mesa",
        "modo_pago": "PAGAR_DESPUES",
        "detalles": [{"producto_id": product["id"], "cantidad": 1}],
    })
    assert created.status_code == 201, created.text
    order = created.json()

    assert client.put(
        f"/api/v1/cocina/pedidos/{order['id']}/estado?estado=LISTO",
        headers=admin_headers,
    ).status_code == 200
    delivered = client.post(
        f"/api/v1/mesero/pedidos/{order['id']}/marcar-entregado",
        headers=admin_headers,
    )
    assert delivered.status_code == 200, delivered.text
    cleaning_url = f"/api/v1/mesero/mesas/{available_table['id']}/limpieza"
    blocked = client.put(cleaning_url, headers=admin_headers, json={"accion": "INICIAR"})
    assert blocked.status_code == 409

    active_shift = client.get("/api/v1/caja/turno-activo", headers=cashier_headers)
    if active_shift.status_code == 404:
        opened = client.post("/api/v1/caja/abrir-turno", headers=cashier_headers, json={"monto_apertura": 0})
        assert opened.status_code == 200, opened.text
    paid = client.post(
        f"/api/v1/caja/pedidos/{order['id']}/cobrar",
        headers=cashier_headers,
        json={
            "metodo_pago": "Efectivo",
            "monto_recibido": order["total"],
            "moneda_pago": "USD",
        },
    )
    assert paid.status_code == 200, paid.text
    table_after_payment = client.get("/api/v1/mesero/mesas", headers=admin_headers).json()
    assert next(table for table in table_after_payment if table["id"] == available_table["id"])["estado"] == "PENDIENTE_LIMPIEZA"

    start_cleaning = client.put(cleaning_url, headers=admin_headers, json={"accion": "INICIAR"})
    assert start_cleaning.status_code == 200, start_cleaning.text
    finish_cleaning = client.put(cleaning_url, headers=admin_headers, json={"accion": "FINALIZAR"})
    assert finish_cleaning.status_code == 200, finish_cleaning.text
    assert finish_cleaning.json()["estado"] == "LIBRE"


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
