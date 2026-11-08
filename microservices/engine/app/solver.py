"""
Generation automatique d'un planning hebdomadaire admissible.

Phase 1 : heuristique gloutonne - construit un planning legal en affectant
          les creneaux du plus contraint au moins contraint.
Phase 2 : recherche locale (swap) - ameliore le score des contraintes molles
          sans jamais violer une contrainte dure.

Algorithme repris a l'identique de l'ancien scheduling/generator.py du Core,
sans aucune dependance a Django : toutes les donnees arrivent dans la requete.
"""

import random
import statistics
from datetime import timedelta

from .schemas import Assignment, Shift, SolveRequest, Staff

# -- Poids des contraintes molles ----------------------------------------------
WEIGHTS = {
    'consecutive_nights': 10,
    'preference':          8,
    'workload':            6,
    'service_change':      4,
    'weekend_imbalance':   5,
    'unfamiliar_service':  3,
    'care_continuity':     2,
}

MAX_LOCAL_SEARCH = 300

FRENCH_DAYS = {
    'lundi': 0, 'mardi': 1, 'mercredi': 2,
    'jeudi': 3, 'vendredi': 4, 'samedi': 5, 'dimanche': 6,
}


# -- Etat du brouillon (en memoire) --------------------------------------------

class DraftState:
    def __init__(self):
        self.entries = []  # list of {'staff': Staff, 'shift': Shift}

    def add(self, staff, shift):
        self.entries.append({'staff': staff, 'shift': shift})

    def remove(self, staff, shift):
        for i, e in enumerate(self.entries):
            if e['staff'].id == staff.id and e['shift'].id == shift.id:
                self.entries.pop(i)
                return

    def staff_shifts(self, staff_id):
        return [e['shift'] for e in self.entries if e['staff'].id == staff_id]

    def shift_count(self, shift_id):
        return sum(1 for e in self.entries if e['shift'].id == shift_id)

    def staff_week_shifts(self, staff_id, week_start, week_end):
        return [
            e['shift'] for e in self.entries
            if e['staff'].id == staff_id
            and week_start <= e['shift'].start_datetime.date() <= week_end
        ]


# -- Point d'entree ------------------------------------------------------------

def solve(request: SolveRequest):
    """
    Calcule un brouillon de planning.
    Retourne (affectations, ids des creneaux non pourvus, score total, detail).
    """
    ctx = _build_context(request)
    rng = random.Random(request.seed)

    shifts_sorted = _sort_by_difficulty(ctx['shifts'], ctx)

    state = DraftState()
    unfilled = []

    # Phase 1 : construction gloutonne
    for shift in shifts_sorted:
        eligible = [s for s in ctx['staff_list']
                    if _check_hard_constraints(s, shift, state, ctx)]
        if not eligible:
            unfilled.append(shift.id)
            continue
        scored = [(s, _compute_penalty(s, shift, state, ctx)) for s in eligible]
        best = min(scored, key=lambda x: x[1])[0]
        state.add(best, shift)

    # Phase 2 : recherche locale
    _local_search(state, ctx, rng)

    total_score, score_detail = _compute_total_score(state, ctx)

    assignments = [
        Assignment(
            staff_id=e['staff'].id,
            shift_id=e['shift'].id,
            penalty=round(_compute_penalty(e['staff'], e['shift'], state, ctx), 2),
        )
        for e in state.entries
    ]
    return assignments, unfilled, total_score, score_detail


# -- Contexte : index en memoire construits a partir de la requete -------------

