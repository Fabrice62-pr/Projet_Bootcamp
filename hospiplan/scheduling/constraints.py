"""
constraints.py
Validation des 8 contraintes dures avant toute affectation (ShiftAssignment).
Chaque fonction leve une ValidationError avec un message clair si violee.
validate_assignment() les appelle toutes dans l'ordre.
"""

from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db.models import Q


def validate_assignment(staff, shift, exclude_assignment_id=None):
    """
    Point d'entree unique : valide toutes les contraintes dures.
    exclude_assignment_id : pk de l'affectation a ignorer lors d'une mise a jour.
    """
    check_no_overlap(staff, shift, exclude_assignment_id)
    check_certifications(staff, shift)
    check_rest_after_night(staff, shift, exclude_assignment_id)
    check_max_staff(shift)
    check_contract_allows_shift(staff, shift)
    check_no_absence(staff, shift)
    check_weekly_hours(staff, shift, exclude_assignment_id)
    check_hard_preferences(staff, shift)


# ── Contrainte 1 : pas de chevauchement de gardes ──────────────────────────

def check_no_overlap(staff, shift, exclude_assignment_id=None):
    from .models import ShiftAssignment

    qs = ShiftAssignment.objects.filter(
        staff=staff,
        shift__start_datetime__lt=shift.end_datetime,
        shift__end_datetime__gt=shift.start_datetime,
    ).exclude(shift=shift)

    if exclude_assignment_id:
        qs = qs.exclude(pk=exclude_assignment_id)

    conflict = qs.select_related("shift__shift_type").first()
    if conflict:
        s = conflict.shift
        raise ValidationError({
            "constraint": "no_overlap",
            "message": (
                f"{staff.first_name} {staff.last_name} est deja affecte(e) a "
                f"'{s.shift_type.name}' ({s.start_datetime:%d/%m/%Y %H:%M}"
                f" -> {s.end_datetime:%H:%M}), chevauchement avec le creneau demande."
            ),
            "conflicting_shift_id": conflict.shift_id,
        })


# ── Contrainte 2 : certifications requises valides a la date de la garde ───

def check_certifications(staff, shift):
    from staff.models import StaffCertification
    from .models import ShiftRequiredCertification

    required = ShiftRequiredCertification.objects.filter(
        shift=shift
    ).select_related("certification")

    for req in required:
        ok = StaffCertification.objects.filter(
            staff=staff,
            certification=req.certification,
            obtained_date__lte=shift.start_datetime.date(),
            expiration_date__gte=shift.start_datetime.date(),
        ).exists()
        if not ok:
            raise ValidationError({
                "constraint": "missing_certification",
                "message": (
                    f"{staff.first_name} {staff.last_name} ne possede pas la "
                    f"certification '{req.certification.name}' ou elle est expiree "
                    f"le {shift.start_datetime:%d/%m/%Y}."
                ),
                "required_certification": req.certification.name,
            })


# ── Contrainte 3 : repos reglementaire apres une garde avec repos requis ───

def check_rest_after_night(staff, shift, exclude_assignment_id=None):
    from .models import ShiftAssignment

    qs = ShiftAssignment.objects.filter(
        staff=staff,
        shift__shift_type__requires_rest_after=True,
        shift__end_datetime__lte=shift.start_datetime,
    ).exclude(shift=shift)

    if exclude_assignment_id:
        qs = qs.exclude(pk=exclude_assignment_id)

    last = qs.order_by("-shift__end_datetime").select_related("shift__shift_type").first()
    if last:
        rest_required = timedelta(hours=last.shift.shift_type.rest_duration_hours)
        gap = shift.start_datetime - last.shift.end_datetime
        if gap < rest_required:
            needed_h = last.shift.shift_type.rest_duration_hours
            actual_h = round(gap.total_seconds() / 3600, 1)
            raise ValidationError({
                "constraint": "insufficient_rest",
                "message": (
                    f"{staff.first_name} {staff.last_name} doit respecter {needed_h}h "
                    f"de repos apres '{last.shift.shift_type.name}' "
                    f"(fin le {last.shift.end_datetime:%d/%m/%Y a %H:%M}). "
                    f"Repos disponible : {actual_h}h seulement."
                ),
                "required_rest_hours": needed_h,
                "actual_rest_hours": actual_h,
            })


# ── Contrainte 4 : seuil max de soignants par creneau ──────────────────────

def check_max_staff(shift):
    """Refuse l'affectation si le creneau est deja complet."""
    from .models import ShiftAssignment

    count = ShiftAssignment.objects.filter(shift=shift).count()
    if count >= shift.max_staff:
        raise ValidationError({
            "constraint": "shift_full",
            "message": (
                f"Le creneau '{shift.shift_type.name}' du "
                f"{shift.start_datetime:%d/%m/%Y %H:%M} est complet "
                f"({count}/{shift.max_staff} soignants)."
            ),
            "current_staff": count,
            "max_staff": shift.max_staff,
        })


