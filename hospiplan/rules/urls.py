from rest_framework.routers import DefaultRouter
from .views import RuleViewSet, PatientLoadViewSet, StaffLoanViewSet

router = DefaultRouter()
router.register(r'rules', RuleViewSet, basename='rule')
router.register(r'patient-loads', PatientLoadViewSet, basename='patientload')
router.register(r'staff-loans', StaffLoanViewSet, basename='staffloan')

urlpatterns = router.urls
