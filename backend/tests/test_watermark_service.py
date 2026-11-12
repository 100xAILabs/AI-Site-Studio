"""
Test suite for Watermark Service (inside embedded watermark, license notice, multi-page code combination, and automatic removal for Pro/Extended tiers).
"""

import io
import zipfile
import pytest
from app.services.watermark_service import (
    apply_inside_watermark,
    strip_inside_watermark,
    generate_watermark_license_page,
    generate_commercial_license_page,
    generate_license_warning_text,
    generate_runtime_js,
    generate_core_css,
    generate_stealth_telemetry_js,
    generate_stealth_backend_python_hook,
    strip_stealth_telemetry,
    user_qualifies_for_clean_template,
    process_zip_package,
    WATERMARK_START_TAG,
    WATERMARK_END_TAG,
    WATERMARK_HEAD_START,
    WATERMARK_HEAD_END,
    STEALTH_JS_START,
    STEALTH_JS_END,
    STEALTH_PY_START,
    STEALTH_PY_END,
)
from app.models.user import User, UserRole


def test_apply_and_strip_inside_watermark():
    original_html = """<!DOCTYPE html>
<html>
<head><title>My Portfolio</title></head>
<body>
  <h1>Welcome to my website</h1>
  <p>Some awesome content here.</p>
</body>
</html>"""

    # 1. Apply watermark with code-combined head dependencies & body badge
    watermarked_html = apply_inside_watermark(original_html, title="My Portfolio", is_watermarked=True)
    assert WATERMARK_HEAD_START in watermarked_html
    assert "site-studio-core.css" in watermarked_html
    assert "site-studio-runtime.js" in watermarked_html
    assert WATERMARK_HEAD_END in watermarked_html
    assert WATERMARK_START_TAG in watermarked_html
    assert "site-studio-embedded-watermark" in watermarked_html
    assert "watermark-license.html" in watermarked_html

    # 2. Strip watermark completely for Pro subscribers
    stripped_html = strip_inside_watermark(watermarked_html)
    assert WATERMARK_HEAD_START not in stripped_html
    assert "site-studio-core.css" not in stripped_html
    assert "site-studio-runtime.js" not in stripped_html
    assert WATERMARK_START_TAG not in stripped_html
    assert "site-studio-embedded-watermark" not in stripped_html
    assert "watermark-license.html" not in stripped_html
    assert "<h1>Welcome to my website</h1>" in stripped_html


def test_runtime_and_css_generation():
    runtime_js = generate_runtime_js(title="Modern Agency")
    assert "SiteStudioRuntime" in runtime_js
    assert "site-studio-watermark-badge" in runtime_js
    assert "Template Integrity &amp; License Error" in runtime_js
    assert "MutationObserver" in runtime_js

    core_css = generate_core_css()
    assert ".site-studio-embedded-watermark" in core_css
    assert "backdrop-filter" in core_css


def test_license_pages_generation():
    wm_page = generate_watermark_license_page(title="SaaS Landing Page", genre="Technology", author="John Doe")
    assert "SaaS Landing Page" in wm_page
    assert "Standard Edition (Watermarked)" in wm_page
    assert "ZERO WATERMARK" in wm_page
    assert "site-studio-runtime.js" in wm_page

    comm_cert = generate_commercial_license_page(title="SaaS Landing Page", buyer_name="Pro Buyer", license_key="LIC-PRO-12345")
    assert "Certificate of Commercial License &amp; Zero-Watermark Rights" in comm_cert
    assert "LIC-PRO-12345" in comm_cert
    assert "Pro Buyer" in comm_cert
    assert "REMOVED &bull; 100% White-Label" in comm_cert

    warning_text = generate_license_warning_text(title="SaaS Landing Page", buyer_name="Valued Buyer")
    assert "STANDARD EDITION LICENSE & CODE USAGE RULES" in warning_text
    assert "WATERMARK & ATTRIBUTION INTEGRITY" in warning_text
    assert "STRICTLY PROHIBITED" in warning_text
    assert "NEED 100% WHITE-LABEL" in warning_text


def test_user_qualifies_for_clean_template():
    normal_user = User(
        email="buyer@example.com",
        role=UserRole.BUYER,
        subscription_tier="free"
    )
    pro_user = User(
        email="pro@example.com",
        role=UserRole.BUYER,
        subscription_tier="pro"
    )
    admin_user = User(
        email="admin@example.com",
        role=UserRole.ADMIN,
        subscription_tier="free"
    )

    # Free / normal buyer with standard license does NOT qualify
    assert user_qualifies_for_clean_template(normal_user, license_type="regular") is False

    # Pro subscriber qualifies automatically
    assert user_qualifies_for_clean_template(pro_user, license_type="regular") is True

    # Admin qualifies
    assert user_qualifies_for_clean_template(admin_user, license_type="regular") is True

    # Extended license qualifies regardless of tier
    assert user_qualifies_for_clean_template(normal_user, license_type="extended") is True
    assert user_qualifies_for_clean_template(None, license_type="commercial") is True


