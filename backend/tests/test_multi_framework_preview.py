"""
Comprehensive tests for Multi-Framework Live Preview & Demo Runner.
Verifies React 18 (single & multi-component), Vue 3 (single & multi-component with script setup),
Angular, Svelte, Static HTML multi-page, and asset delivery from src/assets.
"""

import os
import uuid
import pytest
import tempfile
from pathlib import Path
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import make_preview_token
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.template import Template, TemplateStatus, TemplateFramework


@pytest.fixture
async def seller_user(db: AsyncSession):
    user = User(
        email=f"multi_fw_seller_{uuid.uuid4().hex[:8]}@example.com",
        username=f"fw_seller_{uuid.uuid4().hex[:8]}",
        full_name="Framework Seller",
        role=UserRole.SELLER,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def sample_category(db: AsyncSession):
    cat = Category(name=f"FW Category {uuid.uuid4().hex[:6]}", slug=f"fw-cat-{uuid.uuid4().hex[:6]}")
    db.add(cat)
    await db.flush()
    return cat


@pytest.mark.asyncio
async def test_react_multi_component_preview_runner(client: AsyncClient, db: AsyncSession, seller_user, sample_category):
    """
    Verify React 18 multi-component project runs seamlessly via in-browser runner.
    Ensures subcomponents (Navbar.jsx, Hero.jsx, Footer.jsx) assemble without
    'Identifier PageComponent has already been declared' redeclaration syntax errors.
    """
    tmpl_id = uuid.uuid4()
    preview_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(tmpl_id)
    preview_dir.mkdir(parents=True, exist_ok=True)
    comp_dir = preview_dir / "components"
    comp_dir.mkdir(exist_ok=True)

    # Subcomponent 1: Navbar
    (comp_dir / "Navbar.jsx").write_text("""
import React from 'react';
export default function Navbar() {
    return <nav className="p-4 bg-slate-900 text-white"><h2>CloudPulse</h2></nav>;
}
""", encoding="utf-8")

    # Subcomponent 2: Hero
    (comp_dir / "Hero.jsx").write_text("""
import React from 'react';
export default function Hero() {
    return <section className="py-16 text-center"><h1>Scale Your Cloud 10x</h1></section>;
}
""", encoding="utf-8")

    # Primary App component importing and using subcomponents
    (preview_dir / "App.jsx").write_text("""
import React, { useState } from 'react';
import Navbar from './components/Navbar';
import Hero from './components/Hero';

export default function App() {
    const [active, setActive] = useState(true);
    return (
        <div className="min-h-screen bg-slate-950 text-white">
            <Navbar />
            <Hero />
            <p>Status: {active ? 'Online' : 'Offline'}</p>
        </div>
    );
}
""", encoding="utf-8")

    template = Template(
        id=tmpl_id,
        seller_id=seller_user.id,
        title="CloudPulse React SaaS",
        slug=f"cloudpulse-react-{uuid.uuid4().hex[:6]}",
        short_description="High-velocity cloud platform",
        description="Full multi-component React preview test",
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("49.00"),
        status=TemplateStatus.PUBLISHED,
        framework=TemplateFramework.REACT,
        category_id=sample_category.id,
    )
    db.add(template)
    await db.commit()

    res = await client.get(f"/api/v1/preview/live/{template.id}/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")

    html_content = res.text
    # Verify React 18, Babel, and Tailwind CDN are loaded
    assert "react.production.min.js" in html_content
    assert "babel.min.js" in html_content
    assert "tailwindcss.com" in html_content
    assert "CloudPulse React SaaS - Live Preview (React)" in html_content
    # Verify both subcomponents exist in the bundled script
    assert "var Navbar =" in html_content or "Navbar" in html_content
    assert "var Hero =" in html_content or "Hero" in html_content
    assert "window._components['Navbar']" in html_content
    assert "window._components['Hero']" in html_content


@pytest.mark.asyncio
async def test_vue_multi_component_script_setup_preview_runner(client: AsyncClient, db: AsyncSession, seller_user, sample_category):
    """
    Verify Vue 3 multi-component project with <script setup> runs live in demo/preview.
    Ensures subcomponents (Navbar.vue, Hero.vue) are registered on app.component,
    and declared setup variables/functions are exposed to the template.
    """
    tmpl_id = uuid.uuid4()
    preview_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(tmpl_id)
    preview_dir.mkdir(parents=True, exist_ok=True)
    comp_dir = preview_dir / "components"
    comp_dir.mkdir(exist_ok=True)

    # Subcomponent 1: Navbar.vue with router-link
    (comp_dir / "Navbar.vue").write_text("""
<template>
  <header class="flex justify-between p-4 bg-slate-900 text-white">
    <span class="font-bold">VuePulse</span>
    <router-link to="/pricing">Pricing</router-link>
  </header>
</template>
<script setup>
import { ref } from 'vue';
const navTitle = ref('VuePulse');
</script>
""", encoding="utf-8")

    # Primary App.vue with <script setup>, ref, and subcomponents
    (preview_dir / "App.vue").write_text("""
<template>
  <div class="min-h-screen bg-slate-950 text-white">
    <Navbar />
    <main class="p-8">
      <h1>{{ pageTitle }}</h1>
      <button @click="incrementCount">Count: {{ count }}</button>
    </main>
  </div>
</template>
<script setup>
import { ref } from 'vue';
import Navbar from './components/Navbar.vue';

const pageTitle = ref('Vue 3 NextGen Dashboard');
const count = ref(0);

function incrementCount() {
  count.value++;
}
</script>
<style>
.bg-slate-950 { background-color: #020617; }
</style>
""", encoding="utf-8")

    template = Template(
        id=tmpl_id,
        seller_id=seller_user.id,
        title="Vue 3 Dashboard Hub",
        slug=f"vue3-dashboard-{uuid.uuid4().hex[:6]}",
        short_description="Modern Vue 3 application",
        description="Full multi-component Vue preview test",
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("49.00"),
        status=TemplateStatus.PUBLISHED,
        framework=TemplateFramework.VUE,
        category_id=sample_category.id,
    )
    db.add(template)
    await db.commit()

    res = await client.get(f"/api/v1/preview/live/{template.id}/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")

    html_content = res.text
    # Verify Vue 3 runtime is loaded
    assert "vue@3/dist/vue.global.js" in html_content
    assert "tailwindcss.com" in html_content
    assert "Vue 3 Dashboard Hub - Live Preview (Vue)" in html_content
    # Verify Navbar subcomponent is registered
    assert "app.component('Navbar'" in html_content
    # Verify declared setup variables are returned in setup()
    assert "pageTitle" in html_content
    assert "count" in html_content
    assert "incrementCount" in html_content
    # Verify Vue Router stubs exist
    assert "RouterLinkMock" in html_content


@pytest.mark.asyncio
async def test_angular_universal_standalone_runner(client: AsyncClient, db: AsyncSession, seller_user, sample_category):
    """
    Verify Angular project templates render cleanly via the Angular Universal runner.
    """
    tmpl_id = uuid.uuid4()
    preview_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(tmpl_id)
    preview_dir.mkdir(parents=True, exist_ok=True)
    app_dir = preview_dir / "src" / "app"
    app_dir.mkdir(parents=True, exist_ok=True)

    (app_dir / "app.component.html").write_text("""
<div class="angular-hero p-8 bg-indigo-950 text-white">
  <h1>{{ title }}</h1>
  <p>Engineered with Angular Enterprise Architecture</p>
  <a [routerLink]="['/services']" class="btn">Explore Services</a>
</div>
""", encoding="utf-8")

    (app_dir / "app.component.ts").write_text("""
import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'Angular Enterprise Platform';
}
""", encoding="utf-8")

    template = Template(
        id=tmpl_id,
        seller_id=seller_user.id,
        title="Angular Enterprise Platform",
        slug=f"angular-platform-{uuid.uuid4().hex[:6]}",
        short_description="Enterprise Angular template",
        description="Angular standalone preview test",
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("49.00"),
        status=TemplateStatus.PUBLISHED,
        framework=TemplateFramework.ANGULAR,
        category_id=sample_category.id,
    )
    db.add(template)
    await db.commit()

    res = await client.get(f"/api/v1/preview/live/{template.id}/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")

    html_content = res.text
    assert "<app-root>" in html_content
    assert "Angular Enterprise Platform" in html_content
    assert "Engineered with Angular Enterprise Architecture" in html_content


@pytest.mark.asyncio
async def test_svelte_standalone_preview_runner(client: AsyncClient, db: AsyncSession, seller_user, sample_category):
    """
    Verify Svelte templates render cleanly via the in-browser Svelte runner.
    """
    tmpl_id = uuid.uuid4()
    preview_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(tmpl_id)
    preview_dir.mkdir(parents=True, exist_ok=True)
    src_dir = preview_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "App.svelte").write_text("""
<script>
  let brand = 'SvelteFlow Velocity';
  let metric = 99.98;
</script>

<div class="p-8 bg-slate-900 text-white min-h-screen">
  <h1>{brand}</h1>
  <p>System Uptime Performance: {metric}%</p>
  <button class="px-4 py-2 bg-emerald-500 rounded">Explore Telemetry</button>
</div>

<style>
  h1 { font-weight: 800; font-size: 2rem; }
</style>
""", encoding="utf-8")

    template = Template(
        id=tmpl_id,
        seller_id=seller_user.id,
        title="SvelteFlow Velocity",
        slug=f"svelteflow-velocity-{uuid.uuid4().hex[:6]}",
        short_description="Ultra fast Svelte app",
        description="Svelte standalone preview test",
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("49.00"),
        status=TemplateStatus.PUBLISHED,
        framework=TemplateFramework.SVELTE,
        category_id=sample_category.id,
    )
    db.add(template)
    await db.commit()

    res = await client.get(f"/api/v1/preview/live/{template.id}/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")

    html_content = res.text
    assert "svelte@3/compiler.js" in html_content
    assert "SvelteFlow Velocity" in html_content
    assert "System Uptime Performance" in html_content


