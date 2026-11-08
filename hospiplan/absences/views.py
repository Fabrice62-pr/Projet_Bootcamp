from rest_framework import viewsets

from hospiplan.events import publish_event, recipient

from .models import AbsenceType, Absence
from .serializers import AbsenceTypeSerializer, AbsenceSerializer


class AbsenceTypeViewSet(viewsets.ModelViewSet):
    queryset = AbsenceType.objects.all()
    serializer_class = AbsenceTypeSerializer


class AbsenceViewSet(viewsets.ModelViewSet):
    serializer_class = AbsenceSerializer

    def get_queryset(self):
        qs = Absence.objects.select_related('staff', 'absence_type').all()
        staff_id = self.request.query_params.get('staff')
        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        return qs

    def perform_create(self, serializer):
        absence = serializer.save()
        publish_event('absence.created', {
            'absence_id': absence.id,
            'absence_type': absence.absence_type.name,
            'start_date': absence.start_date,
            'end_date': absence.actual_end_date or absence.expected_end_date,
            'recipients': [recipient(absence.staff)],
        })
