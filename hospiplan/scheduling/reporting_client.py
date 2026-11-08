"""Client HTTP du microservice "Reporting" (bibliotheque standard uniquement)."""

import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class ReportingError(Exception):
    """Le service Reporting est injoignable ou a refuse la requete."""


def planning_pdf(week_start) -> bytes:
    query = urllib.parse.urlencode({'week_start': week_start.isoformat()})
    request = urllib.request.Request(
        f"{settings.REPORTING_URL.rstrip('/')}/api/reports/planning?{query}",
        headers={'X-API-Key': settings.REPORTING_API_KEY, 'Accept': 'application/pdf'},
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.REPORTING_TIMEOUT_SECONDS) as response:
            if response.headers.get_content_type() != 'application/pdf':
                raise ReportingError('Reponse inattendue du service Reporting.')
            return response.read()
    except urllib.error.HTTPError as exc:
        raise ReportingError(f'Le service Reporting a repondu HTTP {exc.code}.') from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ReportingError('Le service Reporting est injoignable.') from exc
