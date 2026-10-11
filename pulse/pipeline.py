"""The weekly job: collect -> label -> count -> write -> deliver."""
import time
from datetime import datetime, timedelta, timezone

from . import classifier, collector, emailer, writer
from .config import Settings, get_settings
from .db import Store
from .trends import build_metrics


class ConfigError(Exception):
    pass


async def run_digest(trigger: str, *, store: Store | None = None, settings: Settings | None = None,
                     now: datetime | None = None, collect=collector.collect,
                     classify=classifier.classify_posts, write=writer.write_brief,
                     send=emailer.send_brief) -> dict:
    settings = settings or get_settings()
    if missing := settings.missing():
        raise ConfigError(f"Missing environment variables: {', '.join(missing)}")
    store = store or Store(settings.supabase_url, settings.supabase_service_key)

    run_id = store.start_run(trigger)
    if run_id is None:
        return {"status": "skipped", "reason": "another run is already in progress"}

    started = time.monotonic()
    now = now or datetime.now(timezone.utc)
    week = timedelta(days=settings.lookback_days)
    cur_start, prev_start = now - week, now - 2 * week
    stats: dict = {"trigger": trigger}
    try:
        topics = store.active_topics()
        if not topics:
            store.finish_run(run_id, "skipped", stats, "No active topics. Add one on the Topics page.")
            return {"status": "skipped", "reason": "no active topics"}

        # 1. Collect two weeks, so the very first run already has a "last week" to compare with.
        keywords = [kw for t in topics for kw in t["keywords"]]
        posts, source_status = await collect(keywords, prev_start, settings)
        store.upsert_posts([p.to_row() for p in posts.values()])
        stats.update(source_status=source_status, posts_collected=len(posts))

        # 2. Label only posts we haven't labelled before (most-discussed first, capped per run).
        pending = store.unclassified_posts(prev_start, settings.max_classify_per_run)
        labels, errors = {}, {}
        if pending:
            labels, errors = await classify(
                settings.gemini_api_key, settings.gemini_model, pending, topics,
                store.known_labels(now - 4 * week), batch_size=settings.classify_batch_size,
            )
            store.save_labels(labels, errors)
        stats.update(newly_classified=len(labels), classify_errors=len(errors))

        # 3. Count and compare in SQL, label trends in code.
        new_categories = {
            t["category"] for t in topics
            if datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")) > cur_start
        }
        metrics = build_metrics(store.pain_point_trends(cur_start, now), new_categories)
        relevant_this_week = sum(m["mentions"] for m in metrics)
        stats["relevant_this_week"] = relevant_this_week

        # 4. Write the brief.
        top_points = [m["pain_point"] for m in metrics if m["mentions"] > 0][:8]
        examples = store.examples(cur_start, now, top_points)
        content = await write(settings.gemini_api_key, settings.gemini_model, cur_start.date(), now.date(),
                              metrics, examples, relevant_this_week, source_status)
        store.save_digest(cur_start.date(), now.date(), content, stats, metrics)

        # 5. Deliver. A failed email must not lose the brief: it is already saved for the dashboard.
        if settings.resend_api_key and settings.digest_email_to:
            try:
                stats["email_id"] = send(settings.resend_api_key, settings.digest_email_from,
                                         settings.digest_email_to,
                                         f"Developer Community Pulse · week ending {now.date()}",
                                         content, settings.app_url)
                stats["email"] = "sent"
            except Exception as exc:
                stats["email"] = f"failed: {exc}"[:300]
        else:
            stats["email"] = "not configured"

        stats["seconds"] = round(time.monotonic() - started, 1)
        store.finish_run(run_id, "success", stats)
        return {"status": "success", "period_end": now.date().isoformat(), **stats}
    except Exception as exc:
        stats["seconds"] = round(time.monotonic() - started, 1)
        store.finish_run(run_id, "failed", stats, f"{exc.__class__.__name__}: {exc}"[:1000])
        raise
