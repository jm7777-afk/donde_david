import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.database import SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.main import app
from backend.app.models.categoria import Categoria
from backend.app.models.mesa import Mesa
from backend.app.models.pedido import Pedido
from backend.app.models.producto import Producto
from backend.app.models.puntos_log import Auditoria
from backend.app.models.turno import Turno
from backend.app.models.usuario import Usuario


@pytest.fixture
def client():
    app.state.limiter.reset()
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"nombre_usuario": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_user_in_db(role: str, *, active: bool = True, points: int = 0) -> tuple[str, str, int]:
    suffix = uuid4().hex[:8]
    username = f"qa_{role}_{suffix}"
    password = f"QaStrongPass!{suffix}"
    db = SessionLocal()
    try:
        user = Usuario(
            nombre="QA",
            apellido=role.title(),
            email=f"{username}@dondedavid.test",
            telefono="04141234567",
            nombre_usuario=username,
            contraseña_hash=get_password_hash(password),
            rol=role,
            activo=active,
            puntos_fidelidad=points,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return username, password, user.id
    finally:
        db.close()


def _ensure_open_shift(client: TestClient, cashier_headers: dict[str, str]) -> dict:
    active = client.get("/api/v1/caja/turno-activo", headers=cashier_headers)
    if active.status_code == 200:
        return active.json()
    opened = client.post("/api/v1/caja/abrir-turno", headers=cashier_headers, json={"monto_apertura": 50.0})
    assert opened.status_code == 200, opened.text
    return opened.json()


def test_role_permission_matrix_enforced_in_backend(client):
    sup_user, sup_pwd, _ = _create_user_in_db("supervisor")
    ger_user, ger_pwd, _ = _create_user_in_db("gerente")
    mes_user, mes_pwd, _ = _create_user_in_db("mesero")

    tokens = {
        "anon": {},
        "admin": _login(client, "admin", "admin123"),
        "supervisor": _login(client, sup_user, sup_pwd),
        "gerente": _login(client, ger_user, ger_pwd),
        "caja": _login(client, "caja", "caja123"),
        "cocina": _login(client, "cocina1", "cocina123"),
        "mesero": _login(client, mes_user, mes_pwd),
        "repartidor": _login(client, "delivery1", "delivery123"),
        "cliente": _login(client, "javier", "javier123"),
    }

    matrix = {
        "/api/v1/admin/usuarios": {"admin", "supervisor"},
        "/api/v1/gerencia/dashboard": {"gerente"},
        "/api/v1/caja/pedidos-pendientes": {"admin", "supervisor", "caja"},
        "/api/v1/cocina/pedidos": {"admin", "supervisor", "caja", "cocina", "mesero"},
        "/api/v1/mesero/mesas": {"admin", "supervisor", "caja", "mesero"},
        "/api/v1/delivery/mis-pedidos": {"admin", "supervisor", "repartidor"},
    }

    for endpoint, allowed_roles in matrix.items():
        for role, headers in tokens.items():
            resp = client.get(endpoint, headers=headers)
            if role in allowed_roles:
                assert resp.status_code == 200, f"{role} should access {endpoint}, got {resp.status_code}"
            elif role == "anon":
                assert resp.status_code in (401, 403), f"anon should be rejected on {endpoint}, got {resp.status_code}"
            else:
                assert resp.status_code == 403, f"{role} should get 403 on {endpoint}, got {resp.status_code}"


def test_kitchen_state_guards_stock_restore_and_payment_idempotency(client):
    admin_headers = _login(client, "admin", "admin123")
    cashier_headers = _login(client, "caja", "caja123")
    kitchen_headers = _login(client, "cocina1", "cocina123")
    _ensure_open_shift(client, cashier_headers)

    cfg = client.post("/api/v1/admin/configuraciones/lote", headers=admin_headers, json={
        "configuraciones": [
            {"clave": "tasa_cambio_bs", "valor": "36.50"},
            {"clave": "pago_movil_banco", "valor": "Banco QA"},
            {"clave": "pago_movil_telefono", "valor": "04140001122"},
            {"clave": "pago_movil_rif", "valor": "J-12345678-9"},
            {"clave": "pago_movil_titular", "valor": "Donde David QA"},
        ],
    })
    assert cfg.status_code == 200, cfg.text

    cat_id = client.get("/api/v1/admin/categorias", headers=admin_headers).json()[0]["id"]
    prod = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"QA Burger {uuid4().hex[:5]}",
        "descripcion": "Prueba concurrencia stock",
        "precio": 10.0,
        "categoria_id": cat_id,
        "stock": 5,
        "disponible": True,
    }).json()

    # 1. Pago Móvil starts in PAGO_PENDIENTE and cannot enter kitchen preparation yet
    mobile_resp = client.post("/api/v1/cliente/pedidos", json={
        "numero_mesa": "Mostrador",
        "tipo": "llevar",
        "modo_pago": "PAGAR_ANTES",
        "metodo_pago": "Pago Móvil",
        "moneda_pago": "VES",
        "referencia_pago": f"PM-{uuid4().hex[:6]}",
        "detalles": [{"producto_id": prod["id"], "cantidad": 2}],
    })
    assert mobile_resp.status_code == 201, mobile_resp.text
    mobile_order = mobile_resp.json()
    assert mobile_order["estado"] == "PAGO_PENDIENTE"

    blocked_prep = client.put(
        f"/api/v1/cocina/pedidos/{mobile_order['id']}/estado?estado=EN_PREPARACION",
        headers=kitchen_headers,
    )
    assert blocked_prep.status_code == 409

    # Rejecting mobile payment cancels order and restores stock back to 5
    rejected = client.post(
        f"/api/v1/caja/pedidos/{mobile_order['id']}/confirmar-pago",
        headers=cashier_headers,
        json={"aprobado": False, "observacion": "No recibido"},
    )
    assert rejected.status_code == 200

    # 2. Cannot revive CANCELADO order or update its items
    revive = client.put(
        f"/api/v1/cocina/pedidos/{mobile_order['id']}/estado?estado=EN_PREPARACION",
        headers=kitchen_headers,
    )
    assert revive.status_code == 409
    bad_item_status = client.put(
        f"/api/v1/cocina/detalles/{mobile_order['detalles'][0]['id']}/estado?estado=LISTO",
        headers=kitchen_headers,
    )
    assert bad_item_status.status_code == 409

    invalid_item_status = client.put(
        f"/api/v1/cocina/detalles/{mobile_order['detalles'][0]['id']}/estado?estado=NO_EXISTE",
        headers=kitchen_headers,
    )
    assert invalid_item_status.status_code == 400

    # Verify stock restored to 5
    db = SessionLocal()
    try:
        refreshed = db.query(Producto).filter(Producto.id == prod["id"]).first()
        assert refreshed.stock == 5
    finally:
        db.close()

    # 3. Payment retry idempotency on /cobrar
    cash_order = client.post("/api/v1/cliente/pedidos", json={
        "numero_mesa": "Mostrador",
        "tipo": "llevar",
        "modo_pago": "PAGAR_ANTES",
        "metodo_pago": "Efectivo",
        "moneda_pago": "USD",
        "detalles": [{"producto_id": prod["id"], "cantidad": 1}],
    }).json()
    shift_before = client.get("/api/v1/caja/turno-activo", headers=cashier_headers).json()

    first_pay = client.post(f"/api/v1/caja/pedidos/{cash_order['id']}/cobrar", headers=cashier_headers, json={
        "metodo_pago": "Efectivo",
        "monto_recibido": float(cash_order["total"]),
        "moneda_pago": "USD",
    })
    assert first_pay.status_code == 200
    assert first_pay.json()["repetido"] is False

    second_pay = client.post(f"/api/v1/caja/pedidos/{cash_order['id']}/cobrar", headers=cashier_headers, json={
        "metodo_pago": "Efectivo",
        "monto_recibido": float(cash_order["total"]),
        "moneda_pago": "USD",
    })
    assert second_pay.status_code == 200
    assert second_pay.json()["repetido"] is True

    shift_after = client.get("/api/v1/caja/turno-activo", headers=cashier_headers).json()
    assert shift_after["total_ventas"] == round(shift_before["total_ventas"] + float(cash_order["total"]), 2)


