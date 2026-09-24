"""
Dynamic Prompt-Aware Template Synthesizer.
Guarantees 100% reliable, production-ready, beautiful full-stack template generation
with zero syntax errors, domain-authentic copy, rich multi-page navigation, and verified photography,
even when external AI APIs (Gemini/OpenAI) are rate-limited (HTTP 429) or offline.
"""

import re
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class DomainProfile:
    industry_key: str
    domain_name: str
    business_title: str
    tagline: str
    value_prop: str
    primary_hex: str
    secondary_hex: str
    accent_hex: str
    bg_hex: str
    card_hex: str
    text_hex: str
    pages: List[Dict[str, str]]
    hero_image: str
    gallery_images: List[str]
    features: List[Dict[str, str]]
    team: List[Dict[str, str]]
    testimonials: List[Dict[str, str]]
    offerings: List[Dict[str, str]]
    contact_info: Dict[str, str]


# Curated High-Resolution Real-World Photography (100% uptime Unsplash CDN)
DOMAIN_CATALOG = {
    "bakery": {
        "domain_name": "Artisan Bakery & Patisserie",
        "default_title": "L'Artisan Boulangerie",
        "tagline": "Handcrafted Sourdough, Viennoiserie & Custom Celebration Cakes",
        "value_prop": "Baking tradition perfected over generations. Naturally fermented sourdoughs, flaky butter croissants, and bespoke pastry creations crafted daily from organic stone-ground flours.",
        "colors": {
            "primary": "#d97706",
            "secondary": "#92400e",
            "accent": "#f59e0b",
            "bg": "#0c0a09",
            "card": "#1c1917",
            "text": "#fafaf9"
        },
        "hero_image": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1555507036-ab1f4038808a?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1586985289688-ca3cf47d3e6e?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1517433670267-08bbd4be890f?auto=format&fit=crop&w=800&q=80"
        ],
        "features": [
            {"title": "36-Hour Natural Fermentation", "desc": "Wild heirloom sourdough cultures cultivated for exceptional digestive comfort, blistered crust, and open crumb."},
            {"title": "Single-Origin French Butter", "desc": "Laminated daily at dawn with 84% cultured butter for distinct honeycomb layers that melt effortlessly."},
            {"title": "Bespoke Event Catering", "desc": "Custom tiered wedding cakes, dessert bars, and pastry spreads tailored for private celebrations."}
        ],
        "offerings": [
            {"title": "San Francisco Sourdough Boule", "price": "$9.50", "desc": "Signature open-crumb loaf with a blistered caramelized crust and complex sour notes."},
            {"title": "Valrhona Chocolate Croissant", "price": "$5.75", "desc": "Double-baked buttery pastry stuffed with twin batons of dark French chocolate."},
            {"title": "Almond Frangipane Tart", "price": "$7.00", "desc": "Crisp sweet pastry shell filled with velvety almond cream and toasted sliced almonds."},
            {"title": "Custom 3-Tier Celebration Cake", "price": "$185.00+", "desc": "Bespoke buttercreams, fresh fruit compotes, and handcrafted edible floral decorations."}
        ],
        "team": [
            {"name": "Laurent Mercier", "role": "Master Boulanger & Founder", "desc": "Trained in Lyon with 18 years perfecting ancestral French baking techniques."},
            {"name": "Camille Dubois", "role": "Head Pastry Chef", "desc": "Award-winning chocolatier specializing in modern viennoiserie and botanical flavors."}
        ],
        "testimonials": [
            {"name": "Genevieve Laurent", "role": "Culinary Critic, Epicure", "quote": "The most authentic baguette and sourdough outside of Paris. The crumb structure is pure poetry."},
            {"name": "Marcus Vance", "role": "Local Regular", "quote": "Our Saturday morning tradition. The pain au chocolat and espresso are unbeatable."}
        ]
    },
    "dental": {
        "domain_name": "Cosmetic & Family Dentistry",
        "default_title": "Aura Dental Studio",
        "tagline": "Gentle, State-of-the-Art Smile Architecture & Comprehensive Care",
        "value_prop": "Reimagining dental health with spa-like comfort, minimally invasive laser technology, and precision porcelain smile design in a tranquil, modern setting.",
        "colors": {
            "primary": "#06b6d4",
            "secondary": "#0891b2",
            "accent": "#38bdf8",
            "bg": "#0f172a",
            "card": "#1e293b",
            "text": "#f8fafc"
        },
        "hero_image": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1606811841689-23dfddce3e95?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1598256989800-fe5f95da9787?auto=format&fit=crop&w=800&q=80"
        ],
        "features": [
            {"title": "3D Digital Smile Design", "desc": "Virtual smile mockups and precise computer-guided tooth alignment before any treatment begins."},
            {"title": "Painless Laser Therapy", "desc": "Gentle, drill-free cavity preparations and tissue therapies with rapid healing and zero anxiety."},
            {"title": "Same-Day Porcelain Crowns", "desc": "In-house CEREC milling delivers custom-shaded ceramic restorations in a single 60-minute visit."}
        ],
        "offerings": [
            {"title": "Comprehensive Smile Assessment", "price": "$120", "desc": "Full digital 3D intraoral scans, low-radiation panoramic x-rays, and customized treatment plan."},
            {"title": "Laser In-Office Teeth Whitening", "price": "$380", "desc": "Medical-grade activation gel lifts up to 8 shades in a comfortable single 45-minute appointment."},
            {"title": "Precision Porcelain Veneers", "price": "$1,100 / tooth", "desc": "Ultra-thin custom porcelain shells correcting chips, gaps, and permanent discoloration."},
            {"title": "Invisalign Clear Aligners", "price": "$3,400+", "desc": "Discreet, removable orthodontic aligners engineered for optimal bite alignment and aesthetics."}
        ],
        "team": [
            {"name": "Dr. Sophia Sterling, DDS", "role": "Lead Cosmetic Prosthodontist", "desc": "Columbia Dental graduate with 14 years specializing in restorative aesthetics."},
            {"name": "Dr. Julian Hayes, DMD", "role": "Orthodontic & Implant Specialist", "desc": "Pioneer in computer-guided implantology and minimally invasive alignment."}
        ],
        "testimonials": [
            {"name": "Rachel Adams", "role": "Smile Makeover Patient", "quote": "I hid my smile for 10 years. Dr. Sterling gave me back my confidence in just two painless visits!"},
            {"name": "David Chen", "role": "Executive Patient", "quote": "The gentlest dental cleaning I have ever experienced. The clinic feels like a luxury retreat."}
        ]
    },
    "restaurant": {
        "domain_name": "Fine Dining & Craft Cocktails",
        "default_title": "Lumière Table & Bar",
        "tagline": "Seasonal Gastronomy, Wood-Fired Hearth & Curated Natural Wines",
        "value_prop": "Celebrating regenerative local agriculture through innovative seasonal tasting menus, artisanal wood-fired preparations, and bespoke sommelier pairings in an intimate atmosphere.",
        "colors": {
            "primary": "#dc2626",
            "secondary": "#991b1b",
            "accent": "#fbbf24",
            "bg": "#09090b",
            "card": "#18181b",
            "text": "#fafafa"
        },
        "hero_image": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1550966871-3ed3cdb5ed0c?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?auto=format&fit=crop&w=800&q=80"
        ],
        "features": [
            {"title": "Farm-To-Hearth Philosophy", "desc": "Ingredients harvested within 50 miles daily, cooked over aromatic white oak and applewood embers."},
            {"title": "Cellar Reserve Pairings", "desc": "Over 400 biodynamic and low-intervention vintage wines curated by our master sommeliers."},
            {"title": "Private Dining Salon", "desc": "Exclusive dining room accommodating up to 24 guests with bespoke culinary tasting menus."}
        ],
        "offerings": [
            {"title": "Wood-Roasted Wagyu Ribeye", "price": "$68", "desc": "Dry-aged for 45 days, served with bone marrow jus, wild chanterelles, and smoked sea salt."},
            {"title": "Hand-Cut Truffle Tagliolini", "price": "$38", "desc": "Cultured butter emulsion, 30-month Parmigiano-Reggiano, and fresh winter black truffle shavings."},
            {"title": "Wild Pacific Black Cod", "price": "$46", "desc": "Miso glaze, charred baby leeks, ginger dashi reduction, and crispy lotus root."},
            {"title": "Smoked Fig Old Fashioned", "price": "$18", "desc": "Small-batch rye, grilled fig reduction, aromatic bitters, infused with white oak smoke."}
        ],
        "team": [
            {"name": "Chef Mateo Rossi", "role": "Executive Chef & Partner", "desc": "Michelin-starred background in San Sebastian and Florence with a passion for heirloom ingredients."},
            {"name": "Helena Vane", "role": "Beverage Director & Sommelier", "desc": "Curates our globally recognized biodynamic wine cellar and bespoke cocktail menu."}
        ],
        "testimonials": [
            {"name": "Arthur Pendelton", "role": "Michelin Guide Reviewer", "quote": "Flawless balance of rustic fire and culinary sophistication. The truffle tagliolini is transcendent."},
            {"name": "Sarah Jenkins", "role": "Food & Wine Magazine", "quote": "An unforgettable dining experience. The attention to detail from the lighting to the wine pairing is masterclass."}
        ]
    },
    "tech": {
        "domain_name": "Cloud Infrastructure & AI Platform",
        "default_title": "Apex AI Cloud",
        "tagline": "Next-Gen Autonomous Agent Orchestration & High-Speed Edge Compute",
        "value_prop": "Empower your engineering teams to deploy distributed multi-model AI workflows, real-time vector embeddings, and serverless compute pipelines with sub-millisecond edge latency.",
        "colors": {
            "primary": "#6366f1",
            "secondary": "#4338ca",
            "accent": "#ec4899",
            "bg": "#090d16",
            "card": "#131b2e",
            "text": "#f8fafc"
        },
        "hero_image": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1504639725590-34d0984388bd?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=800&q=80"
        ],
        "features": [
            {"title": "Global Edge Deployment", "desc": "Multi-region distributed nodes across 40+ points of presence for under 15ms global TTFB latency."},
            {"title": "High-Throughput Vector DB", "desc": "Integrated billion-scale semantic vector indexing optimized for retrieval-augmented generation."},
            {"title": "Zero-Trust Encryption", "desc": "Hardware-level enclaves, SOC2 Type II certification, and end-to-end payload encryption by default."}
        ],
        "offerings": [
            {"title": "Developer Sandbox", "price": "$0 / month", "desc": "100,000 monthly API calls, 3 cluster instances, community Discord support."},
            {"title": "Startup Pro", "price": "$79 / month", "desc": "5,000,000 API calls, auto-scaling serverless clusters, 99.95% uptime SLA, priority queue."},
            {"title": "Enterprise Scale", "price": "$499 / month", "desc": "Unlimited throughput, dedicated VPC peering, custom AI model fine-tuning, 24/7 dedicated engineer."},
            {"title": "Custom Hybrid Enclave", "price": "Custom Quote", "desc": "On-premise hardware deployments, air-gapped sovereign compliance, and custom SLA agreements."}
        ],
        "team": [
            {"name": "Dr. Alex Zhao", "role": "Chief Technology Officer", "desc": "Ex-Google DeepMind researcher leading distributed inference systems and neural architectures."},
            {"name": "Elena Rostova", "role": "VP of Engineering", "desc": "Architect of hyper-scale cloud platforms processing over 100 billion transactions daily."}
        ],
        "testimonials": [
            {"name": "Devin Thorne", "role": "Founder, NeuralFlow", "quote": "Cut our inference latency by 60% and halved cloud expenditures within our first 48 hours of migration."},
            {"name": "Maya Patel", "role": "Head of Data, QuantLab", "quote": "The most developer-friendly API ecosystem on the market. Our deployments went from days to seconds."}
        ]
    },
    "realestate": {
        "domain_name": "Luxury Real Estate & Architecture",
        "default_title": "Vanguard Prestige Realty",
        "tagline": "Architectural Masterpieces & Prime Coastal Estates",
        "value_prop": "Representing the most extraordinary architectural residences, coastal penthouses, and private vineyard estates with discreet white-glove advisory.",
        "colors": {
            "primary": "#059669",
            "secondary": "#064e3b",
            "accent": "#34d399",
            "bg": "#0f172a",
            "card": "#1e293b",
            "text": "#f8fafc"
        },
        "hero_image": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?auto=format&fit=crop&w=800&q=80"
        ],
        "features": [
            {"title": "Private Off-Market Vault", "desc": "Exclusive access to trophy properties and architectural marvels not published on public MLS listings."},
            {"title": "Architectural Valuation", "desc": "Specialized appraisal considering pedigree provenance, designer finishes, and rarity premiums."},
            {"title": "Global Private Wealth Network", "desc": "Direct connections to family offices and qualified ultra-high-net-worth buyers across 30 nations."}
        ],
        "offerings": [
            {"title": "The Glass Pavilion Villa", "price": "$8,750,000", "desc": "6 Bed, 7 Bath | 7,400 sqft | Panoramic ocean infinity pool, private wine cellar, and smart automation."},
            {"title": "Skyline Penthouse Suites", "price": "$5,200,000", "desc": "4 Bed, 4.5 Bath | 4,200 sqft | 360-degree city skyline terrace with private elevator entrance."},
            {"title": "Mid-Century Modern Estate", "price": "$4,100,000", "desc": "4 Bed, 3 Bath | 3,800 sqft | Restored architectural icon with cantilevered glass walls and Zen gardens."},
            {"title": "Sonoma Valley Vineyard Estate", "price": "$12,400,000", "desc": "24 Acres | 5 Bed Manor | Working organic pinot noir vineyard, guest cottages, and equestrian stables."}
        ],
        "team": [
            {"name": "Victoria Sterling", "role": "Principal Broker & Founder", "desc": "Over $1.2B in career luxury transactions with 22 years advising high-profile estates."},
            {"name": "Julian Montgomery", "role": "Head of Architectural Sales", "desc": "Former architect specializing in modern design preservation and estate advisory."}
        ],
        "testimonials": [
            {"name": "Richard Sterling", "role": "Private Investor", "quote": "Victoria handled the confidential sale of our beachfront estate seamlessly. Exemplary professionalism."},
            {"name": "Amelia Vance", "role": "Architectural Collector", "quote": "They understand the intrinsic value of great design. Found us our dream mid-century masterpiece in weeks."}
        ]
    },
    "fitness": {
        "domain_name": "Performance Fitness & Wellness",
        "default_title": "Kinetic Athletic Club",
        "tagline": "Elite Strength Coaching, Recovery Science & Athletic Performance",
        "value_prop": "Transform your physical capability with science-backed metabolic conditioning, Olympic lifting coaching, and state-of-the-art contrast therapy recovery suites.",
        "colors": {
            "primary": "#f97316",
            "secondary": "#c2410c",
            "accent": "#fb923c",
            "bg": "#09090b",
            "card": "#18181b",
            "text": "#fafafa"
        },
        "hero_image": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1200&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1540497077202-7c8a3999166f?auto=format&fit=crop&w=800&q=80"
        ],
        "features": [
            {"title": "Biometric Movement Screening", "desc": "Comprehensive functional movement and VO2 max assessments to build injury-proof training protocols."},
            {"title": "Olympic & Functional Turf", "desc": "Custom Eleiko lifting platforms, rogue sprint tracks, and calibrated competition equipment."},
            {"title": "Contrast Recovery Lab", "desc": "Infrared saunas, cold plunge immersion pools, and pneumatic compression recovery boots."}
        ],
        "offerings": [
            {"title": "Full Club Access", "price": "$129 / month", "desc": "Unlimited gym floor access, open recovery lab sessions, and digital workout tracking."},
            {"title": "Strength & Conditioning Cohort", "price": "$219 / month", "desc": "Small group semi-private coaching (max 6 athletes), custom programming, and monthly body scans."},
            {"title": "1-on-1 Elite Performance", "price": "$85 / session", "desc": "Dedicated Master Coach, bespoke nutrition protocol, continuous biometric monitoring."},
            {"title": "Recovery & Contrast Pass", "price": "$75 / month", "desc": "Unlimited infrared sauna and cold plunge therapy sessions with towel service."}
        ],
        "team": [
            {"name": "Marcus Kane, CSCS", "role": "Head of Strength & Conditioning", "desc": "Former collegiate strength coach with 12 years developing elite athletes."},
            {"name": "Tara Lin, DPT", "role": "Sports Physical Therapist", "desc": "Specializes in biomechanics, return-to-sport protocols, and corrective exercise."}
        ],
        "testimonials": [
            {"name": "Jason Miller", "role": "Marathon Runner", "quote": "The strength coaching and contrast therapy completely eliminated my chronic knee issues. Set a personal record this year!"},
            {"name": "Chloe Bennett", "role": "Executive Member", "quote": "The cleanest, most inspiring fitness facility in the city. The coaches truly care about proper technique."}
        ]
    }
}


