import sys
import os
import json
import logging
from sqlalchemy import inspect, text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.core.database import engine, SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.models.usuario import Usuario
from backend.app.models.categoria import Categoria
from backend.app.models.producto import Producto
from backend.app.models.configuracion import Configuracion
from backend.app.models.mesa import Mesa
from backend.app.models.insumo import Insumo
from backend.app.models.promocion import Promocion
from backend.app.models.puntos_log import PuntosLog
from backend.app.models.guia_item import GuiaItem
from backend.app.models.resena import Resena

logger = logging.getLogger(__name__)

def seed():
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise RuntimeError("Seed data is disabled in production.")
    logger.info("Initializing Donde David development data.")

    if engine.dialect.name == "sqlite":
        table_names = inspect(engine).get_table_names()
        if "turnos" in table_names:
            columns = {column["name"] for column in inspect(engine).get_columns("turnos")}
            with engine.begin() as connection:
                if "efectivo_declarado" not in columns:
                    connection.execute(text("ALTER TABLE turnos ADD COLUMN efectivo_declarado NUMERIC(12, 2)"))
                if "diferencia" not in columns:
                    connection.execute(text("ALTER TABLE turnos ADD COLUMN diferencia NUMERIC(12, 2)"))

    db = SessionLocal()
    try:
        # Ensure seeding runs idempotently; do not exit early

        # 1. Configuración por defecto "Donde David"
        configs = [
            ("nombre_restaurante", "DONDE DAVID | FAST FOOD", "Nombre del negocio"),
            ("impuesto_porcentaje", "16.0", "Porcentaje IVA"),
            ("costo_delivery", "10.00", "Costo estándar de envío a domicilio"),
            ("costo_empaque", "3.00", "Costo adicional por empaque para llevar"),
            ("puntos_por_dolar", "1", "Puntos acreditados por cada $1 de compra"),
            ("puntos_para_canje", "100", "Puntos requeridos para canje de recompensa"),
            ("whatsapp_contacto", "+502 4112 5554", "Número oficial WhatsApp"),
            ("instagram_link", "https://instagram.com/dondedavid", "Enlace a Instagram"),
            ("tiktok_link", "https://tiktok.com/@dondedavid", "Enlace a TikTok"),
            ("tasa_cambio_bs", "36.50", "Tasa de cambio estándar en Bolívares"),
            ("historia_restaurante", "Las mejores hamburguesas artesanales de res 100% preparadas al instante.", "Descripción pública del restaurante"),
            ("direccion_restaurante", "📍 Valencia • Sede Principal", "Ubicación que se muestra en el portal"),
            ("footer_enlaces_titulo", "ENLACES RÁPIDOS", "Título de los enlaces del pie de página"),
            ("footer_inicio_texto", "🏠 Inicio", "Texto del enlace de inicio"),
            ("footer_menu_texto", "🍔 Menú Interactivo", "Texto del enlace al menú"),
            ("footer_puntos_texto", "🎁 Puntos de Fidelidad", "Texto del enlace de fidelidad"),
            ("footer_atencion_titulo", "HORARIO & ATENCIÓN", "Título de horario y atención"),
            ("horario_atencion", "Todos los días: 11:00 AM - 11:00 PM", "Horario público"),
            ("servicio_restaurante", "Delivery directo & Pedidos QR en mesa", "Canales de atención"),
            ("medios_pago_texto", "Pago Móvil • Zelle • Tarjetas • Efectivo", "Medios de pago mostrados al público"),
            ("landing_titulo", "¡BUEN SABOR, RÁPIDO Y RECIÉN HECHO!", "Título de portada"),
            ("landing_descripcion", "Hamburguesas artesanales de carne 100% res, perros calientes con toppings crocantes y malteadas heladas. Pide por QR en mesa o solicita delivery.", "Descripción de portada"),
        ]
        for clave, valor, desc in configs:
            c = db.query(Configuracion).filter(Configuracion.clave == clave).first()
            if not c:
                db.add(Configuracion(clave=clave, valor=valor, descripcion=desc))
        db.commit()

        # 2. Usuarios del sistema
        usuarios = [
            ("Admin", "Donde David", "admin@dondedavid.com", "099111222", "admin", "admin123", "admin", 0),
            ("Javier", "Mendoza", "javier@mail.com", "+502 5123 4567", "javier", "javier123", "cliente", 0),
            ("María", "García", "caja2@dondedavid.com", "099333444", "caja", "caja123", "caja", 0),
            ("Ana", "López", "caja@dondedavid.com", "099555777", "caja_user", "caja123", "caja", 0),
            ("Juan", "Pérez", "cocina@dondedavid.com", "099555666", "cocina1", "cocina123", "cocina", 0),
            ("Pedro", "Rojas", "delivery@dondedavid.com", "099777888", "delivery1", "delivery123", "repartidor", 0)
        ]
        if os.getenv("ENVIRONMENT", "development").lower() != "production":
            for nom, ape, email, tel, user, pwd, rol, pts in usuarios:
                u = db.query(Usuario).filter(Usuario.nombre_usuario == user).first()
                if not u:
                    db.add(Usuario(
                        nombre=nom,
                        apellido=ape,
                        email=email,
                        telefono=tel,
                        nombre_usuario=user,
                        contraseña_hash=get_password_hash(pwd),
                        rol=rol,
                        puntos_fidelidad=pts
                    ))
                elif user == "delivery1" and u.rol != "repartidor":
                    u.rol = "repartidor"
            db.commit()

        # 3. Mesas 1 a 20 con soporte para QR exclusivo
        for i in range(1, 21):
            if not db.query(Mesa).filter(Mesa.numero_mesa == i).first():
                estado_m = "LIBRE"

                db.add(Mesa(
                    numero_mesa=i,
                    estado=estado_m,
                    codigo_qr=f"QR_DONDE_DAVID_MESA_{i}",
                    capacidad=4,
                    cliente_actual=None,
                    tiempo_ocupacion_min=0
                ))
        db.commit()

        # 4. Insumos e Inventario de Ingredientes de Productos
        insumos_data = [
            ("Carne de res 150g", 35.0, 10.0, "kg", "NORMAL"),
            ("Pan de hamburguesa brioche", 18.0, 25.0, "un", "CRITICO"),
            ("Queso Cheddar fundido", 6.0, 10.0, "kg", "CRITICO"),
            ("Tocino ahumado crujiente", 3.0, 8.0, "kg", "CRITICO"),
            ("Salchicha Jumbo", 45.0, 15.0, "un", "NORMAL"),
            ("Papas amarillas rústicas", 40.0, 15.0, "kg", "NORMAL"),
            ("Tomate fresco", 12.0, 5.0, "kg", "NORMAL"),
            ("Cebolla morada", 8.0, 4.0, "kg", "NORMAL"),
            ("Pepinillos agridulces", 5.0, 3.0, "kg", "NORMAL"),
            ("Salsa BBQ de la casa", 10.0, 3.0, "lt", "NORMAL"),
            ("Salsa especial de la casa", 8.0, 2.0, "lt", "NORMAL"),
            ("Maíz dulce", 6.0, 2.0, "kg", "NORMAL"),
            ("Alitas de pollo frescas", 20.0, 8.0, "kg", "NORMAL"),
            ("Helado de Vainilla", 15.0, 5.0, "lt", "NORMAL"),
            ("Galletas Oreo paquetes", 30.0, 10.0, "un", "NORMAL"),
            ("Sirope de Chocolate", 5.0, 2.0, "lt", "NORMAL")
        ]
        for nom, st_act, st_min, um, est in insumos_data:
            if not db.query(Insumo).filter(Insumo.nombre == nom).first():
                db.add(Insumo(
                    nombre=nom,
                    stock_actual=st_act,
                    stock_minimo=st_min,
                    unidad_medida=um,
                    estado=est
                ))
        db.commit()

        # 5. Categorías Toon con FOTOS reales apetitosas
        categorias_data = [
            ("Hamburguesas", "Las más jugosas, preparadas al momento", "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500", 1),
            ("Hot Dogs", "Perros estilo americano con toppings crujientes", "https://images.unsplash.com/photo-1619740455993-9e612b1af08a?w=500", 2),
            ("Papas", "Papas fritas sazonadas corte especial", "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=500", 3),
            ("Bebidas", "Refrescos helados y malteadas cremosas", "https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=500", 4),
            ("Alitas", "Alitas bañadas en salsa BBQ o picante", "https://images.unsplash.com/photo-1567620832903-9fc6debc209f?w=500", 5),
            ("Postres", "Helados y postres artesanales", "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=500", 6),
            ("Combos", "Combos explosivos para compartir", "https://images.unsplash.com/photo-1561758033-d89a9ad46330?w=500", 7),
            ("Extras", "Ingredientes adicionales y salsas de la casa", "https://images.unsplash.com/photo-1576107232684-1279f3908594?w=500", 8)
        ]
        cat_map = {}
        for nom, desc, img, orden in categorias_data:
            cat = db.query(Categoria).filter(Categoria.nombre == nom).first()
            if not cat:
                cat = Categoria(nombre=nom, descripcion=desc, imagen_url=img, orden=orden)
                db.add(cat)
                db.commit()
                db.refresh(cat)
            cat_map[nom] = cat.id

        # 6. Productos Toon con fotos e ingredientes editables
        productos_data = [
            ("Hamburguesa Clásica", "Carne 150g, lechuga, tomate, cebolla morada, queso cheddar y salsa especial.", 42.00, None, cat_map["Hamburguesas"], "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500", ["Carne 150g", "Queso Cheddar", "Tomate", "Cebolla Morada", "Salsa Especial"]),
            ("Hamburguesa Doble", "Doble carne 300g, doble queso cheddar, tocino crujiente.", 59.00, None, cat_map["Hamburguesas"], "https://images.unsplash.com/photo-1586190848861-99aa4a171e90?w=500", ["Doble Carne 300g", "Doble Cheddar", "Tocino Crujiente"]),
            ("Hamburguesa BBQ", "Carne 150g, BBQ, aros de cebolla, queso fundido.", 49.00, None, cat_map["Hamburguesas"], "https://images.unsplash.com/photo-1550547660-d9450f859349?w=500", ["Carne 150g", "Salsa BBQ", "Aros de Cebolla"]),
            ("Hamburguesa Picante", "Carne 150g, jalapeños frescos, salsa picante habanero.", 45.00, None, cat_map["Hamburguesas"], "https://images.unsplash.com/photo-1603064752734-4c48fea5ba57?w=500", ["Carne 150g", "Jalapeños", "Salsa Habanero"]),
            ("Perro Caliente Clásico", "Salchicha premium, papitas picadas y salsas especiales.", 25.00, None, cat_map["Hot Dogs"], "https://images.unsplash.com/photo-1619740455993-9e612b1af08a?w=500", ["Salchicha Premium", "Papitas", "Salsas"]),
            ("Perro Especial Toon", "Salchicha, tocino, queso cheddar y maíz dulce.", 32.00, None, cat_map["Hot Dogs"], "https://images.unsplash.com/photo-1627054247567-8898950d8a43?w=500", ["Salchicha", "Tocino", "Queso Cheddar", "Maíz dulce"]),
            ("Papas Fritas Grandes", "Porción gigante de papas doradas con sazón de la casa.", 18.00, None, cat_map["Papas"], "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=500", ["Papas Amarillas", "Sazón Especial"]),
            ("Papas con Queso y Tocino", "Papas rústicas bañadas en cheddar y tocino troceado.", 28.00, None, cat_map["Papas"], "https://images.unsplash.com/photo-1576107232684-1279f3908594?w=500", ["Papas Rústicas", "Cheddar Derretido", "Tocino"]),
            ("Malteada de Oreo", "Cremosa malteada helada con trozos de galleta Oreo.", 20.00, None, cat_map["Bebidas"], "https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=500", ["Helado de Vainilla", "Galleta Oreo", "Crema Batida"]),
            ("Refresco Helado 500ml", "Coca-Cola / Sprite / Fanta helada.", 12.00, None, cat_map["Bebidas"], "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=500", ["Refresco 500ml"])
        ]

        for nom, desc, precio, pr_promo, cat_id, img, ings in productos_data:
            p = db.query(Producto).filter(Producto.nombre == nom).first()
            if not p:
                db.add(Producto(
                    nombre=nom,
                    descripcion=desc,
                    precio=precio,
                    precio_promocion=pr_promo,
                    categoria_id=cat_id,
                    imagen_url=img,
                    stock=100,
                    tiempo_preparacion=12,
                    ingredientes_json=json.dumps(ings)
                ))
        db.commit()

        # 7. Promociones Editables (BOOM! PROMO DEL DÍA)
        promos = [
            ("COMBO EXPLOSIVO TOON", "2 Hamburguesas + Papas Fritas + 2 Refrescos", 30.0, "COMBO53", "https://images.unsplash.com/photo-1561758033-d89a9ad46330?w=600"),
            ("MARTES DE PERROS 2X1", "Lleva 2 Perros Calientes Especiales por el precio de 1", 50.0, "PERROS2X1", "https://images.unsplash.com/photo-1619740455993-9e612b1af08a?w=600"),
            ("PAPAS Y QUESO GRATIS", "En compras superiores a Q50.00 en pedidos QR", 100.0, "PAPASGRATIS", "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=600")
        ]
        for tit, desc, pct, cod, img in promos:
            if not db.query(Promocion).filter(Promocion.codigo_cupon == cod).first():
                db.add(Promocion(titulo=tit, descripcion=desc, descuento_pct=pct, codigo_cupon=cod, banner_url=img))
        db.commit()

        # 8. Diapositivas de la Guía Interactiva
        guia_data = [
            ("Paso 1: Explora el Menú Apetitoso", "Toca sobre cualquier categoría o producto con fotos para ver sus ingredientes detallados.", "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600", "imagen", "ambos", 1),
            ("Paso 2: Personaliza a tu Gusto", "Agrega extra queso, tocino o remueve ingredientes fácilmente antes de agregar al carrito.", "https://images.unsplash.com/photo-1586190848861-99aa4a171e90?w=600", "imagen", "ambos", 2),
            ("Paso 3: Elección en Mesa o Delivery", "Si estás en mesa escanea tu QR o elige la modalidad Delivery introduciendo tu dirección de envío.", "https://images.unsplash.com/photo-1619740455993-9e612b1af08a?w=600", "imagen", "ambos", 3),
            ("Paso 4: Elige Pagar Ahora o Abrir Cuenta", "En mesa puedes pagar inmediatamente o mantener la cuenta abierta para seguir pidiendo.", "https://images.unsplash.com/photo-1550547660-d9450f859349?w=600", "imagen", "mesa", 4)
        ]
        for tit, desc, media, tipo_m, tipo_v, ord_val in guia_data:
            if not db.query(GuiaItem).filter(GuiaItem.titulo == tit).first():
                db.add(GuiaItem(
                    titulo=tit,
                    descripcion=desc,
                    media_url=media,
                    tipo_media=tipo_m,
                    tipo_vista=tipo_v,
                    orden=ord_val
                ))
        db.commit()

        # 9. Reseñas ⭐⭐⭐⭐⭐ de Clientes
        resenas_data = [
            ("Carlos Ramos", "¡Las mejores hamburguesas de la ciudad! El pan es suave y la carne mega jugosa. ¡El sistema de pedir por QR desde la mesa es rapidísimo!", 5, "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150"),
            ("Sofía López", "Excelente atención y el servicio de Delivery llegó volando. La malteada de Oreo super recomendada.", 5, "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150"),
            ("Andrés Castro", "Muy buena experiencia. La opción de dejar la cuenta abierta en mesa te permite seguir pidiendo papas o bebidas sin complicaciones.", 5, "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150")
        ]
        for nom, com, est, foto in resenas_data:
            if not db.query(Resena).filter(Resena.nombre_cliente == nom).first():
                db.add(Resena(nombre_cliente=nom, comentario=com, estrellas=est, foto_url=foto))
        db.commit()

        logger.info("Donde David seed data loaded.")

    except Exception as e:
        db.rollback()
        logger.exception("Failed to load seed data.")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()
