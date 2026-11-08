"""
Microservice "Moteur de planning" de HospiPlan.

  GET  /health      sonde publique (Azure, tests apres deploiement)
  POST /v1/solve    calcule un planning ; en-tete X-API-Key obligatoire
  GET  /docs        documentation interactive (Swagger), generee par FastAPI

Le service est sans etat et sans base de donnees : il peut etre redemarre ou
duplique a volonte.
"""

import hmac
import logging
import os
import time

from fastapi import Depends, FastAPI, Header, HTTPException, status

from . import __version__
from .schemas import SolveRequest, SolveResponse
from .solver import solve

logging.basicConfig(level=logging.INFO, format='%(levelname)s:     [engine] %(message)s')
logger = logging.getLogger('engine')

API_KEY = os.environ.get('ENGINE_API_KEY', '')
if not API_KEY:
    raise RuntimeError(
        'ENGINE_API_KEY manquant : le moteur refuse de demarrer sans cle '
        "d'API (voir microservices/engine/.env.example)."
    )

app = FastAPI(
    title='HospiPlan - Moteur de planning',
    version=__version__,
    description=(
        "Calcule un planning hebdomadaire respectant les 8 contraintes dures "
        "et minimisant les penalites des contraintes molles."
    ),
)


def require_api_key(x_api_key: str | None = Header(default=None)):
    # compare_digest : comparaison a temps constant, evite de deviner la cle
    # caractere par caractere en mesurant le temps de reponse.
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Cle API invalide ou absente.')


@app.get('/health', tags=['supervision'])
def health():
    return {'service': 'engine', 'status': 'ok', 'version': __version__}


# Fonction synchrone : FastAPI l'execute dans un thread, le calcul ne bloque
# donc pas les autres requetes (dont /health).
@app.post(
    '/v1/solve',
    response_model=SolveResponse,
    dependencies=[Depends(require_api_key)],
    tags=['planning'],
)
def solve_planning(request: SolveRequest):
    started = time.perf_counter()
    assignments, unfilled, total_score, score_detail = solve(request)
    duration_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        'Semaine %s : %d creneaux, %d soignants -> %d affectations, %d non pourvus (%d ms)',
        request.week_start, len(request.shifts), len(request.staff),
        len(assignments), len(unfilled), duration_ms,
    )
    return SolveResponse(
        assignments=assignments,
        unfilled_shift_ids=unfilled,
        total_score=total_score,
        score_detail=score_detail,
        duration_ms=duration_ms,
    )
