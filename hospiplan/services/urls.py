from rest_framework.routers import DefaultRouter
from .views import (
    ServiceViewSet, CareUnitViewSet,
    ServiceStatusViewSet, StaffServiceAssignmentViewSet,
)

router = DefaultRouter()
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'care-units', CareUnitViewSet, basename='careunit')
router.register(r'service-statuses', ServiceStatusViewSet, basename='servicestatus')
router.register(r'service-assignments', StaffServiceAssignmentViewSet, basename='serviceassignment')

urlpatterns = router.urls
