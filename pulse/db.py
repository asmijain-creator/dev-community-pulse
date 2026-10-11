"""All Supabase access in one place (service-role key, server side only)."""
from collections import Counter
from datetime import datetime, timedelta, timezone

from supabase import Client, create_client

RUN_LOCK_MINUTES = 10
CHUNK = 200  # rows per upsert request


def _chunks(rows: list, size: int = CHUNK):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


class Store:
    def __init__(self, url: str, key: str):
        self.sb: Client = create_client(url, key)

    # ---------- topics ----------
    def active_topics(self) -> list[dict]:
        return self.sb.table("topics").select("*").eq("active", True).order("id").execute().data

    def all_topics(self) -> list[dict]:
        return self.sb.table("topics").select("*").order("id").execute().data

    def add_topic(self, category: str, description: str, keywords: list[str]) -> None:
        self.sb.table("topics").insert(
            {"category": category, "description": description, "keywords": keywords}
        ).execute()

    def update_topic(self, topic_id: int, **fields) -> None:
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.sb.table("topics").update(fields).eq("id", topic_id).execute()

    # ---------- runs (log + lock) ----------
    def start_run(self, trigger: str) -> int | None:
        """Returns a run id, or None if another run started in the last few minutes."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=RUN_LOCK_MINUTES)).isoformat()
        busy = (self.sb.table("runs").select("id").eq("status", "running")
                .gte("started_at", cutoff).limit(1).execute().data)
        if busy:
            self.sb.table("runs").insert({"trigger": trigger, "status": "skipped",
                                          "finished_at": datetime.now(timezone.utc).isoformat(),
                                          "error": f"run {busy[0]['id']} already in progress"}).execute()
            return None
        return self.sb.table("runs").insert({"trigger": trigger}).execute().data[0]["id"]

    def finish_run(self, run_id: int, status: str, stats: dict, error: str | None = None) -> None:
        self.sb.table("runs").update({
            "status": status, "stats": stats, "error": error,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()

    def recent_runs(self, limit: int = 8) -> list[dict]:
        return self.sb.table("runs").select("*").order("started_at", desc=True).limit(limit).execute().data

    # ---------- posts ----------
    def upsert_posts(self, rows: list[dict]) -> None:
        for chunk in _chunks(rows):
            self.sb.table("posts").upsert(chunk, on_conflict="id").execute()

    def unclassified_posts(self, since: datetime, limit: int) -> list[dict]:
        return (self.sb.table("posts")
                .select("id,source,title,body,is_answered,score,comments")
                .is_("classified_at", "null").gte("created_at", since.isoformat())
                .order("comments", desc=True).order("score", desc=True)
                .limit(limit).execute().data)

    def save_labels(self, labels: dict[str, dict], errors: dict[str, str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        rows = [{"id": pid, **fields, "classified_at": now, "classify_error": None} for pid, fields in labels.items()]
        for chunk in _chunks(rows):
            self.sb.table("posts").upsert(chunk, on_conflict="id").execute()
        err_rows = [{"id": pid, "classify_error": msg} for pid, msg in errors.items()]
        for chunk in _chunks(err_rows):
            self.sb.table("posts").upsert(chunk, on_conflict="id").execute()

    def known_labels(self, since: datetime) -> list[str]:
        """Pain-point labels used recently, most frequent first, so Gemini reuses them."""
        rows = (self.sb.table("posts").select("pain_point").eq("relevant", True)
                .gte("created_at", since.isoformat()).limit(2000).execute().data)
        counts = Counter(r["pain_point"] for r in rows if r["pain_point"])
        return [label for label, _ in counts.most_common()]

    def pain_point_trends(self, cur_start: datetime, end: datetime) -> list[dict]:
        return self.sb.rpc("pain_point_trends", {
            "p_cur_start": cur_start.isoformat(), "p_end": end.isoformat(),
        }).execute().data

    def examples(self, start: datetime, end: datetime, pain_points: list[str], per_point: int = 3) -> dict[str, list[dict]]:
        if not pain_points:
            return {}
        rows = (self.sb.table("posts")
                .select("source,title,url,summary,is_unresolved,score,comments,pain_point")
                .in_("pain_point", pain_points).eq("relevant", True)
                .gte("created_at", start.isoformat()).lt("created_at", end.isoformat())
                .order("comments", desc=True).limit(500).execute().data)
        out: dict[str, list[dict]] = {}
        for r in rows:
            bucket = out.setdefault(r.pop("pain_point"), [])
            if len(bucket) < per_point:
                bucket.append(r)
        return out

    # ---------- digests ----------
    def save_digest(self, period_start, period_end, content_md: str, stats: dict, metrics: list[dict]) -> None:
        key = period_end.isoformat()
        self.sb.table("digests").upsert({
            "period_end": key, "period_start": period_start.isoformat(),
            "content_md": content_md, "stats": stats,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="period_end").execute()
        self.sb.table("digest_metrics").delete().eq("period_end", key).execute()
        rows = [{"period_end": key, **m} for m in metrics]
        for chunk in _chunks(rows):
            self.sb.table("digest_metrics").insert(chunk).execute()

    def latest_digest(self) -> dict | None:
        rows = self.sb.table("digests").select("*").order("period_end", desc=True).limit(1).execute().data
        return rows[0] if rows else None

    def get_digest(self, period_end: str) -> dict | None:
        rows = self.sb.table("digests").select("*").eq("period_end", period_end).limit(1).execute().data
        return rows[0] if rows else None

    def list_digests(self, limit: int = 52) -> list[dict]:
        return (self.sb.table("digests").select("period_start,period_end,stats,created_at")
                .order("period_end", desc=True).limit(limit).execute().data)

    def digest_metrics(self, period_end: str) -> list[dict]:
        return (self.sb.table("digest_metrics").select("*").eq("period_end", period_end)
                .order("mentions", desc=True).execute().data)

    def metric_history(self, pain_points: list[str], limit_rows: int = 500) -> list[dict]:
        if not pain_points:
            return []
        return (self.sb.table("digest_metrics").select("period_end,pain_point,mentions")
                .in_("pain_point", pain_points).order("period_end").limit(limit_rows).execute().data)
