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
