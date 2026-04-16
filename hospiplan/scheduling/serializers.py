from rest_framework import serializers
from .models import ShiftType, Shift, ShiftRequiredCertification, ShiftAssignment


class ShiftTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftType
        fields = '__all__'


class ShiftRequiredCertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftRequiredCertification
        fields = '__all__'


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = '__all__'


class ShiftDetailSerializer(serializers.ModelSerializer):
    required_certifications = ShiftRequiredCertificationSerializer(many=True, read_only=True)
    assignments = serializers.SerializerMethodField()

    def get_assignments(self, obj):
        return ShiftAssignmentSerializer(obj.assignments.all(), many=True).data

    class Meta:
        model = Shift
        fields = '__all__'


class ShiftAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftAssignment
        fields = '__all__'
        read_only_fields = ('assigned_at',)
