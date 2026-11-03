from sqlalchemy.orm import Session

from backend.app.models.pedido import Pedido
from backend.app.models.puntos_log import PuntosLog
from backend.app.models.usuario import Usuario


def award_order_loyalty_points(db: Session, order: Pedido) -> int:
    if order.puntos_otorgados is not None:
        return order.puntos_otorgados
    if order.estado_pago != "PAGADO" or not order.usuario_id:
        return 0

    customer = db.query(Usuario).filter(Usuario.id == order.usuario_id).with_for_update().first()
    if not customer or customer.rol != "cliente":
        order.puntos_otorgados = 0
        return 0

    previous_log = db.query(PuntosLog).filter(
        PuntosLog.pedido_id == order.id,
        PuntosLog.usuario_id == order.usuario_id,
    ).first()
    if previous_log:
        order.puntos_otorgados = max(0, previous_log.puntos)
        return order.puntos_otorgados

    earned = sum(
        max(0, int(detail.puntos_fidelidad_unitarios or 0)) * max(0, int(detail.cantidad or 0))
        for detail in order.detalles
    )
    customer.pedidos_count = int(customer.pedidos_count or 0) + 1
    customer.total_gastado = round(float(customer.total_gastado or 0) + float(order.total or 0), 2)
    customer.puntos_fidelidad = int(customer.puntos_fidelidad or 0) + earned
    order.puntos_otorgados = earned

    if earned:
        db.add(PuntosLog(
            usuario_id=customer.id,
            puntos=earned,
            concepto=f"Pedido #{order.id}",
            pedido_id=order.id,
        ))
    return earned
