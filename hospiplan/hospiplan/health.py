"""
Sonde de sante du service Core.

Seul endpoint public avec /login/ : il est appele par les sondes Azure et par
les tests apres deploiement, qui n'ont pas de session. Il ne revele rien
d'autre que l'etat du service et de sa base.
"""

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        database = 'ok'
    except Exception:
        database = 'unreachable'

    healthy = database == 'ok'
    return JsonResponse(
        {'service': 'core', 'status': 'ok' if healthy else 'degraded', 'database': database},
        status=200 if healthy else 503,
    )
