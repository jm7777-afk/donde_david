from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.security import require_roles
from backend.app.core.database import get_db
from backend.app.models.insumo import Insumo
from backend.app.models.mesa import Mesa
from backend.app.models.pedido import Pedido
from backend.app.models.producto import Producto
from backend.app.models.turno import Turno

router = APIRouter(prefix="/gerencia", tags=["Gerencia"])


@router.get("/dashboard")
def get_manager_dashboard(
    db: Session = Depends(get_db),
    user=Depends(require_roles(["gerente"], allow_admin_override=False)),
):
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    yesterday_start = today_start - timedelta(days=1)
    active_order_states = ["PENDIENTE", "COBRADO", "EN_PREPARACION", "LISTO"]
    paid_at = func.coalesce(Pedido.fecha_pago, Pedido.fecha_creacion)
    paid_today = db.query(func.coalesce(func.sum(Pedido.total), 0)).filter(
        Pedido.estado_pago == "PAGADO",
        paid_at >= today_start,
        paid_at < now,
    ).scalar()
    paid_yesterday = db.query(func.coalesce(func.sum(Pedido.total), 0)).filter(
        Pedido.estado_pago == "PAGADO",
        paid_at >= yesterday_start,
        paid_at < today_start,
    ).scalar()

    active_orders = db.query(Pedido).filter(Pedido.estado.in_(active_order_states)).all()
    overdue_orders = [
        order for order in active_orders
        if order.fecha_creacion
        and (now - (
            order.fecha_creacion.replace(tzinfo=timezone.utc)
            if order.fecha_creacion.tzinfo is None
            else order.fecha_creacion.astimezone(timezone.utc)
        )).total_seconds() >= 15 * 60
    ]
    critical_inputs = db.query(Insumo).filter(Insumo.estado == "CRITICO").count()
    active_deliveries = db.query(Pedido).filter(
        Pedido.tipo == "delivery",
        Pedido.estado.notin_(["CANCELADO", "ENTREGADO"]),
    ).count()
    active_shift = db.query(Turno).filter(Turno.activo == True).order_by(Turno.id.desc()).first()

    return {
        "fecha_consulta": now.isoformat(),
        "ventas_hoy": round(float(paid_today or 0), 2),
        "ventas_ayer": round(float(paid_yesterday or 0), 2),
        "pedidos_cocina": len(active_orders),
        "pedidos_atrasados": len(overdue_orders),
        "pedidos_atrasados_detalle": [
            {
                "id": order.id,
                "numero_mesa": order.numero_mesa,
                "minutos_transcurridos": max(
                    0,
                    int((now - (
                        order.fecha_creacion.replace(tzinfo=timezone.utc)
                        if order.fecha_creacion.tzinfo is None
                        else order.fecha_creacion.astimezone(timezone.utc)
                    )).total_seconds() // 60),
                ),
            }
            for order in overdue_orders[:10]
        ],
        "insumos_criticos": critical_inputs,
        "delivery_activos": active_deliveries,
        "mesas_ocupadas": db.query(Mesa).filter(Mesa.estado == "OCUPADA").count(),
        "productos_no_disponibles": db.query(Producto).filter(
            Producto.activo == True,
            (Producto.disponible == False) | (Producto.stock <= 0),
        ).count(),
        "turno_activo": {
            "numero": active_shift.numero_turno,
            "ventas": round(float(active_shift.total_ventas or 0), 2),
            "pedidos": int(active_shift.total_pedidos or 0),
        } if active_shift else None,
    }
