from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import create_app
from app.mis.routes import (
    build_errors_pipeline,
    build_fallback_pipeline,
    build_ip_pipeline,
    build_tps_pipeline,
    build_usage_pipeline,
)


class AggregateCollection:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.pipelines = []

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        return iter(self.results)


class TestConfig:
    TESTING = True
    MONGO_URI = "mongodb://localhost:27017"
    MONGO_DB_NAME = "mis_test"
    SECRET_KEY = "test"
    ADMIN_API_KEY = "admin-key"
    DEFAULT_TPS_LIMIT = 5
    TRUSTED_PROXY_IPS = ["127.0.0.1"]
    TRUST_XFF_HEADER_DEV_ONLY = True
    EMERGENCY_LOG_PATH = "logs/test.jsonl"


@pytest.fixture
def mis_client():
    app = create_app(TestConfig)
    logs = AggregateCollection()
    app.extensions["mongo_db"] = {"api_logs": logs}
    return app.test_client(), logs


def admin_headers():
    return {"X-Admin-Key": "admin-key"}


def test_missing_admin_key_uses_uniform_error_envelope(mis_client):
    client, _ = mis_client
    response = client.get("/api/v1/mis/usage?from=2026-07-01&to=2026-07-02")
    assert response.status_code == 401
    body = response.get_json()
    assert body["status"] == "FAILED"
    assert body["error_code"] == "VP4001"
    assert body["request_id"].startswith("req_")


def test_invalid_date_range_uses_vp4022(mis_client):
    client, _ = mis_client
    response = client.get(
        "/api/v1/mis/usage?from=2026-07-03&to=2026-07-01",
        headers=admin_headers(),
    )
    assert response.status_code == 422
    assert response.get_json()["error_code"] == "VP4022"


def test_usage_route_formats_client_aggregation_result(mis_client):
    client, logs = mis_client
    logs.results = [
        {
            "_id": "alphabank",
            "total": 5,
            "success": 3,
            "success_via_fallback": 1,
            "not_verified": 1,
            "failed": 1,
            "avg_latency_ms": 210.555,
        }
    ]
    response = client.get(
        "/api/v1/mis/usage?from=2026-07-01&to=2026-07-07&group_by=client",
        headers=admin_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == [
        {
            "client_id": "alphabank",
            "total": 5,
            "success": 3,
            "success_via_fallback": 1,
            "not_verified": 1,
            "failed": 1,
            "avg_latency_ms": 210.56,
        }
    ]
    assert logs.pipelines[-1][0]["$match"]["created_at"]["$gte"] == datetime(
        2026, 7, 1, tzinfo=timezone.utc
    )


def test_usage_csv_has_headers_even_when_no_rows(mis_client):
    client, logs = mis_client
    logs.results = []
    response = client.get(
        "/api/v1/mis/usage?from=2026-07-01&to=2026-07-07&format=csv",
        headers=admin_headers(),
    )
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.get_data(as_text=True).startswith("client_id,user_id,day,total")
    assert "usage.csv" in response.headers["Content-Disposition"]


def test_errors_route_and_csv(mis_client):
    client, logs = mis_client
    logs.results = [{"_id": {"client_id": "zetafin", "error_code": "VP4029"}, "count": 3}]
    response = client.get(
        "/api/v1/mis/errors?from=2026-07-01&to=2026-07-07&format=csv",
        headers=admin_headers(),
    )
    assert response.status_code == 200
    assert "zetafin,VP4029,3" in response.get_data(as_text=True)


def test_fallback_route_returns_pipeline_result(mis_client):
    client, logs = mis_client
    logs.results = [
        {
            "client_id": "alphabank",
            "total_success": 100,
            "served_by_fallback": 5,
            "fallback_ratio_pct": 5.0,
        }
    ]
    response = client.get(
        "/api/v1/mis/fallback?from=2026-07-01&to=2026-07-07",
        headers=admin_headers(),
    )
    assert response.get_json()[0]["fallback_ratio_pct"] == 5.0


def test_ip_route_surfaces_blocked_non_whitelisted_address(mis_client):
    client, logs = mis_client
    logs.results = [
        {
            "client_id": "alphabank",
            "ip": "198.51.100.20",
            "total_hits": 4,
            "blocked_hits": 4,
            "whitelisted": False,
        }
    ]
    response = client.get(
        "/api/v1/mis/ips?client_id=alphabank&from=2026-07-01&to=2026-07-07",
        headers=admin_headers(),
    )
    assert response.get_json()[0] == logs.results[0]
    serialized_pipeline = repr(logs.pipelines[-1])
    assert "$lookup" in serialized_pipeline
    assert "whitelisted_ips" in serialized_pipeline


def test_tps_route_formats_peak_and_percentile(mis_client):
    client, logs = mis_client
    logs.results = [
        {
            "seconds": [{"_id": datetime(2026, 7, 5, 14, 3, 22, tzinfo=timezone.utc), "count": 9}],
            "summary": [{"total": 207360, "p95_latency_ms": [480.4]}],
        }
    ]
    response = client.get(
        "/api/v1/mis/tps?client_id=alphabank&date=2026-07-05",
        headers=admin_headers(),
    )
    assert response.get_json() == {
        "peak_tps": 9,
        "peak_second": "2026-07-05T14:03:22Z",
        "avg_tps": 2.4,
        "p95_latency_ms": 480.4,
    }
    assert "$percentile" in repr(logs.pipelines[-1])


def test_pipeline_builders_use_required_aggregation_stages():
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = datetime(2026, 7, 8, tzinfo=timezone.utc)
    assert [next(iter(stage)) for stage in build_usage_pipeline(start, end, "user", None)] == [
        "$match",
        "$group",
        "$sort",
    ]
    assert "$group" in build_errors_pipeline(start, end, None)[1]
    assert "$project" in build_fallback_pipeline(start, end)[2]
    assert "$lookup" in build_ip_pipeline(start, end, "alphabank")[2]
    assert "$facet" in build_tps_pipeline("alphabank", start, end)[1]
