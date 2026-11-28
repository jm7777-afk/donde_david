"""
Servicio compartido de pedidos, precios, extras e inventario.
Centraliza el cálculo autoritativo de precios, impuestos, cargos por modalidad,
validación de extras y control transaccional de stock con bloqueo de filas.
"""
import json
import logging
import math
from datetime import datetime, timezone
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.configuracion import Configuracion
from backend.app.models.detalle_pedido import DetallePedido
from backend.app.models.insumo import Insumo
from backend.app.models.movimiento_inventario import MovimientoInventario
from backend.app.models.pedido import Pedido
from backend.app.models.producto import Producto
from backend.app.models.producto_insumo import ProductoInsumo
from backend.app.models.promocion import Promocion
from backend.app.schemas.schemas import DetallePedidoItem, PromocionPedidoItem

logger = logging.getLogger(__name__)

DAY_CODE_MAP = {
    "0": 0, "l": 0, "lu": 0, "lun": 0, "lunes": 0,
    "1": 1, "m": 1, "ma": 1, "mar": 1, "martes": 1,
    "2": 2, "x": 2, "mi": 2, "mie": 2, "miercoles": 2, "miércoles": 2,
    "3": 3, "j": 3, "ju": 3, "jue": 3, "jueves": 3,
    "4": 4, "v": 4, "vi": 4, "vie": 4, "viernes": 4,
    "5": 5, "s": 5, "sa": 5, "sab": 5, "sabado": 5, "sábado": 5,
    "6": 6, "d": 6, "do": 6, "dom": 6, "domingo": 6,
}


def _to_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _is_hhmm_in_range(current_hhmm: str, start_hhmm: Optional[str], end_hhmm: Optional[str]) -> bool:
    start = (start_hhmm or "").strip()
    end = (end_hhmm or "").strip()
    if not start and not end:
        return True
    if start and not end:
        return current_hhmm >= start
    if end and not start:
        return current_hhmm <= end
    if start <= end:
        return start <= current_hhmm <= end
    return current_hhmm >= start or current_hhmm <= end


def is_promotion_currently_valid(promo: Promocion, now: Optional[datetime] = None) -> bool:
    """Evalúa si una promoción está activa y dentro de su vigencia por fecha, día y hora."""
    if not promo or not promo.activo:
        return False
    ref_utc = _to_utc_naive(now or datetime.now(timezone.utc))
    start_dt = _to_utc_naive(getattr(promo, "fecha_inicio", None))
    end_dt = _to_utc_naive(getattr(promo, "fecha_fin", None))
    if start_dt and ref_utc < start_dt:
        return False
    if end_dt and ref_utc > end_dt:
        return False

    ref_local = now or datetime.now()
    raw_days = (getattr(promo, "dias_semana", None) or "").strip()
    if raw_days:
        allowed = set()
        for token in raw_days.split(","):
            mapped = DAY_CODE_MAP.get(token.strip().lower())
            if mapped is not None:
                allowed.add(mapped)
        if allowed and ref_local.weekday() not in allowed:
            return False

    current_hhmm = ref_local.strftime("%H:%M")
    return _is_hhmm_in_range(
        current_hhmm,
        getattr(promo, "hora_inicio", None),
        getattr(promo, "hora_fin", None),
    )


def validate_store_schedule(db: Session, now: Optional[datetime] = None) -> None:
    """Valida horario comercial únicamente cuando `validar_horario_pedidos` está habilitado."""
    rows = {
        row.clave: row.valor
        for row in db.query(Configuracion).filter(
            Configuracion.clave.in_([
                "validar_horario_pedidos",
                "horario_apertura",
                "horario_cierre",
            ])
        ).all()
    }
    if rows.get("validar_horario_pedidos", "false").strip().lower() not in {"true", "1", "si", "on"}:
        return
    apertura = (rows.get("horario_apertura") or "09:00").strip()
    cierre = (rows.get("horario_cierre") or "23:00").strip()
    ref_local = now or datetime.now()
    if not _is_hhmm_in_range(ref_local.strftime("%H:%M"), apertura, cierre):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"El restaurante está fuera de horario de atención ({apertura} - {cierre}).",
        )


