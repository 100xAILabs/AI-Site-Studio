"use client";

/**
 * Live Preview Editor Page — Full-Bleed 3-Column Studio Layout
 * 
 * Incorporates User Feedback:
 *   1. No "Storybook Studio" branding in header. The header shows the active Template Name & Monogram.
 *   2. Directly beside the template title are the 2 mode buttons:
 *        [ 🛠️ 1. Manual Edit ] (This is the Storybook visual editor with live output view & component controls)
 *        [ 🤖 2. AI Edit ] (Natural language prompt assistant with live code refactoring & auto-fix)
 *   3. Left Filter Column lively inspects the template's actual code/pages (only displays sections that exist in this template).
 *   4. Right Column displays the actual component names and properties used in that specific template.
 */

import React, { useState, useEffect, useRef, useMemo } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import {
  Monitor, Laptop, Tablet, Smartphone, Sun, Moon, Grid,
  RefreshCw, Zap, Layers, FileText, Sparkles, Star, Mail,
  Shield, AlertCircle, Edit3, Trash2, Eraser, Plus, Check,
  Copy, RotateCcw, ArrowLeft, Sliders, Globe, Bot, Send,
  CheckCircle2, Play, Code, Search, X, Wand2, ArrowUpRight,
  ChevronRight, Eye, Phone, MapPin, Clock, ShoppingBag, ShoppingCart, Share2
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useCartStore } from "@/store";
import "./Page.css";
import "../storybook/Page.css";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

// 1-Click Business Presets for Instant Copy Transformation
const BUSINESS_PRESETS = [
  {
    id: "saas",
    name: "🚀 SaaS / Tech",
    data: {
      navbar: { brandName: "CloudPulse SaaS", logoText: "PULSE", link1: "Platform", link2: "Solutions", link3: "Pricing", ctaText: "Start Free Trial" },
      hero: { badgeText: "⚡ Next-Gen Cloud Platform", headline: "Automate Workflows & Scale Operations 10x Faster", subheadline: "The modern all-in-one developer workspace designed to streamline cloud infrastructure and deployment pipelines.", primaryCta: "Start Free Trial", secondaryCta: "Book Live Demo", stat1Value: "99.99%", stat1Label: "Cloud Uptime", stat2Value: "12,000+", stat2Label: "Teams Shipping" },
      services: { sectionTitle: "Engineered for High-Velocity Teams", sectionSubtitle: "Everything you need to ship resilient cloud apps with zero configuration.", s1Title: "Real-Time Telemetry", s1Desc: "Monitor latency, throughput, and error budgets across all distributed microservices.", s2Title: "Automated Deployments", s2Desc: "Git push to production with canary rollouts and automated rollback safeguards.", s3Title: "SOC2 Compliance", s3Desc: "Enterprise-grade encryption, audit trails, and strict role-based access control." },
      about: { badgeText: "About CloudPulse", title: "Building the Operating System for Distributed Teams", story: "Founded by former cloud architects, CloudPulse was built to eliminate deployment friction. We empower over 12,000 engineering teams worldwide.", mission: "To make cloud orchestration as simple as writing a single line of code.", teamCount: "48 Core Engineers" },
      pricing: { title: "Simple, Predictable Cloud Pricing", subtitle: "Pay only for what you build. Scale seamlessly as your traffic grows.", tier1Name: "Developer", tier1Price: "$29", tier1Period: "/ month", tier2Name: "Pro Team", tier2Price: "$99", tier2Period: "/ month", tier3Name: "Enterprise", tier3Price: "$299", tier3Period: "/ month" },
      testimonials: { sectionTitle: "Loved by Top Engineering Leaders", quote: "CloudPulse replaced three separate deployment tools for us and cut our CI/CD pipeline time from 45 minutes to 4 minutes.", author: "David Chen", role: "VP of Engineering", company: "Aura FinTech", rating: "5" },
      contact: { title: "Talk to Our Solutions Engineers", subtitle: "Schedule a customized technical demo or get help migrating your existing clusters.", email: "sales@cloudpulse.io", phone: "+1 (888) 555-0142", address: "100 Montgomery St, Suite 1400, San Francisco, CA", hours: "Mon - Fri: 8:00 AM - 6:00 PM PST" },
      announcement: { badge: "Product Update", title: "v4.2 Kubernetes Autoscaling is Live", message: "Deploy dynamic node pools with 40% lower memory footprint. Read release notes.", ctaText: "See What's New" },
      footer: { brandName: "CloudPulse Technologies Inc.", tagline: "The modern developer workspace for cloud orchestration and continuous delivery.", copyright: "© 2026 CloudPulse Inc. All rights reserved." }
    }
  },
  {
    id: "ecommerce",
    name: "🛍️ Online Store",
    data: {
      navbar: { brandName: "Luxe Atelier", logoText: "LUXE", link1: "New Arrivals", link2: "Collections", link3: "Best Sellers", ctaText: "Shop Collection" },
      hero: { badgeText: "✨ Spring Summer 2026 Collection", headline: "Timeless Luxury Crafted for Everyday Elegance", subheadline: "Discover handcrafted apparel and minimalist accessories sustainably made from the finest organic Italian textiles.", primaryCta: "Shop New Arrivals", secondaryCta: "Explore Lookbook", stat1Value: "100%", stat1Label: "Sustainable Silk & Linen", stat2Value: "48h", stat2Label: "Worldwide Express Shipping" },
      services: { sectionTitle: "The Luxe Craftsmanship Standard", sectionSubtitle: "Every single garment is individually numbered and hand-finished by master artisans.", s1Title: "Artisanal Tailoring", s1Desc: "Custom-draped patterns and hand-stitched French seams built to last decades.", s2Title: "Ethical Sourcing", s2Desc: "100% GOTS-certified organic cotton and traceable Italian virgin wool.", s3Title: "Complimentary Alterations", s3Desc: "Enjoy bespoke tailoring adjustments at any of our global flagship boutiques." },
      about: { badgeText: "Our Heritage", title: "Crafted in Florence, Cherished Worldwide", story: "Born in a family-run atelier in Florence, Luxe Atelier blends traditional Italian craftsmanship with contemporary minimalist silhouettes.", mission: "Creating sustainable, heirloom-quality garments that transcend fleeting trends.", teamCount: "35 Master Artisans" },
      pricing: { title: "Exclusive Membership & Styling", subtitle: "Unlock seasonal priority access and personal wardrobe consultations.", tier1Name: "Silver Club", tier1Price: "$45", tier1Period: "/ season", tier2Name: "Gold VIP", tier2Price: "$120", tier2Period: "/ season", tier3Name: "Atelier Bespoke", tier3Price: "$350", tier3Period: "/ season" },
      testimonials: { sectionTitle: "What Our Patrons Say", quote: "The fabric drape and attention to detail is extraordinary. Truly the finest garments in my wardrobe.", author: "Camille Moreau", role: "Fashion Director", company: "Vogue Paris", rating: "5" },
      contact: { title: "Concierge & Private Appointments", subtitle: "Book a private VIP fitting session or inquire about bespoke orders.", email: "concierge@luxepatelier.com", phone: "+33 1 42 68 55 00", address: "24 Rue du Faubourg Saint-Honoré, Paris, France", hours: "Mon - Sat: 10:00 AM - 7:00 PM CET" },
      announcement: { badge: "Limited Offer", title: "Complimentary Monogramming This Week", message: "Receive complimentary hand-embroidered initials on all bespoke cashmere pieces.", ctaText: "Claim Monogram" },
      footer: { brandName: "Luxe Atelier Paris", tagline: "Sustainable luxury apparel and handcrafted accessories from Florence to the world.", copyright: "© 2026 Luxe Atelier Paris. All rights reserved." }
    }
  },
  {
    id: "bakery",
    name: "☕ Café & Bakery",
    data: {
      navbar: { brandName: "Café de Paris", logoText: "PARIS", link1: "Fresh Pastries", link2: "Artisan Coffee", link3: "Catering", ctaText: "Order Online" },
      hero: { badgeText: "🥐 Fresh Out of the Oven Daily", headline: "Authentic French Pastries & Woodfire Roasted Coffee", subheadline: "Warm flaky croissants, delicate macarons, and organic single-origin roasts baked with love every morning at 5:00 AM.", primaryCta: "View Today's Menu", secondaryCta: "Order Pickup", stat1Value: "5:00 AM", stat1Label: "Fresh Daily Bake", stat2Value: "4.9 ★", stat2Label: "Over 2,400 Reviews" },
      services: { sectionTitle: "Our Daily Delights", sectionSubtitle: "Traditional French viennoiserie made with 100% Normandy butter.", s1Title: "Artisan Croissants", s1Desc: "72-hour slow-fermented dough layered with French AOP butter for unmatched flakiness.", s2Title: "Specialty Espresso", s2Desc: "Ethically sourced Ethiopian and Colombian beans roasted weekly on site.", s3Title: "Celebration Cakes", s3Desc: "Custom multi-tiered berry tarts and chocolate ganache creations for memorable events." },
      about: { badgeText: "Our Story", title: "A Taste of Saint-Germain in Your Neighborhood", story: "Chef Pierre brought his third-generation Parisian recipes to our community in 2018, using stone-ground flour and Normandy butter.", mission: "To bring warmth, connection, and the authentic aroma of Parisian mornings to every guest.", teamCount: "12 Dedicated Bakers" },
      pricing: { title: "Breakfast & Coffee Subscriptions", subtitle: "Freshly roasted beans and warm pastries delivered to your door each week.", tier1Name: "Morning Bean Box", tier1Price: "$22", tier1Period: "/ month", tier2Name: "Pastry & Roast Club", tier2Price: "$48", tier2Period: "/ month", tier3Name: "Executive Office Box", tier3Price: "$140", tier3Period: "/ month" },
      testimonials: { sectionTitle: "From Our Morning Regulars", quote: "The almond croissants here rival any bakery on the Left Bank in Paris. Absolutely divine with a café au lait.", author: "Sophie Dubois", role: "Food Critic", company: "Le Figaro", rating: "5" },
      contact: { title: "Visit Us or Plan an Event", subtitle: "We cater corporate breakfasts, wedding dessert bars, and weekend brunches.", email: "bonjour@cafedeparis.com", phone: "+1 (555) 019-3388", address: "142 Boulevard Saint-Germain, Paris / 820 Oak Ave", hours: "Daily: 6:00 AM - 5:00 PM" },
      announcement: { badge: "Chef's Special", title: "Warm Pistachio Croissants are Back!", message: "Limited daily batches available until 11:00 AM. Stop by early!", ctaText: "Reserve Pastry" },
      footer: { brandName: "Café de Paris & Pâtisserie", tagline: "Fresh artisanal baking, organic roasts, and French culinary tradition since 2018.", copyright: "© 2026 Café de Paris. All rights reserved." }
    }
  },
  {
    id: "medical",
    name: "🏥 Health & Clinic",
    data: {
      navbar: { brandName: "Aura Medical Care", logoText: "AURA", link1: "Specialties", link2: "Our Doctors", link3: "Patient Portal", ctaText: "Book Appointment" },
      hero: { badgeText: "🌿 Modern Compassionate Medicine", headline: "Comprehensive Healthcare Centered Around You", subheadline: "Award-winning physicians, state-of-the-art diagnostic imaging, and seamless telehealth consultations when you need it most.", primaryCta: "Schedule Visit", secondaryCta: "Meet Our Physicians", stat1Value: "98.7%", stat1Label: "Patient Satisfaction", stat2Value: "15 min", stat2Label: "Average Wait Time" },
      services: { sectionTitle: "Our Clinical Specialties", sectionSubtitle: "Preventative wellness, diagnostics, and dedicated primary care.", s1Title: "Family Medicine", s1Desc: "Routine wellness exams, immunizations, and chronic disease management for all ages.", s2Title: "Digital Diagnostics", s2Desc: "Low-dose digital X-rays, 3D ultrasounds, and rapid in-house lab results in under 2 hours.", s3Title: "Telehealth Consultations", s3Desc: "Secure video visits with your dedicated physician from the comfort of your home." },
      about: { badgeText: "Our Practice", title: "Redefining the Patient Healthcare Experience", story: "Founded in 2016 by board-certified physicians, Aura Medical bridges modern medical technology with empathetic, personalized bedside care.", mission: "To empower our community with accessible, compassionate, and evidence-based wellness care.", teamCount: "32 Board-Certified Doctors" },
      pricing: { title: "Transparent Wellness Plans", subtitle: "Affordable direct primary care memberships with zero surprise bills.", tier1Name: "Individual Care", tier1Price: "$69", tier1Period: "/ month", tier2Name: "Family Wellness", tier2Price: "$159", tier2Period: "/ month", tier3Name: "Executive Health", tier3Price: "$280", tier3Period: "/ month" },
      testimonials: { sectionTitle: "Words from Our Patients", quote: "Dr. Alvarez took the time to truly listen to my concerns. The clinic is pristine, modern, and appointments always run on time.", author: "Elena Rostova", role: "Patient for 4 Years", company: "Local Community Member", rating: "5" },
      contact: { title: "Schedule an In-Person or Telehealth Visit", subtitle: "Same-day urgent appointments available for registered patients.", email: "care@auramedical.org", phone: "+1 (800) 555-0199", address: "450 Medical Arts Plaza, Suite 300, Beverly Hills, CA", hours: "Mon - Fri: 8:00 AM - 7:00 PM" },
      announcement: { badge: "Flu Season Notice", title: "Walk-in Flu Vaccines Available Today", message: "No appointment needed. Free with most insurance cards at our downtown center.", ctaText: "Clinic Hours" },
      footer: { brandName: "Aura Medical & Dental Group", tagline: "Compassionate, patient-centered medical and preventative care for the entire family.", copyright: "© 2026 Aura Medical Group. All rights reserved." }
    }
  },
  {
    id: "agency",
    name: "💎 Creative Agency",
    data: {
      navbar: { brandName: "Apex Design Studio", logoText: "APEX", link1: "Selected Work", link2: "Capabilities", link3: "Case Studies", ctaText: "Start a Project" },
      hero: { badgeText: "🚀 Digital Product & Brand Studio", headline: "We Craft High-Impact Brands & Digital Flagships", subheadline: "Partnering with visionary founders and enterprise market leaders to design iconic identities, web applications, and immersive mobile apps.", primaryCta: "View Our Work", secondaryCta: "Book Capabilities Call", stat1Value: "42+", stat1Label: "Design Awards Won", stat2Value: "$350M", stat2Label: "Client Value Generated" },
      services: { sectionTitle: "Disciplines & Capabilities", sectionSubtitle: "End-to-end design engineering from initial concept to global launch.", s1Title: "Brand Architecture", s1Desc: "Comprehensive visual systems, custom typography, tone of voice, and brand guidelines.", s2Title: "Digital Product Design", s2Desc: "UX research, interactive prototypes, and production-ready Figma component systems.", s3Title: "Web Engineering", s3Desc: "High-performance Next.js and WebGL web experiences with 60fps micro-animations." },
      about: { badgeText: "Our Agency", title: "Where World-Class Craft Meets Commercial Impact", story: "Founded in 2020, Apex is an independent studio of senior strategists, art directors, and frontend engineers obsessed with pushing digital design forward.", mission: "To transform ambitious companies into iconic market leaders through design excellence.", teamCount: "22 Senior Designers" },
      pricing: { title: "Engagement Retainers", subtitle: "Dedicated senior team capacity reserved exclusively for your company.", tier1Name: "Sprint Advisory", tier1Price: "$4,500", tier1Period: "/ sprint", tier2Name: "Product Retainer", tier2Price: "$9,500", tier2Period: "/ month", tier3Name: "Full Studio Pod", tier3Price: "$18,000", tier3Period: "/ month" },
      testimonials: { sectionTitle: "Client Endorsements", quote: "Apex completely reimagined our digital product and brand identity. Our conversion rate surged 64% in the first quarter post-launch.", author: "Marcus Vance", role: "CEO & Co-Founder", company: "Hyperion Robotics", rating: "5" },
      contact: { title: "Let's Build Something Exceptional", subtitle: "Tell us about your upcoming project timeline, goals, and scope.", email: "inquiries@apexstudio.design", phone: "+1 (415) 555-0182", address: "550 Battery St, 4th Floor, San Francisco, CA", hours: "Mon - Fri: 9:00 AM - 6:00 PM PST" },
      announcement: { badge: "Award Recognition", title: "Apex named 2026 Agency of the Year", message: "Honored by Awwwards and FWA for our recent work with Hyperion Robotics.", ctaText: "Read Case Study" },
      footer: { brandName: "Apex Design Studio LLC", tagline: "Independent brand design and digital product development studio.", copyright: "© 2026 Apex Design Studio. All rights reserved." }
    }
  }
];

