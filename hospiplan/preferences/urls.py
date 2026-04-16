from rest_framework.routers import DefaultRouter
from .views import PreferenceViewSet

router = DefaultRouter()
router.register(r'preferences', PreferenceViewSet, basename='preference')

urlpatterns = router.urls
