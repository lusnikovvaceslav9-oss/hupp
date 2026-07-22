"""Yandex Metrika Reporting API — visits, users, goal reaches by day."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

STAT_URL = "https://api-metrika.yandex.net/stat/v1/data"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"OAuth {token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=120, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        body = err.read()[:400].decode("utf-8", errors="replace")
        raise RuntimeError(f"Metrika HTTP {err.code}: {body}") from err


def _chunk_range(date_since: date, date_until: date, chunk_days: int = 90):
    d = date_since
    while d <= date_until:
        e = min(d + timedelta(days=chunk_days - 1), date_until)
        yield d, e
        d = e + timedelta(days=1)


def fetch_metrics_by_day(
    token: str,
    counter_id: str | int,
    date_since: date,
    date_until: date,
    *,
    goals: list[dict] | None = None,
) -> dict[str, dict[str, int]]:
    """
    Day → {visits, users, <goal.key>: reaches, ...}.

    `goals` items: {id, key} — key becomes the field name in the result.
    """
    goals = [g for g in (goals or []) if g and g.get("id") and g.get("key")]
    # Metrika allows limited metrics per call — chunk goals by 5.
    base_out: dict[str, dict[str, int]] = {}

    def ensure_day(day: str) -> dict[str, int]:
        row = base_out.get(day)
        if row is None:
            row = {"visits": 0, "users": 0}
            for g in goals:
                row[str(g["key"])] = 0
            base_out[day] = row
        return row

    # First pass: visits + users alone (stable).
    for start, end in _chunk_range(date_since, date_until):
        params = {
            "ids": str(counter_id),
            "metrics": "ym:s:visits,ym:s:users",
            "dimensions": "ym:s:date",
            "date1": start.isoformat(),
            "date2": end.isoformat(),
            "accuracy": "full",
            "limit": 10000,
        }
        url = f"{STAT_URL}?{urllib.parse.urlencode(params)}"
        payload = _get_json(url, token)
        for row in payload.get("data") or []:
            dims = row.get("dimensions") or []
            mets = row.get("metrics") or []
            if not dims:
                continue
            day = str(dims[0].get("name") or "")[:10]
            if len(day) != 10 or day[4] != "-":
                continue
            prev = ensure_day(day)
            prev["visits"] += int(float(mets[0])) if len(mets) > 0 else 0
            prev["users"] += int(float(mets[1])) if len(mets) > 1 else 0

    # Goal batches.
    batch_size = 5
    for i in range(0, len(goals), batch_size):
        batch = goals[i : i + batch_size]
        metric_names = [f"ym:s:goal{g['id']}reaches" for g in batch]
        for start, end in _chunk_range(date_since, date_until):
            params = {
                "ids": str(counter_id),
                "metrics": ",".join(metric_names),
                "dimensions": "ym:s:date",
                "date1": start.isoformat(),
                "date2": end.isoformat(),
                "accuracy": "full",
                "limit": 10000,
            }
            url = f"{STAT_URL}?{urllib.parse.urlencode(params)}"
            payload = _get_json(url, token)
            for row in payload.get("data") or []:
                dims = row.get("dimensions") or []
                mets = row.get("metrics") or []
                if not dims:
                    continue
                day = str(dims[0].get("name") or "")[:10]
                if len(day) != 10 or day[4] != "-":
                    continue
                prev = ensure_day(day)
                for j, g in enumerate(batch):
                    if len(mets) > j:
                        prev[str(g["key"])] += int(float(mets[j]))

    return base_out
