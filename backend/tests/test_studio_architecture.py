import pytest
from app.services.architect_agent import architect_agent
from app.services.text_agent import text_agent
from app.services.site_compiler import (
    generate_sitemap_xml,
    generate_robots_txt,
    inject_seo_and_social_tags,
    run_comprehensive_audit,
)


def test_architect_agent_manifest():
    plan = {
        "title": "Apex Animator Portfolio",
        "pages": [
            {"name": "Home", "filename": "index.html"},
            {"name": "Portfolio", "filename": "projects.html"},
            {"name": "About", "filename": "about.html"},
            {"name": "Contact", "filename": "contact.html"},
        ],
    }
    manifest = architect_agent._build_fallback_manifest(
        "build portfolio for animator",
        "Creative",
        "portfolio",
        plan,
        {"business_name": "Jordan Cole"},
        "html-css-js",
    )
    assert len(manifest["pages"]) == 4
    assert manifest["pages"][0]["role"] == "gateway_homepage"
    assert manifest["pages"][1]["role"] == "catalog_portfolio"
    assert "projects.html" in manifest["pages"][0]["outbound_links"]
    assert "Full exhaustive project gallery" in manifest["pages"][0]["forbidden_content"][0]


def test_text_agent_content_dictionary():
    plan = {
        "title": "Apex Animator Portfolio",
        "pages": [
            {"name": "Home", "filename": "index.html"},
            {"name": "Portfolio", "filename": "projects.html"},
            {"name": "About", "filename": "about.html"},
            {"name": "Contact", "filename": "contact.html"},
        ],
    }
    manifest = architect_agent._build_fallback_manifest(
        "build portfolio for animator", "Creative", "portfolio", plan, {}, "html-css-js"
    )
    content_dict = text_agent._build_fallback_dictionary(
        manifest["pages"],
        "Jordan Cole",
        "portfolio",
        "build portfolio for animator",
        {"business_name": "Jordan Cole"},
    )
    assert "index.html" in content_dict["pages"]
    assert "projects.html" in content_dict["pages"]
    assert len(content_dict["pages"]["projects.html"]["rich_items"]) >= 4
    assert "Apex Studios" in content_dict["pages"]["projects.html"]["rich_items"][0]["client"]


def test_site_compiler_sitemap_and_robots():
    sitemap = generate_sitemap_xml(["index.html", "projects.html", "about.html", "contact.html"])
    assert "<loc>https://example.com/index.html</loc>" in sitemap
    assert "<priority>1.0</priority>" in sitemap
    assert "<priority>0.8</priority>" in sitemap

    robots = generate_robots_txt()
    assert "User-agent: *" in robots
    assert "Sitemap: https://example.com/sitemap.xml" in robots


def test_inject_seo_and_social_tags():
    sample_html = "<!DOCTYPE html><html><head><title>Old</title></head><body><h1>Hello</h1></body></html>"
    injected = inject_seo_and_social_tags(
        sample_html,
        "projects.html",
        "Projects - Jordan Cole",
        "Explore animation projects",
        "Jordan Cole",
    )
    assert '<meta property="og:title" content="Projects - Jordan Cole">' in injected
    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in injected
    assert '<link rel="canonical" href="projects.html">' in injected


def test_run_comprehensive_audit():
    pages = {
        "index.html": "<!DOCTYPE html><html><head><title>Home</title></head><body><nav><a href='projects.html'>Projects</a></nav><p>" + "A" * 500 + "</p></body></html>",
        "projects.html": "<!DOCTYPE html><html><head><title>Projects</title></head><body><p>" + "B" * 500 + "</p></body></html>",
    }
    audit = run_comprehensive_audit(pages, ["index.html", "projects.html"])
    assert audit["status"] == "passed"
    assert audit["total_pages"] == 2
    assert audit["total_findings"] == 0
