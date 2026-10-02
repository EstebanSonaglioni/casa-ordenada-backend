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