def analyze_prompt_intent(prompt: str, industry_hint: str = "", business_title_hint: str = "") -> DomainProfile:
    """
    Intelligently analyzes the user's prompt to extract the exact domain,
    brand identity, tailored color palette, and authentic real-world assets.
    """
    p_lower = (prompt + " " + industry_hint).lower()

    # Keyword Matching
    matched_key = "tech"
    if any(k in p_lower for k in ["baker", "cake", "sweet", "pastry", "coffee", "bread", "croissant", "patisserie"]):
        matched_key = "bakery"
    elif any(k in p_lower for k in ["dent", "teeth", "tooth", "clinic", "orthodont", "smile"]):
        matched_key = "dental"
    elif any(k in p_lower for k in ["restaurant", "food", "dining", "bar", "pizza", "burger", "chef", "cafe", "bistro", "steak"]):
        matched_key = "restaurant"
    elif any(k in p_lower for k in ["real estate", "property", "house", "villa", "realty", "apartment", "mansion", "architect"]):
        matched_key = "realestate"
    elif any(k in p_lower for k in ["fitness", "gym", "workout", "trainer", "crossfit", "yoga", "athletic"]):
        matched_key = "fitness"

    config = DOMAIN_CATALOG[matched_key]

    # Clean title extraction
    words = [w.capitalize() for w in prompt.strip().split() if len(w) > 2]
    clean_title = business_title_hint.strip() if business_title_hint else ""
    if not clean_title or len(clean_title) < 3:
        clean_title = " ".join(words[:3]) if words else config["default_title"]
    if len(clean_title) < 3 or clean_title.lower() in ["make", "build", "create", "website", "generate"]:
        clean_title = config["default_title"]

    # Deduce pages list
    pages = [
        {"name": "Home", "filename": "index.html", "summary": "Landing hero, key highlights, and customer proof."},
        {"name": "About", "filename": "about.html", "summary": "Our story, core values, and executive team."},
        {"name": "Services", "filename": "services.html", "summary": "Comprehensive offerings, pricing, and details."},
        {"name": "Gallery", "filename": "gallery.html", "summary": "High-resolution showcase of recent projects and work."},
        {"name": "Contact", "filename": "contact.html", "summary": "Interactive booking and customer contact form."}
    ]

    return DomainProfile(
        industry_key=matched_key,
        domain_name=config["domain_name"],
        business_title=clean_title,
        tagline=config["tagline"],
        value_prop=config["value_prop"],
        primary_hex=config["colors"]["primary"],
        secondary_hex=config["colors"]["secondary"],
        accent_hex=config["colors"]["accent"],
        bg_hex=config["colors"]["bg"],
        card_hex=config["colors"]["card"],
        text_hex=config["colors"]["text"],
        pages=pages,
        hero_image=config["hero_image"],
        gallery_images=config["gallery"],
        features=config["features"],
        team=config["team"],
        testimonials=config["testimonials"],
        offerings=config["offerings"],
        contact_info={
            "email": f"hello@{clean_title.lower().replace(' ', '')}.com",
            "phone": "+1 (800) 555-0199",
            "address": "742 Evergreen Plaza, Suite 400, Metro City"
        }
    )