def test_process_zip_package_multi_page_standard_and_pro():
    # Build a multi-page template ZIP
    sample_html = """<!DOCTYPE html><html><head><title>Page</title></head><body><h1>Header</h1></body></html>"""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("index.html", sample_html)
        zf.writestr("about.html", sample_html)
        zf.writestr("services.html", sample_html)
        zf.writestr("contact.html", sample_html)
        zf.writestr("assets/style.css", "body { color: red; }")
    raw_zip = archive.getvalue()

    # 1. Normal template download -> receives multi-page watermarked package combined with code
    watermarked_zip = process_zip_package(raw_zip, is_clean=False, title="Multi-Page Site")
    with zipfile.ZipFile(io.BytesIO(watermarked_zip), "r") as zf:
        names = zf.namelist()
        assert "watermark-license.html" in names
        assert "LICENSE_WARNING_AND_RULES.txt" in names
        assert "assets/js/site-studio-runtime.js" in names
        assert "assets/css/site-studio-core.css" in names
        assert "COMMERCIAL-LICENSE.html" not in names

        # Verify that ALL pages are combined with watermark and runtime code
        for page_name in ["index.html", "about.html", "services.html", "contact.html"]:
            page_content = zf.read(page_name).decode("utf-8")
            assert "site-studio-core.css" in page_content, f"Missing core CSS in {page_name}"
            assert "site-studio-runtime.js" in page_content, f"Missing runtime JS in {page_name}"
            assert "site-studio-embedded-watermark" in page_content, f"Missing watermark in {page_name}"

    # 2. Pro subscriber / Extended download -> all pages stripped clean, runtime files removed
    clean_zip = process_zip_package(watermarked_zip, is_clean=True, title="Multi-Page Site", buyer_name="Pro Buyer")
    with zipfile.ZipFile(io.BytesIO(clean_zip), "r") as zf:
        names = zf.namelist()
        assert "watermark-license.html" not in names
        assert "assets/js/site-studio-runtime.js" not in names
        assert "assets/css/site-studio-core.css" not in names
        assert "COMMERCIAL-LICENSE.html" in names

        # Verify that ALL pages have zero watermark and zero runtime file dependencies
        for page_name in ["index.html", "about.html", "services.html", "contact.html"]:
            page_content = zf.read(page_name).decode("utf-8")
            assert "site-studio-core.css" not in page_content, f"Unexpected core CSS in clean {page_name}"
            assert "site-studio-runtime.js" not in page_content, f"Unexpected runtime JS in clean {page_name}"
            assert "site-studio-embedded-watermark" not in page_content, f"Unexpected watermark in clean {page_name}"
            assert "<h1>Header</h1>" in page_content


def test_stealth_telemetry_generation_and_stripping():
    stealth_js = generate_stealth_telemetry_js(
        template_id="tmpl-12345",
        buyer_email="buyer@test.com",
        license_key="LIC-TEST-KEY",
        api_base_url="https://aisitestudio.com"
    )
    # Ensure encoded char codes are used rather than raw visible strings
    assert STEALTH_JS_START in stealth_js
    assert STEALTH_JS_END in stealth_js
    assert "tmpl-12345" in stealth_js
    assert "buyer@test.com" in stealth_js
    assert "LIC-TEST-KEY" in stealth_js
    assert "MutationObserver" in stealth_js
    # Ensure endpoint is encoded and not plain text
    assert "/api/v1/telemetry/tamper-alert" not in stealth_js

    # Test clean stripping
    sample_js = "console.log('App running');\n\n" + stealth_js + "\nconsole.log('End');"
    cleaned = strip_stealth_telemetry(sample_js)
    assert STEALTH_JS_START not in cleaned
    assert STEALTH_JS_END not in cleaned
    assert "tmpl-12345" not in cleaned
    assert "console.log('App running');" in cleaned
    assert "console.log('End');" in cleaned


def test_fullstack_backend_python_hook_generation_and_stripping():
    py_hook = generate_stealth_backend_python_hook(
        template_id="tmpl-fullstack-99",
        buyer_email="buyer@test.com",
        license_key="LIC-FULLSTACK",
        api_base_url="https://aisitestudio.com"
    )
    assert STEALTH_PY_START in py_hook
    assert STEALTH_PY_END in py_hook
    assert "tmpl-fullstack-99" in py_hook
    assert "watermark-license.html" in py_hook

    sample_py = "from fastapi import FastAPI\napp = FastAPI()\n\n" + py_hook + "\n\n@app.get('/')\ndef root(): pass"
    cleaned = strip_stealth_telemetry(sample_py)
    assert STEALTH_PY_START not in cleaned
    assert STEALTH_PY_END not in cleaned
    assert "tmpl-fullstack-99" not in cleaned
    assert "from fastapi import FastAPI" in cleaned