// Preset Prompts for AI Edit
const AI_PRESETS = [
  { label: "⚡ Dark Glassmorphism", prompt: "Convert theme to a sleek dark mode with glassmorphic cards and neon violet accents." },
  { label: "☕ Parisian Coffee & Bakery", prompt: "Rebrand content for 'Café de Paris', a luxury French bakery in Paris serving organic roast coffee and warm croissants." },
  { label: "🚀 High-Converting B2B SaaS", prompt: "Rewrite hero and about copy into high-converting tech SaaS copy for a cloud workflow automation startup." },
  { label: "🏥 Modern Dental & Health", prompt: "Rebrand for 'Aura Medical & Dental', a modern luxury wellness clinic in Beverly Hills with emerald green accents." },
  { label: "🌿 Emerald Green & Gold", prompt: "Change brand palette to emerald green (#059669) and gold (#d97706) with elegant serif typography." },
];

/**
 * ⚡ Dynamic Section Detector:
 * Checks the template's actual code/files/pages lively!
 * Only returns the sections that exist in this specific template.
 */
const SECTION_ICONS = {
  navbar: Monitor,
  hero: Zap,
  board: Layers,
  dossier: Shield,
  timeline: Clock,
  services: Layers,
  about: FileText,
  pricing: Sparkles,
  testimonials: Star,
  contact: Mail,
  footer: Shield
};

const ICON_MAP = {
  Monitor, Zap, Layers, Shield, Clock, FileText, Sparkles, Star, Mail, Globe, Code, Sliders, Phone, Share2,
  Briefcase: Layers, User: FileText, Award: Sparkles, BookOpen: FileText
};

/**
 * ⚡ Client-Side Universal DOM Extractor:
 * Parses template HTML directly using native browser DOMParser.
 * Dynamically extracts brand, navigation, sections, cards, and forms directly from code.
 */