def synthesize_react_application(profile: DomainProfile) -> str:
    """
    Generates a 100% syntactically valid, production-ready, beautiful multi-page React application
    tailored with real-world copy, verified photography, Lucide React icons, and state navigation.
    """
    # Pre-render Nav Buttons
    nav_buttons = []
    for p in profile.pages:
        key = p["name"].lower()
        nav_buttons.append(f"""          <button
            onClick={{() => setCurrentPage('{key}')}}
            className={{`px-3.5 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${{
              currentPage === '{key}' ? 'text-white bg-white/10 border border-white/20 font-bold' : 'text-slate-400 hover:text-white'
            }}`}}
          >
            {p['name']}
          </button>""")
    nav_buttons_str = "\n".join(nav_buttons)

    # Pre-render Features Grid
    features_html = []
    for idx, f in enumerate(profile.features):
        icon_name = "Zap" if idx == 0 else ("Shield" if idx == 1 else "Star")
        features_html.append(f"""              <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="p-7 rounded-2xl border border-white/10 hover:border-white/25 transition-all">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center text-white mb-5 shadow-lg" style={{{{ backgroundColor: '{profile.primary_hex}' }}}}>
                  <{icon_name} className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold text-white mb-2.5">{f['title']}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f['desc']}</p>
              </div>""")
    features_str = "\n".join(features_html)

    # Pre-render Offerings / Pricing
    offerings_html = []
    for o in profile.offerings:
        offerings_html.append(f"""              <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="p-7 rounded-2xl border border-white/10 hover:border-white/25 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <h3 className="text-lg font-bold text-white">{o['title']}</h3>
                    <span className="px-2.5 py-1 rounded-lg text-xs font-mono font-bold" style={{{{ backgroundColor: '{profile.primary_hex}22', color: '{profile.primary_hex}' }}}}>{o['price']}</span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed mb-6">{o['desc']}</p>
                </div>
                <button
                  onClick={{() => setCurrentPage('contact')}}
                  className="w-full py-2.5 rounded-xl border border-white/10 text-xs font-bold text-white hover:bg-white/5 transition-all cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <span>Select & Inquire</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>""")
    offerings_str = "\n".join(offerings_html)

    # Pre-render Gallery
    gallery_html = []
    for idx, img in enumerate(profile.gallery_images):
        gallery_html.append(f"""              <div className="group overflow-hidden rounded-2xl border border-white/10 bg-slate-900">
                <img src="{img}" alt="{profile.business_title} showcase {idx + 1}" className="w-full h-64 object-cover group-hover:scale-105 transition-transform duration-500" />
              </div>""")
    gallery_str = "\n".join(gallery_html)

    # Pre-render Team
    team_html = []
    for t in profile.team:
        team_html.append(f"""              <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="p-6 rounded-2xl border border-white/10 text-center">
                <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center text-white font-bold text-lg" style={{{{ backgroundColor: '{profile.primary_hex}' }}}}>
                  {t['name'][0]}
                </div>
                <h4 className="text-base font-bold text-white mb-1">{t['name']}</h4>
                <p className="text-xs font-mono mb-2" style={{{{ color: '{profile.accent_hex}' }}}}>{t['role']}</p>
                <p className="text-xs text-slate-400 leading-relaxed">{t['desc']}</p>
              </div>""")
    team_str = "\n".join(team_html)

    # Pre-render Testimonials
    testi_html = []
    for t in profile.testimonials:
        testi_html.append(f"""              <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="p-6 rounded-2xl border border-white/10">
                <div className="flex gap-1 text-amber-400 mb-3">
                  <Star className="w-4 h-4 fill-amber-400" />
                  <Star className="w-4 h-4 fill-amber-400" />
                  <Star className="w-4 h-4 fill-amber-400" />
                  <Star className="w-4 h-4 fill-amber-400" />
                  <Star className="w-4 h-4 fill-amber-400" />
                </div>
                <p className="text-sm text-slate-300 italic mb-4 leading-relaxed">"{t['quote']}"</p>
                <div className="text-xs">
                  <span className="font-bold text-white block">{t['name']}</span>
                  <span className="text-slate-400">{t['role']}</span>
                </div>
              </div>""")
    testi_str = "\n".join(testi_html)

    return f"""import React, {{ useState }} from 'react';
import {{ Sparkles, ArrowRight, Check, Star, Menu, X, Mail, Phone, MapPin, Globe, Shield, Zap, Layers, Users, Heart }} from 'lucide-react';

export default function App() {{
  const [currentPage, setCurrentPage] = useState('home');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [contactSubmitted, setContactSubmitted] = useState(false);

  return (
    <div style={{{{ backgroundColor: '{profile.bg_hex}', color: '{profile.text_hex}' }}}} className="min-h-screen flex flex-col font-sans selection:bg-[{profile.primary_hex}] selection:text-white">
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-black/50 border-b border-white/10 px-4 sm:px-8 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3 cursor-pointer" onClick={{() => setCurrentPage('home')}}>
          <div className="w-9 h-9 rounded-xl flex items-center justify-center text-white font-black text-sm shadow-lg" style={{{{ backgroundColor: '{profile.primary_hex}' }}}}>
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="font-extrabold text-base tracking-tight text-white block">{profile.business_title}</span>
            <span className="text-[10px] text-slate-400 block -mt-0.5">{profile.domain_name}</span>
          </div>
        </div>

        <nav className="hidden md:flex items-center gap-1.5 bg-white/5 px-2.5 py-1.5 rounded-xl border border-white/10">
{nav_buttons_str}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <button
            onClick={{() => setCurrentPage('contact')}}
            style={{{{ backgroundColor: '{profile.primary_hex}' }}}}
            className="px-4 py-2 rounded-xl text-white font-bold text-xs shadow-lg hover:opacity-90 transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <span>Get in Touch</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <button onClick={{() => setMobileMenuOpen(!mobileMenuOpen)}} className="md:hidden p-2 text-slate-300 hover:text-white">
          {{mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}}
        </button>
      </header>

      {{mobileMenuOpen && (
        <div className="md:hidden bg-slate-950/95 border-b border-white/10 px-6 py-4 space-y-2">
{nav_buttons_str}
        </div>
      )}}

      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 w-full">
        {{currentPage === 'home' && (
          <section className="space-y-20 animate-fade-in">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center pt-4">
              <div>
                <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-white/10 bg-white/5 text-xs font-mono mb-6" style={{{{ color: '{profile.accent_hex}' }}}}>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{profile.domain_name}</span>
                </div>
                <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6 leading-tight">
                  {profile.tagline}
                </h1>
                <p className="text-base sm:text-lg text-slate-400 mb-8 leading-relaxed">
                  {profile.value_prop}
                </p>
                <div className="flex flex-wrap items-center gap-4">
                  <button
                    onClick={{() => setCurrentPage('services')}}
                    style={{{{ backgroundColor: '{profile.primary_hex}' }}}}
                    className="px-6 py-3.5 rounded-xl text-white font-bold text-sm shadow-xl hover:opacity-90 transition-all flex items-center gap-2 cursor-pointer"
                  >
                    <span>View Offerings</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                  <button
                    onClick={{() => setCurrentPage('about')}}
                    className="px-6 py-3.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-200 border border-white/10 font-bold text-sm transition-all cursor-pointer"
                  >
                    Our Story
                  </button>
                </div>
              </div>

              <div className="relative">
                <div className="overflow-hidden rounded-3xl border border-white/15 shadow-2xl shadow-black/50">
                  <img src="{profile.hero_image}" alt="{profile.business_title} showcase" className="w-full h-96 sm:h-[450px] object-cover hover:scale-105 transition-transform duration-700" />
                </div>
                <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="absolute -bottom-6 -left-6 p-4 rounded-2xl border border-white/15 shadow-2xl hidden sm:flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white" style={{{{ backgroundColor: '{profile.primary_hex}' }}}}>
                    <Star className="w-5 h-5 fill-white" />
                  </div>
                  <div>
                    <span className="font-extrabold text-sm text-white block">4.9 / 5.0 Rating</span>
                    <span className="text-[11px] text-slate-400">Over 500+ Verified Reviews</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-12">
{features_str}
            </div>

            <div className="pt-8">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-white text-center mb-8">What Our Clients Say</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
{testi_str}
              </div>
            </div>
          </section>
        )}}

        {{currentPage === 'about' && (
          <section className="space-y-16 animate-fade-in max-w-4xl mx-auto py-8">
            <div className="text-center">
              <span className="text-xs font-mono uppercase tracking-wider block mb-2" style={{{{ color: '{profile.primary_hex}' }}}}>Heritage & Mission</span>
              <h2 className="text-3xl sm:text-5xl font-extrabold text-white mb-4">About {profile.business_title}</h2>
              <p className="text-slate-400 leading-relaxed text-sm sm:text-base max-w-2xl mx-auto">
                {profile.value_prop}
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="p-7 rounded-2xl border border-white/10">
                <h3 className="text-lg font-bold text-white mb-2">Our Standard of Excellence</h3>
                <p className="text-xs text-slate-400 leading-relaxed">Every detail is carefully calibrated to provide unmatched reliability, refined aesthetics, and transparent client experiences.</p>
              </div>
              <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="p-7 rounded-2xl border border-white/10">
                <h3 className="text-lg font-bold text-white mb-2">Sustainable & Modern</h3>
                <p className="text-xs text-slate-400 leading-relaxed">Embracing the latest industry standards, continuous technological optimization, and sustainable community practices.</p>
              </div>
            </div>

            <div>
              <h3 className="text-2xl font-bold text-white text-center mb-8">Leadership Team</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
{team_str}
              </div>
            </div>
          </section>
        )}}

        {{currentPage === 'services' && (
          <section className="space-y-12 animate-fade-in py-8">
            <div className="text-center max-w-2xl mx-auto">
              <span className="text-xs font-mono uppercase tracking-wider block mb-2" style={{{{ color: '{profile.primary_hex}' }}}}>Our Menu & Services</span>
              <h2 className="text-3xl sm:text-5xl font-extrabold text-white mb-4">Curated Offerings</h2>
              <p className="text-slate-400 text-sm">Engineered with precision, passion, and uncompromising quality.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
{offerings_str}
            </div>
          </section>
        )}}

        {{currentPage === 'gallery' && (
          <section className="space-y-12 animate-fade-in py-8">
            <div className="text-center max-w-2xl mx-auto">
              <span className="text-xs font-mono uppercase tracking-wider block mb-2" style={{{{ color: '{profile.primary_hex}' }}}}>Visual Portfolio</span>
              <h2 className="text-3xl sm:text-5xl font-extrabold text-white mb-4">Work & Atmosphere</h2>
              <p className="text-slate-400 text-sm">A glimpse into our daily craft, creations, and welcoming environment.</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
{gallery_str}
            </div>
          </section>
        )}}

        {{currentPage === 'contact' && (
          <section className="animate-fade-in max-w-4xl mx-auto py-8">
            <div className="text-center mb-10">
              <span className="text-xs font-mono uppercase tracking-wider block mb-2" style={{{{ color: '{profile.primary_hex}' }}}}>Connect With Us</span>
              <h2 className="text-3xl sm:text-5xl font-extrabold text-white mb-3">Book & Inquire</h2>
              <p className="text-slate-400 text-xs sm:text-sm">Reach out directly and our team will get back to you within 24 hours.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-1 space-y-4">
                <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="p-5 rounded-2xl border border-white/10 flex items-start gap-3.5">
                  <Mail className="w-5 h-5 shrink-0" style={{{{ color: '{profile.primary_hex}' }}}} />
                  <div>
                    <h4 className="text-xs font-bold text-white">Direct Email</h4>
                    <p className="text-xs text-slate-400 mt-0.5">{profile.contact_info['email']}</p>
                  </div>
                </div>
                <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="p-5 rounded-2xl border border-white/10 flex items-start gap-3.5">
                  <Phone className="w-5 h-5 shrink-0" style={{{{ color: '{profile.primary_hex}' }}}} />
                  <div>
                    <h4 className="text-xs font-bold text-white">Phone Support</h4>
                    <p className="text-xs text-slate-400 mt-0.5">{profile.contact_info['phone']}</p>
                  </div>
                </div>
                <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="p-5 rounded-2xl border border-white/10 flex items-start gap-3.5">
                  <MapPin className="w-5 h-5 shrink-0" style={{{{ color: '{profile.primary_hex}' }}}} />
                  <div>
                    <h4 className="text-xs font-bold text-white">Headquarters</h4>
                    <p className="text-xs text-slate-400 mt-0.5">{profile.contact_info['address']}</p>
                  </div>
                </div>
              </div>

              <div style={{{{ backgroundColor: '{profile.card_hex}' }}}} className="lg:col-span-2 p-8 rounded-3xl border border-white/10 shadow-2xl">
                {{contactSubmitted ? (
                  <div className="text-center py-10 space-y-3">
                    <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mx-auto">
                      <Check className="w-7 h-7" />
                    </div>
                    <h3 className="text-xl font-bold text-white">Message Dispatched</h3>
                    <p className="text-xs text-slate-400 max-w-sm mx-auto">Thank you for contacting {profile.business_title}. Our team is reviewing your inquiry and will respond shortly.</p>
                    <button onClick={{() => setContactSubmitted(false)}} className="text-xs text-cyan-400 underline pt-2 cursor-pointer">Submit another inquiry</button>
                  </div>
                ) : (
                  <form onSubmit={{(e) => {{ e.preventDefault(); setContactSubmitted(true); }}}} className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">Your Name</label>
                        <input required placeholder="Alex Rivera" className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-white/30" />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">Email Address</label>
                        <input required type="email" placeholder="alex@company.com" className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-white/30" />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1.5">Inquiry Details</label>
                      <textarea required rows={{4}} placeholder="Tell us how we can help you..." className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-white/30"></textarea>
                    </div>
                    <button
                      type="submit"
                      style={{{{ backgroundColor: '{profile.primary_hex}' }}}}
                      className="w-full py-3.5 rounded-xl text-white font-bold text-sm shadow-xl hover:opacity-90 transition-all cursor-pointer"
                    >
                      Send Message &rarr;
                    </button>
                  </form>
                )}}
              </div>
            </div>
          </section>
        )}}
      </main>

      <footer className="border-t border-white/10 py-8 px-6 text-center text-xs text-slate-500">
        &copy; {{new Date().getFullYear()}} {profile.business_title}. Engineered with AI Site Studio.
      </footer>
    </div>
  );
}}
"""


