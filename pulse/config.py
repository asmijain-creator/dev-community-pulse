"""All settings come from environment variables (Vercel project settings, or .env locally)."""
import os
from dataclasses import dataclass
from functools import lru_cache

try:  # local development only; on Vercel the variables are already in the environment
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_key: str
    gemini_api_key: str
    gemini_model: str
    resend_api_key: str
    digest_email_to: str
    digest_email_from: str
    cron_secret: str
    admin_password: str
    github_token: str
    stackexchange_key: str
    app_url: str                 # public dashboard URL, linked from the email
    lookback_days: int           # length of one reporting week
    max_posts_per_query: int     # per keyword, per source
    max_classify_per_run: int    # cap on Gemini work per run (time + cost guard)
    classify_batch_size: int

    def missing(self) -> list[str]:
        """Required settings that are not set, for a clear error instead of a stack trace."""
        required = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_SERVICE_ROLE_KEY": self.supabase_service_key,
            "GEMINI_API_KEY": self.gemini_api_key,
        }
        return [name for name, value in required.items() if not value]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        resend_api_key=os.getenv("RESEND_API_KEY", ""),
        digest_email_to=os.getenv("DIGEST_EMAIL_TO", ""),
        digest_email_from=os.getenv("DIGEST_EMAIL_FROM", "Community Pulse <onboarding@resend.dev>"),
        cron_secret=os.getenv("CRON_SECRET", ""),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        stackexchange_key=os.getenv("STACKEXCHANGE_KEY", ""),
        app_url=os.getenv("APP_URL") or (
            f"https://{os.environ['VERCEL_PROJECT_PRODUCTION_URL']}"
            if os.getenv("VERCEL_PROJECT_PRODUCTION_URL") else ""
        ),
        lookback_days=_int("LOOKBACK_DAYS", 7),
        max_posts_per_query=_int("MAX_POSTS_PER_QUERY", 15),
        max_classify_per_run=_int("MAX_CLASSIFY_PER_RUN", 240),
        classify_batch_size=_int("CLASSIFY_BATCH_SIZE", 30),
    )
