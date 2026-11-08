"""Indicateurs d'une semaine de planning, calcules a partir des donnees du Core."""

from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo('Europe/Paris')
OVERLOAD_RATIO = 0.9  # au-dela de 90 % du plafond hebdomadaire : vigilance


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return dt.astimezone(PARIS) if dt.tzinfo else dt.replace(tzinfo=PARIS)


@dataclass
class ShiftRow:
    start: datetime
    end: datetime
    shift_type: str
    service: str
    care_unit: str
    hours: int
    is_night: bool
    min_staff: int
    max_staff: int
    staff_names: list = field(default_factory=list)

    @property
    def assigned(self):
        return len(self.staff_names)

    @property
    def understaffed(self):
        return self.assigned < self.min_staff


@dataclass
class StaffRow:
    name: str
    email: str
    max_hours: int | None
    shifts: int = 0
    hours: int = 0
    nights: int = 0
    weekends: int = 0

    @property
    def load(self):
        return self.hours / self.max_hours if self.max_hours else None

    @property
    def overloaded(self):
        return self.load is not None and self.load >= OVERLOAD_RATIO


@dataclass
class Report:
    week_start: date
    week_end: date
    shifts: list
    staff: list
    managers: list

    @property
    def total_assignments(self):
        return sum(s.assigned for s in self.shifts)

    @property
    def coverage(self):
        """Part des effectifs minimum effectivement pourvus (1.0 = 100 %)."""
        required = sum(s.min_staff for s in self.shifts)
        if not required:
            return 1.0
        return sum(min(s.assigned, s.min_staff) for s in self.shifts) / required

    @property
    def understaffed(self):
        return [s for s in self.shifts if s.understaffed]

    @property
    def overloaded(self):
        return [s for s in self.staff if s.overloaded]


def build_report(data: dict) -> Report:
    staff_by_id = {
        s['id']: StaffRow(name=s['name'], email=s.get('email', ''), max_hours=s.get('max_hours'))
        for s in data.get('staff', [])
    }

    shifts = []
    for raw in data.get('shifts', []):
        row = ShiftRow(
            start=parse_dt(raw['start']), end=parse_dt(raw['end']),
            shift_type=raw.get('shift_type', ''), service=raw.get('service', ''),
            care_unit=raw.get('care_unit', ''), hours=int(raw.get('hours', 0)),
            is_night=bool(raw.get('is_night')), min_staff=int(raw.get('min_staff', 0)),
            max_staff=int(raw.get('max_staff', 0)),
        )
        for staff_id in raw.get('staff_ids', []):
            person = staff_by_id.get(staff_id)
            if person is None:
                continue
            row.staff_names.append(person.name)
            person.shifts += 1
            person.hours += row.hours
            person.nights += row.is_night
            person.weekends += row.start.weekday() >= 5
        shifts.append(row)

    shifts.sort(key=lambda s: (s.start, s.service, s.care_unit))
    staff = sorted(staff_by_id.values(), key=lambda s: (-s.hours, s.name))

    return Report(
        week_start=date.fromisoformat(str(data['week_start'])[:10]),
        week_end=date.fromisoformat(str(data['week_end'])[:10]),
        shifts=shifts,
        staff=staff,
        managers=list(data.get('managers', [])),
    )
