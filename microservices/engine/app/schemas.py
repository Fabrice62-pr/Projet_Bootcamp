"""
Contrat d'echange du moteur de planning.

Le moteur ne connait pas la base de donnees : le Core lui envoie tout ce dont
il a besoin dans une seule requete, et recoit les affectations proposees.
Les identifiants sont ceux du Core ; le moteur les renvoie tels quels.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

# Bornes de securite : une semaine d'hopital reste tres en dessous, mais on
# refuse une requete demesuree avant de lancer un calcul couteux.
MAX_SHIFTS = 2000
MAX_STAFF = 1000
MAX_EXISTING = 20000


class ShiftType(BaseModel):
    duration_hours: int = Field(ge=0)
    requires_rest_after: bool
    rest_duration_hours: int = Field(ge=0)
    is_night_shift: bool


class Shift(BaseModel):
    id: int
    care_unit_id: int
    service_id: int
    start_datetime: datetime
    end_datetime: datetime
    max_staff: int = Field(ge=0)
    shift_type: ShiftType
    required_certification_ids: list[int] = Field(default_factory=list)


class Contract(BaseModel):
    start_date: date
    end_date: date | None = None
    max_hours_per_week: int = Field(ge=0)
    night_shift_allowed: bool
    max_consecutive_nights: int = Field(default=3, ge=0)


class StaffCertification(BaseModel):
    certification_id: int
    obtained_date: date
    expiration_date: date


class Absence(BaseModel):
    start_date: date
    # Fin reelle si connue, sinon fin prevue (calculee par le Core).
    end_date: date


class Preference(BaseModel):
    type: str
    description: str = ''
    is_hard_constraint: bool
    start_date: date
    end_date: date


class Staff(BaseModel):
    id: int
    # Contrat actif sur la semaine ; sans contrat, le soignant n'est pas affectable.
    contract: Contract | None = None
    certifications: list[StaffCertification] = Field(default_factory=list)
    absences: list[Absence] = Field(default_factory=list)
    preferences: list[Preference] = Field(default_factory=list)
    # Services deja travailles (contrainte molle "service non familier").
    known_service_ids: list[int] = Field(default_factory=list)
    # Gardes de week-end sur le trimestre ecoule (equite).
    weekend_count: int = Field(default=0, ge=0)


class ExistingAssignment(BaseModel):
    staff_id: int
    shift: Shift


class SolveRequest(BaseModel):
    week_start: date
    week_end: date
    shifts: list[Shift] = Field(max_length=MAX_SHIFTS)
    staff: list[Staff] = Field(max_length=MAX_STAFF)
    existing_assignments: list[ExistingAssignment] = Field(
        default_factory=list, max_length=MAX_EXISTING
    )
    # Graine aleatoire de la recherche locale : rend un calcul reproductible.
    seed: int | None = None

    @model_validator(mode='after')
    def _check_week(self):
        if self.week_end < self.week_start:
            raise ValueError('week_end doit etre posterieur a week_start')
        return self


class Assignment(BaseModel):
    staff_id: int
    shift_id: int
    penalty: float


class SolveResponse(BaseModel):
    assignments: list[Assignment]
    unfilled_shift_ids: list[int]
    total_score: float
    score_detail: dict[str, float]
    duration_ms: int
