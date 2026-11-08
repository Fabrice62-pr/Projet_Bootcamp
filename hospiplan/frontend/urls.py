from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    # Authentification
    path('login/', views.HospiLoginView.as_view(), name='login'),
    path('logout/', views.HospiLogoutView.as_view(), name='logout'),
    # Deuxieme etape du lien de connexion conversationnel.
    path('login/confirm/', views.chat_link_confirm, name='chat_link_confirm'),

    # Creation de compte (validee par un administrateur)
    path('register/', views.register, name='register'),
    path('register/done/', views.register_done, name='register_done'),

    # Mot de passe oublie
    path('password-reset/', views.HospiPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.HospiPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.HospiPasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('reset/done/', views.HospiPasswordResetCompleteView.as_view(), name='password_reset_complete'),

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
    path('planning/pdf/', views.planning_pdf, name='planning_pdf'),

    # Référentiels
    path('referentiel/services/', views.ref_services, name='ref_services'),
    path('referentiel/shift-types/', views.ref_shift_types, name='ref_shift_types'),
    path('referentiel/contract-types/', views.ref_contract_types, name='ref_contract_types'),

    # Absences
    path('absences/', views.absences_list, name='absences_list'),
    path('referentiel/absence-types/', views.ref_absence_types, name='ref_absence_types'),
]
