import base64
import io
import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pytest

from grocery_price_tracking.common import kroger


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_get_access_token_posts_client_credentials(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse({"access_token": "token-123"})

    monkeypatch.setattr(kroger, "urlopen", fake_urlopen)

    assert kroger.get_access_token("client", "secret") == "token-123"
    request = captured["request"]
    assert request.full_url == kroger.TOKEN_URL
    assert request.get_method() == "POST"
    assert request.data == b"grant_type=client_credentials&scope=product.compact"
    expected = base64.b64encode(b"client:secret").decode()
    assert request.get_header("Authorization") == f"Basic {expected}"


def test_find_store_returns_nearest_match(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse(
            {"data": [{"locationId": "70500123", "name": "QFC Test Store"}]}
        )

    monkeypatch.setattr(kroger, "urlopen", fake_urlopen)

    store = kroger.find_store("token", "98012")

    assert store["locationId"] == "70500123"
    query = parse_qs(urlparse(captured["url"]).query)
    assert query["filter.zipCode.near"] == ["98012"]
    assert query["filter.chain"] == ["QFC"]
    assert query["filter.limit"] == ["1"]


def test_find_store_raises_when_empty(monkeypatch):
    monkeypatch.setattr(
        kroger, "urlopen", lambda request, timeout: FakeResponse({"data": []})
    )

    with pytest.raises(kroger.KrogerError, match="No QFC store"):
        kroger.find_store("token", "98012")


def test_search_products_uses_store_and_term(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse({"data": [{"productId": "0001111060903"}]})

    monkeypatch.setattr(kroger, "urlopen", fake_urlopen)

    products = kroger.search_products("token", "eggs", "70500123", limit=20)

    assert products == [{"productId": "0001111060903"}]
    query = parse_qs(urlparse(captured["url"]).query)
    assert query["filter.term"] == ["eggs"]
    assert query["filter.locationId"] == ["70500123"]
    assert query["filter.limit"] == ["20"]


def test_http_error_becomes_kroger_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"bad credentials"}'),
        )

    monkeypatch.setattr(kroger, "urlopen", fake_urlopen)

    with pytest.raises(kroger.KrogerError, match=r"HTTP 401.*bad credentials"):
        kroger.get_access_token("client", "secret")


def test_network_error_becomes_kroger_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise URLError("dns failure")

    monkeypatch.setattr(kroger, "urlopen", fake_urlopen)

    with pytest.raises(kroger.KrogerError, match=r"Could not reach.*dns failure"):
        kroger.get_access_token("client", "secret")


def test_non_json_response_becomes_kroger_error(monkeypatch):
    class NotJson(FakeResponse):
        def read(self):
            return b"<html>"

    monkeypatch.setattr(kroger, "urlopen", lambda request, timeout: NotJson(None))

    with pytest.raises(kroger.KrogerError, match="non-JSON"):
        kroger.get_access_token("client", "secret")


def test_non_object_response_becomes_kroger_error(monkeypatch):
    monkeypatch.setattr(
        kroger, "urlopen", lambda request, timeout: FakeResponse([1, 2])
    )

    with pytest.raises(kroger.KrogerError, match="unexpected response"):
        kroger.get_access_token("client", "secret")


def test_missing_access_token_becomes_kroger_error(monkeypatch):
    monkeypatch.setattr(kroger, "urlopen", lambda request, timeout: FakeResponse({}))

    with pytest.raises(kroger.KrogerError, match="did not return an access token"):
        kroger.get_access_token("client", "secret")


def test_search_products_requires_a_list(monkeypatch):
    monkeypatch.setattr(kroger, "urlopen", lambda request, timeout: FakeResponse({}))

    with pytest.raises(kroger.KrogerError, match="no product list"):
        kroger.search_products("token", "eggs", "70500123")


def test_credentials_from_env_requires_both(monkeypatch):
    monkeypatch.delenv("KROGER_CLIENT_ID", raising=False)
    monkeypatch.delenv("KROGER_CLIENT_SECRET", raising=False)

    with pytest.raises(kroger.KrogerError, match="KROGER_CLIENT_ID"):
        kroger.credentials_from_env()

    monkeypatch.setenv("KROGER_CLIENT_ID", "client")
    monkeypatch.setenv("KROGER_CLIENT_SECRET", "secret")
    assert kroger.credentials_from_env() == ("client", "secret")


def test_load_dotenv_reads_file_without_overriding_shell(monkeypatch, tmp_path):
    monkeypatch.delenv("KROGER_CLIENT_ID", raising=False)
    monkeypatch.setenv("KROGER_CLIENT_SECRET", "from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# local secrets\n"
        'KROGER_CLIENT_ID="file-id"\n'
        "export KROGER_CLIENT_SECRET='file-secret'\n"
        "not-a-setting\n"
    )

    kroger.load_dotenv(env_file)

    assert kroger.credentials_from_env() == ("file-id", "from-shell")


def test_load_dotenv_ignores_missing_file(tmp_path):
    kroger.load_dotenv(tmp_path / "missing.env")
