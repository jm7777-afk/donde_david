# 📱 DONDE DAVID Enterprise — Mobile App (Flutter)

App móvil oficial multiplataforma (Android, iOS, Web, Windows/macOS) desarrollada con **Flutter 3** y arquitectura limpia (Clean Feature-First Architecture), consumiendo directamente la suite de APIs REST y WebSockets del backend FastAPI del restaurante **DONDE DAVID**.

---

## 🎨 Identidad Visual y Design System (DONDE DAVID Dark Neon)

La aplicación implementa fielmente los tokens visuales y la psicología del color definidos en `DESIGN_SYSTEM.md` y `toon-theme.css`:

| Token | Hex | Uso en la App |
|---|---|---|
| `--brand-navy` | `#071A3D` | Fondo principal oscuro, app bars y gradientes de profundidad. |
| `--brand-navy-dark` | `#0B2557` | Superficie secundaria y contenedores de tarjetas. |
| `--brand-orange` | `#FF7A00` | Botones de llamado a la acción primarios (**CTA**), precios destacados. |
| `--brand-yellow` | `#FFC400` / `#FFBC0D` | Acento Fast Food dorado, títulos de impacto, puntos e insignias VIP. |
| `--cyan-accent` | `#00F5D4` | Escaneo QR de mesa, 1-Clic Reorder, delivery tracking en tiempo real. |
| `--success` | `#22C55E` | Pedido listo, pagado, mesa libre, entrega confirmada. |
| `--danger` | `#F21D1D` | Urgencias >15m en cocina, errores, cancelaciones, alérgenos. |
| `--warning` | `#F59E0B` | Pedidos en cola, mesas ocupadas, validación de pago móvil pendiente. |

---

## 🏛️ Arquitectura del Proyecto

```
mobile_app/
├── assets/
│   └── images/
│       ├── logo.png
│       └── logo-donde-david.jpg
├── lib/
│   ├── core/
│   │   ├── constants/
│   │   │   └── api_constants.dart      # Rutas de endpoints REST y WebSocket
│   │   ├── services/
│   │   │   ├── api_service.dart        # Cliente HTTP con Bearer Tokens e interceptores
│   │   │   ├── storage_service.dart    # Persistencia local con SharedPreferences
│   │   │   └── websocket_service.dart  # Conexión persistente y reconexión en /ws
│   │   └── theme/
│   │       ├── app_colors.dart         # Tokens de color exactos
│   │       └── app_theme.dart          # ThemeData oscuro con Material 3
│   ├── models/
│   │   ├── categoria.dart              # Categorías del menú
│   │   ├── mesa.dart                   # Estado multimodal de mesas de salón
│   │   ├── pedido.dart                 # Pedidos, detalles, personalizaciones y extras
│   │   ├── producto.dart               # Platos, ingredientes, stock y fotos
│   │   ├── solicitud_mesa.dart         # Llamadas a mesero y solicitudes de cuenta
│   │   ├── turno.dart                  # Turnos de caja y arqueos contables
│   │   └── usuario.dart                # Modelo de usuario (cliente / roles staff)
│   ├── providers/
│   │   ├── auth_provider.dart          # Sesión, login, registro de clientes (+50 pts)
│   │   ├── cart_provider.dart          # Carrito, cálculo de IVA 16%, delivery y empaque
│   │   ├── catalog_provider.dart       # Catálogo, tasa BCV en tiempo real, mesa activa
│   │   ├── order_provider.dart         # Checkout en 5 pasos, historial y tracking
│   │   └── staff_provider.dart         # Orquestador de mesero, cocina, caja y delivery
│   ├── screens/
│   │   ├── client/
│   │   │   ├── client_main_screen.dart # Shell con BottomNavigationBar de 5 pestañas
│   │   │   ├── home_tab.dart           # Portada, tasa BCV, accesos de mesa y destacados
│   │   │   ├── menu_tab.dart           # Menú completo con buscador e ingredientes
│   │   │   ├── cart_tab.dart           # Checkout guiado de 5 pasos con Pago Móvil
│   │   │   ├── order_history_tab.dart  # Historial y repetición 1-clic
│   │   │   └── profile_tab.dart        # Perfil y saldo de puntos de fidelidad
│   │   └── staff/
│   │       ├── staff_login_screen.dart # Login de empleados y accesos demo solo en debug
│   │       ├── waiter_screen.dart      # Panel de meseros con mapa táctil de mesas
│   │       ├── kitchen_kds_screen.dart # Monitor de cocina KDS con semáforo y filtros
│   │       ├── pos_cashier_screen.dart # Caja POS, turnos, validación Pago Móvil
│   │       ├── delivery_courier_screen.dart # Panel de repartidor con OTP de entrega
│   │       └── admin_dashboard_screen.dart  # Métricas gerenciales y accesos rápidos
│   ├── widgets/
│   │   ├── brand_header.dart           # Cabecera sticky con logo y tasa BCV
│   │   ├── donde_david_button.dart     # Botones CTA y Gold
│   │   ├── donde_david_card.dart       # Tarjetas glassmorphism
│   │   ├── floating_cart_widget.dart   # Widget flotante inferior con total del pedido
│   │   ├── product_card.dart           # Tarjeta de producto con foto y precio dual
│   │   ├── product_detail_sheet.dart   # BottomSheet con extras y personalizaciones
│   │   ├── qr_scanner_dialog.dart      # Escáner y selector rápido de mesa
│   │   ├── server_config_dialog.dart   # Ajuste en caliente de IP/puerto del backend
│   │   └── status_badge.dart           # Badges de estado multimodales
│   └── main.dart                       # Punto de entrada reactivo de la aplicación
└── test/
    └── widget_test.dart                # Pruebas unitarias de modelos y cálculos de caja
```

