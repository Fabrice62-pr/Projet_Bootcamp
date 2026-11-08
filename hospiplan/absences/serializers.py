from rest_framework import serializers
from .models import AbsenceType, Absence


class AbsenceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbsenceType
        fields = '__all__'


class AbsenceSerializer(serializers.ModelSerializer):
    absence_type_name = serializers.CharField(source='absence_type.name', read_only=True)
    staff_name = serializers.SerializerMethodField()

    def get_staff_name(self, obj):
        return f"{obj.staff.first_name} {obj.staff.last_name}"

    class Meta:
        model = Absence
        fields = '__all__'