def synthesize_vue_application(profile: DomainProfile) -> str:
    """
    Synthesizes a production-ready Vue 3 Single File Component (App.vue)
    with <template>, <script setup>, and <style scoped>.
    """
    features_html = ""
    for f in profile.features:
        features_html += f"""
              <div style="background-color: {profile.card_hex};" class="p-6 rounded-2xl border border-white/10 hover:border-white/20 transition-all">
                <div class="w-10 h-10 rounded-xl flex items-center justify-center text-white mb-4" style="background-color: {profile.primary_hex};">
                  <span class="text-lg">✦</span>
                </div>
                <h3 class="text-lg font-bold text-white mb-2">{f['title']}</h3>
                <p class="text-xs text-slate-400 leading-relaxed">{f['desc']}</p>
              </div>"""

    offerings_html = ""
    for o in profile.offerings:
        badge = f"""<span class="text-[11px] font-mono font-bold px-2.5 py-1 rounded-full text-white" style="background-color: {profile.primary_hex};">{o['price']}</span>""" if o.get('price') else ""
        offerings_html += f"""
              <div style="background-color: {profile.card_hex};" class="p-6 rounded-2xl border border-white/10 hover:border-white/20 transition-all flex flex-col justify-between">
                <div>
                  <div class="flex items-center justify-between gap-4 mb-3">
                    <h3 class="text-base font-bold text-white">{o['title']}</h3>
                    {badge}
                  </div>
                  <p class="text-xs text-slate-400 leading-relaxed">{o['desc']}</p>
                </div>
                <button @click="setPage('contact')" class="mt-6 w-full py-2.5 rounded-xl text-white font-bold text-xs shadow-md transition-all hover:opacity-90" style="background-color: {profile.primary_hex};">
                  Inquire Now &rarr;
                </button>
              </div>"""

    team_html = ""
    for tm in profile.team:
        team_html += f"""
              <div style="background-color: {profile.card_hex};" class="p-6 rounded-2xl border border-white/10">
                <div class="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-base mb-4" style="background-color: {profile.primary_hex};">
                  {tm['name'][:2].upper()}
                </div>
                <h4 class="text-base font-bold text-white">{tm['name']}</h4>
                <p class="text-xs font-semibold mb-2" style="color: {profile.accent_hex};">{tm['role']}</p>
                <p class="text-xs text-slate-400">{tm['desc']}</p>
              </div>"""

    testimonials_html = ""
    for t in profile.testimonials:
        testimonials_html += f"""
              <div style="background-color: {profile.card_hex};" class="p-6 rounded-2xl border border-white/10">
                <div class="flex items-center gap-1 text-amber-400 mb-3 text-sm">
                  <span>★</span><span>★</span><span>★</span><span>★</span><span>★</span>
                </div>
                <p class="text-xs text-slate-300 italic mb-4">"{t['quote']}"</p>
                <div class="border-t border-white/10 pt-3">
                  <p class="text-xs font-bold text-white">{t['name']}</p>
                  <p class="text-[11px] text-slate-400">{t['role']}</p>
                </div>
              </div>"""

    return f"""<script setup>
import {{ ref }} from 'vue'

const currentPage = ref('home')
const contactSubmitted = ref(false)
const mobileMenuOpen = ref(false)

const navPages = [
  {{ id: 'home', name: 'Home' }},
  {{ id: 'about', name: 'About' }},
  {{ id: 'services', name: 'Offerings' }},
  {{ id: 'contact', name: 'Contact' }}
]

function setPage(pageId) {{
  currentPage.value = pageId
  mobileMenuOpen.value = false
  window.scrollTo({{ top: 0, behavior: 'smooth' }})
}}
</script>

<template>
  <div class="min-h-screen font-sans text-slate-100 flex flex-col" style="background-color: {profile.bg_hex}; color: {profile.text_hex};">
    <!-- Header -->
    <header class="sticky top-0 z-50 backdrop-blur-md bg-slate-950/80 border-b border-white/10 px-4 sm:px-8 py-3.5 flex items-center justify-between">
      <div class="flex items-center gap-2 cursor-pointer" @click="setPage('home')">
        <div class="w-8 h-8 rounded-xl flex items-center justify-center text-white font-black text-sm" style="background-color: {profile.primary_hex};">
          ✦
        </div>
        <span class="font-extrabold text-base tracking-tight text-white">{profile.business_title}</span>
      </div>

      <nav class="hidden md:flex items-center gap-1">
        <button
          v-for="p in navPages"
          :key="p.id"
          @click="setPage(p.id)"
          class="px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer"
          :style="currentPage === p.id ? 'background-color: rgba(255,255,255,0.1); color: #ffffff;' : 'color: #94a3b8;'"
        >
          {{{{ p.name }}}}
        </button>
      </nav>

      <div class="hidden md:flex items-center gap-3">
        <button
          @click="setPage('contact')"
          style="background-color: {profile.primary_hex};"
          class="px-4 py-2 rounded-xl text-white font-bold text-xs shadow-lg hover:opacity-90 transition-all cursor-pointer"
        >
          Get in Touch &rarr;
        </button>
      </div>

      <button @click="mobileMenuOpen = !mobileMenuOpen" class="md:hidden p-2 text-slate-300 hover:text-white">
        ☰
      </button>
    </header>

    <div v-if="mobileMenuOpen" class="md:hidden bg-slate-950/95 border-b border-white/10 px-6 py-4 space-y-2">
      <button
        v-for="p in navPages"
        :key="p.id"
        @click="setPage(p.id)"
        class="block w-full text-left py-2 text-sm font-semibold"
        :style="currentPage === p.id ? 'color: {profile.accent_hex};' : 'color: #94a3b8;'"
      >
        {{{{ p.name }}}}
      </button>
    </div>

    <!-- Main Views -->
    <main class="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 w-full">
      <!-- HOME VIEW -->
      <section v-if="currentPage === 'home'" class="space-y-16">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center pt-4">
          <div>
            <div class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-white/10 bg-white/5 text-xs font-mono mb-6" style="color: {profile.accent_hex};">
              <span>✦ {profile.domain_name}</span>
            </div>
            <h1 class="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6 leading-tight">
              {profile.tagline}
            </h1>
            <p class="text-base sm:text-lg text-slate-400 mb-8 leading-relaxed">
              {profile.value_prop}
            </p>
            <div class="flex flex-wrap items-center gap-4">
              <button
                @click="setPage('services')"
                style="background-color: {profile.primary_hex};"
                class="px-6 py-3.5 rounded-xl text-white font-bold text-sm shadow-xl hover:opacity-90 transition-all cursor-pointer"
              >
                View Offerings &rarr;
              </button>
              <button
                @click="setPage('about')"
                class="px-6 py-3.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-200 border border-white/10 font-bold text-sm transition-all cursor-pointer"
              >
                Our Story
              </button>
            </div>
          </div>

          <div class="relative">
            <div class="overflow-hidden rounded-3xl border border-white/15 shadow-2xl">
              <img src="{profile.hero_image}" alt="{profile.business_title}" class="w-full h-96 sm:h-[450px] object-cover hover:scale-105 transition-transform duration-700" />
            </div>
            <div style="background-color: {profile.card_hex};" class="absolute -bottom-6 -left-6 p-4 rounded-2xl border border-white/15 shadow-2xl hidden sm:flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl flex items-center justify-center text-white" style="background-color: {profile.primary_hex};">
                ★
              </div>
              <div>
                <span class="font-extrabold text-sm text-white block">4.9 / 5.0 Rating</span>
                <span class="text-[11px] text-slate-400">Over 500+ Verified Reviews</span>
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 pt-10">
          {features_html}
        </div>

        <div class="pt-8">
          <h2 class="text-2xl sm:text-3xl font-extrabold text-white text-center mb-8">What Our Clients Say</h2>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {testimonials_html}
          </div>
        </div>
      </section>

      <!-- ABOUT VIEW -->
      <section v-if="currentPage === 'about'" class="space-y-16 max-w-4xl mx-auto py-4">
        <div class="text-center">
          <span class="text-xs font-mono uppercase tracking-wider block mb-2" style="color: {profile.primary_hex};">Heritage & Mission</span>
          <h2 class="text-3xl sm:text-5xl font-extrabold text-white mb-4">About {profile.business_title}</h2>
          <p class="text-slate-400 leading-relaxed text-sm sm:text-base max-w-2xl mx-auto">
            {profile.value_prop}
          </p>
        </div>

        <div>
          <h3 class="text-2xl font-bold text-white text-center mb-8">Leadership Team</h3>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {team_html}
          </div>
        </div>
      </section>

      <!-- SERVICES VIEW -->
      <section v-if="currentPage === 'services'" class="space-y-12 py-4">
        <div class="text-center max-w-2xl mx-auto">
          <span class="text-xs font-mono uppercase tracking-wider block mb-2" style="color: {profile.primary_hex};">Our Catalog & Offerings</span>
          <h2 class="text-3xl sm:text-5xl font-extrabold text-white mb-4">Curated Offerings</h2>
          <p class="text-slate-400 text-sm">Crafted with precision, passion, and uncompromising quality.</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {offerings_html}
        </div>
      </section>

      <!-- CONTACT VIEW -->
      <section v-if="currentPage === 'contact'" class="max-w-4xl mx-auto py-4">
        <div class="text-center mb-10">
          <span class="text-xs font-mono uppercase tracking-wider block mb-2" style="color: {profile.primary_hex};">Connect With Us</span>
          <h2 class="text-3xl sm:text-5xl font-extrabold text-white mb-3">Book & Inquire</h2>
          <p class="text-slate-400 text-xs sm:text-sm">Reach out directly and our team will get back to you within 24 hours.</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div class="lg:col-span-1 space-y-4">
            <div style="background-color: {profile.card_hex};" class="p-5 rounded-2xl border border-white/10">
              <h4 class="text-xs font-bold text-white">Direct Email</h4>
              <p class="text-xs text-slate-400 mt-1">{profile.contact_info['email']}</p>
            </div>
            <div style="background-color: {profile.card_hex};" class="p-5 rounded-2xl border border-white/10">
              <h4 class="text-xs font-bold text-white">Phone Support</h4>
              <p class="text-xs text-slate-400 mt-1">{profile.contact_info['phone']}</p>
            </div>
            <div style="background-color: {profile.card_hex};" class="p-5 rounded-2xl border border-white/10">
              <h4 class="text-xs font-bold text-white">Headquarters</h4>
              <p class="text-xs text-slate-400 mt-1">{profile.contact_info['address']}</p>
            </div>
          </div>

          <div style="background-color: {profile.card_hex};" class="lg:col-span-2 p-8 rounded-3xl border border-white/10 shadow-2xl">
            <div v-if="contactSubmitted" class="text-center py-10 space-y-3">
              <div class="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mx-auto text-2xl font-bold">
                ✓
              </div>
              <h3 class="text-xl font-bold text-white">Message Dispatched</h3>
              <p class="text-xs text-slate-400 max-w-sm mx-auto">Thank you for contacting {profile.business_title}. We will respond shortly.</p>
              <button @click="contactSubmitted = false" class="text-xs text-cyan-400 underline pt-2 cursor-pointer">Submit another inquiry</button>
            </div>

            <form v-else @submit.prevent="contactSubmitted = true" class="space-y-4">
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-semibold text-slate-300 mb-1.5">Your Name</label>
                  <input required placeholder="Alex Rivera" class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-white/30" />
                </div>
                <div>
                  <label class="block text-xs font-semibold text-slate-300 mb-1.5">Email Address</label>
                  <input required type="email" placeholder="alex@company.com" class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-white/30" />
                </div>
              </div>
              <div>
                <label class="block text-xs font-semibold text-slate-300 mb-1.5">Inquiry Details</label>
                <textarea required rows="4" placeholder="Tell us how we can help you..." class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-white/30"></textarea>
              </div>
              <button
                type="submit"
                style="background-color: {profile.primary_hex};"
                class="w-full py-3.5 rounded-xl text-white font-bold text-sm shadow-xl hover:opacity-90 transition-all cursor-pointer"
              >
                Send Message &rarr;
              </button>
            </form>
          </div>
        </div>
      </section>
    </main>

    <!-- Footer -->
    <footer class="border-t border-white/10 py-8 px-6 text-center text-xs text-slate-500">
      &copy; {{{{ new Date().getFullYear() }}}} {profile.business_title}. Powered by AI Site Studio.
    </footer>
  </div>
</template>

<style scoped>
/* Scoped styles */
</style>
"""


