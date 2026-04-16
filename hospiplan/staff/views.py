from rest_framework import viewsets
from .models import (
    Staff, Role, StaffRole, Specialty, StaffSpecialty,
    ContractType, Contract, Certification, CertificationDependency, StaffCertification
)
from .serializers import (
    StaffSerializer, StaffDetailSerializer,
    RoleSerializer, StaffRoleSerializer,
    SpecialtySerializer, StaffSpecialtySerializer,
    ContractTypeSerializer, ContractSerializer,
    CertificationSerializer, CertificationDependencySerializer, StaffCertificationSerializer,
)


class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all().order_by('last_name', 'first_name')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return StaffDetailSerializer
        return StaffSerializer


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer


class StaffRoleViewSet(viewsets.ModelViewSet):
    queryset = StaffRole.objects.select_related('staff', 'role').all()
    serializer_class = StaffRoleSerializer


class SpecialtyViewSet(viewsets.ModelViewSet):
    queryset = Specialty.objects.all()
    serializer_class = SpecialtySerializer


class StaffSpecialtyViewSet(viewsets.ModelViewSet):
    queryset = StaffSpecialty.objects.select_related('staff', 'specialty').all()
    serializer_class = StaffSpecialtySerializer


class ContractTypeViewSet(viewsets.ModelViewSet):
    queryset = ContractType.objects.all()
    serializer_class = ContractTypeSerializer


class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.select_related('staff', 'contract_type').all()
    serializer_class = ContractSerializer


class CertificationViewSet(viewsets.ModelViewSet):
    queryset = Certification.objects.all()
    serializer_class = CertificationSerializer


class CertificationDependencyViewSet(viewsets.ModelViewSet):
    queryset = CertificationDependency.objects.select_related(
        'parent_cert', 'required_cert'
    ).all()
    serializer_class = CertificationDependencySerializer


class StaffCertificationViewSet(viewsets.ModelViewSet):
    queryset = StaffCertification.objects.select_related('staff', 'certification').all()
    serializer_class = StaffCertificationSerializer