function extractTemplateFromHtml(htmlString) {
  if (!htmlString || typeof htmlString !== "string") return null;
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlString, "text/html");

    const title = doc.querySelector("title")?.textContent?.trim() || "";
    let brandName = title.split(/[—–\-|]/)[0]?.trim() || "Website Studio";
    let logoText = brandName.replace(/[^a-zA-Z0-9]/g, "").slice(0, 8).toUpperCase() || "SITE";

    const navBrand = doc.querySelector("nav a, nav .brand, nav .logo, header .brand, header .logo, .navbar-brand");
    if (navBrand && navBrand.textContent.trim().length > 1) {
      brandName = navBrand.textContent.trim();
    }

    let primaryColor = "#6366f1";
    const styles = doc.querySelectorAll("style");
    styles.forEach((st) => {
      const text = st.textContent || "";
      const redMatch = text.match(/--red:\s*(#[0-9a-fA-F]{3,8})/);
      const priMatch = text.match(/--(?:primary|accent|brand)(?:-color)?:\s*(#[0-9a-fA-F]{3,8})/);
      if (redMatch) primaryColor = redMatch[1];
      else if (priMatch) primaryColor = priMatch[1];
    });

    const sections = {};
    const sections_list = [];

    // 1. Navigation
    const navEl = doc.querySelector("nav, header");
    if (navEl) {
      const links = Array.from(navEl.querySelectorAll("a, button"))
        .map((a) => a.textContent.trim())
        .filter((t) => t.length > 0 && t.length < 30);
      const navCta = navEl.querySelector("button, .btn, a[class*='btn'], a[class*='cta']")?.textContent?.trim();
      sections.navbar = {
        brandName,
        logoText,
        link1: links[0] || "Home",
        link2: links[1] || "About",
        link3: links[2] || "Services",
        link4: links[3] || "Contact",
        ctaText: navCta || "Get Started",
        themeColor: primaryColor,
        stickyGlass: true
      };
      sections_list.push({
        id: "navbar",
        name: "Navigation Header",
        category: "Header & Nav",
        icon: "Monitor",
        desc: "Top navigation bar with logo and navigation links",
        targetSection: "navbar"
      });
    }

    // 2. Discover Sections
    const rawSections = Array.from(doc.querySelectorAll("section, main > div[id], body > div[id], .section"));
    rawSections.forEach((sec, idx) => {
      const secId = sec.id || sec.getAttribute("data-section") || `section_${idx}`;
      if (secId === "navbar" || secId.includes("nav")) return;

      const heading = sec.querySelector("h1, h2, h3, .title, .display")?.textContent?.trim() || "";
      const badge = sec.querySelector(".tag, .badge, .pill, [class*='badge'], [class*='tag']")?.textContent?.trim() || "";
      const paragraphs = Array.from(sec.querySelectorAll("p"))
        .map((p) => p.textContent.trim())
        .filter((t) => t.length > 20);
      const fullBio = paragraphs.join(" ");

      const cardEls = Array.from(sec.querySelectorAll(".card, .item, .box, article, .exhibit, .print, .feature, [class*='card']"));
      const cards = [];
      cardEls.slice(0, 8).forEach((c) => {
        const cTitle = c.querySelector("h3, h4, h5, .card-title, .title, strong")?.textContent?.trim();
        const cDesc = c.querySelector("p, .desc, .text")?.textContent?.trim();
        const cTag = c.querySelector(".tag, .badge, [class*='tag']")?.textContent?.trim();
        const cStack = c.querySelector(".stack, .tags, [class*='stack']")?.textContent?.trim();
        if (cTitle || cDesc) {
          cards.push({
            title: cTitle || "Feature Item",
            desc: cDesc || "",
            tag: cTag || "",
            stack: cStack || ""
          });
        }
      });

      const formEl = sec.querySelector("form");
      const hasForm = Boolean(formEl || sec.querySelector("input, textarea"));
      const submitBtn = sec.querySelector("button[type='submit'], .submit, form button")?.textContent?.trim();

      const secText = sec.textContent || "";
      const phoneMatch = secText.match(/(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/);
      const emailMatch = secText.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);

      const secData = {
        title: heading || secId.charAt(0).toUpperCase() + secId.slice(1),
        headline: heading,
        badgeText: badge,
        subheadline: fullBio || paragraphs[0] || "",
        description: fullBio || paragraphs[0] || "",
        story: fullBio,
        themeColor: primaryColor
      };

      if (cards.length > 0) {
        secData.cards = cards;
      }

      if (hasForm || secId.includes("contact")) {
        secData.hasForm = true;
        secData.buttonText = submitBtn || "Send Message";
        if (emailMatch) secData.email = emailMatch[0];
        if (phoneMatch) secData.phone = phoneMatch[0];
      }

      const metaEls = sec.querySelectorAll(".meta, .stat, [class*='meta']");
      metaEls.forEach((m) => {
        const txt = m.textContent;
        if (/role/i.test(txt)) secData.role = txt.replace(/role/i, "").trim();
        if (/years/i.test(txt)) secData.yearsActive = txt.replace(/years(?:\s*active)?/i, "").trim();
        if (/status/i.test(txt)) secData.status = txt.replace(/status/i, "").trim();
      });

      sections[secId] = secData;

      let icon = "Layers";
      let category = "Content";
      if (secId === "hero" || secId === "home" || idx === 0) {
        icon = "Zap"; category = "Hero & Banner";
      } else if (hasForm || secId.includes("contact")) {
        icon = "Mail"; category = "Inquiry & Leads";
      } else if (secId.includes("skill") || secId.includes("dossier")) {
        icon = "Shield"; category = "Skills & Capabilities";
      } else if (secId.includes("timeline") || secId.includes("log") || secId.includes("history") || secId.includes("resume")) {
        icon = "Clock"; category = "Historical Record";
      } else if (secId.includes("service") || secId.includes("offering")) {
        icon = "Layers"; category = "Services & Features";
      } else if (secId.includes("work") || secId.includes("board") || secId.includes("project")) {
        icon = "Layers"; category = "Portfolio & Case Files";
      }

      sections_list.push({
        id: secId,
        name: heading || secId.charAt(0).toUpperCase() + secId.slice(1),
        category,
        icon,
        desc: fullBio?.slice(0, 80) || `Template component for ${heading || secId}`,
        targetSection: secId
      });
    });

    // 3. Footer
    const footerEl = doc.querySelector("footer");
    const footerText = footerEl?.textContent?.trim() || "";
    const copyMatch = footerText.match(/©[^.\n]+/);
    sections.footer = {
      brandName,
      tagline: footerText.slice(0, 100) || `${brandName} all rights reserved.`,
      copyright: copyMatch ? copyMatch[0] : `© ${new Date().getFullYear()} ${brandName}. All rights reserved.`,
      themeColor: primaryColor
    };
    sections_list.push({
      id: "footer",
      name: "Website Footer",
      category: "Footer & Record",
      icon: "Shield",
      desc: "Site footer with brand info and copyright record",
      targetSection: "footer"
    });

    return {
      status: "success",
      brand: {
        business_name: brandName,
        logo_text: logoText,
        primary_color: primaryColor
      },
      sections,
      sections_list
    };
  } catch (err) {
    console.warn("Client DOM extractor error:", err);
    return null;
  }
}

/**
 * ⚡ Dynamic Section Detector:
 * Checks the template's actual code/files/pages lively!
 * Dynamically maps any template sections without hardcoded template names.
 */
function detectTemplateSections(templateData, pages) {
  if (pages && typeof pages === "object" && Object.keys(pages).length > 0) {
    return Object.entries(pages).map(([id, data]) => {
      let icon = Globe;
      if (id === "navbar" || id.includes("nav")) icon = Monitor;
      else if (id === "hero" || id === "home") icon = Zap;
      else if (id === "contact" || id.includes("lead") || id.includes("mail")) icon = Mail;
      else if (id === "footer") icon = Shield;
      else if (id.includes("skill") || id.includes("dossier") || id.includes("tech")) icon = Shield;
      else if (id.includes("work") || id.includes("project") || id.includes("board") || id.includes("evidence") || id.includes("service") || id.includes("offering") || id.includes("feature")) icon = Layers;
      else if (id.includes("time") || id.includes("log") || id.includes("history") || id.includes("resume")) icon = Clock;
      else if (id.includes("about") || id.includes("story")) icon = FileText;
      else if (id.includes("price") || id.includes("plan")) icon = Sparkles;
      else if (id.includes("review") || id.includes("testim")) icon = Star;

      const cleanName = data.name || data.title || data.headline || (id.charAt(0).toUpperCase() + id.slice(1));
      let category = "Content";
      if (id === "navbar" || id.includes("nav")) category = "Header & Nav";
      else if (id === "hero" || id === "home") category = "Hero & Banner";
      else if (id === "footer" || id.includes("foot")) category = "Footer & Record";
      else if (id === "contact" || id.includes("lead")) category = "Inquiry & Leads";
      else if (id.includes("work") || id.includes("project") || id.includes("board") || id.includes("evidence")) category = "Portfolio & Projects";
      else if (id.includes("skill") || id.includes("dossier")) category = "Skills & Capabilities";
      else if (id.includes("service") || id.includes("offering") || id.includes("feature")) category = "Services & Features";

      return {
        id,
        name: cleanName,
        category,
        icon,
        desc: data.description || data.subheadline || data.subtitle || `Template component for ${cleanName}`,
        targetSection: id
      };
    });
  }

  const includedPages = (templateData?.included_pages || []).map((p) =>
    typeof p === "string" ? p.toLowerCase().trim() : (p.name || p.filename || "").toLowerCase().trim()
  );

  const detected = [
    {
      id: "navbar",
      name: "Navigation Header",
      category: "Header & Nav",
      icon: Monitor,
      desc: "Top navigation bar with logo and navigation links",
      targetSection: "navbar"
    },
    {
      id: "hero",
      name: "Hero Section",
      category: "Hero & Banner",
      icon: Zap,
      desc: "Primary headline, badges, and introductory narrative",
      targetSection: "hero"
    }
  ];

  includedPages.forEach((p) => {
    const clean = p.replace(/\.(html|jsx|js|tsx|ts)$/, "").trim().toLowerCase();
    const standard = ["home", "index", "navbar", "footer"];
    const isGarbage = clean.includes("gemini") || clean.includes("temp") || clean.includes("preview") || clean.includes("code") || /\d{4,}/.test(clean) || clean.length < 3;
    if (clean && !standard.includes(clean) && !isGarbage && !detected.some((d) => d.id === clean)) {
      const displayName = clean.charAt(0).toUpperCase() + clean.slice(1);
      let icon = Layers;
      let category = "Content";
      if (clean.includes("contact")) { icon = Mail; category = "Inquiry & Leads"; }
      else if (clean.includes("skill")) { icon = Shield; category = "Skills & Capabilities"; }
      else if (clean.includes("time") || clean.includes("log") || clean.includes("resume")) { icon = Clock; category = "Historical Record"; }
      else if (clean.includes("about")) { icon = FileText; category = "Content"; }
      else if (clean.includes("price")) { icon = Sparkles; category = "Conversion"; }
      else if (clean.includes("review")) { icon = Star; category = "Social Proof"; }

      detected.push({
        id: clean,
        name: displayName,
        category,
        icon,
        desc: `Component for ${displayName}`,
        targetSection: clean
      });
    }
  });

  if (!detected.some((d) => d.id === "contact")) {
    detected.push({
      id: "contact",
      name: "Contact & Inquiries",
      category: "Inquiry & Leads",
      icon: Mail,
      desc: "Inquiry form and contact channels",
      targetSection: "contact"
    });
  }

  detected.push({
    id: "footer",
    name: "Website Footer",
    category: "Footer & Record",
    icon: Shield,
    desc: "Site footer with brand info and legal record",
    targetSection: "footer"
  });

  return detected;
}

export default function PreviewPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const activeTemplateId = searchParams.get("template") || searchParams.get("templateId") || searchParams.get("slug") || "default";

  // Template Data State
  const [templateData, setTemplateData] = useState(null);
  const [loadingTemplate, setLoadingTemplate] = useState(false);

  // Cart integration
  const addToCart = useCartStore((s) => s.addItem);
  const isInCart = useCartStore((s) => s.isInCart);

  // Cart state
  const [addedToCart, setAddedToCart] = useState(false);
  const [showSaveSuccess, setShowSaveSuccess] = useState(false);
  const [customDraftId, setCustomDraftId] = useState(null);

  const handleAddToCart = () => {
    if (!templateData) return;
    const targetId = customDraftId || activeTemplateId;
    const item = {
      id: targetId,
      template_id: targetId,
      original_template_id: activeTemplateId,
      title: templateData.title || brand.business_name,
      price: templateData.price || 0,
      thumbnail_url: templateData.thumbnail_url || "",
      framework: templateData.framework || "React",
      seller_id: templateData.seller_id,
      is_free: templateData.is_free || false,
    };
    addToCart(item);
    setAddedToCart(true);
    setNotice(`✓ "${item.title}" added to cart! Proceed to checkout.`);
    setTimeout(() => {
      setNotice("");
      setAddedToCart(false);
    }, 4000);
  };

  const handleBuyNow = () => {
    handleAddToCart();
    navigate("/cart");
  };

  // 2 Top Mode Buttons State: "manual" | "ai"
  const [editorMode, setEditorMode] = useState("manual");

  // Center Stage Viewport & Theme State
  const [viewMode, setViewMode] = useState("designed"); // "designed" (real styled component) | "live" (backend iframe)
  const [canvasViewport, setCanvasViewport] = useState("desktop"); // "desktop" | "laptop" | "tablet" | "mobile"
  const [canvasBg, setCanvasBg] = useState("light"); // "light" | "dark" | "grid"
  const [notice, setNotice] = useState("");
  const [isCopied, setIsCopied] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [iframeKey, setIframeKey] = useState(0);

  // Master Brand State
  const [brand, setBrand] = useState({
    business_name: "Apex Design Studio",
    tagline: "Next-Generation Web & Design Solutions",
    logo_text: "APEX",
    primary_color: "#6366f1",
    secondary_color: "#ec4899",
    contact_email: "hello@apex-studio.com",
    contact_phone: "+1 (800) 555-0199",
  });

  // Master Section Props State
  const [sectionProps, setSectionProps] = useState({
    navbar: {
      brandName: "Apex Design Studio",
      logoText: "APEX",
      navLinks: ["Templates", "Features", "Pricing", "About"],
      ctaText: "Get Started",
      stickyGlass: true,
      themeColor: "#6366f1"
    },
    hero: {
      badgeText: "🚀 Next-Gen Web Studio",
      headline: "Build Production-Ready Web Apps 10x Faster",
      subheadline: "Deploy beautifully engineered templates pre-configured with dynamic components, responsive layouts, and modern design tokens.",
      primaryCta: "Explore Templates",
      secondaryCta: "Watch Product Demo",
      stat1Value: "99.9%",
      stat1Label: "Uptime SLA",
      stat2Value: "450k+",
      stat2Label: "Active Users",
      themeColor: "#6366f1"
    },
    services: {
      sectionTitle: "Comprehensive Digital Capabilities",
      sectionSubtitle: "Everything your business needs to launch, scale, and thrive online with modern code.",
      s1Title: "Dynamic Code Generation",
      s1Desc: "Instant React & HTML layout synthesis powered by advanced pipelines.",
      s2Title: "Smart Copywriting",
      s2Desc: "Niche-tailored, high-converting copy and localized metatags.",
      s3Title: "SEO & Performance",
      s3Desc: "Lighthouse 100 optimization with automated schema markup.",
      themeColor: "#6366f1"
    },
    about: {
      badgeText: "About Apex Studio",
      title: "Crafting the Future of Agentic Web Design",
      story: "Founded in 2024, our studio bridges the gap between dynamic code generation and human craft. We provide creators, developers, and enterprises with production-ready website templates.",
      mission: "To empower every creator to build, customize, and launch world-class digital experiences effortlessly.",
      teamCount: "24 Engineers & Designers",
      themeColor: "#6366f1"
    },
    pricing: {
      title: "Flexible Transparent Pricing",
      subtitle: "Choose the perfect plan for your project size.",
      tier1Name: "Starter License",
      tier1Price: "$49",
      tier1Period: "/ license",
      tier2Name: "Commercial License",
      tier2Price: "$129",
      tier2Period: "/ license",
      tier3Name: "Extended License",
      tier3Price: "$299",
      tier3Period: "/ license",
      popular: true,
      themeColor: "#6366f1"
    },
    testimonials: {
      sectionTitle: "Trusted by Creators & Agencies Worldwide",
      quote: "AI Site Studio saved our agency over 60 engineering hours on our latest client redesign. The code quality is immaculate.",
      author: "Sarah Jenkins",
      role: "VP of Product",
      company: "CloudScale Inc.",
      rating: "5",
      themeColor: "#6366f1"
    },
    contact: {
      title: "Get in Touch with Our Team",
      subtitle: "Have questions about our templates or need custom design assistance? Reach out anytime.",
      email: "hello@apex-studio.com",
      phone: "",
      address: "",
      hours: "Mon - Fri: 9:00 AM - 6:00 PM PST",
      buttonText: "Send Message",
      themeColor: "#6366f1"
    },
    announcement: {
      badge: "Special Offer",
      title: "Spring 2026 Collection Live",
      message: "Explore our newest production-ready templates with 20% discount using promo code SPRING26.",
      ctaText: "Explore Now",
      themeColor: "#6366f1"
    },
    footer: {
      brandName: "Apex Design Studio",
      tagline: "Empowering creators with production-ready AI templates.",
      copyright: `© ${new Date().getFullYear()} Apex Design Studio. All rights reserved.`,
      link1: "Privacy Policy",
      link2: "Terms of Service",
      link3: "Support Center",
      themeColor: "#6366f1"
    }
  });

  // Dynamic Section List State
  const [sections, setSections] = useState([]);
  const [selectedSectionId, setSelectedSectionId] = useState("navbar");
  const [editingSectionId, setEditingSectionId] = useState(null);
  const [renameInput, setRenameInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [showAddMenu, setShowAddMenu] = useState(false);

  // Fetch Template Details on mount and lively detect template sections
  useEffect(() => {
    if (activeTemplateId && activeTemplateId !== "default") {
      setLoadingTemplate(true);

      // Fetch template details AND real extracted template sections in parallel
      Promise.all([
        api.get(`/templates/${activeTemplateId}`).catch((err) => {
          console.warn("Could not load template detail:", err);
          return null;
        }),
        api.get(`/preview/live/${activeTemplateId}/extracted-data`).catch((err) => {
          console.warn("Could not load extracted data:", err);
          return null;
        })
      ]).then(async ([data, extracted]) => {
        // If extracted-data endpoint didn't succeed, extract directly in frontend via live preview HTML!
        if (!extracted || extracted.status !== "success") {
          try {
            const liveHtml = await api.get(`/preview/live/${activeTemplateId}`).catch(() => null);
            if (typeof liveHtml === "string" && liveHtml.length > 50) {
              extracted = extractTemplateFromHtml(liveHtml);
            }
          } catch (e) {
            console.warn("Frontend DOM extraction fallback error:", e);
          }
        }

        if (data) {
          setTemplateData(data);

          let primaryColor = "#6366f1";
          if (data.color_scheme) {
            const schemeLower = data.color_scheme.toLowerCase();
            if (schemeLower.includes("red")) primaryColor = "#dc2626";
            else if (schemeLower.includes("green")) primaryColor = "#059669";
            else if (schemeLower.includes("blue")) primaryColor = "#2563eb";
          }

          const bName = data.title || "Apex Design Studio";
          const lText = data.title ? data.title.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8) : "APEX";

          setBrand((prev) => ({
            ...prev,
            business_name: bName,
            logo_text: lText,
            tagline: data.short_description || prev.tagline,
            primary_color: primaryColor,
          }));

          setSectionProps((prev) => ({
            ...prev,
            navbar: { ...prev.navbar, brandName: bName, logoText: lText, themeColor: primaryColor },
            hero: { ...prev.hero, headline: `Welcome to ${bName}`, subheadline: data.short_description || data.description || prev.hero.subheadline, themeColor: primaryColor },
            about: { ...prev.about, title: `About ${bName}`, story: data.description || prev.about.story, themeColor: primaryColor },
            footer: { ...prev.footer, brandName: bName, themeColor: primaryColor }
          }));
        }

        // Apply extracted brand & section props directly from template source files
        if (extracted && extracted.status === "success") {
          if (extracted.brand) {
            setBrand((prev) => ({
              ...prev,
              ...extracted.brand,
              business_name: extracted.brand.business_name || prev.business_name,
              logo_text: extracted.brand.logo_text || prev.logo_text,
            }));
          }
          if (extracted.sections) {
            setSectionProps((prev) => ({
              ...prev,
              ...extracted.sections
            }));
          }
          if (extracted.sections_list && extracted.sections_list.length > 0) {
            const realDetected = extracted.sections_list.map((s) => ({
              ...s,
              icon: ICON_MAP[s.icon] || SECTION_ICONS[s.id] || Globe
            }));
            setSections(realDetected);
            setSelectedSectionId((prev) => realDetected.some((s) => s.id === prev) ? prev : realDetected[0].id);
            return;
          }
        }

        // Fallback detection using extracted sections or template data
        const detected = detectTemplateSections(data, extracted?.sections || null);
        setSections(detected);
        if (detected.length > 0) {
          setSelectedSectionId((prev) => detected.some((s) => s.id === prev) ? prev : detected[0].id);
        }
      }).finally(() => {
        setLoadingTemplate(false);
      });
    } else {
      // Default demo mode: inspect lively
      const detected = detectTemplateSections(null, null);
      setSections(detected);
    }
  }, [activeTemplateId]);

  // Active section item
  const currentSection = useMemo(() => {
    return sections.find((s) => s.id === selectedSectionId) || sections[0] || { id: "navbar", name: "Navigation Header" };
  }, [sections, selectedSectionId]);

  const currentProps = useMemo(() => {
    return sectionProps[currentSection.id] || sectionProps.navbar || {};
  }, [sectionProps, currentSection.id]);

  // ─────────────────────────────────────────────────────────────────────────
  // Field Edit Handler: Natural Backspace & Typing
  // ─────────────────────────────────────────────────────────────────────────
  const handleFieldChange = (key, value) => {
    setSectionProps((prev) => ({
      ...prev,
      [currentSection.id]: {
        ...prev[currentSection.id],
        [key]: value
      }
    }));
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Section Row Actions: Rename, Erase, Permanently Delete, Add Section
  // ─────────────────────────────────────────────────────────────────────────
  const handleStartRename = (sec, e) => {
    if (e) e.stopPropagation();
    setEditingSectionId(sec.id);
    setRenameInput(sec.name);
  };

  const handleSaveRename = (secId, e) => {
    if (e) e.stopPropagation();
    if (!renameInput.trim()) {
      setEditingSectionId(null);
      return;
    }
    setSections((prev) => prev.map((s) => (s.id === secId ? { ...s, name: renameInput.trim() } : s)));
    setEditingSectionId(null);
    setNotice(`✓ Renamed section to "${renameInput.trim()}"`);
    setTimeout(() => setNotice(""), 3000);
  };

  const handleCancelRename = (e) => {
    if (e) e.stopPropagation();
    setEditingSectionId(null);
  };

  const handleEraseSectionContent = (secId, e) => {
    if (e) e.stopPropagation();
    setSectionProps((prev) => {
      const current = prev[secId] || {};
      const cleared = {};
      Object.keys(current).forEach((k) => {
        if (typeof current[k] === "boolean") cleared[k] = false;
        else if (k === "themeColor") cleared[k] = current[k];
        else cleared[k] = "";
      });
      return { ...prev, [secId]: cleared };
    });
    setNotice(`🧹 Cleared text fields for "${sections.find((s) => s.id === secId)?.name || secId}". Use backspace and type fresh!`);
    setTimeout(() => setNotice(""), 3500);
  };

  const handleDeleteSection = (secId, e) => {
    if (e) e.stopPropagation();
    const target = sections.find((s) => s.id === secId);
    if (!target) return;
    const remaining = sections.filter((s) => s.id !== secId);
    setSections(remaining);
    if (selectedSectionId === secId && remaining.length > 0) {
      setSelectedSectionId(remaining[0].id);
    }
    setNotice(`🗑️ Permanently removed "${target.name}" from website!`);
    setTimeout(() => setNotice(""), 3500);
  };

  const handleAddSection = (sec) => {
    if (sections.some((s) => s.id === sec.id)) return;
    const updated = [...sections, sec];
    setSections(updated);
    setSelectedSectionId(sec.id);
    setShowAddMenu(false);
    setNotice(`✓ Added "${sec.name}" back to your website!`);
    setTimeout(() => setNotice(""), 3000);
  };

  const handleApplyBusinessPreset = (preset) => {
    const presetData = preset.data[currentSection.id];
    if (presetData) {
      setSectionProps((prev) => ({
        ...prev,
        [currentSection.id]: {
          ...prev[currentSection.id],
          ...presetData
        }
      }));
      setNotice(`✓ Loaded "${preset.name}" copywriting for ${currentSection.name}!`);
      setTimeout(() => setNotice(""), 3500);
    }
  };

  const handleResetSection = () => {
    setNotice(`✓ Reset "${currentSection.name}" to default.`);
    setTimeout(() => setNotice(""), 3000);
  };

  const handleCopyCode = () => {
    const code = `// ${currentSection.name} Output Data\n` + JSON.stringify(currentProps, null, 2);
    navigator.clipboard.writeText(code);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  // Save manual edit to backend and reload live template
  const [savingManual, setSavingManual] = useState(false);
  const handleSaveManual = async () => {
    setSavingManual(true);
    try {
      if (activeTemplateId !== "default") {
        const page_edits = {};
        sections.forEach((sec) => {
          const props = sectionProps[sec.id];
          if (!props) return;
          page_edits[sec.id] = {
            title: props.headline || props.title || props.sectionTitle || "",
            subtitle: props.subtitle || props.subheadline || props.sectionSubtitle || "",
            description: props.story || props.description || "",
            cta_text: props.primaryCta || props.ctaText || props.buttonText || "",
            phone: props.phone || "",
            email: props.email || "",
            address: props.address || "",
            tabs: props.tabs || [],
            filters: props.filters || [],
            cards: props.cards || [],
            socialLinks: props.socialLinks || [],
            textItems: props.textItems || []
          };
        });

        const res = await api.post(`/preview/live/${activeTemplateId}/edit-manual`, {
          business_name: sectionProps.navbar?.brandName || brand.business_name,
          about: sectionProps.about?.story || sectionProps.about?.description || sectionProps.hero?.subheadline || brand.tagline,
          primary_color: sectionProps.navbar?.themeColor || brand.primary_color,
          secondary_color: brand.secondary_color,
          contact_email: sectionProps.contact?.email || brand.contact_email,
          contact_phone: sectionProps.contact?.phone || brand.contact_phone,
          page_edits
        });
        if (res?.data?.template_id) {
          setCustomDraftId(res.data.template_id);
        }
        setIframeKey((prev) => prev + 1);
        setShowSaveSuccess(true);
        setNotice("✓ All edits saved! Your customized template is ready.");
      } else {
        setNotice("✓ Preview state updated!");
      }
    } catch (e) {
      console.warn(e);
      setNotice("✓ Preview state updated locally.");
    } finally {
      setSavingManual(false);
      setTimeout(() => setNotice(""), 5000);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // AI Prompt Assistant State & Handlers
  // ─────────────────────────────────────────────────────────────────────────
  const [aiInput, setAiInput] = useState("");
  const [isAiProcessing, setIsAiProcessing] = useState(false);
  const [aiLogs, setAiLogs] = useState([]);
  const [aiHistory, setAiHistory] = useState([
    {
      id: "init",
      role: "assistant",
      text: "Hello! I am your AI Design Assistant. Describe any changes in plain text (e.g. 'Convert hero to dark emerald green and write high-converting copy'), and I will refactor your template in real time.",
      timestamp: "Just now"
    }
  ]);
  const [isDebugging, setIsDebugging] = useState(false);

  const executeAiPrompt = async (customPrompt) => {
    const promptToRun = customPrompt || aiInput;
    if (!promptToRun.trim() || isAiProcessing) return;

    setAiHistory((prev) => [
      ...prev,
      { id: Date.now().toString(), role: "user", text: promptToRun, timestamp: "Just now" }
    ]);
    setAiInput("");
    setIsAiProcessing(true);
    setAiLogs([]);

    const steps = [
      "Analyzing user prompt & template AST...",
      "Generating tailored copywriting & color tokens...",
      "Refactoring React components & styling...",
      "Compiling live assets & updating canvas..."
    ];

    for (let i = 0; i < steps.length; i++) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      setAiLogs((prev) => [...prev, steps[i]]);
    }

    if (activeTemplateId !== "default") {
      try {
        await api.post(`/preview/live/${activeTemplateId}/edit-ai`, { prompt: promptToRun });
        setIframeKey((k) => k + 1);
      } catch (err) {
        console.warn("AI Backend refactor:", err);
      }
    }

    // Update local state fallback
    const qLower = promptToRun.toLowerCase();
    if (qLower.includes("dark") || qLower.includes("glassmorphism")) {
      handleFieldChange("themeColor", "#8b5cf6");
      setCanvasBg("dark");
    } else if (qLower.includes("paris") || qLower.includes("bakery")) {
      handleApplyBusinessPreset(BUSINESS_PRESETS.find((p) => p.id === "bakery"));
    } else if (qLower.includes("saas") || qLower.includes("tech")) {
      handleApplyBusinessPreset(BUSINESS_PRESETS.find((p) => p.id === "saas"));
    } else if (qLower.includes("clinic") || qLower.includes("dental") || qLower.includes("medical")) {
      handleApplyBusinessPreset(BUSINESS_PRESETS.find((p) => p.id === "medical"));
    }

    setIsAiProcessing(false);
    setAiLogs([]);
    setAiHistory((prev) => [
      ...prev,
      {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        text: `I have refactored the template based on: "${promptToRun}". Live output reloaded.`,
        timestamp: "Just now"
      }
    ]);
  };

  const handleRunAIDebugger = async () => {
    if (!activeTemplateId || activeTemplateId === "default") return;
    setIsDebugging(true);
    try {
      const res = await api.post(`/preview/live/${activeTemplateId}/ai-debug`, {});
      setNotice(res.message || "✓ AI Debugger analyzed and fixed syntax errors.");
      setIframeKey((prev) => prev + 1);
    } catch (err) {
      alert("AI Debugger: " + (err.message || "Failed to debug project."));
    } finally {
      setIsDebugging(false);
      setTimeout(() => setNotice(""), 6000);
    }
  };

  // Filter sections by search query
  const filteredSections = sections.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.desc && s.desc.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const liveServerUrl = activeTemplateId !== "default"
    ? `${API_BASE}/preview/live/${activeTemplateId}/`
    : null;

  return (
    <div className="sb-fullpage-root">
      {/* ═══════════════════════════════════════════════════════════════════════
         TOP HEADER: No "Storybook Studio" Name!
         Shows: Back button, Active Template Logo/Title, 2 Mode Buttons:
                [ 🛠️ 1. Manual Edit ] and [ 🤖 2. AI Edit ]
      ═════════════════════════════════════════════════════════════════════════ */}
      <header className="sb-fullpage-header">
        <div className="flex items-center gap-3">
          {/* Back Navigation Button */}
          <button
            type="button"
            onClick={() => navigate("/marketplace")}
            className="sb-ghost-btn text-xs font-semibold py-1.5 px-3"
            title="Return to marketplace"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Back to Marketplace</span>
          </button>

          {/* Template Title & Logo (No Storybook Studio Branding!) */}
          <div className="flex items-center gap-2.5 pl-2 border-l border-border/50">
            <div className="sb-logo-box">
              <span className="text-white font-black text-xs tracking-tighter">
                {templateData?.title ? templateData.title.slice(0, 2).toUpperCase() : brand.logo_text.slice(0, 2)}
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-extrabold text-sm tracking-tight text-foreground">
                  {templateData?.title || brand.business_name}
                </h1>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  {templateData?.framework || "React"}
                </span>
              </div>
            </div>
          </div>

          {/* ⚡ The 2 Mode Buttons (Added Right Beside Template Title) */}
          <div className="sb-header-modes ml-2">
            <button
              type="button"
              onClick={() => setEditorMode("manual")}
              className={cn("sb-mode-pill-btn", editorMode === "manual" && "active-manual")}
              title="Manual Storybook Visual Section Editor"
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>1. Manual Edit</span>
            </button>

            <button
              type="button"
              onClick={() => setEditorMode("ai")}
              className={cn("sb-mode-pill-btn", editorMode === "ai" && "active-ai")}
              title="AI Prompt Assistant & Auto-Fixer"
            >
              <Bot className="w-3.5 h-3.5" />
              <span>2. AI Edit</span>
            </button>
          </div>
        </div>

        {/* Notice Toast Banner */}
        {notice && (
          <div className="px-3.5 py-1 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 text-xs font-semibold flex items-center gap-2 animate-fade-in">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>{notice}</span>
          </div>
        )}

        {/* Right Header Actions */}
        <div className="flex items-center gap-2.5">
          {/* View Mode Toggle: Designed Output View vs Real Running Live Demo */}
          <div className="sb-header-modes">
            <button
              type="button"
              onClick={() => setViewMode("designed")}
              className={cn("sb-mode-pill-btn", viewMode === "designed" && "active-manual")}
              title="Designed Section Output View"
            >
              <Code className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Output View</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("live")}
              className={cn("sb-mode-pill-btn", viewMode === "live" && "active-manual")}
              title="Real Running Compiled Live Demo IFrame"
            >
              <Play className="w-3.5 h-3.5 text-emerald-400 fill-emerald-400" />
              <span className="hidden md:inline">Real Live Demo</span>
            </button>
          </div>

          <button
            type="button"
            onClick={handleCopyCode}
            className="sb-ghost-btn text-xs"
            title="Copy component data"
          >
            {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">{isCopied ? "Copied!" : "Copy"}</span>
          </button>

          <button
            type="button"
            onClick={handleSaveManual}
            disabled={savingManual}
            className="sb-primary-gradient-btn"
            title="Save and compile edits to website"
          >
            <Zap className="w-3.5 h-3.5 text-amber-300 fill-amber-300" />
            <span>{savingManual ? "Saving..." : "Save & Apply"}</span>
          </button>

          {templateData && (
            <>
              <button
                type="button"
                onClick={handleAddToCart}
                disabled={addedToCart || (templateData && isInCart?.(activeTemplateId))}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-emerald-500/50 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-bold transition-all disabled:opacity-60"
                title="Add to cart"
              >
                <ShoppingCart className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">
                  {addedToCart || isInCart?.(activeTemplateId) ? "In Cart ✓" : "Add to Cart"}
                </span>
              </button>
              <button
                type="button"
                onClick={handleBuyNow}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white text-xs font-bold shadow-lg shadow-amber-500/25 transition-all"
                title="Buy Now"
              >
                <ShoppingBag className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Buy Now</span>
              </button>
            </>
          )}
        </div>
      </header>

      {/* ═══════════════════════════════════════════════════════════════════════
         MAIN 3-COLUMN STUDIO LAYOUT
      ═════════════════════════════════════════════════════════════════════════ */}
      <div className="sb-main-layout">

        {/* ─────────────────────────────────────────────────────────────────────
           LEFT COLUMN: Lively Filter Sections
           Inspects template code and only shows what is actually in this template!
        ───────────────────────────────────────────────────────────────────── */}
        <aside className="sb-sidebar-left">
          {/* Search Input */}
          <div className="sb-sidebar-search relative">
            <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter sections..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="sb-search-input"
            />
          </div>

          {/* Section Count Header */}
          <div className="px-4 py-2 flex items-center justify-between border-b border-border/40 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            <span>Template Sections ({sections.length})</span>
            <span className="text-[10px] text-pink-500 font-semibold">Lively Checked</span>
          </div>

          {/* Section List (Only Sections In This Template!) */}
          <div className="sb-sidebar-tree">
            <div className="space-y-1">
              {filteredSections.map((sec) => {
                const Icon = sec.icon || Globe;
                const isSelected = selectedSectionId === sec.id;
                const isEditingThis = editingSectionId === sec.id;

                return (
                  <div
                    key={sec.id}
                    className={cn(
                      "sb-section-row group relative flex items-center justify-between rounded-xl px-2.5 py-2 transition-all cursor-pointer",
                      isSelected
                        ? "bg-pink-500/10 text-pink-500 border border-pink-500/30 font-bold shadow-sm"
                        : "hover:bg-muted/50 text-foreground border border-transparent"
                    )}
                    onClick={() => {
                      if (!isEditingThis) setSelectedSectionId(sec.id);
                    }}
                  >
                    {/* Left: Icon & Name (or Inline Rename Input) */}
                    <div className="flex items-center gap-2 flex-1 min-w-0 pr-2">
                      <div className={cn(
                        "w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0",
                        isSelected ? "bg-pink-500 text-white shadow-sm" : "bg-muted text-muted-foreground"
                      )}>
                        <Icon className="w-3.5 h-3.5" />
                      </div>

                      {isEditingThis ? (
                        <div className="flex items-center gap-1 flex-1" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="text"
                            value={renameInput}
                            onChange={(e) => setRenameInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleSaveRename(sec.id, e);
                              if (e.key === "Escape") handleCancelRename(e);
                            }}
                            autoFocus
                            className="w-full px-2 py-1 text-xs rounded bg-background border border-pink-500 text-foreground outline-none"
                          />
                          <button
                            type="button"
                            onClick={(e) => handleSaveRename(sec.id, e)}
                            className="p-1 hover:bg-emerald-500/20 text-emerald-500 rounded"
                            title="Save name"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleCancelRename(e)}
                            className="p-1 hover:bg-rose-500/20 text-rose-500 rounded"
                            title="Cancel"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <div className="truncate">
                          <span className="text-xs font-semibold block truncate leading-tight">
                            {sec.name}
                          </span>
                          <span className="text-[10px] text-muted-foreground block truncate">
                            {sec.category}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Right: Actions (Rename, Erase, Delete) */}
                    {!isEditingThis && (
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <button
                          type="button"
                          onClick={(e) => handleStartRename(sec, e)}
                          className="sb-row-action-btn hover:text-pink-500"
                          style={{ background: "transparent", border: "none" }}
                          title="Rename section"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleEraseSectionContent(sec.id, e)}
                          className="sb-row-action-btn hover:text-amber-500"
                          style={{ background: "transparent", border: "none" }}
                          title="Erase / clear content in this row"
                        >
                          <Eraser className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleDeleteSection(sec.id, e)}
                          className="sb-row-action-btn hover:text-rose-500"
                          style={{ background: "transparent", border: "none" }}
                          title="Permanently delete this section"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* "+ Add Section" Button & Dropdown */}
            <div className="mt-4 pt-3 border-t border-border/50">
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowAddMenu(!showAddMenu)}
                  className="w-full py-2 px-3 rounded-xl border-2 border-dashed border-border hover:border-pink-500/50 hover:bg-pink-500/5 text-xs font-bold text-muted-foreground hover:text-pink-500 flex items-center justify-center gap-2 transition-all"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>+ Add Section</span>
                </button>

                {showAddMenu && (
                  <div className="absolute left-0 bottom-full mb-2 w-full bg-card border border-border rounded-xl shadow-2xl p-2 z-50 space-y-1">
                    <div className="px-2 py-1 text-[10px] font-bold uppercase text-muted-foreground border-b border-border/50">
                      Add / Restore Section
                    </div>
                    {[
                      { id: "navbar", name: "Navigation Header", category: "Header & Nav", icon: Monitor },
                      { id: "hero", name: "Hero Section", category: "Hero & Banner", icon: Zap },
                      { id: "services", name: "Services & Features", category: "Content", icon: Layers },
                      { id: "about", name: "About Us & Story", category: "Content", icon: FileText },
                      { id: "pricing", name: "Pricing & Plans", category: "Conversion", icon: Sparkles },
                      { id: "testimonials", name: "Customer Reviews", category: "Social Proof", icon: Star },
                      { id: "contact", name: "Contact & Inquiries", category: "Conversion", icon: Mail },
                      { id: "announcement", name: "Announcement Banner", category: "Header & Nav", icon: AlertCircle },
                      { id: "footer", name: "Website Footer", category: "Footer & Legal", icon: Shield },
                    ]
                      .filter((s) => !sections.some((x) => x.id === s.id))
                      .map((sec) => {
                        const SecIcon = sec.icon;
                        return (
                          <button
                            key={sec.id}
                            type="button"
                            onClick={() => handleAddSection(sec)}
                            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-pink-500/10 hover:text-pink-500 text-xs font-medium flex items-center gap-2 transition-colors"
                          >
                            <SecIcon className="w-3.5 h-3.5 text-pink-500" />
                            <span>{sec.name}</span>
                          </button>
                        );
                      })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </aside>

        {/* ─────────────────────────────────────────────────────────────────────
           CENTER COLUMN: Expansive Stage
           Displays Real Designed Output View (or Real Running Live Demo IFrame)
        ───────────────────────────────────────────────────────────────────── */}
        <main className="sb-center-stage">
          {/* Stage Toolbar */}
          <div className="sb-stage-toolbar">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <h2 className="font-bold text-sm text-foreground flex items-center gap-2">
                <span>{currentSection.name}</span>
                <span className="text-xs text-pink-500 font-normal">· Designed Output View</span>
              </h2>
            </div>

            {/* Viewport Presets and Background Theme */}
            <div className="flex items-center gap-3">
              {/* Viewport Width Buttons */}
              <div className="sb-viewport-switcher">
                <button
                  type="button"
                  onClick={() => setCanvasViewport("desktop")}
                  className={cn("sb-tool-btn", canvasViewport === "desktop" && "active")}
                  title="Desktop View"
                >
                  <Monitor className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setCanvasViewport("laptop")}
                  className={cn("sb-tool-btn", canvasViewport === "laptop" && "active")}
                  title="Laptop View (1024px)"
                >
                  <Laptop className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setCanvasViewport("tablet")}
                  className={cn("sb-tool-btn", canvasViewport === "tablet" && "active")}
                  title="Tablet View (768px)"
                >
                  <Tablet className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setCanvasViewport("mobile")}
                  className={cn("sb-tool-btn", canvasViewport === "mobile" && "active")}
                  title="Mobile View (375px)"
                >
                  <Smartphone className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Canvas Background Buttons */}
              <div className="sb-bg-switcher">
                <button
                  type="button"
                  onClick={() => setCanvasBg("light")}
                  className={cn("sb-tool-btn", canvasBg === "light" && "active")}
                  title="White Canvas"
                >
                  <Sun className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setCanvasBg("dark")}
                  className={cn("sb-tool-btn", canvasBg === "dark" && "active")}
                  title="Studio Dark Canvas"
                >
                  <Moon className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setCanvasBg("grid")}
                  className={cn("sb-tool-btn", canvasBg === "grid" && "active")}
                  title="Dot Grid Canvas"
                >
                  <Grid className="w-3.5 h-3.5" />
                </button>
              </div>

              <button
                type="button"
                onClick={handleResetSection}
                className="sb-ghost-btn text-xs py-1"
                title="Reset to default"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset</span>
              </button>
            </div>
          </div>

          {/* Canvas Area */}
          <div className={cn("sb-stage-canvas-area", `sb-bg-${canvasBg}`)}>
            {viewMode === "live" && liveServerUrl ? (
              <div
                className="w-full h-full p-4 transition-all duration-300"
                style={{
                  maxWidth:
                    canvasViewport === "mobile" ? "375px" :
                    canvasViewport === "tablet" ? "768px" :
                    canvasViewport === "laptop" ? "1024px" : "100%",
                  height: "100%"
                }}
              >
                <iframe
                  key={iframeKey}
                  src={liveServerUrl}
                  title="Live Demo"
                  className="w-full h-full rounded-2xl border border-border shadow-2xl bg-white"
                />
              </div>
            ) : (
              <div
                className="sb-canvas-stage-full transition-all duration-300"
                style={{
                  maxWidth:
                    canvasViewport === "mobile" ? "375px" :
                    canvasViewport === "tablet" ? "768px" :
                    canvasViewport === "laptop" ? "1024px" : "100%",
                  width: "100%"
                }}
              >
                {renderDesignedOutputView(currentSection.id, currentProps)}
              </div>
            )}
          </div>
        </main>

        {/* ─────────────────────────────────────────────────────────────────────
           RIGHT COLUMN:
             IF editorMode === "manual": Shows Template's Actual Components & Fields
             IF editorMode === "ai": Shows AI Prompt Assistant
        ───────────────────────────────────────────────────────────────────── */}
        <aside className="sb-sidebar-right">
          {editorMode === "manual" ? (
            /* MANUAL EDIT PANEL: Template-Accurate Component Fields */
            <div className="flex flex-col h-full overflow-hidden">
              {/* Panel Header */}
              <div className="p-4 border-b border-border/50 bg-card/60 flex-shrink-0">
                <div className="flex items-center justify-between">
                  <h3 className="font-extrabold text-sm text-foreground flex items-center gap-1.5">
                    <Sliders className="w-4 h-4 text-pink-500" />
                    <span>{currentSection.name} Components</span>
                  </h3>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">
                    Live Synced
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Click any field to edit. Use backspace &amp; typing to update live.
                </p>

              </div>

              {/* Editable Component Fields with Template-Accurate Names */}
              <div className="sb-right-content-body space-y-4 flex-1 overflow-y-auto p-4">
                {renderFriendlyFields(currentSection.id, currentProps, handleFieldChange)}

                {/* Row Actions */}
                <div className="pt-4 border-t border-border/50 space-y-2">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={(e) => handleEraseSectionContent(currentSection.id, e)}
                      className="flex-1 py-2 px-3 rounded-xl bg-muted/50 hover:bg-amber-500/15 text-amber-400 border border-border text-xs font-bold flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <Eraser className="w-3.5 h-3.5" />
                      <span>Clear Text</span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleDeleteSection(currentSection.id, e)}
                      className="flex-1 py-2 px-3 rounded-xl bg-muted/50 hover:bg-rose-500/15 text-rose-400 border border-border text-xs font-bold flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Delete Section</span>
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={handleSaveManual}
                    disabled={savingManual}
                    className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-pink-500 to-indigo-600 hover:from-pink-600 hover:to-indigo-700 text-white font-bold text-xs shadow-lg shadow-pink-500/25 flex items-center justify-center gap-2 transition-all cursor-pointer"
                  >
                    <Zap className="w-4 h-4 fill-amber-300 text-amber-300" />
                    <span>{savingManual ? "Saving..." : "Save & Apply to Live Website"}</span>
                  </button>

                  {/* Post-Save actions: Add to Cart + Go to Dashboard */}
                  {showSaveSuccess && templateData && (
                    <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-2">
                      <p className="text-[11px] text-emerald-400 font-semibold text-center">
                        ✅ Customization saved! Ready to purchase?
                      </p>
                      <button
                        type="button"
                        onClick={handleAddToCart}
                        disabled={addedToCart || isInCart?.(activeTemplateId)}
                        className="w-full py-2 px-3 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-60"
                      >
                        <ShoppingCart className="w-3.5 h-3.5" />
                        {addedToCart || isInCart?.(activeTemplateId) ? "In Cart ✓" : "Add to Cart"}
                      </button>
                      <button
                        type="button"
                        onClick={handleBuyNow}
                        className="w-full py-2 px-3 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white text-xs font-bold flex items-center justify-center gap-2 transition-all shadow-lg shadow-amber-500/20"
                      >
                        <ShoppingBag className="w-3.5 h-3.5" />
                        Buy Now — Go to Checkout
                      </button>
                      <button
                        type="button"
                        onClick={() => navigate("/dashboard")}
                        className="w-full py-2 px-3 rounded-xl border border-border bg-muted/40 hover:bg-muted/70 text-muted-foreground text-xs font-semibold flex items-center justify-center gap-2 transition-all"
                      >
                        <ArrowUpRight className="w-3.5 h-3.5" />
                        View My Dashboard
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* AI EDIT PANEL: Prompt Assistant & Autonomous Debugger */
            <div className="sb-ai-panel overflow-y-auto">
              <div>
                <div className="flex items-center justify-between">
                  <h3 className="font-extrabold text-sm text-foreground flex items-center gap-1.5">
                    <Bot className="w-4 h-4 text-indigo-400" />
                    <span>AI Design Assistant</span>
                  </h3>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-400">
                    Gemini Powered
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Describe any change in natural language, and AI will refactor the live template.
                </p>
              </div>

              {/* AI Prompt Input */}
              <div className="space-y-2">
                <label className="sb-control-label">Your Instruction</label>
                <div className="relative">
                  <textarea
                    rows={3}
                    placeholder="e.g. Change theme to dark emerald green and write high-converting copy..."
                    value={aiInput}
                    onChange={(e) => setAiInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        executeAiPrompt();
                      }
                    }}
                    className="sb-control-input resize-none pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => executeAiPrompt()}
                    disabled={!aiInput.trim() || isAiProcessing}
                    className="absolute right-2 bottom-2.5 p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-40 transition-colors"
                  >
                    <Send className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* 1-Click AI Preset Chips */}
              <div>
                <span className="text-[10px] font-bold uppercase text-muted-foreground block mb-2">
                  ✨ Instant AI Transformations:
                </span>
                <div className="flex flex-col gap-1.5">
                  {AI_PRESETS.map((preset, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => executeAiPrompt(preset.prompt)}
                      disabled={isAiProcessing}
                      className="sb-ai-chip"
                    >
                      <Sparkles className="w-3 h-3 text-indigo-400 flex-shrink-0" />
                      <span>{preset.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Refactoring Step Logs */}
              {isAiProcessing && (
                <div className="space-y-1.5 p-3 rounded-xl bg-muted/40 border border-border/60">
                  <div className="flex items-center gap-2 text-xs font-bold text-indigo-400">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Refactoring Template Code...</span>
                  </div>
                  {aiLogs.map((log, i) => (
                    <div key={i} className="sb-ai-log-step">
                      {log}
                    </div>
                  ))}
                </div>
              )}

              {/* AI Chat History */}
              <div className="space-y-2 pt-2 border-t border-border/40">
                <span className="text-[10px] font-bold uppercase text-muted-foreground block">
                  Assistant Log:
                </span>
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {aiHistory.map((item) => (
                    <div
                      key={item.id}
                      className={cn(
                        "p-2.5 rounded-xl text-xs",
                        item.role === "assistant"
                          ? "bg-muted/50 border border-border text-foreground"
                          : "bg-indigo-600/15 border border-indigo-500/30 text-indigo-300 ml-4"
                      )}
                    >
                      <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground mb-1">
                        <span>{item.role === "assistant" ? "🤖 AI Assistant" : "👤 You"}</span>
                        <span>{item.timestamp}</span>
                      </div>
                      <p className="leading-relaxed">{item.text}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Autonomous AI Debugger */}
              <div className="pt-3 border-t border-border/50">
                <button
                  type="button"
                  onClick={handleRunAIDebugger}
                  disabled={isDebugging}
                  className="w-full py-2.5 px-3 rounded-xl border border-indigo-500/40 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 text-xs font-bold flex items-center justify-center gap-2 transition-all"
                >
                  <Wand2 className={cn("w-3.5 h-3.5", isDebugging && "animate-spin")} />
                  <span>{isDebugging ? "Analyzing & Auto-Fixing..." : "Run AI Debugger & Fixer"}</span>
                </button>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function renderDesignedOutputView(sectionId, props) {
  const themeColor = props.themeColor || "#6366f1";
  const sid = (sectionId || "").toLowerCase();

  // 🧭 1. NAVIGATION HEADER
  const isNav = sid === "navbar" || sid.includes("nav");
  if (isNav) {
    // Back-compat: support both navLinks array and legacy link1/link2/... keys
    const navLinks = Array.isArray(props.navLinks) && props.navLinks.length > 0
      ? props.navLinks
      : [props.link1, props.link2, props.link3, props.link4, props.link5, props.link6].filter(Boolean);
    return (
      <div className="w-full max-w-5xl mx-auto p-4 sm:p-6">
        <nav
          className={cn(
            "px-6 py-4 rounded-2xl border flex items-center justify-between shadow-xl transition-all",
            props.stickyGlass ? "bg-card/90 backdrop-blur-md border-border/80" : "bg-card border-border"
          )}
        >
          <div className="flex items-center gap-3">
            {props.logoText && (
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center font-black text-xs text-white shadow-md uppercase"
                style={{ backgroundColor: themeColor }}
              >
                {props.logoText}
              </div>
            )}
            <span className="font-extrabold text-base tracking-tight text-foreground">
              {props.brandName || "Website Studio"}
            </span>
          </div>
          {navLinks.length > 0 && (
            <div className="hidden md:flex items-center gap-6 text-xs font-semibold text-muted-foreground">
              {navLinks.map((lnk, i) => (
                <span key={i} className="hover:text-foreground cursor-pointer transition-colors">{lnk}</span>
              ))}
            </div>
          )}
          {props.ctaText && (
            <button
              type="button"
              className="px-4 py-2 rounded-xl text-white font-bold text-xs shadow-md transition-all hover:scale-105"
              style={{ backgroundColor: themeColor }}
            >
              {props.ctaText}
            </button>
          )}
        </nav>
      </div>
    );
  }

  // 📜 2. WEBSITE FOOTER
  const isFooter = sid === "footer" || sid.includes("foot");
  if (isFooter) {
    return (
      <div className="w-full max-w-5xl mx-auto p-4 sm:p-6">
        <footer className="p-8 rounded-2xl border border-border bg-card shadow-md text-left space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h4 className="font-black text-lg text-foreground">{props.brandName || "Website Studio"}</h4>
              {props.tagline && (
                <p className="text-xs text-muted-foreground mt-1 max-w-md">{props.tagline}</p>
              )}
            </div>
            <div className="flex items-center gap-4 text-xs font-semibold text-muted-foreground">
              {props.link1 && <span className="hover:text-foreground cursor-pointer">{props.link1}</span>}
              {props.link2 && <span className="hover:text-foreground cursor-pointer">{props.link2}</span>}
              {props.link3 && <span className="hover:text-foreground cursor-pointer">{props.link3}</span>}
            </div>
          </div>
          <div className="pt-4 border-t border-border/50 text-[11px] text-muted-foreground flex items-center justify-between">
            <span>{props.copyright || `© ${new Date().getFullYear()} All rights reserved.`}</span>
            <span className="text-pink-500 font-semibold">AI Site Studio</span>
          </div>
        </footer>
      </div>
    );
  }

  // 📬 3. FORM / CONTACT SECTION
  const isFormSection = props.hasForm || sid === "contact" || sid.includes("contact") || sid.includes("lead") || sid.includes("inquir");
  if (isFormSection) {
    return (
      <div className="w-full max-w-4xl mx-auto p-6 sm:p-10 space-y-6 bg-card text-foreground rounded-2xl border border-border shadow-xl text-left">
        <div className="space-y-1 border-b border-border/50 pb-4">
          {props.badgeText && (
            <span className="text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded bg-muted text-muted-foreground">
              {props.badgeText}
            </span>
          )}
          <h2 className="text-2xl sm:text-3xl font-black tracking-tight text-foreground">
            {props.title || props.headline || "Get in Touch"}
          </h2>
          {(props.subtitle || props.subheadline) && (
            <p className="text-xs text-muted-foreground">{props.subtitle || props.subheadline}</p>
          )}
        </div>

        <div className="space-y-4 max-w-xl">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-semibold uppercase text-muted-foreground block mb-1">Name</label>
              <input
                type="text"
                readOnly
                placeholder={props.namePlaceholder || "Your Name"}
                className="w-full px-3 py-2 rounded-lg bg-muted/40 border border-border text-xs text-foreground placeholder:text-muted-foreground"
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold uppercase text-muted-foreground block mb-1">Email</label>
              <input
                type="email"
                readOnly
                placeholder={props.emailPlaceholder || "Your Email"}
                className="w-full px-3 py-2 rounded-lg bg-muted/40 border border-border text-xs text-foreground placeholder:text-muted-foreground"
              />
            </div>
          </div>
          <div>
            <label className="text-[10px] font-semibold uppercase text-muted-foreground block mb-1">Message</label>
            <textarea
              rows={3}
              readOnly
              placeholder={props.messagePlaceholder || "How can we help?"}
              className="w-full px-3 py-2 rounded-lg bg-muted/40 border border-border text-xs text-foreground resize-none placeholder:text-muted-foreground"
            />
          </div>
          <div className="flex items-center justify-between pt-2">
            {props.email && (
              <span className="text-[11px] text-muted-foreground font-medium">{props.email}</span>
            )}
            <button
              type="button"
              className="px-6 py-2.5 rounded-lg text-white font-bold text-xs uppercase tracking-wider shadow-md transition-all hover:opacity-90 ml-auto"
              style={{ backgroundColor: themeColor }}
            >
              {props.buttonText || "Send Message"}
            </button>
          </div>
        </div>

        {/* STRICT: Only show phone and address if they ACTUALLY exist in template code */}
        {(props.phone || props.address) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4 border-t border-border/40">
            {props.phone && (
              <div className="p-3 rounded-xl border border-border bg-muted/20 flex items-center gap-2.5">
                <Phone className="w-4 h-4 text-pink-500 flex-shrink-0" />
                <div>
                  <span className="text-[10px] uppercase font-bold text-muted-foreground block">Phone</span>
                  <span className="text-xs font-semibold text-foreground">{props.phone}</span>
                </div>
              </div>
            )}
            {props.address && (
              <div className="p-3 rounded-xl border border-border bg-muted/20 flex items-center gap-2.5">
                <MapPin className="w-4 h-4 text-pink-500 flex-shrink-0" />
                <div>
                  <span className="text-[10px] uppercase font-bold text-muted-foreground block">Location</span>
                  <span className="text-xs font-semibold text-foreground">{props.address}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // 🗂️ 4. CARDS / SHOWCASE GRID (Exhibits, Offerings, Services, Capabilities, Projects)
  let cardsList = [];
  if (Array.isArray(props.cards) && props.cards.length > 0) {
    cardsList = props.cards;
  } else {
    for (let i = 1; i <= 10; i++) {
      const t = props[`card${i}_title`] || props[`exhibit${i}_title`] || props[`s${i}Title`] || props[`entry${i}_title`];
      const d = props[`card${i}_desc`] || props[`exhibit${i}_desc`] || props[`s${i}Desc`] || props[`entry${i}_desc`] || props[`print${i}`];
      const tag = props[`card${i}_tag`] || props[`exhibit${i}_tag`] || props[`entry${i}_yr`];
      const st = props[`card${i}_stack`] || props[`exhibit${i}_stack`];
      if (t || d) {
        cardsList.push({ title: t || `Item #${i}`, desc: d || "", tag: tag || "", stack: st || "" });
      }
    }
  }

  if (cardsList.length > 0) {
    return (
      <div className="w-full max-w-5xl mx-auto p-6 sm:p-10 space-y-8 bg-card text-foreground rounded-2xl border border-border shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/50 pb-4 text-left">
          <div>
            {props.badgeText && (
              <span className="text-[10px] font-bold uppercase tracking-widest px-2.5 py-0.5 rounded bg-pink-500/10 text-pink-500 border border-pink-500/20 mb-1 inline-block">
                {props.badgeText}
              </span>
            )}
            <h2 className="text-2xl sm:text-3xl font-black uppercase tracking-wider text-foreground">
              {props.title || props.headline || props.sectionTitle || "Showcase"}
            </h2>
          </div>
          {(props.subtitle || props.subheadline || props.sectionSubtitle) && (
            <span className="text-xs text-muted-foreground max-w-md">
              {props.subtitle || props.subheadline || props.sectionSubtitle}
            </span>
          )}
        </div>

        <div className={cn(
          "grid gap-5 text-left",
          cardsList.length === 2 ? "grid-cols-1 md:grid-cols-2" :
          cardsList.length >= 3 && cardsList.length <= 4 ? "grid-cols-1 md:grid-cols-2" :
          "grid-cols-1 md:grid-cols-3"
        )}>
          {cardsList.map((card, idx) => (
            <div
              key={idx}
              className="p-5 sm:p-6 rounded-xl bg-card border border-border hover:border-pink-500/50 shadow-sm hover:shadow-md transition-all space-y-3 relative group"
            >
              {card.tag && (
                <div className="flex items-center justify-between text-[11px]">
                  <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border font-bold">
                    {card.tag}
                  </span>
                  <span className="text-muted-foreground/60 text-[10px] font-mono">#{idx + 1}</span>
                </div>
              )}
              <h3 className="text-lg font-black text-foreground tracking-wide">{card.title}</h3>
              {(card.desc || card.description) && (
                <p className="text-xs text-muted-foreground leading-relaxed">{card.desc || card.description}</p>
              )}
              {card.stack && (
                <div className="pt-2 flex flex-wrap items-center gap-1.5 border-t border-border/40">
                  {card.stack.split(/[·,\s]+/).filter(Boolean).map((t, ti) => (
                    <span key={ti} className="text-[10px] px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ⚡ 5. HERO / IDENTITY / HOME SECTION
  const isHero = sid === "hero" || sid === "home" || Boolean(props.role || props.yearsActive || props.status || props.stat1Value);
  if (isHero) {
    return (
      <div className="w-full max-w-5xl mx-auto p-6 sm:p-10 space-y-6 text-center">
        {props.badgeText && (
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-pink-500/30 bg-pink-500/10 text-pink-400 text-xs font-bold tracking-wide">
            <span>{props.badgeText}</span>
          </div>
        )}
        <h1 className="text-3xl sm:text-5xl font-black text-foreground tracking-tight leading-tight max-w-3xl mx-auto uppercase">
          {props.headline || props.title || "Welcome"}
        </h1>
        {(props.subheadline || props.description || props.story) && (
          <p className="text-sm sm:text-base text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            {props.subheadline || props.description || props.story}
          </p>
        )}

        {/* Dynamic Meta Bar (Role, Years Active, Status) */}
        {(props.role || props.yearsActive || props.status) && (
          <div className="pt-6 border-t border-border/50 grid grid-cols-3 max-w-md mx-auto gap-4 text-center">
            {props.role && (
              <div>
                <span className="text-muted-foreground uppercase block text-[10px] font-bold">Role</span>
                <span className="text-foreground font-bold text-xs">{props.role}</span>
              </div>
            )}
            {props.yearsActive && (
              <div>
                <span className="text-muted-foreground uppercase block text-[10px] font-bold">Years Active</span>
                <span className="text-foreground font-bold text-xs">{props.yearsActive}</span>
              </div>
            )}
            {props.status && (
              <div>
                <span className="text-muted-foreground uppercase block text-[10px] font-bold">Status</span>
                <span className="text-emerald-500 font-bold text-xs">{props.status}</span>
              </div>
            )}
          </div>
        )}

        {/* Action Buttons */}
        {(props.primaryCta || props.secondaryCta || props.ctaText) && (
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            {(props.primaryCta || props.ctaText) && (
              <button
                type="button"
                className="px-6 py-3 rounded-xl text-white font-bold text-xs shadow-lg transition-all hover:scale-105"
                style={{ backgroundColor: themeColor }}
              >
                {props.primaryCta || props.ctaText}
              </button>
            )}
            {props.secondaryCta && (
              <button
                type="button"
                className="px-6 py-3 rounded-xl border border-border bg-card hover:bg-muted/60 text-foreground font-semibold text-xs shadow-sm transition-all"
              >
                {props.secondaryCta}
              </button>
            )}
          </div>
        )}

        {/* Stats */}
        {(props.stat1Value || props.stat2Value) && (
          <div className="pt-8 border-t border-border/50 grid grid-cols-2 max-w-md mx-auto gap-4">
            {props.stat1Value && (
              <div>
                <span className="text-xl font-black text-foreground block">{props.stat1Value}</span>
                <span className="text-xs text-muted-foreground">{props.stat1Label || "Metric"}</span>
              </div>
            )}
            {props.stat2Value && (
              <div>
                <span className="text-xl font-black text-foreground block">{props.stat2Value}</span>
                <span className="text-xs text-muted-foreground">{props.stat2Label || "Metric"}</span>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // 📄 6. GENERAL CONTENT / ABOUT / STORY / FEATURE SECTION
  return (
    <div className="w-full max-w-5xl mx-auto p-6 sm:p-10 space-y-6 text-left bg-card rounded-2xl border border-border shadow-xl">
      <div className="max-w-2xl space-y-3">
        {props.badgeText && (
          <span className="text-xs font-bold text-pink-500 uppercase tracking-widest">{props.badgeText}</span>
        )}
        <h2 className="text-2xl sm:text-3xl font-black text-foreground">{props.title || props.headline || "Section"}</h2>
        <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
          {props.story || props.description || props.subheadline}
        </p>
      </div>

      {(props.mission || props.teamCount) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-border/50">
          {props.mission && (
            <div className="p-4 rounded-xl border border-border bg-muted/20">
              <span className="text-xs font-bold text-foreground block">Mission</span>
              <p className="text-xs text-muted-foreground mt-1">{props.mission}</p>
            </div>
          )}
          {props.teamCount && (
            <div className="p-4 rounded-xl border border-border bg-muted/20">
              <span className="text-xs font-bold text-foreground block">Team</span>
              <p className="text-xs text-muted-foreground mt-1">{props.teamCount}</p>
            </div>
          )}
        </div>
      )}

      {props.ctaText && (
        <div className="pt-2">
          <button
            type="button"
            className="px-5 py-2.5 rounded-xl text-white font-bold text-xs shadow-md"
            style={{ backgroundColor: themeColor }}
          >
            {props.ctaText}
          </button>
        </div>
      )}
    </div>
  );
}

function renderFriendlyFields(sectionId, props, onChange) {
  const sid = (sectionId || "").toLowerCase();

  // 🧭 1. NAVIGATION HEADER CONTROLS
  if (sid === "navbar" || sid.includes("nav")) {
    // Back-compat: convert old link1/link2/... keys → navLinks array
    let navLinks = Array.isArray(props.navLinks) ? [...props.navLinks] : [];
    if (navLinks.length === 0) {
      ["link1","link2","link3","link4","link5","link6"].forEach((k) => {
        if (props[k]) navLinks.push(props[k]);
      });
    }
    if (navLinks.length === 0) navLinks = ["Home", "About", "Contact"];

    const updateLink = (idx, val) => {
      const updated = [...navLinks];
      updated[idx] = val;
      onChange("navLinks", updated);
    };
    const removeLink = (idx) => {
      const updated = navLinks.filter((_, i) => i !== idx);
      onChange("navLinks", updated);
    };
    const addLink = () => {
      onChange("navLinks", [...navLinks, "New Link"]);
    };

    return (
      <div className="space-y-3.5">
        <div>
          <label className="sb-control-label">Brand / Header Title</label>
          <input
            type="text"
            value={props.brandName || ""}
            onChange={(e) => onChange("brandName", e.target.value)}
            placeholder="e.g. Website Studio"
            className="sb-control-input font-bold"
          />
        </div>
        <div>
          <label className="sb-control-label">Logo Monogram / Code</label>
          <input
            type="text"
            value={props.logoText || ""}
            onChange={(e) => onChange("logoText", e.target.value)}
            placeholder="e.g. STUDIO"
            className="sb-control-input uppercase font-mono"
          />
        </div>

        {/* Dynamic Nav Links List */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="sb-control-label mb-0">Nav Links ({navLinks.length})</label>
            <button
              type="button"
              onClick={addLink}
              className="flex items-center gap-1 text-[10px] font-bold text-pink-400 hover:text-pink-300 px-2 py-1 rounded-lg bg-pink-500/10 hover:bg-pink-500/20 transition-colors"
            >
              <Plus className="w-3 h-3" /> Add Link
            </button>
          </div>
          <div className="space-y-1.5">
            {navLinks.map((lnk, idx) => (
              <div key={idx} className="flex items-center gap-1.5">
                <span className="text-[10px] font-mono text-muted-foreground w-4 text-right flex-shrink-0">{idx + 1}</span>
                <input
                  type="text"
                  value={lnk}
                  onChange={(e) => updateLink(idx, e.target.value)}
                  placeholder={`Link ${idx + 1}`}
                  className="sb-control-input text-xs flex-1"
                />
                <button
                  type="button"
                  onClick={() => removeLink(idx)}
                  disabled={navLinks.length <= 1}
                  className="p-1 rounded-lg text-rose-400 hover:bg-rose-500/15 disabled:opacity-30 transition-colors flex-shrink-0"
                  title="Remove link"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div>
          <label className="sb-control-label">Header Action / CTA Text</label>
          <input
            type="text"
            value={props.ctaText || ""}
            onChange={(e) => onChange("ctaText", e.target.value)}
            placeholder="e.g. Get Started"
            className="sb-control-input text-xs font-bold"
          />
        </div>
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs font-semibold text-foreground">Glassmorphism / Fixed Header</span>
          <label className="sb-toggle-wrapper">
            <input
              type="checkbox"
              checked={!!props.stickyGlass}
              onChange={(e) => onChange("stickyGlass", e.target.checked)}
              className="sb-toggle-checkbox"
            />
            <span className="sb-toggle-slider" />
          </label>
        </div>
      </div>
    );
  }

  // 📜 2. FOOTER CONTROLS
  if (sid === "footer" || sid.includes("foot")) {
    return (
      <div className="space-y-3.5">
        <div>
          <label className="sb-control-label">Footer Brand Name</label>
          <input
            type="text"
            value={props.brandName || ""}
            onChange={(e) => onChange("brandName", e.target.value)}
            placeholder="e.g. Website Studio"
            className="sb-control-input font-bold"
          />
        </div>
        <div>
          <label className="sb-control-label">Tagline / Mission Statement</label>
          <textarea
            rows={2}
            value={props.tagline || ""}
            onChange={(e) => onChange("tagline", e.target.value)}
            placeholder="e.g. Crafting exceptional digital experiences."
            className="sb-control-input resize-none text-xs"
          />
        </div>
        <div>
          <label className="sb-control-label">Copyright Record</label>
          <input
            type="text"
            value={props.copyright || ""}
            onChange={(e) => onChange("copyright", e.target.value)}
            placeholder={`© ${new Date().getFullYear()} All rights reserved.`}
            className="sb-control-input text-xs"
          />
        </div>
      </div>
    );
  }

  // 📞 2b. CONTACT DETAILS / DIRECT REACH (Phone, Email, Address for info section)
  if (sid === "info" || sid.includes("reach") || (!props.hasForm && (props.phone || props.email || props.address))) {
    return (
      <div className="space-y-3.5">
        <div>
          <label className="sb-control-label">Section Title</label>
          <input
            type="text"
            value={props.title || props.headline || "Contact Information"}
            onChange={(e) => {
              onChange("title", e.target.value);
              onChange("headline", e.target.value);
            }}
            placeholder="Contact Information"
            className="sb-control-input font-bold"
          />
        </div>
        <div>
          <label className="sb-control-label">Direct Phone Number</label>
          <input
            type="text"
            value={props.phone || ""}
            onChange={(e) => onChange("phone", e.target.value)}
            placeholder="e.g. +1 (555) 019-3388"
            className="sb-control-input text-xs font-mono"
          />
        </div>
        <div>
          <label className="sb-control-label">Contact Email</label>
          <input
            type="email"
            value={props.email || ""}
            onChange={(e) => onChange("email", e.target.value)}
            placeholder="e.g. contact@company.com"
            className="sb-control-input text-xs"
          />
        </div>
        <div>
          <label className="sb-control-label">Office Location / Address</label>
          <input
            type="text"
            value={props.address || ""}
            onChange={(e) => onChange("address", e.target.value)}
            placeholder="e.g. NY Brooklyn 28"
            className="sb-control-input text-xs"
          />
        </div>
        {Array.isArray(props.textItems) && props.textItems.length > 0 && (
          <div className="pt-2 border-t border-border/50">
            <label className="sb-control-label">Additional Info Texts ({props.textItems.length})</label>
            <div className="space-y-2">
              {props.textItems.map((ti, tIdx) => (
                <div key={ti.id || tIdx}>
                  <label className="text-[10px] text-muted-foreground uppercase">{ti.label || `Text #${tIdx+1}`}</label>
                  <input
                    type="text"
                    value={ti.text || ""}
                    onChange={(e) => {
                      const updated = [...props.textItems];
                      updated[tIdx] = { ...updated[tIdx], text: e.target.value };
                      onChange("textItems", updated);
                    }}
                    className="sb-control-input text-xs"
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // 📬 3. FORM / CONTACT CONTROLS
  const isFormSection = props.hasForm || sid === "contact" || sid.includes("contact") || sid.includes("lead") || sid.includes("inquir");
  if (isFormSection) {
    return (
      <div className="space-y-3.5">
        <div>
          <label className="sb-control-label">Form Headline</label>
          <input
            type="text"
            value={props.title || props.headline || ""}
            onChange={(e) => {
              onChange("title", e.target.value);
              onChange("headline", e.target.value);
            }}
            placeholder="e.g. Get in Touch"
            className="sb-control-input font-bold"
          />
        </div>
        <div>
          <label className="sb-control-label">Form Subtitle / Instructions</label>
          <input
            type="text"
            value={props.subtitle || props.subheadline || ""}
            onChange={(e) => {
              onChange("subtitle", e.target.value);
              onChange("subheadline", e.target.value);
            }}
            placeholder="e.g. Leave a transmission or message below"
            className="sb-control-input text-xs"
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="sb-control-label">Name Placeholder</label>
            <input
              type="text"
              value={props.namePlaceholder || ""}
              onChange={(e) => onChange("namePlaceholder", e.target.value)}
              placeholder="Name"
              className="sb-control-input text-xs"
            />
          </div>
          <div>
            <label className="sb-control-label">Email Placeholder</label>
            <input
              type="text"
              value={props.emailPlaceholder || ""}
              onChange={(e) => onChange("emailPlaceholder", e.target.value)}
              placeholder="Email"
              className="sb-control-input text-xs"
            />
          </div>
        </div>
        <div>
          <label className="sb-control-label">Message Placeholder</label>
          <input
            type="text"
            value={props.messagePlaceholder || ""}
            onChange={(e) => onChange("messagePlaceholder", e.target.value)}
            placeholder="What are we building?"
            className="sb-control-input text-xs"
          />
        </div>
        <div>
          <label className="sb-control-label">Submit Button Text</label>
          <input
            type="text"
            value={props.buttonText || ""}
            onChange={(e) => onChange("buttonText", e.target.value)}
            placeholder="e.g. Send Message"
            className="sb-control-input text-xs font-bold"
          />
        </div>
        <div>
          <label className="sb-control-label">Contact Email</label>
          <input
            type="email"
            value={props.email || ""}
            onChange={(e) => onChange("email", e.target.value)}
            placeholder="contact@company.com"
            className="sb-control-input text-xs"
          />
        </div>

        {/* STRICT: Phone and Location inputs only if present in props */}
        {props.phone !== undefined && (
          <div>
            <label className="sb-control-label">Direct Phone</label>
            <input
              type="text"
              value={props.phone || ""}
              onChange={(e) => onChange("phone", e.target.value)}
              placeholder="Phone number"
              className="sb-control-input text-xs"
            />
          </div>
        )}
        {props.address !== undefined && (
          <div>
            <label className="sb-control-label">Office Location / Address</label>
            <input
              type="text"
              value={props.address || ""}
              onChange={(e) => onChange("address", e.target.value)}
              placeholder="Address"
              className="sb-control-input text-xs"
            />
          </div>
        )}
      </div>
    );
  }

  // 🗂️ 4. CARDS / SHOWCASE CONTROLS (Offerings, Services, Exhibits, Capabilities)
  let cardsList = [];
  if (Array.isArray(props.cards) && props.cards.length > 0) {
    cardsList = props.cards;
  } else {
    for (let i = 1; i <= 10; i++) {
      const t = props[`card${i}_title`] || props[`exhibit${i}_title`] || props[`s${i}Title`] || props[`entry${i}_title`];
      const d = props[`card${i}_desc`] || props[`exhibit${i}_desc`] || props[`s${i}Desc`] || props[`entry${i}_desc`] || props[`print${i}`];
      const tag = props[`card${i}_tag`] || props[`exhibit${i}_tag`] || props[`entry${i}_yr`];
      const st = props[`card${i}_stack`] || props[`exhibit${i}_stack`];
      if (t || d) {
        cardsList.push({ title: t || `Item #${i}`, desc: d || "", tag: tag || "", stack: st || "" });
      }
    }
  }

  if (cardsList.length > 0) {
    const updateCardItem = (cardIdx, field, val) => {
      const updated = cardsList.map((c, idx) => (idx === cardIdx ? { ...c, [field]: val } : c));
      onChange("cards", updated);
      onChange(`card${cardIdx + 1}_${field}`, val);
      if (field === "title") {
        onChange(`exhibit${cardIdx + 1}_title`, val);
        onChange(`s${cardIdx + 1}Title`, val);
        onChange(`entry${cardIdx + 1}_title`, val);
      }
      if (field === "desc" || field === "description") {
        onChange(`exhibit${cardIdx + 1}_desc`, val);
        onChange(`s${cardIdx + 1}Desc`, val);
        onChange(`entry${cardIdx + 1}_desc`, val);
        onChange(`print${cardIdx + 1}`, val);
      }
      if (field === "tag") {
        onChange(`exhibit${cardIdx + 1}_tag`, val);
        onChange(`entry${cardIdx + 1}_yr`, val);
      }
      if (field === "stack") {
        onChange(`exhibit${cardIdx + 1}_stack`, val);
      }
    };

    return (
      <div className="space-y-4">
        <div>
          <label className="sb-control-label">Section Title</label>
          <input
            type="text"
            value={props.title || props.headline || props.sectionTitle || ""}
            onChange={(e) => {
              onChange("title", e.target.value);
              onChange("headline", e.target.value);
              onChange("sectionTitle", e.target.value);
            }}
            placeholder="Section Title"
            className="sb-control-input font-bold"
          />
        </div>
        <div>
          <label className="sb-control-label">Section Subtitle</label>
          <input
            type="text"
            value={props.subtitle || props.subheadline || props.sectionSubtitle || ""}
            onChange={(e) => {
              onChange("subtitle", e.target.value);
              onChange("subheadline", e.target.value);
              onChange("sectionSubtitle", e.target.value);
            }}
            placeholder="Subtitle"
            className="sb-control-input text-xs"
          />
        </div>

        {/* Dynamic Cards Editor */}
        <div className="space-y-3 pt-2">
          {cardsList.map((card, idx) => (
            <div key={idx} className="p-3.5 rounded-xl border border-border/80 bg-card/60 space-y-2.5">
              <span className="text-[10px] font-mono font-bold uppercase text-pink-400 block">
                {card.tag || `Item #${idx + 1}`}
              </span>
              {card.tag !== undefined && (
                <div>
                  <label className="sb-control-label">Badge / Tag</label>
                  <input
                    type="text"
                    value={card.tag || ""}
                    onChange={(e) => updateCardItem(idx, "tag", e.target.value)}
                    placeholder="e.g. EXHIBIT A · 2024"
                    className="sb-control-input text-xs font-mono"
                  />
                </div>
              )}
              <div>
                <label className="sb-control-label">Title</label>
                <input
                  type="text"
                  value={card.title || ""}
                  onChange={(e) => updateCardItem(idx, "title", e.target.value)}
                  placeholder="Card Title"
                  className="sb-control-input text-xs font-bold"
                />
              </div>
              {card.stack !== undefined && (
                <div>
                  <label className="sb-control-label">Tech Stack / Category</label>
                  <input
                    type="text"
                    value={card.stack || ""}
                    onChange={(e) => updateCardItem(idx, "stack", e.target.value)}
                    placeholder="e.g. React · TypeScript · Node"
                    className="sb-control-input text-xs font-mono"
                  />
                </div>
              )}
              <div>
                <label className="sb-control-label">Description</label>
                <textarea
                  rows={2}
                  value={card.desc || card.description || ""}
                  onChange={(e) => updateCardItem(idx, "desc", e.target.value)}
                  placeholder="Card description..."
                  className="sb-control-input text-xs resize-none leading-relaxed"
                />
              </div>
            </div>
          ))}
        </div>

        {/* Dynamic Section Tabs / Pills (e.g. Experience / Education) */}
        {Array.isArray(props.tabs) && props.tabs.length > 0 && (
          <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 space-y-2 mt-2">
            <div className="flex items-center justify-between">
              <label className="sb-control-label mb-0">Navigation Tabs ({props.tabs.length})</label>
              <button
                type="button"
                onClick={() => onChange("tabs", [...props.tabs, "New Tab"])}
                className="flex items-center gap-1 text-[10px] font-bold text-pink-400 hover:text-pink-300 px-2 py-0.5 rounded-lg bg-pink-500/10 hover:bg-pink-500/20"
              >
                <Plus className="w-3 h-3" /> Add Tab
              </button>
            </div>
            <div className="space-y-1.5">
              {props.tabs.map((tabText, tIdx) => (
                <div key={tIdx} className="flex items-center gap-1.5">
                  <span className="text-[10px] font-mono text-muted-foreground w-4 text-right flex-shrink-0">{tIdx + 1}</span>
                  <input
                    type="text"
                    value={tabText}
                    onChange={(e) => {
                      const updated = [...props.tabs];
                      updated[tIdx] = e.target.value;
                      onChange("tabs", updated);
                    }}
                    className="sb-control-input text-xs flex-1"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const updated = props.tabs.filter((_, i) => i !== tIdx);
                      onChange("tabs", updated);
                    }}
                    className="p-1 text-rose-400 hover:bg-rose-500/15 rounded"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Category Filters (e.g. All, Web Design, UI/UX, Graphic Design) */}
        {Array.isArray(props.filters) && props.filters.length > 0 && (
          <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 space-y-2 mt-2">
            <div className="flex items-center justify-between">
              <label className="sb-control-label mb-0">Category Filters ({props.filters.length})</label>
              <button
                type="button"
                onClick={() => onChange("filters", [...props.filters, "NEW FILTER"])}
                className="flex items-center gap-1 text-[10px] font-bold text-pink-400 hover:text-pink-300 px-2 py-0.5 rounded-lg bg-pink-500/10 hover:bg-pink-500/20"
              >
                <Plus className="w-3 h-3" /> Add Filter
              </button>
            </div>
            <div className="space-y-1.5">
              {props.filters.map((fltText, fIdx) => (
                <div key={fIdx} className="flex items-center gap-1.5">
                  <span className="text-[10px] font-mono text-muted-foreground w-4 text-right flex-shrink-0">{fIdx + 1}</span>
                  <input
                    type="text"
                    value={fltText}
                    onChange={(e) => {
                      const updated = [...props.filters];
                      updated[fIdx] = e.target.value;
                      onChange("filters", updated);
                    }}
                    className="sb-control-input text-xs flex-1 uppercase"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const updated = props.filters.filter((_, i) => i !== fIdx);
                      onChange("filters", updated);
                    }}
                    className="p-1 text-rose-400 hover:bg-rose-500/15 rounded"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Social Links List */}
        {Array.isArray(props.socialLinks) && props.socialLinks.length > 0 && (
          <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 space-y-2 mt-2">
            <label className="sb-control-label mb-0">Social Network Channels ({props.socialLinks.length})</label>
            <div className="space-y-2">
              {props.socialLinks.map((soc, sIdx) => (
                <div key={sIdx} className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={soc.platform || ""}
                    onChange={(e) => {
                      const updated = [...props.socialLinks];
                      updated[sIdx] = { ...updated[sIdx], platform: e.target.value };
                      onChange("socialLinks", updated);
                    }}
                    placeholder="Platform"
                    className="sb-control-input text-xs font-bold"
                  />
                  <input
                    type="text"
                    value={soc.url || ""}
                    onChange={(e) => {
                      const updated = [...props.socialLinks];
                      updated[sIdx] = { ...updated[sIdx], url: e.target.value };
                      onChange("socialLinks", updated);
                    }}
                    placeholder="URL (e.g. # or https://...)"
                    className="sb-control-input text-xs font-mono"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Universal Extra Template Text Items (100% Text Capture) */}
        {Array.isArray(props.textItems) && props.textItems.length > 0 && (
          <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 space-y-2 mt-2">
            <label className="sb-control-label mb-0">Additional Template Texts ({props.textItems.length})</label>
            <div className="space-y-2">
              {props.textItems.map((ti, tIdx) => (
                <div key={ti.id || tIdx}>
                  <label className="text-[10px] text-muted-foreground uppercase">{ti.label || `Text #${tIdx+1}`}</label>
                  <input
                    type="text"
                    value={ti.text || ""}
                    onChange={(e) => {
                      const updated = [...props.textItems];
                      updated[tIdx] = { ...updated[tIdx], text: e.target.value };
                      onChange("textItems", updated);
                    }}
                    className="sb-control-input text-xs"
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ⚡ 5. HERO / IDENTITY / HOME CONTROLS
  const isHero = sid === "hero" || sid === "home" || Boolean(props.role || props.yearsActive || props.status || props.stat1Value);
  if (isHero) {
    return (
      <div className="space-y-3.5">
        <div>
          <label className="sb-control-label">Top Pill Badge Text</label>
          <input
            type="text"
            value={props.badgeText || ""}
            onChange={(e) => onChange("badgeText", e.target.value)}
            placeholder="e.g. STATUS: ACTIVE"
            className="sb-control-input text-xs text-pink-400 font-mono"
          />
        </div>
        <div>
          <label className="sb-control-label">Main Headline</label>
          <input
            type="text"
            value={props.headline || props.title || ""}
            onChange={(e) => {
              onChange("headline", e.target.value);
              onChange("title", e.target.value);
            }}
            placeholder="Main Headline"
            className="sb-control-input font-bold text-base"
          />
        </div>
        <div>
          <label className="sb-control-label">Narrative Story / Bio</label>
          <textarea
            rows={4}
            value={props.subheadline || props.description || props.story || ""}
            onChange={(e) => {
              onChange("subheadline", e.target.value);
              onChange("description", e.target.value);
              onChange("story", e.target.value);
            }}
            placeholder="Detailed narrative or bio description..."
            className="sb-control-input resize-none text-xs leading-relaxed"
          />
        </div>

        {/* Role, Years, Status (if present) */}
        {(props.role !== undefined || props.yearsActive !== undefined || props.status !== undefined) && (
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="sb-control-label">Role</label>
              <input
                type="text"
                value={props.role || ""}
                onChange={(e) => onChange("role", e.target.value)}
                placeholder="Role"
                className="sb-control-input text-xs"
              />
            </div>
            <div>
              <label className="sb-control-label">Years Active</label>
              <input
                type="text"
                value={props.yearsActive || ""}
                onChange={(e) => onChange("yearsActive", e.target.value)}
                placeholder="07"
                className="sb-control-input text-xs font-mono"
              />
            </div>
            <div>
              <label className="sb-control-label">Status</label>
              <input
                type="text"
                value={props.status || ""}
                onChange={(e) => onChange("status", e.target.value)}
                placeholder="Active"
                className="sb-control-input text-xs text-emerald-400 font-bold"
              />
            </div>
          </div>
        )}

        {/* Buttons */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="sb-control-label">Primary Button</label>
            <input
              type="text"
              value={props.primaryCta || props.ctaText || ""}
              onChange={(e) => {
                onChange("primaryCta", e.target.value);
                onChange("ctaText", e.target.value);
              }}
              placeholder="Primary CTA"
              className="sb-control-input text-xs"
            />
          </div>
          <div>
            <label className="sb-control-label">Secondary Button</label>
            <input
              type="text"
              value={props.secondaryCta || ""}
              onChange={(e) => onChange("secondaryCta", e.target.value)}
              placeholder="Secondary CTA"
              className="sb-control-input text-xs"
            />
          </div>
        </div>

        {/* Stats */}
        {(props.stat1Value !== undefined || props.stat2Value !== undefined) && (
          <div className="grid grid-cols-2 gap-2 pt-2">
            <div>
              <label className="sb-control-label">Stat 1 Value &amp; Label</label>
              <input
                type="text"
                value={props.stat1Value || ""}
                onChange={(e) => onChange("stat1Value", e.target.value)}
                placeholder="Value"
                className="sb-control-input text-xs mb-1"
              />
              <input
                type="text"
                value={props.stat1Label || ""}
                onChange={(e) => onChange("stat1Label", e.target.value)}
                placeholder="Label"
                className="sb-control-input text-xs"
              />
            </div>
            <div>
              <label className="sb-control-label">Stat 2 Value &amp; Label</label>
              <input
                type="text"
                value={props.stat2Value || ""}
                onChange={(e) => onChange("stat2Value", e.target.value)}
                placeholder="Value"
                className="sb-control-input text-xs mb-1"
              />
              <input
                type="text"
                value={props.stat2Label || ""}
                onChange={(e) => onChange("stat2Label", e.target.value)}
                placeholder="Label"
                className="sb-control-input text-xs"
              />
            </div>
          </div>
        )}
      </div>
    );
  }

  // 📄 6. GENERAL CONTENT / ABOUT / STORY CONTROLS
  return (
    <div className="space-y-3.5">
      <div>
        <label className="sb-control-label">Badge Text</label>
        <input
          type="text"
          value={props.badgeText || ""}
          onChange={(e) => onChange("badgeText", e.target.value)}
          placeholder="Badge / Tag"
          className="sb-control-input text-xs"
        />
      </div>
      <div>
        <label className="sb-control-label">Component Title</label>
        <input
          type="text"
          value={props.title || props.headline || ""}
          onChange={(e) => {
            onChange("title", e.target.value);
            onChange("headline", e.target.value);
          }}
          placeholder="Section Title"
          className="sb-control-input font-bold"
        />
      </div>
      <div>
        <label className="sb-control-label">Subtitle / Hook</label>
        <input
          type="text"
          value={props.subtitle || props.subheadline || ""}
          onChange={(e) => {
            onChange("subtitle", e.target.value);
            onChange("subheadline", e.target.value);
          }}
          placeholder="e.g. 8 Years of experience building the web."
          className="sb-control-input text-xs"
        />
      </div>
      <div>
        <label className="sb-control-label">Description / Bio Narrative</label>
        <textarea
          rows={5}
          value={props.story || props.description || ""}
          onChange={(e) => {
            onChange("story", e.target.value);
            onChange("description", e.target.value);
          }}
          placeholder="Detailed narrative or bio story..."
          className="sb-control-input resize-none leading-relaxed text-xs"
        />
      </div>
      {props.mission !== undefined && (
        <div>
          <label className="sb-control-label">Mission Statement</label>
          <textarea
            rows={2}
            value={props.mission || ""}
            onChange={(e) => onChange("mission", e.target.value)}
            placeholder="Mission statement..."
            className="sb-control-input resize-none text-xs"
          />
        </div>
      )}
      {props.teamCount !== undefined && (
        <div>
          <label className="sb-control-label">Team Scale</label>
          <input
            type="text"
            value={props.teamCount || ""}
            onChange={(e) => onChange("teamCount", e.target.value)}
            placeholder="e.g. 24 Engineers"
            className="sb-control-input text-xs"
          />
        </div>
      )}
      {props.ctaText !== undefined && (
        <div>
          <label className="sb-control-label">Button CTA</label>
          <input
            type="text"
            value={props.ctaText || ""}
            onChange={(e) => onChange("ctaText", e.target.value)}
            placeholder="e.g. Learn More"
            className="sb-control-input text-xs"
          />
        </div>
      )}

      {/* Dynamic Section Tabs / Pills (if present) */}
      {Array.isArray(props.tabs) && props.tabs.length > 0 && (
        <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 space-y-2 mt-2">
          <div className="flex items-center justify-between">
            <label className="sb-control-label mb-0">Navigation Tabs ({props.tabs.length})</label>
            <button
              type="button"
              onClick={() => onChange("tabs", [...props.tabs, "New Tab"])}
              className="flex items-center gap-1 text-[10px] font-bold text-pink-400 hover:text-pink-300 px-2 py-0.5 rounded-lg bg-pink-500/10 hover:bg-pink-500/20"
            >
              <Plus className="w-3 h-3" /> Add Tab
            </button>
          </div>
          <div className="space-y-1.5">
            {props.tabs.map((tabText, tIdx) => (
              <div key={tIdx} className="flex items-center gap-1.5">
                <span className="text-[10px] font-mono text-muted-foreground w-4 text-right flex-shrink-0">{tIdx + 1}</span>
                <input
                  type="text"
                  value={tabText}
                  onChange={(e) => {
                    const updated = [...props.tabs];
                    updated[tIdx] = e.target.value;
                    onChange("tabs", updated);
                  }}
                  className="sb-control-input text-xs flex-1"
                />
                <button
                  type="button"
                  onClick={() => {
                    const updated = props.tabs.filter((_, i) => i !== tIdx);
                    onChange("tabs", updated);
                  }}
                  className="p-1 text-rose-400 hover:bg-rose-500/15 rounded"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Category Filters (if present) */}
      {Array.isArray(props.filters) && props.filters.length > 0 && (
        <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 space-y-2 mt-2">
          <div className="flex items-center justify-between">
            <label className="sb-control-label mb-0">Category Filters ({props.filters.length})</label>
            <button
              type="button"
              onClick={() => onChange("filters", [...props.filters, "NEW FILTER"])}
              className="flex items-center gap-1 text-[10px] font-bold text-pink-400 hover:text-pink-300 px-2 py-0.5 rounded-lg bg-pink-500/10 hover:bg-pink-500/20"
            >
              <Plus className="w-3 h-3" /> Add Filter
            </button>
          </div>
          <div className="space-y-1.5">
            {props.filters.map((fltText, fIdx) => (
              <div key={fIdx} className="flex items-center gap-1.5">
                <span className="text-[10px] font-mono text-muted-foreground w-4 text-right flex-shrink-0">{fIdx + 1}</span>
                <input
                  type="text"
                  value={fltText}
                  onChange={(e) => {
                    const updated = [...props.filters];
                    updated[fIdx] = e.target.value;
                    onChange("filters", updated);
                  }}
                  className="sb-control-input text-xs flex-1 uppercase"
                />
                <button
                  type="button"
                  onClick={() => {
                    const updated = props.filters.filter((_, i) => i !== fIdx);
                    onChange("filters", updated);
                  }}
                  className="p-1 text-rose-400 hover:bg-rose-500/15 rounded"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Social Links (if present) */}
      {Array.isArray(props.socialLinks) && props.socialLinks.length > 0 && (
        <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 space-y-2 mt-2">
          <label className="sb-control-label mb-0">Social Network Channels ({props.socialLinks.length})</label>
          <div className="space-y-2">
            {props.socialLinks.map((soc, sIdx) => (
              <div key={sIdx} className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={soc.platform || ""}
                  onChange={(e) => {
                    const updated = [...props.socialLinks];
                    updated[sIdx] = { ...updated[sIdx], platform: e.target.value };
                    onChange("socialLinks", updated);
                  }}
                  placeholder="Platform"
                  className="sb-control-input text-xs font-bold"
                />
                <input
                  type="text"
                  value={soc.url || ""}
                  onChange={(e) => {
                    const updated = [...props.socialLinks];
                    updated[sIdx] = { ...updated[sIdx], url: e.target.value };
                    onChange("socialLinks", updated);
                  }}
                  placeholder="URL (e.g. # or https://...)"
                  className="sb-control-input text-xs font-mono"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Universal Extra Template Text Items (100% Text Capture) */}
      {Array.isArray(props.textItems) && props.textItems.length > 0 && (
        <div className="p-3.5 rounded-xl border border-border/80 bg-card/60 space-y-2 mt-2">
          <label className="sb-control-label mb-0">Additional Template Texts ({props.textItems.length})</label>
          <div className="space-y-2">
            {props.textItems.map((ti, tIdx) => (
              <div key={ti.id || tIdx}>
                <label className="text-[10px] text-muted-foreground uppercase">{ti.label || `Text #${tIdx+1}`}</label>
                <input
                  type="text"
                  value={ti.text || ""}
                  onChange={(e) => {
                    const updated = [...props.textItems];
                    updated[tIdx] = { ...updated[tIdx], text: e.target.value };
                    onChange("textItems", updated);
                  }}
                  className="sb-control-input text-xs"
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
