"""Lecture des donnees du Core via son API interne (cle de service)."""

import json
import urllib.error
import urllib.parse
import urllib.request

REPORT_PATH = '/api/internal/planning-report/'


class CoreUnavailable(Exception):
    pass


def fetch_planning_data(base_url: str, service_key: str, week_start, timeout=30) -> dict:
    query = urllib.parse.urlencode({'week_start': week_start.isoformat()})
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{REPORT_PATH}?{query}",
        headers={'X-Service-Key': service_key, 'Accept': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise CoreUnavailable(f'Le Core a repondu HTTP {exc.code}') from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise CoreUnavailable(f'Core injoignable : {exc}') from exc