def test_otp_verification_requires_authorization_and_loyalty_redeem_locks_balance(client):
    guest_headers = _login(client, "javier", "javier123")
    _, other_pwd, _ = _create_user_in_db("cliente")
    other_username = None
    # Create dedicated client with 60 points for redemption check
    c_user, c_pwd, c_id = _create_user_in_db("cliente", points=60)
    c_headers = _login(client, c_user, c_pwd)

    prod = next(item for item in client.get("/api/v1/cliente/productos").json() if item["stock"] > 0)
    delivery_resp = client.post("/api/v1/cliente/pedidos", json={
        "numero_mesa": "Delivery Test",
        "tipo": "delivery",
        "modo_pago": "PAGAR_ANTES",
        "metodo_pago": "Efectivo",
        "moneda_pago": "USD",
        "nombre_cliente_delivery": "Visitante",
        "telefono_delivery": "04141112233",
        "direccion_delivery": "Av. Bolivar #10",
        "detalles": [{"producto_id": prod["id"], "cantidad": 1}],
    })
    assert delivery_resp.status_code == 201, delivery_resp.text
    delivery_order = delivery_resp.json()
    assert delivery_order["codigo_otp"] is None
    assert delivery_order["token_seguimiento"]

    db = SessionLocal()
    try:
        otp_code = db.query(Pedido).filter(Pedido.id == delivery_order["id"]).first().codigo_otp
    finally:
        db.close()

    # Anonymous without tracking token gets 404 even with right OTP
    unauth = client.post("/api/v1/cliente/pedidos/verificar-otp", json={
        "pedido_id": delivery_order["id"],
        "codigo_otp": otp_code,
    })
    assert unauth.status_code == 404

    # Another logged-in customer gets 404
    wrong_user = client.post("/api/v1/cliente/pedidos/verificar-otp", headers=guest_headers, json={
        "pedido_id": delivery_order["id"],
        "codigo_otp": otp_code,
    })
    assert wrong_user.status_code == 404

    # Guest with valid X-Order-Tracking-Token succeeds
    valid_token_res = client.post(
        "/api/v1/cliente/pedidos/verificar-otp",
        headers={"X-Order-Tracking-Token": delivery_order["token_seguimiento"]},
        json={"pedido_id": delivery_order["id"], "codigo_otp": otp_code},
    )
    assert valid_token_res.status_code == 200
    assert valid_token_res.json()["valido"] is True

    # Loyalty redemption: 60 points can redeem 50-pt Bebida Gratis once, second attempt fails cleanly
    ok_redeem = client.post("/api/v1/cliente/puntos/canjear?recompensa=Bebida Gratis", headers=c_headers)
    assert ok_redeem.status_code == 200
    assert ok_redeem.json()["puntos_restantes"] == 10

    fail_redeem = client.post("/api/v1/cliente/puntos/canjear?recompensa=Bebida Gratis", headers=c_headers)
    assert fail_redeem.status_code == 400


def test_admin_validation_safeguards_and_audit_trail(client):
    admin_headers = _login(client, "admin", "admin123")

    # Missing category -> 404
    bad_cat = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": "Producto Sin Cat",
        "precio": 10.0,
        "categoria_id": 999999,
        "stock": 5,
    })
    assert bad_cat.status_code == 404

    # Promo > base price -> 422
    cat_id = client.get("/api/v1/admin/categorias", headers=admin_headers).json()[0]["id"]
    bad_promo = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": "Promo Invalida",
        "precio": 10.0,
        "precio_promocion": 15.0,
        "categoria_id": cat_id,
        "stock": 5,
    })
    assert bad_promo.status_code == 422

    # Admin cannot deactivate themselves
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    self_deact = client.put(f"/api/v1/admin/usuarios/{me['id']}", headers=admin_headers, json={"activo": False})
    assert self_deact.status_code == 409

    # Duplicate email on user update -> 400
    _, _, other_id = _create_user_in_db("mesero")
    dup_email = client.put(
        f"/api/v1/admin/usuarios/{other_id}",
        headers=admin_headers,
        json={"email": me["email"]},
    )
    assert dup_email.status_code == 400

    # Config update creates CONFIG_UPDATE audit record
    cfg_resp = client.post("/api/v1/admin/configuraciones", headers=admin_headers, json={
        "clave": "horario_atencion",
        "valor": "Lunes a Domingo 11am - 11pm",
    })
    assert cfg_resp.status_code == 200
    db = SessionLocal()
    try:
        audit = db.query(Auditoria).filter(
            Auditoria.accion == "CONFIG_UPDATE",
            Auditoria.recurso_id == "horario_atencion",
        ).order_by(Auditoria.id.desc()).first()
        assert audit is not None
    finally:
        db.close()


