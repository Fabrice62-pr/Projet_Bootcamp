from django import forms
from django.contrib import admin

from .models import McpProject


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
