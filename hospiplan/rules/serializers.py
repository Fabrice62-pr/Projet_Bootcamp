from rest_framework import serializers
from .models import Rule, PatientLoad, StaffLoan


class RuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rule
        fields = '__all__'


class PatientLoadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientLoad
        fields = '__all__'


class StaffLoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffLoan
        fields = '__all__'
