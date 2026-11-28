"""
Servicio compartido de pedidos, precios, extras e inventario.
Centraliza el cálculo autoritativo de precios, impuestos, cargos por modalidad,
validación de extras y control transaccional de stock con bloqueo de filas.
"""
import json
import logging
import math
from typing import Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.configuracion import Configuracion
from backend.app.models.detalle_pedido import DetallePedido
from backend.app.models.movimiento_inventario import MovimientoInventario
from backend.app.models.pedido import Pedido
from backend.app.models.producto import Producto
from backend.app.models.promocion import Promocion
from backend.app.schemas.schemas import DetallePedidoItem, PromocionPedidoItem

logger = logging.getLogger(__name__)


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


def deduct_order_stock(
    db: Session,
    pedido_id: int,
    products: dict[int, Producto],
    requested_quantities: dict[int, int],
    stock_before: dict[int, int],
    usuario_id: Optional[int],
) -> None:
    """Descuenta existencias y registra movimientos de inventario de venta."""
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


def restore_order_stock(
    db: Session,
    pedido: Pedido,
    *,
    motivo: str,
    usuario_id: Optional[int],
    strict: bool = False,
) -> None:
    """Restaura existencias y registra movimientos de devolución ordenadamente."""
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