def get_pricing_config(db: Session) -> dict[str, float]:
    """Obtiene la configuración vigente de impuesto, delivery y empaque."""
    configs = {
        row.clave: row.valor
        for row in db.query(Configuracion).filter(
            Configuracion.clave.in_([
                "iva_activo",
                "impuesto_porcentaje",
                "costo_delivery",
                "costo_empaque",
            ])
        ).all()
    }
    is_iva_active = configs.get("iva_activo", "true").lower() in ("true", "1")
    raw_tax = configs.get("impuesto_porcentaje")
    tax_rate = (float(raw_tax) if raw_tax is not None else 16.0) if is_iva_active else 0.0
    raw_delivery = configs.get("costo_delivery")
    delivery_fee = float(raw_delivery) if raw_delivery is not None else 5.0
    raw_package = configs.get("costo_empaque")
    package_fee = float(raw_package) if raw_package is not None else 3.0
    return {
        "tax_rate": tax_rate,
        "delivery_fee": delivery_fee,
        "package_fee": package_fee,
    }


def prepare_order_items(
    db: Session,
    items: Sequence[DetallePedidoItem],
    *,
    always_serialize_personalizations: bool = False,
) -> tuple[dict[int, Producto], dict[int, int], dict[int, int], list[DetallePedido], float]:
    """
    Bloquea los productos solicitados en orden determinista para evitar interbloqueos,
    valida disponibilidad/stock/extras y construye los renglones con precios del servidor.
    """
    requested_quantities: dict[int, int] = {}
    for item in items:
        requested_quantities[item.producto_id] = (
            requested_quantities.get(item.producto_id, 0) + item.cantidad
        )

    products: dict[int, Producto] = {}
    stock_before: dict[int, int] = {}
    for product_id in sorted(requested_quantities):
        quantity = requested_quantities[product_id]
        product = db.query(Producto).filter(
            Producto.id == product_id,
            Producto.activo == True,
            Producto.disponible == True,
        ).with_for_update().first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con ID {product_id} no disponible.",
            )
        if int(product.stock or 0) < quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Stock insuficiente para el producto '{product.nombre}' "
                    f"(Disponible: {product.stock}, Solicitado: {quantity})."
                ),
            )
        products[product_id] = product
        stock_before[product_id] = int(product.stock or 0)

    subtotal_acumulado = 0.0
    detalles_db: list[DetallePedido] = []

    for item in items:
        producto = products[item.producto_id]
        precio_base = (
            float(producto.precio_promocion)
            if (producto.precio_promocion and float(producto.precio_promocion) > 0)
            else float(producto.precio)
        )
        customizations = item.personalizaciones or {}
        extras_requested = customizations.get("extras", [])
        if not isinstance(extras_requested, list):
            raise HTTPException(status_code=422, detail="La lista de extras no es válida.")
        try:
            configured_extras = json.loads(producto.extras_json or "[]")
        except json.JSONDecodeError as exc:
            logger.exception("Invalid extras_json for product %s", producto.id)
            raise HTTPException(
                status_code=500,
                detail="La configuración de extras de un producto es inválida.",
            ) from exc
        if not isinstance(configured_extras, list):
            logger.error("Invalid extras_json shape for product %s", producto.id)
            raise HTTPException(
                status_code=500,
                detail="La configuración de extras de un producto es inválida.",
            )
        configured_by_name = {
            entry["nombre"]: float(entry["precio"])
            for entry in configured_extras
            if isinstance(entry, dict)
            and isinstance(entry.get("nombre"), str)
            and isinstance(entry.get("precio"), (int, float))
            and not isinstance(entry.get("precio"), bool)
            and math.isfinite(entry["precio"])
            and entry["precio"] >= 0
        }

        selected_names: list[str] = []
        extra_total = 0.0
        for extra in extras_requested:
            if not isinstance(extra, str) or extra not in configured_by_name or extra in selected_names:
                raise HTTPException(
                    status_code=422,
                    detail=f"El extra solicitado no está disponible para {producto.nombre}.",
                )
            selected_names.append(extra)
            extra_total += configured_by_name[extra]

        unit_price = round(precio_base + extra_total, 2)
        subtotal_item = round(unit_price * item.cantidad, 2)
        subtotal_acumulado += subtotal_item

        personalizations_to_save = dict(customizations)
        if extras_requested or always_serialize_personalizations:
            if extras_requested or "extras" in personalizations_to_save:
                personalizations_to_save["extras"] = selected_names
        personalizaciones_str = (
            json.dumps(personalizations_to_save)
            if (personalizations_to_save and (customizations or always_serialize_personalizations))
            else None
        )

        detalle_row = DetallePedido(
            producto_id=producto.id,
            cantidad=item.cantidad,
            precio_unitario=unit_price,
            subtotal=subtotal_item,
            puntos_fidelidad_unitarios=max(0, int(producto.puntos_fidelidad or 0)),
            personalizaciones=personalizaciones_str,
            observaciones=item.observaciones,
            estado="PENDIENTE",
        )
        detalle_row._base_unit_price = precio_base
        detalle_row._extra_unit_price = extra_total
        detalles_db.append(detalle_row)

    return products, requested_quantities, stock_before, detalles_db, round(subtotal_acumulado, 2)


