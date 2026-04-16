from rest_framework import viewsets
from .models import Service, CareUnit, ServiceStatus, StaffServiceAssignment
from .serializers import (
    ServiceSerializer, ServiceDetailSerializer,
    CareUnitSerializer, ServiceStatusSerializer, StaffServiceAssignmentSerializer,
)


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ServiceDetailSerializer
        return ServiceSerializer


class CareUnitViewSet(viewsets.ModelViewSet):
    queryset = CareUnit.objects.select_related('service').all()
    serializer_class = CareUnitSerializer


class ServiceStatusViewSet(viewsets.ModelViewSet):
    queryset = ServiceStatus.objects.select_related('service').all()
    serializer_class = ServiceStatusSerializer


class StaffServiceAssignmentViewSet(viewsets.ModelViewSet):
    queryset = StaffServiceAssignment.objects.select_related('staff', 'service').all()
    serializer_class = StaffServiceAssignmentSerializer
