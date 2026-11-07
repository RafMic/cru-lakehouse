import responses
from responses import matchers

BASE_URL = "https://rejestrumow.example/api-dp/v1"


def search_body(total: int, content: list[dict]) -> dict:
    return {"totalMatchingElements": total, "content": content}


def add_search_response(
    total: int, content: list[dict], *, limit: int, offset: int = 0, body: dict | None = None
) -> None:
    """Mock the search endpoint's reply to requests with the given offset and limit, and with the given body if any."""
    params = {"offset": str(offset), "limit": str(limit), "sortKey": "modificationDateAsc"}
    match = [matchers.query_param_matcher(params)]
    if body is not None:
        match.append(matchers.json_params_matcher(body))
    responses.add(responses.POST, f"{BASE_URL}/agreements/search", json=search_body(total, content), match=match)
