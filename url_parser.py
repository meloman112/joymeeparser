import re
from urllib.parse import parse_qs, urlparse


def extract_url(text: str) -> str:
    m = re.search(r"https?://[^\s\])>]+", text.strip())
    if not m:
        raise ValueError("Пришли ссылку на API Joymi с параметрами")
    return m.group(0).rstrip(".,;)")


def parse_filter_url(text: str) -> dict:
    url = extract_url(text)
    parsed = urlparse(url)

    if "announcement" not in parsed.path and "joymi" not in parsed.netloc:
        raise ValueError("Нужна ссылка на api.joymi.uz/.../announcement/...")

    params = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=False).items()}
    if not params:
        raise ValueError("В ссылке нет query-параметров (?lat=...&radius=...)")

    path = parsed.path.rstrip("/")
    endpoint = path.split("/")[-1] if path else "all-in-map-by-radius"

    return {
        "url": url,
        "endpoint": endpoint,
        "params": params,
        "title": _title_from_params(params),
    }


def _title_from_params(params: dict[str, str]) -> str:
    parts = []
    for key in ("max_price", "lat", "long", "radius", "category"):
        if key in params:
            parts.append(f"{key}={params[key]}")
    if not parts:
        parts = [f"{k}={v}" for k, v in list(params.items())[:4]]
    return " · ".join(parts)
