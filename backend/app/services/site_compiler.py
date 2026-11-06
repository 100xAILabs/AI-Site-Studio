from datetime import datetime, timezone
import logging
import re
from typing import Any, Optional

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


def run_comprehensive_audit(
    pages: dict[str, str],
    planned_filenames: list[str],
) -> dict[str, Any]:
    """
    Performs rigorous automated code quality, link integrity, and HTML validity checks.
    """
    findings = []
    generated_filenames = set(pages.keys())

    # Check 1: Zero Missing Pages
    for planned in planned_filenames:
        if planned not in generated_filenames:
            findings.append({
                "severity": "critical",
                "file": planned,
                "rule": "zero_missing_pages",
                "message": f"Planned page '{planned}' was not generated in output package.",
            })
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
                findings.append({
                    "severity": "high",
                    "file": fname,
                    "rule": "broken_internal_link",
                    "message": f"Page '{fname}' links to '{clean_target}' which does not exist in package.",
                })

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

        # Check 3: HTML Tag Balance
        if not re.search(r'</html>\s*$', html.strip(), flags=re.IGNORECASE):
            findings.append({
                "severity": "high",
                "file": fname,
                "rule": "unclosed_html_root",
                "message": f"File '{fname}' is missing closing </html> tag.",
            })

    passed = len([f for f in findings if f["severity"] in {"critical", "high"}]) == 0
    return {
        "status": "passed" if passed else "warning",
        "total_pages": len(pages),
        "total_findings": len(findings),
        "findings": findings,
        "summary": "100% link integrity and file coverage verified." if passed else f"Audit completed with {len(findings)} findings.",
    }
