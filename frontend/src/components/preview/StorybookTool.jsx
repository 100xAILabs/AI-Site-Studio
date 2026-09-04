import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  Monitor, Zap, Layers, FileText, Sparkles, Star, Mail,
  Shield, AlertCircle, Edit3, Trash2, Eraser, Plus, RefreshCw,
  Check, Copy, RotateCcw, ExternalLink, Sun, Moon, Grid,
  Laptop, Tablet, Smartphone, Search, CheckCircle2, ChevronRight,
  Eye, Sliders, Code, X
} from "lucide-react";
import { cn } from "@/lib/utils";

// ─────────────────────────────────────────────────────────────────────────────
// Business Website Sections (Actual Names, Not Developer Primitives)
// ─────────────────────────────────────────────────────────────────────────────
const INITIAL_SECTIONS = [
  {
    id: "navbar",
    name: "Navigation Header",
    icon: Monitor,
    desc: "Top site navigation bar with brand logo, menu links, and CTA button",
    targetSection: "navbar"
  },
  {
    id: "hero",
    name: "Hero Section",
    icon: Zap,
    desc: "High-impact conversion banner with headline, dual CTAs, and trust stats",
    targetSection: "hero"
  },
  {
    id: "services",
    name: "Services & Features",
    icon: Layers,
    desc: "3-column feature showcase highlighting core capabilities",
    targetSection: "services"
  },
  {
    id: "about",
    name: "About Us & Story",
    icon: FileText,
    desc: "Company mission, background story, and team scale metrics",
    targetSection: "about"
  },
  {
    id: "pricing",
    name: "Pricing & Plans",
    icon: Sparkles,
    desc: "Tiered subscription packages with popular highlight badge",
    targetSection: "pricing"
  },
  {
    id: "testimonials",
    name: "Customer Reviews",
    icon: Star,
    desc: "Client testimonials with star ratings and verified credentials",
    targetSection: "about"
  },
  {
    id: "contact",
    name: "Contact & Inquiries",
    icon: Mail,
    desc: "Lead capture inquiry form with email, phone, and address",
    targetSection: "contact"
  },
  {
    id: "announcement",
    name: "Announcement Banner",
    icon: AlertCircle,
    desc: "Top promo or notification banner for special offers and updates",
    targetSection: "announcement"
  },
  {
    id: "footer",
    name: "Website Footer",
    icon: Shield,
    desc: "Site footer with brand info, legal copyright, and quick links",
    targetSection: "footer"
  }
];

