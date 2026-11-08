import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reporter.pdf import render_planning_pdf  # noqa: E402
from reporter.stats import build_report  # noqa: E402
from reporter.weekly import build_weekly_event  # noqa: E402


def shift(id, start, end, staff_ids, min_staff=1, night=False, hours=8):
    return {'id': id, 'start': start, 'end': end, 'hours': hours, 'is_night': night,
            'shift_type': 'Nuit' if night else 'Matin', 'service': 'Urgences', 'care_unit': 'Box A',
            'min_staff': min_staff, 'max_staff': 2, 'staff_ids': staff_ids}


DATA = {
    'week_start': '2026-11-16', 'week_end': '2026-11-22',
    'shifts': [
        shift(1, '2026-11-16T06:00:00Z', '2026-11-16T14:00:00Z', [1]),
        shift(2, '2026-11-17T06:00:00Z', '2026-11-17T14:00:00Z', [], min_staff=2),   # non pourvu
        shift(3, '2026-11-21T20:00:00Z', '2026-11-22T06:00:00Z', [1, 2], night=True, hours=10),  # samedi
    ],
    'staff': [
        {'id': 1, 'name': 'Alice Martin', 'email': 'a@t.fr', 'max_hours': 20},
        {'id': 2, 'name': 'Bob Durand', 'email': 'b@t.fr', 'max_hours': 40},
        {'id': 3, 'name': 'Chloé Bernard', 'email': 'c@t.fr', 'max_hours': None},
    ],
    'managers': [{'email': 'chef@t.fr', 'name': 'Chef Urgences', 'service': 'Urgences'}],
}


def test_indicators():
    r = build_report(DATA)
    assert len(r.shifts) == 3 and r.total_assignments == 3
    # minimum requis : 1 + 2 + 1 = 4 ; pourvus : 1 + 0 + 1 = 2
    assert r.coverage == 0.5
    assert [s.shift_type for s in r.understaffed] == ['Matin']
    alice = next(p for p in r.staff if p.name == 'Alice Martin')
    assert (alice.shifts, alice.hours, alice.nights, alice.weekends) == (2, 18, 1, 1)
    assert [p.name for p in r.overloaded] == ['Alice Martin']   # 18 h / 20 h = 90 %
    assert r.shifts[0].start.hour == 7                         # 06:00 UTC -> 07:00 Paris


def test_empty_week_has_full_coverage():
    r = build_report({'week_start': '2026-11-16', 'week_end': '2026-11-22', 'shifts': [], 'staff': []})
    assert r.coverage == 1.0 and r.understaffed == []


def test_pdf_is_generated_with_accents():
    pdf = render_planning_pdf(build_report(DATA))
    assert pdf.startswith(b'%PDF') and len(pdf) > 2000


def test_pdf_for_empty_week():
    pdf = render_planning_pdf(build_report({'week_start': '2026-11-16', 'week_end': '2026-11-22'}))
    assert pdf.startswith(b'%PDF')


def test_weekly_event_targets_managers():
    event = build_weekly_event(build_report(DATA))
    assert event['type'] == 'report.weekly' and event['version'] == 1
    data = event['data']
    assert data['coverage_percent'] == 50 and data['understaffed_total'] == 1
    assert data['recipients'] == [{'email': 'chef@t.fr', 'name': 'Chef Urgences', 'service': 'Urgences'}]
    assert data['overloaded'] == [{'name': 'Alice Martin', 'hours': 18, 'max_hours': 20}]
