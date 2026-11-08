from rest_framework.routers import DefaultRouter
from .views import (
    ShiftTypeViewSet, ShiftViewSet,
    ShiftRequiredCertificationViewSet, ShiftAssignmentViewSet,
    PlanningSessionViewSet,
)

router = DefaultRouter()
router.register(r'shift-types', ShiftTypeViewSet, basename='shifttype')
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'shift-certifications', ShiftRequiredCertificationViewSet, basename='shiftcert')
router.register(r'assignments', ShiftAssignmentViewSet, basename='assignment')
router.register(r'plannings', PlanningSessionViewSet, basename='planning')

urlpatterns = router.urls