// 1-Click Business Presets
const BUSINESS_PRESETS = [
  {
    id: "saas",
    name: "🚀 SaaS / Tech",
    data: {
      navbar: { brandName: "CloudPulse SaaS", logoText: "PULSE", link1: "Platform", link2: "Solutions", link3: "Pricing", ctaText: "Start Free Trial" },
      hero: { badgeText: "⚡ Next-Gen Cloud Platform", headline: "Automate Workflows & Scale Operations 10x Faster", subheadline: "The modern all-in-one developer workspace designed to streamline cloud infrastructure and deployment pipelines.", primaryCta: "Start Free Trial", secondaryCta: "Book Live Demo", stat1Value: "99.99%", stat1Label: "Cloud Uptime", stat2Value: "12,000+", stat2Label: "Teams Shipping" },
      services: { sectionTitle: "Engineered for High-Velocity Teams", sectionSubtitle: "Everything you need to ship resilient cloud apps.", s1Title: "Real-Time Telemetry", s1Desc: "Monitor latency, throughput, and error budgets across microservices.", s2Title: "Automated Deployments", s2Desc: "Git push to production with canary rollouts and rollback safeguards.", s3Title: "SOC2 Compliance", s3Desc: "Enterprise-grade encryption and audit trails." },
      about: { badgeText: "About CloudPulse", title: "Building the Operating System for Cloud Teams", story: "Founded by former cloud architects, CloudPulse was built to eliminate deployment friction.", mission: "To make cloud orchestration as simple as writing a single line of code.", teamCount: "48 Core Engineers" },
      pricing: { title: "Simple, Predictable Cloud Pricing", subtitle: "Pay only for what you build.", tier1Name: "Developer", tier1Price: "$29", tier1Period: "/ mo", tier2Name: "Pro Team", tier2Price: "$99", tier2Period: "/ mo", tier3Name: "Enterprise", tier3Price: "$299", tier3Period: "/ mo" },
      testimonials: { sectionTitle: "Loved by Top Engineering Leaders", quote: "CloudPulse cut our CI/CD pipeline time from 45 minutes to 4 minutes.", author: "David Chen", role: "VP of Engineering", company: "Aura FinTech", rating: "5" },
      contact: { title: "Talk to Our Solutions Engineers", subtitle: "Schedule a technical demo or get help migrating.", email: "sales@cloudpulse.io", phone: "+1 (888) 555-0142", address: "100 Montgomery St, San Francisco, CA" },
      announcement: { badge: "Product Update", title: "v4.2 Kubernetes Autoscaling Live", message: "Deploy dynamic node pools with 40% lower memory footprint.", ctaText: "See What's New" },
      footer: { brandName: "CloudPulse Technologies Inc.", tagline: "The modern developer workspace for cloud orchestration.", copyright: "© 2026 CloudPulse Inc. All rights reserved." }
    }
  },
  {
    id: "ecommerce",
    name: "🛍️ Online Store",
    data: {
      navbar: { brandName: "Luxe Atelier", logoText: "LUXE", link1: "New Arrivals", link2: "Collections", link3: "Best Sellers", ctaText: "Shop Collection" },
      hero: { badgeText: "✨ Spring 2026 Collection", headline: "Timeless Luxury Crafted for Everyday Elegance", subheadline: "Handcrafted apparel and minimalist accessories sustainably made from organic Italian textiles.", primaryCta: "Shop New Arrivals", secondaryCta: "Explore Lookbook", stat1Value: "100%", stat1Label: "Sustainable Silk", stat2Value: "48h", stat2Label: "Worldwide Shipping" },
      services: { sectionTitle: "The Luxe Craftsmanship Standard", sectionSubtitle: "Every garment is hand-finished by master artisans.", s1Title: "Artisanal Tailoring", s1Desc: "Custom-draped patterns and hand-stitched French seams.", s2Title: "Ethical Sourcing", s2Desc: "100% GOTS-certified organic cotton and virgin wool.", s3Title: "Complimentary Alterations", s3Desc: "Bespoke tailoring at any flagship boutique." },
      about: { badgeText: "Our Heritage", title: "Crafted in Florence, Cherished Worldwide", story: "Born in a family atelier in Florence, Luxe Atelier blends traditional craft with modern minimalism.", mission: "Creating sustainable heirloom-quality garments that transcend trends.", teamCount: "35 Master Artisans" },
      pricing: { title: "Exclusive Membership & Styling", subtitle: "Unlock seasonal priority access.", tier1Name: "Silver Club", tier1Price: "$45", tier1Period: "/ season", tier2Name: "Gold VIP", tier2Price: "$120", tier2Period: "/ season", tier3Name: "Atelier Bespoke", tier3Price: "$350", tier3Period: "/ season" },
      testimonials: { sectionTitle: "What Our Patrons Say", quote: "The fabric drape and attention to detail is extraordinary. Truly exquisite.", author: "Camille Moreau", role: "Fashion Director", company: "Vogue Paris", rating: "5" },
      contact: { title: "Concierge & Appointments", subtitle: "Book a private VIP fitting session.", email: "concierge@luxepatelier.com", phone: "+33 1 42 68 55 00", address: "24 Rue Saint-Honoré, Paris" },
      announcement: { badge: "Limited Offer", title: "Complimentary Monogramming This Week", message: "Receive hand-embroidered initials on all cashmere pieces.", ctaText: "Claim Monogram" },
      footer: { brandName: "Luxe Atelier Paris", tagline: "Sustainable luxury apparel and handcrafted accessories.", copyright: "© 2026 Luxe Atelier Paris. All rights reserved." }
    }
  },
  {
    id: "bakery",
    name: "☕ Café & Bakery",
    data: {
      navbar: { brandName: "Café de Paris", logoText: "PARIS", link1: "Fresh Pastries", link2: "Artisan Coffee", link3: "Catering", ctaText: "Order Online" },
      hero: { badgeText: "🥐 Fresh Daily at 5:00 AM", headline: "Authentic French Pastries & Woodfire Roasted Coffee", subheadline: "Flaky croissants, delicate macarons, and organic single-origin roasts baked fresh every morning.", primaryCta: "View Today's Menu", secondaryCta: "Order Pickup", stat1Value: "5:00 AM", stat1Label: "Fresh Daily Bake", stat2Value: "4.9 ★", stat2Label: "Over 2,400 Reviews" },
      services: { sectionTitle: "Our Daily Delights", sectionSubtitle: "Traditional French viennoiserie made with 100% Normandy butter.", s1Title: "Artisan Croissants", s1Desc: "72-hour slow-fermented dough layered with French AOP butter.", s2Title: "Specialty Espresso", s2Desc: "Ethically sourced beans roasted weekly on site.", s3Title: "Celebration Cakes", s3Desc: "Custom multi-tiered berry tarts and chocolate ganache." },
      about: { badgeText: "Our Story", title: "A Taste of Paris in Your Neighborhood", story: "Chef Pierre brought his third-generation recipes to our neighborhood using stone-ground flour.", mission: "Bringing warmth and the authentic aroma of Parisian mornings to every guest.", teamCount: "12 Dedicated Bakers" },
      pricing: { title: "Breakfast & Coffee Subscriptions", subtitle: "Freshly roasted beans delivered weekly.", tier1Name: "Morning Bean Box", tier1Price: "$22", tier1Period: "/ mo", tier2Name: "Pastry & Roast Club", tier2Price: "$48", tier2Period: "/ mo", tier3Name: "Executive Office Box", tier3Price: "$140", tier3Period: "/ mo" },
      testimonials: { sectionTitle: "From Our Morning Regulars", quote: "The almond croissants here rival any bakery in Paris. Divine!", author: "Sophie Dubois", role: "Food Critic", company: "Le Figaro", rating: "5" },
      contact: { title: "Visit Us or Plan an Event", subtitle: "We cater corporate breakfasts and wedding dessert bars.", email: "bonjour@cafedeparis.com", phone: "+1 (555) 019-3388", address: "142 Boulevard Saint-Germain / 820 Oak Ave" },
      announcement: { badge: "Chef's Special", title: "Warm Pistachio Croissants are Back!", message: "Limited daily batches available until 11:00 AM.", ctaText: "Reserve Pastry" },
      footer: { brandName: "Café de Paris", tagline: "Fresh artisanal baking and organic roasts since 2018.", copyright: "© 2026 Café de Paris. All rights reserved." }
    }
  }
];

