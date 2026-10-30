# 🍔 DONDE DAVID - FRESH & TASTY! (v2.0.0 Enterprise)

> Sistema Web Integral de Automatización de Pedidos vía Código QR, Gestión de Caja Registradora POS Touch, Monitor KDS de Cocina y Conversión Multimoneda.

---

## 📚 Tesis y Autoría
- **Título**: Sistema Web Integral de Automatización de Pedidos vía Código QR, Gestión de Caja Registradora POS Touch, Monitor KDS de Cocina y Conversión Multimoneda para el Restaurante "Donde David - Fresh & Tasty!"
- **Autor**: Javier Mendoza
- **Institución**: Instituto Universitario de Tecnología (Carrera: Análisis de Sistemas, 2026).

---

## 🎯 Características Clave
- 📱 **Autoservicio QR Mobile**: Carta digital interactiva con conversión en tiempo real USD ($) ↔ Bolívares (Bs.).
- 🍳 **KDS Cocina (Kitchen Display System)**: Actualización instantánea vía WebSockets con alertas sonoras y control visual de tiempos (>15 min en rojo).
- 💵 **Caja POS Touch**: Apertura/cierre de turnos, egresos auditables y arqueo por efectivo, Pago Móvil y punto de venta; productos frecuentes y facturación ticket con IVA configurado.
- 🪑 **Panel de Meseros**: Vista responsive de mesas y pedidos activos, solicitudes de atención/cuenta enviadas por QR y transferencia de cuentas.
- 📦 **Retiro en mostrador**: Cola separada de pedidos listos para retirar y validación de un código aleatorio de seis dígitos en caja.
- 👋 **Cliente personalizado**: saludo por cuenta, última orden repetible con validación de stock/precio y recomendaciones locales según pedidos y ventas reales.
- 📊 **Panel de Gerencia**: Indicadores agregados de solo lectura y alertas operativas; no expone datos personales ni acciones administrativas.
- 🥗 **Información de producto**: Disponibilidad, alérgenos declarados y duración estimada de preparación visibles en el menú; no se presenta como tiempo de traslado garantizado.
- 📊 **Admin SaaS Dashboard**: KPIs operacionales, gráficos de tendencia y control total CRUD.
- 📱 **Paneles adaptables**: navegación y vistas operativas optimizadas para escritorio, tablet y pantallas pequeñas; QR usa el origen real de la aplicación.
- 🧹 **Instalación limpia**: seed sin mesas ficticiamente ocupadas, turno de demostración ni ventas inventadas; las métricas iniciales reflejan cero actividad real.

La personalización se calcula localmente en la base de datos. No se contrató ni conectó una IA externa o una pasarela de pago; Pago Móvil permanece sujeto a validación manual en caja.

Antes de borrar o recrear una base SQLite local, detén el servidor y respalda cada archivo fuera del repositorio. La operación elimina datos de prueba y no debe realizarse en producción. Los detalles de API y tablas están en [API.md](./API.md) y [DATABASE.md](./DATABASE.md).

---

## 🚦 Guía Rápida de Inicio

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Iniciar servidor FastAPI
python -m backend.app.main
```

Acceso web: [http://localhost:8000](http://localhost:8000)
