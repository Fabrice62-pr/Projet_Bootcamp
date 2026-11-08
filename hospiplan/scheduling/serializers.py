from rest_framework import serializers
from .models import ShiftType, Shift, ShiftRequiredCertification, ShiftAssignment, PlanningSession, DraftAssignment


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


class DraftAssignmentSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    shift_start = serializers.DateTimeField(source='shift.start_datetime', read_only=True)
    shift_end = serializers.DateTimeField(source='shift.end_datetime', read_only=True)
    shift_type_name = serializers.CharField(source='shift.shift_type.name', read_only=True)
    is_night_shift = serializers.BooleanField(source='shift.shift_type.is_night_shift', read_only=True)
    care_unit_name = serializers.CharField(source='shift.care_unit.name', read_only=True)
    service_name = serializers.CharField(source='shift.care_unit.service.name', read_only=True)

    def get_staff_name(self, obj):
        return f"{obj.staff.first_name} {obj.staff.last_name}"

    class Meta:
        model = DraftAssignment
        fields = [
            'id', 'staff', 'staff_name', 'shift',
            'shift_start', 'shift_end', 'shift_type_name', 'is_night_shift',
            'care_unit_name', 'service_name', 'penalty',
        ]


class PlanningSessionSerializer(serializers.ModelSerializer):
    draft_assignments = DraftAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = PlanningSession
        fields = '__all__'