def check_min_staff_on_delete(shift):
    """
    A appeler avant suppression d'une affectation.
    Verifie que le service ne passe pas sous le seuil de securite.
    """
    from .models import ShiftAssignment

    count = ShiftAssignment.objects.filter(shift=shift).count()
    threshold = shift.care_unit.service.min_staff_threshold
    if count - 1 < threshold:
        raise ValidationError({
            "constraint": "below_min_threshold",
            "message": (
                f"Suppression refusee : le service '{shift.care_unit.service.name}' "
                f"passerait a {count - 1} soignant(s), "
                f"sous le seuil de securite de {threshold}."
            ),
            "current_staff": count,
            "min_threshold": threshold,
        })


# ── Contrainte 5 : le contrat autorise ce type de garde ────────────────────

def check_contract_allows_shift(staff, shift):
    from staff.models import Contract

    today = shift.start_datetime.date()
    contract = Contract.objects.filter(
        staff=staff,
        start_date__lte=today,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).select_related("contract_type").first()

    if not contract:
        raise ValidationError({
            "constraint": "no_active_contract",
            "message": (
                f"{staff.first_name} {staff.last_name} n'a aucun contrat actif "
                f"le {today:%d/%m/%Y}."
            ),
        })

    if shift.shift_type.is_night_shift and not contract.contract_type.night_shift_allowed:
        raise ValidationError({
            "constraint": "night_shift_not_allowed",
            "message": (
                f"Le contrat '{contract.contract_type.name}' de "
                f"{staff.first_name} {staff.last_name} "
                f"n'autorise pas les gardes de nuit."
            ),
            "contract_type": contract.contract_type.name,
        })


# ── Contrainte 6 : soignant en absence declaree ────────────────────────────

def check_no_absence(staff, shift):
    from absences.models import Absence

    shift_date = shift.start_datetime.date()
    absence = Absence.objects.filter(
        staff=staff,
        start_date__lte=shift_date,
        expected_end_date__gte=shift_date,
    ).select_related("absence_type").first()

    # Si l'absence a une fin reelle avant la garde, elle est terminee
    if absence and absence.actual_end_date and absence.actual_end_date < shift_date:
        absence = None

    if absence:
        raise ValidationError({
            "constraint": "staff_absent",
            "message": (
                f"{staff.first_name} {staff.last_name} est en absence "
                f"'{absence.absence_type.name}' "
                f"du {absence.start_date:%d/%m/%Y} "
                f"au {absence.expected_end_date:%d/%m/%Y}. "
                f"Affectation impossible."
            ),
            "absence_type": absence.absence_type.name,
            "absence_start": str(absence.start_date),
            "absence_end": str(absence.expected_end_date),
        })


# ── Contrainte 7 : quota d'heures hebdomadaires contractuelles ─────────────

def check_weekly_hours(staff, shift, exclude_assignment_id=None):
    from staff.models import Contract
    from .models import ShiftAssignment

    shift_date = shift.start_datetime.date()
    week_start = shift_date - timedelta(days=shift_date.weekday())
    week_end = week_start + timedelta(days=6)

    contract = Contract.objects.filter(
        staff=staff,
        start_date__lte=shift_date,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=shift_date)
    ).select_related("contract_type").first()

    if not contract:
        return  # contrainte 5 gere deja l'absence de contrat

    qs = ShiftAssignment.objects.filter(
        staff=staff,
        shift__start_datetime__date__range=[week_start, week_end],
    ).exclude(shift=shift).select_related("shift__shift_type")

    if exclude_assignment_id:
        qs = qs.exclude(pk=exclude_assignment_id)

    already = sum(a.shift.shift_type.duration_hours for a in qs)
    new_total = already + shift.shift_type.duration_hours
    max_h = contract.contract_type.max_hours_per_week

    if new_total > max_h:
        raise ValidationError({
            "constraint": "weekly_hours_exceeded",
            "message": (
                f"Affectation refusee : {staff.first_name} {staff.last_name} "
                f"atteindrait {new_total}h cette semaine "
                f"(quota contractuel : {max_h}h)."
            ),
            "already_hours": already,
            "shift_hours": shift.shift_type.duration_hours,
            "total_hours": new_total,
            "max_hours": max_h,
        })


# ── Contrainte 8 : preferences imperatives (is_hard_constraint=True) ───────

FRENCH_DAYS = {
    "lundi": 0, "mardi": 1, "mercredi": 2,
    "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6,
}


def check_hard_preferences(staff, shift):
    from preferences.models import Preference

    shift_date = shift.start_datetime.date()
    hard_prefs = Preference.objects.filter(
        staff=staff,
        is_hard_constraint=True,
        start_date__lte=shift_date,
        end_date__gte=shift_date,
    )

    for pref in hard_prefs:
        desc_lower = pref.description.lower()
        if pref.type == "indisponibilite":
            shift_weekday = shift.start_datetime.weekday()
            for fr_day, wd in FRENCH_DAYS.items():
                if fr_day in desc_lower and shift_weekday == wd:
                    raise ValidationError({
                        "constraint": "hard_preference_violated",
                        "message": (
                            f"Contrainte imperative violee pour "
                            f"{staff.first_name} {staff.last_name} : "
                            f"'{pref.description}'"
                        ),
                        "preference_id": pref.pk,
                        "preference_description": pref.description,
                    })
