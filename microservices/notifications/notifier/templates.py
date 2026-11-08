"""Contenu des e-mails, en francais, version texte et HTML."""

from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

PARIS = ZoneInfo('Europe/Paris')
DAYS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
          'août', 'septembre', 'octobre', 'novembre', 'décembre']


@dataclass(frozen=True)
class Message:
    subject: str
    text: str
    html: str


def _day(d: date) -> str:
    return f'{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}'


def fmt_date(value: str) -> str:
    try:
        return _day(date.fromisoformat(value[:10]))
    except (TypeError, ValueError):
        return str(value)


def fmt_datetime(value: str) -> str:
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return str(value)
    if dt.tzinfo:
        dt = dt.astimezone(PARIS)
    return f'{_day(dt.date())} à {dt:%H:%M}'


def _shift_line(shift: dict) -> str:
    end = fmt_datetime(shift.get('end', ''))
    end_time = end.rsplit(' à ', 1)[-1]
    return (f"{fmt_datetime(shift.get('start', ''))} - {end_time} : "
            f"{shift.get('shift_type', 'Garde')}, {shift.get('service', '')} / {shift.get('care_unit', '')}")


def _safe_url(url) -> str:
    """Seuls les liens http(s) sont acceptes (pas de javascript:, data:, ...)."""
    url = str(url or '').strip()
    return url if url.startswith(('https://', 'http://')) else ''


def _build(subject, greeting_name, paragraphs, items=(), footer=(), action=None):
    hello = f'Bonjour {greeting_name},' if greeting_name else 'Bonjour,'
    signature = "L'équipe planification — HospiPlan"
    label, url = action if action else ('', '')
    url = _safe_url(url)

    text = '\n\n'.join([hello, *paragraphs])
    if items:
        text += '\n\n' + '\n'.join(f'  - {i}' for i in items)
    if url:
        text += f'\n\n{label} : {url}'
    if footer:
        text += '\n\n' + '\n\n'.join(footer)
    text += f'\n\n{signature}\n'

    html_items = ''.join(f'<li>{escape(i)}</li>' for i in items)
    html_action = (
        f'<p style="margin:24px 0"><a href="{escape(url, quote=True)}" '
        'style="background:#2e86c1;color:#ffffff;padding:12px 22px;border-radius:8px;'
        f'text-decoration:none;font-weight:600;display:inline-block">{escape(label)}</a></p>'
        f'<p style="font-size:12px;color:#6b7280">Si le bouton ne fonctionne pas, copiez ce lien : '
        f'{escape(url)}</p>'
    ) if url else ''
    html = (
        '<div style="font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#1f2937">'
        f'<p>{escape(hello)}</p>'
        + ''.join(f'<p>{escape(p)}</p>' for p in paragraphs)
        + (f'<ul>{html_items}</ul>' if items else '')
        + html_action
        + ''.join(f'<p>{escape(p)}</p>' for p in footer)
        + f'<p style="color:#6b7280">{escape(signature)}</p></div>'
    )
    return Message(subject=subject, text=text, html=html)


