"""
Historique des notifications : la base propre du service.

Azure Table Storage, dans le compte de stockage deja requis par Functions
(cout quasi nul ; en local, emule par Azurite). Une ligne par couple
(evenement, destinataire) : c'est aussi ce qui rend le traitement idempotent,
un evenement rejoue ne renvoie pas un e-mail deja parti.
"""

import hashlib
from datetime import datetime, timezone

TABLE_NAME = 'notifications'


def _keys(event_id, email):
    return event_id, hashlib.sha256(email.strip().lower().encode()).hexdigest()[:24]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class TableStore:
    def __init__(self, connection_string, table_name=TABLE_NAME):
        from azure.data.tables import TableServiceClient
        service = TableServiceClient.from_connection_string(connection_string)
        self.table = service.create_table_if_not_exists(table_name)

    def get(self, event_id, email):
        from azure.core.exceptions import ResourceNotFoundError
        pk, rk = _keys(event_id, email)
        try:
            return dict(self.table.get_entity(partition_key=pk, row_key=rk))
        except ResourceNotFoundError:
            return None

    def save(self, record):
        pk, rk = _keys(record['event_id'], record['recipient'])
        self.table.upsert_entity({'PartitionKey': pk, 'RowKey': rk, **record})

    def list_recent(self, limit=50):
        rows = [dict(e) for e in self.table.list_entities()]
        rows.sort(key=lambda r: r.get('updated_at', ''), reverse=True)
        return [_public(r) for r in rows[:limit]]


class MemoryStore:
    """Meme interface, en memoire : pour les tests."""

    def __init__(self):
        self.rows = {}

    def get(self, event_id, email):
        return self.rows.get(_keys(event_id, email))

    def save(self, record):
        self.rows[_keys(record['event_id'], record['recipient'])] = dict(record)

    def list_recent(self, limit=50):
        rows = sorted(self.rows.values(), key=lambda r: r.get('updated_at', ''), reverse=True)
        return [_public(r) for r in rows[:limit]]


def _public(row):
    return {k: v for k, v in row.items() if k not in ('PartitionKey', 'RowKey', 'etag', 'Timestamp')}
