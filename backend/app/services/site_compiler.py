from datetime import datetime, timezone
import logging
import re
from typing import Any, Optional

from .agent_memory import agent_memory

logger = logging.getLogger(__name__)

MOTION_CSS = """<style id="studio-motion-engine">
:root {
  --studio-ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --studio-ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --studio-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}

html {
  scroll-behavior: smooth !important;
}

/* 1. Universal Hero Entrance Keyframes */
@keyframes studioFadeInUp {
  0% {
    opacity: 0;
    transform: translateY(28px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes studioFadeIn {
  0% { opacity: 0; }
  100% { opacity: 1; }
}

@keyframes studioFloatSlow {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-7px); }
}

@keyframes studioPulseGlow {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.04); }
}

/* Staggered Hero Elements Entrance */
header, .navbar, .nav-container {
  animation: studioFadeIn 0.8s var(--studio-ease-out) both;
}

.hero h1, header + main > section:first-of-type h1, main > section:first-child h1, .hero-title {
  animation: studioFadeInUp 0.9s var(--studio-ease-out) 0.08s both;
}

.hero p, header + main > section:first-of-type p, main > section:first-child p, .hero-subtitle, .lead {
  animation: studioFadeInUp 0.9s var(--studio-ease-out) 0.22s both;
}

.hero .buttons, .hero .cta, .hero .cta-group,
header + main > section:first-of-type a.button, header + main > section:first-of-type button,
main > section:first-child a.button, main > section:first-child button {
  animation: studioFadeInUp 0.9s var(--studio-ease-out) 0.36s both;
}

.hero img, .hero-media, .hero-image, .hero-visual,
header + main > section:first-of-type img {
  animation: studioFadeInUp 1s var(--studio-ease-out) 0.3s both;
}

/* 2. Scroll Reveal Animations */
.studio-reveal {
  opacity: 0;
  transform: translateY(28px);
  transition: opacity 0.85s var(--studio-ease-out), transform 0.85s var(--studio-ease-out);
  will-change: opacity, transform;
}

.studio-reveal.is-revealed {
  opacity: 1 !important;
  transform: translateY(0) !important;
}

.studio-reveal-left {
  opacity: 0;
  transform: translateX(-30px);
  transition: opacity 0.85s var(--studio-ease-out), transform 0.85s var(--studio-ease-out);
}
.studio-reveal-left.is-revealed {
  opacity: 1 !important;
  transform: translateX(0) !important;
}

.studio-reveal-right {
  opacity: 0;
  transform: translateX(30px);
  transition: opacity 0.85s var(--studio-ease-out), transform 0.85s var(--studio-ease-out);
}
.studio-reveal-right.is-revealed {
  opacity: 1 !important;
  transform: translateX(0) !important;
}

/* Staggered Delay Utilities */
.delay-100 { transition-delay: 0.1s !important; }
.delay-200 { transition-delay: 0.2s !important; }
.delay-300 { transition-delay: 0.3s !important; }
.delay-400 { transition-delay: 0.4s !important; }
.delay-500 { transition-delay: 0.5s !important; }

/* 3. Modern Interactive Card & Showcase Micro-Interactions */
.card, article, .feature, .service-card, .project-card, .pricing-card, .testimonial-card, .portfolio-card {
  transition: transform 0.35s var(--studio-ease-out), box-shadow 0.35s var(--studio-ease-out), border-color 0.35s var(--studio-ease-out) !important;
}

.card:hover, article:hover, .feature:hover, .service-card:hover, .project-card:hover, .pricing-card:hover, .testimonial-card:hover, .portfolio-card:hover {
  transform: translateY(-6px) scale(1.008) !important;
  box-shadow: 0 20px 35px -10px rgba(0, 0, 0, 0.15), 0 0 22px rgba(99, 102, 241, 0.12) !important;
}

/* Card image zoom effect on hover */
.card:hover img, article:hover img, .project-card:hover img, .portfolio-card:hover img, .feature:hover img {
  transform: scale(1.04);
}
.card img, article img, .project-card img, .portfolio-card img, .feature img {
  transition: transform 0.5s var(--studio-ease-out) !important;
}

/* 4. Tactile Buttons & Controls */
button, .button, a.button, a.btn, .btn, input[type="submit"] {
  position: relative;
  transition: transform 0.25s var(--studio-ease-out), box-shadow 0.25s var(--studio-ease-out), filter 0.25s var(--studio-ease-out), background-color 0.25s var(--studio-ease-out) !important;
  cursor: pointer;
}

button:hover, .button:hover, a.button:hover, a.btn:hover, .btn:hover, input[type="submit"]:hover {
  transform: translateY(-2px);
  filter: brightness(1.08);
  box-shadow: 0 10px 22px -6px rgba(49, 86, 201, 0.35);
}

button:active, .button:active, a.button:active, a.btn:active, .btn:active, input[type="submit"]:active {
  transform: translateY(0) scale(0.97) !important;
}

/* 5. Ambient Badges & Floats */
.badge, .chip, .tag, [class*="badge"], [class*="pill"] {
  display: inline-flex;
  align-items: center;
  transition: transform 0.25s var(--studio-ease-out);
}
.badge:hover, .chip:hover, .tag:hover {
  transform: scale(1.06);
}
.floating-accent, .animate-float {
  animation: studioFloatSlow 4s ease-in-out infinite;
}

/* 6. Elevated Header on Scroll */
header.header-scrolled, nav.nav-scrolled {
  backdrop-filter: blur(16px) !important;
  -webkit-backdrop-filter: blur(16px) !important;
  box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.15) !important;
  transition: backdrop-filter 0.3s ease, box-shadow 0.3s ease;
}

/* 7. Strict Accessibility: Respect prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  .studio-reveal, .studio-reveal-left, .studio-reveal-right {
    opacity: 1 !important;
    transform: none !important;
  }
}
</style>
<noscript>
  <style>
    .studio-reveal, .studio-reveal-left, .studio-reveal-right {
      opacity: 1 !important;
      transform: none !important;
    }
  </style>
</noscript>"""

