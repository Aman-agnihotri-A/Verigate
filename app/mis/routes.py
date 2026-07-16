"""Admin-protected MIS endpoints backed by MongoDB aggregation pipelines."""
from __future__ import annotations

import csv
import io
from datetime import datetime, time, timedelta, timezone
from functools import wraps
from uuid import uuid4

from flask import Blueprint, Response, current_app, jsonify, request

from app.responses import error_response

mis_bp = Blueprint("mis", __name__)

_USAGE_FIELDS = [
    "client_id",
    "user_id",
    "day",
    "total",
    "success",
    "success_via_fallback",
    "not_verified",
    "failed",
    "avg_latency_ms",
]
_ERROR_FIELDS = ["client_id", "error_code", "count"]


def _request_id() -> str:
    return "req_" + uuid4().hex[:12]


def _validation_error(message: str):
    return jsonify(error_response(_request_id(), "VP4022", message)), 422


def require_admin(function):
    """Require the configured admin key for every MIS endpoint."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        configured_key = current_app.config.get("ADMIN_API_KEY")
        supplied_key = request.headers.get("X-Admin-Key")
        if not configured_key or supplied_key != configured_key:
            return (
                jsonify(
                    error_response(
                        _request_id(),
                        "VP4001",
                        "Missing or invalid admin key",
                    )
                ),
                401,
            )
        return function(*args, **kwargs)

    return wrapped


def _parse_date(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD)") from exc
    return datetime.combine(parsed, time.min, tzinfo=timezone.utc)


def _date_range() -> tuple[datetime, datetime]:
    if "from" not in request.args or "to" not in request.args:
        raise ValueError("from and to date parameters are required")
    start = _parse_date(request.args["from"], "from")
    inclusive_to = _parse_date(request.args["to"], "to")
    if start > inclusive_to:
        raise ValueError("from must be earlier than or equal to to")
    return start, inclusive_to + timedelta(days=1)


def _csv_response(rows: list[dict], fields: list[str], filename: str) -> Response:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def build_usage_pipeline(
    start: datetime,
    end: datetime,
    group_by: str,
    client_id: str | None,
) -> list[dict]:
    """Build the client/user/day usage aggregation pipeline."""
    group_ids = {
        "client": "$client_id",
        "user": {"client_id": "$client_id", "user_id": "$user_id"},
        "day": {
            "client_id": "$client_id",
            "day": {
                "$dateToString": {
                    "format": "%Y-%m-%d",
                    "date": "$created_at",
                    "timezone": "UTC",
                }
            },
        },
    }
    if group_by not in group_ids:
        raise ValueError("group_by must be client, user, or day")

    match: dict = {"created_at": {"$gte": start, "$lt": end}}
    if client_id:
        match["client_id"] = client_id

    return [
        {"$match": match},
        {
            "$group": {
                "_id": group_ids[group_by],
                "total": {"$sum": 1},
                "success": {
                    "$sum": {
                        "$cond": [
                            {"$in": ["$error_code", ["VP2000", "VP2001"]]},
                            1,
                            0,
                        ]
                    }
                },
                "success_via_fallback": {
                    "$sum": {"$cond": [{"$eq": ["$error_code", "VP2001"]}, 1, 0]}
                },
                "not_verified": {
                    "$sum": {"$cond": [{"$eq": ["$error_code", "VP2002"]}, 1, 0]}
                },
                "failed": {
                    "$sum": {"$cond": [{"$gte": ["$http_status", 400]}, 1, 0]}
                },
                "avg_latency_ms": {"$avg": "$latency_ms"},
            }
        },
        {"$sort": {"_id": 1}},
    ]


def build_errors_pipeline(
    start: datetime,
    end: datetime,
    client_id: str | None,
) -> list[dict]:
    match: dict = {
        "created_at": {"$gte": start, "$lt": end},
        "http_status": {"$gte": 400},
    }
    if client_id:
        match["client_id"] = client_id
    return [
        {"$match": match},
        {
            "$group": {
                "_id": {"client_id": "$client_id", "error_code": "$error_code"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1, "_id.client_id": 1, "_id.error_code": 1}},
    ]


def build_fallback_pipeline(start: datetime, end: datetime) -> list[dict]:
    return [
        {
            "$match": {
                "created_at": {"$gte": start, "$lt": end},
                "error_code": {"$in": ["VP2000", "VP2001"]},
            }
        },
        {
            "$group": {
                "_id": "$client_id",
                "total_success": {"$sum": 1},
                "served_by_fallback": {
                    "$sum": {"$cond": ["$fallback_used", 1, 0]}
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "client_id": "$_id",
                "total_success": 1,
                "served_by_fallback": 1,
                "fallback_ratio_pct": {
                    "$round": [
                        {
                            "$multiply": [
                                {"$divide": ["$served_by_fallback", "$total_success"]},
                                100,
                            ]
                        },
                        2,
                    ]
                },
            }
        },
        {"$sort": {"client_id": 1}},
    ]


def build_ip_pipeline(
    start: datetime,
    end: datetime,
    client_id: str | None,
) -> list[dict]:
    """Build an IP report that compares attempts with each client's whitelist."""
    match: dict = {"created_at": {"$gte": start, "$lt": end}}
    if client_id:
        match["client_id"] = client_id
    return [
        {"$match": match},
        {
            "$group": {
                "_id": {"client_id": "$client_id", "ip": "$ip"},
                "total_hits": {"$sum": 1},
                "blocked_hits": {
                    "$sum": {"$cond": [{"$eq": ["$error_code", "VP4003"]}, 1, 0]}
                },
            }
        },
        {
            "$lookup": {
                "from": "clients",
                "localField": "_id.client_id",
                "foreignField": "client_id",
                "as": "client",
            }
        },
        {"$set": {"client": {"$first": "$client"}}},
        {
            "$project": {
                "_id": 0,
                "client_id": "$_id.client_id",
                "ip": "$_id.ip",
                "total_hits": 1,
                "blocked_hits": 1,
                "whitelisted": {
                    "$in": ["$_id.ip", {"$ifNull": ["$client.whitelisted_ips", []]}]
                },
            }
        },
        {"$sort": {"total_hits": -1, "client_id": 1, "ip": 1}},
    ]


