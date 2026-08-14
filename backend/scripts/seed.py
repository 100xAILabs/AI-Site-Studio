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

# Template pool — (title, cat_slug, description, price, dark_mode, ai_ready, sub_category)
TEMPLATE_POOL = [
    # Business
    ("Nexus Pro",         "business", "A premium business template with a professional layout", 49, True,  True,  "Corporate"),
    ("CorporatePeak",     "business", "Corporate website for enterprises",                       59, True,  False, "Corporate"),
    ("Boardroom",         "business", "Executive-level business presentation",                   39, False, True,  "Enterprise"),
    ("Momentum",          "business", "Modern business landing page",                            29, True,  True,  "Startup"),
    ("Pinnacle",          "business", "Premium consulting firm template",                        79, True,  False, "Consulting"),
    ("Stratos",           "business", "Startup business template",                              19, True,  True,  "Startup"),
    ("Veritas",           "business", "Legal and professional services",                        49, False, False, "Small Business"),
    ("Elevate",           "business", "Business portfolio and services",                        39, True,  True,  "Accounting"),
    ("Meridian",          "business", "Global business and consulting",                         59, True,  False, "Finance"),
    ("Apex",              "business", "Corporate SaaS landing page",                            69, True,  True,  "Enterprise"),
    # E-Commerce
    ("ShopVibe",          "ecommerce", "Modern e-commerce storefront",                          89, True,  True,  "Fashion"),
    ("CartFlow",          "ecommerce", "Minimal online shop template",                          69, True,  False, "Digital Products"),
    ("StoreX",            "ecommerce", "Multi-vendor marketplace",                              99, True,  True,  "Multi Vendor"),
    ("Luxe Shop",         "ecommerce", "Luxury goods e-commerce",                             129, False, False, "Jewelry"),
    ("QuickBuy",          "ecommerce", "Fast checkout e-commerce template",                     49, True,  True,  "Electronics"),
    ("FreshMarket",       "ecommerce", "Grocery and organic store",                             59, True,  False, "Grocery"),
    ("TechStore",         "ecommerce", "Electronics and gadgets shop",                         79, True,  True,  "Electronics"),
    ("FashionHub",        "ecommerce", "Fashion and clothing store",                           89, False, True,  "Fashion"),
    ("PetShop",           "ecommerce", "Pet supplies online store",                             49, True,  False, "Pet Store"),
    ("BookHaven",         "ecommerce", "Online bookstore template",                             39, True,  True,  "Book Store"),
    # Portfolio
    ("ArtBoard",          "portfolio", "Creative artist portfolio",                             29, True,  True,  "Artist"),
    ("PixelCraft",        "portfolio", "Photography portfolio template",                        39, True,  False, "Photographer"),
    ("Designio",          "portfolio", "UI/UX designer portfolio",                              49, True,  True,  "Designer"),
    ("StudioReel",        "portfolio", "Video and motion portfolio",                            59, False, True,  "Videographer"),
    ("Showcase",          "portfolio", "Minimal personal portfolio",                            19, True,  False, "Freelancer"),
    ("Canvas",            "portfolio", "Painter and illustrator portfolio",                     29, True,  True,  "Artist"),
    ("Luminate",          "portfolio", "Creative agency portfolio",                             69, True,  False, "Designer"),
    ("Folio",             "portfolio", "Freelancer showcase template",                          39, True,  True,  "Freelancer"),
    ("Aura",              "portfolio", "Branding and identity portfolio",                       49, False, False, "Designer"),
    ("Sketch",            "portfolio", "Architecture portfolio",                                59, True,  True,  "Architect"),
    # Restaurant
    ("Gastro",            "restaurant", "Fine dining restaurant template",                      59, True,  True,  "Restaurant"),
    ("CafeBliss",         "restaurant", "Coffee shop and cafe template",                        39, True,  False, "Cafe"),
    ("PizzaTime",         "restaurant", "Pizza and fast food template",                         29, True,  True,  "Fast Food"),
    ("SushiBar",          "restaurant", "Japanese restaurant template",                         49, False, True,  "Restaurant"),
    ("Brunch",            "restaurant", "Brunch cafe template",                                 39, True,  False, "Cafe"),
    ("FoodTruck",         "restaurant", "Food truck and street food",                           29, True,  True,  "Food Delivery"),
    ("Bakehouse",         "restaurant", "Bakery and pastry shop",                               35, True,  False, "Bakery"),
    ("Vegan",             "restaurant", "Plant-based restaurant template",                      45, True,  True,  "Restaurant"),
    ("BBQ",               "restaurant", "BBQ and grill restaurant",                             39, False, False, "Restaurant"),
    ("IceCream",          "restaurant", "Dessert and ice cream shop",                           25, True,  True,  "Ice Cream"),
    # Healthcare
    ("MediCare",          "healthcare", "Medical clinic template",                              79, True,  True,  "Clinic"),
    ("DentaSmile",        "healthcare", "Dental clinic template",                               69, True,  False, "Dentist"),
    ("Wellness",          "healthcare", "Health and wellness center",                           59, True,  True,  "Mental Health"),
    ("PhysioFit",         "healthcare", "Physiotherapy and rehab",                              69, False, True,  "Physiotherapy"),
    ("MindCare",          "healthcare", "Mental health clinic template",                        79, True,  False, "Mental Health"),
    ("VetCare",           "healthcare", "Veterinary clinic template",                           49, True,  True,  "Veterinary"),
    ("Pharmacy",          "healthcare", "Pharmacy and drug store",                              59, True,  False, "Pharmacy"),
    ("Hospital",          "healthcare", "Hospital and medical center",                          99, False, True,  "Hospital"),
    ("NutriHealth",       "healthcare", "Nutrition and dietitian clinic",                       69, True,  False, "Clinic"),
    ("Yoga",              "healthcare", "Yoga and meditation studio",                           45, True,  True,  "Mental Health"),
    # Real Estate
    ("EstateView",        "real-estate", "Property listing template",                          89, True,  True,  "Property Listing"),
    ("Homely",            "real-estate", "Home buying and selling template",                    79, True,  False, "Home Rental"),
    ("LuxRealty",         "real-estate", "Luxury real estate template",                       129, False, True,  "Villa"),
    ("RentEase",          "real-estate", "Rental property template",                           69, True,  False, "Home Rental"),
    ("UrbanSpaces",       "real-estate", "Urban apartment template",                           79, True,  True,  "Apartment"),
    ("Propify",           "real-estate", "Property management template",                       89, False, False, "Property Listing"),
    ("OpenHouse",         "real-estate", "Real estate agency template",                        99, True,  True,  "Builder"),
    ("VillaLux",          "real-estate", "Villa and luxury estate",                           149, True,  False, "Villa"),
    ("CommercialPro",     "real-estate", "Commercial property template",                      109, False, True,  "Commercial Property"),
    ("RealtyCo",          "real-estate", "Real estate company template",                       79, True,  True,  "Builder"),
    # Education
    ("EduLearn",          "education", "Online course platform template",                      99, True,  True,  "Online Courses"),
    ("KidsLearn",         "education", "Children's education template",                        69, True,  False, "Kindergarten"),
    ("CollegeHub",        "education", "University and college template",                      89, False, True,  "University"),
    ("TutorPro",          "education", "Private tutoring template",                            59, True,  False, "Tuition"),
    ("LanguageLab",       "education", "Language learning platform",                           79, True,  True,  "Online Courses"),
    ("CodingAcademy",     "education", "Coding bootcamp template",                             99, True,  False, "Coaching Center"),
    ("MusicSchool",       "education", "Music school and lessons",                             69, True,  True,  "School"),
    ("ArtStudio",         "education", "Art class and workshop",                               59, False, True,  "Coaching Center"),
    ("Preschool",         "education", "Preschool and kindergarten",                           49, True,  False, "Kindergarten"),
    ("ELearning",         "education", "E-learning and LMS template",                        119, True,  True,  "LMS"),
    # Technology
    ("SaasKit",           "technology", "SaaS product landing page",                          99, True,  True,  "SaaS"),
    ("AppLaunch",         "technology", "Mobile app launch template",                          79, True,  False, "Mobile App"),
    ("StartupX",          "technology", "Startup and product template",                        89, True,  True,  "Tech Startup"),
    ("DevPortal",         "technology", "Developer tools and API",                             69, False, True,  "DevOps"),
    ("CloudSaaS",         "technology", "Cloud service platform",                             109, True,  False, "Cloud Computing"),
    ("AIProduct",         "technology", "AI and ML product template",                         119, True,  True,  "Data Analytics"),
    ("CyberSec",          "technology", "Cybersecurity company template",                      99, False, False, "Cyber Security"),
    ("TechBlog",          "technology", "Tech blog and news template",                         49, True,  True,  "Software"),
    ("HardwareCo",        "technology", "Hardware product template",                           79, True,  False, "Software"),
    ("Fintech",           "technology", "Fintech and banking app",                            129, True,  True,  "CRM"),
    # Travel
    ("WanderLust",        "travel", "Travel agency landing page",                              69, True,  True,  "Tour Agency"),
    ("HotelLux",          "travel", "Hotel and resort template",                               89, True,  False, "Hotel Booking"),
    ("TourGuide",         "travel", "Tour operator template",                                  59, True,  True,  "Tour Agency"),
    ("AirTravel",         "travel", "Flight booking template",                                 79, False, True,  "Airline"),
    ("BackpackerBlog",    "travel", "Travel blog template",                                    39, True,  False, "Travel Blog"),
    ("CruiseLine",        "travel", "Cruise and maritime template",                            99, True,  True,  "Resort"),
    ("SkiResort",         "travel", "Ski and mountain resort",                                 89, False, False, "Resort"),
    ("BeachHotel",        "travel", "Beach and tropical resort",                               79, True,  True,  "Hotel Booking"),
    ("Nomad",             "travel", "Digital nomad and remote work travel",                    49, True,  False, "Travel Blog"),
    ("CityBreaks",        "travel", "City tourism and experience",                             59, True,  True,  "Tour Agency"),
    # Agency
    ("CreativeAgency",   "agency", "Full-service creative agency",                             99, True,  True,  "Creative Studio"),
    ("DesignStudio",     "agency", "Design studio and branding",                               89, True,  False, "Branding"),
    ("MarketingPro",     "agency", "Digital marketing agency",                                 79, True,  True,  "Digital Agency"),
    ("PRAgency",         "agency", "Public relations agency",                                  89, False, True,  "PR Agency"),
    ("WebAgency",        "agency", "Web development agency",                                   99, True,  False, "Digital Agency"),
    ("SEOAgency",        "agency", "SEO and content agency",                                   69, True,  True,  "SEO Agency"),
    ("VideoAgency",      "agency", "Video production agency",                                 109, False, False, "Creative Studio"),
    ("SocialMedia",      "agency", "Social media management agency",                           79, True,  True,  "Marketing Agency"),
    ("BrandAgency",      "agency", "Brand strategy agency",                                   119, True,  False, "Branding"),
    ("GrowthHQ",         "agency", "Growth hacking agency",                                    89, True,  True,  "Marketing Agency"),
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
        for i, (title, cat_slug, description, price, dark_mode, ai_ready, sub_category) in enumerate(TEMPLATE_POOL):
            slug = title.lower().replace(" ", "-").replace("&", "and")
            existing = (await db.execute(
                sa_select(Template).where(Template.slug == slug)
            )).scalar_one_or_none()
            if existing:
                sub_lower = sub_category.lower()
                sub_slug_tag = sub_lower.replace(" ", "-")
                existing_tags = list(existing.tags or [])
                new_tags = list(existing_tags)
                for tag in [sub_lower, sub_slug_tag]:
                    if tag not in new_tags:
                        new_tags.append(tag)
                existing.tags = new_tags
                if not existing.industry or " — " not in existing.industry:
                    existing.industry = f"{sub_category} — {INDUSTRIES[cat_slug]}"
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
                tags=[
                    cat_slug,
                    framework,
                    INDUSTRIES[cat_slug].lower(),
                    sub_category.lower(),
                    sub_category.lower().replace(" ", "-"),
                ],
                industry=f"{sub_category} — {INDUSTRIES[cat_slug]}",
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
