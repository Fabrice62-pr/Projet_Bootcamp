from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    ShiftTypeViewSet, ShiftViewSet,
    ShiftRequiredCertificationViewSet, ShiftAssignmentViewSet,
    PlanningSessionViewSet,
)
from .internal_api import planning_report_data

router = DefaultRouter()
router.register(r'shift-types', ShiftTypeViewSet, basename='shifttype')
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'shift-certifications', ShiftRequiredCertificationViewSet, basename='shiftcert')
router.register(r'assignments', ShiftAssignmentViewSet, basename='assignment')
router.register(r'plannings', PlanningSessionViewSet, basename='planning')

urlpatterns = router.urls + [
    # Reserve aux microservices (cle de service), voir internal_api.py
    path('internal/planning-report/', planning_report_data, name='internal-planning-report'),
]
