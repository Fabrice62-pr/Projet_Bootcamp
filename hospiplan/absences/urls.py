from rest_framework.routers import DefaultRouter
from .views import AbsenceTypeViewSet, AbsenceViewSet

router = DefaultRouter()
router.register(r'absence-types', AbsenceTypeViewSet, basename='absencetype')
router.register(r'absences', AbsenceViewSet, basename='absence')

urlpatterns = router.urls