def _build_context(request: SolveRequest):
    staff_list = request.staff
    existing = request.existing_assignments

    assignments_by_staff = {}
    assignments_by_shift = {}
    for a in existing:
        assignments_by_staff.setdefault(a.staff_id, []).append(a)
        assignments_by_shift.setdefault(a.shift.id, []).append(a)

    weekend_counts = {s.id: s.weekend_count for s in staff_list if s.weekend_count}
    avg_weekend = (sum(weekend_counts.values()) / max(len(staff_list), 1)
                   if weekend_counts else 0.0)

    return {
        'week_start': request.week_start,
        'week_end': request.week_end,
        'shifts': request.shifts,
        'staff_list': staff_list,
        'existing': existing,
        'assignments_by_staff': assignments_by_staff,
        'assignments_by_shift': assignments_by_shift,
        'contracts': {s.id: s.contract for s in staff_list if s.contract},
        'staff_certs': {s.id: s.certifications for s in staff_list},
        'absences': {s.id: s.absences for s in staff_list},
        'preferences': {s.id: s.preferences for s in staff_list},
        'service_history': {s.id: set(s.known_service_ids) for s in staff_list},
        'weekend_counts': weekend_counts,
        'avg_weekend': avg_weekend,
    }


# -- Tri par difficulte --------------------------------------------------------

def _sort_by_difficulty(shifts, ctx):
    """Nuits en premier, puis par heure de debut (les plus tot = plus contraints)."""
    return sorted(shifts, key=lambda s: (
        not s.shift_type.is_night_shift,
        s.start_datetime,
    ))


# -- Verification des 8 contraintes dures --------------------------------------

def _check_hard_constraints(staff: Staff, shift: Shift, state, ctx):
    return (
        _hc_no_overlap(staff, shift, state, ctx) and
        _hc_certifications(staff, shift, ctx) and
        _hc_rest_after_night(staff, shift, state, ctx) and
        _hc_max_staff(shift, state, ctx) and
        _hc_contract_allows(staff, shift, ctx) and
        _hc_no_absence(staff, shift, ctx) and
        _hc_weekly_hours(staff, shift, state, ctx) and
        _hc_hard_preferences(staff, shift, ctx)
    )


def _hc_no_overlap(staff, shift, state, ctx):
    all_staff_shifts = (
        [a.shift for a in ctx['assignments_by_staff'].get(staff.id, [])] +
        state.staff_shifts(staff.id)
    )
    for s in all_staff_shifts:
        if s.id != shift.id:
            if s.start_datetime < shift.end_datetime and s.end_datetime > shift.start_datetime:
                return False
    return True


def _hc_certifications(staff, shift, ctx):
    shift_date = shift.start_datetime.date()
    for cert_id in shift.required_certification_ids:
        has = any(
            sc.certification_id == cert_id
            and sc.obtained_date <= shift_date
            and sc.expiration_date >= shift_date
            for sc in ctx['staff_certs'].get(staff.id, [])
        )
        if not has:
            return False
    return True


def _hc_rest_after_night(staff, shift, state, ctx):
    candidates = []
    for a in ctx['assignments_by_staff'].get(staff.id, []):
        if a.shift.shift_type.requires_rest_after and a.shift.end_datetime <= shift.start_datetime:
            candidates.append(a.shift)
    for s in state.staff_shifts(staff.id):
        if s.shift_type.requires_rest_after and s.end_datetime <= shift.start_datetime:
            candidates.append(s)
    if not candidates:
        return True
    last = max(candidates, key=lambda s: s.end_datetime)
    gap = shift.start_datetime - last.end_datetime
    return gap >= timedelta(hours=last.shift_type.rest_duration_hours)


def _hc_max_staff(shift, state, ctx):
    existing_count = len(ctx['assignments_by_shift'].get(shift.id, []))
    return (existing_count + state.shift_count(shift.id)) < shift.max_staff


def _hc_contract_allows(staff, shift, ctx):
    contract = ctx['contracts'].get(staff.id)
    if not contract:
        return False
    shift_date = shift.start_datetime.date()
    if contract.start_date > shift_date:
        return False
    if contract.end_date and contract.end_date < shift_date:
        return False
    if shift.shift_type.is_night_shift and not contract.night_shift_allowed:
        return False
    return True


def _hc_no_absence(staff, shift, ctx):
    shift_date = shift.start_datetime.date()
    for ab in ctx['absences'].get(staff.id, []):
        if ab.start_date <= shift_date <= ab.end_date:
            return False
    return True


