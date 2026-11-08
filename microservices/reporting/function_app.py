"""
Microservice "Reporting" de HospiPlan (Azure Functions, Python v2).

  GET  /api/health                sonde publique
  GET  /api/reports/planning      PDF du planning d'une semaine (?week_start=AAAA-MM-JJ)
  POST /api/reports/weekly/run    lance la synthese hebdomadaire a la demande (demo, tests)
  minuteur weekly_report          chaque lundi (WEEKLY_REPORT_SCHEDULE) : synthese
                                  publiee vers le service Notifications

Les routes /api/reports/* exigent l'en-tete X-API-Key.
Donnees lues via l'API interne du Core : aucun acces direct a la base.
"""

import hmac
import json
import logging
import os
from datetime import date, datetime, timedelta

import azure.functions as func

from reporter.core_client import CoreUnavailable, fetch_planning_data
from reporter.pdf import render_planning_pdf
from reporter.stats import PARIS, build_report
from reporter.weekly import build_weekly_event, publish

logging.getLogger('azure').setLevel(logging.WARNING)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _json(body, status=200):
    return func.HttpResponse(json.dumps(body, ensure_ascii=False), status_code=status,
                             mimetype='application/json')


def _authorized(req: func.HttpRequest) -> bool:
    expected = os.environ.get('REPORTING_API_KEY', '')
    return bool(expected) and hmac.compare_digest(req.headers.get('X-API-Key', ''), expected)


def _week_start(value: str | None) -> date:
    """Lundi de la semaine demandee ; semaine en cours (heure de Paris) par defaut."""
    d = date.fromisoformat(value) if value else datetime.now(PARIS).date()
    return d - timedelta(days=d.weekday())


def _load_report(week_start: date):
    data = fetch_planning_data(os.environ['CORE_URL'], os.environ['CORE_SERVICE_KEY'], week_start)
    return build_report(data)


@app.route(route='health', methods=['GET'])
def health(req: func.HttpRequest):
    return _json({'service': 'reporting', 'status': 'ok'})


@app.route(route='reports/planning', methods=['GET'])
def planning_pdf(req: func.HttpRequest):
    if not _authorized(req):
        return _json({'detail': 'Cle API invalide ou absente.'}, status=401)
    try:
        week_start = _week_start(req.params.get('week_start'))
    except ValueError:
        return _json({'detail': 'week_start invalide (AAAA-MM-JJ).'}, status=400)
    try:
        report = _load_report(week_start)
    except CoreUnavailable as exc:
        logging.error('PDF %s impossible : %s', week_start, exc)
        return _json({'detail': 'Donnees du Core indisponibles.'}, status=502)

    pdf = render_planning_pdf(report)
    logging.info('PDF semaine %s : %d creneaux, %d octets', week_start, len(report.shifts), len(pdf))
    return func.HttpResponse(
        pdf, status_code=200, mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="planning-{week_start}.pdf"'},
    )


def _run_weekly(week_start: date) -> dict:
    report = _load_report(week_start)
    event = build_weekly_event(report)
    recipients = len(event['data']['recipients'])
    if recipients:
        publish(event, os.environ['EVENTS_STORAGE'], os.environ.get('NOTIFICATIONS_QUEUE', 'notification-events'))
    summary = {
        'week_start': week_start.isoformat(),
        'coverage_percent': event['data']['coverage_percent'],
        'understaffed': event['data']['understaffed_total'],
        'recipients': recipients,
        'published': bool(recipients),
    }
    logging.info('Synthese hebdomadaire : %s', summary)
    return summary


@app.timer_trigger(arg_name='timer', schedule='%WEEKLY_REPORT_SCHEDULE%', run_on_startup=False)
def weekly_report(timer: func.TimerRequest):
    # Une exception laisse Functions journaliser l'echec ; la prochaine
    # execution aura lieu lundi suivant (ou a la demande via /weekly/run).
    _run_weekly(_week_start(None))


@app.route(route='reports/weekly/run', methods=['POST'])
def weekly_run(req: func.HttpRequest):
    if not _authorized(req):
        return _json({'detail': 'Cle API invalide ou absente.'}, status=401)
    try:
        week_start = _week_start(req.params.get('week_start'))
    except ValueError:
        return _json({'detail': 'week_start invalide (AAAA-MM-JJ).'}, status=400)
    try:
        return _json(_run_weekly(week_start))
    except CoreUnavailable as exc:
        logging.error('Synthese %s impossible : %s', week_start, exc)
        return _json({'detail': 'Donnees du Core indisponibles.'}, status=502)
