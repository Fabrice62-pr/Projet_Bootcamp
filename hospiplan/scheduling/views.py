from rest_framework import viewsets, status
from rest_framework.response import Response
from django.core.exceptions import ValidationError

from .models import ShiftType, Shift, ShiftRequiredCertification, ShiftAssignment
from .serializers import (
    ShiftTypeSerializer, ShiftSerializer, ShiftDetailSerializer,
    ShiftRequiredCertificationSerializer, ShiftAssignmentSerializer,
)
from .constraints import validate_assignment, check_min_staff_on_delete


class ShiftTypeViewSet(viewsets.ModelViewSet):
    queryset = ShiftType.objects.all()
    serializer_class = ShiftTypeSerializer


class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.select_related('care_unit__service', 'shift_type').all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ShiftDetailSerializer
        return ShiftSerializer


class ShiftRequiredCertificationViewSet(viewsets.ModelViewSet):
    queryset = ShiftRequiredCertification.objects.select_related('shift', 'certification').all()
    serializer_class = ShiftRequiredCertificationSerializer


class ShiftAssignmentViewSet(viewsets.ModelViewSet):
    """
    CRUD des affectations.
    CREATE et UPDATE appellent validate_assignment() qui applique les 8 contraintes dures.
    DELETE appelle check_min_staff_on_delete() pour proteger le seuil de securite.
    """
    queryset = ShiftAssignment.objects.select_related(
        'staff', 'shift__shift_type', 'shift__care_unit__service'
    ).all()
    serializer_class = ShiftAssignmentSerializer

    def _run_constraints(self, staff, shift, exclude_id=None):
        """Execute la validation et retourne une Response d'erreur si echec, None sinon."""
        try:
            validate_assignment(staff, shift, exclude_assignment_id=exclude_id)
        except ValidationError as exc:
            if hasattr(exc, 'error_dict'):
                # ValidationError levée avec un dict : chaque valeur est une liste d'ErrorObject
                error = {
                    k: v[0].message if v else ''
                    for k, v in exc.error_dict.items()
                }
            elif hasattr(exc, 'error_list') and exc.error_list:
                first = exc.error_list[0]
                error = {"message": first.message if hasattr(first, 'message') else str(first)}
            else:
                error = {"message": str(exc)}
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        return None

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        staff = serializer.validated_data['staff']
        shift = serializer.validated_data['shift']

        error_response = self._run_constraints(staff, shift)
        if error_response:
            return error_response

        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        staff = serializer.validated_data.get('staff', instance.staff)
        shift = serializer.validated_data.get('shift', instance.shift)

        error_response = self._run_constraints(staff, shift, exclude_id=instance.pk)
        if error_response:
            return error_response

        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            check_min_staff_on_delete(instance.shift)
        except ValidationError as exc:
            if isinstance(exc.message, dict):
                error = exc.message
            elif hasattr(exc, 'message_dict'):
                error = exc.message_dict
            else:
                error = {"message": exc.messages[0] if exc.messages else str(exc)}
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
