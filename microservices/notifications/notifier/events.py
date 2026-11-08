"""
Lecture et validation des evenements publies par le Core.

Format (version 1) :
{
  "id": "uuid", "type": "planning.published", "version": 1,
  "occurred_at": "2026-11-08T12:00:00+00:00", "source": "core",
  "data": { ..., "recipients": [{"email": "...", "name": "...", ...}] }
}
Chaque destinataire porte ses propres details (ex. ses gardes) : le service
n'a jamais besoin d'interroger le Core.
"""

import json
from dataclasses import dataclass, field

EVENT_TYPES = {
    'planning.published', 'assignment.created', 'absence.created', 'report.weekly',
    'password.reset_requested', 'account.requested', 'account.activated',
}
SUPPORTED_VERSION = 1
MAX_RECIPIENTS = 1000


class InvalidEvent(ValueError):
    """Message illisible ou non conforme : inutile de le rejouer."""


@dataclass(frozen=True)
class Recipient:
    email: str
    name: str
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    id: str
    type: str
    occurred_at: str
    data: dict
    recipients: tuple


def parse_event(raw) -> Event:
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    try:
        body = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise InvalidEvent('JSON invalide') from exc
    if not isinstance(body, dict):
        raise InvalidEvent("l'evenement doit etre un objet JSON")

    event_id, event_type = body.get('id'), body.get('type')
    if not isinstance(event_id, str) or not event_id:
        raise InvalidEvent('id manquant')
    if event_type not in EVENT_TYPES:
        raise InvalidEvent(f'type inconnu : {event_type!r}')
    if body.get('version') != SUPPORTED_VERSION:
        raise InvalidEvent(f"version non supportee : {body.get('version')!r}")

    data = body.get('data')
    if not isinstance(data, dict):
        raise InvalidEvent('data manquant')
    raw_recipients = data.get('recipients')
    if not isinstance(raw_recipients, list) or len(raw_recipients) > MAX_RECIPIENTS:
        raise InvalidEvent('recipients invalide')

    recipients = []
    for r in raw_recipients:
        if not isinstance(r, dict):
            raise InvalidEvent('destinataire invalide')
        email = str(r.get('email', '')).strip()
        if '@' not in email:
            raise InvalidEvent(f'adresse invalide : {email!r}')
        details = {k: v for k, v in r.items() if k not in ('email', 'name')}
        recipients.append(Recipient(email=email, name=str(r.get('name', '')), details=details))

    return Event(
        id=event_id,
        type=event_type,
        occurred_at=str(body.get('occurred_at', '')),
        data=data,
        recipients=tuple(recipients),
    )
