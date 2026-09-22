import React from "react";
import {
  Sparkles, Box, Check, Star, ArrowRight, Shield, Zap,
  ExternalLink, RefreshCw, Layers, Monitor, FileText, Mail,
  ShoppingBag, Phone, MapPin, Clock, ChevronRight, CheckCircle2
} from "lucide-react";
import { cn } from "@/lib/utils";

export const PRESET_THEMES = [
  { id: "saas", label: "SaaS Modern", emoji: "🚀", color: "#6366f1", desc: "Tech startups, devtools & cloud apps" },
  { id: "ecommerce", label: "E-Commerce", emoji: "🛍️", color: "#0f766e", desc: "Bespoke goods, fashion & lifestyle" },
  { id: "bakery", label: "Artisanal Café", emoji: "☕", color: "#d97706", desc: "French bakery, bistro & roastery" },
  { id: "medical", label: "Healthcare", emoji: "🏥", color: "#059669", desc: "Holistic clinic, dental & wellness" },
  { id: "agency", label: "Creative Agency", emoji: "💎", color: "#8b5cf6", desc: "Design studio, brand craft & WebGL" },
];

export const STORYBOOK_SECTION_PRESETS = {
  brand: {
    saas: {
      business_name: "Apex Cloud Studio",
      tagline: "Autonomous Cloud Infrastructure & AI Automation",
      logo_text: "APEX",
      primary_color: "#4f46e5",
      secondary_color: "#0ea5e9",
      contact_email: "hello@apexcloud.io",
      contact_phone: "+1 (800) 555-0199",
    },
    ecommerce: {
      business_name: "Luxe Atelier Store",
      tagline: "Handcrafted Luxury Apparel & Organic Goods",
      logo_text: "LUXE",
      primary_color: "#0f766e",
      secondary_color: "#f59e0b",
      contact_email: "care@luxeatelier.shop",
      contact_phone: "+1 (888) 400-2910",
    },
    bakery: {
      business_name: "Café de Paris",
      tagline: "Authentic French Bakery & Artisanal Espresso",
      logo_text: "PARIS",
      primary_color: "#d97706",
      secondary_color: "#78350f",
      contact_email: "bonjour@cafedeparis.fr",
      contact_phone: "+33 1 42 68 55 00",
    },
    medical: {
      business_name: "Aura Dental & Wellness",
      tagline: "Gentle Modern Dentistry & Whole-Body Health",
      logo_text: "AURA",
      primary_color: "#059669",
      secondary_color: "#0284c7",
      contact_email: "appointments@auraclinic.com",
      contact_phone: "+1 (310) 555-8822",
    },
    agency: {
      business_name: "Studio Vanguard",
      tagline: "Award-Winning Brand Architecture & Digital Craft",
      logo_text: "VANGUARD",
      primary_color: "#8b5cf6",
      secondary_color: "#f43f5e",
      contact_email: "hello@vanguard.design",
      contact_phone: "+1 (415) 555-3301",
    },
  },
  navbar: {
    saas: {
      brandName: "Apex Cloud",
      logoText: "APEX",
      link1: "Platform",
      link2: "Integrations",
      link3: "Pricing",
      ctaText: "Deploy Now",
    },
    ecommerce: {
      brandName: "Luxe Atelier",
      logoText: "LUXE",
      link1: "New Arrivals",
      link2: "Collections",
      link3: "Sustainability",
      ctaText: "Shop Catalog",
    },
    bakery: {
      brandName: "Café de Paris",
      logoText: "PARIS",
      link1: "Menu",
      link2: "Our Story",
      link3: "Catering",
      ctaText: "Reserve Table",
    },
    medical: {
      brandName: "Aura Clinic",
      logoText: "AURA",
      link1: "Treatments",
      link2: "Specialists",
      link3: "Patient Portal",
      ctaText: "Book Visit",
    },
    agency: {
      brandName: "Studio Vanguard",
      logoText: "VANGUARD",
      link1: "Work",
      link2: "Methodology",
      link3: "Manifesto",
      ctaText: "Start Project",
    },
  },
  hero: {
    saas: {
      badgeText: "🚀 Next-Gen React & Storybook UI",
      headline: "Autonomous Cloud Workflows Built for Scale",
      subheadline: "Connect your repositories, synthesize type-safe React templates, and launch production micro-apps in seconds.",
      primaryCta: "Start Free Trial",
      secondaryCta: "Watch 2-Min Demo",
      stat1_value: "99.99%",
      stat1_label: "Uptime SLA",
      stat2_value: "450k+",
      stat2_label: "Deployments",
      stat3_value: "10x",
      stat3_label: "Velocity Boost",
    },
    ecommerce: {
      badgeText: "✨ Handpicked Spring 2026 Collection",
      headline: "Elevated Essentials for Mindful Living",
      subheadline: "Explore sustainable textiles, bespoke ceramics, and ethically sourced lifestyle goods crafted by world-class artisans.",
      primaryCta: "Explore Collection",
      secondaryCta: "Read Craft Journal",
      stat1_value: "100%",
      stat1_label: "Organic Cotton",
      stat2_value: "25k+",
      stat2_label: "Happy Customers",
      stat3_value: "Free",
      stat3_label: "Global Shipping",
    },
    bakery: {
      badgeText: "🥐 Fresh From Oven Every 30 Mins",
      headline: "Warm French Croissants & Single-Origin Roast",
      subheadline: "Handcrafted in the traditional French method using stone-ground Normandy wheat and slow-churned butter.",
      primaryCta: "Order Online",
      secondaryCta: "View Daily Menu",
      stat1_value: "1974",
      stat1_label: "Founded in Paris",
      stat2_value: "1,200+",
      stat2_label: "Pastries Daily",
      stat3_value: "4.9 ★",
      stat3_label: "Google Reviews",
    },
    medical: {
      badgeText: "🏥 State-of-the-Art Holistic Care",
      headline: "Gentle Laser Dentistry & Whole-Body Wellness",
      subheadline: "Experience stress-free dental exams, 3D laser imaging, and pain-free whitening in our calm spa-like clinic.",
      primaryCta: "Schedule Appointment",
      secondaryCta: "Meet Doctors",
      stat1_value: "20+",
      stat1_label: "Years Experience",
      stat2_value: "15k+",
      stat2_label: "Smiles Restored",
      stat3_value: "100%",
      stat3_label: "Pain-Free Tech",
    },
    agency: {
      badgeText: "💎 Cannes Lions & Awwwards Studio of Year",
      headline: "We Shape Brands That Command Industry Leadership",
      subheadline: "High-conviction digital design, design tokens, and immersive web experiences for category-defining companies.",
      primaryCta: "Explore Showcase",
      secondaryCta: "Request Proposal",
      stat1_value: "38+",
      stat1_label: "Design Awards",
      stat2_value: "$2.4B",
      stat2_label: "Client Valuation Added",
      stat3_value: "14",
      stat3_label: "Years in Craft",
    },
  },
  services: {
    saas: {
      title: "Enterprise Architecture & Capabilities",
      s1_title: "Instant Code Synthesis",
      s1_desc: "Generate production-grade TypeScript components adhering to strict design tokens.",
      s2_title: "Automated Test Harness",
      s2_desc: "Self-healing Playwright and Jest test suites generated automatically.",
      s3_title: "Zero-Config Edge Deploy",
      s3_desc: "Global CDN edge distribution with sub-10ms TTFB across 285 locations.",
    },
    ecommerce: {
      title: "Our Artisanal Guarantees",
      s1_title: "Ethical Sourcing",
      s1_desc: "Every raw textile is verified fair-trade from independent regenerative farms.",
      s2_title: "Lifetime Repair Warranty",
      s2_desc: "We mend and condition all leather and denim goods free of charge for life.",
      s3_title: "Carbon-Neutral Delivery",
      s3_desc: "100% compostable packaging with offset maritime and land freight.",
    },
    bakery: {
      title: "Artisanal Baking Methodology",
      s1_title: "72-Hour Sourdough Ferment",
      s1_desc: "Slow wild fermentation yields complex aromas, crispy crusts, and easy digestion.",
      s2_title: "Normandy Cultured Butter",
      s2_desc: "84% butterfat French pasture butter creates the signature honeycomb crumb.",
      s3_title: "Specialty Micro-Roast Coffee",
      s3_desc: "Direct-trade beans roasted in small batches weekly for peak floral notes.",
    },
    medical: {
      title: "Comprehensive Clinical Services",
      s1_title: "Laser Cosmetic Dentistry",
      s1_desc: "Single-visit ceramic veneers and painless enamel-safe laser whitening.",
      s2_title: "3D Digital Implantology",
      s2_desc: "Guided computer-assisted implant placement with lifetime titanium warranty.",
      s3_title: "Anxiety-Free Sedation",
      s3_desc: "Gentle nitrous oxide and soothing music therapy for completely relaxed visits.",
    },
    agency: {
      title: "Our Design Disciplines",
      s1_title: "Identity & Design Systems",
      s1_desc: "Multi-platform design systems with codified tokens, typography, and React libraries.",
      s2_title: "Interactive Web & 3D WebGL",
      s2_desc: "Fluid 60fps animations and WebGL shaders that create unforgettable brand impressions.",
      s3_title: "Product Strategy & Growth",
      s3_desc: "Conversion-optimized customer journeys that turn casual visitors into loyal advocates.",
    },
  },
  about: {
    saas: {
      title: "Architecting the Future of Agentic Software",
      story: "Founded by veteran cloud engineers, Apex Cloud Studio bridges the gap between dynamic code synthesis and enterprise scalability. Over 10,000 teams trust our platform for mission-critical digital products.",
      mission: "To eliminate repetitive UI boilerplate and liberate developers to build extraordinary products.",
      team_count: "48 Cloud Engineers & Architects across 12 countries",
    },
    ecommerce: {
      title: "A Commitment to Timeless Craft & Planetary Care",
      story: "Luxe Atelier began with a simple belief: clothing should be made to endure decades, not seasons. We partner directly with heritage weavers and master ceramists.",
      mission: "To foster conscious consumption through heirloom-quality craftsmanship and radical transparency.",
      team_count: "35 Master Artisans & Sustainable Weavers",
    },
    bakery: {
      title: "Over 50 Years of Parisian Baking Heritage",
      story: "Established in 1974 in the 6th arrondissement of Paris, Café de Paris preserves the rigorous craft of classical French boulangerie and patisserie.",
      mission: "To bring the authentic aroma, warmth, and hospitality of Paris to every neighborhood we serve.",
      team_count: "18 French Master Bakers & Baristas",
    },
    medical: {
      title: "Pioneering Holistic, Compassionate Healthcare",
      story: "Aura Clinic was founded by Dr. Elena Vance to transform the dental experience from cold and intimidating to restorative, serene, and luxurious.",
      mission: "To deliver world-class dental precision alongside genuine human warmth and patient comfort.",
      team_count: "14 Specialized Doctors, Hygienists & Care Coordinators",
    },
    agency: {
      title: "Where Radical Creative Meets Precise Engineering",
      story: "Vanguard is an independent design laboratory. We reject cookie-cutter templates in favor of bespoke creative direction that redefines categories.",
      mission: "To elevate great companies into iconic cultural forces through peerless brand craft.",
      team_count: "26 Creative Directors, Shaders Artists & Engineers",
    },
  },
  pricing: {
    saas: {
      tierName: "Growth Engine",
      price: "$79",
      billingPeriod: "/ month",
      description: "Ideal for scaling engineering teams and startups.",
      feature1: "Unlimited Production Deployments",
      feature2: "Full Commercial React & Next.js Code",
      feature3: "24/7 Priority SLA & Dedicated Architect",
      popular: true,
      ctaText: "Deploy Growth Plan",
    },
    ecommerce: {
      tierName: "Collector Membership",
      price: "$29",
      billingPeriod: "/ year",
      description: "Exclusive access to limited archival releases.",
      feature1: "Early Access to Limited Capsule Runs",
      feature2: "Free Global Express Carbon-Neutral Delivery",
      feature3: "Complimentary Bespoke Monogramming",
      popular: true,
      ctaText: "Join Membership",
    },
    bakery: {
      tierName: "Pastry Club Box",
      price: "$35",
      billingPeriod: "/ month",
      description: "Weekly artisanal baked goods delivered hot.",
      feature1: "Weekly Box of 6 Warm Viennoiseries",
      feature2: "1 Bag of House Roast Arabica Beans",
      feature3: "15% Off All In-Café Orders",
      popular: true,
      ctaText: "Subscribe to Club",
    },
    medical: {
      tierName: "Wellness Care Plan",
      price: "$49",
      billingPeriod: "/ month",
      description: "Comprehensive preventive oral healthcare.",
      feature1: "2 Comprehensive Exams & Laser Cleanings",
      feature2: "Full 3D Panoramic Imaging Included",
      feature3: "20% Off All Cosmetic Treatments",
      popular: true,
      ctaText: "Enroll in Care Plan",
    },
    agency: {
      tierName: "Retainer Partnership",
      price: "$4,500",
      billingPeriod: "/ sprint",
      description: "Dedicated full-stack design & engineering pod.",
      feature1: "Dedicated Senior Product Designer & Lead Dev",
      feature2: "Bi-Weekly Production Ship Cycles",
      feature3: "Complete IP & Source Code Ownership",
      popular: true,
      ctaText: "Initiate Retainer",
    },
  },
  contact: {
    saas: {
      email: "enterprise@apexcloud.io",
      phone: "+1 (800) 555-0199",
      address: "100 Pine St, Suite 2400, San Francisco, CA 94111",
      hours: "Mon - Fri: 24/7 Emergency Support SLA",
    },
    ecommerce: {
      email: "concierge@luxeatelier.shop",
      phone: "+1 (888) 400-2910",
      address: "420 West Broadway, SoHo, New York, NY 10012",
      hours: "Mon - Sat: 10:00 AM - 7:00 PM EST",
    },
    bakery: {
      email: "bonjour@cafedeparis.fr",
      phone: "+33 1 42 68 55 00",
      address: "14 Rue de Buci, 75006 Paris, France",
      hours: "Daily: 6:30 AM - 8:00 PM CET",
    },
    medical: {
      email: "care@auraclinic.com",
      phone: "+1 (310) 555-8822",
      address: "9454 Wilshire Blvd, Beverly Hills, CA 90212",
      hours: "Mon - Fri: 8:00 AM - 6:00 PM PST",
    },
    agency: {
      email: "collaborate@vanguard.design",
      phone: "+1 (415) 555-3301",
      address: "550 Montgomery St, San Francisco, CA 94111",
      hours: "Mon - Fri: 9:00 AM - 6:00 PM PST",
    },
  },
  footer: {
    saas: {
      brandName: "Apex Cloud Studio",
      tagline: "The fastest way to engineer, deploy, and scale modern web apps.",
      copyrightText: "© 2026 Apex Cloud Studio Inc. All rights reserved.",
    },
    ecommerce: {
      brandName: "Luxe Atelier",
      tagline: "Handcrafted heirloom essentials for conscious modern lifestyles.",
      copyrightText: "© 2026 Luxe Atelier Goods. Responsibly crafted.",
    },
    bakery: {
      brandName: "Café de Paris",
      tagline: "Traditional French viennoiserie, artisan sourdough & specialty espresso.",
      copyrightText: "© 1974–2026 Café de Paris Boulangerie. Fait avec amour.",
    },
    medical: {
      brandName: "Aura Dental & Wellness",
      tagline: "Modern gentle dentistry, laser aesthetics & compassionate healthcare.",
      copyrightText: "© 2026 Aura Medical Group. Accredited Board of Dentistry.",
    },
    agency: {
      brandName: "Studio Vanguard",
      tagline: "Brand strategy, digital experiences and design systems for category leaders.",
      copyrightText: "© 2026 Studio Vanguard LLC. All rights reserved.",
    },
  },
};