def test_admin_dashboard_stats_filters_by_category_and_payment_method(client):
    admin_headers = _login(client, "admin", "admin123")
    cashier_headers = _login(client, "caja", "caja123")
    _ensure_open_shift(client, cashier_headers)

    prev_iva = client.get("/api/v1/cliente/configuraciones-publicas").json().get("iva_activo", "true")
    # Disable IVA temporarily for deterministic arithmetic in this check
    client.post("/api/v1/admin/configuraciones", headers=admin_headers, json={
        "clave": "iva_activo",
        "valor": "false",
    })
    try:
        cats = client.get("/api/v1/admin/categorias", headers=admin_headers).json()
        postre_cat = next(c for c in cats if "postre" in c["nombre"].lower())
        comida_cat = next(c for c in cats if "hamburguesa" in c["nombre"].lower())

        postre = client.post("/api/v1/admin/productos", headers=admin_headers, json={
            "nombre": f"QA Helado {uuid4().hex[:4]}",
            "precio": 7.0,
            "categoria_id": postre_cat["id"],
            "stock": 20,
        }).json()
        comida = client.post("/api/v1/admin/productos", headers=admin_headers, json={
            "nombre": f"QA Double {uuid4().hex[:4]}",
            "precio": 13.0,
            "categoria_id": comida_cat["id"],
            "stock": 20,
        }).json()

        # Pay one dessert with Efectivo and one burger with Punto de Venta
        res_postre = client.post("/api/v1/caja/crear-y-cobrar-rapido", headers=cashier_headers, json={
            "numero_mesa": "Mostrador",
            "tipo": "llevar",
            "metodo_pago": "Efectivo",
            "moneda_pago": "USD",
            "monto_recibido": 15.0,
            "detalles": [{"producto_id": postre["id"], "cantidad": 1}],
        })
        assert res_postre.status_code == 200, res_postre.text

        res_comida = client.post("/api/v1/caja/crear-y-cobrar-rapido", headers=cashier_headers, json={
            "numero_mesa": "Mostrador",
            "tipo": "llevar",
            "metodo_pago": "Punto de Venta",
            "moneda_pago": "USD",
            "monto_recibido": 20.0,
            "detalles": [{"producto_id": comida["id"], "cantidad": 1}],
        })
        assert res_comida.status_code == 200, res_comida.text

        dessert_stats = client.get(
            "/api/v1/admin/dashboard-stats?categoria=postres&metodo_pago=Efectivo",
            headers=admin_headers,
        ).json()
        assert dessert_stats["filtros_aplicados"] == {"categoria": "postres", "metodo_pago": "Efectivo"}
        assert dessert_stats["total_ventas"] >= 7.0
        assert any(p["nombre"] == postre["nombre"] for p in dessert_stats["top_productos"])
        assert not any(p["nombre"] == comida["nombre"] for p in dessert_stats["top_productos"])

        card_food_stats = client.get(
            "/api/v1/admin/dashboard-stats?categoria=comidas&metodo_pago=Tarjeta",
            headers=admin_headers,
        ).json()
        assert any(p["nombre"] == comida["nombre"] for p in card_food_stats["top_productos"])
        assert not any(p["nombre"] == postre["nombre"] for p in card_food_stats["top_productos"])
    finally:
        client.post("/api/v1/admin/configuraciones", headers=admin_headers, json={
            "clave": "iva_activo",
            "valor": str(prev_iva),
        })


def test_full_e2e_qr_kitchen_waiter_cashier_cleaning_flow(client):
    admin_headers = _login(client, "admin", "admin123")
    cashier_headers = _login(client, "caja", "caja123")
    kitchen_headers = _login(client, "cocina1", "cocina123")
    mesero_user, mesero_pwd, _ = _create_user_in_db("mesero")
    waiter_headers = _login(client, mesero_user, mesero_pwd)
    _ensure_open_shift(client, cashier_headers)

    # Pick/create a free mesa
    mesa_num = 77
    db = SessionLocal()
    try:
        mesa_obj = db.query(Mesa).filter(Mesa.numero_mesa == mesa_num).first()
        if not mesa_obj:
            mesa_obj = Mesa(numero_mesa=mesa_num, capacidad=4, estado="LIBRE")
            db.add(mesa_obj)
            db.commit()
            db.refresh(mesa_obj)
        else:
            mesa_obj.estado = "LIBRE"
            db.commit()
        mesa_id = mesa_obj.id
    finally:
        db.close()

    product = next(p for p in client.get("/api/v1/cliente/productos").json() if p["stock"] > 0)

    # 1. Guest submits QR table order with PAGAR_DESPUES
    order = client.post("/api/v1/cliente/pedidos", json={
        "numero_mesa": f"Mesa {mesa_num}",
        "tipo": "mesa",
        "modo_pago": "PAGAR_DESPUES",
        "detalles": [{"producto_id": product["id"], "cantidad": 1}],
    })
    assert order.status_code == 201, order.text
    order_data = order.json()
    assert order_data["estado"] == "PENDIENTE"

    # 2. Kitchen prepares and marks LISTO
    assert client.put(f"/api/v1/cocina/pedidos/{order_data['id']}/estado?estado=EN_PREPARACION", headers=kitchen_headers).status_code == 200
    assert client.put(f"/api/v1/cocina/pedidos/{order_data['id']}/estado?estado=LISTO", headers=kitchen_headers).status_code == 200

    # 3. Waiter marks ENTREGADO
    delivered = client.post(f"/api/v1/mesero/pedidos/{order_data['id']}/marcar-entregado", headers=waiter_headers)
    assert delivered.status_code == 200, delivered.text

    # 4. Cashier collects payment and fetches invoice
    paid = client.post(f"/api/v1/caja/pedidos/{order_data['id']}/cobrar", headers=cashier_headers, json={
        "metodo_pago": "Efectivo",
        "monto_recibido": float(order_data["total"]) + 5.0,
        "moneda_pago": "USD",
    })
    assert paid.status_code == 200, paid.text
    invoice = client.get(f"/api/v1/caja/pedidos/{order_data['id']}/factura", headers=cashier_headers)
    assert invoice.status_code == 200
    assert invoice.json()["total"] == order_data["total"]

    # 5. Waiter cleans & releases table back to LIBRE
    assert client.put(f"/api/v1/mesero/mesas/{mesa_id}/limpieza", headers=waiter_headers, json={"accion": "INICIAR"}).status_code == 200
    assert client.put(f"/api/v1/mesero/mesas/{mesa_id}/limpieza", headers=waiter_headers, json={"accion": "FINALIZAR"}).status_code == 200
    mesas = client.get("/api/v1/mesero/mesas", headers=waiter_headers).json()
    assert next(m for m in mesas if m["id"] == mesa_id)["estado"] == "LIBRE"


