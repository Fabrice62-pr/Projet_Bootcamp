from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # API REST
    path('api/', include('staff.urls')),
    path('api/', include('scheduling.urls')),
    path('api/', include('services.urls')),
    path('api/', include('absences.urls')),
    path('api/', include('preferences.urls')),
    path('api/', include('rules.urls')),
    # Frontend
    path('', include('frontend.urls', namespace='frontend')),
]
