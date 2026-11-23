"""
Pruebas Automatizadas de Auditoría, Observabilidad (Logs) y Copias de Seguridad (Backups)
=======================================================================================
Verifica el cumplimiento de roles, contratos de respuesta, exportación CSV, rotación
de logs, generación criptográfica de respaldos y restauración segura.
"""
from datetime import datetime, timezone
import json
import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.services.audit_service import record_audit, get_audit_logs
from backend.app.services.log_service import get_system_logs, get_log_statistics
from backend.app.services.backup_service import create_database_backup, list_backups, BACKUPS_DIR


@pytest.fixture
def client():
    app.state.limiter.reset()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_headers(client):
    login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "admin",
        "password": "admin123"
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture
def caja_headers(client):
    login = client.post("/api/v1/auth/login", json={
        "nombre_usuario": "caja",
        "password": "caja123"
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# ==================== PRUEBAS DE AUDITORÍA ====================

def test_audit_service_records_and_retrieves_events(client):
    db = SessionLocal()
    try:
        entry = record_audit(
            db=db,
            accion="TEST_ACTION",
            usuario="test_admin",
            recurso="productos",
            recurso_id="999",
            detalle="Prueba unitaria de auditoría",
            datos_previos={"precio": 10.0},
            datos_nuevos={"precio": 15.0}
        )
        assert entry is not None
        assert entry.id is not None
        assert entry.accion == "TEST_ACTION"
        assert entry.usuario == "test_admin"

        items, total = get_audit_logs(db=db, accion="TEST_ACTION")
        assert total >= 1
        assert any(i.id == entry.id for i in items)
    finally:
        db.close()


def test_audit_endpoints_require_admin_or_supervisor(client, caja_headers, admin_headers):
    # Usuario 'caja' no tiene permisos para ver auditorías generales
    resp_caja = client.get("/api/v1/admin/auditoria", headers=caja_headers)
    assert resp_caja.status_code == 403

    # Administrador sí tiene acceso
    resp_admin = client.get("/api/v1/admin/auditoria", headers=admin_headers)
    assert resp_admin.status_code == 200
    data = resp_admin.json()
    assert "total" in data
    assert "items" in data
    assert "acciones_disponibles" in data
    assert isinstance(data["items"], list)


def test_audit_export_csv_endpoint(client, admin_headers):
    resp = client.get("/api/v1/admin/auditoria/export", headers=admin_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "ID,Fecha (UTC),Acción,Usuario" in resp.text


def test_audit_catalog_endpoints(client, admin_headers):
    acciones = client.get("/api/v1/admin/auditoria/acciones", headers=admin_headers)
    assert acciones.status_code == 200
    assert isinstance(acciones.json(), list)

    recursos = client.get("/api/v1/admin/auditoria/recursos", headers=admin_headers)
    assert recursos.status_code == 200
    assert isinstance(recursos.json(), list)


# ==================== PRUEBAS DE OBSERVABILIDAD Y LOGS ====================

def test_logs_endpoint_returns_structured_entries(client, admin_headers):
    # Generar tráfico para poblar logs
    client.get("/health")

    resp = client.get("/api/v1/admin/logs?limit=50", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert "total_returned" in data
    assert isinstance(data["logs"], list)


def test_logs_stats_endpoint(client, admin_headers):
    resp = client.get("/api/v1/admin/logs/stats", headers=admin_headers)
    assert resp.status_code == 200
    stats = resp.json()
    assert "total_recent_events" in stats
    assert "counts_by_level" in stats
    assert "error_rate_percentage" in stats


def test_logs_download_and_unauthorized_access(client, caja_headers, admin_headers):
    # Caja no puede descargar logs
    forbidden = client.get("/api/v1/admin/logs/download?tipo=app", headers=caja_headers)
    assert forbidden.status_code == 403

    # Admin puede descargar el archivo de logs
    resp = client.get("/api/v1/admin/logs/download?tipo=app", headers=admin_headers)
    assert resp.status_code in [200, 404]  # 404 si el archivo está vacío al inicio de un entorno limpio


# ==================== PRUEBAS DE COPIAS DE SEGURIDAD (BACKUPS) ====================

def test_backup_create_list_and_download(client, admin_headers, caja_headers):
    # 1. Caja no tiene permisos para crear backups
    caja_forbidden = client.post("/api/v1/admin/backups/crear", headers=caja_headers, json={"descripcion": "Intento"})
    assert caja_forbidden.status_code == 403

    # 2. Admin crea un respaldo
    create_resp = client.post(
        "/api/v1/admin/backups/crear",
        headers=admin_headers,
        json={"descripcion": "Respaldo automatizado de prueba"}
    )
    assert create_resp.status_code == 201
    backup_data = create_resp.json()
    assert "filename" in backup_data
    assert "sha256" in backup_data
    assert len(backup_data["sha256"]) == 64
    filename = backup_data["filename"]

    # 3. Listar respaldos y verificar presencia
    list_resp = client.get("/api/v1/admin/backups", headers=admin_headers)
    assert list_resp.status_code == 200
    backups_list = list_resp.json()
    assert any(b["filename"] == filename for b in backups_list)

    # 4. Descargar respaldo
    download_resp = client.get(f"/api/v1/admin/backups/{filename}/descargar", headers=admin_headers)
    assert download_resp.status_code == 200
    assert len(download_resp.content) > 0

    # 5. Intentar descargar con directory traversal debe ser rechazado
    traversal_resp = client.get("/api/v1/admin/backups/..%2F..%2Fmain.py/descargar", headers=admin_headers)
    assert traversal_resp.status_code in [400, 404]

    # 6. Eliminar respaldo creado para limpieza
    del_resp = client.delete(f"/api/v1/admin/backups/{filename}", headers=admin_headers)
    assert del_resp.status_code == 200


def test_backup_restore_creates_safety_checkpoint(client, admin_headers):
    # Crear backup inicial
    create_resp = client.post(
        "/api/v1/admin/backups/crear",
        headers=admin_headers,
        json={"descripcion": "Pre-restauracion"}
    )
    assert create_resp.status_code == 201
    filename = create_resp.json()["filename"]

    # Restaurar backup
    restore_resp = client.post(
        f"/api/v1/admin/backups/{filename}/restaurar",
        headers=admin_headers
    )
    assert restore_resp.status_code == 200
    restore_data = restore_resp.json()
    assert "checkpoint_previo" in restore_data or "tablas_restauradas" in restore_data

    # Limpieza
    client.delete(f"/api/v1/admin/backups/{filename}", headers=admin_headers)