def test_security_and_frontend_contract_hygiene():
    root = Path(__file__).resolve().parent.parent
    login_html = (root / "backend/static/login.html").read_text(encoding="utf-8")
    for leaked_pwd in ("admin123", "caja123", "cocina123", "delivery123", "localStorage.setItem(\"dd_saved_pass"):
        assert leaked_pwd not in login_html

    cliente_js = (root / "backend/static/js/cliente-toon.js").read_text(encoding="utf-8")
    assert "dd_client_saved_pass" not in cliente_js

    caja_html = (root / "backend/static/caja/panel.html").read_text(encoding="utf-8")
    assert 'id="view-btn-app-payments"' in caja_html
    assert 'id="pos-history-payment-filter"' in caja_html


def test_promotions_support_editable_product_groups_and_public_mesas(client):
    admin_headers = _login(client, "admin", "admin123")

    mesas_resp = client.get("/api/v1/cliente/mesas")
    assert mesas_resp.status_code == 200
    assert isinstance(mesas_resp.json(), list)

    prods = client.get("/api/v1/admin/productos", headers=admin_headers).json()
    assert len(prods) >= 2
    p1, p2 = prods[0]["id"], prods[1]["id"]

    # Missing product ID rejected with 404
    bad_promo = client.post("/api/v1/admin/promociones", headers=admin_headers, json={
        "titulo": "Promo Invalida",
        "descripcion": "No debe guardarse",
        "descuento_pct": 10,
        "activo": True,
        "producto_ids": [99999999],
    })
    assert bad_promo.status_code == 404

    created = client.post("/api/v1/admin/promociones", headers=admin_headers, json={
        "titulo": f"Combo QA {uuid4().hex[:5]}",
        "descripcion": "Grupo inicial de productos",
        "descuento_pct": 15,
        "codigo_cupon": f"QA{uuid4().hex[:6].upper()}",
        "activo": True,
        "producto_ids": [p1],
    })
    assert created.status_code == 200, created.text
    promo = created.json()
    assert promo["producto_ids"] == [p1]
    assert len(promo["productos"]) == 1

    # Public promotions return linked product group
    public_promos = client.get("/api/v1/cliente/promociones").json()
    matched = next(item for item in public_promos if item["id"] == promo["id"])
    assert matched["producto_ids"] == [p1]

    # Edit product group via dedicated endpoint
    updated_group = client.put(
        f"/api/v1/admin/promociones/{promo['id']}/productos",
        headers=admin_headers,
        json={"producto_ids": [p1, p2]},
    )
    assert updated_group.status_code == 200, updated_group.text
    assert set(updated_group.json()["producto_ids"]) == {p1, p2}
    assert len(updated_group.json()["productos"]) == 2

    # Clean up promo
    assert client.delete(f"/api/v1/admin/promociones/{promo['id']}", headers=admin_headers).status_code == 200


