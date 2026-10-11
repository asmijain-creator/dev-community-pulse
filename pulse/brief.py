"""Splits the stored brief markdown into the sections the dashboard lays out along Sumit's journey."""
import re

from .emailer import safe_markdown

# heading prefix (lowercase) -> section key
SECTION_KEYS = {
    "tl;dr": "tldr",
    "top pain points": "top",
    "unresolved": "gaps",
    "objections": "objections",
    "suggested actions": "actions",
    "the numbers": "numbers",
}
_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.*)$")


def split_sections(content_md: str) -> dict[str, str]:
    """{'tldr': md, 'top': md, ..., 'warnings': md, 'extra': md}; unknown headings go to 'extra'."""
    sections: dict[str, list[str]] = {}
    key = "preamble"
    for line in content_md.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            key = next((v for k, v in SECTION_KEYS.items() if heading.startswith(k)), "extra")
            if key == "extra":
                sections.setdefault("extra", []).append(line)
            continue
        sections.setdefault(key, []).append(line)
    out = {k: "\n".join(v).strip() for k, v in sections.items()}
    # Source warnings ("⚠️ ...") sit in the preamble, under the title line.
    out["warnings"] = "\n".join(l for l in out.pop("preamble", "").splitlines() if l.startswith("⚠️"))
    return out


def list_items(section_md: str) -> list[str]:
    """Markdown list items as inline HTML, for the sprint-planning checklist."""
    items = []
    for line in section_md.splitlines():
        if match := _LIST_ITEM.match(line):
            html = safe_markdown(match.group(1)).strip()
            items.append(re.sub(r"^<p>(.*)</p>$", r"\1", html, flags=re.S))
    return items
