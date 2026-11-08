"""
Microservice "Notifications" de HospiPlan (Azure Functions, Python v2).

  on_event                declenche par la file NOTIFICATIONS_QUEUE : un message
                          = un evenement metier publie par le Core
  GET /api/health         sonde publique
  GET /api/notifications  historique des envois ; en-tete X-API-Key obligatoire

Echec d'envoi : l'exception laisse le message dans la file, Functions le
rejoue (5 tentatives, voir host.json) puis le range dans la file "-poison".
Les destinataires deja servis ne sont pas relances (voir notifier.service).
"""

import hmac
import json
import logging
import os

import azure.functions as func

from notifier.events import InvalidEvent
from notifier.senders import build_sender
from notifier.service import process_event
from notifier.store import TableStore

# Le SDK Azure journalise chaque requete HTTP en INFO : trop bavard.
logging.getLogger('azure').setLevel(logging.WARNING)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

_sender = None
_store = None


def get_sender():
    global _sender
    if _sender is None:
        _sender = build_sender(os.environ)
    return _sender


def get_store():
    global _store
    if _store is None:
        _store = TableStore(os.environ['EVENTS_STORAGE'])
    return _store


def _json(body, status=200):
    return func.HttpResponse(json.dumps(body, ensure_ascii=False), status_code=status,
                             mimetype='application/json')


@app.queue_trigger(arg_name='msg', queue_name='%NOTIFICATIONS_QUEUE%', connection='EVENTS_STORAGE')
def on_event(msg: func.QueueMessage):
    try:
        outcome = process_event(msg.get_body(), get_sender(), get_store())
    except InvalidEvent as exc:
        # Rejouer un message mal forme ne servirait a rien : on le trace et on l'abandonne.
        logging.error('Message %s rejete : %s', msg.id, exc)
        return
    logging.info('%s : %d envoye(s), %d deja traite(s) [mode %s]',
                 outcome.event_type, outcome.sent, outcome.skipped, get_sender().mode)


@app.route(route='health', methods=['GET'])
def health(req: func.HttpRequest):
    return _json({'service': 'notifications', 'status': 'ok',
                  'email_mode': os.environ.get('EMAIL_MODE', 'simulated')})


@app.route(route='notifications', methods=['GET'])
def list_notifications(req: func.HttpRequest):
    expected = os.environ.get('NOTIFICATIONS_API_KEY', '')
    given = req.headers.get('X-API-Key', '')
    if not expected or not hmac.compare_digest(given, expected):
        return _json({'detail': 'Cle API invalide ou absente.'}, status=401)
    try:
        limit = max(1, min(int(req.params.get('limit', 50)), 500))
    except ValueError:
        limit = 50
    return _json({'notifications': get_store().list_recent(limit)})
