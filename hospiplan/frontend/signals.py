"""
Prevenir l'utilisateur quand un administrateur active son compte.

Le signal couvre tous les chemins d'activation : case "Actif" cochee sur la
fiche de l'admin Django, action groupee, ou script.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse

from hospiplan.events import publish_event, recipient_user


@receiver(pre_save, sender=get_user_model())
def notify_account_activated(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk or not instance.is_active or not instance.email:
        return
    was_active = sender.objects.filter(pk=instance.pk).values_list('is_active', flat=True).first()
    if was_active is False:
        publish_event('account.activated', {
            'username': instance.get_username(),
            'login_url': settings.SITE_URL.rstrip('/') + reverse('frontend:login') if settings.SITE_URL else '',
            'recipients': [recipient_user(instance)],
        })
