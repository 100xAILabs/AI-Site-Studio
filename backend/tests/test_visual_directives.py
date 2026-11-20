"""
Test Suite for Phase 9: Premium Visual Generation Directives.
Tests:
- UI Designer Agent design system normalization (Premium Dark Luxe vs Clean Modern SaaS)
- Visual token guarantees (glow_accent, card_border, card_shadow, fluid clamps, 44px touch targets)
- Architect Agent page manifest visual directives embedding
- Studio code generation rules compliance
"""

import pytest
from app.services.studio_service import _normalize_design_system, STUDIO_CLINERULES
from app.services.architect_agent import architect_agent


class TestDesignSystemNormalization:
    """Tests UI Designer Agent design tokens and aesthetic archetypes."""

    def test_dark_luxe_archetype_for_tech_and_creative(self):
        ds = _normalize_design_system(
            raw={},
            category="portfolio",
            genre="creative",
            prompt="Design a dark luxury cyberpunk portfolio for an AI engineer"
        )
        assert ds["aesthetic_direction"] == "dark_luxe"
        assert ds["background"].startswith("#")
        assert "glow_accent" in ds
        assert "rgba" in ds["glow_accent"]
        assert "card_border" in ds
        assert "card_shadow" in ds
        assert "clamp(" in ds["fluid_heading_clamp"]
        assert "clamp(" in ds["fluid_body_clamp"]
        assert ds["min_touch_target"] == "44px"

    def test_clean_saas_archetype_for_business_and_commerce(self):
        ds = _normalize_design_system(
            raw={},
            category="business",
            genre="b2b_saas",
            prompt="Build a clean modern B2B analytics platform for teams"
        )
        assert ds["aesthetic_direction"] == "clean_saas"
        assert ds["background"] == "#FFFFFF"
        assert ds["text"] == "#0F172A"
        assert "card_border" in ds
        assert "card_shadow" in ds
        assert "clamp(" in ds["fluid_heading_clamp"]
        assert ds["min_touch_target"] == "44px"

    def test_preserves_custom_llm_colors_while_filling_visual_tokens(self):
        custom_raw = {
            "primary": "#FF5722",
            "accent": "#4CAF50",
            "heading_font": "Space Grotesk, sans-serif",
        }
        ds = _normalize_design_system(
            raw=custom_raw,
            category="agency",
            genre="creative",
            prompt="Design studio agency"
        )
        # Custom colors should be preserved
        assert ds["primary"] == "#FF5722"
        assert ds["accent"] == "#4CAF50"
        assert ds["heading_font"] == "Space Grotesk, sans-serif"
        # Missing visual tokens should be automatically supplied
        assert "glow_accent" in ds
        assert "card_border" in ds
        assert "card_shadow" in ds
        assert "fluid_heading_clamp" in ds
        assert ds["min_touch_target"] == "44px"


class TestArchitectAgentVisualDirectives:
    """Tests Architect Agent embedding of visual directives into project manifests."""

    @pytest.mark.asyncio
    async def test_manifest_embeds_visual_directive_on_every_page(self):
        plan = {
            "title": "Neon Agency",
            "pages": [
                {"name": "Home", "filename": "index.html", "purpose": "Entrance portal"},
                {"name": "Work", "filename": "projects.html", "purpose": "Showcase"},
                {"name": "Contact", "filename": "contact.html", "purpose": "Booking inquiry"},
            ]
        }
        manifest = await architect_agent.design_manifest(
            prompt="Build a dark luxe portfolio agency",
            category="agency",
            genre="creative",
            plan=plan,
            design="{}",
            answers={"business_name": "Neon Agency"},
            stack="html-css-js"
        )

        assert "pages" in manifest
        assert len(manifest["pages"]) == 3
        for page in manifest["pages"]:
            assert "visual_directive" in page
            vd = page["visual_directive"]
            assert "clamp(" in vd["fluid_heading_clamp"]
            assert "clamp(" in vd["fluid_body_clamp"]
            assert vd["min_touch_target"] == "44px"
            assert vd["zero_horizontal_overflow"] is True
            assert vd["mobile_breakpoint"] == "768px"

    def test_fallback_manifest_contains_visual_directives(self):
        plan = {
            "title": "Clean Clinic",
            "pages": [
                {"name": "Home", "filename": "index.html", "purpose": "Home"},
                {"name": "Services", "filename": "services.html", "purpose": "Services"},
            ]
        }
        manifest = architect_agent._build_fallback_manifest(
            prompt="Medical clinic",
            category="medical",
            genre="clinic",
            plan=plan,
            answers={"business_name": "Clean Clinic"},
            stack="html-css-js"
        )

        for page in manifest["pages"]:
            assert "visual_directive" in page
            assert page["visual_directive"]["min_touch_target"] == "44px"
            assert page["visual_directive"]["zero_horizontal_overflow"] is True


class TestStudioRulesVisualDirectives:
    """Tests that STUDIO_CLINERULES contains Phase 9 directives."""

    def test_studio_rules_contains_phase_9_guidance(self):
        assert "MODERN AESTHETIC DIRECTIVES" in STUDIO_CLINERULES
        assert "Premium Dark Luxe" in STUDIO_CLINERULES
        assert "Clean Modern SaaS" in STUDIO_CLINERULES
        assert "Multi-Breakpoint Fluid Grids" in STUDIO_CLINERULES
        assert "clamp()" in STUDIO_CLINERULES
        assert "44px" in STUDIO_CLINERULES
