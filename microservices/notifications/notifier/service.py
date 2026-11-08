"""Traitement d'un evenement : un e-mail par destinataire, chacun trace."""

from dataclasses import dataclass

from .events import parse_event
from .store import now_iso
from .templates import render

DONE = ('sent', 'simulated')


class DeliveryFailed(RuntimeError):
    """Au moins un envoi a echoue : le message sera rejoue par la file."""


@dataclass
class Outcome:
    event_type: str
    sent: int = 0
    skipped: int = 0
    failed: int = 0


def process_event(raw, sender, store) -> Outcome:
    event = parse_event(raw)
    outcome = Outcome(event_type=event.type)

    for recipient in event.recipients:
        previous = store.get(event.id, recipient.email)
        # Deja envoye lors d'une tentative precedente : on ne renvoie pas.
        if previous and previous.get('status') in DONE:
            outcome.skipped += 1
            continue

        message = render(event, recipient)
        try:
            sender.send(recipient.email, recipient.name, message)
            status, error = sender.success_status, ''
            outcome.sent += 1
        except Exception as exc:  # noqa: BLE001 - tout echec est trace puis rejoue
            status, error = 'failed', f'{type(exc).__name__}: {exc}'[:500]
            outcome.failed += 1

        store.save({
            'event_id': event.id,
            'event_type': event.type,
            'recipient': recipient.email,
            'recipient_name': recipient.name,
            'subject': message.subject,
            'mode': sender.mode,
            'status': status,
            'error': error,
            'attempts': int(previous.get('attempts', 0)) + 1 if previous else 1,
            'created_at': previous.get('created_at') if previous else now_iso(),
            'updated_at': now_iso(),
        })

    if outcome.failed:
        raise DeliveryFailed(f'{outcome.failed} envoi(s) en echec pour {event.type} {event.id}')
    return outcome
