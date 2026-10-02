# Backend

API de gestión del hogar basada en FastAPI.

## Desarrollo

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

La configuración se carga desde variables de entorno. No se deben commitear
archivos `.env`.

## API financiera

La API usa importes enteros en centavos (`amount_cents`) y requiere un token
JWT de acceso. Sus grupos principales son:

- `/api/v1/categories`: categorías y sobres de la economía familiar.
- `/api/v1/periods`: períodos mensuales, ingresos y resúmenes.
- `/api/v1/recurring-expenses`: pagos fijos o variables que se repiten.
- `/api/v1/planned-expenses`: gastos futuros.
- `/api/v1/periods/{id}/allocations`: dinero separado por categoría.
- `/api/v1/periods/{id}/expenses`: gastos diarios, incluso divididos entre
  varios sobres.
- `/api/v1/periods/{id}/transfers`: transferencias entre sobres.
- `/api/v1/periods/{id}/rollover`: cierre y traspaso de saldos positivos al
  período siguiente.
