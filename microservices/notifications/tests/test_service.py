import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notifier.events import InvalidEvent, parse_event  # noqa: E402
from notifier.senders import ConfigError, SimulatedSender, build_sender  # noqa: E402
from notifier.service import DeliveryFailed, process_event  # noqa: E402
from notifier.store import MemoryStore  # noqa: E402
from notifier.templates import render  # noqa: E402

SHIFT = {
    'start': '2026-11-09T06:00:00Z', 'end': '2026-11-09T14:00:00Z',
    'shift_type': 'Matin', 'service': 'Urgences', 'care_unit': 'Box A',
}


def event(type_='planning.published', recipients=None, **data):
    if recipients is None:
        recipients = [
            {'email': 'alice@test.fr', 'name': 'Alice Martin', 'shifts': [SHIFT]},
            {'email': 'bob@test.fr', 'name': 'Bob Durand', 'shifts': [SHIFT, SHIFT]},
        ]
    return json.dumps({
        'id': 'evt-1', 'type': type_, 'version': 1, 'occurred_at': '2026-11-08T10:00:00Z',
        'source': 'core',
        'data': {'week_start': '2026-11-09', 'week_end': '2026-11-15', 'recipients': recipients, **data},
    })


class RecordingSender:
    mode, success_status = 'mailpit', 'sent'

    def __init__(self, fail_for=()):
        self.sent, self.fail_for = [], set(fail_for)

    def send(self, email, name, message):
        if email in self.fail_for:
            raise ConnectionError('SMTP indisponible')
        self.sent.append((email, message.subject))


def test_one_email_per_recipient_and_history():
    sender, store = RecordingSender(), MemoryStore()
    outcome = process_event(event(), sender, store)
    assert outcome.sent == 2 and outcome.failed == 0
    assert {e for e, _ in sender.sent} == {'alice@test.fr', 'bob@test.fr'}
    assert all(r['status'] == 'sent' for r in store.list_recent())


def test_replayed_event_does_not_resend():
    sender, store = RecordingSender(), MemoryStore()
    process_event(event(), sender, store)
    outcome = process_event(event(), sender, store)
    assert outcome.skipped == 2 and len(sender.sent) == 2


def test_failure_is_recorded_then_retry_only_failed_recipient():
    store = MemoryStore()
    with pytest.raises(DeliveryFailed):
        process_event(event(), RecordingSender(fail_for={'bob@test.fr'}), store)
    statuses = {r['recipient']: r['status'] for r in store.list_recent()}
    assert statuses == {'alice@test.fr': 'sent', 'bob@test.fr': 'failed'}

    retry_sender = RecordingSender()
    outcome = process_event(event(), retry_sender, store)
    assert retry_sender.sent == [('bob@test.fr', retry_sender.sent[0][1])]
    assert outcome.sent == 1 and outcome.skipped == 1
    bob = next(r for r in store.list_recent() if r['recipient'] == 'bob@test.fr')
    assert bob['status'] == 'sent' and bob['attempts'] == 2


def test_simulated_mode_records_without_sending():
    store = MemoryStore()
    process_event(event(), SimulatedSender(), store)
    assert {r['status'] for r in store.list_recent()} == {'simulated'}


@pytest.mark.parametrize('raw', [
    'pas du json',
    json.dumps({'id': 'x', 'type': 'inconnu', 'version': 1, 'data': {'recipients': []}}),
    json.dumps({'id': 'x', 'type': 'absence.created', 'version': 2, 'data': {'recipients': []}}),
    event(recipients=[{'email': 'sans-arobase', 'name': 'X'}]),
])
def test_invalid_events_are_rejected(raw):
    with pytest.raises(InvalidEvent):
        parse_event(raw)


def test_planning_email_content_in_paris_time():
    ev = parse_event(event())
    msg = render(ev, ev.recipients[0])
    assert msg.subject == 'Votre planning du lundi 9 novembre 2026 au dimanche 15 novembre 2026'
    assert 'Bonjour Alice Martin,' in msg.text
    # 06:00 UTC = 07:00 a Paris en novembre
    assert 'lundi 9 novembre 2026 à 07:00 - 15:00 : Matin, Urgences / Box A' in msg.text
    assert '<li>' in msg.html


def test_html_is_escaped():
    ev = parse_event(event(recipients=[{'email': 'x@t.fr', 'name': '<script>', 'shifts': []}]))
    assert '<script>' not in render(ev, ev.recipients[0]).html


def test_absence_email():
    ev = parse_event(event('absence.created', recipients=[{'email': 'a@t.fr', 'name': 'Alice'}],
                           absence_type='Maladie', start_date='2026-11-10', end_date='2026-11-12'))
    msg = render(ev, ev.recipients[0])
    assert msg.subject == 'Confirmation de votre absence'
    assert 'Maladie' in msg.text and 'mardi 10 novembre 2026' in msg.text


def test_weekly_report_email():
    ev = parse_event(event('report.weekly', recipients=[{'email': 'chef@t.fr', 'name': 'Chef', 'service': 'Urgences'}],
                           total_shifts=5, total_assignments=4, coverage_percent=80, understaffed_total=1,
                           understaffed=[{'start': '2026-11-17T06:00:00Z', 'shift_type': 'Matin',
                                          'service': 'Urgences', 'care_unit': 'Box A',
                                          'assigned': 0, 'min_staff': 1}],
                           overloaded=[{'name': 'Alice Martin', 'hours': 36, 'max_hours': 40}]))
    msg = render(ev, ev.recipients[0])
    assert msg.subject == 'Rapport hebdomadaire — semaine du lundi 9 novembre 2026'
    assert 'Couverture des effectifs minimum : 80 %' in msg.text
    assert 'mardi 17 novembre 2026 à 07:00 : Matin, Urgences / Box A — 0/1 soignant(s)' in msg.text
    assert 'Alice Martin (36 h / 40 h)' in msg.text


def test_sender_configuration():
    assert build_sender({}).mode == 'simulated'
    assert build_sender({'EMAIL_MODE': 'mailpit'}).mode == 'mailpit'
    with pytest.raises(ConfigError):
        build_sender({'EMAIL_MODE': 'acs'})
    with pytest.raises(ConfigError):
        build_sender({'EMAIL_MODE': 'pigeon'})
