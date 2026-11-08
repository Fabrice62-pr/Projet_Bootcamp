from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm,
)
from django.forms import EmailInput, PasswordInput, TextInput
from django.urls import reverse

User = get_user_model()

INPUT_CLASS = 'form-control form-control-lg'
PENDING_MESSAGE = (
    "Votre compte est en attente de validation par un administrateur. "
    "Vous recevrez un e-mail dès son activation."
)


def _style(field, placeholder, autocomplete, label=None, autofocus=False):
    attrs = {'class': INPUT_CLASS, 'placeholder': placeholder, 'autocomplete': autocomplete}
    if autofocus:
        attrs['autofocus'] = True
    field.widget.attrs.update(attrs)
    if label:
        field.label = label


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
            'class': INPUT_CLASS,
            'placeholder': "Identifiant",
            'autofocus': True,
            'autocomplete': 'username',
        })
        self.fields['username'].label = "Identifiant"
        self.fields['password'].widget = PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Mot de passe',
            'autocomplete': 'current-password',
        })
        self.fields['password'].label = "Mot de passe"

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError:
            # Le backend refuse un compte inactif comme un mauvais mot de passe.
            # Si le mot de passe est juste, on explique plutot que le compte
            # attend sa validation (rien n'est revele sans le bon mot de passe).
            user = User.objects.filter(username=self.cleaned_data.get('username')).first()
            password = self.cleaned_data.get('password')
            if user and not user.is_active and password and user.check_password(password):
                raise forms.ValidationError(PENDING_MESSAGE, code='pending')
            raise


class RegisterForm(UserCreationForm):
    """
    Demande de creation de compte. Le compte est cree INACTIF : il ne donne
    acces a rien tant qu'un administrateur ne l'a pas valide.
    """

    first_name = forms.CharField(label='Prénom', max_length=150)
    last_name = forms.CharField(label='Nom', max_length=150)
    email = forms.EmailField(label='Adresse e-mail professionnelle')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'email', 'username')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self.fields['first_name'], 'Prénom', 'given-name', autofocus=True)
        _style(self.fields['last_name'], 'Nom', 'family-name')
        _style(self.fields['email'], 'prenom.nom@hopital.fr', 'email')
        _style(self.fields['username'], 'Identifiant de connexion', 'username', label='Identifiant')
        self.fields['username'].help_text = 'Lettres, chiffres et @ . + - _ uniquement.'
        _style(self.fields['password1'], 'Mot de passe', 'new-password', label='Mot de passe')
        self.fields['password1'].help_text = (
            '8 caractères minimum, pas uniquement des chiffres, ni trop courant.'
        )
        _style(self.fields['password2'], 'Confirmation', 'new-password', label='Confirmer le mot de passe')
        self.fields['password2'].help_text = ''

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Un compte utilise déjà cette adresse e-mail.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_active = False
        if commit:
            user.save()
        return user


class PasswordResetRequestForm(PasswordResetForm):
    """
    Demande de lien de reinitialisation. L'e-mail n'est pas envoye par Django :
    il est publie comme evenement et expedie par le microservice Notifications.
    Seuls les comptes actifs, avec cette adresse, recoivent un lien ; la page
    de confirmation est la meme dans tous les cas (on ne revele pas qui a un compte).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Adresse e-mail'
        self.fields['email'].widget = EmailInput(attrs={
            'class': INPUT_CLASS, 'placeholder': 'prenom.nom@hopital.fr',
            'autocomplete': 'email', 'autofocus': True,
        })

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        from hospiplan.events import publish_event

        user = context['user']
        path = reverse('frontend:password_reset_confirm',
                       kwargs={'uidb64': context['uid'], 'token': context['token']})
        reset_url = f"{context['protocol']}://{context['domain']}{path}"
        if settings.DEBUG and not settings.EVENTS_STORAGE_CONNECTION_STRING:
            # Developpement sans file d'evenements : le lien s'affiche dans la console.
            import logging
            logging.getLogger(__name__).warning('Lien de reinitialisation (dev) : %s', reset_url)
        publish_event('password.reset_requested', {
            'expires_hours': settings.PASSWORD_RESET_TIMEOUT // 3600,
            'recipients': [{
                'email': to_email,
                'name': user.get_full_name() or user.get_username(),
                'reset_url': reset_url,
            }],
        })


class NewPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self.fields['new_password1'], 'Nouveau mot de passe', 'new-password',
               label='Nouveau mot de passe', autofocus=True)
        self.fields['new_password1'].help_text = (
            '8 caractères minimum, pas uniquement des chiffres, ni trop courant.'
        )
        _style(self.fields['new_password2'], 'Confirmation', 'new-password',
               label='Confirmer le mot de passe')
