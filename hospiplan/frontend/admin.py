from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import McpProject

User = get_user_model()


class HospiUserAdmin(UserAdmin):
    """
    Comptes utilisateurs : les demandes de creation arrivent inactives.
    Filtrer sur "Actif : Non" pour les voir, puis utiliser l'action ci-dessous.
    """
    list_display = ('username', 'get_full_name', 'email', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    ordering = ('is_active', '-date_joined')
    actions = ['activate_accounts']

    @admin.action(description='Valider les comptes sélectionnés (et prévenir par e-mail)')
    def activate_accounts(self, request, queryset):
        count = 0
        # save() un par un, et non update() : le signal d'activation envoie l'e-mail.
        for user in queryset.filter(is_active=False):
            user.is_active = True
            user.save(update_fields=['is_active'])
            count += 1
        self.message_user(request, f'{count} compte(s) validé(s).', messages.SUCCESS)


# Le modele User est deja enregistre par django.contrib.auth : on le remplace.
admin.site.unregister(User)
admin.site.register(User, HospiUserAdmin)


class McpProjectForm(forms.ModelForm):
    """
    Le secret est masque a la saisie comme un mot de passe.

    `render_value=True` le conserve a la reouverture du formulaire : sans
    lui, enregistrer une simple correction de libelle effacerait le secret.
    """

    class Meta:
        model = McpProject
        fields = '__all__'
        widgets = {
            'verify_secret': forms.PasswordInput(render_value=True),
        }


@admin.register(McpProject)
class McpProjectAdmin(admin.ModelAdmin):
    form = McpProjectForm
    list_display = ('__str__', 'project_id', 'base_url', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('label', 'project_id')
    # Le secret n'apparait dans aucune liste : il ne se lit que sur la fiche,
    # et masque.
    fields = ('label', 'project_id', 'verify_secret', 'base_url', 'is_active')
