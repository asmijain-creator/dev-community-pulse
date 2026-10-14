"""SAMPLE DATA for the Building Now projects table prototype.

Every project, builder and link below is fictional and illustrative. Links point at example.com, a domain
reserved for documentation, so nothing here can be mistaken for real public evidence. The page labels this
data as a sample everywhere it is shown. Replace it by pointing lib/building_data.load_projects() at Supabase.

The records deliberately cover UI edge cases: a very long project name, missing builder details, unknown build
stages, no blocker information (None) versus none reported ([]), insufficient activity history, long focus
text, five-technology stacks and observations older than the default 30-day window.
"""
from typing import Literal, Optional, TypedDict

BuildStage = Literal["idea", "prototype", "mvp", "beta", "launched", "unknown"]
ActivityTrend = Literal["rising", "stable", "declining", "insufficient"]
EvidenceType = Literal["explicit", "inferred"]
EventType = Literal["project_announcement", "product_launch", "feature_update", "public_demo",
                    "repository_update", "technical_question", "reported_blocker"]


class Blocker(TypedDict):
    title: str
    category: str
    evidenceType: EvidenceType          # explicit = the builder said it; inferred = an AI suggestion
    excerpt: Optional[str]


class TimelineEvent(TypedDict):
    type: EventType
    title: str
    publishedAt: Optional[str]          # when the source was posted, if known
    collectedAt: str                    # when DevvIT observed it
    sourceUrl: Optional[str]
    excerpt: Optional[str]


class BuildingProject(TypedDict):
    id: str
    name: str
    description: str
    builderName: Optional[str]
    builderUsername: Optional[str]
    builderProfileUrl: Optional[str]
    category: str
    techStack: list[str]
    buildStage: BuildStage
    currentFocus: Optional[str]
    blockers: Optional[list[Blocker]]   # None = no blocker information; [] = checked, none reported
    activityTrend: ActivityTrend
    firstSeenAt: str
    lastObservedAt: str                 # latest observation of public evidence, not when work happened
    sourcePlatform: Optional[str]
    sourceUrl: Optional[str]
    projectUrl: Optional[str]
    repositoryUrl: Optional[str]
    isWatched: bool
    timeline: list[TimelineEvent]


AS_OF = "2026-10-14"                    # the sample's "today", so relative dates stay stable
_S = "https://example.com/sample"       # placeholder links only


def _ev(type_: EventType, title: str, published: Optional[str], collected: str, slug: str,
        excerpt: Optional[str] = None) -> TimelineEvent:
    return {"type": type_, "title": title, "publishedAt": published, "collectedAt": collected,
            "sourceUrl": f"{_S}/{slug}", "excerpt": excerpt}


