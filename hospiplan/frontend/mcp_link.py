"""
Validation du lien de connexion emis par la plateforme MCP.

Quand un utilisateur ecrit a l'assistant depuis WhatsApp ou le widget web,
la plateforme constate que la conversation n'est pas authentifiee et lui
envoie un lien vers la page de connexion de cette application, avec deux
parametres : `token` (le lien lui-meme) et `projectId`.

Une fois l'utilisateur identifie ici, c'est a nous de prevenir la
plateforme. Le sens de l'appel ne change jamais : HospiPlan appelle la
plateforme, jamais l'inverse.

Bibliotheque standard uniquement : ajouter une dependance pour un seul
POST ne se justifie pas.
"""

import json
import urllib.error
import urllib.request
from typing import NamedTuple

from django.conf import settings

#: Chemin fixe par le contrat de la plateforme.
CALLBACK_PATH = '/auth/chat-link/callback'

#: Duree de vie demandee pour le jeton transmis, en secondes. La plateforme
#: plafonne a 24 h ; un jeton DRF n'expirant pas de lui-meme, autant demander
#: le maximum plutot que de voir l'utilisateur ejecte au bout d'une heure.
USER_TOKEN_TTL_SECONDS = 86400

#: Un lien vaut quelques minutes : inutile d'attendre longtemps une
#: plateforme qui ne repond pas, l'utilisateur est devant son ecran.
TIMEOUT_SECONDS = 10


class LinkResult(NamedTuple):
    """
    Issue d'une validation.

    `retryable` marque le cas ou reafficher le formulaire a du sens : la
    plateforme verifie le secret AVANT de toucher au lien, qui reste donc
    utilisable apres une saisie erronee. Elle repond 404 aussi bien pour un
    secret faux que pour un lien inconnu — volontairement, pour ne pas
    confirmer l'existence d'un token a qui ne le connait pas — les deux
    partagent donc le meme traitement.
    """

    ok: bool
    message: str
    retryable: bool = False


def _api_token(user) -> str:
    """
    Jeton d'API de l'utilisateur, cree au premier besoin.

    Import local : ce module est charge avec les vues, avant que le registre
    des applications ne soit pret.
    """
    from rest_framework.authtoken.models import Token

    return Token.objects.get_or_create(user=user)[0].key


def _project(project_id: str):
    from .models import McpProject

    return McpProject.objects.filter(project_id=project_id, is_active=True).first()


def _base_url(project_id: str) -> str:
    """
    Adresse de la plateforme : la fiche du projet d'abord, sinon les
    settings — un projet non enregistre reste joignable si l'operateur
    n'en a qu'un.
    """
    project = _project(project_id)
    return project.base_url if project else settings.MCP_BASE_URL


def _stored_secret(project_id: str) -> str:
    """
    Secret enregistre cote serveur, quand l'utilisateur n'en saisit pas.

    La base d'abord — un administrateur peut la corriger sans redemarrer —
    puis la variable d'environnement, pour ne pas casser une installation
    qui l'utilise deja.
    """
    project = _project(project_id)

    if project:
        return project.verify_secret

    return settings.MCP_VERIFY_SECRET


def validate_chat_link(
    project_id: str,
    token: str,
    user,
    secret: str | None = None,
) -> LinkResult:
    """
    Signale a la plateforme que l'utilisateur vient de s'authentifier.

    Transmet aussi le jeton d'API de cet utilisateur : les tools declares
    `auth: project_auth` appelleront alors HospiPlan avec SES droits, et non
    ceux d'un compte de service partage par tout le monde.

    `secret` permet a l'appelant d'imposer le secret a envoyer — c'est le
    cas quand l'utilisateur le saisit lui-meme. Sans lui, celui enregistre
    cote serveur est utilise.

    Le message retourne s'adresse a l'utilisateur final : il ne contient ni
    le secret, ni le token du lien.
    """
    if not token or not project_id:
        return LinkResult(False, (
            "Lien incomplet : il doit porter les parametres token et projectId. "
            "Renvoyez un message dans la conversation pour en obtenir un nouveau."
        ))

    secret = secret or _stored_secret(project_id)
    base_url = _base_url(project_id)

    if not secret:
        return LinkResult(False, (
            "Aucun secret de verification disponible pour ce projet. Un "
            "administrateur doit l'enregistrer dans l'administration, section "
            "« Projets conversationnels »."
        ))

    payload = {
        'projectId': project_id,
        'token': token,
        'secret': secret,
        'externalUserId': user.get_username(),
        'resolvedTokenRef': _api_token(user),
        'resolvedTokenExpiresIn': USER_TOKEN_TTL_SECONDS,
    }

    request = urllib.request.Request(
        base_url.rstrip('/') + CALLBACK_PATH,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS):
            return LinkResult(
                True,
                "Conversation authentifiee. Vous pouvez commencer a discuter.",
            )
    except urllib.error.HTTPError as error:
        return LinkResult(False, _explain(error), retryable=error.code in (401, 404))
    except urllib.error.URLError as error:
        return LinkResult(False, (
            f"Plateforme conversationnelle injoignable ({base_url}) : "
            f"{error.reason}"
        ))


def _explain(error: urllib.error.HTTPError) -> str:
    """
    Traduit la reponse de la plateforme en message actionnable.

    Un « 401 » brut ne dit pas a l'exploitant si c'est le secret qui est
    faux ou le lien qui a expire — or les deux se corrigent differemment.
    """
    if error.code == 401:
        return (
            "Secret de verification refuse par la plateforme. Verifiez "
            "votre saisie, ou demandez le secret courant a un administrateur."
        )

    if error.code == 404:
        # La plateforme ne distingue pas les deux cas dans sa reponse : le
        # message ne peut pas etre plus precis qu'elle.
        return (
            "Secret de verification refuse, ou lien invalide. Verifiez votre "
            "saisie ; si l'erreur persiste, renvoyez un message dans la "
            "conversation pour obtenir un nouveau lien."
        )

    if error.code == 409:
        return (
            "Ce lien a deja ete utilise. Renvoyez un message dans la "
            "conversation pour en obtenir un nouveau."
        )

    if error.code == 410:
        return (
            "Ce lien a expire. Renvoyez un message dans la conversation "
            "pour en obtenir un nouveau."
        )

    return f"La plateforme a repondu {error.code}."