def test_new_client_ui_qr_iva_promos_no_chatbot_and_high_priority_alerts():
    root = Path(__file__).resolve().parent.parent
    app_html = (root / "backend/static/cliente/app.html").read_text(encoding="utf-8")
    login_html = (root / "backend/static/login.html").read_text(encoding="utf-8")
    admin_html = (root / "backend/static/admin/index.html").read_text(encoding="utf-8")
    caja_html = (root / "backend/static/caja/panel.html").read_text(encoding="utf-8")

    cliente_js = (root / "backend/static/js/cliente-toon.js").read_text(encoding="utf-8")
    websocket_js = (root / "backend/static/js/websocket.js").read_text(encoding="utf-8")
    caja_js = (root / "backend/static/js/caja.js").read_text(encoding="utf-8")
    mesero_js = (root / "backend/static/js/mesero.js").read_text(encoding="utf-8")
    cocina_js = (root / "backend/static/js/cocina.js").read_text(encoding="utf-8")

    # 1. Manual table selector removed from QR scanner modal
    assert 'id="client-scanner-table-select"' not in app_html
    assert "SELECCIÓN MANUAL DE MESA" not in app_html

    # 2. IVA enable/disable controls present
    assert 'id="admin-iva-toggle-btn"' in admin_html
    assert 'id="pos-iva-status-badge"' in caja_html

    # 3. Payment mode modifiable in Step 2 & Step 4
    assert 'name="modo_pago"' in app_html
    assert 'id="checkout-step4-mesa-mode"' in app_html
    assert "syncMesaPaymentMode" in cliente_js

    # 4. Monkey emoji removed; eye SVG toggle present on login and register
    for content in (app_html, login_html, cliente_js):
        for monkey in ("🙈", "🙉", "🙊"):
            assert monkey not in content
    assert 'id="toggle-client-pass"' in app_html
    assert 'id="toggle-client-reg-pass"' in app_html
    assert 'id="toggle-portal-pass"' in login_html

    # 5 & 6. Promo group modal, promo product picker, and active promo/combo notifications
    assert 'id="promo-products-picker"' in admin_html
    assert 'id="promo-products-modal"' in app_html
    assert 'id="client-promo-notifications"' in app_html

    # 7. Chatbot completely removed
    for chatbot_token in ("fab-chatbot", "chatbot-modal", "DavidBot", "sendChatbotMessage"):
        assert chatbot_token not in app_html
        assert chatbot_token not in cliente_js

    # 8. High-priority notifications wired for Caja, Salón, and Cocina
    assert "function notifyHighPriority" in websocket_js
    for js_content in (caja_js, mesero_js, cocina_js):
        assert "notifyHighPriority(" in js_content

    # 9. Global promo pricing UI controls & payload wiring
    assert 'id="promo-precio-global"' in admin_html
    assert 'id="promo-regular-sum-hint"' in admin_html
    assert 'id="promo-bundle-pricing-bar"' in app_html
    assert 'id="promo-modal-global-price"' in app_html
    assert 'id="promo-bundle-qty-val"' in app_html
    assert "_computePromoBundleAllocations" in cliente_js
    assert "promociones: promocionesPayload" in cliente_js

    # 10. Enhanced UI contracts across Turnos, POS, KDS, Mesero, Admin, and Gerencia
    turnos_html = (root / "backend/static/turnos/pantalla.html").read_text(encoding="utf-8")
    mesero_html = (root / "backend/static/mesero/panel.html").read_text(encoding="utf-8")
    cocina_html = (root / "backend/static/cocina/monitor.html").read_text(encoding="utf-8")
    gerencia_html = (root / "backend/static/gerencia/panel.html").read_text(encoding="utf-8")
    assert 'id="turnos-prep-list"' in turnos_html and 'id="turnos-ready-list"' in turnos_html
    assert 'id="checkout-coupon-code"' in app_html and 'id="cart-upsell-section"' in app_html
    assert 'id="split-bill-modal"' in caja_html and 'id="pay-mixed-toggle"' in caja_html
    assert 'id="kds-allday-summary"' in cocina_html and 'id="kds-layout-btn"' in cocina_html
    assert 'id="waiter-order-modal"' in mesero_html and 'id="mesero-status-filter"' in mesero_html
    assert 'id="recipe-modal"' in admin_html and 'id="compra-inventario-modal"' in admin_html
    assert 'id="manager-avg-rating"' in gerencia_html and 'id="manager-tips-today"' in gerencia_html


def test_recipes_purchases_stock_alerts_and_profitability_sla(client):
    admin_headers = _login(client, "admin", "admin123")
    cat_id = client.get("/api/v1/admin/categorias", headers=admin_headers).json()[0]["id"]

    # Create insumo + product linked via recipe
    ins_res = client.post("/api/v1/admin/insumos", headers=admin_headers, json={
        "nombre": f"Carne Receta {uuid4().hex[:5]}",
        "stock_actual": 4.0,
        "stock_minimo": 2.0,
        "unidad_medida": "un",
        "costo_unitario": 1.50,
    })
    assert ins_res.status_code == 200, ins_res.text
    insumo = ins_res.json()

    prod_res = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"Burger Receta {uuid4().hex[:5]}",
        "precio": 12.00,
        "costo_unitario": 3.00,
        "categoria_id": cat_id,
        "stock": 10,
        "disponible": True,
    })
    assert prod_res.status_code == 200, prod_res.text
    prod = prod_res.json()

    rec_res = client.put(f"/api/v1/admin/productos/{prod['id']}/receta", headers=admin_headers, json={
        "items": [{"insumo_id": insumo["id"], "cantidad_por_unidad": 2.0}]
    })
    assert rec_res.status_code == 200, rec_res.text
    assert len(rec_res.json()) == 1

    # Order 2 units -> consumes 4.0 insumo -> insumo drops to 0.0 CRITICO & product auto-disabled
    order_res = client.post("/api/v1/cliente/pedidos", json={
        "numero_mesa": "Mostrador",
        "tipo": "llevar",
        "modo_pago": "PAGAR_ANTES",
        "metodo_pago": "Efectivo",
        "moneda_pago": "USD",
        "detalles": [{"producto_id": prod["id"], "cantidad": 2}],
    })
    assert order_res.status_code == 201, order_res.text

    alerts_res = client.get("/api/v1/admin/stock-alertas", headers=admin_headers)
    assert alerts_res.status_code == 200
    assert any(item["id"] == insumo["id"] for item in alerts_res.json()["insumos"])

    # Restock insumo via purchase endpoint -> re-enables product cleanly
    compra_res = client.post("/api/v1/admin/inventario/compra", headers=admin_headers, json={
        "insumo_id": insumo["id"],
        "cantidad": 6.0,
        "costo_unitario": 1.75,
        "proveedor": "Carnes QA",
    })
    assert compra_res.status_code == 200, compra_res.text
    assert compra_res.json()["stock_nuevo"] == pytest.approx(6.0)

    prods_map = {p["id"]: p for p in client.get("/api/v1/admin/productos", headers=admin_headers).json()}
    assert prods_map[prod["id"]]["disponible"] is True

    # Pay order, check profitability, CSV export & SLA endpoints
    cashier_headers = _login(client, "caja", "caja123")
    _ensure_open_shift(client, cashier_headers)
    order_data = order_res.json()
    pay_res = client.post(f"/api/v1/caja/pedidos/{order_data['id']}/cobrar", headers=cashier_headers, json={
        "metodo_pago": "Efectivo",
        "monto_recibido": order_data["total"],
        "moneda_pago": "USD",
    })
    assert pay_res.status_code == 200, pay_res.text

    prof = client.get("/api/v1/admin/reportes/rentabilidad", headers=admin_headers)
    assert prof.status_code == 200
    assert prof.json()["total_ingresos_usd"] > 0

    csv_res = client.get("/api/v1/admin/reportes/exportar?formato=excel", headers=admin_headers)
    assert csv_res.status_code == 200
    assert "Pedido_ID;Fecha;Factura" in csv_res.text

    sla_res = client.get("/api/v1/admin/cocina/sla", headers=admin_headers)
    assert sla_res.status_code == 200
    assert "tiempo_promedio_min" in sla_res.json()
    client.put(f"/api/v1/admin/productos/{prod['id']}", headers=admin_headers, json={"activo": False})