---

## 🚀 Funcionalidades Clave Implementadas

### 1. Modo Cliente (Público, Mesa QR & Delivery)
- **Tasa BCV Dinámica**: Muestra la tasa oficial del día en tiempo real (`GET /api/v1/cliente/configuraciones-publicas`) con conversión automática de todos los precios a Bolívares (Bs.) y Dólares (\$ USD).
- **Mesa QR**: Escaneo de código QR o selección táctil de mesa. Al estar en mesa, se activan los botones directos de **"🙋 Llamar Mesero"** y **"🧾 Pedir Cuenta"** (`POST /api/v1/cliente/solicitudes-mesa`).
- **Personalización de Platos**: Bottom sheet modal para agregar toppings/extras (`extras_json`) y excluir ingredientes ("Sin cebolla", "Sin salsas", etc.).
- **Checkout Guiado en 5 Pasos**:
  1. **Carrito**: Revisión de platos, cantidades, subtotal, IVA del 16%, empaque para llevar (\$1.00) y delivery (\$5.00).
  2. **Entrega**: Modalidad (Mesa, Delivery con dirección y GPS, o Para Llevar con retiro en mostrador). En mesa permite elegir entre *Pagar antes* o *Cuenta abierta*.
  3. **Resumen**: Verificación de destino, importes finales y puntos acumulables.
  4. **Método de Pago**: Efectivo, Punto de Venta físico, o Pago Móvil (muestra datos bancarios del restaurante y campo para ingresar la referencia bancaria).
  5. **Seguimiento en Vivo**: Consulta el estado de la comanda en tiempo real. Muestra el **código OTP de entrega** para pedidos delivery o el **código de retiro de 6 dígitos** para pedidos para llevar.
- **Puntos de Fidelidad & Repetición 1-Clic**: Bono de 50 puntos al registrarse como nuevo cliente y botón para reordenar el pedido anterior instantáneamente.

### 2. Portal de Personal & Empleados (Staff)
- **Mesero**: Mapa interactivo de mesas con estado (`LIBRE`, `OCUPADA`, `PENDIENTE_LIMPIEZA`, `EN_LIMPIEZA`), antigüedad de ocupación en minutos, bandeja de llamadas del salón y pedidos listos para servir.
- **Cocina KDS**: Contadores en vivo (`RECIBIDOS`, `PREPARANDO`, `LISTOS`), alertas de pedidos urgentes (>15 minutos), filtros por modalidad y botones de avance de comanda.
- **Caja POS**: Apertura y cierre de turnos con arqueo contable en USD, cobro y facturación de cuentas, validación manual de Pago Móvil (aprobar o rechazar con reposición de inventario) y confirmación de retiro en mostrador con código de 6 dígitos.
- **Repartidor Delivery**: Mis pedidos asignados, cambio de estado de ruta (`RECOGIDO` → `EN_CAMINO`) y confirmación de entrega segura validando el código OTP del cliente.
- **WebSocket en Tiempo Real**: Conexión bidireccional a `/ws` con autenticación JWT para sincronización instantánea de comandas, mesas y cobros entre todos los dispositivos del personal.

---

## 🛠️ Cómo Ejecutar la App Móvil

### 1. Iniciar el Backend FastAPI
Asegúrate de que el servidor FastAPI esté corriendo en la raíz del proyecto:
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Configurar la Conexión de Red
- **En Emulador Android**: La app usa por defecto `http://10.0.2.2:8000`.
- **En Dispositivo Físico (Teléfono por Wi-Fi)**: Abre la app, toca el botón de configuración (ícono de ecualizador en la esquina superior derecha) y escribe la IP local de tu PC (ejemplo: `http://192.168.1.100:8000`).
- **En Windows / Web**: Conecta directamente a `http://localhost:8000`.

### 3. Ejecutar la App en Flutter
Dentro de la carpeta `mobile_app`:
```bash
cd mobile_app
flutter run
```

Los accesos directos de cuentas demo están deshabilitados por defecto. Solo se habilitan en una compilación debug con `--dart-define=ENABLE_DEMO_LOGINS=true` y deben usarse contra un backend de desarrollo. En producción, el personal debe ingresar sus credenciales asignadas. La confirmación biométrica requiere usuario y contraseña; no reemplaza ni genera credenciales.

---

## 💡 Recomendaciones del Equipo Senior de Desarrollo

1. **Notificaciones Push (FCM / Firebase Cloud Messaging)**:
   - Integrar `firebase_messaging` para notificar al cliente en segundo plano cuando su pedido pase a estado `LISTO` o `EN_CAMINO`, y al mesero cuando una mesa solicite la cuenta.
2. **Geolocalización Nativa & Mapas**:
   - Integrar `geolocator` y `flutter_map` / `google_maps_flutter` para que los clientes puedan arrastrar un pin directamente sobre el mapa para su entrega delivery.
3. **Validar escaneo QR en dispositivos reales**:
   - El escáner usa `mobile_scanner`; verificar permisos, manejo de cámara ocupada y los formatos de QR desplegados en Android e iOS.
4. **Fortalecer el modo sin conexión**:
   - El catálogo tiene caché en `SharedPreferences`. Mostrar cuándo los datos están desactualizados y evitar que precios en caché se usen como autoridad para crear pedidos.
5. **Endurecer la autenticación biométrica**:
   - `local_auth` confirma la identidad local antes de enviar las credenciales ingresadas. Para un acceso biométrico sin contraseña, primero se requiere un diseño con almacenamiento seguro y revocación de sesión.