/**
 * StorybookPresetBar — Renders 1-click Storybook Preset fetch controls for a specific section
 */
export function StorybookPresetBar({ sectionKey, onFetchPreset, activePreset = "saas" }) {
  return (
    <div className="section-storybook-banner">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5">
          <div className="w-5 h-5 rounded-md bg-gradient-to-tr from-pink-500 to-indigo-600 flex items-center justify-center text-white text-[10px] font-black shadow-sm">
            SB
          </div>
          <div>
            <span className="text-xs font-bold text-foreground">Auto-Fetch from Storybook</span>
            <span className="text-[10px] text-pink-400 font-mono block">@ecommerce/ui &bull; {sectionKey.toUpperCase()}</span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => onFetchPreset(activePreset || "saas")}
          className="px-2.5 py-1 bg-gradient-to-r from-pink-500 to-indigo-600 hover:opacity-95 text-white rounded-lg text-[11px] font-bold flex items-center gap-1 shadow-sm transition-all"
          title="Instantly fetch curated Storybook content into this form"
        >
          <Zap className="w-3 h-3 fill-current" />
          <span>Fetch Content</span>
        </button>
      </div>

      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[10px] font-semibold text-muted-foreground mr-0.5">Presets:</span>
        {PRESET_THEMES.map((theme) => {
          const isSelected = activePreset === theme.id;
          return (
            <button
              key={theme.id}
              type="button"
              onClick={() => onFetchPreset(theme.id)}
              className={cn(
                "storybook-preset-pill",
                isSelected && "active"
              )}
              title={theme.desc}
            >
              <span>{theme.emoji}</span>
              <span>{theme.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * StorybookMiniPreview — Renders an interactive live Storybook preview card inside each section editor
 */
export function StorybookMiniPreview({ section, brand, pages }) {
  const primaryColor = brand?.primary_color || "#4f46e5";
  const secondaryColor = brand?.secondary_color || "#0ea5e9";

  return (
    <div className="storybook-mini-preview-card">
      <div className="mini-preview-header">
        <div className="flex items-center gap-1.5">
          <span className="live-dot" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Live Storybook Component &bull; {section.toUpperCase()}
          </span>
        </div>
        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-pink-500/10 text-pink-400 font-bold border border-pink-500/20">
          STORY PREVIEW
        </span>
      </div>

      <div className="mini-preview-stage">
        {/* BRAND PREVIEW */}
        {section === "brand" && (
          <div className="w-full p-3 rounded-lg bg-card border border-border/60 text-left space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-black text-xs shadow-md"
                  style={{ background: `linear-gradient(135deg, ${primaryColor}, ${secondaryColor})` }}
                >
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <h5 className="font-bold text-xs text-foreground">{brand?.business_name || "Apex Design"}</h5>
                  <p className="text-[10px] text-muted-foreground">{brand?.tagline || "Brand Slogan"}</p>
                </div>
              </div>
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                {brand?.logo_text || "APEX"}
              </span>
            </div>

            <div className="flex items-center gap-3 pt-2 border-t border-border/40 text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded-full border border-white/20 shadow-sm" style={{ backgroundColor: primaryColor }} />
                <span className="font-mono text-muted-foreground">Primary: {primaryColor}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded-full border border-white/20 shadow-sm" style={{ backgroundColor: secondaryColor }} />
                <span className="font-mono text-muted-foreground">Secondary: {secondaryColor}</span>
              </div>
            </div>
          </div>
        )}

        {/* NAVBAR PREVIEW */}
        {section === "navbar" && (
          <div className="w-full p-2.5 rounded-lg bg-card/90 backdrop-blur-md border border-border/70 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <div
                className="w-6 h-6 rounded-md flex items-center justify-center text-white text-[10px] font-black shadow-sm"
                style={{ background: `linear-gradient(135deg, ${primaryColor}, ${secondaryColor})` }}
              >
                <Sparkles className="w-3 h-3" />
              </div>
              <span className="font-bold text-foreground text-xs">{pages?.navbar?.brand_name || brand?.business_name || "Apex Studio"}</span>
            </div>
            <div className="hidden sm:flex items-center gap-3 text-[11px] text-muted-foreground font-medium">
              <span>{pages?.navbar?.link1 || "Home"}</span>
              <span>{pages?.navbar?.link2 || "About"}</span>
              <span>{pages?.navbar?.link3 || "Services"}</span>
            </div>
            <button
              type="button"
              className="px-2.5 py-1 rounded-md text-white text-[10px] font-bold shadow-sm"
              style={{ backgroundColor: primaryColor }}
            >
              {pages?.navbar?.cta_text || "Get Started"}
            </button>
          </div>
        )}

        {/* HERO PREVIEW */}
        {section === "hero" && (
          <div className="w-full p-4 rounded-xl bg-card border border-border/60 text-center space-y-2">
            <span
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border"
              style={{
                color: primaryColor,
                borderColor: `${primaryColor}44`,
                backgroundColor: `${primaryColor}15`
              }}
            >
              <Zap className="w-3 h-3" />
              {brand?.tagline || "High-Converting Headline"}
            </span>
            <h4 className="font-extrabold text-sm text-foreground leading-snug">
              {pages?.home?.hero_title || "Build Production-Ready Web Apps 10x Faster"}
            </h4>
            <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2 max-w-sm mx-auto">
              {pages?.home?.hero_subtitle || "Deploy beautifully engineered React and Next.js templates pre-linked with dynamic components."}
            </p>
            <div className="flex items-center justify-center gap-2 pt-1">
              <button
                type="button"
                className="px-3 py-1.5 rounded-lg text-white text-xs font-bold flex items-center gap-1 shadow-md"
                style={{ backgroundColor: primaryColor }}
              >
                <span>{pages?.home?.cta_primary || "Get Started"}</span>
                <ChevronRight className="w-3 h-3" />
              </button>
              <button
                type="button"
                className="px-3 py-1.5 rounded-lg border border-border bg-muted/50 text-foreground text-xs font-semibold"
              >
                {pages?.home?.cta_secondary || "Learn More"}
              </button>
            </div>
          </div>
        )}

        {/* SERVICES PREVIEW */}
        {section === "services" && (
          <div className="w-full p-3 rounded-xl bg-card border border-border/60 text-left space-y-2">
            <div className="flex items-center justify-between">
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-xs font-bold shadow-sm"
                style={{ backgroundColor: `${primaryColor}25`, color: primaryColor }}
              >
                <Layers className="w-3.5 h-3.5" />
              </div>
              <span className="text-[10px] font-bold text-indigo-400 font-mono">FEATURE CARD</span>
            </div>
            <h5 className="font-bold text-xs text-foreground mt-1">
              {pages?.services?.s1_title || "Instant Code Synthesis"}
            </h5>
            <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
              {pages?.services?.s1_desc || "Generate production-grade TypeScript components adhering to strict design tokens."}
            </p>
            <button
              type="button"
              className="text-[11px] font-bold flex items-center gap-1 pt-1"
              style={{ color: primaryColor }}
            >
              <span>Explore Capability</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        )}

        {/* ABOUT PREVIEW */}
        {section === "about" && (
          <div className="w-full p-3 rounded-xl bg-card border border-border/60 text-left space-y-2">
            <div className="flex items-center gap-1 text-amber-400">
              {[...Array(5)].map((_, i) => (
                <Star key={i} className="w-3 h-3 fill-current" />
              ))}
            </div>
            <h5 className="font-bold text-xs text-foreground">
              {pages?.about?.title || "Crafting the Future of Web Design"}
            </h5>
            <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-3 italic">
              "{pages?.about?.story || "Founded in 2024, our studio bridges the gap between dynamic code generation and human craft."}"
            </p>
            <div className="pt-2 border-t border-border/40 flex items-center justify-between text-[10px]">
              <span className="font-bold text-foreground">Scale & Team</span>
              <span className="font-semibold text-muted-foreground">{pages?.about?.team_count || "24 Engineers"}</span>
            </div>
          </div>
        )}

        {/* PRICING PREVIEW */}
        {section === "pricing" && (
          <div className="w-full max-w-xs mx-auto p-3.5 rounded-xl bg-card border border-indigo-500/40 shadow-md text-left relative">
            <span
              className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full text-[9px] font-black text-white"
              style={{ backgroundColor: primaryColor }}
            >
              POPULAR TIER
            </span>
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              {pages?.pricing?.tier2_name || "Commercial Plan"}
            </span>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-2xl font-black text-foreground" style={{ color: primaryColor }}>
                {pages?.pricing?.tier2_price || "$129"}
              </span>
              <span className="text-[10px] text-muted-foreground">{pages?.pricing?.tier2_period || "/ month"}</span>
            </div>
            <div className="space-y-1.5 mt-2.5 pt-2 border-t border-border/40 text-[10px]">
              {(pages?.pricing?.tier2_features || ["Unlimited Domains", "Commercial License", "Priority Support"]).slice(0, 3).map((f, i) => (
                <div key={i} className="flex items-center gap-1.5 text-muted-foreground">
                  <Check className="w-3 h-3 text-emerald-500 flex-shrink-0" />
                  <span>{f}</span>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="w-full mt-3 py-1.5 rounded-lg text-white font-bold text-[11px] shadow-sm"
              style={{ backgroundColor: primaryColor }}
            >
              Choose Plan
            </button>
          </div>
        )}

        {/* CONTACT PREVIEW */}
        {section === "contact" && (
          <div className="w-full p-3 rounded-xl bg-card border border-border/60 text-left space-y-2">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-xs flex items-center gap-2">
              <Mail className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
              <span className="font-mono text-[11px] text-foreground truncate">{pages?.contact?.email || brand?.contact_email || "support@studio.com"}</span>
            </div>
            <div className="p-2 rounded-lg bg-muted/40 border border-border/40 text-xs flex items-center gap-2">
              <Phone className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
              <span className="font-mono text-[11px] text-foreground">{pages?.contact?.phone || brand?.contact_phone || "+1 (555) 019-2834"}</span>
            </div>
            <div className="p-2 rounded-lg bg-muted/40 border border-border/40 text-xs flex items-center gap-2">
              <MapPin className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
              <span className="text-[10px] text-muted-foreground truncate">{pages?.contact?.address || "500 Innovation Way, San Francisco, CA"}</span>
            </div>
          </div>
        )}

        {/* FOOTER PREVIEW */}
        {section === "footer" && (
          <div className="w-full p-3 rounded-xl bg-card border border-border/60 text-left space-y-2">
            <div className="flex items-center justify-between">
              <div>
                <h5 className="font-bold text-xs text-foreground">{pages?.footer?.brand_name || brand?.business_name || "Apex Studio"}</h5>
                <p className="text-[10px] text-muted-foreground">{pages?.footer?.tagline || brand?.tagline || "Digital Solutions"}</p>
              </div>
              <span className="text-[9px] font-mono text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded">FOOTER</span>
            </div>
            <div className="pt-2 border-t border-border/40 flex items-center justify-between text-[10px] text-muted-foreground">
              <span>{pages?.footer?.copyright || `© ${new Date().getFullYear()} All rights reserved.`}</span>
              <span className="font-semibold">Storybook UI</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
