from datetime import datetime, timedelta, timezone
from urllib.error import URLError

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.models.configuracion import Configuracion
from backend.app.services import exchange_rate


@pytest.fixture
def rate_db():
    engine = create_engine("sqlite:///:memory:")
    Configuracion.__table__.create(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_manual_rate_stays_active_until_explicit_refresh(rate_db, monkeypatch):
    exchange_rate.save_manual_rate(rate_db, 123.45)
    monkeypatch.setattr(exchange_rate, "_parse_provider_rate", lambda: pytest.fail("Unexpected provider request"))

    result = exchange_rate.get_bcv_rate(rate_db)

    assert result["tasa_cambio_bs"] == 123.45
    assert result["tasa_fuente"] == "Manual (administrador)"
    assert result["tasa_estado"] == "manual"


def test_provider_refresh_updates_cached_rate(rate_db, monkeypatch):
    updated = datetime.now(timezone.utc)
    monkeypatch.setattr(exchange_rate, "_parse_provider_rate", lambda: (150.25, updated))

    result = exchange_rate.get_bcv_rate(rate_db)

    assert result["tasa_cambio_bs"] == 150.25
    assert result["tasa_fuente"] == "DolarApi (fuente oficial)"
    assert result["tasa_respaldo"] is False


def test_provider_failure_returns_last_saved_rate(rate_db, monkeypatch):
    rate_db.add_all([
        Configuracion(clave="tasa_cambio_bs", valor="140.2500"),
        Configuracion(clave="tasa_fuente", valor="DolarApi (fuente oficial)"),
        Configuracion(
            clave="tasa_actualizada_at",
            valor=(datetime.now(timezone.utc) - timedelta(hours=49)).isoformat(),
        ),
    ])
    rate_db.commit()

    def unavailable():
        raise URLError("provider offline")

    monkeypatch.setattr(exchange_rate, "_parse_provider_rate", unavailable)
    result = exchange_rate.get_bcv_rate(rate_db)

    assert result["tasa_cambio_bs"] == 140.25
    assert result["tasa_estado"] == "respaldo"
    assert result["tasa_respaldo"] is True