def test_coupons_schedule_tips_mixed_payments_split_bill_favorites_reviews_turnos_and_waiter(client):
    from datetime import datetime, timedelta
    admin_headers = _login(client, "admin", "admin123")
    cashier_headers = _login(client, "caja", "caja123")
    w_user, w_pass, _ = _create_user_in_db("mesero")
    waiter_headers = _login(client, w_user, w_pass)
    k_user, k_pass, _ = _create_user_in_db("cocina")
    kitchen_headers = _login(client, k_user, k_pass)
    _ensure_open_shift(client, cashier_headers)

    cat_id = client.get("/api/v1/admin/categorias", headers=admin_headers).json()[0]["id"]
    p1 = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"Plato Cupon A {uuid4().hex[:5]}",
        "precio": 20.00,
        "categoria_id": cat_id,
        "stock": 20,
    }).json()
    p2 = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"Plato Cupon B {uuid4().hex[:5]}",
        "precio": 10.00,
        "categoria_id": cat_id,
        "stock": 20,
    }).json()

    # Active coupon vs out-of-window coupon
    coupon_code = f"SAVE20_{uuid4().hex[:4].upper()}"
    active_promo = client.post("/api/v1/admin/promociones", headers=admin_headers, json={
        "titulo": "Promo Vigente Hoy",
        "descuento_pct": 20,
        "codigo_cupon": coupon_code,
        "dias_semana": "0,1,2,3,4,5,6",
        "hora_inicio": "00:00",
        "hora_fin": "23:59",
        "activo": True,
        "producto_ids": [p1["id"]],
    })
    assert active_promo.status_code == 200, active_promo.text

    now_local = datetime.now()
    closed_start = (now_local + timedelta(hours=2)).strftime("%H:00")
    closed_end = (now_local + timedelta(hours=3)).strftime("%H:00")
    expired_code = f"OFF_{uuid4().hex[:4].upper()}"
    client.post("/api/v1/admin/promociones", headers=admin_headers, json={
        "titulo": "Promo Fuera de Horario",
        "descuento_pct": 50,
        "codigo_cupon": expired_code,
        "hora_inicio": closed_start,
        "hora_fin": closed_end,
        "activo": True,
        "producto_ids": [p1["id"]],
    })

    val_ok = client.post("/api/v1/cliente/cupones/validar", json={
        "codigo_cupon": coupon_code,
        "producto_ids": [p1["id"]],
    })
    assert val_ok.status_code == 200
    assert val_ok.json()["descuento_pct"] == pytest.approx(20.0)

    val_off = client.post("/api/v1/cliente/cupones/validar", json={
        "codigo_cupon": expired_code,
        "producto_ids": [p1["id"]],
    })
    assert val_off.status_code == 404

    # Favorites CRUD
    c_user, c_pass, _ = _create_user_in_db("cliente")
    c_headers = _login(client, c_user, c_pass)
    assert client.post(f"/api/v1/cliente/favoritos/{p1['id']}", headers=c_headers).status_code == 201
    assert p1["id"] in client.get("/api/v1/cliente/favoritos", headers=c_headers).json()
    assert client.delete(f"/api/v1/cliente/favoritos/{p1['id']}", headers=c_headers).status_code == 200

    # Order with Coupon (-20% on $20 -> $16 subtotal) + Tip ($2.00)
    cfg = client.get("/api/v1/cliente/configuraciones-publicas").json()
    iva_active = str(cfg.get("iva_activo", "true")).lower() not in ("false", "0", "no", "off")
    tax_rate = float(cfg.get("porcentaje_iva", 16)) if iva_active else 0.0
    pkg_fee = float(cfg.get("costo_empaque", 3))

    ord_res = client.post("/api/v1/cliente/pedidos", headers=c_headers, json={
        "numero_mesa": "Mostrador",
        "tipo": "llevar",
        "modo_pago": "PAGAR_ANTES",
        "metodo_pago": "Efectivo",
        "moneda_pago": "USD",
        "codigo_cupon": coupon_code,
        "propina": 2.00,
        "detalles": [{"producto_id": p1["id"], "cantidad": 1}],
    })
    assert ord_res.status_code == 201, ord_res.text
    ord_data = ord_res.json()
    assert ord_data["subtotal"] == pytest.approx(16.00)
    assert ord_data["descuento"] == pytest.approx(4.00)
    assert ord_data["propina"] == pytest.approx(2.00)
    expected_tax = round(16.00 * tax_rate / 100.0, 2)
    assert ord_data["total"] == pytest.approx(round(16.00 + expected_tax + pkg_fee + 2.00, 2))

    # Public turnos board before and after LISTO + Post-delivery order review
    turnos_before = client.get("/api/v1/cliente/turnos").json()
    assert any(item["id"] == ord_data["id"] for item in turnos_before["preparando"])

    assert client.post(f"/api/v1/caja/pedidos/{ord_data['id']}/cobrar", headers=cashier_headers, json={
        "metodo_pago": "Efectivo",
        "monto_recibido": ord_data["total"],
        "moneda_pago": "USD",
    }).status_code == 200
    assert client.put(f"/api/v1/cocina/pedidos/{ord_data['id']}/estado?estado=LISTO", headers=kitchen_headers).status_code == 200
    turnos_after = client.get("/api/v1/cliente/turnos").json()
    assert any(item["id"] == ord_data["id"] for item in turnos_after["listos"])

    rev_res = client.post(
        f"/api/v1/cliente/pedidos/{ord_data['id']}/resena",
        headers=c_headers,
        json={"estrellas": 5, "comentario": "Excelente comida y tiempo de entrega"},
    )
    assert rev_res.status_code == 201, rev_res.text
    assert client.post(
        f"/api/v1/cliente/pedidos/{ord_data['id']}/resena",
        headers=c_headers,
        json={"estrellas": 4, "comentario": "Duplicado"},
    ).status_code == 409

    # Mesa zona + Waiter order + Split bill + Mixed payment + Corte X
    mesa_num = 88
    client.delete(f"/api/v1/admin/mesas/{mesa_num}", headers=admin_headers)
    assert client.post("/api/v1/admin/mesas", headers=admin_headers, json={
        "numero_mesa": mesa_num,
        "capacidad": 4,
        "zona": "Terraza",
    }).status_code == 200
    mesero_mesas = client.get("/api/v1/mesero/mesas", headers=waiter_headers).json()
    assert any(m["numero_mesa"] == mesa_num and m["zona"] == "Terraza" for m in mesero_mesas)

    waiter_ord = client.post("/api/v1/mesero/pedidos", headers=waiter_headers, json={
        "numero_mesa": f"Mesa {mesa_num}",
        "tipo": "mesa",
        "modo_pago": "PAGAR_DESPUES",
        "detalles": [
            {"producto_id": p1["id"], "cantidad": 1},
            {"producto_id": p2["id"], "cantidad": 1},
        ],
    })
    assert waiter_ord.status_code == 201, waiter_ord.text
    waiter_ord_id = waiter_ord.json()["id"]

    # Split bill into 2 equal checks, then pay one with mixed payments (Efectivo + Punto de Venta)
    split_res = client.post(f"/api/v1/caja/pedidos/{waiter_ord_id}/dividir", headers=cashier_headers, json={
        "modo": "igual",
        "partes": 2,
    })
    assert split_res.status_code == 200, split_res.text
    child_id = split_res.json()["nuevos_pedidos"][0]

    pending_map = {o["id"]: o for o in client.get("/api/v1/caja/pedidos-pendientes", headers=cashier_headers).json()}
    part_total = float(pending_map[child_id]["total"])
    half1 = round(part_total / 2.0, 2)
    half2 = round(part_total - half1, 2)

    shift_before = client.get("/api/v1/caja/turno-activo", headers=cashier_headers).json()["esperado_por_metodo"]
    mix_res = client.post(f"/api/v1/caja/pedidos/{child_id}/cobrar", headers=cashier_headers, json={
        "metodo_pago": "Pago Mixto",
        "monto_recibido": part_total,
        "moneda_pago": "USD",
        "pagos_mixtos": [
            {"metodo_pago": "Efectivo", "monto_usd": half1, "moneda": "USD"},
            {"metodo_pago": "Punto de Venta", "monto_usd": half2, "moneda": "USD"},
        ],
    })
    assert mix_res.status_code == 200, mix_res.text

    shift_after = client.get("/api/v1/caja/turno-activo", headers=cashier_headers).json()["esperado_por_metodo"]
    assert shift_after["Efectivo"] == pytest.approx(round(shift_before["Efectivo"] + half1, 2))
    assert shift_after["Punto de Venta"] == pytest.approx(round(shift_before["Punto de Venta"] + half2, 2))

    corte_x = client.get("/api/v1/caja/corte-x", headers=cashier_headers)
    assert corte_x.status_code == 200
    assert corte_x.json()["total_propinas"] >= 2.0

    # Cleanup test promo and synthetic test products
    client.delete(f"/api/v1/admin/promociones/{active_promo.json()['id']}", headers=admin_headers)
    client.put(f"/api/v1/admin/productos/{p1['id']}", headers=admin_headers, json={"activo": False})
    client.put(f"/api/v1/admin/productos/{p2['id']}", headers=admin_headers, json={"activo": False})