def apply_promo_bundles_pricing(
    db: Session,
    detalles_db: list[DetallePedido],
    promo_bundles: Optional[Sequence[PromocionPedidoItem]],
) -> tuple[float, float]:
    """
    Aplica el precio global oficial de promociones/combos sobre los renglones
    correspondientes (manteniendo extras pagados y asignando prorrateo exacto).
    Retorna `(nuevo_subtotal, descuento_total)`.
    """
    if not promo_bundles:
        current_sub = round(sum(float(d.subtotal or 0) for d in detalles_db), 2)
        return current_sub, 0.0

    bundled_flags = [False] * len(detalles_db)
    total_discount = 0.0

    for bundle in promo_bundles:
        promo = db.query(Promocion).filter(
            Promocion.id == bundle.promocion_id,
            Promocion.activo == True,
        ).first()
        if not promo or promo.precio_global is None or float(promo.precio_global) <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La promoción #{bundle.promocion_id} no está activa o no tiene precio global configurado.",
            )
        if not is_promotion_currently_valid(promo):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La promoción '{promo.titulo}' no está vigente en este horario o día.",
            )
        promo_products = [prod for prod in (promo.productos or []) if prod.activo and prod.disponible]
        if not promo_products or len(promo_products) != len(promo.productos or []):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La promoción '{promo.titulo}' no tiene todos sus productos disponibles.",
            )

        matched_indices: list[int] = []
        for prod in promo_products:
            remaining_needed = int(bundle.cantidad)
            for idx in range(len(detalles_db)):
                if remaining_needed <= 0:
                    break
                row = detalles_db[idx]
                if bundled_flags[idx] or row.producto_id != prod.id:
                    continue
                row_qty = int(row.cantidad or 0)
                if row_qty <= 0:
                    continue
                take = min(row_qty, remaining_needed)
                if take < row_qty:
                    base_unit = float(getattr(row, "_base_unit_price", float(row.precio_unitario or 0)))
                    extra_unit = float(getattr(row, "_extra_unit_price", 0.0))
                    remainder_qty = row_qty - take
                    remainder_row = DetallePedido(
                        producto_id=row.producto_id,
                        cantidad=remainder_qty,
                        precio_unitario=row.precio_unitario,
                        subtotal=round(float(row.precio_unitario or 0) * remainder_qty, 2),
                        puntos_fidelidad_unitarios=row.puntos_fidelidad_unitarios,
                        personalizaciones=row.personalizaciones,
                        observaciones=row.observaciones,
                        estado=row.estado,
                    )
                    remainder_row._base_unit_price = base_unit
                    remainder_row._extra_unit_price = extra_unit
                    row.cantidad = take
                    row.subtotal = round(float(row.precio_unitario or 0) * take, 2)
                    detalles_db.append(remainder_row)
                    bundled_flags.append(False)
                bundled_flags[idx] = True
                setattr(row, "_is_global_bundle", True)
                matched_indices.append(idx)
                remaining_needed -= take

            if remaining_needed > 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"La promoción '{promo.titulo}' requiere todos los productos seleccionados en la cantidad solicitada.",
                )

        target_global = round(float(promo.precio_global) * int(bundle.cantidad), 2)
        base_amounts = [
            round(
                float(getattr(detalles_db[idx], "_base_unit_price", float(detalles_db[idx].precio_unitario or 0)))
                * int(detalles_db[idx].cantidad),
                2,
            )
            for idx in matched_indices
        ]
        base_sum = round(sum(base_amounts), 2)
        allocated_sum = 0.0
        for pos, idx in enumerate(matched_indices):
            row = detalles_db[idx]
            qty = int(row.cantidad)
            extra_unit = float(getattr(row, "_extra_unit_price", 0.0))
            if pos == len(matched_indices) - 1:
                allocated_base = round(target_global - allocated_sum, 2)
            elif base_sum > 0:
                allocated_base = round(target_global * (base_amounts[pos] / base_sum), 2)
                allocated_sum = round(allocated_sum + allocated_base, 2)
            else:
                allocated_base = round(target_global / len(matched_indices), 2)
                allocated_sum = round(allocated_sum + allocated_base, 2)
            new_subtotal = round(max(0.0, allocated_base) + (extra_unit * qty), 2)
            row.subtotal = new_subtotal
            row.precio_unitario = round(new_subtotal / qty, 2)

        total_discount = round(total_discount + max(0.0, base_sum - target_global), 2)

    final_subtotal = round(sum(float(d.subtotal or 0) for d in detalles_db), 2)
    return final_subtotal, total_discount