MOTION_SCRIPT = """<script id="studio-motion-script">
(function() {
  if (window.__STUDIO_MOTION_LOADED__) return;
  window.__STUDIO_MOTION_LOADED__ = true;

  function initMotionSystem() {
    var prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      document.querySelectorAll('.studio-reveal, .studio-reveal-left, .studio-reveal-right').forEach(function(el) {
        el.classList.add('is-revealed');
      });
      return;
    }

    var targetSelectors = [
      'section:not(:first-of-type)',
      '.grid > *',
      '.cards > *',
      '.card-grid > *',
      '.product-grid > *',
      '.team-grid > *',
      '.services-grid > *',
      '.card',
      'article',
      '.feature',
      '.project-card',
      '.pricing-card',
      '.testimonial',
      '.faq-item'
    ];

    var targets = document.querySelectorAll(targetSelectors.join(', '));
    targets.forEach(function(el) {
      if (el.closest('header, nav, #drawerOverlay, [class*="drawer"], [class*="modal"], [id*="modal"]')) return;
      if (!el.classList.contains('studio-reveal') && !el.classList.contains('is-revealed')) {
        el.classList.add('studio-reveal');
        var parent = el.parentElement;
        if (parent && (parent.classList.contains('grid') || parent.classList.contains('cards') || parent.classList.contains('card-grid') || parent.classList.contains('product-grid') || parent.children.length > 1)) {
          var childIndex = Array.prototype.indexOf.call(parent.children, el);
          if (childIndex > 0 && childIndex < 6) {
            el.style.transitionDelay = (childIndex * 0.08) + 's';
          }
        }
      }
    });

    if ('IntersectionObserver' in window) {
      var revealObserver = new IntersectionObserver(function(entries, observer) {
        entries.forEach(function(entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-revealed');
            observer.unobserve(entry.target);
          }
        });
      }, {
        root: null,
        rootMargin: '0px 0px -30px 0px',
        threshold: 0.06
      });

      document.querySelectorAll('.studio-reveal, .studio-reveal-left, .studio-reveal-right').forEach(function(el) {
        var rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight && rect.bottom > 0) {
          el.classList.add('is-revealed');
        } else {
          revealObserver.observe(el);
        }
      });
    } else {
      document.querySelectorAll('.studio-reveal, .studio-reveal-left, .studio-reveal-right').forEach(function(el) {
        el.classList.add('is-revealed');
      });
    }

    var header = document.querySelector('header') || document.querySelector('nav');
    if (header) {
      window.addEventListener('scroll', function() {
        if (window.scrollY > 20) {
          header.classList.add('header-scrolled');
          header.classList.add('nav-scrolled');
        } else {
          header.classList.remove('header-scrolled');
          header.classList.remove('nav-scrolled');
        }
      }, { passive: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMotionSystem);
  } else {
    initMotionSystem();
  }
})();
</script>"""


def inject_modern_motion_system(html: str) -> str:
    """
    Enriches generated HTML with a modern, zero-dependency CSS motion kit
    and an IntersectionObserver scroll-reveal runtime.
    Guarantees fluid hero entrances, scroll reveals, card hover lifts,
    and button micro-interactions while strictly respecting prefers-reduced-motion.
    """
    if not html or not isinstance(html, str):
        return html

    # 1. Inject Motion CSS into <head>
    if "studio-motion-engine" not in html:
        if "</head>" in html:
            html = html.replace("</head>", f"{MOTION_CSS}\n</head>", 1)
        elif "<head>" in html:
            html = html.replace("<head>", f"<head>\n{MOTION_CSS}", 1)
        else:
            html = f"{MOTION_CSS}\n{html}"

    # 2. Inject Motion Runtime Script before </body>
    if "studio-motion-script" not in html:
        if "</body>" in html:
            html = html.replace("</body>", f"\n{MOTION_SCRIPT}\n</body>", 1)
        elif "</html>" in html:
            html = html.replace("</html>", f"\n{MOTION_SCRIPT}\n</html>", 1)
        else:
            html = f"{html}\n{MOTION_SCRIPT}"

    return html


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
        else:
            # Single-Page Navigation Normalization:
            # If a link references a sibling .html file that does not exist, rewrite it to in-page section hash
            page_to_section = {
                "about.html": "#about",
                "projects.html": "#projects",
                "portfolio.html": "#portfolio",
                "work.html": "#work",
                "contact.html": "#contact",
                "services.html": "#services",
                "pricing.html": "#pricing",
                "skills.html": "#skills",
            }

            def _fix_single_page_links(m: re.Match) -> str:
                full_tag = m.group(0)
                href = m.group(1).lower()
                clean_target = href.split("/")[-1].split("?")[0]
                if clean_target in page_to_section:
                    return full_tag.replace(m.group(1), page_to_section[clean_target])
                return full_tag

            html = re.sub(
                r'<a\b[^>]*\bhref=[\'"]([^\'"]+\.html)[\'"][^>]*>',
                _fix_single_page_links,
                html,
                flags=re.IGNORECASE,
            )

        # Enforce modern motion system (smooth scrolling, hero entrance, scroll reveals, card/button hover lift)
        html = inject_modern_motion_system(html)

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