def test_promotion_global_price_bundle_pricing_and_validation(client):
    admin_headers = _login(client, "admin", "admin123")
    cats = client.get("/api/v1/admin/categorias", headers=admin_headers).json()
    cat_id = cats[0]["id"]

    # Create two dedicated products with known regular prices and sufficient stock
    p1_res = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"Combo Burger {uuid4().hex[:5]}",
        "precio": 12.00,
        "categoria_id": cat_id,
        "stock": 10,
        "disponible": True,
    })
    p2_res = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"Combo Shake {uuid4().hex[:5]}",
        "precio": 8.00,
        "categoria_id": cat_id,
        "stock": 10,
        "disponible": True,
    })
    assert p1_res.status_code == 200, p1_res.text
    assert p2_res.status_code == 200, p2_res.text
    p1 = p1_res.json()
    p2 = p2_res.json()

    # Non-positive global price rejected with 422
    bad_promo = client.post("/api/v1/admin/promociones", headers=admin_headers, json={
        "titulo": "Combo Precio Cero",
        "descuento_pct": 0,
        "precio_global": 0,
        "activo": True,
        "producto_ids": [p1["id"], p2["id"]],
    })
    assert bad_promo.status_code == 422

    # Create promo with global bundle price $14.00 (vs $20.00 individual sum)
    created = client.post("/api/v1/admin/promociones", headers=admin_headers, json={
        "titulo": f"Combo Global {uuid4().hex[:5]}",
        "descripcion": "2 productos por un precio global único",
        "descuento_pct": 30,
        "precio_global": 14.00,
        "codigo_cupon": f"GLOB{uuid4().hex[:4].upper()}",
        "activo": True,
        "producto_ids": [p1["id"], p2["id"]],
    })
    assert created.status_code == 200, created.text
    promo = created.json()
    assert promo["precio_global"] == pytest.approx(14.00)
    assert set(promo["producto_ids"]) == {p1["id"], p2["id"]}

    public_promos = client.get("/api/v1/cliente/promociones").json()
    public_match = next(item for item in public_promos if item["id"] == promo["id"])
    assert public_match["precio_global"] == pytest.approx(14.00)

    # Order missing one required product in the bundle must be rejected cleanly
    incomplete = client.post("/api/v1/cliente/pedidos", json={
        "numero_mesa": "Para Llevar",
        "tipo": "llevar",
        "modo_pago": "PAGAR_ANTES",
        "metodo_pago": "Efectivo",
        "moneda_pago": "USD",
        "detalles": [{"producto_id": p1["id"], "cantidad": 1}],
        "promociones": [{"promocion_id": promo["id"], "cantidad": 1}],
    })
    assert incomplete.status_code == 422
    assert "requiere todos los productos seleccionados" in incomplete.json()["detail"].lower()

    # Valid order with 2 bundles pays 2 * $14.00 = $28.00 subtotal (saving $12.00 vs $40.00)
    cfg = client.get("/api/v1/cliente/configuraciones-publicas").json()
    iva_active = str(cfg.get("iva_activo", "true")).lower() not in ("false", "0", "no", "off")
    tax_rate = float(cfg.get("porcentaje_iva", 16)) if iva_active else 0.0
    pkg_fee = float(cfg.get("costo_empaque", 3))

    order_res = client.post("/api/v1/cliente/pedidos", json={
        "numero_mesa": "Para Llevar",
        "tipo": "llevar",
        "modo_pago": "PAGAR_ANTES",
        "metodo_pago": "Efectivo",
        "moneda_pago": "USD",
        "detalles": [
            {"producto_id": p1["id"], "cantidad": 2},
            {"producto_id": p2["id"], "cantidad": 2},
        ],
        "promociones": [{"promocion_id": promo["id"], "cantidad": 2}],
    })
    assert order_res.status_code == 201, order_res.text
    order = order_res.json()
    assert order["subtotal"] == pytest.approx(28.00)
    assert order["descuento"] == pytest.approx(12.00)
    expected_tax = round(28.00 * tax_rate / 100.0, 2)
    assert order["impuesto"] == pytest.approx(expected_tax)
    assert order["total"] == pytest.approx(round(28.00 + expected_tax + pkg_fee, 2))

    # Both bundled products had stock deducted by 2
    prods_after = {p["id"]: p for p in client.get("/api/v1/admin/productos", headers=admin_headers).json()}
    assert prods_after[p1["id"]]["stock"] == 8
    assert prods_after[p2["id"]]["stock"] == 8

    # Update global price and verify
    updated = client.put(f"/api/v1/admin/promociones/{promo['id']}", headers=admin_headers, json={
        "titulo": promo["titulo"],
        "descripcion": promo["descripcion"],
        "descuento_pct": 25,
        "precio_global": 15.50,
        "codigo_cupon": promo["codigo_cupon"],
        "activo": True,
        "producto_ids": [p1["id"], p2["id"]],
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["precio_global"] == pytest.approx(15.50)

    # Cleanup test promo
    assert client.delete(f"/api/v1/admin/promociones/{promo['id']}", headers=admin_headers).status_code == 200


def test_media_db_storage_cliente_scope_and_database_format(client):
    from pathlib import Path
    from backend.scripts.seed_data import seed

    root = Path(__file__).resolve().parent.parent
    cliente_js = (root / "backend/static/js/cliente-toon.js").read_text(encoding="utf-8")
    cocina_js = (root / "backend/static/js/cocina.js").read_text(encoding="utf-8")
    assert "\nfunction computeCartPricingSnapshot(" in cliente_js
    assert "\nfunction setKDSModeFilter(" in cocina_js
    assert "\nfunction setKDSSearch(" in cocina_js

    admin_headers = _login(client, "admin", "admin123")
    cat_id = client.get("/api/v1/admin/categorias", headers=admin_headers).json()[0]["id"]

    # 1. Upload PNG & JPEG (even with image/jpg MIME) -> stored in DB and served publicly
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    up_png = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        files={"file": ("burger.png", png_bytes, "image/png")},
    )
    assert up_png.status_code == 200, up_png.text
    up_data = up_png.json()
    assert up_data["provider"] == "database"
    assert up_data["url"].startswith("/api/v1/cliente/media/")

    jpg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 24
    up_jpg = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        files={"file": ("combo.JPG", jpg_bytes, "image/jpg")},
    )
    assert up_jpg.status_code == 200, up_jpg.text
    assert up_jpg.json()["url"].startswith("/api/v1/cliente/media/")

    served = client.get(up_data["url"])
    assert served.status_code == 200
    assert served.content == png_bytes
    assert served.headers["content-type"].startswith("image/png")

    prod_res = client.post("/api/v1/admin/productos", headers=admin_headers, json={
        "nombre": f"Foto DB {uuid4().hex[:5]}",
        "precio": 9.5,
        "categoria_id": cat_id,
        "imagen_url": up_data["url"],
        "stock": 10,
    })
    assert prod_res.status_code == 200, prod_res.text
    prod_id = prod_res.json()["id"]

    public_prods = client.get("/api/v1/cliente/productos").json()
    assert any(p["id"] == prod_id and p["imagen_url"] == up_data["url"] for p in public_prods)

    # 2. Format DB endpoint requires explicit confirmation and wipes records cleanly
    bad_fmt = client.post(
        "/api/v1/admin/backups/formatear-bd",
        headers=admin_headers,
        json={"confirmacion": "NO"},
    )
    assert bad_fmt.status_code == 422

    try:
        ok_fmt = client.post(
            "/api/v1/admin/backups/formatear-bd",
            headers=admin_headers,
            json={"confirmacion": "FORMATEAR"},
        )
        assert ok_fmt.status_code == 200, ok_fmt.text
        assert client.get("/api/v1/cliente/productos").json() == []
        assert client.get("/api/v1/cliente/categorias").json() == []
        assert client.get(up_data["url"]).status_code == 404
        users_left = client.get("/api/v1/admin/usuarios", headers=admin_headers).json()
        assert len(users_left) == 1 and users_left[0]["rol"] == "admin"

        root = Path(__file__).resolve().parents[1]
        cliente_html = (root / "backend" / "static" / "cliente" / "app.html").read_text(encoding="utf-8")
        cliente_js = (root / "backend" / "static" / "js" / "cliente-toon.js").read_text(encoding="utf-8")
        admin_html = (root / "backend" / "static" / "admin" / "index.html").read_text(encoding="utf-8")
        admin_js = (root / "backend" / "static" / "js" / "admin-toon.js").read_text(encoding="utf-8")

        assert 'id="product-gallery-lightbox"' in cliente_html
        assert 'id="modal-product-thumb-strip"' in cliente_html
        assert "openProductGalleryFromCard" in cliente_js
        assert "openDishLightbox" in cliente_js
        assert "_getProductGalleryItems" in cliente_js
        assert "uploadProductGalleryFiles" in admin_html
        assert "uploadProductGalleryFiles" in admin_js
    finally:
        seed()
