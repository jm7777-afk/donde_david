import sys
import os
import unittest

os.environ["TESTING"] = "true"
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_restaurante.db")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.core.database import Base, engine
from backend.scripts.seed_data import seed
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
seed()

from fastapi.testclient import TestClient
from backend.app.main import app

client = None

class TestDondeDavidSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global client
        client = TestClient(app)
        client.__enter__()

    @classmethod
    def tearDownClass(cls):
        client.__exit__(None, None, None)

    def test_01_health(self):
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)

    def test_02_login_and_register(self):
        res = client.post("/api/v1/auth/login", json={"nombre_usuario": "admin", "password": "admin123"})
        self.assertEqual(res.status_code, 200)
        TestDondeDavidSystem.token = res.json()["access_token"]

        # Register new client
        reg_payload = {
            "nombre": "Test",
            "apellido": "User",
            "email": "testuser@mail.com",
            "telefono": "+502 9999 8888",
            "nombre_usuario": "testuser",
            "password": "testuser1234"
        }
        res_reg = client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(res_reg.status_code, 200)
        self.assertEqual(res_reg.json()["usuario"]["puntos_fidelidad"], 50)

    def test_03_mesas_and_qr(self):
        headers = {"Authorization": f"Bearer {TestDondeDavidSystem.token}"}
        res = client.get("/api/v1/admin/mesas", headers=headers)
        self.assertEqual(res.status_code, 200)
        mesas = res.json()
        self.assertEqual(len(mesas), 20)

        # Get QR info for Mesa 3
        res_qr = client.get("/api/v1/admin/mesas/3/qr", headers=headers)
        self.assertEqual(res_qr.status_code, 200)
        self.assertIn("qr_image_url", res_qr.json())

    def test_04_insumos_inventory(self):
        headers = {"Authorization": f"Bearer {TestDondeDavidSystem.token}"}
        res = client.get("/api/v1/admin/insumos", headers=headers)
        self.assertEqual(res.status_code, 200)
        insumos = res.json()
        self.assertGreater(len(insumos), 0)

    def test_05_promociones(self):
        res = client.get("/api/v1/cliente/promociones")
        self.assertEqual(res.status_code, 200)
        promos = res.json()
        self.assertGreater(len(promos), 0)

    def test_06_puntos_canje(self):
        # The development seed starts with zero points; verify canje against the current balance.
        res_log = client.post("/api/v1/auth/login", json={"nombre_usuario": "javier", "password": "javier123"})
        token_j = res_log.json()["access_token"]
        headers = {"Authorization": "Bearer " + token_j}
        history = client.get("/api/v1/cliente/puntos/historial", headers=headers)
        self.assertEqual(history.status_code, 200)
        points_before = history.json()["puntos_actuales"]

        res_canje = client.post("/api/v1/cliente/puntos/canjear?recompensa=Papas%20Gratis", headers=headers)
        if points_before >= 100:
            self.assertEqual(res_canje.status_code, 200, res_canje.text)
            self.assertEqual(res_canje.json()["puntos_restantes"], points_before - 100)
        else:
            self.assertEqual(res_canje.status_code, 400, res_canje.text)

if __name__ == "__main__":
    unittest.main()
