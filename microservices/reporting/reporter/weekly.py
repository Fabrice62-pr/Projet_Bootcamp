"""
Synthese hebdomadaire : publiee comme evenement "report.weekly" dans la file
du microservice Notifications, qui l'envoie aux chefs de service.
Reporting et Notifications communiquent ainsi sans passer par le Core.
"""

import json
import uuid
from datetime import datetime, timezone

from .stats import Report

MAX_LISTED = 20


def build_weekly_event(report: Report) -> dict:
    return {
        'id': str(uuid.uuid4()),
        'type': 'report.weekly',
        'version': 1,
        'occurred_at': datetime.now(timezone.utc).isoformat(),
        'source': 'reporting',
        'data': {
            'week_start': report.week_start.isoformat(),
            'week_end': report.week_end.isoformat(),
            'total_shifts': len(report.shifts),
            'total_assignments': report.total_assignments,
            'coverage_percent': round(report.coverage * 100),
            'understaffed': [
                {'start': s.start.isoformat(), 'shift_type': s.shift_type, 'service': s.service,
                 'care_unit': s.care_unit, 'assigned': s.assigned, 'min_staff': s.min_staff}
                for s in report.understaffed[:MAX_LISTED]
            ],
            'understaffed_total': len(report.understaffed),
            'overloaded': [
                {'name': p.name, 'hours': p.hours, 'max_hours': p.max_hours}
                for p in report.overloaded[:MAX_LISTED]
            ],
            'recipients': [
                {'email': m['email'], 'name': m.get('name', ''), 'service': m.get('service', '')}
                for m in report.managers if m.get('email')
            ],
        },
    }


def publish(event: dict, connection_string: str, queue_name: str) -> None:
    from azure.core.exceptions import ResourceExistsError
    from azure.storage.queue import QueueClient, TextBase64EncodePolicy

    client = QueueClient.from_connection_string(
        connection_string, queue_name, message_encode_policy=TextBase64EncodePolicy(),
    )
    try:
        client.create_queue()
    except ResourceExistsError:
        pass
    client.send_message(json.dumps(event, ensure_ascii=False))
