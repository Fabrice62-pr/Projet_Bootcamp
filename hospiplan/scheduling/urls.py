from rest_framework.routers import DefaultRouter
from .views import (
    ShiftTypeViewSet, ShiftViewSet,
    ShiftRequiredCertificationViewSet, ShiftAssignmentViewSet,
)

router = DefaultRouter()
router.register(r'shift-types', ShiftTypeViewSet, basename='shifttype')
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'shift-certifications', ShiftRequiredCertificationViewSet, basename='shiftcert')
router.register(r'assignments', ShiftAssignmentViewSet, basename='assignment')

urlpatterns = router.urls