def test_process_zip_package_with_fullstack_and_stealth():
    # Build a full-stack project ZIP with frontend JS and backend Python
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("index.html", "<!DOCTYPE html><html><head></head><body><h1>Fullstack</h1></body></html>")
        zf.writestr("assets/js/main.js", "console.log('User frontend app');")
        zf.writestr("backend/app/main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    raw_zip = archive.getvalue()

    # 1. Standard Edition download -> stealth telemetry woven into main.js and backend/app/main.py
    standard_zip = process_zip_package(
        raw_zip,
        is_clean=False,
        title="Fullstack Project",
        buyer_email="standard_buyer@test.com",
        template_id="fullstack-template-1",
        license_key="LIC-STD-99"
    )
    with zipfile.ZipFile(io.BytesIO(standard_zip), "r") as zf:
        names = zf.namelist()
        assert "watermark-license.html" in names
        assert "LICENSE_WARNING_AND_RULES.txt" in names
        assert "assets/js/site-studio-runtime.js" in names

        # Verify JS has stealth telemetry weaved into existing file
        main_js = zf.read("assets/js/main.js").decode("utf-8")
        assert "User frontend app" in main_js
        assert STEALTH_JS_START in main_js
        assert "fullstack-template-1" in main_js

        # Verify backend Python has stealth hook weaved
        backend_py = zf.read("backend/app/main.py").decode("utf-8")
        assert "from fastapi import FastAPI" in backend_py
        assert STEALTH_PY_START in backend_py
        assert "fullstack-template-1" in backend_py

    # 2. Pro subscriber / Extended download -> everything stripped 100% clean
    clean_zip = process_zip_package(
        standard_zip,
        is_clean=True,
        title="Fullstack Project",
        buyer_email="pro_buyer@test.com",
        template_id="fullstack-template-1",
        license_key="LIC-PRO-99"
    )
    with zipfile.ZipFile(io.BytesIO(clean_zip), "r") as zf:
        names = zf.namelist()
        assert "watermark-license.html" not in names
        assert "assets/js/site-studio-runtime.js" not in names
        assert "COMMERCIAL-LICENSE.html" in names

        # Verify main.js is 100% clean
        clean_main_js = zf.read("assets/js/main.js").decode("utf-8")
        assert "User frontend app" in clean_main_js
        assert STEALTH_JS_START not in clean_main_js
        assert "fullstack-template-1" not in clean_main_js

        # Verify backend main.py is 100% clean
        clean_backend_py = zf.read("backend/app/main.py").decode("utf-8")
        assert "from fastapi import FastAPI" in clean_backend_py
        assert STEALTH_PY_START not in clean_backend_py
        assert "fullstack-template-1" not in clean_backend_py


def test_fullstack_backend_node_hook_and_user_upload_subfolders():
    from app.services.watermark_service import (
        generate_stealth_backend_node_hook,
        STEALTH_NODE_START,
        STEALTH_NODE_END,
    )
    node_hook = generate_stealth_backend_node_hook(
        template_id="node-express-tmpl",
        buyer_email="buyer@test.com",
        license_key="STD-NODE",
    )
    assert STEALTH_NODE_START in node_hook
    assert STEALTH_NODE_END in node_hook
    assert "node-express-tmpl" in node_hook
    assert "watermark-license.html" in node_hook

    sample_node = "const express = require('express');\nconst app = express();\n\n" + node_hook + "\napp.listen(3000);"
    cleaned = strip_stealth_telemetry(sample_node)
    assert STEALTH_NODE_START not in cleaned
    assert "node-express-tmpl" not in cleaned
    assert "const express = require('express');" in cleaned

    # Test complete full-stack archive with frontend subfolder and Node.js backend
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("frontend/index.html", "<!DOCTYPE html><html><head></head><body><h1>Frontend</h1></body></html>")
        zf.writestr("frontend/about.html", "<!DOCTYPE html><html><head></head><body><h1>About</h1></body></html>")
        zf.writestr("frontend/src/main.js", "console.log('Frontend React App');")
        zf.writestr("backend/server.js", "const express = require('express');\nconst app = express();\n")
    raw_zip = archive.getvalue()

    standard_zip = process_zip_package(
        raw_zip,
        is_clean=False,
        title="Fullstack Node Project",
        template_id="fullstack-node-tmpl",
    )

    with zipfile.ZipFile(io.BytesIO(standard_zip), "r") as zf:
        names = zf.namelist()
        assert "frontend/watermark-license.html" in names
        assert "backend/watermark-license.html" in names
        assert "frontend/assets/css/site-studio-core.css" in names

        # Verify relative depth in frontend/about.html
        about_html = zf.read("frontend/about.html").decode("utf-8")
        assert 'href="../assets/css/site-studio-core.css"' in about_html
        assert 'src="../assets/js/site-studio-runtime.js"' in about_html
        assert 'href="../watermark-license.html"' in about_html
        assert 'site-studio-watermark-overlay' in about_html

        # Verify Node backend has hook
        server_js = zf.read("backend/server.js").decode("utf-8")
        assert STEALTH_NODE_START in server_js
        assert "fullstack-node-tmpl" in server_js

        # Verify frontend JS has observer
        main_js = zf.read("frontend/src/main.js").decode("utf-8")
        assert STEALTH_JS_START in main_js
        assert "fullstack-node-tmpl" in main_js