def apply_coupon_discount(
    db: Session,
    detalles_db: Sequence[DetallePedido],
    codigo_cupon: Optional[str],
    existing_discount: float = 0.0,
) -> tuple[float, float, Optional[Promocion]]:
    """
    Aplica el descuento porcentual de un código de cupón válido sobre los renglones
    elegibles que no formen parte de un combo con precio global fijo.
    """
    cleaned = (codigo_cupon or "").strip()
    if not cleaned:
        return round(sum(float(d.subtotal or 0) for d in detalles_db), 2), round(existing_discount, 2), None

    promo = db.query(Promocion).filter(
        Promocion.activo == True,
        func.upper(Promocion.codigo_cupon) == cleaned.upper(),
    ).first()
    if not promo or not is_promotion_currently_valid(promo):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El código de cupón no existe o no está vigente en este momento.",
        )

    pct = float(promo.descuento_pct or 0.0)
    if pct <= 0 or pct > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Este cupón corresponde a un combo promocional; agrégalo desde Promociones.",
        )

    promo_product_ids = {prod.id for prod in (promo.productos or [])}
    eligible_rows = [
        row for row in detalles_db
        if not getattr(row, "_is_global_bundle", False)
        and (not promo_product_ids or row.producto_id in promo_product_ids)
    ]
    eligible_total = round(sum(float(r.subtotal or 0) for r in eligible_rows), 2)
    if not eligible_rows or eligible_total <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El cupón no aplica a los productos seleccionados en tu carrito.",
        )

    coupon_discount = round(eligible_total * (pct / 100.0), 2)
    discount_distributed = 0.0
    for idx, row in enumerate(eligible_rows):
        row_sub = float(row.subtotal or 0.0)
        if idx == len(eligible_rows) - 1:
            row_disc = round(coupon_discount - discount_distributed, 2)
        else:
            row_disc = round(coupon_discount * (row_sub / eligible_total), 2)
            discount_distributed = round(discount_distributed + row_disc, 2)
        new_sub = round(max(0.0, row_sub - row_disc), 2)
        row.subtotal = new_sub
        qty = max(1, int(row.cantidad or 1))
        row.precio_unitario = round(new_sub / qty, 2)

    final_subtotal = round(sum(float(d.subtotal or 0) for d in detalles_db), 2)
    return final_subtotal, round(existing_discount + coupon_discount, 2), promo


