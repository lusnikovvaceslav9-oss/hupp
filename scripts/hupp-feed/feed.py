"""Orchestrate Hupp feed: Direct spend + Metrika visits/goals."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from cohort import analyze_cohort_from_daily, default_anchor
from daily import EXTRA_INT_KEYS, estimate_today_spend, load_daily_csv, merge_daily, write_daily_csv
from direct import fetch_direct_by_day
from metrika import fetch_metrics_by_day
from secrets import load_secrets


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def _goals_from_config(cfg: dict) -> list[dict]:
    goals = cfg.get("goals")
    if isinstance(goals, list) and goals:
        out = []
        for g in goals:
            if not g:
                continue
            gid = str(g.get("id") or "").strip()
            key = str(g.get("key") or "").strip()
            if not gid or not key:
                continue
            out.append(
                {
                    "id": gid,
                    "key": key,
                    "label": g.get("label") or key,
                    "csv": g.get("csv") or key,
                }
            )
        return out
    # Backward-compatible fallback
    legacy = []
    mapping = [
        ("metrika_goal_id", "reach_pay", "trials", "клик «Получить/Оплатить» → скролл к форме"),
        ("metrika_goal_id_secondary", "view_pay", "fb", "карточка оплаты на экране"),
        ("metrika_goal_id_tertiary", "pay_submit", "sold", "нажал «Оплатить» → ЮKassa"),
    ]
    for cfg_key, key, csv_col, label in mapping:
        gid = cfg.get(cfg_key)
        if gid:
            legacy.append({"id": str(gid), "key": key, "csv": csv_col, "label": label})
    return legacy


def run_feed(work_dir: Path, config_path: Path | None = None) -> int:
    work_dir = work_dir.resolve()
    cfg_path = config_path or (work_dir / "config" / "hupp.json")
    if not cfg_path.is_file():
        cfg_path = Path(__file__).resolve().parent / "config" / "hupp.json"
    cfg = load_config(cfg_path)

    secrets = load_secrets(work_dir)
    anchor = date.fromisoformat(cfg.get("anchor") or default_anchor().isoformat())
    until = datetime.now(ZoneInfo("Europe/Moscow")).date()
    refresh_days = int(cfg.get("refresh_days") or 14)
    lag = int(cfg.get("attribution_lag_days") or 2)
    window_start = max(anchor, until - timedelta(days=refresh_days + lag))

    daily_path = work_dir / cfg.get("daily_csv", "data/hupp-daily.csv")
    cohort_path = work_dir / cfg.get("cohort_json", "data/hupp-cohort.json")
    meta_path = work_dir / cfg.get("meta_json", "data/hupp-meta.json")

    existing = load_daily_csv(daily_path)
    old_goals_total = sum(int(v.get("trials") or 0) for v in existing.values())

    spend: dict[str, float] = {}
    clicks: dict[str, int] = {}
    impressions: dict[str, int] = {}
    visits: dict[str, int] = {}
    goal_series: dict[str, dict[str, int]] = {}
    sources: dict[str, str] = {}
    errors: list[str] = []
    goals_cfg = _goals_from_config(cfg)

    def _split_direct(raw: dict[str, dict]) -> tuple[dict[str, float], dict[str, int], dict[str, int]]:
        sp: dict[str, float] = {}
        cl: dict[str, int] = {}
        im: dict[str, int] = {}
        for day, vals in raw.items():
            sp[day] = float(vals.get("spend") or 0)
            cl[day] = int(vals.get("clicks") or 0)
            im[day] = int(vals.get("impressions") or 0)
        return sp, cl, im

    def _fetch_direct_range(date_since: date, date_until: date, *, chunk_days: int = 10) -> dict[str, dict]:
        out: dict[str, dict] = {}
        d = date_since
        while d <= date_until:
            e = min(d + timedelta(days=chunk_days - 1), date_until)
            part = fetch_direct_by_day(direct_token, client_login, d, e)
            out.update(part)
            d = e + timedelta(days=1)
        return out

    direct_token = secrets.get("DIRECT_OAUTH_TOKEN")
    client_login = secrets.get("DIRECT_CLIENT_LOGIN") or cfg.get("direct_client_login") or ""
    if direct_token:
        try:
            direct_win = _fetch_direct_range(window_start, until)
            spend, clicks, impressions = _split_direct(direct_win)
            sources["spend"] = "direct_api"
            sources["clicks"] = "direct_api"
            sources["impressions"] = "direct_api"
            print(f"  Direct: {len(spend)} days (spend+clicks+impressions)")
        except Exception as exc:
            errors.append(f"direct: {exc}")
            print(f"  Direct failed: {exc}")
    else:
        errors.append("direct: DIRECT_OAUTH_TOKEN missing")

    metrika_token = secrets.get("METRIKA_OAUTH_TOKEN")
    counter_id = secrets.get("METRIKA_COUNTER_ID") or cfg.get("metrika_counter_id") or ""

    if metrika_token and counter_id:
        try:
            metrika = fetch_metrics_by_day(
                metrika_token,
                counter_id,
                anchor,
                until,
                goals=goals_cfg,
            )
            for day, vals in metrika.items():
                visits[day] = int(vals.get("visits") or 0)
                for g in goals_cfg:
                    key = g["key"]
                    goal_series.setdefault(key, {})[day] = int(vals.get(key) or 0)
            sources["visits"] = "metrika_stat"
            sources["installs"] = "metrika_visits"
            for g in goals_cfg:
                sources[g["key"]] = f"metrika_{g['key']}_{g['id']}"
            parts = [f"visits={sum(visits.values())}"]
            for g in goals_cfg:
                parts.append(f"{g['key']}={sum(goal_series.get(g['key'], {}).values())}")
            print(f"  Metrika: {len(visits)} days · " + " · ".join(parts))
        except Exception as exc:
            errors.append(f"metrika: {exc}")
            print(f"  Metrika failed: {exc}")
    else:
        if not metrika_token:
            errors.append("metrika: METRIKA_OAUTH_TOKEN missing")
        if not counter_id:
            errors.append("metrika: METRIKA_COUNTER_ID missing")

    full_spend, full_clicks, full_impressions = spend, clicks, impressions
    if anchor < window_start and direct_token:
        try:
            direct_full = _fetch_direct_range(anchor, until)
            full_spend, full_clicks, full_impressions = _split_direct(direct_full)
            ws = window_start.isoformat()
            for day_key, value in spend.items():
                if day_key >= ws:
                    full_spend[day_key] = value
                    full_clicks[day_key] = clicks.get(day_key, 0)
                    full_impressions[day_key] = impressions.get(day_key, 0)
            print(f"  Direct full range: {len(full_spend)} days")
        except Exception as exc:
            errors.append(f"direct_full: {exc}")
            print(f"  Direct full range failed: {exc}")

    if sources.get("visits") == "metrika_stat":
        d = anchor
        while d <= until:
            key = d.isoformat()
            visits.setdefault(key, 0)
            for g in goals_cfg:
                goal_series.setdefault(g["key"], {}).setdefault(key, 0)
            d += timedelta(days=1)

    # Map goal keys → CSV columns
    by_csv: dict[str, dict[str, int]] = {}
    for g in goals_cfg:
        by_csv[g["csv"]] = goal_series.get(g["key"], {})

    extras = {
        k: by_csv.get(k, {})
        for k in EXTRA_INT_KEYS
    }

    merged = merge_daily(
        existing,
        spend=full_spend,
        installs=visits,
        trials=by_csv.get("trials", {}),
        bills=by_csv.get("fb", {}),
        sold=by_csv.get("sold", {}),
        clicks=full_clicks,
        impressions=full_impressions,
        extras=extras,
        anchor=anchor,
        until=until,
    )
    spend_today_estimated = estimate_today_spend(merged, until)
    if spend_today_estimated:
        print(f"  Direct: estimated spend for {until.isoformat()} from recent CPV")
    write_daily_csv(daily_path, merged)
    print(f"  Daily CSV: {daily_path} ({len(merged)} days)")

    new_goals_total = sum(int(v.get("trials") or 0) for v in merged.values())

    # Minimal cohort stub (UI когорты отключены)
    daily_for_cohort = {
        k: {
            "spend": v.get("spend", 0),
            "installs": v.get("installs", 0),
            "trials": v.get("trials", 0),
        }
        for k, v in merged.items()
    }
    cohort = analyze_cohort_from_daily(
        anchor=anchor,
        until=until,
        report_date=until,
        daily=daily_for_cohort,
        paid_by_cohort_day={},
        sold_by_cohort_day={},
        trial_starts=None,
    )
    cohort_path.parent.mkdir(parents=True, exist_ok=True)
    cohort_path.write_text(json.dumps(cohort, indent=2, ensure_ascii=False), encoding="utf-8")

    visits_total = sum(int(v.get("installs") or 0) for v in merged.values())
    spend_total = sum(float(v.get("spend") or 0) for v in merged.values())
    totals = {
        "spend": round(spend_total, 2),
        "visits": visits_total,
    }
    for g in goals_cfg:
        csv_col = g["csv"]
        if csv_col == "trials":
            field = "trials"
        elif csv_col == "fb":
            field = "fb"
        elif csv_col == "sold":
            field = "sold"
        else:
            field = csv_col
        totals[g["key"]] = sum(int(v.get(field) or 0) for v in merged.values())

    meta = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "project": "hupp",
        "anchor": anchor.isoformat(),
        "until": until.isoformat(),
        "window_start": window_start.isoformat(),
        "metric_map": {
            "installs": "metrika_visits",
            "trials": "reach_pay",
            "fb": "view_pay",
            "sold": "pay_submit",
            "purchase": "purchase",
            "contact_info": "contact_info",
            "form_submit": "form_submit",
            "contact_sent": "contact_sent",
            "spend": "direct_cost_no_vat",
        },
        "goals": goals_cfg,
        "sources": sources,
        "errors": errors,
        "days": len(merged),
        "totals": totals,
        "reconcile_diff": {
            "reach_pay_old": old_goals_total,
            "reach_pay_new": new_goals_total,
            "delta": new_goals_total - old_goals_total,
        },
        "metrika_counter_id": str(counter_id) if counter_id else None,
    }
    if spend_today_estimated:
        meta["spend_today_estimated"] = True
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Meta JSON: {meta_path}")
    if errors:
        print(f"  Warnings: {errors}")

    return 0 if merged else 1
