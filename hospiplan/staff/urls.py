from rest_framework.routers import DefaultRouter
from .views import (
    StaffViewSet, RoleViewSet, StaffRoleViewSet,
    SpecialtyViewSet, StaffSpecialtyViewSet,
    ContractTypeViewSet, ContractViewSet,
    CertificationViewSet, CertificationDependencyViewSet, StaffCertificationViewSet,
)

router = DefaultRouter()
router.register(r'staff', StaffViewSet, basename='staff')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'staff-roles', StaffRoleViewSet, basename='staffrole')
router.register(r'specialties', SpecialtyViewSet, basename='specialty')
router.register(r'staff-specialties', StaffSpecialtyViewSet, basename='staffspecialty')
router.register(r'contract-types', ContractTypeViewSet, basename='contracttype')
router.register(r'contracts', ContractViewSet, basename='contract')
router.register(r'certifications', CertificationViewSet, basename='certification')
router.register(r'certification-dependencies', CertificationDependencyViewSet, basename='certdep')
router.register(r'staff-certifications', StaffCertificationViewSet, basename='staffcert')

urlpatterns = router.urls