def _hc_weekly_hours(staff, shift, state, ctx):
    contract = ctx['contracts'].get(staff.id)
    if not contract:
        return True
    shift_date = shift.start_datetime.date()
    wk_start = shift_date - timedelta(days=shift_date.weekday())
    wk_end = wk_start + timedelta(days=6)
    max_h = contract.max_hours_per_week

    existing_h = sum(
        a.shift.shift_type.duration_hours
        for a in ctx['assignments_by_staff'].get(staff.id, [])
        if wk_start <= a.shift.start_datetime.date() <= wk_end
    )
    draft_h = sum(
        s.shift_type.duration_hours
        for s in state.staff_week_shifts(staff.id, wk_start, wk_end)
    )
    return (existing_h + draft_h + shift.shift_type.duration_hours) <= max_h


def _blocked_weekdays(pref):
    """Jours de la semaine cites dans une indisponibilite ("pas le lundi")."""
    if pref.type != 'indisponibilite':
        return ()
    desc = pref.description.lower()
    return [wd for fr_day, wd in FRENCH_DAYS.items() if fr_day in desc]


def _hc_hard_preferences(staff, shift, ctx):
    shift_date = shift.start_datetime.date()
    shift_wd = shift.start_datetime.weekday()
    for pref in ctx['preferences'].get(staff.id, []):
        if not pref.is_hard_constraint:
            continue
        if not (pref.start_date <= shift_date <= pref.end_date):
            continue
        if shift_wd in _blocked_weekdays(pref):
            return False
    return True


# -- Penalite totale (contraintes molles) --------------------------------------

def _compute_penalty(staff, shift, state, ctx):
    return (
        _sc_consecutive_nights(staff, shift, state, ctx) * WEIGHTS['consecutive_nights'] +
        _sc_preference(staff, shift, ctx)                * WEIGHTS['preference'] +
        _sc_workload(staff, state, ctx)                  * WEIGHTS['workload'] +
        _sc_service_change(staff, shift, state, ctx)     * WEIGHTS['service_change'] +
        _sc_weekend_imbalance(staff, shift, ctx)         * WEIGHTS['weekend_imbalance'] +
        _sc_unfamiliar_service(staff, shift, ctx)        * WEIGHTS['unfamiliar_service'] +
        _sc_care_continuity(staff, shift, state, ctx)    * WEIGHTS['care_continuity']
    )


def _sc_consecutive_nights(staff, shift, state, ctx):
    if not shift.shift_type.is_night_shift:
        return 0.0
    contract = ctx['contracts'].get(staff.id)
    max_nights = contract.max_consecutive_nights if contract else 3

    shift_date = shift.start_datetime.date()
    night_dates = set()
    for a in ctx['assignments_by_staff'].get(staff.id, []):
        if a.shift.shift_type.is_night_shift:
            night_dates.add(a.shift.start_datetime.date())
    for s in state.staff_shifts(staff.id):
        if s.shift_type.is_night_shift:
            night_dates.add(s.start_datetime.date())
    night_dates.add(shift_date)

    consecutive = 0
    check = shift_date
    while check in night_dates:
        consecutive += 1
        check -= timedelta(days=1)
    return float(max(0, consecutive - max_nights))


def _sc_preference(staff, shift, ctx):
    shift_date = shift.start_datetime.date()
    shift_wd = shift.start_datetime.weekday()
    penalty = 0.0
    for pref in ctx['preferences'].get(staff.id, []):
        if pref.is_hard_constraint:
            continue
        if not (pref.start_date <= shift_date <= pref.end_date):
            continue
        penalty += sum(1.0 for wd in _blocked_weekdays(pref) if wd == shift_wd)
    return penalty


def _sc_workload(staff, state, ctx):
    """Penalise les soignants deja beaucoup charges cette semaine (brouillon)."""
    week_shifts = state.staff_week_shifts(staff.id, ctx['week_start'], ctx['week_end'])
    return float(len(week_shifts))


def _sc_service_change(staff, shift, state, ctx):
    ws, we = ctx['week_start'], ctx['week_end']
    services = set()
    for a in ctx['assignments_by_staff'].get(staff.id, []):
        if ws <= a.shift.start_datetime.date() <= we:
            services.add(a.shift.service_id)
    for s in state.staff_week_shifts(staff.id, ws, we):
        services.add(s.service_id)
    services.add(shift.service_id)
    return float(max(0, len(services) - 1))


