from rest_framework import viewsets
from .models import Rule, PatientLoad, StaffLoan
from .serializers import RuleSerializer, PatientLoadSerializer, StaffLoanSerializer


class RuleViewSet(viewsets.ModelViewSet):
    queryset = Rule.objects.all()
    serializer_class = RuleSerializer


class PatientLoadViewSet(viewsets.ModelViewSet):
    queryset = PatientLoad.objects.select_related('care_unit__service').all()
    serializer_class = PatientLoadSerializer


class StaffLoanViewSet(viewsets.ModelViewSet):
    queryset = StaffLoan.objects.select_related('staff', 'from_service', 'to_service').all()
    serializer_class = StaffLoanSerializer
