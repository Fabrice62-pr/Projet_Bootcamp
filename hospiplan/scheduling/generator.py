"""
generator.py
Generation automatique d'un planning hebdomadaire admissible.

Le calcul est delegue au microservice "Moteur de planning"
(microservices/engine). Ce module ne fait que :
  1. lire en base tout ce dont le moteur a besoin ;
  2. l'envoyer au moteur (engine_client) ;
  3. enregistrer le brouillon renvoye.

La publication du brouillon revalide chaque affectation (validate_assignment) :
aucune affectation illegale ne peut etre enregistree, meme si le moteur se
trompait.
"""

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q

from . import engine_client
from .engine_client import EngineError  # noqa: F401  (re-exporte pour les vues)


def generate_planning(week_start: date, seed: int | None = None):
    """
    Genere un brouillon de planning pour la semaine commencant le lundi week_start.
    Retourne (PlanningSession, list[shift_id non pourvus]).
    Leve EngineError si le moteur ne repond pas.
    """
    from .models import DraftAssignment, PlanningSession

    week_end = week_start + timedelta(days=6)
    payload = build_payload(week_start, week_end)
    payload['seed'] = seed

    result = engine_client.solve(payload)

    # On ne fait pas confiance aveuglement a la reponse : seuls les couples
    # (soignant, creneau) envoyes sont acceptes, et chacun une seule fois.
    staff_ids = {s['id'] for s in payload['staff']}
    shift_ids = {s['id'] for s in payload['shifts']}
    seen = set()
    drafts = []
    for a in result.get('assignments', []):
        pair = (a.get('staff_id'), a.get('shift_id'))
        if pair[0] in staff_ids and pair[1] in shift_ids and pair not in seen:
            seen.add(pair)
            drafts.append((pair, float(a.get('penalty', 0.0))))

    unfilled = [i for i in result.get('unfilled_shift_ids', []) if i in shift_ids]

    with transaction.atomic():
        session = PlanningSession.objects.create(
            week_start=week_start,
            week_end=week_end,
            total_score=float(result.get('total_score', 0.0)),
            score_detail=result.get('score_detail', {}),
            unpaved_shifts_count=len(unfilled),
            status='draft',
        )
        DraftAssignment.objects.bulk_create([
            DraftAssignment(session=session, staff_id=staff_id, shift_id=shift_id, penalty=penalty)
            for (staff_id, shift_id), penalty in drafts
        ])

    return session, unfilled


# -- Construction de la requete envoyee au moteur ------------------------------

def _shift_payload(shift, required_cert_ids=()):
    st = shift.shift_type
    return {
        'id': shift.id,
        'care_unit_id': shift.care_unit_id,
        'service_id': shift.care_unit.service_id,
        'start_datetime': shift.start_datetime,
        'end_datetime': shift.end_datetime,
        'max_staff': shift.max_staff,
        'shift_type': {
            'duration_hours': st.duration_hours,
            'requires_rest_after': st.requires_rest_after,
            'rest_duration_hours': st.rest_duration_hours,
            'is_night_shift': st.is_night_shift,
        },
        'required_certification_ids': list(required_cert_ids),
    }


def build_payload(week_start, week_end):
    from absences.models import Absence
    from preferences.models import Preference
    from staff.models import Contract, Staff, StaffCertification

    from .models import Shift, ShiftAssignment, ShiftRequiredCertification

    quarter_start = week_start - timedelta(weeks=13)
    load_from = week_start - timedelta(days=14)

    shifts = list(Shift.objects.filter(
        start_datetime__date__range=[week_start, week_end]
    ).select_related('shift_type', 'care_unit'))

    staff_list = list(Staff.objects.filter(is_active=True))
    staff_ids = [s.id for s in staff_list]

    # Affectations recentes (2 semaines avant + semaine cible) pour les contraintes
    existing = list(ShiftAssignment.objects.filter(
        staff_id__in=staff_ids,
        shift__end_datetime__date__gte=load_from,
    ).select_related('shift__shift_type', 'shift__care_unit'))

    # Contrat actif (le plus recent couvrant la semaine)
    contracts = {}
    for c in Contract.objects.filter(
        staff_id__in=staff_ids,
        start_date__lte=week_end,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=week_start)
    ).select_related('contract_type').order_by('staff_id', '-start_date'):
        if c.staff_id not in contracts:
            contracts[c.staff_id] = {
                'start_date': c.start_date,
                'end_date': c.end_date,
                'max_hours_per_week': c.contract_type.max_hours_per_week,
                'night_shift_allowed': c.contract_type.night_shift_allowed,
                'max_consecutive_nights': c.contract_type.max_consecutive_nights,
            }

    staff_certs = {}
    for sc in StaffCertification.objects.filter(staff_id__in=staff_ids):
        staff_certs.setdefault(sc.staff_id, []).append({
            'certification_id': sc.certification_id,
            'obtained_date': sc.obtained_date,
            'expiration_date': sc.expiration_date,
        })

    # Absences chevauchant la semaine ; fin reelle si connue, sinon prevue.
    absences = {}
    for ab in Absence.objects.filter(
        staff_id__in=staff_ids,
        start_date__lte=week_end,
        expected_end_date__gte=week_start,
    ):
        absences.setdefault(ab.staff_id, []).append({
            'start_date': ab.start_date,
            'end_date': ab.actual_end_date or ab.expected_end_date,
        })

    preferences = {}
    for pref in Preference.objects.filter(
        staff_id__in=staff_ids,
        start_date__lte=week_end,
        end_date__gte=week_start,
    ):
        preferences.setdefault(pref.staff_id, []).append({
            'type': pref.type,
            'description': pref.description,
            'is_hard_constraint': pref.is_hard_constraint,
            'start_date': pref.start_date,
            'end_date': pref.end_date,
        })

    shift_certs = {}
    if shifts:
        for src in ShiftRequiredCertification.objects.filter(
            shift_id__in=[s.id for s in shifts]
        ):
            shift_certs.setdefault(src.shift_id, []).append(src.certification_id)

    # Services deja travailles (contrainte molle "service non familier")
    service_history = {}
    for row in ShiftAssignment.objects.filter(
        staff_id__in=staff_ids
    ).values('staff_id', 'shift__care_unit__service_id'):
        sid = row['shift__care_unit__service_id']
        if sid:
            service_history.setdefault(row['staff_id'], set()).add(sid)

    # Gardes de week-end sur le trimestre (equite)
    weekend_counts = {}
    for staff_id, start in ShiftAssignment.objects.filter(
        staff_id__in=staff_ids,
        shift__start_datetime__date__gte=quarter_start,
    ).values_list('staff_id', 'shift__start_datetime'):
        if start.weekday() in (5, 6):
            weekend_counts[staff_id] = weekend_counts.get(staff_id, 0) + 1

    return {
        'week_start': week_start,
        'week_end': week_end,
        'shifts': [_shift_payload(s, shift_certs.get(s.id, ())) for s in shifts],
        'staff': [
            {
                'id': s.id,
                'contract': contracts.get(s.id),
                'certifications': staff_certs.get(s.id, []),
                'absences': absences.get(s.id, []),
                'preferences': preferences.get(s.id, []),
                'known_service_ids': sorted(service_history.get(s.id, ())),
                'weekend_count': weekend_counts.get(s.id, 0),
            }
            for s in staff_list
        ],
        'existing_assignments': [
            {'staff_id': a.staff_id, 'shift': _shift_payload(a.shift)}
            for a in existing
        ],
    }