export default function StorybookTool({
  onApplyComponent,
  activeBrandColors = {},
  templateId = "default",
  templatePages = {}
}) {
  // Active Sections State
  const [sections, setSections] = useState(INITIAL_SECTIONS);
  const [selectedSectionId, setSelectedSectionId] = useState("navbar");
  const [appliedNotice, setAppliedNotice] = useState("");

  // Canvas Viewport & Theme
  const [canvasBg, setCanvasBg] = useState("light");
  const [canvasViewport, setCanvasViewport] = useState("desktop");

  // Master Section Props (Initialized from real template data)
  const [sectionProps, setSectionProps] = useState(() => {
    const bName = templatePages?.navbar?.brand_name || activeBrandColors?.business_name || "Apex Design Studio";
    const lText = templatePages?.navbar?.logo_text || activeBrandColors?.logo_text || "APEX";
    const pColor = activeBrandColors?.primary_color || "#6366f1";

    return {
      navbar: {
        brandName: bName,
        logoText: lText,
        link1: templatePages?.navbar?.link1 || "Templates",
        link2: templatePages?.navbar?.link2 || "Features",
        link3: templatePages?.navbar?.link3 || "Pricing",
        ctaText: templatePages?.navbar?.cta_text || "Get Started",
        stickyGlass: true,
        themeColor: pColor
      },
      hero: {
        badgeText: activeBrandColors?.tagline || "🚀 Next-Gen Web Studio",
        headline: templatePages?.home?.hero_title || "Build Production-Ready Web Apps 10x Faster",
        subheadline: templatePages?.home?.hero_subtitle || "Deploy beautifully engineered templates pre-configured with dynamic components and Tailwind tokens.",
        primaryCta: templatePages?.home?.cta_primary || "Explore Templates",
        secondaryCta: templatePages?.home?.cta_secondary || "Watch Product Demo",
        stat1Value: templatePages?.home?.stat1_value || "99.9%",
        stat1Label: templatePages?.home?.stat1_label || "Uptime SLA",
        stat2Value: templatePages?.home?.stat2_value || "450k+",
        stat2Label: templatePages?.home?.stat2_label || "Active Users",
        themeColor: pColor
      },
      services: {
        sectionTitle: templatePages?.services?.title || "Comprehensive Digital Capabilities",
        sectionSubtitle: "Everything your business needs to launch and scale online.",
        s1Title: templatePages?.services?.s1_title || "Dynamic Code Generation",
        s1Desc: templatePages?.services?.s1_desc || "Instant React & HTML layout synthesis powered by advanced pipelines.",
        s2Title: templatePages?.services?.s2_title || "Smart Copywriting",
        s2Desc: templatePages?.services?.s2_desc || "Niche-tailored, high-converting copy and metatags.",
        s3Title: templatePages?.services?.s3_title || "SEO & Performance",
        s3Desc: templatePages?.services?.s3_desc || "Lighthouse 100 optimization with automated schema markup.",
        themeColor: pColor
      },
      about: {
        badgeText: `About ${bName}`,
        title: templatePages?.about?.title || "Crafting the Future of Web Design",
        story: templatePages?.about?.story || "Founded in 2024, our studio bridges the gap between dynamic code generation and human craft.",
        mission: templatePages?.about?.mission || "To empower every creator to build and launch world-class digital experiences effortlessly.",
        teamCount: templatePages?.about?.team_count || "24 Engineers & Designers",
        themeColor: pColor
      },
      pricing: {
        title: templatePages?.pricing?.title || "Flexible Transparent Pricing",
        subtitle: templatePages?.pricing?.subtitle || "Choose the perfect plan for your project size.",
        tier1Name: templatePages?.pricing?.tier1_name || "Starter License",
        tier1Price: templatePages?.pricing?.tier1_price || "$49",
        tier1Period: templatePages?.pricing?.tier1_period || "/ mo",
        tier2Name: templatePages?.pricing?.tier2_name || "Commercial License",
        tier2Price: templatePages?.pricing?.tier2_price || "$129",
        tier2Period: templatePages?.pricing?.tier2_period || "/ mo",
        tier3Name: templatePages?.pricing?.tier3_name || "Extended License",
        tier3Price: templatePages?.pricing?.tier3_price || "$299",
        tier3Period: templatePages?.pricing?.tier3_period || "/ mo",
        themeColor: pColor
      },
      testimonials: {
        sectionTitle: "Trusted by Creators Worldwide",
        quote: "AI Site Studio saved our agency over 60 engineering hours on our latest client redesign. The code quality is immaculate.",
        author: "Sarah Jenkins",
        role: "VP of Product",
        company: "CloudScale Inc.",
        rating: "5",
        themeColor: pColor
      },
      contact: {
        title: "Get in Touch with Our Team",
        subtitle: "Have questions about our templates or need custom design assistance? Reach out anytime.",
        email: templatePages?.contact?.email || "hello@apex-studio.com",
        phone: templatePages?.contact?.phone || "+1 (800) 555-0199",
        address: templatePages?.contact?.address || "500 Innovation Way, Suite 400, San Francisco, CA",
        buttonText: "Send Message",
        themeColor: pColor
      },
      announcement: {
        badge: "Special Offer",
        title: "Spring 2026 Collection Live",
        message: "Explore our newest production-ready templates with 20% discount using promo code SPRING26.",
        ctaText: "Explore Now",
        themeColor: pColor
      },
      footer: {
        brandName: templatePages?.footer?.brand_name || bName,
        tagline: templatePages?.footer?.tagline || activeBrandColors?.tagline || "Empowering creators with production-ready AI templates.",
        copyright: templatePages?.footer?.copyright || `© ${new Date().getFullYear()} ${bName}. All rights reserved.`,
        link1: "Privacy Policy",
        link2: "Terms of Service",
        link3: "Support Center",
        themeColor: pColor
      }
    };
  });

  const currentSection = sections.find((s) => s.id === selectedSectionId) || sections[0];
  const currentProps = sectionProps[currentSection.id] || {};

  // Handle Field Changes (Natural backspace & text typing)
  const handleFieldChange = (key, value) => {
    setSectionProps((prev) => ({
      ...prev,
      [currentSection.id]: {
        ...prev[currentSection.id],
        [key]: value
      }
    }));
  };

  // Erase Row Content
  const handleEraseSection = () => {
    setSectionProps((prev) => {
      const current = prev[currentSection.id] || {};
      const cleared = {};
      Object.keys(current).forEach((k) => {
        if (typeof current[k] === "boolean") cleared[k] = false;
        else if (k === "themeColor") cleared[k] = current[k];
        else cleared[k] = "";
      });
      return { ...prev, [currentSection.id]: cleared };
    });
    setAppliedNotice(`🧹 Cleared text fields for ${currentSection.name}`);
    setTimeout(() => setAppliedNotice(""), 3000);
  };

  // 1-Click Business Preset
  const handleApplyPreset = (preset) => {
    const data = preset.data[currentSection.id];
    if (data) {
      setSectionProps((prev) => ({
        ...prev,
        [currentSection.id]: {
          ...prev[currentSection.id],
          ...data
        }
      }));
      setAppliedNotice(`✓ Loaded "${preset.name}" copy for ${currentSection.name}!`);
      setTimeout(() => setAppliedNotice(""), 3000);
    }
  };

  // Apply to Live Preview
  const handleApplyToLivePreview = () => {
    if (onApplyComponent) {
      onApplyComponent(currentSection.targetSection || currentSection.id, currentSection.id, currentProps);
      setAppliedNotice(`✓ Applied "${currentSection.name}" to Live Preview!`);
      setTimeout(() => setAppliedNotice(""), 4000);
    }
  };

  return (
    <div className="storybook-tool-container flex flex-col h-full bg-card/60">
      {/* Top Banner with Full Page Link */}
      <div className="p-3 border-b border-border/50 bg-muted/20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-pink-500 flex items-center justify-center text-white shadow-sm">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <div>
            <h3 className="font-extrabold text-xs text-foreground flex items-center gap-1.5">
              <span>Website Section Studio</span>
              <span className="text-[10px] text-pink-500 font-bold px-1.5 py-0.2 rounded-full bg-pink-500/10">Visual</span>
            </h3>
            <span className="text-[10px] text-muted-foreground block">Select a section to edit live</span>
          </div>
        </div>

        <Link
          to={`/storybook?template=${templateId}&story=${selectedSectionId}`}
          className="px-2.5 py-1 rounded-lg bg-gradient-to-r from-pink-500 to-indigo-600 hover:opacity-90 text-white text-[11px] font-bold flex items-center gap-1 shadow-sm transition-all"
          title="Open expansive full-page Section Studio"
        >
          <span>Open Full Page Studio</span>
          <ExternalLink className="w-3 h-3" />
        </Link>
      </div>

      {appliedNotice && (
        <div className="mx-3 mt-2.5 p-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 text-xs font-semibold flex items-center gap-2 animate-fade-in">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span>{appliedNotice}</span>
        </div>
      )}

      {/* Section Selection Bar (Horizontal scrollable pills) */}
      <div className="p-2.5 border-b border-border/40 bg-card overflow-x-auto flex items-center gap-1.5 no-scrollbar">
        {sections.map((sec) => {
          const SecIcon = sec.icon;
          const isSelected = selectedSectionId === sec.id;
          return (
            <button
              key={sec.id}
              type="button"
              onClick={() => setSelectedSectionId(sec.id)}
              className={cn(
                "px-2.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 whitespace-nowrap transition-all flex-shrink-0 cursor-pointer",
                isSelected
                  ? "bg-pink-500 text-white shadow-md shadow-pink-500/20"
                  : "bg-muted/40 hover:bg-muted text-muted-foreground hover:text-foreground"
              )}
            >
              <SecIcon className="w-3 h-3" />
              <span>{sec.name}</span>
            </button>
          );
        })}
      </div>

      {/* Center Canvas Preview: Designed Output View */}
      <div className="p-3 border-b border-border/40">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-bold text-foreground flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>{currentSection.name} Output View</span>
          </span>

          <div className="flex items-center gap-1.5">
            <div className="flex items-center gap-0.5 p-0.5 rounded-md bg-muted border border-border/50 text-[10px]">
              <button
                type="button"
                onClick={() => setCanvasViewport("desktop")}
                className={cn("p-1 rounded", canvasViewport === "desktop" && "bg-card text-pink-500 font-bold shadow-sm")}
                title="Desktop"
              >
                <Monitor className="w-3 h-3" />
              </button>
              <button
                type="button"
                onClick={() => setCanvasViewport("mobile")}
                className={cn("p-1 rounded", canvasViewport === "mobile" && "bg-card text-pink-500 font-bold shadow-sm")}
                title="Mobile"
              >
                <Smartphone className="w-3 h-3" />
              </button>
            </div>
            <button
              type="button"
              onClick={() => setCanvasBg(canvasBg === "light" ? "dark" : "light")}
              className="p-1 rounded-md bg-muted border border-border/50 text-muted-foreground hover:text-foreground"
              title="Toggle canvas theme"
            >
              {canvasBg === "light" ? <Moon className="w-3 h-3" /> : <Sun className="w-3 h-3" />}
            </button>
          </div>
        </div>

        {/* Scaled Output View Canvas */}
        <div
          className={cn(
            "rounded-xl border border-border/60 overflow-hidden shadow-inner flex items-center justify-center p-3 transition-all",
            canvasBg === "dark" ? "bg-slate-950 text-white" : "bg-slate-50 text-slate-900"
          )}
          style={{ minHeight: "150px" }}
        >
          <div
            className="w-full transition-all duration-200"
            style={{ maxWidth: canvasViewport === "mobile" ? "320px" : "100%" }}
          >
            {renderToolOutputView(currentSection.id, currentProps)}
          </div>
        </div>
      </div>

      {/* Editing Form: Natural Backspace & Text Typing */}
      <div className="p-3 flex-1 overflow-y-auto space-y-3">
        {/* 1-Click Business Presets */}
        <div>
          <span className="text-[10px] font-bold uppercase text-muted-foreground block mb-1">
            ⚡ Quick Business Presets:
          </span>
          <div className="flex flex-wrap gap-1">
            {BUSINESS_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => handleApplyPreset(preset)}
                className="px-2 py-0.5 rounded bg-muted/60 hover:bg-pink-500/15 hover:text-pink-500 text-[10px] font-semibold text-foreground transition-all"
              >
                {preset.name}
              </button>
            ))}
          </div>
        </div>

        {/* Input Fields */}
        <div className="space-y-2.5 pt-1">
          {renderToolFormFields(currentSection.id, currentProps, handleFieldChange)}
        </div>

        {/* Action Buttons */}
        <div className="pt-3 border-t border-border/40 space-y-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleEraseSection}
              className="flex-1 py-1.5 px-2 rounded-lg bg-muted/50 hover:bg-amber-500/15 text-amber-500 border border-border text-[11px] font-bold flex items-center justify-center gap-1 transition-colors"
            >
              <Eraser className="w-3 h-3" />
              <span>Clear Fields</span>
            </button>
          </div>

          <button
            type="button"
            onClick={handleApplyToLivePreview}
            className="w-full py-2 px-3 rounded-xl bg-gradient-to-r from-pink-500 to-indigo-600 hover:opacity-95 text-white font-bold text-xs shadow-md shadow-pink-500/20 flex items-center justify-center gap-1.5 transition-all cursor-pointer"
          >
            <Zap className="w-3.5 h-3.5 fill-amber-300 text-amber-300" />
            <span>Apply to Live Preview</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// COMPACT DESIGNED OUTPUT VIEWS FOR EMBEDDED TOOL
