from fastapi.testclient import TestClient

from app.main import app

from .factories import request, shift, staff

client = TestClient(app)
KEY = {'X-API-Key': 'test-key'}


def test_health_is_public():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['service'] == 'engine'


def test_solve_requires_api_key():
    body = request([shift(1)], [staff(10)])
    assert client.post('/v1/solve', json=body).status_code == 401
    assert client.post('/v1/solve', json=body, headers={'X-API-Key': 'mauvaise'}).status_code == 401


def test_solve_returns_assignments():
    body = request([shift(1), shift(2, day=1)], [staff(10), staff(11)])
    r = client.post('/v1/solve', json=body, headers=KEY)
    assert r.status_code == 200
    data = r.json()
    assert {a['shift_id'] for a in data['assignments']} == {1, 2}
    assert data['unfilled_shift_ids'] == []
    assert set(data['score_detail']) >= {'workload', 'preference', 'care_continuity'}


def test_invalid_payload_is_rejected():
    body = request([shift(1)], [staff(10)])
    body['week_end'] = '2026-11-01'  # avant week_start
    assert client.post('/v1/solve', json=body, headers=KEY).status_code == 422
