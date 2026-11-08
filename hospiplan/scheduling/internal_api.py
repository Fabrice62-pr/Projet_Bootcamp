"""
API interne reservee aux microservices (aucun acces navigateur).

Authentification par cle de service (en-tete X-Service-Key), distincte des
sessions utilisateur : le microservice Reporting n'a pas de compte Django.
"""

import hmac
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response


class HasServiceKey(BasePermission):
    message = 'Cle de service invalide ou absente.'

    def has_permission(self, request, view):
        expected = settings.REPORTING_SERVICE_KEY
        given = request.headers.get('X-Service-Key', '')
        return bool(expected) and hmac.compare_digest(given, expected)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([HasServiceKey])
def planning_report_data(request):
    """Donnees brutes d'une semaine de planning, pour le microservice Reporting."""
    from services.models import Service
    from staff.models import Contract, Staff

    from .models import Shift, ShiftAssignment

    try:
        ws = date.fromisoformat(request.query_params.get('week_start', ''))
    except ValueError:
        return Response({'error': 'week_start requis (AAAA-MM-JJ).'}, status=400)
    ws -= timedelta(days=ws.weekday())
    we = ws + timedelta(days=6)

    shifts = list(Shift.objects.filter(
        start_datetime__date__range=[ws, we]
    ).select_related('shift_type', 'care_unit__service').order_by('start_datetime'))

    assigned = {}
    for a in ShiftAssignment.objects.filter(shift__in=shifts).values('shift_id', 'staff_id'):
        assigned.setdefault(a['shift_id'], []).append(a['staff_id'])

    staff_ids = {sid for ids in assigned.values() for sid in ids}
    staff = Staff.objects.filter(Q(is_active=True) | Q(id__in=staff_ids)).order_by('last_name', 'first_name')

    max_hours = {}
    for c in Contract.objects.filter(
        start_date__lte=we
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=ws)).select_related(
        'contract_type'
    ).order_by('staff_id', '-start_date'):
        max_hours.setdefault(c.staff_id, c.contract_type.max_hours_per_week)

    managers = [
        {'email': s.manager.email, 'name': f'{s.manager.first_name} {s.manager.last_name}', 'service': s.name}
        for s in Service.objects.filter(manager__isnull=False, manager__is_active=True).select_related('manager')
    ]

    return Response({
        'week_start': ws,
        'week_end': we,
        'shifts': [
            {
                'id': s.id,
                'start': s.start_datetime,
                'end': s.end_datetime,
                'hours': s.shift_type.duration_hours,
                'is_night': s.shift_type.is_night_shift,
                'shift_type': s.shift_type.name,
                'service': s.care_unit.service.name,
                'care_unit': s.care_unit.name,
                'min_staff': s.min_staff,
                'max_staff': s.max_staff,
                'staff_ids': assigned.get(s.id, []),
            }
            for s in shifts
        ],
        'staff': [
            {
                'id': s.id,
                'name': f'{s.first_name} {s.last_name}',
                'email': s.email,
                'max_hours': max_hours.get(s.id),
            }
            for s in staff
        ],
        'managers': managers,
    })
