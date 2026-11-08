"""Constructeurs de donnees de test au format JSON du contrat d'API."""

from datetime import date, datetime, timedelta, timezone

MONDAY = date(2026, 11, 9)


def shift_type(night=False, hours=8):
    return {
        'duration_hours': hours,
        'requires_rest_after': night,
        'rest_duration_hours': 11,
        'is_night_shift': night,
    }


def shift(id, day=0, hour=7, hours=8, night=False, max_staff=1,
          care_unit_id=1, service_id=1, certs=()):
    start = datetime(MONDAY.year, MONDAY.month, MONDAY.day, hour, tzinfo=timezone.utc) \
        + timedelta(days=day)
    return {
        'id': id,
        'care_unit_id': care_unit_id,
        'service_id': service_id,
        'start_datetime': start.isoformat(),
        'end_datetime': (start + timedelta(hours=hours)).isoformat(),
        'max_staff': max_staff,
        'shift_type': shift_type(night, hours),
        'required_certification_ids': list(certs),
    }


def staff(id, night_ok=True, max_hours=48, contract=True, **extra):
    data = {
        'id': id,
        'contract': {
            'start_date': '2026-01-01',
            'end_date': None,
            'max_hours_per_week': max_hours,
            'night_shift_allowed': night_ok,
            'max_consecutive_nights': 3,
        } if contract else None,
        'known_service_ids': [1],
    }
    data.update(extra)
    return data


def request(shifts, staff_list, existing=(), seed=1):
    return {
        'week_start': MONDAY.isoformat(),
        'week_end': (MONDAY + timedelta(days=6)).isoformat(),
        'shifts': shifts,
        'staff': staff_list,
        'existing_assignments': list(existing),
        'seed': seed,
    }
