"""
Database seed script — creates 10 categories and 100 sample templates.

Usage:
    cd backend
    python scripts/seed.py

Requirements: DATABASE_URL must be set (or .env file present).
"""

import asyncio
import sys
import os
import uuid
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models import *  # noqa — registers all models with Base


# ── Sample Data Definitions ───────────────────────────────────────────────────

CATEGORIES = [
    {"name": "Business", "slug": "business", "icon": "Briefcase", "color": "#6366f1", "description": "Professional business and corporate templates"},
    {"name": "E-Commerce", "slug": "ecommerce", "icon": "ShoppingCart", "color": "#8b5cf6", "description": "Online store and shopping templates"},
    {"name": "Portfolio", "slug": "portfolio", "icon": "Palette", "color": "#ec4899", "description": "Creative portfolio and personal brand templates"},
    {"name": "Restaurant", "slug": "restaurant", "icon": "UtensilsCrossed", "color": "#f59e0b", "description": "Food, cafe, and restaurant templates"},
    {"name": "Healthcare", "slug": "healthcare", "icon": "Heart", "color": "#10b981", "description": "Medical, clinic, and wellness templates"},
    {"name": "Real Estate", "slug": "real-estate", "icon": "Home", "color": "#3b82f6", "description": "Property listing and real estate templates"},
    {"name": "Education", "slug": "education", "icon": "GraduationCap", "color": "#14b8a6", "description": "Course, LMS, and education templates"},
    {"name": "Technology", "slug": "technology", "icon": "Cpu", "color": "#f43f5e", "description": "SaaS, startup, and tech product templates"},
    {"name": "Travel", "slug": "travel", "icon": "Plane", "color": "#06b6d4", "description": "Travel agency, hotel, and tourism templates"},
    {"name": "Agency", "slug": "agency", "icon": "Building2", "color": "#a855f7", "description": "Creative agency and studio templates"},
]

