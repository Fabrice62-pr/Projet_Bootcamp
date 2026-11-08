from django.contrib.auth.forms import AuthenticationForm
from django.forms import TextInput, PasswordInput


class LoginForm(AuthenticationForm):
    """Formulaire de connexion habille aux couleurs de l'application."""

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': "Identifiant ou mot de passe incorrect.",
        'inactive': "Ce compte est desactive. Contactez l'administrateur.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget = TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': "Identifiant",
            'autofocus': True,
            'autocomplete': 'username',
        })
        self.fields['username'].label = "Identifiant"
        self.fields['password'].widget = PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Mot de passe',
            'autocomplete': 'current-password',
        })
        self.fields['password'].label = "Mot de passe"