@pytest.mark.asyncio
async def test_static_html_multi_page_and_src_assets(client: AsyncClient, db: AsyncSession, seller_user, sample_category):
    """
    Verify Static HTML multi-page projects serve relative subpages (about.html)
    and static assets (e.g. logo.png in src/assets/) without 404 blocking.
    """
    tmpl_id = uuid.uuid4()
    preview_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(tmpl_id)
    preview_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = preview_dir / "src" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 1. Main index.html
    (preview_dir / "index.html").write_text("""
<!DOCTYPE html>
<html>
<head><title>Apex Landing</title></head>
<body>
  <h1>Apex Creative Flagship</h1>
  <a href="about.html">About Us</a>
  <img src="src/assets/logo.png" alt="Logo" />
</body>
</html>
""", encoding="utf-8")

    # 2. Subpage about.html
    (preview_dir / "about.html").write_text("""
<!DOCTYPE html>
<html>
<head><title>About Apex</title></head>
<body>
  <h1>About Our Senior Design Pod</h1>
</body>
</html>
""", encoding="utf-8")

    # 3. Static image asset in src/assets/logo.png (1x1 valid transparent PNG)
    png_bytes = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,
        0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
        0x42, 0x60, 0x82
    ])
    (assets_dir / "logo.png").write_bytes(png_bytes)

    template = Template(
        id=tmpl_id,
        seller_id=seller_user.id,
        title="Apex Creative HTML",
        slug=f"apex-creative-html-{uuid.uuid4().hex[:6]}",
        short_description="Static HTML creative agency",
        description="Multi-page HTML and asset delivery test",
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("49.00"),
        status=TemplateStatus.PUBLISHED,
        framework=TemplateFramework.HTML,
        category_id=sample_category.id,
    )
    db.add(template)
    await db.commit()

    # 1. Root index.html request
    res_root = await client.get(f"/api/v1/preview/live/{template.id}/")
    assert res_root.status_code == 200
    assert "Apex Creative Flagship" in res_root.text

    # 2. Subpage about.html request
    res_about = await client.get(f"/api/v1/preview/live/{template.id}/about.html")
    assert res_about.status_code == 200
    assert "About Our Senior Design Pod" in res_about.text

    # 3. Static asset in src/assets/logo.png request: MUST succeed and serve image/png (not 404 blocked)
    res_asset = await client.get(f"/api/v1/preview/live/{template.id}/src/assets/logo.png")
    assert res_asset.status_code == 200
    assert "image/png" in res_asset.headers.get("content-type", "")
    assert res_asset.content == png_bytes