// ─────────────────────────────────────────────────────────────────────────────
function renderToolOutputView(sectionId, props) {
  const themeColor = props.themeColor || "#6366f1";

  switch (sectionId) {
    case "navbar":
      return (
        <div className="p-2 bg-card rounded-xl border border-border/80 shadow-sm flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded-md flex items-center justify-center text-white font-bold text-[10px]"
              style={{ backgroundColor: themeColor }}
            >
              {(props.logoText || "AP").slice(0, 2)}
            </div>
            <span className="font-extrabold truncate max-w-[120px]">{props.brandName || "Brand Name"}</span>
          </div>
          <div className="hidden sm:flex items-center gap-3 text-[11px] text-muted-foreground font-semibold">
            <span>{props.link1 || "Home"}</span>
            <span>{props.link2 || "Features"}</span>
            <span>{props.link3 || "Pricing"}</span>
          </div>
          <button
            type="button"
            className="px-2.5 py-1 rounded-md text-white text-[10px] font-bold"
            style={{ backgroundColor: themeColor }}
          >
            {props.ctaText || "Get Started"}
          </button>
        </div>
      );

    case "hero":
      return (
        <div className="p-3 text-center space-y-2">
          {props.badgeText && (
            <span
              className="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold border"
              style={{ color: themeColor, backgroundColor: `${themeColor}15`, borderColor: `${themeColor}30` }}
            >
              {props.badgeText}
            </span>
          )}
          <h2 className="text-sm sm:text-base font-black leading-tight tracking-tight">
            {props.headline || "Headline Text"}
          </h2>
          <p className="text-[11px] text-muted-foreground line-clamp-2 max-w-sm mx-auto">
            {props.subheadline || "Subtitle description."}
          </p>
          <div className="flex items-center justify-center gap-2 pt-1">
            <button
              type="button"
              className="px-3 py-1 rounded-lg text-white text-[11px] font-bold shadow-sm"
              style={{ backgroundColor: themeColor }}
            >
              {props.primaryCta || "Get Started"}
            </button>
            {props.secondaryCta && (
              <button
                type="button"
                className="px-2.5 py-1 rounded-lg border border-border text-[11px] font-bold bg-card"
              >
                {props.secondaryCta}
              </button>
            )}
          </div>
        </div>
      );

    case "services":
      return (
        <div className="p-2 text-left space-y-2">
          <div className="text-center mb-1">
            <h3 className="text-xs font-bold">{props.sectionTitle || "Our Services"}</h3>
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-[10px]">
            <div className="p-2 rounded-lg bg-card border border-border shadow-xs">
              <span className="font-bold block truncate" style={{ color: themeColor }}>{props.s1Title || "Service 1"}</span>
              <p className="text-muted-foreground line-clamp-2 text-[9px] mt-0.5">{props.s1Desc}</p>
            </div>
            <div className="p-2 rounded-lg bg-card border border-border shadow-xs">
              <span className="font-bold block truncate" style={{ color: themeColor }}>{props.s2Title || "Service 2"}</span>
              <p className="text-muted-foreground line-clamp-2 text-[9px] mt-0.5">{props.s2Desc}</p>
            </div>
            <div className="p-2 rounded-lg bg-card border border-border shadow-xs">
              <span className="font-bold block truncate" style={{ color: themeColor }}>{props.s3Title || "Service 3"}</span>
              <p className="text-muted-foreground line-clamp-2 text-[9px] mt-0.5">{props.s3Desc}</p>
            </div>
          </div>
        </div>
      );

    case "about":
      return (
        <div className="p-2.5 text-left space-y-1.5 text-xs">
          <span className="text-[10px] font-bold uppercase" style={{ color: themeColor }}>{props.badgeText}</span>
          <h3 className="font-extrabold text-xs">{props.title}</h3>
          <p className="text-[11px] text-muted-foreground line-clamp-2">{props.story}</p>
          <div className="p-1.5 rounded-md bg-card border border-border flex items-center justify-between text-[10px] font-bold">
            <span className="text-muted-foreground">Team Scale</span>
            <span>{props.teamCount}</span>
          </div>
        </div>
      );

    case "pricing":
      return (
        <div className="p-2 text-left space-y-2">
          <div className="text-center">
            <h3 className="text-xs font-bold">{props.title || "Pricing Plans"}</h3>
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-center">
            <div className="p-2 rounded-lg bg-card border border-border text-[10px]">
              <span className="font-bold block">{props.tier1Name || "Starter"}</span>
              <span className="font-black text-xs block mt-1">{props.tier1Price || "$49"}</span>
            </div>
            <div
              className="p-2 rounded-lg bg-card border-2 text-[10px] relative shadow-sm"
              style={{ borderColor: themeColor }}
            >
              <span className="font-bold block">{props.tier2Name || "Pro"}</span>
              <span className="font-black text-xs block mt-1" style={{ color: themeColor }}>{props.tier2Price || "$129"}</span>
            </div>
            <div className="p-2 rounded-lg bg-card border border-border text-[10px]">
              <span className="font-bold block">{props.tier3Name || "Enterprise"}</span>
              <span className="font-black text-xs block mt-1">{props.tier3Price || "$299"}</span>
            </div>
          </div>
        </div>
      );

    case "testimonials":
      return (
        <div className="p-2.5 text-left bg-card rounded-xl border border-border shadow-xs space-y-1.5">
          <div className="flex items-center gap-1 text-amber-400">
            {[...Array(5)].map((_, i) => (
              <Star key={i} className="w-3 h-3 fill-amber-400 text-amber-400" />
            ))}
          </div>
          <p className="text-[11px] italic font-serif leading-tight">"{props.quote}"</p>
          <div className="pt-1 text-[10px] font-bold text-muted-foreground">
            <span className="text-foreground">{props.author}</span> · {props.role}
          </div>
        </div>
      );

    case "contact":
      return (
        <div className="p-2 text-left space-y-1.5 text-xs">
          <h3 className="font-bold text-xs">{props.title || "Contact Us"}</h3>
          <div className="space-y-1 text-[11px] text-muted-foreground">
            <div>✉️ {props.email}</div>
            <div>📞 {props.phone}</div>
            <div>📍 {props.address}</div>
          </div>
          <button
            type="button"
            className="w-full mt-1 py-1 rounded-md text-white text-[10px] font-bold"
            style={{ backgroundColor: themeColor }}
          >
            {props.buttonText || "Send Message"}
          </button>
        </div>
      );

    case "announcement":
      return (
        <div
          className="p-2.5 rounded-xl border flex items-center justify-between text-xs"
          style={{ backgroundColor: `${themeColor}12`, borderColor: `${themeColor}35` }}
        >
          <div>
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded text-white" style={{ backgroundColor: themeColor }}>
              {props.badge || "Notice"}
            </span>
            <span className="font-bold ml-1.5 text-[11px]">{props.title}</span>
          </div>
          <button
            type="button"
            className="px-2 py-0.5 rounded text-[10px] font-bold text-white"
            style={{ backgroundColor: themeColor }}
          >
            {props.ctaText || "View"}
          </button>
        </div>
      );

    case "footer":
      return (
        <div className="p-2.5 bg-card rounded-xl border border-border shadow-xs text-left space-y-1 text-xs">
          <div className="flex items-center justify-between font-bold">
            <span>{props.brandName}</span>
            <span className="text-[9px] text-muted-foreground">{props.copyright}</span>
          </div>
          <p className="text-[10px] text-muted-foreground">{props.tagline}</p>
        </div>
      );

    default:
      return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// COMPACT FORM FIELDS FOR EMBEDDED TOOL
// ─────────────────────────────────────────────────────────────────────────────
function renderToolFormFields(sectionId, props, onChange) {
  switch (sectionId) {
    case "navbar":
      return (
        <>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Brand / Business Name</label>
            <input
              type="text"
              value={props.brandName || ""}
              onChange={(e) => onChange("brandName", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Logo Monogram</label>
            <input
              type="text"
              value={props.logoText || ""}
              onChange={(e) => onChange("logoText", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background font-mono uppercase outline-none"
            />
          </div>
          <div className="grid grid-cols-3 gap-1.5">
            <input
              type="text"
              value={props.link1 || ""}
              onChange={(e) => onChange("link1", e.target.value)}
              placeholder="Link 1"
              className="px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none"
            />
            <input
              type="text"
              value={props.link2 || ""}
              onChange={(e) => onChange("link2", e.target.value)}
              placeholder="Link 2"
              className="px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none"
            />
            <input
              type="text"
              value={props.link3 || ""}
              onChange={(e) => onChange("link3", e.target.value)}
              placeholder="Link 3"
              className="px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Button CTA Text</label>
            <input
              type="text"
              value={props.ctaText || ""}
              onChange={(e) => onChange("ctaText", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
        </>
      );

    case "hero":
      return (
        <>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Top Badge Text</label>
            <input
              type="text"
              value={props.badgeText || ""}
              onChange={(e) => onChange("badgeText", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Main Headline</label>
            <input
              type="text"
              value={props.headline || ""}
              onChange={(e) => onChange("headline", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background font-bold outline-none"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Subtitle Description</label>
            <textarea
              rows={2}
              value={props.subheadline || ""}
              onChange={(e) => onChange("subheadline", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none resize-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <input
              type="text"
              value={props.primaryCta || ""}
              onChange={(e) => onChange("primaryCta", e.target.value)}
              placeholder="Primary Button"
              className="px-2 py-1.5 text-xs rounded-lg border border-border bg-background outline-none"
            />
            <input
              type="text"
              value={props.secondaryCta || ""}
              onChange={(e) => onChange("secondaryCta", e.target.value)}
              placeholder="Secondary Button"
              className="px-2 py-1.5 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
        </>
      );

    case "services":
      return (
        <>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Section Title</label>
            <input
              type="text"
              value={props.sectionTitle || ""}
              onChange={(e) => onChange("sectionTitle", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none font-bold"
            />
          </div>
          <div className="space-y-1.5">
            <input
              type="text"
              value={props.s1Title || ""}
              onChange={(e) => onChange("s1Title", e.target.value)}
              placeholder="Card 1 Title"
              className="w-full px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none"
            />
            <input
              type="text"
              value={props.s2Title || ""}
              onChange={(e) => onChange("s2Title", e.target.value)}
              placeholder="Card 2 Title"
              className="w-full px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none"
            />
            <input
              type="text"
              value={props.s3Title || ""}
              onChange={(e) => onChange("s3Title", e.target.value)}
              placeholder="Card 3 Title"
              className="w-full px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
        </>
      );

    case "about":
      return (
        <>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">About Heading</label>
            <input
              type="text"
              value={props.title || ""}
              onChange={(e) => onChange("title", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none font-bold"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Story / Mission</label>
            <textarea
              rows={3}
              value={props.story || ""}
              onChange={(e) => onChange("story", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none resize-none"
            />
          </div>
        </>
      );

    case "pricing":
      return (
        <>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Section Title</label>
            <input
              type="text"
              value={props.title || ""}
              onChange={(e) => onChange("title", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none font-bold"
            />
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <input
              type="text"
              value={props.tier1Name || ""}
              onChange={(e) => onChange("tier1Name", e.target.value)}
              placeholder="Tier 1 Name"
              className="px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none"
            />
            <input
              type="text"
              value={props.tier1Price || ""}
              onChange={(e) => onChange("tier1Price", e.target.value)}
              placeholder="Tier 1 Price"
              className="px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none font-mono"
            />
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <input
              type="text"
              value={props.tier2Name || ""}
              onChange={(e) => onChange("tier2Name", e.target.value)}
              placeholder="Tier 2 Name"
              className="px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none"
            />
            <input
              type="text"
              value={props.tier2Price || ""}
              onChange={(e) => onChange("tier2Price", e.target.value)}
              placeholder="Tier 2 Price"
              className="px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none font-mono"
            />
          </div>
        </>
      );

    case "testimonials":
      return (
        <>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Review Quote</label>
            <textarea
              rows={3}
              value={props.quote || ""}
              onChange={(e) => onChange("quote", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none resize-none font-serif"
            />
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <input
              type="text"
              value={props.author || ""}
              onChange={(e) => onChange("author", e.target.value)}
              placeholder="Author Name"
              className="px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none"
            />
            <input
              type="text"
              value={props.role || ""}
              onChange={(e) => onChange("role", e.target.value)}
              placeholder="Role / Title"
              className="px-2 py-1 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
        </>
      );

    case "contact":
      return (
        <>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Contact Email</label>
            <input
              type="text"
              value={props.email || ""}
              onChange={(e) => onChange("email", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Phone Number</label>
            <input
              type="text"
              value={props.phone || ""}
              onChange={(e) => onChange("phone", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Address</label>
            <input
              type="text"
              value={props.address || ""}
              onChange={(e) => onChange("address", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
        </>
      );

    case "announcement":
      return (
        <>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Banner Title</label>
            <input
              type="text"
              value={props.title || ""}
              onChange={(e) => onChange("title", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none font-bold"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Message Text</label>
            <textarea
              rows={2}
              value={props.message || ""}
              onChange={(e) => onChange("message", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none resize-none"
            />
          </div>
        </>
      );

    case "footer":
      return (
        <>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Brand Name</label>
            <input
              type="text"
              value={props.brandName || ""}
              onChange={(e) => onChange("brandName", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none font-bold"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Tagline</label>
            <input
              type="text"
              value={props.tagline || ""}
              onChange={(e) => onChange("tagline", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-foreground block mb-0.5">Copyright Notice</label>
            <input
              type="text"
              value={props.copyright || ""}
              onChange={(e) => onChange("copyright", e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-background outline-none"
            />
          </div>
        </>
      );

    default:
      return null;
  }
}
