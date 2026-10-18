# Changelog

## [Unreleased]

### Added

- API FastAPI inicial con endpoint de login y renovación de tokens JWT.
- Modelo de usuario con contraseña hasheada y seed configurable para desarrollo.
- Roles persistidos en usuarios y propagados en tokens de autenticación.
- Modelos y endpoints para ingresos, períodos, categorías, sobres, gastos y
  transferencias, con importes en centavos y validación de distribuciones.
- Migraciones Alembic y rollover de saldos positivos entre períodos.
- El usuario de desarrollo `aleman` se sincroniza con rol `owner` al iniciar.
- Monedas, cotizaciones históricas y conversión de resúmenes a ARS.
- Vencimientos recurrentes almacenados como fechas.
- Endpoint de historial financiero que unifica ingresos, asignaciones, gastos y
  transferencias por período, sobre, moneda o tipo.
- Endpoint de calendario mensual para vencimientos recurrentes y gastos previstos.
- Registro de pagos por vencimiento recurrente y actualización de estado de pagos previstos.
- Endpoints para editar y eliminar sobres sin movimientos.
- Endpoint para actualizar el color de la categoría asociada a un sobre.

### Fixed

- Migración inicial de Inventario tolera tablas existentes sin versión Alembic registrada.
- CORS admite `https://localhost` para WebView de Capacitor.
- Integración server-side de Mercado Pago con sincronización configurable, reservas y vinculación de movimientos a sobres.
- Uso del endpoint oficial de reportes de liberación para detectar reservas.
- Importación de filas del reporte Account Money con deduplicación por `SOURCE_ID`.
- El saldo general y disponible de cada sobre usan solo el monto asignado; el
  monto planificado queda como meta informativa.
- La creación de una categoría duplicada devuelve `409` con un mensaje claro.
- El monto planificado de un sobre es opcional y toma valor cero por defecto.
- Modelos, migración y API de inventario por lote, productos, ubicaciones, lista de compras y checkout financiero.
- Subcategorías, iconos editables, historial filtrable y edición de fecha/comercio de compras.
- Apertura parcial de lotes por unidades y campo de cantidad abierta.

### Changed

- CORS admite orígenes de Capacitor durante el desarrollo Android local.
