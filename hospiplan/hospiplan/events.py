"""
Publication des evenements metier vers la file Azure Storage Queue.

Le Core annonce ce qui s'est passe (planning publie, garde attribuee, absence
declaree) ; le microservice Notifications s'en charge ensuite, de facon
asynchrone. Le Core n'attend pas l'envoi des e-mails et ne sait meme pas
qu'ils existent.

Garanties :
  - publication apres le commit (transaction.on_commit) : pas d'annonce d'un
    changement finalement annule ;
  - une file indisponible ne fait jamais echouer la requete de l'utilisateur
    (l'erreur est journalisee) ;
  - sans EVENTS_STORAGE_CONNECTION_STRING, la publication est desactivee
    (ex. runserver sans Azurite).
"""

import json
import logging
import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

EVENT_VERSION = 1
_queue_client = None


def _client():
    global _queue_client
    if _queue_client is None:
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.queue import QueueClient, TextBase64EncodePolicy

        client = QueueClient.from_connection_string(
            settings.EVENTS_STORAGE_CONNECTION_STRING,
            settings.EVENTS_QUEUE_NAME,
            # Azure Functions attend des messages encodes en base64.
            message_encode_policy=TextBase64EncodePolicy(),
            retry_total=2,
            connection_timeout=5,
            read_timeout=5,
        )
        try:
            client.create_queue()
        except ResourceExistsError:
            pass
        _queue_client = client
    return _queue_client


def publish_event(event_type: str, data: dict) -> None:
    if not settings.EVENTS_STORAGE_CONNECTION_STRING:
        logger.info('Evenement %s non publie : file non configuree.', event_type)
        return

    body = json.dumps({
        'id': str(uuid.uuid4()),
        'type': event_type,
        'version': EVENT_VERSION,
        'occurred_at': timezone.now(),
        'source': 'core',
        'data': data,
    }, cls=DjangoJSONEncoder)

    def send():
        try:
            _client().send_message(body)
        except Exception:
            logger.exception('Publication de l\'evenement %s impossible.', event_type)

    transaction.on_commit(send)


# -- Aides pour construire les donnees des evenements --------------------------

def recipient(staff, **details) -> dict:
    return {'email': staff.email, 'name': f'{staff.first_name} {staff.last_name}'.strip(), **details}


def recipient_user(user, **details) -> dict:
    """Destinataire a partir d'un compte utilisateur Django (et non d'un soignant)."""
    return {'email': user.email, 'name': user.get_full_name() or user.get_username(), **details}


def shift_details(shift) -> dict:
    return {
        'start': shift.start_datetime,
        'end': shift.end_datetime,
        'shift_type': shift.shift_type.name,
        'care_unit': shift.care_unit.name,
        'service': shift.care_unit.service.name,
    }
