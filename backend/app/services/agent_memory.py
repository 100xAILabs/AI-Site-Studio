from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default persistent store path
_MEMORY_DIR = Path(__file__).resolve().parent.parent / "data"
_MEMORY_FILE = _MEMORY_DIR / "agent_learning_memory.json"

# Core foundational lessons seeded into the memory engine
_DEFAULT_LESSONS = [
    {
        "id": "lesson_multi_page_nav_hashes",
        "category": "navigation",
        "title": "Cross-Page Relative Navigation Mandate",
        "rule": "In multi-page websites, NEVER use bare anchor hashes (e.g. href=\"#featured\", href=\"#services\", href=\"#about\") in the navigation of secondary pages. All cross-page links must be relative (e.g. href=\"about.html\", href=\"projects.html\", href=\"skills.html\", or href=\"index.html#featured\").",
        "mistake_trigger": "navigation_hash_anchor",
        "severity": "high",
        "occurrence_count": 2,
        "last_seen": "2026-11-06T18:00:00Z"
    },
    {
        "id": "lesson_shared_layout_parity",
        "category": "layout",
        "title": "Header & Footer Route Consistency",
        "rule": "The desktop <header> and mobile navigation drawer MUST provide the exact same page routes across all sibling pages. Only the .active class / aria-current=\"page\" attribute may differ to highlight the current active file.",
        "mistake_trigger": "inconsistent_navigation_parity",
        "severity": "high",
        "occurrence_count": 2,
        "last_seen": "2026-11-06T18:00:00Z"
    },
    {
        "id": "lesson_zero_markdown_leakage",
        "category": "syntax",
        "title": "Zero Markdown or Conversational Leakage",
        "rule": "Never include markdown backtick fences (```html or ```) or conversational commentary (e.g. 'This completes the HTML structure...') in generated code files. Output pure, clean HTML/CSS/JS only.",
        "mistake_trigger": "markdown_code_fence_leakage",
        "severity": "critical",
        "occurrence_count": 1,
        "last_seen": "2026-11-06T18:00:00Z"
    },
    {
        "id": "lesson_dom_tag_balance",
        "category": "syntax",
        "title": "Strict DOM Tag Matching & Unique IDs",
        "rule": "Ensure every opened tag has a single matching closing tag. Never emit orphan </div> closing tags or duplicate overlay IDs (such as multiple id=\"drawerOverlay\").",
        "mistake_trigger": "unmatched_closing_tag",
        "severity": "high",
        "occurrence_count": 1,
        "last_seen": "2026-11-06T18:00:00Z"
    },
    {
        "id": "lesson_mobile_drawer_controller",
        "category": "mobile",
        "title": "Universal Mobile Drawer Functionality",
        "rule": "Every page with a hamburger button (#mobileMenuBtn) MUST have a corresponding mobile drawer (#mobileDrawer) and overlay (#drawerOverlay), wired with a clean working JavaScript open/close toggle script.",
        "mistake_trigger": "missing_drawer_markup",
        "severity": "high",
        "occurrence_count": 1,
        "last_seen": "2026-11-06T18:00:00Z"
    }
]


class AgentMemoryRegistry:
    """
    Persistent self-reflection and learning memory for AI Site Studio agents.
    Captures audit warnings, test failures, and link flaws, then formats them
    into distilled negative constraints injected into future generation prompts.
    """

    def __init__(self, memory_file: Optional[Path] = None):
        self.memory_file = memory_file or _MEMORY_FILE
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.memory_file.exists():
                self._save_data({
                    "version": "1.0",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "total_mistakes_logged": len(_DEFAULT_LESSONS),
                    "lessons": _DEFAULT_LESSONS
                })
        except Exception as e:
            logger.warning(f"Could not initialize agent memory storage: {e}")

    def _load_data(self) -> dict[str, Any]:
        try:
            if self.memory_file.exists():
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading agent memory: {e}")
        return {"version": "1.0", "lessons": _DEFAULT_LESSONS}

    def _save_data(self, data: dict[str, Any]) -> None:
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Error saving agent memory: {e}")

    def record_mistake(
        self,
        category: str,
        mistake_trigger: str,
        lesson_rule: str,
        file_path: Optional[str] = None,
        severity: str = "high",
        title: Optional[str] = None,
    ) -> None:
        """
        Records a detected audit or generation flaw, updating occurrence metrics
        and persisting the rule to agent memory.
        """
        data = self._load_data()
        lessons: list[dict[str, Any]] = data.get("lessons", [])
        now_iso = datetime.now(timezone.utc).isoformat()

        # Find existing rule by trigger or category
        matched = None
        for item in lessons:
            if item.get("mistake_trigger") == mistake_trigger:
                matched = item
                break

        if matched:
            matched["occurrence_count"] = matched.get("occurrence_count", 0) + 1
            matched["last_seen"] = now_iso
            matched["severity"] = severity
            if file_path:
                matched["last_file"] = file_path
            logger.info(f"Agent memory reinforced: '{mistake_trigger}' (seen {matched['occurrence_count']}x)")
        else:
            new_id = f"lesson_{mistake_trigger.replace('-', '_').replace(' ', '_').lower()}"
            new_lesson = {
                "id": new_id,
                "category": category,
                "title": title or mistake_trigger.replace("_", " ").title(),
                "rule": lesson_rule,
                "mistake_trigger": mistake_trigger,
                "severity": severity,
                "occurrence_count": 1,
                "last_seen": now_iso,
                "last_file": file_path or ""
            }
            lessons.append(new_lesson)
            logger.info(f"Agent learned new lesson from mistake: '{mistake_trigger}'")

        data["lessons"] = lessons
        data["total_mistakes_logged"] = sum(l.get("occurrence_count", 1) for l in lessons)
        self._save_data(data)

    def get_learned_constraints_prompt(self, category: Optional[str] = None) -> str:
        """
        Formats active learned rules into a strict, concise prompt block
        that prevents LLMs from repeating documented past mistakes.
        """
        data = self._load_data()
        lessons: list[dict[str, Any]] = data.get("lessons", [])

        if category:
            lessons = [l for l in lessons if l.get("category") == category]

        # Prioritize high/critical and frequently occurring lessons
        sorted_lessons = sorted(
            lessons,
            key=lambda l: (
                1 if l.get("severity") == "critical" else 2 if l.get("severity") == "high" else 3,
                -l.get("occurrence_count", 1)
            )
        )

        if not sorted_lessons:
            return ""

        lines = [
            "=== AGENT LEARNED LESSONS & AVOIDANCE CONSTRAINTS (STRICT) ===",
            "You MUST follow these strict quality rules learned from previous generation audits:"
        ]
        for idx, item in enumerate(sorted_lessons[:6], start=1):
            title = item.get("title", f"Rule {idx}")
            rule = item.get("rule", "").strip()
            lines.append(f"{idx}. [{title.upper()}]: {rule}")

        return "\n".join(lines)

    def get_all_lessons(self) -> list[dict[str, Any]]:
        return self._load_data().get("lessons", [])


# Global singleton instance
agent_memory = AgentMemoryRegistry()