def build_tps_pipeline(client_id: str, start: datetime, end: datetime) -> list[dict]:
    """Calculate peak-second TPS and percentile latency entirely in MongoDB."""
    return [
        {"$match": {"client_id": client_id, "created_at": {"$gte": start, "$lt": end}}},
        {
            "$facet": {
                "seconds": [
                    {
                        "$group": {
                            "_id": {
                                "$dateTrunc": {
                                    "date": "$created_at",
                                    "unit": "second",
                                    "timezone": "UTC",
                                }
                            },
                            "count": {"$sum": 1},
                        }
                    },
                    {"$sort": {"count": -1, "_id": 1}},
                    {"$limit": 1},
                ],
                "summary": [
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": 1},
                            "p95_latency_ms": {
                                "$percentile": {
                                    "input": "$latency_ms",
                                    "p": [0.95],
                                    "method": "approximate",
                                }
                            },
                        }
                    }
                ],
            }
        },
    ]


def _usage_rows(raw_rows: list[dict], group_by: str) -> list[dict]:
    rows: list[dict] = []
    for raw in raw_rows:
        row = dict(raw)
        identity = row.pop("_id")
        if isinstance(identity, dict):
            row.update(identity)
        elif group_by == "client":
            row["client_id"] = identity
        row["avg_latency_ms"] = round(row.get("avg_latency_ms") or 0, 2)
        rows.append(row)
    return rows


@mis_bp.get("/api/v1/mis/usage")
@require_admin
def usage():
    try:
        start, end = _date_range()
        group_by = request.args.get("group_by", "client")
        pipeline = build_usage_pipeline(
            start,
            end,
            group_by,
            request.args.get("client_id"),
        )
    except ValueError as exc:
        return _validation_error(str(exc))

    raw_rows = list(current_app.extensions["mongo_db"]["api_logs"].aggregate(pipeline))
    rows = _usage_rows(raw_rows, group_by)
    if request.args.get("format") == "csv":
        return _csv_response(rows, _USAGE_FIELDS, "usage.csv")
    return jsonify(rows)


@mis_bp.get("/api/v1/mis/errors")
@require_admin
def errors():
    try:
        start, end = _date_range()
    except ValueError as exc:
        return _validation_error(str(exc))

    pipeline = build_errors_pipeline(start, end, request.args.get("client_id"))
    raw_rows = current_app.extensions["mongo_db"]["api_logs"].aggregate(pipeline)
    rows = [{**row["_id"], "count": row["count"]} for row in raw_rows]
    if request.args.get("format") == "csv":
        return _csv_response(rows, _ERROR_FIELDS, "errors.csv")
    return jsonify(rows)


@mis_bp.get("/api/v1/mis/fallback")
@require_admin
def fallback():
    try:
        start, end = _date_range()
    except ValueError as exc:
        return _validation_error(str(exc))
    pipeline = build_fallback_pipeline(start, end)
    return jsonify(list(current_app.extensions["mongo_db"]["api_logs"].aggregate(pipeline)))


@mis_bp.get("/api/v1/mis/ips")
@require_admin
def ips():
    try:
        start, end = _date_range()
    except ValueError as exc:
        return _validation_error(str(exc))
    pipeline = build_ip_pipeline(start, end, request.args.get("client_id"))
    return jsonify(list(current_app.extensions["mongo_db"]["api_logs"].aggregate(pipeline)))


@mis_bp.get("/api/v1/mis/tps")
@require_admin
def tps():
    client_id = request.args.get("client_id", "").strip()
    date_value = request.args.get("date", "").strip()
    if not client_id or not date_value:
        return _validation_error("client_id and date are required")
    try:
        start = _parse_date(date_value, "date")
    except ValueError as exc:
        return _validation_error(str(exc))
    end = start + timedelta(days=1)

    pipeline = build_tps_pipeline(client_id, start, end)
    data = list(current_app.extensions["mongo_db"]["api_logs"].aggregate(pipeline))
    facet = data[0] if data else {"seconds": [], "summary": []}
    peak = facet.get("seconds", [])
    summary = facet.get("summary", [])

    peak_tps = peak[0]["count"] if peak else 0
    peak_second = (
        peak[0]["_id"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if peak
        else None
    )
    total = summary[0].get("total", 0) if summary else 0
    percentile = summary[0].get("p95_latency_ms", []) if summary else []
    p95_latency = round(percentile[0], 2) if percentile else 0

    return jsonify(
        {
            "peak_tps": peak_tps,
            "peak_second": peak_second,
            "avg_tps": round(total / 86400, 4),
            "p95_latency_ms": p95_latency,
        }
    )
