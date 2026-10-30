import sys
import os
import unittest

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_restaurante.db")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from backend.app.main import app

client = None

class TestRestauranteAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global client
        client = TestClient(app)
        client.__enter__()

    @classmethod
    def tearDownClass(cls):
        client.__exit__(None, None, None)

    def test_01_health_check(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_02_login_admin(self):
        response = client.post("/api/v1/auth/login", json={
            "nombre_usuario": "admin",
            "password": "admin123"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["usuario"]["rol"], "admin")
        TestRestauranteAPI.admin_token = data["access_token"]

    def test_03_login_caja(self):
        response = client.post("/api/v1/auth/login", json={
            "nombre_usuario": "caja",
            "password": "caja123"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        TestRestauranteAPI.caja_token = data["access_token"]

    def test_04_get_menu(self):
        response = client.get("/api/v1/cliente/productos")
        self.assertEqual(response.status_code, 200)
        prods = response.json()
        self.assertGreater(len(prods), 0)
        TestRestauranteAPI.producto_id = prods[0]["id"]

    def test_05_crear_pedido_cliente_qr(self):
        payload = {
            "numero_mesa": "Mesa 5",
            "codigo_qr": "QR_MESA_5",
            "tipo": "mesa",
            "observaciones": "Sin cebolla por favor",
            "detalles": [
                {
                    "producto_id": TestRestauranteAPI.producto_id,
                    "cantidad": 2,
                    "personalizaciones": {"opciones": ["Queso Extra"]},
                    "observaciones": "Bien cocido"
                }
            ]
        }
        response = client.post("/api/v1/cliente/pedidos", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["numero_mesa"], "Mesa 5")
        self.assertEqual(data["estado"], "PENDIENTE")
        self.assertGreater(data["total"], 0)
        TestRestauranteAPI.pedido_id = data["id"]
        TestRestauranteAPI.pedido_total = data["total"]

    def test_06_cocina_pedidos_y_cambio_estado(self):
        headers = {"Authorization": f"Bearer {TestRestauranteAPI.admin_token}"}
        
        # Consultar pedidos en cocina
        headers = {"Authorization": "Bearer " + TestRestauranteAPI.caja_token}
        response = client.get("/api/v1/cocina/pedidos", headers=headers)
        self.assertEqual(response.status_code, 200)
        pedidos = response.json()
        self.assertTrue(any(p["id"] == TestRestauranteAPI.pedido_id for p in pedidos))

        # Cambiar estado a EN_PREPARACION
        response = client.put(f"/api/v1/cocina/pedidos/{TestRestauranteAPI.pedido_id}/estado?estado=EN_PREPARACION", headers=headers)
        self.assertEqual(response.status_code, 200)

        # Cambiar estado a LISTO
        response = client.put(f"/api/v1/cocina/pedidos/{TestRestauranteAPI.pedido_id}/estado?estado=LISTO", headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_06b_cancelar_restaura_inventario(self):
        headers = {"Authorization": "Bearer " + TestRestauranteAPI.caja_token}
        product = client.get("/api/v1/cliente/productos").json()
        stock_before = next(item["stock"] for item in product if item["id"] == TestRestauranteAPI.producto_id)
        order = client.post("/api/v1/cliente/pedidos", json={
            "numero_mesa": "Mesa 5",
            "tipo": "mesa",
            "detalles": [{"producto_id": TestRestauranteAPI.producto_id, "cantidad": 1}]
        })
        self.assertEqual(order.status_code, 201)

        canceled = client.put(
            f"/api/v1/cocina/pedidos/{order.json()['id']}/estado?estado=CANCELADO",
            headers=headers
        )
        self.assertEqual(canceled.status_code, 200)
        products_after = client.get("/api/v1/cliente/productos").json()
        stock_after = next(item["stock"] for item in products_after if item["id"] == TestRestauranteAPI.producto_id)
        self.assertEqual(stock_after, stock_before)

    def test_07_caja_cobrar_pedido(self):
        headers = {"Authorization": f"Bearer {TestRestauranteAPI.caja_token}"}
        
        # Cobrar pedido
        headers = {"Authorization": "Bearer " + TestRestauranteAPI.caja_token}
        active_shift = client.get("/api/v1/caja/turno-activo", headers=headers)
        if active_shift.status_code == 404:
            opened = client.post(
                "/api/v1/caja/abrir-turno",
                json={"monto_apertura": 0},
                headers=headers,
            )
            self.assertEqual(opened.status_code, 200, opened.text)
        payload = {
            "metodo_pago": "Efectivo",
            "monto_recibido": TestRestauranteAPI.pedido_total
        }
        insufficient = client.post(
            f"/api/v1/caja/pedidos/{TestRestauranteAPI.pedido_id}/cobrar",
            json={**payload, "monto_recibido": max(0, TestRestauranteAPI.pedido_total - 0.01)},
            headers=headers
        )
        self.assertEqual(insufficient.status_code, 400)
        response = client.post(f"/api/v1/caja/pedidos/{TestRestauranteAPI.pedido_id}/cobrar", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["mensaje"], "Pago procesado exitosamente")
        self.assertGreaterEqual(data["cambio"], 0)

    def test_08_admin_dashboard_stats(self):
        headers = {"Authorization": f"Bearer {TestRestauranteAPI.admin_token}"}
        headers = {"Authorization": "Bearer " + TestRestauranteAPI.admin_token}
        response = client.get("/api/v1/admin/dashboard-stats", headers=headers)
        self.assertEqual(response.status_code, 200)
        stats = response.json()
        self.assertGreaterEqual(stats["total_pedidos"], 1)
        self.assertGreater(stats["total_ventas"], 0)
        movements = client.get("/api/v1/admin/inventario/movimientos", headers=headers)
        self.assertEqual(movements.status_code, 200)
        self.assertTrue(any(row["tipo_movimiento"] == "VENTA" for row in movements.json()))

if __name__ == "__main__":
    unittest.main()