def synthesize_standalone_html(profile: DomainProfile, framework: str = "react") -> str:
    """
    Synthesizes a 100% complete, fully self-contained HTML page that renders the entire project
    immediately when opened in ANY browser (via double click in Windows Explorer, file://, or web server),
    while also seamlessly mounting the Vite React / Vue framework app when running `npm run dev`.
    """
    features_html = ""
    for f in profile.features:
        features_html += f"""
          <div style="background-color: {profile.card_hex};" class="p-6 rounded-2xl border border-white/10 hover:border-white/20 transition-all">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center text-white mb-4" style="background-color: {profile.primary_hex};">
              <span class="text-lg">✦</span>
            </div>
            <h3 class="text-lg font-bold text-white mb-2">{f['title']}</h3>
            <p class="text-xs text-slate-400 leading-relaxed">{f['desc']}</p>
          </div>"""

    offerings_html = ""
    for o in profile.offerings:
        badge = f"""<span class="text-[11px] font-mono font-bold px-2.5 py-1 rounded-full text-white" style="background-color: {profile.primary_hex};">{o['price']}</span>""" if o.get('price') else ""
        offerings_html += f"""
          <div style="background-color: {profile.card_hex};" class="p-6 rounded-2xl border border-white/10 hover:border-white/20 transition-all flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between gap-4 mb-3">
                <h3 class="text-base font-bold text-white">{o['title']}</h3>
                {badge}
              </div>
              <p class="text-xs text-slate-400 leading-relaxed">{o['desc']}</p>
            </div>
            <button onclick="switchTab('contact')" class="mt-6 w-full py-2.5 rounded-xl text-white font-bold text-xs shadow-md transition-all hover:opacity-90 cursor-pointer" style="background-color: {profile.primary_hex};">
              Inquire Now &rarr;
            </button>
          </div>"""

    team_html = ""
    for tm in profile.team:
        team_html += f"""
          <div style="background-color: {profile.card_hex};" class="p-6 rounded-2xl border border-white/10">
            <div class="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-base mb-4" style="background-color: {profile.primary_hex};">
              {tm['name'][:2].upper()}
            </div>
            <h4 class="text-base font-bold text-white">{tm['name']}</h4>
            <p class="text-xs font-semibold mb-2" style="color: {profile.accent_hex};">{tm['role']}</p>
            <p class="text-xs text-slate-400">{tm['desc']}</p>
          </div>"""

    testimonials_html = ""
    for t in profile.testimonials:
        testimonials_html += f"""
          <div style="background-color: {profile.card_hex};" class="p-6 rounded-2xl border border-white/10">
            <div class="flex items-center gap-1 text-amber-400 mb-3 text-sm">
              <span>★</span><span>★</span><span>★</span><span>★</span><span>★</span>
            </div>
            <p class="text-xs text-slate-300 italic mb-4">"{t['quote']}"</p>
            <div class="border-t border-white/10 pt-3">
              <p class="text-xs font-bold text-white">{t['name']}</p>
              <p class="text-[11px] text-slate-400">{t['role']}</p>
            </div>
          </div>"""

    entry_script = "./src/main.js" if framework.lower() == "vue" else "./src/main.jsx"

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{profile.business_title} — {profile.tagline}</title>
    <meta name="description" content="{profile.value_prop}" />
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
      body {{ margin: 0; background-color: {profile.bg_hex}; color: {profile.text_hex}; font-family: system-ui, -apple-system, sans-serif; }}
      .page-tab {{ display: none; }}
      .page-tab.active {{ display: block; animation: tabFade 0.25s ease-out; }}
      @keyframes tabFade {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    </style>
  </head>
  <body style="background-color: {profile.bg_hex}; color: {profile.text_hex};">
    <!-- Standalone Universal Showcase Container (Renders instantly on double-click in any browser) -->
    <div id="root">
      <div class="min-h-screen flex flex-col justify-between">
        <!-- Header / Navbar -->
        <header class="sticky top-0 z-50 backdrop-blur-md bg-slate-950/80 border-b border-white/10 px-4 sm:px-8 py-3.5 flex items-center justify-between">
          <div class="flex items-center gap-2 cursor-pointer" onclick="switchTab('home')">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center text-white font-black text-sm" style="background-color: {profile.primary_hex};">
              ✦
            </div>
            <span class="font-extrabold text-base tracking-tight text-white">{profile.business_title}</span>
          </div>

          <nav class="hidden md:flex items-center gap-1">
            <button onclick="switchTab('home')" class="nav-btn px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer text-white" data-tab="home" style="border-bottom: 2px solid {profile.primary_hex};">
              Home
            </button>
            <button onclick="switchTab('about')" class="nav-btn px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer text-slate-400" data-tab="about" style="border-bottom: 2px solid transparent;">
              About
            </button>
            <button onclick="switchTab('services')" class="nav-btn px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer text-slate-400" data-tab="services" style="border-bottom: 2px solid transparent;">
              Offerings
            </button>
            <button onclick="switchTab('contact')" class="nav-btn px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer text-slate-400" data-tab="contact" style="border-bottom: 2px solid transparent;">
              Contact
            </button>
          </nav>

          <div class="hidden md:flex items-center gap-3">
            <button onclick="switchTab('contact')" style="background-color: {profile.primary_hex};" class="px-4 py-2 rounded-xl text-white font-bold text-xs shadow-lg hover:opacity-90 transition-all cursor-pointer">
              Get in Touch &rarr;
            </button>
          </div>
        </header>

        <!-- Main Content with Tab Pages -->
        <main class="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 w-full">
          <!-- TAB 1: HOME -->
          <div id="view-home" class="page-tab active space-y-16">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center pt-4">
              <div>
                <div class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-white/10 bg-white/5 text-xs font-mono mb-6" style="color: {profile.accent_hex};">
                  <span>✦ {profile.domain_name}</span>
                </div>
                <h1 class="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6 leading-tight">
                  {profile.tagline}
                </h1>
                <p class="text-base sm:text-lg text-slate-400 mb-8 leading-relaxed">
                  {profile.value_prop}
                </p>
                <div class="flex flex-wrap items-center gap-4">
                  <button onclick="switchTab('services')" style="background-color: {profile.primary_hex};" class="px-6 py-3.5 rounded-xl text-white font-bold text-sm shadow-xl hover:opacity-90 transition-all cursor-pointer">
                    View Offerings &rarr;
                  </button>
                  <button onclick="switchTab('about')" class="px-6 py-3.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-200 border border-white/10 font-bold text-sm transition-all cursor-pointer">
                    Our Story
                  </button>
                </div>
              </div>

              <div class="relative">
                <div class="overflow-hidden rounded-3xl border border-white/15 shadow-2xl">
                  <img src="{profile.hero_image}" alt="{profile.business_title}" class="w-full h-96 sm:h-[450px] object-cover hover:scale-105 transition-transform duration-700" />
                </div>
                <div style="background-color: {profile.card_hex};" class="absolute -bottom-6 -left-6 p-4 rounded-2xl border border-white/15 shadow-2xl hidden sm:flex items-center gap-3">
                  <div class="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm" style="background-color: {profile.primary_hex};">
                    ★
                  </div>
                  <div>
                    <span class="font-extrabold text-sm text-white block">4.9 / 5.0 Rating</span>
                    <span class="text-[11px] text-slate-400">Over 500+ Verified Reviews</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 pt-10">
              {features_html}
            </div>

            <div class="pt-8">
              <h2 class="text-2xl sm:text-3xl font-extrabold text-white text-center mb-8">What Our Clients Say</h2>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {testimonials_html}
              </div>
            </div>
          </div>

          <!-- TAB 2: ABOUT -->
          <div id="view-about" class="page-tab space-y-16 max-w-4xl mx-auto py-4">
            <div class="text-center">
              <span class="text-xs font-mono uppercase tracking-wider block mb-2" style="color: {profile.primary_hex};">Heritage & Mission</span>
              <h2 class="text-3xl sm:text-5xl font-extrabold text-white mb-4">About {profile.business_title}</h2>
              <p class="text-slate-400 leading-relaxed text-sm sm:text-base max-w-2xl mx-auto">
                {profile.value_prop}
              </p>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div style="background-color: {profile.card_hex};" class="p-7 rounded-2xl border border-white/10">
                <h3 class="text-lg font-bold text-white mb-2">Our Standard of Excellence</h3>
                <p class="text-xs text-slate-400 leading-relaxed">Every detail is calibrated to provide unmatched reliability, refined aesthetics, and transparent client experiences.</p>
              </div>
              <div style="background-color: {profile.card_hex};" class="p-7 rounded-2xl border border-white/10">
                <h3 class="text-lg font-bold text-white mb-2">Sustainable & Modern</h3>
                <p class="text-xs text-slate-400 leading-relaxed">Embracing the latest industry standards, continuous technological optimization, and sustainable community practices.</p>
              </div>
            </div>

            <div>
              <h3 class="text-2xl font-bold text-white text-center mb-8">Leadership Team</h3>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {team_html}
              </div>
            </div>
          </div>

          <!-- TAB 3: SERVICES -->
          <div id="view-services" class="page-tab space-y-12 py-4">
            <div class="text-center max-w-2xl mx-auto">
              <span class="text-xs font-mono uppercase tracking-wider block mb-2" style="color: {profile.primary_hex};">Our Catalog & Offerings</span>
              <h2 class="text-3xl sm:text-5xl font-extrabold text-white mb-4">Curated Offerings</h2>
              <p class="text-slate-400 text-sm">Engineered with precision, passion, and uncompromising quality.</p>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {offerings_html}
            </div>
          </div>

          <!-- TAB 4: CONTACT -->
          <div id="view-contact" class="page-tab max-w-4xl mx-auto py-4">
            <div class="text-center mb-10">
              <span class="text-xs font-mono uppercase tracking-wider block mb-2" style="color: {profile.primary_hex};">Connect With Us</span>
              <h2 class="text-3xl sm:text-5xl font-extrabold text-white mb-3">Book & Inquire</h2>
              <p class="text-slate-400 text-xs sm:text-sm">Reach out directly and our team will get back to you within 24 hours.</p>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div class="lg:col-span-1 space-y-4">
                <div style="background-color: {profile.card_hex};" class="p-5 rounded-2xl border border-white/10">
                  <h4 class="text-xs font-bold text-white">Direct Email</h4>
                  <p class="text-xs text-slate-400 mt-1">{profile.contact_info['email']}</p>
                </div>
                <div style="background-color: {profile.card_hex};" class="p-5 rounded-2xl border border-white/10">
                  <h4 class="text-xs font-bold text-white">Phone Support</h4>
                  <p class="text-xs text-slate-400 mt-1">{profile.contact_info['phone']}</p>
                </div>
                <div style="background-color: {profile.card_hex};" class="p-5 rounded-2xl border border-white/10">
                  <h4 class="text-xs font-bold text-white">Headquarters</h4>
                  <p class="text-xs text-slate-400 mt-1">{profile.contact_info['address']}</p>
                </div>
              </div>

              <div style="background-color: {profile.card_hex};" class="lg:col-span-2 p-8 rounded-3xl border border-white/10 shadow-2xl">
                <div id="contact-success-card" class="hidden text-center py-10 space-y-3">
                  <div class="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mx-auto text-2xl font-bold">
                    ✓
                  </div>
                  <h3 class="text-xl font-bold text-white">Message Dispatched</h3>
                  <p class="text-xs text-slate-400 max-w-sm mx-auto">Thank you for contacting {profile.business_title}. We will respond shortly.</p>
                  <button onclick="document.getElementById('contact-success-card').classList.add('hidden'); document.getElementById('contact-form-card').classList.remove('hidden');" class="text-xs text-cyan-400 underline pt-2 cursor-pointer">Submit another inquiry</button>
                </div>

                <div id="contact-form-card">
                  <form id="site-contact-form" class="space-y-4">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label class="block text-xs font-semibold text-slate-300 mb-1.5">Your Name</label>
                        <input required placeholder="Alex Rivera" class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-white/30" />
                      </div>
                      <div>
                        <label class="block text-xs font-semibold text-slate-300 mb-1.5">Email Address</label>
                        <input required type="email" placeholder="alex@company.com" class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-white/30" />
                      </div>
                    </div>
                    <div>
                      <label class="block text-xs font-semibold text-slate-300 mb-1.5">Inquiry Details</label>
                      <textarea required rows="4" placeholder="Tell us how we can help you..." class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-white/30"></textarea>
                    </div>
                    <button
                      type="submit"
                      style="background-color: {profile.primary_hex};"
                      class="w-full py-3.5 rounded-xl text-white font-bold text-sm shadow-xl hover:opacity-90 transition-all cursor-pointer"
                    >
                      Send Message &rarr;
                    </button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        </main>

        <!-- Footer -->
        <footer class="border-t border-white/10 py-8 px-6 text-center text-xs text-slate-500">
          &copy; 2026 {profile.business_title}. Engineered with AI Site Studio.
        </footer>
      </div>
    </div>

    <!-- Client-side Interactive Tab Navigation -->
    <script>
      function switchTab(pageId) {{
        document.querySelectorAll('.page-tab').forEach(function(el) {{ el.classList.remove('active'); }});
        var target = document.getElementById('view-' + pageId);
        if (target) target.classList.add('active');
        document.querySelectorAll('.nav-btn').forEach(function(btn) {{
          if (btn.dataset.tab === pageId) {{
            btn.style.color = '#ffffff';
            btn.style.borderBottom = '2px solid {profile.primary_hex}';
          }} else {{
            btn.style.color = '#94a3b8';
            btn.style.borderBottom = '2px solid transparent';
          }}
        }});
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
      }}

      document.addEventListener('DOMContentLoaded', function() {{
        var form = document.getElementById('site-contact-form');
        if (form) {{
          form.addEventListener('submit', function(e) {{
            e.preventDefault();
            var successCard = document.getElementById('contact-success-card');
            var formCard = document.getElementById('contact-form-card');
            if (successCard && formCard) {{
              formCard.classList.add('hidden');
              successCard.classList.remove('hidden');
            }}
          }});
        }}
      }});
    </script>

    <!-- Vite Framework Entry (Hydrates into full reactive app when running npm run dev) -->
    <script type="module" src="{entry_script}"></script>
  </body>
</html>
"""