def collect_stock_alerts(
    products: dict[int, Producto],
    touched_insumos: Sequence[Insumo] = (),
) -> list[dict]:
    """Recopila productos e insumos que alcanzaron nivel mínimo o agotamiento."""
    alerts: list[dict] = []
    for prod in products.values():
        stock = int(prod.stock or 0)
        minimo = int(prod.stock_minimo or 0)
        if stock <= minimo:
            alerts.append({
                "tipo": "PRODUCTO",
                "id": prod.id,
                "nombre": prod.nombre,
                "stock": stock,
                "stock_minimo": minimo,
                "agotado": stock <= 0,
            })
    for ins in touched_insumos:
        if ins.estado == "CRITICO" or float(ins.stock_actual or 0) <= float(ins.stock_minimo or 0):
            alerts.append({
                "tipo": "INSUMO",
                "id": ins.id,
                "nombre": ins.nombre,
                "stock": round(float(ins.stock_actual or 0), 2),
                "stock_minimo": round(float(ins.stock_minimo or 0), 2),
                "unidad": ins.unidad_medida,
                "agotado": float(ins.stock_actual or 0) <= 0,
            })
    return alerts


def deduct_order_stock(
    db: Session,
    pedido_id: int,
    products: dict[int, Producto],
    requested_quantities: dict[int, int],
    stock_before: dict[int, int],
    usuario_id: Optional[int],
) -> list[Insumo]:
    """Descuenta existencias de productos, recetas de insumos asociadas y registra movimientos."""
    for product_id in sorted(requested_quantities):
        quantity = requested_quantities[product_id]
        products[product_id].stock = int(products[product_id].stock or 0) - quantity
        db.add(MovimientoInventario(
            producto_id=product_id,
            tipo_movimiento="VENTA",
            cantidad_cambio=-quantity,
            cantidad_anterior=stock_before[product_id],
            cantidad_nueva=products[product_id].stock,
            motivo=f"Pedido #{pedido_id}",
            usuario_id=usuario_id,
        ))

    recipes = (
        db.query(ProductoInsumo)
        .filter(ProductoInsumo.producto_id.in_(list(requested_quantities.keys())))
        .all()
    ) if requested_quantities else []
    if not recipes:
        return []

    usage_by_insumo: dict[int, list[tuple[int, float]]] = {}
    for rec in recipes:
        qty_used = round(float(rec.cantidad_por_unidad or 0) * int(requested_quantities.get(rec.producto_id, 0)), 4)
        if qty_used > 0:
            usage_by_insumo.setdefault(rec.insumo_id, []).append((rec.producto_id, qty_used))

    touched_insumos: list[Insumo] = []
    depleted_insumo_ids: list[int] = []
    for insumo_id in sorted(usage_by_insumo):
        insumo = db.query(Insumo).filter(Insumo.id == insumo_id).with_for_update().first()
        if not insumo:
            continue
        total_needed = round(sum(q for _, q in usage_by_insumo[insumo_id]), 4)
        current = round(float(insumo.stock_actual or 0.0), 4)
        if current < total_needed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insumo insuficiente para preparar el pedido: '{insumo.nombre}' (Disponible: {current} {insumo.unidad_medida}).",
            )
        prev_val = current
        for prod_id, used_qty in usage_by_insumo[insumo_id]:
            next_val = round(prev_val - used_qty, 4)
            db.add(MovimientoInventario(
                insumo_id=insumo.id,
                producto_id=prod_id,
                tipo_movimiento="VENTA",
                cantidad_cambio=-used_qty,
                cantidad_anterior=prev_val,
                cantidad_nueva=next_val,
                motivo=f"Consumo receta Pedido #{pedido_id}",
                usuario_id=usuario_id,
            ))
            prev_val = next_val
        insumo.stock_actual = prev_val
        insumo.estado = "CRITICO" if prev_val <= float(insumo.stock_minimo or 0) else "NORMAL"
        insumo.fecha_actualizacion = datetime.now(timezone.utc)
        touched_insumos.append(insumo)
        if prev_val <= 0:
            depleted_insumo_ids.append(insumo.id)

    if depleted_insumo_ids:
        affected_product_ids = [
            row.producto_id
            for row in db.query(ProductoInsumo.producto_id)
            .filter(ProductoInsumo.insumo_id.in_(depleted_insumo_ids))
            .distinct()
            .all()
        ]
        if affected_product_ids:
            db.query(Producto).filter(Producto.id.in_(affected_product_ids)).update(
                {Producto.disponible: False},
                synchronize_session=False,
            )

    return touched_insumos


