"""
Client HTTP du microservice "Moteur de planning".

Bibliotheque standard uniquement, comme frontend/mcp_link.py : un POST JSON
ne justifie pas d'ajouter une dependance.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

SOLVE_PATH = '/v1/solve'


class EngineError(Exception):
    """Le moteur est injoignable ou a refuse la requete."""


def solve(payload: dict) -> dict:
    url = settings.ENGINE_URL.rstrip('/') + SOLVE_PATH
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, cls=DjangoJSONEncoder).encode('utf-8'),
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-API-Key': settings.ENGINE_API_KEY,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.ENGINE_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise EngineError(f'Le moteur de planning a repondu HTTP {exc.code}.') from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EngineError('Le moteur de planning est injoignable.') from exc
    except ValueError as exc:
        raise EngineError('Reponse illisible du moteur de planning.') from exc
