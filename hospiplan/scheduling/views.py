from datetime import date, timedelta

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError

from .models import ShiftType, Shift, ShiftRequiredCertification, ShiftAssignment, PlanningSession, DraftAssignment
from .serializers import (
    ShiftTypeSerializer, ShiftSerializer, ShiftDetailSerializer,
    ShiftRequiredCertificationSerializer, ShiftAssignmentSerializer,
    PlanningSessionSerializer,
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


class PlanningSessionViewSet(viewsets.ModelViewSet):
    queryset = PlanningSession.objects.prefetch_related(
        'draft_assignments__staff',
        'draft_assignments__shift__shift_type',
        'draft_assignments__shift__care_unit__service',
    ).all()
    serializer_class = PlanningSessionSerializer
    http_method_names = ['get', 'delete', 'post', 'head', 'options']

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        week_start_str = request.data.get('week_start')
        if not week_start_str:
            return Response({'error': 'week_start requis (YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ws = date.fromisoformat(str(week_start_str))
        except ValueError:
            return Response({'error': 'Format invalide. Utilisez YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        # Recaler sur le lundi
        ws = ws - timedelta(days=ws.weekday())

        from .generator import generate_planning
        session, unpaved_ids = generate_planning(ws)

        data = PlanningSessionSerializer(session).data
        data['unpaved_shift_ids'] = unpaved_ids
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='publish')
    def publish(self, request, pk=None):
        session = self.get_object()
        if session.status != 'draft':
            return Response({'error': 'Ce planning est déjà publié.'}, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        errors = []

        for da in session.draft_assignments.select_related(
            'staff', 'shift__shift_type', 'shift__care_unit__service'
        ):
            if ShiftAssignment.objects.filter(staff=da.staff, shift=da.shift).exists():
                created_count += 1
                continue
            try:
                validate_assignment(da.staff, da.shift)
                ShiftAssignment.objects.create(staff=da.staff, shift=da.shift)
                created_count += 1
            except ValidationError as exc:
                reason = exc.message if isinstance(exc.message, str) else '; '.join(exc.messages)
                errors.append({
                    'staff': f"{da.staff.first_name} {da.staff.last_name}",
                    'shift_id': da.shift_id,
                    'reason': reason,
                })

        session.status = 'published'
        session.save()

        return Response({
            'status': 'published',
            'created': created_count,
            'errors': errors,
        })