# Template pool — 10 per category (will be repeated with variation)
TEMPLATE_POOL = [
    # Business
    ("Nexus Pro", "business", "A premium business template with a professional layout", 49, True, True),
    ("CorporatePeak", "business", "Corporate website for enterprises", 59, True, False),
    ("Boardroom", "business", "Executive-level business presentation", 39, False, True),
    ("Momentum", "business", "Modern business landing page", 29, True, True),
    ("Pinnacle", "business", "Premium consulting firm template", 79, True, False),
    ("Stratos", "business", "Startup business template", 19, True, True),
    ("Veritas", "business", "Legal and professional services", 49, False, False),
    ("Elevate", "business", "Business portfolio and services", 39, True, True),
    ("Meridian", "business", "Global business and consulting", 59, True, False),
    ("Apex", "business", "Corporate SaaS landing page", 69, True, True),
    # E-Commerce
    ("ShopVibe", "ecommerce", "Modern e-commerce storefront", 89, True, True),
    ("CartFlow", "ecommerce", "Minimal online shop template", 69, True, False),
    ("StoreX", "ecommerce", "Multi-vendor marketplace", 99, True, True),
    ("Luxe Shop", "ecommerce", "Luxury goods e-commerce", 129, False, False),
    ("QuickBuy", "ecommerce", "Fast checkout e-commerce template", 49, True, True),
    ("FreshMarket", "ecommerce", "Grocery and organic store", 59, True, False),
    ("TechStore", "ecommerce", "Electronics and gadgets shop", 79, True, True),
    ("FashionHub", "ecommerce", "Fashion and clothing store", 89, False, True),
    ("PetShop", "ecommerce", "Pet supplies online store", 49, True, False),
    ("BookHaven", "ecommerce", "Online bookstore template", 39, True, True),
    # Portfolio
    ("ArtBoard", "portfolio", "Creative artist portfolio", 29, True, True),
    ("PixelCraft", "portfolio", "Photography portfolio template", 39, True, False),
    ("Designio", "portfolio", "UI/UX designer portfolio", 49, True, True),
    ("StudioReel", "portfolio", "Video and motion portfolio", 59, False, True),
    ("Showcase", "portfolio", "Minimal personal portfolio", 19, True, False),
    ("Canvas", "portfolio", "Painter and illustrator portfolio", 29, True, True),
    ("Luminate", "portfolio", "Creative agency portfolio", 69, True, False),
    ("Folio", "portfolio", "Freelancer showcase template", 39, True, True),
    ("Aura", "portfolio", "Branding and identity portfolio", 49, False, False),
    ("Sketch", "portfolio", "Architecture portfolio", 59, True, True),
    # Restaurant
    ("Gastro", "restaurant", "Fine dining restaurant template", 59, True, True),
    ("CafeBliss", "restaurant", "Coffee shop and cafe template", 39, True, False),
    ("PizzaTime", "restaurant", "Pizza and fast food template", 29, True, True),
    ("SushiBar", "restaurant", "Japanese restaurant template", 49, False, True),
    ("Brunch", "restaurant", "Brunch cafe template", 39, True, False),
    ("FoodTruck", "restaurant", "Food truck and street food", 29, True, True),
    ("Bakehouse", "restaurant", "Bakery and pastry shop", 35, True, False),
    ("Vegan", "restaurant", "Plant-based restaurant template", 45, True, True),
    ("BBQ", "restaurant", "BBQ and grill restaurant", 39, False, False),
    ("IceCream", "restaurant", "Dessert and ice cream shop", 25, True, True),
    # Healthcare
    ("MediCare", "healthcare", "Medical clinic template", 79, True, True),
    ("DentaSmile", "healthcare", "Dental clinic template", 69, True, False),
    ("Wellness", "healthcare", "Health and wellness center", 59, True, True),
    ("PhysioFit", "healthcare", "Physiotherapy and rehab", 69, False, True),
    ("MindCare", "healthcare", "Mental health clinic template", 79, True, False),
    ("VetCare", "healthcare", "Veterinary clinic template", 49, True, True),
    ("Pharmacy", "healthcare", "Pharmacy and drug store", 59, True, False),
    ("Hospital", "healthcare", "Hospital and medical center", 99, False, True),
    ("NutriHealth", "healthcare", "Nutrition and dietitian clinic", 69, True, False),
    ("Yoga", "healthcare", "Yoga and meditation studio", 45, True, True),
    # Real Estate
    ("EstateView", "real-estate", "Property listing template", 89, True, True),
    ("Homely", "real-estate", "Home buying and selling template", 79, True, False),
    ("LuxRealty", "real-estate", "Luxury real estate template", 129, False, True),
    ("RentEase", "real-estate", "Rental property template", 69, True, False),
    ("UrbanSpaces", "real-estate", "Urban apartment template", 79, True, True),
    ("Propify", "real-estate", "Property management template", 89, False, False),
    ("OpenHouse", "real-estate", "Real estate agency template", 99, True, True),
    ("VillaLux", "real-estate", "Villa and luxury estate", 149, True, False),
    ("CommercialPro", "real-estate", "Commercial property template", 109, False, True),
    ("RealtyCo", "real-estate", "Real estate company template", 79, True, True),
    # Education
    ("EduLearn", "education", "Online course platform template", 99, True, True),
    ("KidsLearn", "education", "Children's education template", 69, True, False),
    ("CollegeHub", "education", "University and college template", 89, False, True),
    ("TutorPro", "education", "Private tutoring template", 59, True, False),
    ("LanguageLab", "education", "Language learning platform", 79, True, True),
    ("CodingAcademy", "education", "Coding bootcamp template", 99, True, False),
    ("MusicSchool", "education", "Music school and lessons", 69, True, True),
    ("ArtStudio", "education", "Art class and workshop", 59, False, True),
    ("Preschool", "education", "Preschool and kindergarten", 49, True, False),
    ("ELearning", "education", "E-learning and LMS template", 119, True, True),
    # Technology
    ("SaasKit", "technology", "SaaS product landing page", 99, True, True),
    ("AppLaunch", "technology", "Mobile app launch template", 79, True, False),
    ("StartupX", "technology", "Startup and product template", 89, True, True),
    ("DevPortal", "technology", "Developer tools and API", 69, False, True),
    ("CloudSaaS", "technology", "Cloud service platform", 109, True, False),
    ("AIProduct", "technology", "AI and ML product template", 119, True, True),
    ("CyberSec", "technology", "Cybersecurity company template", 99, False, False),
    ("TechBlog", "technology", "Tech blog and news template", 49, True, True),
    ("HardwareCo", "technology", "Hardware product template", 79, True, False),
    ("Fintech", "technology", "Fintech and banking app", 129, True, True),
    # Travel
    ("WanderLust", "travel", "Travel agency landing page", 69, True, True),
    ("HotelLux", "travel", "Hotel and resort template", 89, True, False),
    ("TourGuide", "travel", "Tour operator template", 59, True, True),
    ("AirTravel", "travel", "Flight booking template", 79, False, True),
    ("BackpackerBlog", "travel", "Travel blog template", 39, True, False),
    ("CruiseLine", "travel", "Cruise and maritime template", 99, True, True),
    ("SkiResort", "travel", "Ski and mountain resort", 89, False, False),
    ("BeachHotel", "travel", "Beach and tropical resort", 79, True, True),
    ("Nomad", "travel", "Digital nomad and remote work travel", 49, True, False),
    ("CityBreaks", "travel", "City tourism and experience", 59, True, True),
    # Agency
    ("CreativeAgency", "agency", "Full-service creative agency", 99, True, True),
    ("DesignStudio", "agency", "Design studio and branding", 89, True, False),
    ("MarketingPro", "agency", "Digital marketing agency", 79, True, True),
    ("PRAgency", "agency", "Public relations agency", 89, False, True),
    ("WebAgency", "agency", "Web development agency", 99, True, False),
    ("SEOAgency", "agency", "SEO and content agency", 69, True, True),
    ("VideoAgency", "agency", "Video production agency", 109, False, False),
    ("SocialMedia", "agency", "Social media management agency", 79, True, True),
    ("BrandAgency", "agency", "Brand strategy agency", 119, True, False),
    ("GrowthHQ", "agency", "Growth hacking agency", 89, True, True),
]

