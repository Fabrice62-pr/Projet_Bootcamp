"""Le moteur ne doit jamais proposer une affectation qui viole une contrainte dure."""

from app.schemas import SolveRequest
from app.solver import solve

from .factories import request, shift, staff


def run(shifts, staff_list, existing=(), seed=1):
    assignments, unfilled, score, detail = solve(
        SolveRequest.model_validate(request(shifts, staff_list, existing, seed))
    )
    return {(a.staff_id, a.shift_id) for a in assignments}, unfilled


def test_night_shift_requires_contract_allowing_nights():
    pairs, unfilled = run([shift(1, hour=21, night=True)], [staff(10, night_ok=False)])
    assert pairs == set() and unfilled == [1]


def test_staff_without_contract_is_never_assigned():
    pairs, unfilled = run([shift(1)], [staff(10, contract=False)])
    assert pairs == set() and unfilled == [1]


def test_absent_staff_is_skipped():
    absent = staff(10, absences=[{'start_date': '2026-11-09', 'end_date': '2026-11-10'}])
    pairs, _ = run([shift(1)], [absent, staff(11)])
    assert pairs == {(11, 1)}


def test_missing_certification_blocks_assignment():
    certified = staff(11, certifications=[{
        'certification_id': 5, 'obtained_date': '2025-01-01', 'expiration_date': '2027-01-01',
    }])
    pairs, _ = run([shift(1, certs=[5])], [staff(10), certified])
    assert pairs == {(11, 1)}


def test_no_overlap_and_max_staff():
    # Deux creneaux simultanes, un seul soignant : il ne peut en prendre qu'un.
    pairs, unfilled = run([shift(1), shift(2)], [staff(10)])
    assert len(pairs) == 1 and len(unfilled) == 1


def test_rest_after_night_is_respected():
    # Nuit lundi 21h -> mardi 5h, puis creneau mardi 7h : repos de 11 h non respecte.
    pairs, unfilled = run(
        [shift(1, hour=21, night=True), shift(2, day=1, hour=7)],
        [staff(10)],
    )
    assert len(pairs) == 1 and len(unfilled) == 1


def test_weekly_hours_cap():
    # 3 creneaux de 8 h sur des jours differents, plafond 16 h.
    pairs, unfilled = run([shift(i, day=i) for i in range(3)], [staff(10, max_hours=16)])
    assert len(pairs) == 2 and len(unfilled) == 1


def test_hard_unavailability_preference():
    prefers_no_monday = staff(10, preferences=[{
        'type': 'indisponibilite', 'description': 'Pas le lundi',
        'is_hard_constraint': True, 'start_date': '2026-11-01', 'end_date': '2026-11-30',
    }])
    pairs, _ = run([shift(1, day=0)], [prefers_no_monday, staff(11)])
    assert pairs == {(11, 1)}


def test_same_seed_gives_same_planning():
    shifts = [shift(i, day=i % 7, hour=7 + 8 * (i // 7)) for i in range(14)]
    team = [staff(10 + i) for i in range(5)]
    assert run(shifts, team, seed=42) == run(shifts, team, seed=42)
