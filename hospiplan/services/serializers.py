from rest_framework import serializers
from .models import Service, CareUnit, ServiceStatus, StaffServiceAssignment


class CareUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = CareUnit
        fields = '__all__'


class ServiceStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceStatus
        fields = '__all__'


class StaffServiceAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffServiceAssignment
        fields = '__all__'


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'


class ServiceDetailSerializer(serializers.ModelSerializer):
    care_units = CareUnitSerializer(many=True, read_only=True)
    statuses = ServiceStatusSerializer(many=True, read_only=True)
    staff_assignments = StaffServiceAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = '__all__'
