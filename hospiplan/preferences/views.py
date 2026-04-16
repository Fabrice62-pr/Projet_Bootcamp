from rest_framework import viewsets
from .models import Preference
from .serializers import PreferenceSerializer


class PreferenceViewSet(viewsets.ModelViewSet):
    queryset = Preference.objects.select_related('staff').all()
    serializer_class = PreferenceSerializer
