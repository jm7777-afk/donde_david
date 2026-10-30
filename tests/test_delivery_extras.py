import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    app.state.limiter.reset()
    with TestClient(app) as test_client:
        yield test_client


def test_configured_product_extras_are_authoritative_and_delivery_coordinates_are_validated(client):
    login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "admin",
        "password": "admin123",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    suffix = uuid4().hex[:12]
    category = client.post("/api/v1/admin/categorias", headers=headers, json={
        "nombre": f"Categoría extras {suffix}",
    })
    assert category.status_code == 200, category.text
    product = client.post("/api/v1/admin/productos", headers=headers, json={
        "nombre": f"Producto extras {suffix}",
        "categoria_id": category.json()["id"],
        "precio": 3.25,
        "stock": 5,
        "extras_json": '[{"nombre":"Extra queso","precio":1.25}]',
        "media_json": '[{"tipo":"imagen","url":"https://example.com/product.webp"}]',
    })
    assert product.status_code == 200, product.text
    product_id = product.json()["id"]
    assert json.loads(product.json()["extras_json"]) == [{"nombre": "Extra queso", "precio": 1.25}]
    assert json.loads(product.json()["media_json"]) == [{
        "tipo": "imagen",
        "url": "https://example.com/product.webp",
    }]

    order = {
        "numero_mesa": "Delivery",
        "tipo": "delivery",
        "metodo_pago": "Efectivo",
        "nombre_cliente_delivery": "Cliente QA",
        "telefono_delivery": "04120000000",
        "direccion_delivery": "Punto de prueba",
        "delivery_lat": 10.4806,
        "delivery_lng": -66.9036,
        "detalles": [{
            "producto_id": product_id,
            "cantidad": 2,
            "personalizaciones": {"extras": ["Extra queso"]},
        }],
    }
    unauthorized_extra = {
        **order,
        "detalles": [{
            **order["detalles"][0],
            "personalizaciones": {"extras": ["Extra no configurado"]},
        }],
    }
    rejected = client.post("/api/v1/cliente/pedidos", json=unauthorized_extra)
    assert rejected.status_code == 422, rejected.text

    created = client.post("/api/v1/cliente/pedidos", json=order)
    assert created.status_code == 201, created.text
    created_order = created.json()
    assert created_order["subtotal"] == 9.0
    assert created_order["delivery_lat"] == 10.4806
    assert created_order["delivery_lng"] == -66.9036
    assert created_order["detalles"][0]["precio_unitario"] == 4.5
    assert json.loads(created_order["detalles"][0]["personalizaciones"])["extras"] == ["Extra queso"]

    order["delivery_lng"] = None
    invalid_coordinates = client.post("/api/v1/cliente/pedidos", json=order)
    assert invalid_coordinates.status_code == 422
