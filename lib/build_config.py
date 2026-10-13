"""Building Now settings in one place: recency windows, freshness, trend rules, taxonomies.

Every "active", "new", "rising" or "trending" label on the Building Now pages comes from these numbers,
so changing a rule here changes it everywhere (and the explanations shown on the page)."""

# ---------- freshness (based on ORIGINAL post dates, never on when DevvIT collected them) ----------
NEW_DAYS = 14             # first public observation within this many days -> "Newly discovered"
RECENT_DAYS = 30          # latest public observation within this many days -> "Recently observed"
ACTIVE_BUILDER_DAYS = 30  # a builder counts as an active public builder only with a post this recent

# ---------- project activity trend ----------
TREND_WINDOW_DAYS = 28    # compare the latest 28 days with the 28 days before
TREND_MIN_OBS = 3         # fewer observations across both windows -> "Insufficient data"
TREND_MIN_DELTA = 2       # rising/declining needs at least this absolute change
TREND_RATIO = 1.5         # ... and at least this ratio

# ---------- Trending Stack (technologies) ----------
# Periods are whole Friday-to-Thursday weeks, so the current partial week is never compared.
PERIOD_WEEKS = {7: 1, 30: 4, 90: 13}
STACK_MIN_PROJECTS = 2    # a technology needs this many distinct projects in the period to be listed
STACK_POPULAR = 3         # in both periods -> "Consistently popular"
STACK_ORIGIN = "show_hn"  # trends count only Show HN posts: sampled the same way every week

# ---------- table ----------
PAGE_SIZE = 25
PERIODS = [(7, "Last 7 days"), (30, "Last 30 days"), (90, "Last 90 days"), (0, "Last 12 months")]
DEFAULT_PERIOD = 30
LOAD_DAYS = 365           # observations loaded for the overview (older ones stay stored for detail pages)

# ---------- taxonomies (spec values; older stored values are mapped, never rewritten) ----------
STAGES = {"idea": "Idea", "prototype": "Prototype", "mvp": "MVP", "beta": "Beta", "launched": "Launched",
          "unknown": "Unknown"}
# Values written by the first Building Now version -> current stages
LEGACY_STAGE = {"idea": "idea", "prototype": "prototype", "alpha_beta": "beta", "launched": "launched",
                "maintained": "launched", "mvp": "mvp", "beta": "beta"}

EVENTS = {"project_announcement": "Project announcement", "product_launch": "Product launch",
          "feature_update": "Feature update", "public_demo": "Public demo", "repository_update": "Repository update",
          "technical_question": "Technical question", "reported_blocker": "Reported blocker",
          "unclear": "Not classified"}

BLOCKER_CATEGORIES = {"debugging": "Debugging", "deployment": "Deployment", "authentication": "Authentication",
                      "api_integration": "API integration", "testing": "Testing", "documentation": "Documentation",
                      "ai_reliability": "AI reliability", "infrastructure_costs": "Infrastructure costs",
                      "performance": "Performance", "data_management": "Data management",
                      "developer_experience": "Developer experience", "code_review": "Code review", "other": "Other"}
# Blocker kinds from the first version -> current categories (display only; stored rows keep their value)
LEGACY_BLOCKER = {"integration": "api_integration", "api_limits": "api_integration", "deployment": "deployment",
                  "tool_reliability": "developer_experience", "performance": "performance",
                  "testing_debugging": "debugging", "ai_agent_reliability": "ai_reliability",
                  "code_review": "code_review", "other": "other"}

# Technology groups for the Trending Stack filters. Known names are grouped by this list; anything else
# falls back to the kind Gemini gave it (language, database, ...), and "framework" alone isn't enough to
# say frontend or backend, so unknown frameworks go to "Other frameworks".
TECH_GROUPS = {"languages": "Programming languages", "frontend": "Frontend frameworks",
               "backend": "Backend frameworks", "databases": "Databases", "ai": "AI models & tooling",
               "cloud": "Cloud & infrastructure", "platforms": "Developer platforms",
               "testing": "Testing & security", "frameworks": "Other frameworks", "other": "Other"}
_KNOWN = {
    "frontend": "react reactjs nextjs vue vuejs nuxt svelte sveltekit angular solidjs solid astro remix qwik htmx "
                "tailwind tailwindcss preact alpinejs jquery flutter reactnative swiftui jetpackcompose electron tauri",
    "backend": "django flask fastapi rails rubyonrails express expressjs nestjs spring springboot laravel phoenix "
               "gin fiber actix axum rocket hono koa aspnet aspnetcore dotnet nodejs node deno bun",
    "databases": "postgres postgresql mysql sqlite mongodb redis supabase firebase dynamodb cassandra clickhouse "
                 "duckdb neo4j elasticsearch pinecone qdrant weaviate pgvector chroma planetscale neon turso",
    "ai": "openai gpt gpt4 gpt4o gpt5 chatgpt claude anthropic gemini llama ollama mistral langchain llamaindex "
          "huggingface transformers pytorch tensorflow whisper stablediffusion mcp vllm deepseek qwen copilot cursor",
    "cloud": "aws gcp googlecloud azure vercel netlify cloudflare cloudflareworkers flyio fly heroku render railway "
             "docker kubernetes k8s terraform nginx lambda digitalocean hetzner",
    "platforms": "github gitlab bitbucket vscode jetbrains githubactions npm pypi homebrew stripe slack discord",
    "testing": "jest vitest pytest playwright cypress selenium mocha junit owasp snyk semgrep sonarqube",
    "languages": "python javascript typescript rust go golang java kotlin swift c c++ c# csharp ruby php elixir zig "
                 "haskell scala clojure lua dart ocaml julia r",
}
KNOWN_TECH = {k: g for g, names in _KNOWN.items() for k in names.split()}
KIND_GROUP = {"language": "languages", "database": "databases", "ai_model": "ai", "infrastructure": "cloud",
              "dev_tool": "platforms", "framework": "frameworks", "api": "platforms", "other": "other"}

# Hosts that don't identify a project by themselves (a video, a blog post, a social profile...).
GENERIC_HOSTS = {"news.ycombinator.com", "youtube.com", "youtu.be", "twitter.com", "x.com", "medium.com",
                 "dev.to", "reddit.com", "linkedin.com", "substack.com", "producthunt.com", "docs.google.com",
                 "drive.google.com", "loom.com", "imgur.com", "gist.github.com", "stackoverflow.com"}