def render(event, recipient) -> Message:
    data, details = event.data, recipient.details

    if event.type == 'planning.published':
        shifts = sorted(details.get('shifts', []), key=lambda s: s.get('start', ''))
        period = f"du {fmt_date(data.get('week_start', ''))} au {fmt_date(data.get('week_end', ''))}"
        return _build(
            f'Votre planning {period}',
            recipient.name,
            [f'Le planning de la semaine {period} vient d\'être publié.',
             f'Vous êtes affecté(e) à {len(shifts)} garde(s) :'],
            [_shift_line(s) for s in shifts],
        )

    if event.type == 'assignment.created':
        return _build(
            'Nouvelle garde dans votre planning',
            recipient.name,
            ['Une nouvelle garde vient de vous être attribuée :'],
            [_shift_line(details.get('shift', {}))],
        )

    if event.type == 'absence.created':
        return _build(
            'Confirmation de votre absence',
            recipient.name,
            [f"Votre absence ({data.get('absence_type', 'absence')}) a bien été enregistrée "
             f"du {fmt_date(data.get('start_date', ''))} au {fmt_date(data.get('end_date', ''))}.",
             'Vous ne serez affecté(e) à aucune garde sur cette période.'],
        )

    if event.type == 'report.weekly':
        period = f"du {fmt_date(data.get('week_start', ''))} au {fmt_date(data.get('week_end', ''))}"
        understaffed = data.get('understaffed', [])
        total_under = data.get('understaffed_total', len(understaffed))
        paragraphs = [
            f'Voici la synthèse du planning de la semaine {period}'
            + (f" (service {details['service']})." if details.get('service') else '.'),
            f"Couverture des effectifs minimum : {data.get('coverage_percent', 0)} % "
            f"({data.get('total_assignments', 0)} affectation(s) pour {data.get('total_shifts', 0)} créneau(x)).",
        ]
        if total_under:
            paragraphs.append(f'{total_under} créneau(x) en sous-effectif :')
        else:
            paragraphs.append('Tous les créneaux atteignent leur effectif minimum.')
        items = [
            f"{fmt_datetime(s.get('start', ''))} : {s.get('shift_type', '')}, "
            f"{s.get('service', '')} / {s.get('care_unit', '')} — "
            f"{s.get('assigned', 0)}/{s.get('min_staff', 0)} soignant(s)"
            for s in understaffed
        ]
        if total_under > len(understaffed):
            items.append(f'… et {total_under - len(understaffed)} autre(s)')
        footer = []
        overloaded = data.get('overloaded', [])
        if overloaded:
            footer.append('Soignants proches de leur plafond horaire : ' + ', '.join(
                f"{p.get('name', '')} ({p.get('hours', 0)} h / {p.get('max_hours', 0)} h)" for p in overloaded
            ) + '.')
        footer.append('Le planning détaillé est disponible en PDF depuis la page Planning.')
        return _build(f"Rapport hebdomadaire — semaine du {fmt_date(data.get('week_start', ''))}",
                      recipient.name, paragraphs, items, footer)

    if event.type == 'password.reset_requested':
        hours = data.get('expires_hours', 2)
        return _build(
            'Réinitialisation de votre mot de passe',
            recipient.name,
            ['Vous avez demandé à réinitialiser le mot de passe de votre compte HospiPlan.',
             f'Cliquez sur le bouton ci-dessous pour en choisir un nouveau. Ce lien est valable '
             f'{hours} heure(s) et ne peut servir qu\'une fois.'],
            action=('Choisir un nouveau mot de passe', details.get('reset_url')),
            footer=["Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail : "
                    "votre mot de passe reste inchangé."],
        )

    if event.type == 'account.requested':
        who = data.get('full_name') or data.get('username', '')
        return _build(
            f"Nouvelle demande de compte : {data.get('username', '')}",
            recipient.name,
            [f"{who} ({data.get('email', '')}) a demandé un compte HospiPlan "
             f"avec l'identifiant « {data.get('username', '')} ».",
             "Le compte reste inactif tant qu'un administrateur ne l'a pas validé."],
            action=('Examiner la demande', data.get('review_url')),
            footer=["Pour valider : cochez « Actif » sur la fiche, ou utilisez l'action "
                    "« Valider les comptes sélectionnés » dans la liste des utilisateurs."],
        )

    if event.type == 'account.activated':
        return _build(
            'Votre compte HospiPlan est activé',
            recipient.name,
            [f"Votre compte « {data.get('username', '')} » a été validé par un administrateur.",
             'Vous pouvez désormais vous connecter à HospiPlan.'],
            action=('Se connecter', data.get('login_url')),
        )

    raise ValueError(f'Aucun modele pour {event.type}')
