"""
Authentification par jeton porteur.

DRF attend `Authorization: Token <cle>`. La plateforme conversationnelle,
elle, envoie `Authorization: Bearer <cle>` pour les tools declares
`auth: project_auth` — ce format est fixe de son cote, non configurable.

Cette classe accepte donc le meme jeton sous les deux prefixes. Aucun
nouveau jeton, aucun nouveau stockage : seul le mot-cle change.
"""

from rest_framework.authentication import TokenAuthentication


class BearerTokenAuthentication(TokenAuthentication):
    keyword = 'Bearer'
