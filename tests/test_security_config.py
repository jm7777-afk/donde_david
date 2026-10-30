import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings
from backend.app.core.security import get_password_hash, verify_password
from backend.app.schemas.schemas import CobrarPedidoRequest, DetallePedidoItem
from backend.scripts.seed_data import seed


def test_production_requires_secret_database_and_exact_origins(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://restaurant.example")
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings()

    monkeypatch.setenv("SECRET_KEY", "a" * 48)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./restaurant.db")
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings()

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS"):
        Settings()


def test_production_normalizes_postgres_url(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 48)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://restaurant.example")

    assert Settings().DATABASE_URL == "postgresql+psycopg://user:pass@localhost/db"


def test_passwords_are_always_hashed():
    password = "not-a-demo-password"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)
    assert not verify_password(password, password)

def test_demo_seed_is_blocked_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="disabled in production"):
        seed()


def test_order_and_payment_values_reject_invalid_inputs():
    with pytest.raises(ValidationError):
        DetallePedidoItem(producto_id=1, cantidad=0)
    with pytest.raises(ValidationError):
        CobrarPedidoRequest(metodo_pago="Efectivo", monto_recibido=-1)
    with pytest.raises(ValidationError):
        CobrarPedidoRequest(metodo_pago="Efectivo", monto_recibido=float("inf"))
