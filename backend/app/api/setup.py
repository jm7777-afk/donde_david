import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from backend.app.core.database import get_db
from backend.app.core.rate_limit import limiter
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.models.configuracion import Configuracion
from backend.app.models.usuario import Usuario

router = APIRouter(prefix="/setup", tags=["Módulo de Instalación Inicial (Setup Wizard)"])

LOCK_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../installed.lock"))

def check_system_installed(db: Session) -> bool:
    if os.path.exists(LOCK_FILE_PATH):
        return True
    cfg = db.query(Configuracion).filter(Configuracion.clave == "is_installed").first()
    return True if (cfg and cfg.valor.lower() == "true") else False

class SetupInstallRequest(BaseModel):
    # Datos de Marca
    nombre_restaurante: str = Field(min_length=1, max_length=150)
    logo_url: Optional[str] = "/static/images/logo-donde-david.jpg"
    color_primario: Optional[str] = "#ffb703"
    color_secundario: Optional[str] = "#ff8800"
    color_acento: Optional[str] = "#00f5d4"
    tasa_cambio_bs: Optional[float] = Field(default=None, gt=0, lt=1_000_000, allow_inf_nan=False)
    
    # Datos de Contacto
    telefono: Optional[str] = "+502 4112 5554"
    whatsapp: Optional[str] = "+502 4112 5554"
    direccion: Optional[str] = "Av. Principal #123, Ciudad"
    horario: Optional[str] = "Lunes a Domingo: 11:00 AM - 11:00 PM"
    
    # Cuenta SuperAdmin
    admin_nombre: str = Field(min_length=1, max_length=100)
    admin_apellido: str = Field(min_length=1, max_length=100)
    admin_email: EmailStr
    admin_usuario: str = Field(min_length=3, max_length=50)
    admin_password: str = Field(min_length=12, max_length=72)

@router.get("/status")
def get_setup_status(db: Session = Depends(get_db)):
    is_inst = check_system_installed(db)
    return {"is_installed": is_inst}

@router.post("/install")
@limiter.limit("5/hour")
def run_setup_install(
    request: Request,
    response: Response,
    data: SetupInstallRequest,
    db: Session = Depends(get_db)
):
    if check_system_installed(db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: El sistema ya se encuentra instalado y configurado previamente."
        )

    existing_admin = db.query(Usuario).filter(
        (Usuario.nombre_usuario == data.admin_usuario) | (Usuario.email == data.admin_email)
    ).first()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario o correo ya pertenece a una cuenta existente."
        )

    # 1. Guardar configuraciones del sistema
    config_items = [
        ("is_installed", "true", "Bandera de instalación única completada"),
        ("nombre_restaurante", data.nombre_restaurante, "Nombre comercial del negocio"),
        ("logo_url", data.logo_url or "/static/images/logo-donde-david.jpg", "Logo oficial del negocio"),
        ("color_primario", data.color_primario or "#ffb703", "Color primario de la marca"),
        ("color_secundario", data.color_secundario or "#ff8800", "Color secundario de la marca"),
        ("color_acento", data.color_acento or "#00f5d4", "Color acento de la marca"),
        ("telefono_contacto", data.telefono or "", "Teléfono principal de contacto"),
        ("whatsapp_contacto", data.whatsapp or "", "WhatsApp oficial"),
        ("direccion", data.direccion or "", "Dirección física"),
        ("horario", data.horario or "", "Horarios de atención")
    ]
    if data.tasa_cambio_bs is not None:
        config_items.extend([
            ("tasa_cambio_bs", f"{data.tasa_cambio_bs:.4f}", "Tasa de cambio manual en Bolívares"),
            ("tasa_fuente", "Manual (administrador)", "Origen de la tasa de cambio"),
            ("tasa_actualizada_at", datetime.now(timezone.utc).isoformat(), "Fecha de actualización de la tasa"),
        ])

    for clave, valor, desc in config_items:
        cfg = db.query(Configuracion).filter(Configuracion.clave == clave).first()
        if not cfg:
            db.add(Configuracion(clave=clave, valor=valor, descripcion=desc))
        else:
            cfg.valor = valor

    # 2. Crear SuperAdmin principal
    pwd_hash = get_password_hash(data.admin_password)
    admin_user = Usuario(
        nombre=data.admin_nombre,
        apellido=data.admin_apellido,
        email=data.admin_email,
        nombre_usuario=data.admin_usuario,
        contraseña_hash=pwd_hash,
        rol="admin",
        telefono=data.telefono,
        tour_completed=False,
        activo=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    # 3. Crear archivo de bloqueo permanente installed.lock
    try:
        with open(LOCK_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(f"INSTALLED_ON={data.nombre_restaurante}\nSUPERADMIN={data.admin_usuario}\nSTATUS=LOCK\n")
    except Exception as e:
        print(f"Aviso creando lock file: {e}")

    # 4. Generar Token JWT de acceso directo
    access_token = create_access_token(data={"sub": admin_user.nombre_usuario, "rol": "admin"})

    return {
        "mensaje": "¡Instalación y autoconfiguración inicial completadas con éxito!",
        "is_installed": True,
        "access_token": access_token,
        "token_type": "bearer",
        "usuario": {
            "id": admin_user.id,
            "nombre": admin_user.nombre,
            "nombre_usuario": admin_user.nombre_usuario,
            "rol": admin_user.rol,
            "tour_completed": admin_user.tour_completed
        }
    }
