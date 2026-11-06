from datetime import datetime, timezone
import logging
import re
from typing import Any, Optional

from .agent_memory import agent_memory

logger = logging.getLogger(__name__)


def generate_sitemap_xml(filenames: list[str], base_url: str = "https://example.com") -> str:
    """Generates standard compliant sitemap.xml for multi-page package."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls_xml = []
    for fname in sorted(filenames):
        clean_name = fname.lstrip("/")
        loc = f"{base_url.rstrip('/')}/{clean_name}"
        priority = "1.0" if clean_name == "index.html" else "0.8"
        changefreq = "weekly" if clean_name == "index.html" else "monthly"
        urls_xml.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls_xml)
        + "\n</urlset>\n"
    )


def generate_robots_txt(base_url: str = "https://example.com") -> str:
    """Generates standard robots.txt permitting indexing and referencing sitemap."""
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {base_url.rstrip('/')}/sitemap.xml\n"
    )


def inject_seo_and_social_tags(
    html: str,
    filename: str,
    seo_title: str,
    seo_description: str,
    brand_name: str,
    og_image_url: str = "",
) -> str:
    """
    Ensures complete, standard-compliant SEO and Open Graph metadata in <head>.
    """
    seo_title = seo_title or f"{filename.rsplit('.', 1)[0].title()} | {brand_name}"
    seo_description = seo_description or f"Official website of {brand_name}. High quality creative work and responsive digital experiences."

    # Guarantee viewport meta tag
    if not re.search(r'<meta\b[^>]*\bname=[\'"]viewport[\'"]', html, flags=re.IGNORECASE):
        html = re.sub(
            r'(<head\b[^>]*>)',
            r'\1\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    # Replace or inject <title>
    if re.search(r'<title\b[^>]*>.*?</title\s*>', html, flags=re.IGNORECASE | re.DOTALL):
        html = re.sub(r'<title\b[^>]*>.*?</title\s*>', f"<title>{seo_title}</title>", html, count=1, flags=re.IGNORECASE)
    else:
        html = re.sub(r'(<head\b[^>]*>)', rf'\1\n  <title>{seo_title}</title>', html, count=1, flags=re.IGNORECASE)

    # Replace or inject meta description
    if re.search(r'<meta\b[^>]*\bname=[\'"]description[\'"][^>]*>', html, flags=re.IGNORECASE):
        html = re.sub(
            r'<meta\b[^>]*\bname=[\'"]description[\'"][^>]*>',
            f'<meta name="description" content="{seo_description}">',
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        html = re.sub(r'(<head\b[^>]*>)', rf'\1\n  <meta name="description" content="{seo_description}">', html, count=1, flags=re.IGNORECASE)

    # Inject canonical link if missing
    if not re.search(r'<link\b[^>]*\brel=[\'"]canonical[\'"]', html, flags=re.IGNORECASE):
        html = re.sub(
            r'(<head\b[^>]*>)',
            rf'\1\n  <link rel="canonical" href="{filename}">',
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    # Inject Open Graph tags if missing
    og_tags = f"""  <meta property="og:title" content="{seo_title}">
  <meta property="og:description" content="{seo_description}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{filename}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{seo_title}">
  <meta name="twitter:description" content="{seo_description}">"""
    if og_image_url:
        og_tags += f'\n  <meta property="og:image" content="{og_image_url}">\n  <meta name="twitter:image" content="{og_image_url}">'

    if not re.search(r'<meta\b[^>]*\bproperty=[\'"]og:title[\'"]', html, flags=re.IGNORECASE):
        html = re.sub(r'(</head\s*>)', f"{og_tags}\n\\1", html, count=1, flags=re.IGNORECASE)

    return html


def normalize_multi_page_navigation(
    pages: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """
    Deterministically cleans, normalizes, and repairs multi-page navigation,
    header parity, cross-page relative links, duplicate DOM IDs, and markdown leakage.
    Returns (repaired_pages, repairs_list).
    """
    repaired_pages: dict[str, str] = {}
    repairs_log: list[dict[str, Any]] = []

    # Map of all real HTML pages in this generated project
    available_html_pages = {k.lower(): k for k in pages.keys() if k.lower().endswith(".html")}
    is_multi_page = len(available_html_pages) > 1

    for fname, raw_html in pages.items():
        if not fname.lower().endswith(".html"):
            repaired_pages[fname] = raw_html
            continue

        html = raw_html

        # 1. Clean Trailing Markdown Fences & Conversational Leakage
        if "</html>" in html.lower():
            closing_match = re.search(r'</html>', html, flags=re.IGNORECASE)
            if closing_match:
                end_pos = closing_match.end()
                trailing_content = html[end_pos:].strip()
                if trailing_content:
                    html = html[:end_pos] + "\n"
                    repairs_log.append({
                        "file": fname,
                        "type": "markdown_code_fence_leakage",
                        "description": f"Stripped {len(trailing_content)} chars of trailing markdown leakage after </html>",
                    })
                    agent_memory.record_mistake(
                        category="syntax",
                        mistake_trigger="markdown_code_fence_leakage",
                        lesson_rule="Never emit markdown code fences or conversational text at the end of HTML files.",
                        file_path=fname,
                        severity="critical",
                    )

        # 2. Fix Duplicate Drawer Overlay IDs & Orphan Closing Tags
        if html.count('id="drawerOverlay"') > 1 or html.count("id='drawerOverlay'") > 1:
            # Keep only first occurrence of drawerOverlay
            seen_overlay = False
            def _dedup_overlay(m: re.Match) -> str:
                nonlocal seen_overlay
                if not seen_overlay:
                    seen_overlay = True
                    return m.group(0)
                return ""

            html = re.sub(
                r'<div\b[^>]*\bid=[\'"]drawerOverlay[\'"][^>]*>\s*</div>',
                _dedup_overlay,
                html,
                flags=re.IGNORECASE,
            )
            repairs_log.append({
                "file": fname,
                "type": "duplicate_overlay_id",
                "description": "Removed duplicate #drawerOverlay DOM elements.",
            })
            agent_memory.record_mistake(
                category="syntax",
                mistake_trigger="duplicate_overlay_id",
                lesson_rule="Ensure every DOM ID like #drawerOverlay is unique; never emit duplicate overlay elements.",
                file_path=fname,
                severity="high",
            )

        # Clean duplicate script tags
        script_pattern = r'(<script\b[^>]*src=[\'"]([^\'"]+)[\'"][^>]*>\s*</script>)'
        seen_scripts: set[str] = set()
        def _dedup_script(m: re.Match) -> str:
            src = m.group(2).strip()
            if src in seen_scripts:
                return ""
            seen_scripts.add(src)
            return m.group(1)

        html = re.sub(script_pattern, _dedup_script, html, flags=re.IGNORECASE)

        # 3. Multi-Page Navigation Normalization
        if is_multi_page:
            is_index_page = fname.lower() in {"index.html", "home.html"}

            # Map common section hashes to dedicated sibling pages
            section_to_page = {
                "#about": "about.html",
                "#bio": "about.html",
                "#biography": "about.html",
                "#projects": "projects.html",
                "#work": "projects.html",
                "#portfolio": "projects.html",
                "#case-studies": "projects.html",
                "#skills": "skills.html",
                "#services": "services.html",
                "#pricing": "pricing.html",
                "#contact": "contact.html",
            }

            def _normalize_nav_link(m: re.Match) -> str:
                full_tag = m.group(0)
                href = m.group(1)

                # Check if hash points directly to an existing sibling page
                target_page = section_to_page.get(href.lower())
                if target_page and target_page in available_html_pages:
                    return full_tag.replace(href, target_page)

                # On secondary pages, prefix homepage section hashes with index.html
                if not is_index_page and href.startswith("#"):
                    return full_tag.replace(href, f"index.html{href}")

                return full_tag

            # Scan and normalize inside <nav> and <header> blocks
            html = re.sub(
                r'<a\b[^>]*\bhref=[\'"](#[a-zA-Z0-9_\-]+)[\'"][^>]*>',
                _normalize_nav_link,
                html,
                flags=re.IGNORECASE,
            )

            # Ensure current page has active highlight and others don't in desktop nav
            clean_fname = fname.split("/")[-1].lower()
            def _fix_active_highlight(nav_match: re.Match) -> str:
                nav_block = nav_match.group(0)

                # Helper to update active class per link
                def _link_replacer(link_match: re.Match) -> str:
                    link_tag = link_match.group(0)
                    href = link_match.group(1).lower()

                    is_current = (
                        href == clean_fname or
                        href.endswith(f"/{clean_fname}") or
                        (clean_fname in {"index.html", "home.html"} and href in {"index.html", "home.html", "./", "/"})
                    )

                    # Strip existing active / aria-current
                    cleaned = re.sub(r'\s+aria-current=[\'"]page[\'"]', "", link_tag, flags=re.IGNORECASE)
                    cleaned = re.sub(r'\s+active\b', "", cleaned, flags=re.IGNORECASE)
                    cleaned = re.sub(r'class=[\'"]([^\'"]*)[\'"]', lambda cm: f'class="{cm.group(1).replace("active", "").strip()}"', cleaned, flags=re.IGNORECASE)

                    if is_current:
                        if 'class="' in cleaned:
                            cleaned = re.sub(r'class="([^"]*)"', r'class="\1 active"', cleaned, count=1)
                        elif "class='" in cleaned:
                            cleaned = re.sub(r"class='([^']*)'", r"class='\1 active'", cleaned, count=1)
                        else:
                            cleaned = cleaned.replace("<a", '<a class="active"', 1)
                        cleaned = cleaned.replace(">", ' aria-current="page">', 1)

                    return cleaned

                return re.sub(r'<a\b[^>]*\bhref=[\'"]([^\'"]+)[\'"][^>]*>', _link_replacer, nav_block, flags=re.IGNORECASE)

            html = re.sub(r'<nav\b[^>]*>.*?</nav\s*>', _fix_active_highlight, html, flags=re.IGNORECASE | re.DOTALL)

        repaired_pages[fname] = html

    return repaired_pages, repairs_log


def run_comprehensive_audit(
    pages: dict[str, str],
    planned_filenames: list[str],
) -> dict[str, Any]:
    """
    Performs rigorous automated code quality, link integrity, and HTML validity checks.
    Automatically logs any flaws into agent_memory for persistent learning.
    """
    findings = []
    generated_filenames = set(pages.keys())

    # Check 1: Zero Missing Pages
    for planned in planned_filenames:
        if planned not in generated_filenames:
            msg = f"Planned page '{planned}' was not generated in output package."
            findings.append({
                "severity": "critical",
                "file": planned,
                "rule": "zero_missing_pages",
                "message": msg,
            })
            agent_memory.record_mistake(
                category="navigation",
                mistake_trigger="missing_planned_page",
                lesson_rule="All planned pages must physically exist and contain rich domain-specific content.",
                file_path=planned,
                severity="critical",
            )
        else:
            content = pages[planned]
            if len(content) < 400:
                findings.append({
                    "severity": "warning",
                    "file": planned,
                    "rule": "page_content_depth",
                    "message": f"Page '{planned}' has suspiciously low character count ({len(content)} chars).",
                })

    # Check 2: Internal Link Integrity
    for fname, html in pages.items():
        # Find all relative links
        hrefs = re.findall(r'href=[\'"]([a-zA-Z0-9_\-\.\/]+\.html)(?:#[^\'"]*)?[\'"]', html, flags=re.IGNORECASE)
        for target in hrefs:
            clean_target = target.split("#")[0].lstrip("/")
            if clean_target and clean_target not in generated_filenames:
                msg = f"Page '{fname}' links to '{clean_target}' which does not exist in package."
                findings.append({
                    "severity": "high",
                    "file": fname,
                    "rule": "broken_internal_link",
                    "message": msg,
                })
                agent_memory.record_mistake(
                    category="navigation",
                    mistake_trigger="broken_internal_link",
                    lesson_rule="All relative links in headers, drawers, and buttons must link to files that actually exist in the package.",
                    file_path=fname,
                    severity="high",
                )

        # Check for unlinked hash anchors in navigation
        nav_matches = re.findall(r'<nav\b[^>]*>(.*?)</nav\s*>', html, flags=re.IGNORECASE | re.DOTALL)
        for nav_content in nav_matches:
            dead_hashes = re.findall(r'href=[\'"](#(?:about|projects|work|skills|contact|services|pricing|team))[\'"]', nav_content, flags=re.IGNORECASE)
            if dead_hashes:
                findings.append({
                    "severity": "warning",
                    "file": fname,
                    "rule": "navigation_hash_anchor",
                    "message": f"Navigation on '{fname}' contains raw anchor links {dead_hashes} instead of sibling page links.",
                })
                agent_memory.record_mistake(
                    category="navigation",
                    mistake_trigger="navigation_hash_anchor",
                    lesson_rule="In multi-page websites, never use bare anchor hashes (#section) on secondary pages. Always prefix with index.html#section or point to the dedicated page.",
                    file_path=fname,
                    severity="high",
                )

        # Check 3: HTML Tag Balance
        if not re.search(r'</html>\s*$', html.strip(), flags=re.IGNORECASE):
            findings.append({
                "severity": "high",
                "file": fname,
                "rule": "unclosed_html_root",
                "message": f"File '{fname}' is missing closing </html> tag.",
            })
            agent_memory.record_mistake(
                category="syntax",
                mistake_trigger="unclosed_html_root",
                lesson_rule="Every HTML document must end cleanly with </html> and have no unclosed tags or trailing markdown fences.",
                file_path=fname,
                severity="high",
            )

    passed = len([f for f in findings if f["severity"] in {"critical", "high"}]) == 0
    return {
        "status": "passed" if passed else "warning",
        "total_pages": len(pages),
        "total_findings": len(findings),
        "findings": findings,
        "summary": "100% link integrity and file coverage verified." if passed else f"Audit completed with {len(findings)} findings.",
    }
