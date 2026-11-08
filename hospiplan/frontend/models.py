from django.db import models


class McpProject(models.Model):
    """
    Projet de la plateforme conversationnelle branche sur HospiPlan.

    Le secret de verification vit ici plutot que dans une variable
    d'environnement pour trois raisons : il est propre a chaque projet, il
    change des qu'on le regenere dans le dashboard, et le saisir dans
    l'admin evite de redemarrer le serveur a chaque fois.

    Il n'est jamais expose a l'utilisateur final : seul le serveur s'en sert,
    pour s'authentifier aupres de la plateforme quand il confirme qu'un
    utilisateur vient de se connecter.
    """

    project_id = models.CharField(
        "Identifiant du projet",
        max_length=64,
        unique=True,
        help_text="UUID du projet, visible dans l'URL du dashboard.",
    )
    label = models.CharField(
        "Nom",
        max_length=100,
        blank=True,
        help_text="Pour s'y retrouver quand plusieurs projets sont branches.",
    )
    verify_secret = models.CharField(
        "Secret de verification",
        max_length=255,
        help_text=(
            "Affiche une seule fois dans le dashboard, a la configuration du "
            "provider d'authentification du projet."
        ),
    )
    base_url = models.URLField(
        "Adresse de la plateforme",
        default="http://localhost:4000",
        help_text="Racine de l'API MCP, sans barre oblique finale.",
    )
    is_active = models.BooleanField(
        "Actif",
        default=True,
        help_text="Decocher suspend l'authentification des conversations de ce projet.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Projet conversationnel"
        verbose_name_plural = "Projets conversationnels"
        ordering = ('label', 'project_id')

    def __str__(self):
        return self.label or self.project_id
