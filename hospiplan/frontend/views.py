from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordResetCompleteView, PasswordResetConfirmView,
    PasswordResetDoneView, PasswordResetView,
)
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.urls import reverse, reverse_lazy

from .forms import LoginForm, NewPasswordForm, PasswordResetRequestForm, RegisterForm
from .mcp_link import validate_chat_link


# ── Authentification ───────────────────────────────────────────────────

class HospiLoginView(LoginView):
    """
    Page de connexion : seul point d'entree public de l'application.

    Elle sert aussi de point d'arrivee aux liens de connexion emis par la
    plateforme conversationnelle. Un tel lien porte `token` et `projectId`
    en parametres ; le formulaire n'ayant pas d'attribut `action`, il se
    soumet sur l'URL courante et la chaine de requete survit au POST. Rien
    n'a donc besoin d'etre recopie dans un champ cache ni garde en session.
    """
    template_name = 'frontend/auth/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        # Un lien de connexion redemande TOUJOURS les identifiants, meme
        # quand une session Django est deja ouverte : rien ne garantit que
        # la personne devant l'ecran est celle qui a ouvert cette session,
        # et c'est cette identite-la qui sera rattachee a la conversation.
        #
        # Sans cette ligne, LoginView redirigerait un utilisateur deja
        # connecte sans jamais passer par form_valid, et le lien serait
        # perdu en route.
        if self._link_params()[0]:
            self.redirect_authenticated_user = False

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # `super()` ouvre la session : l'utilisateur n'est authentifie
        # qu'apres cet appel, et son identite est ce que la plateforme
        # attend.
        response = super().form_valid(form)

        if self._link_params()[0]:
            return self._confirm_link()

        return response

    def _link_params(self):
        return (
            self.request.GET.get('token', ''),
            self.request.GET.get('projectId', ''),
        )

    def _confirm_link(self):
        """
        Deuxieme etape : demander le secret de verification.

        Le lien n'est pas valide tout de suite. L'ecran suivant reprend le
        token et le projet en champs caches — les garder en session
        n'apporterait rien et survivrait a l'abandon du parcours.
        """
        token, project_id = self._link_params()

        return render(
            self.request,
            'frontend/auth/chat_link_secret.html',
            {'token': token, 'project_id': project_id},
        )


class HospiLogoutView(LogoutView):
    """Deconnexion (POST uniquement, conformement a Django >= 5)."""
    next_page = reverse_lazy('frontend:login')


# ── Creation de compte (validee par un administrateur) ─────────────────

def register(request):
    """
    Demande de compte : le compte est cree inactif et les administrateurs
    sont prevenus par e-mail (evenement "account.requested").
    """
    from django.contrib.auth import get_user_model
    from django.shortcuts import redirect

    from hospiplan.events import publish_event, recipient_user

    if request.user.is_authenticated:
        return redirect('frontend:dashboard')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST':
        # Champ piege rempli : c'est un robot. On simule un succes sans rien creer.
        if request.POST.get('website'):
            return redirect('frontend:register_done')
        if form.is_valid():
            user = form.save()
            admins = get_user_model().objects.filter(
                is_superuser=True, is_active=True
            ).exclude(email='')
            if admins:
                publish_event('account.requested', {
                    'username': user.username,
                    'full_name': user.get_full_name(),
                    'email': user.email,
                    'review_url': request.build_absolute_uri(
                        reverse('admin:auth_user_change', args=[user.pk])
                    ),
                    'recipients': [recipient_user(a) for a in admins],
                })
            return redirect('frontend:register_done')

    return render(request, 'frontend/auth/register.html', {'form': form})


def register_done(request):
    return render(request, 'frontend/auth/register_done.html')


# ── Mot de passe oublie ────────────────────────────────────────────────

class HospiPasswordResetView(PasswordResetView):
    template_name = 'frontend/auth/password_reset.html'
    form_class = PasswordResetRequestForm
    success_url = reverse_lazy('frontend:password_reset_done')


class HospiPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'frontend/auth/password_reset_done.html'

    def get_context_data(self, **kwargs):
        from django.conf import settings
        return {**super().get_context_data(**kwargs),
                'reset_hours': settings.PASSWORD_RESET_TIMEOUT // 3600}


class HospiPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'frontend/auth/password_reset_confirm.html'
    form_class = NewPasswordForm
    success_url = reverse_lazy('frontend:password_reset_complete')


class HospiPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'frontend/auth/password_reset_complete.html'


@login_required
@require_POST
def chat_link_confirm(request):
    """
    Valide le lien de connexion avec le secret saisi par l'utilisateur.

    Un secret refuse ne consomme pas le lien — la plateforme le verifie
    avant de toucher au token — donc on peut reafficher le formulaire et
    laisser corriger la saisie.
    """
    token = request.POST.get('token', '')
    project_id = request.POST.get('projectId', '')
    secret = request.POST.get('secret', '').strip()

    if not secret:
        return render(request, 'frontend/auth/chat_link_secret.html', {
            'token': token,
            'project_id': project_id,
            'error': "Saisissez le secret de verification.",
        })

    result = validate_chat_link(project_id, token, request.user, secret=secret)

    if result.retryable:
        return render(request, 'frontend/auth/chat_link_secret.html', {
            'token': token,
            'project_id': project_id,
            'error': result.message,
        }, status=400)

    # 502 sur echec : la plateforme n'a pas confirme, et un 200 laisserait
    # croire a une conversation authentifiee qui ne l'est pas.
    return render(
        request,
        'frontend/auth/chat_link.html',
        {'ok': result.ok, 'message': result.message},
        status=200 if result.ok else 502,
    )


@login_required
def dashboard(request):
    return render(request, 'frontend/dashboard.html')


# ── Soignants ──────────────────────────────────────────────────────────

@login_required
def staff_list(request):
    return render(request, 'frontend/staff/list.html')


@login_required
def staff_add(request):
    return render(request, 'frontend/staff/form.html')


@login_required
def staff_edit(request, pk):
    return render(request, 'frontend/staff/form.html', {'staff_id': pk})


# ── Postes / Gardes ────────────────────────────────────────────────────

@login_required
def shift_list(request):
    return render(request, 'frontend/shifts/list.html')


@login_required
def shift_add(request):
    return render(request, 'frontend/shifts/form.html')


@login_required
def shift_edit(request, pk):
    return render(request, 'frontend/shifts/form.html', {'shift_id': pk})


# ── Affectation ────────────────────────────────────────────────────────

@login_required
def assignment_new(request):
    return render(request, 'frontend/assignments/form.html')


# ── Planning ───────────────────────────────────────────────────────────

@login_required
def planning(request):
    return render(request, 'frontend/planning/planning.html')


@login_required
def planning_pdf(request):
    """
    Telechargement du planning en PDF. Le PDF est produit par le microservice
    Reporting ; le Core verifie la session puis relaie, la cle d'API ne quitte
    donc jamais le serveur.
    """
    from datetime import date, timedelta

    from scheduling.reporting_client import ReportingError, planning_pdf as fetch_pdf

    try:
        week_start = date.fromisoformat(request.GET.get('week_start', ''))
    except ValueError:
        return HttpResponseBadRequest('Parametre week_start invalide (AAAA-MM-JJ).')
    week_start -= timedelta(days=week_start.weekday())

    try:
        pdf = fetch_pdf(week_start)
    except ReportingError as exc:
        return HttpResponse(
            f'{exc} Reessayez dans quelques instants.',
            status=503, content_type='text/plain; charset=utf-8',
        )

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="planning-{week_start.isoformat()}.pdf"'
    return response


# ── Référentiels ────────────────────────────────────────────────────────

@login_required
def ref_services(request):
    return render(request, 'frontend/referentiel/services.html')


@login_required
def ref_shift_types(request):
    return render(request, 'frontend/referentiel/shift_types.html')


@login_required
def ref_contract_types(request):
    return render(request, 'frontend/referentiel/contract_types.html')


# ── Absences ────────────────────────────────────────────────────────────

@login_required
def absences_list(request):
    return render(request, 'frontend/absences/list.html')


@login_required
def ref_absence_types(request):
    return render(request, 'frontend/referentiel/absence_types.html')
