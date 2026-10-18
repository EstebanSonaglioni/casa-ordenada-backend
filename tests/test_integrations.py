from dataclasses import replace

from app.config import settings
from app.integrations import provider_request


def test_provider_response_accepts_list(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"is_reserve": True}]

    monkeypatch.setattr("app.integrations.httpx.get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr("app.integrations.settings", replace(settings, mercadopago_access_token="token"))

    assert provider_request("https://example.test") == [{"is_reserve": True}]


def test_provider_response_accepts_results_object(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"id": 1}]}

    monkeypatch.setattr("app.integrations.httpx.get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr("app.integrations.settings", replace(settings, mercadopago_access_token="token"))

    assert provider_request("https://example.test") == [{"id": 1}]
