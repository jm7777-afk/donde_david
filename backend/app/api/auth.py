from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from backend.app.core.database import get_db
from backend.app.core.rate_limit import limiter
from backend.app.core.security import verify_password, create_access_token, get_current_user, get_password_hash
from backend.app.models.usuario import Usuario
from backend.app.schemas.schemas import LoginRequest, Token, UsuarioOut
from backend.app.services.audit_service import record_audit

router = APIRouter(prefix="/auth", tags=["Autenticación"])

class RegisterRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    email: EmailStr
    telefono: str = Field(min_length=1, max_length=20)
    nombre_usuario: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=12, max_length=72)

class RecoverPasswordRequest(BaseModel):
    email_o_telefono: str = Field(min_length=3, max_length=150)

@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, response: Response, login_data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(
        (Usuario.nombre_usuario == login_data.nombre_usuario) | (Usuario.email == login_data.nombre_usuario),
        Usuario.activo == True
    ).first()
    
    client_ip = request.client.host if request.client else None
    if not user or not verify_password(login_data.password, user.contraseña_hash):
        record_audit(
            db=db,
            accion="LOGIN_FAILED",
            usuario=login_data.nombre_usuario,
            ip_address=client_ip,
            recurso="auth",
            detalle=f"Intento fallido de inicio de sesión para el usuario '{login_data.nombre_usuario}'"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    record_audit(
        db=db,
        accion="LOGIN_SUCCESS",
        usuario=user.nombre_usuario,
        usuario_id=user.id,
        ip_address=client_ip,
        recurso="auth",
        detalle=f"Inicio de sesión exitoso con rol '{user.rol}'"
    )

    access_token = create_access_token(data={"sub": user.nombre_usuario, "rol": user.rol})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "usuario": {
            "id": user.id,
            "nombre": user.nombre,
            "apellido": user.apellido,
            "nombre_usuario": user.nombre_usuario,
            "email": user.email,
            "telefono": user.telefono,
            "rol": user.rol,
            "puntos_fidelidad": user.puntos_fidelidad,
            "pedidos_count": user.pedidos_count,
            "total_gastado": user.total_gastado
        }
    }

@router.post("/register")
@limiter.limit("5/hour")
def register(request: Request, response: Response, data: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.nombre_usuario == data.nombre_usuario).first():
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está registrado.")
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail="El correo ya está registrado.")

    nuevo = Usuario(
        nombre=data.nombre,
        apellido=data.apellido,
        email=data.email,
        telefono=data.telefono,
        nombre_usuario=data.nombre_usuario,
        contraseña_hash=get_password_hash(data.password),
        rol="cliente",
        puntos_fidelidad=50 # Bonus de bienvenida (50 pts)
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    client_ip = request.client.host if request.client else None
    record_audit(
        db=db,
        accion="USER_REGISTER",
        usuario=nuevo.nombre_usuario,
        usuario_id=nuevo.id,
        ip_address=client_ip,
        recurso="usuarios",
        recurso_id=str(nuevo.id),
        detalle="Registro de nuevo cliente con bono de bienvenida"
    )

    token = create_access_token(data={"sub": nuevo.nombre_usuario, "rol": nuevo.rol})
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": nuevo.id,
            "nombre": nuevo.nombre,
            "apellido": nuevo.apellido,
            "email": nuevo.email,
            "nombre_usuario": nuevo.nombre_usuario,
            "rol": nuevo.rol,
            "puntos_fidelidad": nuevo.puntos_fidelidad
        }
    }

@router.post("/recuperar-password")
@limiter.limit("3/hour")
def recuperar_password(request: Request, response: Response, data: RecoverPasswordRequest):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="La recuperación de contraseña no está habilitada; contacte al administrador."
    )

@router.get("/me", response_model=UsuarioOut)
def read_current_user(current_user: Usuario = Depends(get_current_user)):
    return current_user