def _sc_weekend_imbalance(staff, shift, ctx):
    if shift.start_datetime.weekday() not in (5, 6):
        return 0.0
    count = ctx['weekend_counts'].get(staff.id, 0)
    return float(max(0.0, count - ctx['avg_weekend']))


def _sc_unfamiliar_service(staff, shift, ctx):
    known = ctx['service_history'].get(staff.id, set())
    return 0.0 if shift.service_id in known else 1.0


def _sc_care_continuity(staff, shift, state, ctx):
    """Penalise si quelqu'un d'autre couvrait cette unite hier."""
    shift_date = shift.start_datetime.date()
    prev_date = shift_date - timedelta(days=1)
    cu_id = shift.care_unit_id

    prev_ids = set()
    for a in ctx['existing']:
        if a.shift.care_unit_id == cu_id and a.shift.start_datetime.date() == prev_date:
            prev_ids.add(a.staff_id)
    for e in state.entries:
        if e['shift'].care_unit_id == cu_id and e['shift'].start_datetime.date() == prev_date:
            prev_ids.add(e['staff'].id)

    if not prev_ids:
        return 0.0
    return 0.0 if staff.id in prev_ids else 1.0


# -- Score global (rapport final) ----------------------------------------------

def _compute_total_score(state, ctx):
    detail = {k: 0.0 for k in WEIGHTS}
    ws, we = ctx['week_start'], ctx['week_end']

    for e in state.entries:
        staff, shift = e['staff'], e['shift']
        detail['consecutive_nights'] += _sc_consecutive_nights(staff, shift, state, ctx) * WEIGHTS['consecutive_nights']
        detail['preference']          += _sc_preference(staff, shift, ctx)                * WEIGHTS['preference']
        detail['service_change']      += _sc_service_change(staff, shift, state, ctx)     * WEIGHTS['service_change']
        detail['weekend_imbalance']   += _sc_weekend_imbalance(staff, shift, ctx)         * WEIGHTS['weekend_imbalance']
        detail['unfamiliar_service']  += _sc_unfamiliar_service(staff, shift, ctx)        * WEIGHTS['unfamiliar_service']
        detail['care_continuity']     += _sc_care_continuity(staff, shift, state, ctx)    * WEIGHTS['care_continuity']

    # Desequilibre de charge : ecart-type du nombre de gardes par soignant
    counts = {}
    for e in state.entries:
        if ws <= e['shift'].start_datetime.date() <= we:
            counts[e['staff'].id] = counts.get(e['staff'].id, 0) + 1
    if len(counts) > 1:
        detail['workload'] = statistics.stdev(counts.values()) * WEIGHTS['workload']

    total = sum(detail.values())
    return round(total, 2), {k: round(v, 2) for k, v in detail.items()}


# -- Recherche locale (swap) ---------------------------------------------------

def _local_search(state, ctx, rng):
    for _ in range(MAX_LOCAL_SEARCH):
        if len(state.entries) < 2:
            break

        e1, e2 = rng.sample(state.entries, 2)
        s1, sh1 = e1['staff'], e1['shift']
        s2, sh2 = e2['staff'], e2['shift']

        if s1.id == s2.id or sh1.id == sh2.id:
            continue

        p_before = (
            _compute_penalty(s1, sh1, state, ctx) +
            _compute_penalty(s2, sh2, state, ctx)
        )

        state.remove(s1, sh1)
        state.remove(s2, sh2)

        feasible = (
            _check_hard_constraints(s1, sh2, state, ctx) and
            _check_hard_constraints(s2, sh1, state, ctx)
        )

        if feasible:
            state.add(s1, sh2)
            state.add(s2, sh1)
            p_after = (
                _compute_penalty(s1, sh2, state, ctx) +
                _compute_penalty(s2, sh1, state, ctx)
            )
            if p_after >= p_before:
                state.remove(s1, sh2)
                state.remove(s2, sh1)
                state.add(s1, sh1)
                state.add(s2, sh2)
        else:
            state.add(s1, sh1)
            state.add(s2, sh2)
