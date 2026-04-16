from rest_framework import viewsets
from .models import AbsenceType, Absence
from .serializers import AbsenceTypeSerializer, AbsenceSerializer


class AbsenceTypeViewSet(viewsets.ModelViewSet):
    queryset = AbsenceType.objects.all()
    serializer_class = AbsenceTypeSerializer


class AbsenceViewSet(viewsets.ModelViewSet):
    queryset = Absence.objects.select_related('staff', 'absence_type').all()
    serializer_class = AbsenceSerializer
