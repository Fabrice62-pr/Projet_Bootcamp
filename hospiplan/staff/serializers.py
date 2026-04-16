from rest_framework import serializers
from .models import (
    Staff, Role, StaffRole, Specialty, StaffSpecialty,
    ContractType, Contract, Certification, CertificationDependency, StaffCertification
)


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = '__all__'


class ContractTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractType
        fields = '__all__'


class CertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = '__all__'


class CertificationDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificationDependency
        fields = '__all__'


class StaffCertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffCertification
        fields = '__all__'


class StaffRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffRole
        fields = '__all__'


class StaffSpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffSpecialty
        fields = '__all__'


class ContractSerializer(serializers.ModelSerializer):
    contract_type_name = serializers.CharField(source='contract_type.name', read_only=True)
    night_shift_allowed = serializers.BooleanField(source='contract_type.night_shift_allowed', read_only=True)
    max_hours_per_week = serializers.IntegerField(source='contract_type.max_hours_per_week', read_only=True)

    class Meta:
        model = Contract
        fields = '__all__'


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = '__all__'


class StaffDetailSerializer(serializers.ModelSerializer):
    """Lecture enrichie : roles, specialites, contrats, certifications."""
    staff_roles = StaffRoleSerializer(many=True, read_only=True)
    staff_specialties = StaffSpecialtySerializer(many=True, read_only=True)
    contracts = ContractSerializer(many=True, read_only=True)
    certifications = StaffCertificationSerializer(many=True, read_only=True)

    class Meta:
        model = Staff
        fields = '__all__'
