class ApiConstants {
  // Production URL on Render
  static const String defaultProductionUrl =
      'https://app-dondedavid.onrender.com';
  static const String defaultLocalhostUrl = 'http://localhost:8000';
  static const String defaultEmulatorUrl = 'http://10.0.2.2:8000';

  // Default Base URL points directly to the live production server
  static const String defaultBaseUrl = defaultProductionUrl;

  static const String apiV1 = '/api/v1';

  // Auth
  static const String login = '$apiV1/auth/login';
  static const String register = '$apiV1/auth/register';
  static const String me = '$apiV1/auth/me';

  // Cliente
  static const String configuracionesPublicas =
      '$apiV1/cliente/configuraciones-publicas';
  static const String categorias = '$apiV1/cliente/categorias';
  static const String productos = '$apiV1/cliente/productos';
  static const String promociones = '$apiV1/cliente/promociones';
  static const String resenas = '$apiV1/cliente/resenas';
  static const String publicaciones = '$apiV1/cliente/publicaciones';
  static const String crearPedido = '$apiV1/cliente/pedidos';
  static const String trackingPedido =
      '$apiV1/cliente/pedidos'; // + /{id}/seguimiento
  static const String historialPedidos = '$apiV1/cliente/pedidos/historial';
  static const String personalizacion = '$apiV1/cliente/personalizacion';
  static const String solicitudesMesa = '$apiV1/cliente/solicitudes-mesa';
  static const String verificarOtp = '$apiV1/cliente/pedidos/verificar-otp';

  // Cocina KDS
  static const String cocinaPedidos = '$apiV1/cocina/pedidos';
  static const String cocinaEstadoPedido =
      '$apiV1/cocina/pedidos'; // + /{id}/estado

  // Mesero
  static const String meseroMesas = '$apiV1/mesero/mesas';
  static const String meseroLimpieza =
      '$apiV1/mesero/mesas'; // + /{id}/limpieza
  static const String meseroSolicitudes =
      '$apiV1/mesero/solicitudes'; // + /{id}/estado
  static const String meseroPedidosActivos = '$apiV1/mesero/pedidos-activos';
  static const String meseroMarcarEntregado =
      '$apiV1/mesero/pedidos'; // + /{id}/marcar-entregado
  static const String meseroCambiarMesa =
      '$apiV1/mesero/pedidos'; // + /{id}/cambiar-mesa

  // Caja POS
  static const String cajaTurnoActivo = '$apiV1/caja/turno-activo';
  static const String cajaAbrirTurno = '$apiV1/caja/abrir-turno';
  static const String cajaCerrarTurno = '$apiV1/caja/cerrar-turno';
  static const String cajaPedidosPendientes = '$apiV1/caja/pedidos-pendientes';
  static const String cajaCobrar = '$apiV1/caja/pedidos'; // + /{id}/cobrar
  static const String cajaConfirmarPago =
      '$apiV1/caja/pedidos'; // + /{id}/confirmar-pago
  static const String cajaPedidosRetiro = '$apiV1/caja/pedidos-retiro';
  static const String cajaConfirmarRetiro =
      '$apiV1/caja/pedidos'; // + /{id}/confirmar-retiro
  static const String cajaMovimientos = '$apiV1/caja/movimientos';
  static const String cajaCrearYCobrarRapido =
      '$apiV1/caja/crear-y-cobrar-rapido';

  // Delivery
  static const String deliveryMisPedidos = '$apiV1/delivery/mis-pedidos';
  static const String deliveryEstado =
      '$apiV1/delivery/pedidos'; // + /{id}/estado
  static const String deliveryEntregar =
      '$apiV1/delivery/pedidos'; // + /{id}/entregar
  static const String deliveryUbicacion =
      '$apiV1/delivery/pedidos'; // + /{id}/ubicacion
  static const String deliveryDespachoPedidos =
      '$apiV1/delivery/despacho/pedidos';
  static const String deliveryDespachoRepartidores =
      '$apiV1/delivery/despacho/repartidores';

  // Gerencia / Admin
  static const String gerenciaDashboard = '$apiV1/gerencia/dashboard';
  static const String adminDashboardStats = '$apiV1/admin/dashboard-stats';
  static const String adminProductos = '$apiV1/admin/productos';
  static const String adminCategorias = '$apiV1/admin/categorias';
  static const String adminInsumos = '$apiV1/admin/insumos';
  static const String adminInventarioMovimientos =
      '$apiV1/admin/inventario/movimientos';
  static const String adminMesas = '$apiV1/admin/mesas';
  static const String adminUsuarios = '$apiV1/admin/usuarios';
  static const String adminConfiguraciones = '$apiV1/admin/configuraciones';
  static const String adminConfiguracionesLote =
      '$apiV1/admin/configuraciones/lote';
  static const String adminTasaBcvActualizar =
      '$apiV1/admin/tasa-bcv/actualizar';
  static const String adminPromociones = '$apiV1/admin/promociones';
  static const String adminResenas = '$apiV1/admin/resenas';
  static const String adminPublicaciones = '$apiV1/admin/publicaciones';

  // WebSocket endpoint
  static const String ws = '/ws';
}