PROJECTS: list[BuildingProject] = [
    {
        "id": "s-lintwise", "name": "Lintwise",
        "description": "Groups noisy AI code-review comments into one summary per pull request.",
        "builderName": "Priya N.", "builderUsername": "priyabuilds", "builderProfileUrl": f"{_S}/u/priyabuilds",
        "category": "AI tools", "techStack": ["Python", "FastAPI", "PostgreSQL", "LLM API"],
        "buildStage": "beta", "currentFocus": "Cutting false-positive comments on diffs over 1,000 lines.",
        "blockers": [
            {"title": "Model output varies between runs", "category": "AI reliability", "evidenceType": "explicit",
             "excerpt": "the same diff gets different comments on every run"},
            {"title": "Rate limits on the review API", "category": "API integration", "evidenceType": "inferred",
             "excerpt": None},
        ],
        "activityTrend": "rising", "firstSeenAt": "2026-08-30", "lastObservedAt": "2026-10-12",
        "sourcePlatform": "Hacker News", "sourceUrl": f"{_S}/hn/lintwise", "projectUrl": f"{_S}/lintwise",
        "repositoryUrl": f"{_S}/repo/lintwise", "isWatched": True,
        "timeline": [
            _ev("feature_update", "Lintwise now batches comments per file", "2026-10-11", "2026-10-12", "hn/lintwise-2",
                "batching cut comment volume roughly in half on our test repos"),
            _ev("reported_blocker", "Ask: how do you keep LLM review output stable?", "2026-09-24", "2026-09-25", "hn/lintwise-q"),
            _ev("project_announcement", "Show: Lintwise, quieter AI code review", "2026-08-29", "2026-08-30", "hn/lintwise"),
        ],
    },
    {
        "id": "s-driftboard", "name": "Driftboard",
        "description": "Alerts when a production Postgres schema drifts from the migrations in the repo.",
        "builderName": "Tomas R.", "builderUsername": "tomas_r", "builderProfileUrl": f"{_S}/u/tomas_r",
        "category": "Data and analytics", "techStack": ["Go", "PostgreSQL", "Docker"],
        "buildStage": "mvp", "currentFocus": "Adding support for multiple schemas per database.",
        "blockers": [{"title": "Permissions needed to read pg_catalog on managed hosts", "category": "Infrastructure",
                      "evidenceType": "explicit", "excerpt": "some hosts don't grant read access to the catalog"}],
        "activityTrend": "stable", "firstSeenAt": "2026-07-18", "lastObservedAt": "2026-10-09",
        "sourcePlatform": "GitHub", "sourceUrl": f"{_S}/gh/driftboard", "projectUrl": None,
        "repositoryUrl": f"{_S}/repo/driftboard", "isWatched": False,
        "timeline": [
            _ev("repository_update", "v0.4 release notes", "2026-10-08", "2026-10-09", "gh/driftboard-v04"),
            _ev("project_announcement", "Show: Driftboard", "2026-07-17", "2026-07-18", "gh/driftboard"),
        ],
    },
    {
        "id": "s-quiethours",
        "name": "Quiet Hours: a calendar-aware focus timer for distributed engineering teams across time zones",
        "description": "Blocks notifications during agreed focus windows that respect each teammate's time zone.",
        "builderName": "Quiet Hours team", "builderUsername": "quiethours", "builderProfileUrl": None,
        "category": "Productivity", "techStack": ["TypeScript", "React", "Node.js"],
        "buildStage": "launched", "currentFocus": "Calendar sync reliability for recurring events.",
        "blockers": [],
        "activityTrend": "declining", "firstSeenAt": "2026-05-02", "lastObservedAt": "2026-09-28",
        "sourcePlatform": "Hacker News", "sourceUrl": f"{_S}/hn/quiethours", "projectUrl": f"{_S}/quiethours",
        "repositoryUrl": None, "isWatched": False,
        "timeline": [
            _ev("product_launch", "Launch: Quiet Hours 1.0", "2026-06-10", "2026-06-11", "hn/quiethours-launch",
                "we're out of beta and open to every team"),
            _ev("feature_update", "Recurring-event sync rewrite", "2026-09-27", "2026-09-28", "hn/quiethours"),
        ],
    },
    {
        "id": "s-tinyqueue", "name": "tinyqueue",
        "description": "A small persistent job queue for single-binary services.",
        "builderName": None, "builderUsername": None, "builderProfileUrl": None,
        "category": "Open source", "techStack": ["Rust", "SQLite"],
        "buildStage": "unknown", "currentFocus": None, "blockers": None,
        "activityTrend": "insufficient", "firstSeenAt": "2026-10-13", "lastObservedAt": "2026-10-13",
        "sourcePlatform": "GitHub", "sourceUrl": f"{_S}/gh/tinyqueue", "projectUrl": None,
        "repositoryUrl": f"{_S}/repo/tinyqueue", "isWatched": False,
        "timeline": [_ev("repository_update", "Repository first observed", None, "2026-10-13", "gh/tinyqueue")],
    },
    {
        "id": "s-patchnote", "name": "Patchnote",
        "description": "Writes customer-facing changelogs from merged pull requests.",
        "builderName": "Lena K.", "builderUsername": "lenak", "builderProfileUrl": f"{_S}/u/lenak",
        "category": "SaaS", "techStack": ["Next.js", "TypeScript", "PostgreSQL", "LLM API"],
        "buildStage": "launched", "currentFocus": "Team plans and per-repository templates.",
        "blockers": [{"title": "GitHub webhooks arrive out of order", "category": "API integration",
                      "evidenceType": "explicit", "excerpt": "merge events sometimes land before the PR update"}],
        "activityTrend": "stable", "firstSeenAt": "2026-04-21", "lastObservedAt": "2026-10-02",
        "sourcePlatform": "Hacker News", "sourceUrl": f"{_S}/hn/patchnote", "projectUrl": f"{_S}/patchnote",
        "repositoryUrl": None, "isWatched": False,
        "timeline": [
            _ev("feature_update", "Templates per repository", "2026-10-01", "2026-10-02", "hn/patchnote-2"),
            _ev("product_launch", "Launch: Patchnote", "2026-04-20", "2026-04-21", "hn/patchnote"),
        ],
    },
    {
        "id": "s-keyringlite", "name": "Keyring Lite",
        "description": "Pre-commit hook that catches secrets before they reach a remote.",
        "builderName": "Sam O.", "builderUsername": "samo", "builderProfileUrl": f"{_S}/u/samo",
        "category": "Security", "techStack": ["Go", "TypeScript"],
        "buildStage": "prototype", "currentFocus": "Reducing false positives on test fixtures.",
        "blockers": [],
        "activityTrend": "rising", "firstSeenAt": "2026-09-15", "lastObservedAt": "2026-10-11",
        "sourcePlatform": "GitHub", "sourceUrl": f"{_S}/gh/keyringlite", "projectUrl": None,
        "repositoryUrl": f"{_S}/repo/keyringlite", "isWatched": False,
        "timeline": [
            _ev("public_demo", "Demo: catching a leaked token in a commit", "2026-10-10", "2026-10-11", "gh/keyringlite-demo"),
            _ev("project_announcement", "Show: Keyring Lite", "2026-09-14", "2026-09-15", "gh/keyringlite"),
        ],
    },
    {
        "id": "s-fieldnotes", "name": "Fieldnotes",
        "description": "Readable diffs for data notebooks, cell by cell.",
        "builderName": "Arun M.", "builderUsername": "arunm", "builderProfileUrl": f"{_S}/u/arunm",
        "category": "Data and analytics", "techStack": ["Python", "DuckDB", "React"],
        "buildStage": "idea",
        "currentFocus": ("Deciding whether to diff rendered outputs or only source cells, after feedback that output "
                         "diffs are noisy for plots but essential for tables, and working out how to show both "
                         "without making reviews slower for teams that commit notebooks daily."),
        "blockers": [{"title": "Notebook outputs are too large to diff in the browser", "category": "Performance",
                      "evidenceType": "inferred", "excerpt": None}],
        "activityTrend": "insufficient", "firstSeenAt": "2026-09-20", "lastObservedAt": "2026-09-20",
        "sourcePlatform": "Stack Overflow", "sourceUrl": f"{_S}/so/fieldnotes", "projectUrl": None,
        "repositoryUrl": None, "isWatched": False,
        "timeline": [_ev("technical_question", "Ask: diffing notebook outputs efficiently", "2026-09-19", "2026-09-20",
                         "so/fieldnotes")],
    },
    {
        "id": "s-cidoctor", "name": "CI Doctor",
        "description": "Explains why a CI run failed in plain language and links the likely cause.",
        "builderName": "Mei L.", "builderUsername": "meil", "builderProfileUrl": f"{_S}/u/meil",
        "category": "Developer tools", "techStack": ["TypeScript", "Node.js", "GitHub API", "LLM API"],
        "buildStage": "beta", "currentFocus": "Detecting flaky tests separately from real failures.",
        "blockers": [
            {"title": "Logs are truncated for long jobs", "category": "API integration", "evidenceType": "explicit",
             "excerpt": "the API only returns the last part of very long logs"},
            {"title": "Flaky tests look like real failures", "category": "Testing", "evidenceType": "explicit",
             "excerpt": "half of our 'failures' pass on retry"},
            {"title": "Costs grow with log size", "category": "Infrastructure costs", "evidenceType": "inferred",
             "excerpt": None},
        ],
        "activityTrend": "rising", "firstSeenAt": "2026-08-05", "lastObservedAt": "2026-10-13",
        "sourcePlatform": "Hacker News", "sourceUrl": f"{_S}/hn/cidoctor", "projectUrl": f"{_S}/cidoctor",
        "repositoryUrl": f"{_S}/repo/cidoctor", "isWatched": True,
        "timeline": [
            _ev("feature_update", "Flaky-test detection in beta", "2026-10-12", "2026-10-13", "hn/cidoctor-3"),
            _ev("reported_blocker", "Ask: getting full logs for long jobs", "2026-09-18", "2026-09-19", "hn/cidoctor-q"),
            _ev("project_announcement", "Show: CI Doctor", "2026-08-04", "2026-08-05", "hn/cidoctor"),
        ],
    },
    {
        "id": "s-mapleform", "name": "Mapleform",
        "description": "Form builder for internal tools with approval steps.",
        "builderName": "Jordan P.", "builderUsername": "jordanp", "builderProfileUrl": f"{_S}/u/jordanp",
        "category": "SaaS", "techStack": ["Vue", "Laravel", "MySQL"],
        "buildStage": "mvp", "currentFocus": "Single sign-on for the first paying customers.",
        "blockers": [{"title": "SSO setup differs per identity provider", "category": "Authentication",
                      "evidenceType": "explicit", "excerpt": "every provider needs its own setup steps"}],
        "activityTrend": "declining", "firstSeenAt": "2026-03-11", "lastObservedAt": "2026-09-05",
        "sourcePlatform": "Hacker News", "sourceUrl": f"{_S}/hn/mapleform", "projectUrl": f"{_S}/mapleform",
        "repositoryUrl": None, "isWatched": False,
        "timeline": [_ev("feature_update", "SSO in progress", "2026-09-04", "2026-09-05", "hn/mapleform")],
    },
    {
        "id": "s-edgecachekit", "name": "Edgecache Kit",
        "description": "Tests CDN cache rules locally before they ship.",
        "builderName": "Dev S.", "builderUsername": "devs", "builderProfileUrl": f"{_S}/u/devs",
        "category": "Infrastructure", "techStack": ["Go", "Docker"],
        "buildStage": "prototype", "currentFocus": "Matching edge behaviour for query-string normalisation.",
        "blockers": [],
        "activityTrend": "stable", "firstSeenAt": "2026-08-22", "lastObservedAt": "2026-10-07",
        "sourcePlatform": "GitHub", "sourceUrl": f"{_S}/gh/edgecachekit", "projectUrl": None,
        "repositoryUrl": f"{_S}/repo/edgecachekit", "isWatched": False,
        "timeline": [_ev("repository_update", "Query-string rules added", "2026-10-06", "2026-10-07", "gh/edgecachekit")],
    },
    {
        "id": "s-promptfolio", "name": "Promptfolio",
        "description": "Version control and review for prompts used in production.",
        "builderName": "Promptfolio team", "builderUsername": None, "builderProfileUrl": None,
        "category": "AI tools", "techStack": ["Python", "SQLite", "Electron"],
        "buildStage": "idea", "currentFocus": None, "blockers": None,
        "activityTrend": "insufficient", "firstSeenAt": "2026-10-10", "lastObservedAt": "2026-10-10",
        "sourcePlatform": "Hacker News", "sourceUrl": f"{_S}/hn/promptfolio", "projectUrl": None,
        "repositoryUrl": None, "isWatched": False,
        "timeline": [_ev("project_announcement", "Looking for feedback: prompt versioning", "2026-10-09", "2026-10-10",
                         "hn/promptfolio")],
    },
    {
        "id": "s-commitcraft", "name": "Commitcraft",
        "description": "Suggests commit messages from staged changes, offline by default.",
        "builderName": "Kai W.", "builderUsername": "kaiw", "builderProfileUrl": f"{_S}/u/kaiw",
        "category": "Developer tools", "techStack": ["Rust", "LLM API"],
        "buildStage": "launched", "currentFocus": "Local models for teams that can't send code to an API.",
        "blockers": [{"title": "Local models are slow on older laptops", "category": "Performance",
                      "evidenceType": "explicit", "excerpt": "takes several seconds per commit on a 2019 laptop"}],
        "activityTrend": "rising", "firstSeenAt": "2026-06-30", "lastObservedAt": "2026-10-12",
        "sourcePlatform": "GitHub", "sourceUrl": f"{_S}/gh/commitcraft", "projectUrl": f"{_S}/commitcraft",
        "repositoryUrl": f"{_S}/repo/commitcraft", "isWatched": False,
        "timeline": [
            _ev("feature_update", "Offline mode with local models", "2026-10-11", "2026-10-12", "gh/commitcraft-2"),
            _ev("product_launch", "Commitcraft 1.0", "2026-07-15", "2026-07-16", "gh/commitcraft"),
        ],
    },
    {
        "id": "s-haystacklogs", "name": "Haystack Logs",
        "description": "Log search for small teams without running a cluster.",
        "builderName": "Ines F.", "builderUsername": "inesf", "builderProfileUrl": f"{_S}/u/inesf",
        "category": "Data and analytics", "techStack": ["Go", "ClickHouse", "Svelte", "Docker", "Kubernetes"],
        "buildStage": "mvp", "currentFocus": "Retention policies and storage costs.",
        "blockers": [
            {"title": "Storage costs grow faster than expected", "category": "Infrastructure costs",
             "evidenceType": "explicit", "excerpt": "storage is now our biggest bill"},
            {"title": "Kubernetes setup is hard for small teams", "category": "Deployment",
             "evidenceType": "inferred", "excerpt": None},
        ],
        "activityTrend": "stable", "firstSeenAt": "2026-07-02", "lastObservedAt": "2026-09-30",
        "sourcePlatform": "Hacker News", "sourceUrl": f"{_S}/hn/haystacklogs", "projectUrl": f"{_S}/haystacklogs",
        "repositoryUrl": f"{_S}/repo/haystacklogs", "isWatched": False,
        "timeline": [_ev("feature_update", "Retention policies", "2026-09-29", "2026-09-30", "hn/haystacklogs")],
    },
    {
        "id": "s-gitstreak", "name": "Habit tracker that syncs with git activity",
        "description": "Turns daily commits into a habit streak. The post doesn't name the project.",
        "builderName": None, "builderUsername": "anon_dev", "builderProfileUrl": None,
        "category": "Other", "techStack": ["JavaScript"],
        "buildStage": "unknown", "currentFocus": None, "blockers": None,
        "activityTrend": "insufficient", "firstSeenAt": "2026-08-20", "lastObservedAt": "2026-08-20",
        "sourcePlatform": "Hacker News", "sourceUrl": None, "projectUrl": None,
        "repositoryUrl": None, "isWatched": False,
        "timeline": [{"type": "project_announcement", "title": "Weekend project: git habit streaks",
                      "publishedAt": None, "collectedAt": "2026-08-20", "sourceUrl": None, "excerpt": None}],
    },
]
