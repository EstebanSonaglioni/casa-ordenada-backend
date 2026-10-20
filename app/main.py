import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.auth import router as auth_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.finance import router as finance_router
from app.finance_models import Category, Currency, Household, HouseholdMember
from app.inventory import router as inventory_router
from app.health import router as health_router
from app.assistant import router as assistant_router
from app.assistant import cleanup_expired
from app.inventory_models import InventoryCategory, StorageLocation
from app.integrations import router as integrations_router
from app.household import router as household_router
from app.household_context import active_household_id
from app.models import User
from app.security import hash_password


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "role VARCHAR(50) NOT NULL DEFAULT 'member'"
            )
        )
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(120)"))
        connection.execute(text("UPDATE users SET display_name = username WHERE display_name IS NULL"))
    if not settings.test_user_username or not settings.test_user_password:
        return

    with SessionLocal() as database:
        if database.scalar(select(Currency.id).where(Currency.code == "ARS")) is None:
            database.add(Currency(code="ARS", name="Peso argentino", symbol="$", decimal_places=2))
        if database.scalar(select(Currency.id).where(Currency.code == "USD")) is None:
            database.add(Currency(code="USD", name="Dólar estadounidense", symbol="US$", decimal_places=2))
        database.commit()
        existing_user = database.scalar(
            select(User).where(User.username == settings.test_user_username)
        )
        if existing_user is None:
            database.add(
                User(
                    username=settings.test_user_username,
                    display_name=settings.test_user_username,
                    password_hash=hash_password(settings.test_user_password),
                    role=settings.test_user_role,
                )
            )
            database.commit()

        user = database.scalar(select(User).where(User.username == settings.test_user_username))
        if user is not None:
            if user.role != settings.test_user_role:
                user.role = settings.test_user_role
            household = database.scalar(select(Household).where(Household.name == "Casa familiar"))
            if household is None:
                household = Household(name="Casa familiar")
                database.add(household)
                database.flush()
            membership = database.scalar(
                select(HouseholdMember).where(
                    HouseholdMember.household_id == household.id,
                    HouseholdMember.user_id == user.id,
                )
            )
            if membership is None:
                database.add(HouseholdMember(household_id=household.id, user_id=user.id, role=user.role))
            else:
                membership.role = user.role
            if database.scalar(select(Category.id).where(Category.household_id == household.id)) is None:
                database.add_all([
                    Category(household_id=household.id, name=name, kind=kind, color=color)
                    for name, kind, color in [
                        ("Seguros", "fixed", "#5B8266"),
                        ("Servicios", "fixed", "#5B8266"),
                        ("Cuotas", "fixed", "#E07A5F"),
                        ("Carnes", "variable", "#E07A5F"),
                        ("Verdulería", "variable", "#5B8266"),
                        ("Limpieza", "variable", "#F2CC8F"),
                        ("Bebé", "variable", "#F2CC8F"),
                        ("Nafta", "variable", "#E07A5F"),
                        ("Futuro", "future", "#F2CC8F"),
                    ]
                ])
            if database.scalar(select(InventoryCategory.id).where(InventoryCategory.household_id == household.id)) is None:
                database.add_all([
                    InventoryCategory(household_id=household.id, name=name, color=color, icon=icon)
                    for name, color, icon in [
                        ("Alimentos", "#5B8266", "food"),
                        ("Limpieza", "#5C7CFA", "clean"),
                        ("Higiene", "#9C6ADE", "hygiene"),
                        ("Bebé", "#F2CC8F", "baby"),
                        ("Farmacia", "#E07A5F", "medicine"),
                        ("Otros", "#4D908E", "other"),
                    ]
                ])
            if database.scalar(select(StorageLocation.id).where(StorageLocation.household_id == household.id)) is None:
                database.add_all([
                    StorageLocation(household_id=household.id, name=name, kind=kind)
                    for name, kind in [
                        ("Heladera", "refrigerated"),
                        ("Freezer", "frozen"),
                        ("Alacena", "pantry"),
                        ("Baño", "bathroom"),
                        ("Lavadero", "laundry"),
                    ]
                ])
            database.commit()


async def assistant_cleanup_loop() -> None:
    while True:
        await asyncio.sleep(3600)
        with SessionLocal() as database:
            cleanup_expired(database)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    cleanup_task = asyncio.create_task(assistant_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Casa Ordenada API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def active_household_middleware(request: Request, call_next):
    raw_household_id = request.headers.get("X-Household-ID")
    try:
        household_id = int(raw_household_id) if raw_household_id else None
    except ValueError:
        household_id = None
    token = active_household_id.set(household_id)
    try:
        return await call_next(request)
    finally:
        active_household_id.reset(token)
app.include_router(auth_router)
app.include_router(finance_router)
app.include_router(inventory_router)
app.include_router(health_router)
app.include_router(assistant_router)
app.include_router(integrations_router)
app.include_router(household_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