def restore_order_stock(
    db: Session,
    pedido: Pedido,
    *,
    motivo: str,
    usuario_id: Optional[int],
    strict: bool = False,
) -> None:
    """Restaura existencias de productos e insumos de receta ordenadamente."""
    quantities_by_product: dict[int, int] = {}
    for detalle in pedido.detalles:
        quantities_by_product[detalle.producto_id] = (
            quantities_by_product.get(detalle.producto_id, 0) + int(detalle.cantidad or 0)
        )

    for product_id in sorted(quantities_by_product):
        qty = quantities_by_product[product_id]
        producto = db.query(Producto).filter(Producto.id == product_id).with_for_update().first()
        if not producto:
            if strict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se pudo restaurar inventario del producto #{product_id}.",
                )
            continue
        anterior = int(producto.stock or 0)
        producto.stock = anterior + qty
        db.add(MovimientoInventario(
            producto_id=producto.id,
            tipo_movimiento="DEVOLUCION",
            cantidad_cambio=qty,
            cantidad_anterior=anterior,
            cantidad_nueva=producto.stock,
            motivo=motivo,
            usuario_id=usuario_id,
        ))

    recipes = (
        db.query(ProductoInsumo)
        .filter(ProductoInsumo.producto_id.in_(list(quantities_by_product.keys())))
        .all()
    ) if quantities_by_product else []
    if not recipes:
        return

    restore_by_insumo: dict[int, float] = {}
    for rec in recipes:
        qty_back = round(float(rec.cantidad_por_unidad or 0) * int(quantities_by_product.get(rec.producto_id, 0)), 4)
        if qty_back > 0:
            restore_by_insumo[rec.insumo_id] = round(restore_by_insumo.get(rec.insumo_id, 0.0) + qty_back, 4)

    for insumo_id in sorted(restore_by_insumo):
        insumo = db.query(Insumo).filter(Insumo.id == insumo_id).with_for_update().first()
        if not insumo:
            continue
        anterior_ins = round(float(insumo.stock_actual or 0.0), 4)
        restored_qty = restore_by_insumo[insumo_id]
        insumo.stock_actual = round(anterior_ins + restored_qty, 4)
        insumo.estado = "CRITICO" if insumo.stock_actual <= float(insumo.stock_minimo or 0) else "NORMAL"
        insumo.fecha_actualizacion = datetime.now(timezone.utc)
        db.add(MovimientoInventario(
            insumo_id=insumo.id,
            tipo_movimiento="DEVOLUCION",
            cantidad_cambio=restored_qty,
            cantidad_anterior=anterior_ins,
            cantidad_nueva=insumo.stock_actual,
            motivo=motivo,
            usuario_id=usuario_id,
        ))
