"""Minimal client for the Kroger public API (which powers QFC and Fred Meyer).

The API uses OAuth2 client credentials. Create a free app at
https://developer.kroger.com and set KROGER_CLIENT_ID and KROGER_CLIENT_SECRET.
Only the standard library is used, so no extra dependency is needed.
"""

import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://api.kroger.com/v1"
TOKEN_URL = f"{API_BASE}/connect/oauth2/token"
SCOPE = "product.compact"
TIMEOUT_SECONDS = 30


class KrogerError(RuntimeError):
    """Raised when the Kroger API cannot be used (credentials, network, response)."""


def load_dotenv(path: str | Path = ".env") -> None:
    """Load KEY=VALUE pairs from a local .env file into the environment.

    Existing environment variables win, so shell exports and CI secrets are not
    overridden. Comment lines, blank lines and a leading "export " are ignored.

    Arguments:
    path -- file to read; a relative path is resolved from the current directory.
    """
    env_file = Path(path)
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def credentials_from_env() -> tuple[str, str]:
    """Read the API client credentials from the environment.

    Returns:
    the client ID and client secret.

    Raises:
    KrogerError -- if KROGER_CLIENT_ID or KROGER_CLIENT_SECRET is unset.
    """
    client_id = os.environ.get("KROGER_CLIENT_ID")
    client_secret = os.environ.get("KROGER_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise KrogerError(
            "Set KROGER_CLIENT_ID and KROGER_CLIENT_SECRET to use the Kroger API. "
            "Create a free app at https://developer.kroger.com."
        )
    return client_id, client_secret


def _auth_headers(token: str) -> dict[str, str]:
    """Build the headers for an authenticated GET request.

    Arguments:
    token -- bearer token from get_access_token().

    Returns:
    headers with the bearer token and JSON accept type.
    """
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _request_json(request: Request) -> dict:
    """Send a request and decode its JSON response.

    Arguments:
    request -- fully built urllib request.

    Returns:
    the decoded JSON object.

    Raises:
    KrogerError -- if the request fails or the response is not a JSON object.
    """
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise KrogerError(
            f"Kroger API returned HTTP {error.code}: {detail[:500]}"
        ) from error
    except URLError as error:
        raise KrogerError(f"Could not reach the Kroger API: {error.reason}") from error

    try:
        body = json.loads(payload)
    except json.JSONDecodeError as error:
        raise KrogerError("Kroger API returned a non-JSON response.") from error
    if not isinstance(body, dict):
        raise KrogerError("Kroger API returned an unexpected response.")
    return body


def get_access_token(client_id: str, client_secret: str) -> str:
    """Exchange client credentials for a Kroger API access token.

    Arguments:
    client_id -- OAuth2 client ID from the Kroger developer portal.
    client_secret -- OAuth2 client secret from the Kroger developer portal.

    Returns:
    the bearer token used by the location and product endpoints.

    Raises:
    KrogerError -- if Kroger rejects the credentials or omits the token.
    """
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    form = urlencode({"grant_type": "client_credentials", "scope": SCOPE}).encode()
    request = Request(
        TOKEN_URL,
        data=form,
        method="POST",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    token = _request_json(request).get("access_token")
    if not token:
        raise KrogerError("Kroger API did not return an access token.")
    return token


def find_store(
    token: str, zip_code: str, chain: str = "QFC", radius_miles: int = 15
) -> dict:
    """Find the nearest store of one chain around a ZIP code.

    Arguments:
    token -- bearer token from get_access_token().
    zip_code -- ZIP code to search around, e.g. "98012".
    chain -- Kroger chain name, e.g. "QFC" or "FREDMEYER".
    radius_miles -- how far around the ZIP code to search.

    Returns:
    the nearest location object, including locationId and name.

    Raises:
    KrogerError -- if no matching store is found.
    """
    query = urlencode(
        {
            "filter.zipCode.near": zip_code,
            "filter.chain": chain,
            "filter.radiusInMiles": radius_miles,
            "filter.limit": 1,
        }
    )
    request = Request(f"{API_BASE}/locations?{query}", headers=_auth_headers(token))
    locations = _request_json(request).get("data") or []
    if not locations:
        raise KrogerError(
            f"No {chain} store found within {radius_miles} miles of ZIP {zip_code}."
        )
    return locations[0]


def search_products(
    token: str, term: str, location_id: str, limit: int = 50
) -> list[dict]:
    """Search products at one store, including that store's prices.

    Arguments:
    token -- bearer token from get_access_token().
    term -- search term, e.g. "eggs".
    location_id -- 8-character locationId from find_store().
    limit -- maximum number of products to return.

    Returns:
    the matching product objects; each has description, brand and items.

    Raises:
    KrogerError -- if the response does not contain a product list.
    """
    query = urlencode(
        {
            "filter.term": term,
            "filter.locationId": location_id,
            "filter.limit": limit,
        }
    )
    request = Request(f"{API_BASE}/products?{query}", headers=_auth_headers(token))
    products = _request_json(request).get("data")
    if not isinstance(products, list):
        raise KrogerError("Kroger API returned no product list.")
    return products
