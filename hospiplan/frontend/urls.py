from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Soignants
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_add, name='staff_add'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),

    # Postes / Gardes
    path('shifts/', views.shift_list, name='shift_list'),
    path('shifts/add/', views.shift_add, name='shift_add'),
    path('shifts/<int:pk>/edit/', views.shift_edit, name='shift_edit'),

    # Affectation
    path('assignments/new/', views.assignment_new, name='assignment_new'),

    # Planning
    path('planning/', views.planning, name='planning'),

    # Référentiels
    path('referentiel/services/', views.ref_services, name='ref_services'),
    path('referentiel/shift-types/', views.ref_shift_types, name='ref_shift_types'),
    path('referentiel/contract-types/', views.ref_contract_types, name='ref_contract_types'),
]
