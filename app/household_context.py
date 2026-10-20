from contextvars import ContextVar


active_household_id: ContextVar[int | None] = ContextVar("active_household_id", default=None)