PICSUM_BASE = "https://picsum.photos/seed"
FRAMEWORKS = ["react", "nextjs", "html", "vue", "nuxt"]
INDUSTRIES = {
    "business": "Business & Corporate",
    "ecommerce": "Retail & E-Commerce",
    "portfolio": "Creative & Arts",
    "restaurant": "Food & Beverage",
    "healthcare": "Healthcare & Medical",
    "real-estate": "Real Estate & Property",
    "education": "Education & Training",
    "technology": "Technology & Software",
    "travel": "Travel & Tourism",
    "agency": "Marketing & Agency",
}


async def seed():
    print("[START] Seeding database...")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        # ── Categories ────────────────────────────────────────────────────────
        cat_map = {}
        for cat_data in CATEGORIES:
            from sqlalchemy import select as sa_select
            existing = (await db.execute(
                sa_select(Category).where(Category.slug == cat_data["slug"])
            )).scalar_one_or_none()

            if existing:
                cat_map[cat_data["slug"]] = existing
                print(f"  [EXISTING] Category already exists: {cat_data['name']}")
                continue

            cat = Category(
                name=cat_data["name"],
                slug=cat_data["slug"],
                icon=cat_data["icon"],
                color=cat_data["color"],
                description=cat_data["description"],
                is_active=True,
                is_featured=True,
                sort_order=CATEGORIES.index(cat_data),
            )
            db.add(cat)
            await db.flush()
            cat_map[cat_data["slug"]] = cat
            print(f"  [OK] Category: {cat_data['name']}")

        # ── Templates ─────────────────────────────────────────────────────────
        created = 0
        for i, (title, cat_slug, description, price, dark_mode, ai_ready) in enumerate(TEMPLATE_POOL):
            from sqlalchemy import select as sa_select
            slug = title.lower().replace(" ", "-").replace("&", "and")
            existing = (await db.execute(
                sa_select(Template).where(Template.slug == slug)
            )).scalar_one_or_none()
            if existing:
                continue

            category = cat_map.get(cat_slug)
            if not category:
                continue

            seed_id = i + 42
            framework = FRAMEWORKS[i % len(FRAMEWORKS)]
            pages = (i % 8) + 3  # 3–10 pages
            downloads = (i * 37 + 100) % 5000
            rating_avg = round(3.5 + (i % 15) * 0.1, 1)
            rating_count = (i * 13 + 5) % 500

            template = Template(
                title=title,
                slug=slug,
                short_description=f"{description}. Built with {framework.upper()}.",
                description=f"""
## {title}

{description}

### Features
- Fully responsive design (Desktop, Tablet, Mobile)
- {'Dark mode support' if dark_mode else 'Clean light mode'}
- {'AI-ready with content generation support' if ai_ready else 'Standard template'}
- {pages} pre-built pages
- Built with {framework.upper()}
- Clean, maintainable code
- 1 year of free updates
- Detailed documentation

### What's Included
- Source code ({framework})
- HTML version
- Design files
- Documentation
                """.strip(),
                price=Decimal(str(price)),
                original_price=Decimal(str(int(price * 1.4))) if i % 3 == 0 else None,
                is_free=False,
                is_on_sale=i % 3 == 0,
                thumbnail_url=f"{PICSUM_BASE}/{seed_id}/800/500",
                preview_url=f"https://preview.aisitestudio.com/{slug}",
                video_url=None,
                gallery_images=[
                    f"{PICSUM_BASE}/{seed_id + 1}/1200/800",
                    f"{PICSUM_BASE}/{seed_id + 2}/1200/800",
                    f"{PICSUM_BASE}/{seed_id + 3}/1200/800",
                ],
                category_id=category.id,
                tags=[cat_slug, framework, INDUSTRIES[cat_slug].lower()],
                industry=INDUSTRIES[cat_slug],
                color_scheme="blue" if i % 4 == 0 else ("purple" if i % 4 == 1 else ("green" if i % 4 == 2 else "orange")),
                framework=TemplateFramework(framework),
                pages_count=pages,
                has_dark_mode=dark_mode,
                is_responsive=True,
                is_rtl_supported=i % 10 == 0,
                is_ai_ready=ai_ready,
                compatibility=["Chrome", "Firefox", "Safari", "Edge"],
                version="1.0.0",
                license_type=TemplateLicense.REGULAR,
                status=TemplateStatus.PUBLISHED,
                is_featured=i % 5 == 0,
                is_bestseller=i % 7 == 0,
                is_new=i > 80,
                downloads_count=downloads,
                views_count=downloads * 8,
                likes_count=downloads // 5,
                rating_avg=rating_avg,
                rating_count=rating_count,
                developer_name=["Alex Chen", "Maria Santos", "Jamal Williams", "Priya Patel", "Tom Brooks"][i % 5],
                developer_avatar=f"{PICSUM_BASE}/avatar-{i % 20}/100/100",
                included_pages=["Home", "About", "Services", "Contact", "Blog"][:pages],
                seo_keywords=[title.lower(), cat_slug, framework, "template", "website"],
                download_assets={
                    "react": f"https://downloads.aisitestudio.com/{slug}/react.zip",
                    "html": f"https://downloads.aisitestudio.com/{slug}/html.zip",
                    "zip": f"https://downloads.aisitestudio.com/{slug}/full.zip",
                },
            )
            db.add(template)
            created += 1

        await db.commit()
        print(f"\n[SUCCESS] Seed complete! Created {created} templates across {len(cat_map)} categories.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
