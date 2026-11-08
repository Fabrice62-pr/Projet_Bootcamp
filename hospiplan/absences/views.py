from rest_framework import viewsets
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
