import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.configuracion import Configuracion

logger = logging.getLogger(__name__)
RATE_CACHE_MINUTES = 30
RATE_MAX_AGE = timedelta(hours=48)


def _get_config(db: Session, key: str) -> Configuracion | None:
    return db.query(Configuracion).filter(Configuracion.clave == key).first()


def _set_config(db: Session, key: str, value: str) -> None:
    config = _get_config(db, key)
    if config is None:
        db.add(Configuracion(clave=key, valor=value))
    else:
        config.valor = value


def _read_saved_rate(db: Session) -> dict:
    rate = _get_config(db, "tasa_cambio_bs")
    source = _get_config(db, "tasa_fuente")
    updated = _get_config(db, "tasa_actualizada_at")
    if rate is None:
        return {"tasa_cambio_bs": None, "tasa_fuente": None, "tasa_actualizada_at": None}
    return {
        "tasa_cambio_bs": float(rate.valor),
        "tasa_fuente": source.valor if source else "Manual (origen sin registrar)",
        "tasa_actualizada_at": updated.valor if updated else None,
    }


def _parse_provider_rate() -> tuple[float, datetime]:
    request = Request(
        settings.BCV_RATE_API_URL,
        headers={"Accept": "application/json", "User-Agent": "DondeDavid/2.0"},
    )
    with urlopen(request, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not isinstance(data, dict) or data.get("moneda") != "USD" or data.get("fuente") != "oficial":
        raise ValueError("El proveedor no devolvió una tasa oficial USD reconocible.")
    rate = float(data.get("promedio") or 0)
    if not 0 < rate < 1_000_000:
        raise ValueError("La tasa recibida está fuera de rango.")

    updated = datetime.fromisoformat(data["fechaActualizacion"].replace("Z", "+00:00"))
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if updated > now + timedelta(minutes=10) or now - updated > RATE_MAX_AGE:
        raise ValueError("La tasa del proveedor está vencida o tiene una fecha futura.")
    return rate, updated.astimezone(timezone.utc)


def get_bcv_rate(db: Session, force_refresh: bool = False) -> dict:
    saved = _read_saved_rate(db)
    now = datetime.now(timezone.utc)
    if saved["tasa_cambio_bs"] and saved["tasa_fuente"] == "Manual (administrador)" and not force_refresh:
        return {**saved, "tasa_estado": "manual", "tasa_respaldo": True}
    if saved["tasa_cambio_bs"] and saved["tasa_actualizada_at"] and not force_refresh:
        try:
            updated = datetime.fromisoformat(saved["tasa_actualizada_at"].replace("Z", "+00:00"))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if saved["tasa_fuente"] == "DolarApi (fuente oficial)" and now - updated < timedelta(minutes=RATE_CACHE_MINUTES):
                return {**saved, "tasa_estado": "actualizada", "tasa_respaldo": False}
        except ValueError:
            logger.warning("Stored exchange-rate timestamp is invalid; refreshing from provider.")

    try:
        rate, updated = _parse_provider_rate()
        timestamp = updated.isoformat()
        _set_config(db, "tasa_cambio_bs", f"{rate:.4f}")
        _set_config(db, "tasa_fuente", "DolarApi (fuente oficial)")
        _set_config(db, "tasa_actualizada_at", timestamp)
        db.commit()
        return {
            "tasa_cambio_bs": rate,
            "tasa_fuente": "DolarApi (fuente oficial)",
            "tasa_actualizada_at": timestamp,
            "tasa_estado": "actualizada",
            "tasa_respaldo": False,
        }
    except (URLError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("BCV rate provider unavailable or invalid: %s", exc)
        db.rollback()
        saved = _read_saved_rate(db)
        if saved["tasa_cambio_bs"] is not None:
            return {**saved, "tasa_estado": "respaldo", "tasa_respaldo": True}
        return {
            **saved,
            "tasa_estado": "no_disponible",
            "tasa_respaldo": True,
        }


def save_manual_rate(db: Session, rate: float) -> dict:
    if not 0 < rate < 1_000_000:
        raise ValueError("La tasa debe ser mayor que cero y menor que 1.000.000.")
    timestamp = datetime.now(timezone.utc).isoformat()
    _set_config(db, "tasa_cambio_bs", f"{rate:.4f}")
    _set_config(db, "tasa_fuente", "Manual (administrador)")
    _set_config(db, "tasa_actualizada_at", timestamp)
    db.commit()
    return {
        "tasa_cambio_bs": rate,
        "tasa_fuente": "Manual (administrador)",
        "tasa_actualizada_at": timestamp,
        "tasa_estado": "manual",
        "tasa_respaldo": True,
    }
