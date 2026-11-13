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

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import {
  Image, UploadCloud, Palette, Paintbrush,
  Monitor, Laptop, Tablet, Smartphone, Sun, Moon, Grid,
  RefreshCw, Zap, Layers, FileText, Sparkles, Star, Mail,
  Shield, AlertCircle, Edit3, Trash2, Eraser, Plus, Check,
  Copy, RotateCcw, ArrowLeft, Sliders, Globe, Bot, Send,
  CheckCircle2, Play, Code, Search, X, Wand2, ArrowUpRight,
  ChevronRight, ChevronLeft, MoreVertical, Menu, Eye, Phone, MapPin, Clock, ShoppingBag, ShoppingCart, Share2, Upload
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useCartStore } from "@/store";
import { useAuthStore } from "@/store/authStore";
import { getFallbackTemplate } from "@/data/popularTemplatesData";
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

    let primaryColor = "#b5804f";
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

export const dispatchLiveIframeColor = (cleanHex) => {
  try {
    if (!cleanHex || typeof cleanHex !== "string") return;
    const clean = cleanHex.replace('#', '');
    const hex = clean.length === 3 ? clean.split('').map((c) => c + c).join('') : clean;
    const r = parseInt(hex.substring(0, 2), 16) || 79;
    const g = parseInt(hex.substring(2, 4), 16) || 70;
    const b = parseInt(hex.substring(4, 6), 16) || 229;
    const rH = Math.max(0, Math.floor(r * 0.82));
    const gH = Math.max(0, Math.floor(g * 0.82));
    const bH = Math.max(0, Math.floor(b * 0.82));
    const hoverColor = '#' + [rH, gH, bH].map((x) => x.toString(16).padStart(2, '0')).join('');
    const fullHex = `#${hex.toUpperCase()}`;
    const gradCss = `linear-gradient(135deg, ${fullHex} 0%, ${hoverColor} 100%)`;
    const gradRevCss = `linear-gradient(135deg, ${hoverColor} 0%, ${fullHex} 100%)`;

    const iframes = document.querySelectorAll("iframe");
    iframes.forEach((frame) => {
      // 1. PostMessage to iframe sandbox listener
      try {
        frame.contentWindow?.postMessage(
          { type: "UPDATE_THEME_COLOR", color: fullHex, hoverColor },
          "*"
        );
      } catch (_) {}

      // 2. Direct DOM override if accessible
      try {
        if (frame.contentDocument) {
          const doc = frame.contentDocument;
          let styleTag = doc.getElementById("studio-live-theme-override");
          if (!styleTag) {
            styleTag = doc.createElement("style");
            styleTag.id = "studio-live-theme-override";
            doc.head?.appendChild(styleTag);
          }
          styleTag.textContent = `
            :root, :root[data-theme="light"], :root[data-theme="dark"], html, body {
              --c-primary: ${fullHex} !important;
              --c-primary-hover: ${hoverColor} !important;
              --color-primary: ${fullHex} !important;
              --color-primary-dark: ${hoverColor} !important;
              --color-primary-hover: ${hoverColor} !important;
              --primary: ${fullHex} !important;
              --primary-color: ${fullHex} !important;
              --primary-hover: ${hoverColor} !important;
              --primary-dark: ${hoverColor} !important;
              --accent: ${fullHex} !important;
              --accent-color: ${fullHex} !important;
              --accent-primary: ${fullHex} !important;
              --accent-hover: ${hoverColor} !important;
              --color-accent: ${fullHex} !important;
              --theme-color: ${fullHex} !important;
              --brand: ${fullHex} !important;
              --brand-color: ${fullHex} !important;
              --cta-bg: ${fullHex} !important;
              --accent-gold: ${fullHex} !important;
              --accent-gold-hover: ${hoverColor} !important;
              --accent-amber: ${fullHex} !important;
              --blue: ${fullHex} !important;
              --violet: ${hoverColor} !important;
              --cyan: ${fullHex} !important;
              --green: ${fullHex} !important;
              --red: ${fullHex} !important;
              --red-dim: ${hoverColor} !important;
              --grad: ${gradCss} !important;
              --grad-r: ${gradRevCss} !important;
              --glow-blue: rgba(${r}, ${g}, ${b}, 0.25) !important;
              --glow-vio: rgba(${rH}, ${gH}, ${bH}, 0.2) !important;
              --border2: rgba(${r}, ${g}, ${b}, 0.3) !important;
            }
            .btn-primary, .nav-cta, .hero-cta, .btn, .button, .primary-btn, a.btn-primary, button.btn-primary, [data-theme-color="true"], [class*="btn-primary"], [class*="nav-cta"] {
              background: ${gradCss} !important;
              background-color: ${fullHex} !important;
              background-image: ${gradCss} !important;
              border-color: ${fullHex} !important;
              color: #ffffff !important;
              box-shadow: 0 4px 18px rgba(${r}, ${g}, ${b}, 0.35) !important;
            }
            .btn-primary:hover, .nav-cta:hover, .hero-cta:hover, .primary-btn:hover {
              background: ${gradRevCss} !important;
              background-color: ${hoverColor} !important;
              background-image: ${gradRevCss} !important;
              border-color: ${hoverColor} !important;
              color: #ffffff !important;
            }
            .nav-logo, h1 .accent, .accent, .accent-text, [class*="accent-text"], .gradient-text, .text-gradient, a.brand-logo span, .hero-subtitle span {
              background: ${gradCss} !important;
              background-clip: text !important;
              -webkit-background-clip: text !important;
              -webkit-text-fill-color: transparent !important;
            }
            .text-primary, [class*="text-primary"], .nav-links a:hover, .brand-text, .gold-text {
              color: ${fullHex} !important;
            }
            .pulse, .status-dot {
              background: ${fullHex} !important;
              box-shadow: 0 0 0 0 rgba(${r}, ${g}, ${b}, 0.5) !important;
            }
            #crosshair, .tape-stripe { border-color: ${fullHex} !important; }
            #crosshair::before, #crosshair::after { background: ${fullHex} !important; }
            ::selection { background: ${fullHex} !important; color: #ffffff !important; }
          `;
          ['--c-primary', '--color-primary', '--primary', '--theme-color', '--accent', '--blue', '--violet', '--cyan', '--grad'].forEach((p) => {
            try { doc.documentElement.style.setProperty(p, fullHex, 'important'); } catch(_) {}
          });
        }
      } catch (_) {}
    });
  } catch (err) {
    console.warn("Could not dispatch live color:", err);
  }
};

export const dispatchLiveSectionScroll = (sectionId) => {
  try {
    if (!sectionId) return;
    const iframes = document.querySelectorAll("iframe");
    iframes.forEach((frame) => {
      try {
        frame.contentWindow?.postMessage({ type: "SCROLL_TO_SECTION", sectionId }, "*");
      } catch (_) {}
    });
  } catch (_) {}
};

export const dispatchLiveContentUpdate = (sectionId, key, value, prevValue = null) => {
  try {
    if (typeof value === "undefined") return;
    const payload = {
      type: "UPDATE_CONTENT",
      sectionId,
      key,
      value,
      prevValue
    };
    const iframes = document.querySelectorAll("iframe");
    iframes.forEach((frame) => {
      try {
        frame.contentWindow?.postMessage(payload, "*");
      } catch (_) {}
    });
  } catch (err) {
    console.warn("Could not dispatch live content update:", err);
  }
};

export default function PreviewPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const activeTemplateId = searchParams.get("template") || searchParams.get("templateId") || searchParams.get("slug") || "default";
  const studioBuildId = searchParams.get("build") || "";
  const [customDraftId, setCustomDraftId] = useState(null);
  const effectiveTemplateId = customDraftId || activeTemplateId;

  // Template Data State
  const [templateData, setTemplateData] = useState(null);
  const [loadingTemplate, setLoadingTemplate] = useState(false);

  // Authentication & Demo Lock State
  const isSignedIn = useAuthStore((s) => s.isSignedIn);
  const authToken = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const [demoSessionToken, setDemoSessionToken] = useState(null);
  const [demoRemainingSeconds, setDemoRemainingSeconds] = useState(1800); // 30 minutes
  const [isDemoExpired, setIsDemoExpired] = useState(false);
  const [isWipingData, setIsWipingData] = useState(false);

  const formatDemoTime = (totalSec) => {
    const mins = Math.floor(Math.max(0, totalSec) / 60);
    const secs = Math.max(0, totalSec) % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  // Helper to end session and wipe demo data permanently
  const endSessionAndWipe = async (reason = "manual") => {
    setIsWipingData(true);
    const targetToken = demoSessionToken;
    const targetId = customDraftId || activeTemplateId;
    const endpoint = `${API_BASE}/preview/demo/session/end?session_token=${encodeURIComponent(targetToken || "")}&template_id=${encodeURIComponent(targetId || "")}&reason=${encodeURIComponent(reason)}`;

    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      try {
        navigator.sendBeacon(endpoint, "");
      } catch (e) { }
    } else {
      try {
        await fetch(endpoint, { method: "POST", keepalive: true });
      } catch (e) { }
    }
  };

  const handleBackToMarketplace = async () => {
    if (hasUnfinalizedChanges) {
      setShowExitConfirmModal(true);
      return;
    }
    await endSessionAndWipe("back_nav");
    navigate("/marketplace");
  };

  const handleDemoTimeout = async () => {
    setIsDemoExpired(true);
    await endSessionAndWipe("timeout_30m");
  };

  // 1. Initialize 30-minute Demo Session on mount if authenticated
  useEffect(() => {
    if (!isSignedIn) return;
    const targetId = customDraftId || activeTemplateId;
    if (!targetId || targetId === "default") return;

    let timer = null;
    let pollInterval = null;

    const startSession = async () => {
      try {
        const headers = { "Content-Type": "application/json" };
        if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

        const res = await fetch(`${API_BASE}/preview/demo/session/start`, {
          method: "POST",
          headers,
          body: JSON.stringify({ template_id: targetId }),
        });

        if (res.ok) {
          const data = await res.json();
          setDemoSessionToken(data.session_token);
          if (typeof data.remaining_seconds === "number") {
            setDemoRemainingSeconds(data.remaining_seconds);
          }
        }
      } catch (err) {
        console.warn("Could not start demo session:", err);
      }
    };

    startSession();

    // Local countdown timer (1s interval)
    timer = setInterval(() => {
      setDemoRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleDemoTimeout();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    // Periodic backend status sync (every 60s)
    pollInterval = setInterval(async () => {
      if (!demoSessionToken) return;
      try {
        const res = await fetch(`${API_BASE}/preview/demo/session/status?session_token=${encodeURIComponent(demoSessionToken)}`);
        if (res.ok) {
          const sData = await res.json();
          if (sData.expired) {
            handleDemoTimeout();
          } else if (typeof sData.remaining_seconds === "number") {
            setDemoRemainingSeconds(sData.remaining_seconds);
          }
        }
      } catch (e) { }
    }, 60000);

    return () => {
      if (timer) clearInterval(timer);
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [isSignedIn, activeTemplateId, customDraftId, authToken]);

  // 2. Beacon on window close / tab navigation
  useEffect(() => {
    const handleUnload = () => {
      endSessionAndWipe("tab_closed");
    };
    window.addEventListener("beforeunload", handleUnload);
    window.addEventListener("pagehide", handleUnload);
    window.addEventListener("popstate", () => endSessionAndWipe("back_nav"));
    return () => {
      window.removeEventListener("beforeunload", handleUnload);
      window.removeEventListener("pagehide", handleUnload);
    };
  }, [demoSessionToken, customDraftId, activeTemplateId]);

  // Cart integration
  const addToCart = useCartStore((s) => s.addItem);
  const isInCart = useCartStore((s) => s.isInCart);

  // Cart state
  const [addedToCart, setAddedToCart] = useState(false);
  const [showSaveSuccess, setShowSaveSuccess] = useState(false);
  const templateId = customDraftId || activeTemplateId;

  const handleAddToCart = () => {
    const targetId = customDraftId || activeTemplateId;
    const catItem = getFallbackTemplate(targetId) || getFallbackTemplate(activeTemplateId);
    const resolvedPrice = Number(templateData?.price) > 0 ? Number(templateData.price) : (catItem?.price || 49);
    const item = {
      templateId: targetId,
      id: targetId,
      template_id: targetId,
      original_template_id: activeTemplateId,
      title: templateData?.title || catItem?.displayName || catItem?.title || brand?.business_name || `Template #${targetId}`,
      price: resolvedPrice,
      price_currency: templateData?.price_currency || catItem?.price_currency || "USD",
      thumbnail: templateData?.thumbnail_url || templateData?.thumbnail || catItem?.thumbnail_url || "/landing/template_saas.png",
      thumbnail_url: templateData?.thumbnail_url || catItem?.thumbnail_url || "/landing/template_saas.png",
      framework: templateData?.framework || catItem?.framework || "React 19 + Tailwind",
      seller_id: templateData?.seller_id,
      licenseType: "regular",
      is_free: false,
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
    navigate("/checkout");
  };

  // 2 Top Mode Buttons State: "manual" | "ai"
  const [editorMode, setEditorMode] = useState("manual"); // "manual" | "ai" | "assets"
  const [projectAssets, setProjectAssets] = useState([]);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [replacingAssetPath, setReplacingAssetPath] = useState(null);
  const [restoringAssetPath, setRestoringAssetPath] = useState(null);
  const [replacedAssetPaths, setReplacedAssetPaths] = useState(new Set());
  const [assetTimestamp, setAssetTimestamp] = useState(Date.now());
  const assetFileInputRef = useRef(null);
  const [selectedAssetForUpload, setSelectedAssetForUpload] = useState(null);

  const fetchProjectAssets = async () => {
    if (!templateId) return;
    setLoadingAssets(true);
    try {
      const res = await fetch(`${API_BASE}/preview/live/${templateId}/assets`);
      if (res.ok) {
        const data = await res.json();
        setProjectAssets(data.assets || []);
      }
    } catch (err) {
      console.warn("Could not fetch project assets:", err);
    } finally {
      setLoadingAssets(false);
    }
  };

  useEffect(() => {
    if (editorMode === "assets") {
      fetchProjectAssets();
    }
  }, [editorMode, templateId]);

  const handleTriggerReplaceAsset = (asset) => {
    setSelectedAssetForUpload(asset);
    if (assetFileInputRef.current) {
      assetFileInputRef.current.value = "";
      assetFileInputRef.current.click();
    }
  };

  const handleAssetFileSelected = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !selectedAssetForUpload || !templateId) return;

    // Subscription Tier Enforcement:
    // 1. Free: Requires credits or plan upgrade
    // 2. Pro: Maximum 2 image replacements per template
    // 3. Extreme: Unlimited image changes multiple times
    const userTier = (user?.subscription_tier || "free").toLowerCase();
    const isExtreme = ["extreme", "agency", "enterprise"].includes(userTier);
    const isPro = userTier === "pro";
    const isAdmin = user?.role === "admin" || user?.role === "super_admin";

    if (!isExtreme && !isPro && !isAdmin) {
      if ((user?.ai_credits || 0) < 5) {
        alert("On the Free Tier, image replacements require purchasing credits or upgrading your plan. Upgrade to the Pro Plan (up to 2 image replacements per template) or Extreme Plan (unlimited image changes) to modify templates.");
        return;
      }
    }

    if (isPro && !isExtreme && !isAdmin) {
      const alreadyReplacedThis = replacedAssetPaths.has(selectedAssetForUpload.rel_path);
      if (!alreadyReplacedThis && replacedAssetPaths.size >= 2) {
        alert("Your Pro Plan includes up to 2 image replacements per template. You have already customized 2 photos for this template! Upgrade to the Extreme Plan for unlimited image and asset replacements multiple times.");
        return;
      }
    }

    setReplacingAssetPath(selectedAssetForUpload.rel_path);
    try {
      const draftId = await ensureUserDraftCopy();
      if (!draftId || !authToken) throw new Error("Sign in to edit this asset. Your changes are saved to a private draft.");
      const formData = new FormData();
      formData.append("target_rel_path", selectedAssetForUpload.rel_path);
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/preview/live/${draftId}/assets/replace`, {
        method: "POST",
        headers: { Authorization: `Bearer ${authToken}` },
        body: formData,
      });
      const data = await res.json();
      if (res.ok && data.success) {
        const newTs = Date.now();
        setAssetTimestamp(newTs);
        setIframeKey((k) => k + 1);
        setHasUnfinalizedChanges(true);
        setReplacedAssetPaths((prev) => new Set([...prev, selectedAssetForUpload.rel_path]));
        setProjectAssets((prev) =>
          prev.map((a) => (a.rel_path === selectedAssetForUpload.rel_path ? { ...a, has_backup: true, timestamp: newTs } : a))
        );
        setNotice(`✓ Replaced photo "${selectedAssetForUpload.filename}"! Code remains 100% intact.`);
        setTimeout(() => setNotice(""), 4000);
        await fetchProjectAssets();
      } else {
        alert(data.detail || "Failed to replace asset.");
      }
    } catch (err) {
      alert("Error uploading asset replacement: " + err.message);
    } finally {
      setReplacingAssetPath(null);
      setSelectedAssetForUpload(null);
    }
  };

  const handleRestoreAsset = async (asset) => {
    if (!asset || !templateId) return;
    setRestoringAssetPath(asset.rel_path);
    try {
      const draftId = customDraftId || activeTemplateId;
      const res = await fetch(`${API_BASE}/preview/live/${draftId}/assets/restore`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ target_rel_path: asset.rel_path }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        const newTs = Date.now();
        setAssetTimestamp(newTs);
        setIframeKey((k) => k + 1);
        setReplacedAssetPaths((prev) => {
          const next = new Set(prev);
          next.delete(asset.rel_path);
          return next;
        });
        setProjectAssets((prev) =>
          prev.map((a) => (a.rel_path === asset.rel_path ? { ...a, has_backup: false, timestamp: newTs } : a))
        );
        setNotice(`✓ Returned original photo for "${asset.filename}"!`);
        setTimeout(() => setNotice(""), 4000);
        await fetchProjectAssets();
      } else {
        alert(data.detail || "Failed to return asset.");
      }
    } catch (err) {
      alert("Error returning asset: " + err.message);
    } finally {
      setRestoringAssetPath(null);
    }
  };
  const [mobilePanel, setMobilePanel] = useState("preview");
  const [leftSidebarCollapsed, setLeftSidebarCollapsed] = useState(false);
  const [rightSidebarCollapsed, setRightSidebarCollapsed] = useState(false);
  const [showMobileActionMenu, setShowMobileActionMenu] = useState(false);

  // Center Stage Viewport & Theme State
  const [viewMode, setViewMode] = useState(() => {
    if (typeof window !== "undefined") {
      const sp = new URLSearchParams(window.location.search);
      const mode = sp.get("mode");
      if (mode === "live") return "live";
      if (mode === "designed") return "designed";
      const tmpl = sp.get("template") || sp.get("templateId") || sp.get("slug");
      if (tmpl && tmpl !== "default") return "live";
    }
    return "designed";
  });
  const [canvasViewport, setCanvasViewport] = useState("desktop"); // "desktop" | "laptop" | "tablet" | "mobile"
  const [canvasBg, setCanvasBg] = useState("light"); // "light" | "dark" | "grid"
  const [notice, setNotice] = useState("");
  const [hasUnfinalizedChanges, setHasUnfinalizedChanges] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);
  const [showExitConfirmModal, setShowExitConfirmModal] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [iframeKey, setIframeKey] = useState(0);

  // Multi-Page Visual AI Studio State
  const [pages, setPages] = useState([
    { id: "index.html", title: "Home", icon: "🏠", sectionKey: "hero", path: "index.html" },
    { id: "about.html", title: "About", icon: "🏢", sectionKey: "about", path: "about.html" },
    { id: "services.html", title: "Services", icon: "⚙️", sectionKey: "services", path: "services.html" },
    { id: "pricing.html", title: "Pricing", icon: "💳", sectionKey: "pricing", path: "pricing.html" },
    { id: "contact.html", title: "Contact", icon: "✉️", sectionKey: "contact", path: "contact.html" },
  ]);
  const [activePage, setActivePage] = useState("index.html");
  const [showAddPageModal, setShowAddPageModal] = useState(false);
  const [newPageName, setNewPageName] = useState("");
  const [newPagePreset, setNewPagePreset] = useState("content");

  const handleSelectPage = (page) => {
    const isFile = page.id && !page.id.startsWith("#");
    setActivePage(page.id);
    setEditorMode("manual");
    if (isFile) {
      // Force fresh reload of the canvas iframe for the selected subpage file
      setIframeKey((k) => k + 1);
    } else {
      const sId = page.id.replace("#", "");
      setSelectedSectionId(sId);
      dispatchLiveSectionScroll(sId);
    }
    if (page.sectionKey && sections.some((s) => s.id === page.sectionKey)) {
      setSelectedSectionId(page.sectionKey);
    }
    setNotice(`✓ Switched to "${page.title}" (${page.path || page.id})`);
    setTimeout(() => setNotice(""), 3000);
  };

  const handleConfirmAddPage = () => {
    if (!newPageName.trim()) return;
    const cleanSlug = newPageName.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    if (!cleanSlug) {
      setNotice("Use at least one letter or number in the page title.");
      return;
    }
    const pageFileName = `${cleanSlug}.html`;
    if (pages.some((page) => page.id.toLowerCase() === pageFileName.toLowerCase())) {
      setNotice("A page with that name already exists.");
      return;
    }
    const newPageObj = {
      id: pageFileName,
      title: newPageName.trim(),
      icon: "📄",
      path: pageFileName,
      sectionKey: cleanSlug,
      isNew: true,
    };
    setPages((prev) => [...prev, newPageObj]);

    // If section does not exist in the left filter column, register it dynamically
    if (!sections.some((s) => s.id === cleanSlug)) {
      const newSec = {
        id: cleanSlug,
        name: `${newPageName.trim()} Page`,
        category: "Custom Subpages",
        icon: FileText,
        desc: `Custom dynamic page layout for ${newPageName.trim()}`,
        targetSection: cleanSlug,
      };
      setSections((prev) => [...prev, newSec]);
      setSectionProps((prev) => ({
        ...prev,
        [cleanSlug]: {
          headline: newPageName.trim(),
          subheadline: `Discover our specialized ${newPageName.trim()} solutions and resources.`,
          sectionTitle: newPageName.trim(),
          sectionSubtitle: `Welcome to the official ${newPageName.trim()} subpage.`,
          story: `This page is fully integrated into your multi-page website studio. Customize its layout, copy, and components lively.`,
          primaryCta: "Learn More",
          themeColor: brand.primary_color || "#c89666",
        },
      }));
    }

    setActivePage(pageFileName);
    setSelectedSectionId(cleanSlug);
    setShowAddPageModal(false);
    setNewPageName("");
    setNotice(`Added "${newPageName.trim()}" to this editor session. A source page file is not created yet.`);
    setTimeout(() => setNotice(""), 4000);
  };

  // Master Brand State
  const [brand, setBrand] = useState({
    business_name: "Apex Design Studio",
    tagline: "Next-Generation Web & Design Solutions",
    logo_text: "APEX",
    primary_color: "#b5804f",
    secondary_color: "#0ea5e9",
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
      themeColor: "#b5804f"
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
      themeColor: "#b5804f"
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
      themeColor: "#b5804f"
    },
    about: {
      badgeText: "About Apex Studio",
      title: "Crafting the Future of Agentic Web Design",
      story: "Founded in 2024, our studio bridges the gap between dynamic code generation and human craft. We provide creators, developers, and enterprises with production-ready website templates.",
      mission: "To empower every creator to build, customize, and launch world-class digital experiences effortlessly.",
      teamCount: "24 Engineers & Designers",
      themeColor: "#b5804f"
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
      themeColor: "#b5804f"
    },
    testimonials: {
      sectionTitle: "Trusted by Creators & Agencies Worldwide",
      quote: "AI Site Studio saved our agency over 60 engineering hours on our latest client redesign. The code quality is immaculate.",
      author: "Sarah Jenkins",
      role: "VP of Product",
      company: "CloudScale Inc.",
      rating: "5",
      themeColor: "#b5804f"
    },
    contact: {
      title: "Get in Touch with Our Team",
      subtitle: "Have questions about our templates or need custom design assistance? Reach out anytime.",
      email: "hello@apex-studio.com",
      phone: "",
      address: "",
      hours: "Mon - Fri: 9:00 AM - 6:00 PM PST",
      buttonText: "Send Message",
      themeColor: "#b5804f"
    },
    announcement: {
      badge: "Special Offer",
      title: "Spring 2026 Collection Live",
      message: "Explore our newest production-ready templates with 20% discount using promo code SPRING26.",
      ctaText: "Explore Now",
      themeColor: "#b5804f"
    },
    footer: {
      brandName: "Apex Design Studio",
      tagline: "Empowering creators with production-ready AI templates.",
      copyright: `© ${new Date().getFullYear()} Apex Design Studio. All rights reserved.`,
      link1: "Privacy Policy",
      link2: "Terms of Service",
      link3: "Support Center",
      themeColor: "#b5804f"
    }
  });
  const defaultSectionPropsRef = useRef(sectionProps);
  const initialSectionPropsRef = useRef(sectionProps);

  // Dynamic Section List State
  const [sections, setSections] = useState([]);
  const [selectedSectionId, setSelectedSectionId] = useState("navbar");
  const [editingSectionId, setEditingSectionId] = useState(null);
  const [renameInput, setRenameInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [showAddMenu, setShowAddMenu] = useState(false);

  // Fetch Template Details on mount and lively detect template sections
  useEffect(() => {
    let cancelled = false;
    if (activeTemplateId && activeTemplateId !== "default") {
      setLoadingTemplate(true);
      setTemplateData(null);
      setSectionProps(defaultSectionPropsRef.current);
      setSections([]);

      // Fetch template details AND real extracted template sections in parallel
      Promise.all([
        api.get(`/templates/${activeTemplateId}`).catch((err) => {
          console.warn("Could not load template detail:", err);
          return getFallbackTemplate(activeTemplateId) || null;
        }),
        api.get(`/preview/live/${activeTemplateId}/extracted-data`).catch((err) => {
          console.warn("Could not load extracted data:", err);
          return null;
        })
      ]).then(async ([data, extracted]) => {
        // If extracted-data endpoint didn't succeed, extract directly in frontend via live preview HTML!
        if (!extracted || extracted.status !== "success") {
          try {
            const rawRes = await fetch(`${API_BASE}/preview/live/${activeTemplateId}`);
            if (rawRes.ok) {
              const liveHtml = await rawRes.text();
              if (typeof liveHtml === "string" && liveHtml.length > 50) {
                extracted = extractTemplateFromHtml(liveHtml);
              }
            }
          } catch (e) {
            console.warn("Frontend DOM extraction fallback error:", e);
          }
        }

        if (cancelled) return;
        let initialProps = { ...defaultSectionPropsRef.current };
        let primaryColor = "#c89666";

        // Check local storage for persistent user custom color first!
        try {
          const cachedColor = localStorage.getItem(`studio_theme_color_${activeTemplateId}`) || localStorage.getItem(`studio_theme_color_${effectiveTemplateId}`);
          if (cachedColor && /^#[0-9a-fA-F]{3,8}$/.test(cachedColor)) {
            primaryColor = cachedColor;
          }
        } catch (_) {}

        if (data) {
          setTemplateData(data);

          // Dynamically load generated project pages into multi-page switcher
          if (data.changelog?.plan?.pages && Array.isArray(data.changelog.plan.pages) && data.changelog.plan.pages.length > 0) {
            const dynamicPages = data.changelog.plan.pages.map((p, idx) => {
              const fname = p.filename || `${(p.name || "page").toLowerCase().replace(/[^a-z0-9]+/g, "-")}.html`;
              const isHome = idx === 0 || fname === "index.html" || (p.name || "").toLowerCase() === "home";
              const targetFname = isHome ? "index.html" : fname;
              return {
                id: targetFname,
                title: isHome ? "Home" : (p.name || targetFname.replace(".html", "").replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())),
                icon: isHome ? "🏠" : "📄",
                path: targetFname,
                sectionKey: targetFname.replace(".html", ""),
              };
            });
            setPages(dynamicPages);
          } else if (data.included_pages && Array.isArray(data.included_pages) && data.included_pages.length > 0) {
            const dynamicPages = data.included_pages.map((pName, idx) => {
              const clean = String(pName);
              const isHome = idx === 0 || clean.toLowerCase() === "home" || clean.toLowerCase() === (data.title || "").toLowerCase();
              const fname = isHome ? "index.html" : (clean.endsWith(".html") ? clean : `${clean.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.html`);
              return {
                id: fname,
                title: isHome ? "Home" : clean.replace(".html", "").replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
                icon: isHome ? "🏠" : "📄",
                path: fname,
                sectionKey: fname.replace(".html", ""),
              };
            });
            setPages(dynamicPages);
          }

          if (primaryColor === "#c89666" && data.color_scheme) {
            if (data.color_scheme.trim().startsWith("#")) {
              primaryColor = data.color_scheme.trim();
            } else {
              const schemeLower = data.color_scheme.toLowerCase();
              if (schemeLower.includes("red")) primaryColor = "#dc2626";
              else if (schemeLower.includes("green")) primaryColor = "#059669";
              else if (schemeLower.includes("blue")) primaryColor = "#2563eb";
            }
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
          initialProps = {
            ...initialProps,
            navbar: { ...initialProps.navbar, brandName: bName, logoText: lText, themeColor: primaryColor },
            hero: { ...initialProps.hero, headline: `Welcome to ${bName}`, subheadline: data.short_description || data.description || initialProps.hero.subheadline, themeColor: primaryColor },
            about: { ...initialProps.about, title: `About ${bName}`, story: data.description || initialProps.about.story, themeColor: primaryColor },
            footer: { ...initialProps.footer, brandName: bName, themeColor: primaryColor },
          };
        }

        // Apply extracted brand & section props directly from template source files
        if (extracted && extracted.status === "success") {
          const diskColor = extracted.brand?.primary_color;
          if (diskColor && diskColor.startsWith("#") && primaryColor === "#c89666") {
            primaryColor = diskColor;
          }

          if (extracted.brand) {
            setBrand((prev) => ({
              ...prev,
              ...extracted.brand,
              business_name: extracted.brand.business_name || prev.business_name,
              logo_text: extracted.brand.logo_text || prev.logo_text,
              primary_color: primaryColor,
            }));
          }
          if (extracted.sections) {
            setSectionProps((prev) => ({
              ...prev,
              ...extracted.sections
            }));
            initialProps = { ...initialProps, ...extracted.sections };
          }
          initialSectionPropsRef.current = initialProps;
          if (extracted.sections_list && extracted.sections_list.length > 0) {
            const realDetected = extracted.sections_list.map((s) => ({
              ...s,
              icon: ICON_MAP[s.icon] || SECTION_ICONS[s.id] || Globe
            }));
            setSections(realDetected);
            setSelectedSectionId((prev) => realDetected.some((s) => s.id === prev) ? prev : realDetected[0].id);

            // Populate top multi-page switcher if only 1 page exists
            setPages((prevPages) => {
              if (!prevPages || prevPages.length <= 1) {
                const sectionPages = [
                  { id: "index.html", title: "Home", icon: "🏠", path: "index.html", sectionKey: "navbar" }
                ];
                realDetected.forEach((sec) => {
                  if (sec.id !== "navbar" && sec.id !== "footer") {
                    sectionPages.push({
                      id: `#${sec.id}`,
                      title: sec.name,
                      icon: "📑",
                      path: `#${sec.id}`,
                      sectionKey: sec.id
                    });
                  }
                });
                return sectionPages;
              }
              return prevPages;
            });
            return;
          }
        }

        // Fallback detection using extracted sections or template data
        const detected = detectTemplateSections(data, extracted?.sections || null);
        initialSectionPropsRef.current = initialProps;
        setSections(detected);
        if (detected.length > 0) {
          setSelectedSectionId((prev) => detected.some((s) => s.id === prev) ? prev : detected[0].id);
        }
      }).finally(() => {
        if (!cancelled) setLoadingTemplate(false);
      });
    } else {
      // Default demo mode: inspect lively
      const detected = detectTemplateSections(null, null);
      setTemplateData(null);
      setSectionProps(defaultSectionPropsRef.current);
      initialSectionPropsRef.current = defaultSectionPropsRef.current;
      setSections(detected);
      setLoadingTemplate(false);
    }
    return () => { cancelled = true; };
  }, [activeTemplateId]);

  // Active section item
  const currentSection = useMemo(() => {
    return sections.find((s) => s.id === selectedSectionId) || sections[0] || { id: "navbar", name: "Navigation Header" };
  }, [sections, selectedSectionId]);

  const currentProps = useMemo(() => {
    return sectionProps[currentSection.id] || sectionProps.navbar || {};
  }, [sectionProps, currentSection.id]);

  const forkingRef = useRef(false);

  const ensureUserDraftCopy = useCallback(async () => {
    if (customDraftId) return customDraftId;
    if (forkingRef.current) return null;
    if (templateData && templateData.status === "draft") {
      setCustomDraftId(templateData.id);
      return templateData.id;
    }
    if (!activeTemplateId || activeTemplateId === "default") return null;

    forkingRef.current = true;
    try {
      const res = await api.post(`/preview/live/${activeTemplateId}/fork-draft`);
      const newDraftId = res?.draft_id || res?.data?.draft_id || res?.template_id;
      if (newDraftId) {
        setCustomDraftId(newDraftId);
        try {
          const u = new URL(window.location.href);
          u.searchParams.set("template", newDraftId);
          window.history.replaceState(null, "", u.pathname + u.search);
        } catch (_) {}
        setNotice("📁 Cloned template to your private draft. Marketplace template is protected.");
        setTimeout(() => setNotice(""), 4500);
        return newDraftId;
      }
    } catch (err) {
      console.warn("Could not auto-fork draft:", err);
    } finally {
      forkingRef.current = false;
    }
    return null;
  }, [customDraftId, templateData, activeTemplateId]);

  // ─────────────────────────────────────────────────────────────────────────
  // Field Edit Handler: Natural Backspace & Typing
  // ─────────────────────────────────────────────────────────────────────────
  const handleFieldChange = (key, value) => {
    const prevVal = sectionProps[currentSection?.id]?.[key];
    setHasUnfinalizedChanges(true);
    setSectionProps((prev) => ({
      ...prev,
      [currentSection.id]: {
        ...prev[currentSection.id],
        [key]: value
      }
    }));

    // If changing themeColor, instantly propagate to all live preview iframes
    if (key === "themeColor" && typeof value === "string") {
      try {
        if (effectiveTemplateId) {
          localStorage.setItem(`studio_theme_color_${effectiveTemplateId}`, value);
          localStorage.setItem(`studio_theme_color_${activeTemplateId}`, value);
        }
      } catch (_) {}
      dispatchLiveIframeColor(value);
    } else {
      // Instantly dispatch live content update to center demo iframe ("like copy-paste")
      dispatchLiveContentUpdate(currentSection?.id, key, value, prevVal);
    }

    // Auto-fork marketplace template into private draft so master is never edited
    ensureUserDraftCopy();
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
    setNotice(`Renamed this editor section to "${renameInput.trim()}". The source template label is unchanged.`);
    setTimeout(() => setNotice(""), 3000);
  };

  const handleCancelRename = (e) => {
    if (e) e.stopPropagation();
    setEditingSectionId(null);
  };

  const handleEraseSectionContent = (secId, e) => {
    if (e) e.stopPropagation();
    setHasUnfinalizedChanges(true);
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
    setHasUnfinalizedChanges(true);
    const target = sections.find((s) => s.id === secId);
    if (!target) return;
    if (sections.length === 1) {
      setNotice("Keep at least one section in the editor.");
      return;
    }
    const remaining = sections.filter((s) => s.id !== secId);
    setSections(remaining);
    if (selectedSectionId === secId && remaining.length > 0) {
      setSelectedSectionId(remaining[0].id);
    }
    setNotice(`Removed "${target.name}" from this editor session. The source template is unchanged.`);
    setTimeout(() => setNotice(""), 3500);
  };

  const handleAddSection = (sec) => {
    if (sections.some((s) => s.id === sec.id)) return;
    setHasUnfinalizedChanges(true);
    setEditorMode("manual");
    const updated = [...sections, sec];
    setSections(updated);
    setSelectedSectionId(sec.id);
    setShowAddMenu(false);
    setNotice(`Added "${sec.name}" to this editor session. The source template is unchanged.`);
    setTimeout(() => setNotice(""), 3000);
  };

  const handleApplyBusinessPreset = (preset) => {
    setHasUnfinalizedChanges(true);
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
    const resetValue = initialSectionPropsRef.current?.[currentSection?.id]
      || defaultSectionPropsRef.current?.[currentSection?.id];
    if (!resetValue) {
      setNotice(`No saved starting values are available for ${currentSection?.name || "this section"}.`);
      return;
    }
    setSectionProps((prev) => ({ ...prev, [currentSection.id]: { ...resetValue } }));

    // Instantly sync the reset values back to the live iframe DOM
    Object.entries(resetValue).forEach(([k, v]) => {
      dispatchLiveContentUpdate(currentSection.id, k, v);
    });

    if (resetValue.themeColor) {
      dispatchLiveIframeColor(resetValue.themeColor);
    }

    // Refresh iframe to guarantee DOM clean state
    setIframeKey((prev) => prev + 1);

    setNotice(`✓ Reset "${currentSection?.name || "Section"}" to original values.`);
    setTimeout(() => setNotice(""), 3000);
  };

  const handleCopyCode = () => {
    const code = `// ${currentSection.name} Output Data\n` + JSON.stringify(currentProps, null, 2);
    navigator.clipboard.writeText(code);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  // Save manual edit to backend and reload live template
  // ─────────────────────────────────────────────────────────────────────────
  // Apply Theme Color directly into Website Code (CSS files & disk)
  // ─────────────────────────────────────────────────────────────────────────
  const handleApplyThemeColorToProject = async (newColor) => {
    setHasUnfinalizedChanges(true);
    let targetId = customDraftId;
    if (!targetId && templateData?.status !== "draft") {
      targetId = await ensureUserDraftCopy();
    }
    if (!targetId) targetId = effectiveTemplateId;

    if (!targetId || targetId === "default") {
      setNotice("Theme color preview updated in memory.");
      return;
    }
    try {
      const res = await api.post(`/preview/live/${targetId}/apply-theme-color`, {
        primary_color: newColor
      });
      if (res?.draft_id && res.draft_id !== targetId) {
        setCustomDraftId(res.draft_id);
        targetId = res.draft_id;
        try {
          const u = new URL(window.location.href);
          u.searchParams.set("template", res.draft_id);
          window.history.replaceState(null, "", u.pathname + u.search);
        } catch (_) {}
      }
      // Save locally to guarantee persistence across browser refreshes
      try {
        localStorage.setItem(`studio_theme_color_${effectiveTemplateId}`, newColor);
        localStorage.setItem(`studio_theme_color_${activeTemplateId}`, newColor);
      } catch (_) {}
      // Broadcast live styling to iframes immediately
      dispatchLiveIframeColor(newColor);
      // Update local state across all sections
      setSectionProps((prev) => {
        const next = { ...prev };
        Object.keys(next).forEach((k) => {
          next[k] = { ...next[k], themeColor: newColor };
        });
        return next;
      });
      setBrand((prev) => ({ ...prev, primary_color: newColor }));
      // Reload iframe from updated disk files
      setIframeKey((prev) => prev + 1);
      setNotice(`✓ Theme color ${newColor} permanently applied to website code (index.css)!`);
      setTimeout(() => setNotice(""), 6000);
      return res;
    } catch (err) {
      console.warn("Could not apply theme color to code:", err);
      setNotice(`Could not save theme color: ${err?.message || "Please try again."}`);
      setTimeout(() => setNotice(""), 5000);
      throw err;
    }
  };

  const [savingManual, setSavingManual] = useState(false);
  const [savingWithAi, setSavingWithAi] = useState(false);

  const handleSaveManual = async (useAi = false) => {
    if (useAi) {
      setSavingWithAi(true);
      setNotice("⚡ Verifying codebase synthesis and saving changes...");
    } else {
      setSavingManual(true);
      setNotice("⚡ Fast-saving your changes directly...");
    }
    try {
      if (activeTemplateId !== "default") {
        const targetId = customDraftId || activeTemplateId;
        const page_edits = {};
        sections.forEach((sec) => {
          const props = sectionProps[sec.id];
          if (!props) return;
          page_edits[sec.id] = {
            title: props.headline || props.title || props.sectionTitle || props.brandName || "",
            subtitle: props.subtitle || props.subheadline || props.sectionSubtitle || "",
            description: props.story || props.description || "",
            cta_text: props.primaryCta || props.ctaText || props.buttonText || "",
            cta_link: props.ctaLink || "",
            phone: props.phone || "",
            email: props.email || "",
            address: props.address || "",
            tabs: props.tabs || [],
            filters: props.filters || [],
            cards: props.cards || [],
            socialLinks: props.socialLinks || [],
            textItems: props.textItems || [],
            brandName: props.brandName || "",
            logoText: props.logoText || "",
            navLinks: props.navLinks || []
          };
        });

        if (sectionProps.navbar) {
          page_edits["navbar"] = {
            ...(page_edits["navbar"] || {}),
            brandName: sectionProps.navbar.brandName || brand.business_name,
            logoText: sectionProps.navbar.logoText || brand.logo_text,
            navLinks: sectionProps.navbar.navLinks || [],
            cta_text: sectionProps.navbar.ctaText || "",
            cta_link: sectionProps.navbar.ctaLink || ""
          };
        }

        const res = await api.post(`/preview/live/${targetId}/edit-manual`, {
          business_name: sectionProps.navbar?.brandName || brand.business_name,
          about: sectionProps.about?.story || sectionProps.about?.description || sectionProps.hero?.subheadline || brand.tagline,
          primary_color: sectionProps[currentSection?.id]?.themeColor || sectionProps.navbar?.themeColor || sectionProps.hero?.themeColor || brand.primary_color,
          secondary_color: brand.secondary_color,
          contact_email: sectionProps.contact?.email || brand.contact_email,
          contact_phone: sectionProps.contact?.phone || brand.contact_phone,
          page_edits,
          use_ai: !!useAi
        });
        const newDraftId = res?.template_id || res?.data?.template_id;
        if (!newDraftId) throw new Error("The save endpoint did not return a draft ID.");
        setCustomDraftId(newDraftId);
        if (initialSectionPropsRef) {
          initialSectionPropsRef.current = JSON.parse(JSON.stringify(sectionProps));
        }
        setHasUnfinalizedChanges(false);
        navigate(`/preview?template=${newDraftId}&mode=live`, { replace: true });
        setViewMode("live");
        setIframeKey((prev) => prev + 1);
        setShowSaveSuccess(true);
        if (useAi) {
          setNotice("✓ Save complete: Entire codebase verified & saved to your private draft!");
        } else {
          setNotice("✓ Saved directly to your private project draft!");
        }
        return true;
      } else {
        setNotice("Preview changes are local to this session. Select a template to save a draft.");
      }
    } catch (e) {
      console.warn(e);
      setNotice(`Could not save changes: ${e?.message || "Please try again."}`);
    } finally {
      setSavingManual(false);
      setSavingWithAi(false);
      setTimeout(() => setNotice(""), 6000);
    }
  };
  const handleFinalizeChanges = async (useAi = false) => {
    const res = await handleSaveManual(useAi);
    if (res !== false) {
      setHasUnfinalizedChanges(false);
    }
    return res;
  };

  const handleSaveSingleSection = async (sectionId) => {
    const secObj = sections.find((s) => s.id === sectionId) || currentSection;
    const secName = secObj?.name || sectionId;
    setSavingManual(true);
    setNotice(`💾 Saving "${secName}" section to project...`);
    try {
      const res = await handleSaveManual();
      if (res !== false) {
        setNotice(`✓ Saved "${secName}" section successfully!`);
      }
    } catch (err) {
      setNotice(`Could not save "${secName}": ${err?.message || "Please try again."}`);
    } finally {
      setSavingManual(false);
      setTimeout(() => setNotice(""), 5000);
    }
  };

  const handleSaveAllSections = async () => {
    setSavingManual(true);
    setNotice("⚡ Saving all sections at once across your website...");
    try {
      const res = await handleSaveManual();
      if (res !== false) {
        setNotice("✓ Successfully saved all sections at once to your project draft!");
      }
    } catch (err) {
      setNotice(`Could not save all sections: ${err?.message || "Please try again."}`);
    } finally {
      setSavingManual(false);
      setTimeout(() => setNotice(""), 5000);
    }
  };

  const handleAddMoreContent = () => {
    if (!currentSection?.id) return;
    setHasUnfinalizedChanges(true);

    // 1. If section has cards array
    if (Array.isArray(currentProps.cards) && currentProps.cards.length > 0) {
      const last = currentProps.cards[currentProps.cards.length - 1] || {};
      const newIdx = currentProps.cards.length + 1;
      const newCard = {
        title: `Item #${newIdx} Title`,
        desc: "Detailed description of newly added content item...",
        tag: `PRINT 0${newIdx}`,
        stack: last.stack || ""
      };
      const updated = [...currentProps.cards, newCard];
      handleFieldChange("cards", updated);
      dispatchLiveContentUpdate(currentSection.id, "cards", updated);
      setNotice(`✓ Added item #${newIdx} into ${currentSection.name}!`);
      setTimeout(() => setNotice(""), 4000);
      return;
    }

    // 2. If section has textItems array
    if (Array.isArray(currentProps.textItems)) {
      const last = currentProps.textItems[currentProps.textItems.length - 1] || {};
      const newIdx = currentProps.textItems.length + 1;
      const newItem = {
        id: `text-${Date.now()}-${newIdx}`,
        label: last.label || "<SPAN> TEXT",
        text: `New content text #${newIdx}`,
        originalText: "",
        isNew: true
      };
      const updated = [...currentProps.textItems, newItem];
      handleFieldChange("textItems", updated);
      dispatchLiveContentUpdate(currentSection.id, "textItems", updated);
      setNotice(`✓ Added new text element into ${currentSection.name}!`);
      setTimeout(() => setNotice(""), 4000);
      return;
    }

    // 3. Fallback: Initialize cards with a rich new item
    const newCard = {
      title: "New Showcase Item",
      desc: "Detailed description of newly added section item...",
      tag: "NEW"
    };
    handleFieldChange("cards", [newCard]);
    dispatchLiveContentUpdate(currentSection.id, "cards", [newCard]);
    setNotice(`✓ Added new content item into ${currentSection.name}!`);
    setTimeout(() => setNotice(""), 4000);
  };

  const handleRevokeChanges = async () => {
    setIsRevoking(true);
    setNotice("↩️ Revoking all changes and restoring original template...");
    try {
      const targetId = customDraftId || effectiveTemplateId;
      if (targetId && targetId !== "default") {
        try {
          await api.post(`/preview/live/${targetId}/revoke`);
        } catch (backendErr) {
          console.warn("Backend revoke warning:", backendErr);
        }
      }
      if (initialSectionPropsRef.current) {
        setSectionProps(JSON.parse(JSON.stringify(initialSectionPropsRef.current)));
        // Dispatch each section's reset values to live iframe DOM
        Object.entries(initialSectionPropsRef.current).forEach(([secId, sProps]) => {
          if (sProps && typeof sProps === "object") {
            Object.entries(sProps).forEach(([k, v]) => {
              dispatchLiveContentUpdate(secId, k, v);
            });
          }
        });
      }
      const origColor =
        initialSectionPropsRef.current?.navbar?.themeColor ||
        initialSectionPropsRef.current?.hero?.themeColor ||
        brand?.primary_color ||
        "#4F46E5";
      dispatchLiveIframeColor(origColor);
      setIframeKey((prev) => prev + 1);
      setHasUnfinalizedChanges(false);
      setShowSaveSuccess(false);
      setNotice("✓ Revoked all changes. Restored original template state.");
    } catch (err) {
      console.warn("Could not revoke changes:", err);
      setNotice(`Could not revoke changes: ${err?.message || "Please try again."}`);
    } finally {
      setIsRevoking(false);
      setTimeout(() => setNotice(""), 4000);
    }
  };

  const handleRevokeAndExit = async () => {
    await handleRevokeChanges();
    await endSessionAndWipe("back_nav");
    setShowExitConfirmModal(false);
    navigate("/marketplace");
  };

  const handleFinalizeAndExit = async () => {
    const res = await handleFinalizeChanges();
    if (res !== false) {
      setShowExitConfirmModal(false);
      navigate("/marketplace");
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // AI Prompt Assistant State & Handlers
  // ─────────────────────────────────────────────────────────────────────────
  const [aiInput, setAiInput] = useState("");
  const [selectedAiModel, setSelectedAiModel] = useState("gemini-1.5-flash");
  const [isAiProcessing, setIsAiProcessing] = useState(false);
  const [aiLogs, setAiLogs] = useState([]);
  const [aiHistory, setAiHistory] = useState([
    {
      id: "init",
      role: "assistant",
      text: "Hello! Describe any change in plain text (e.g. 'Change colors to dark blue', 'Change headline to Jordan Cole', 'Make background dark red', 'Add 3 feature cards') and I will refactor your template code in real time.",
      timestamp: "Just now"
    }
  ]);
  const [isDebugging, setIsDebugging] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    if (editorMode === "ai") {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [aiHistory, isAiProcessing, editorMode]);

  useEffect(() => {
    if (!studioBuildId) return undefined;
    let active = true;
    api.get(`/studio/builds/${studioBuildId}`).then((build) => {
      if (!active || !Array.isArray(build?.messages)) return;
      const restored = build.messages
        .filter((message) => message.type !== "build_brief")
        .map((message) => ({
          id: message.id,
          role: message.role,
          text: message.content,
          timestamp: message.created_at ? new Date(message.created_at).toLocaleString() : "Saved",
        }));
      if (restored.length) setAiHistory(restored);
    }).catch((err) => console.warn("Could not restore Studio build chat:", err));
    return () => { active = false; };
  }, [studioBuildId]);

  const persistBuildMessage = async (role, content, message_type = "chat") => {
    if (!studioBuildId) return;
    try {
      await api.post(`/studio/builds/${studioBuildId}/messages`, { role, content, message_type });
    } catch (err) {
      console.warn("Could not save Studio build chat message:", err);
    }
  };

  const executeAiPrompt = async (customPrompt) => {
    const promptToRun = customPrompt || aiInput;
    if (!promptToRun.trim() || isAiProcessing) return;

    setAiHistory((prev) => [
      ...prev,
      { id: Date.now().toString(), role: "user", text: promptToRun, timestamp: "Just now" }
    ]);
    setAiInput("");
    setIsAiProcessing(true);
    setHasUnfinalizedChanges(true);
    setAiLogs(["Sending your request to the editor..."]);
    await persistBuildMessage("user", promptToRun);

    const targetId = customDraftId || activeTemplateId;
    try {
      if (targetId !== "default") {
        const res = await api.post(`/preview/live/${targetId}/edit-ai`, { prompt: promptToRun, model: selectedAiModel });
        const newDraftId = res?.template_id || res?.data?.template_id;
        if (!newDraftId) throw new Error("The editor did not return a saved draft.");
        setCustomDraftId(newDraftId);
        const buildQuery = studioBuildId ? `&build=${encodeURIComponent(studioBuildId)}` : "";
        navigate(`/preview?template=${newDraftId}&mode=live${buildQuery}`, { replace: true });
        setViewMode("live");
        setIframeKey((k) => k + 1);
        const assistantText = res?.message || `✓ Applied your request: "${promptToRun}". Live preview in the center is updated!`;
        setAiHistory((prev) => [...prev, {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          text: assistantText,
          timestamp: "Just now"
        }]);
        await persistBuildMessage("assistant", assistantText);
        return;
      }

      // The built-in demo has no source archive or AI backend target. Support only the local presets here.
      const qLower = promptToRun.toLowerCase();
      const preset = qLower.includes("paris") || qLower.includes("bakery")
        ? BUSINESS_PRESETS.find((p) => p.id === "bakery")
        : qLower.includes("saas") || qLower.includes("tech")
          ? BUSINESS_PRESETS.find((p) => p.id === "saas")
          : qLower.includes("clinic") || qLower.includes("dental") || qLower.includes("medical")
            ? BUSINESS_PRESETS.find((p) => p.id === "medical")
            : null;
      if (preset) {
        handleApplyBusinessPreset(preset);
      } else if (qLower.includes("dark") || qLower.includes("glassmorphism")) {
        handleFieldChange("themeColor", "#d4a373");
        setCanvasBg("dark");
      } else {
        throw new Error("AI editing needs a real template draft. In demo mode, try a listed business or theme preset.");
      }
      const assistantText = "Applied a matching local demo preset. This did not call the AI service or save a draft.";
      setAiHistory((prev) => [...prev, {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        text: assistantText,
        timestamp: "Just now"
      }]);
      await persistBuildMessage("assistant", assistantText);
    } catch (err) {
      console.warn("AI editor request failed:", err);
      setNotice(`AI edit failed: ${err?.message || "Please try again."}`);
      await persistBuildMessage("assistant", `The edit was not completed: ${err?.message || "Please try again."}`, "error");
      setAiHistory((prev) => [...prev, {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        text: `The edit was not completed: ${err?.message || "Please try again."}`,
        timestamp: "Just now"
      }]);
    } finally {
      setIsAiProcessing(false);
      setAiLogs([]);
    }
  };

  const handleRunAIDebugger = async () => {
    const targetId = customDraftId || activeTemplateId;
    if (!targetId || targetId === "default") return;
    setIsDebugging(true);
    try {
      const res = await api.post(`/preview/live/${targetId}/ai-debug`, {});
      setNotice(res.message || "✓ Autonomous Debugger analyzed and fixed syntax errors.");
      setViewMode("live");
      setIframeKey((prev) => prev + 1);
    } catch (err) {
      alert("Auto Debugger: " + (err.message || "Failed to debug project."));
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

  const pageRouteParam = activePage && activePage !== "index.html" ? activePage : "";
  // 🔒 Lock Check: Require sign-in to access interactive demo
  if (!isSignedIn) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-card border border-border rounded-2xl p-8 shadow-2xl text-center relative overflow-hidden">
          <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-500 flex items-center justify-center mx-auto mb-5 shadow-inner">
            <Shield className="w-8 h-8" />
          </div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-500 mb-3 border border-amber-500/30">
            🔒 Interactive Demo Locked
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground mb-2">
            Sign in to Access Live Demo
          </h2>
          <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
            Sign in to launch your interactive 30-minute sandbox preview. Try out full-stack features, edit live with AI, test endpoints, and preview on all devices.
          </p>
          <div className="p-3.5 rounded-xl bg-muted/50 border border-border/80 text-left mb-6 space-y-1.5 text-xs text-muted-foreground">
            <div className="flex items-center gap-2 text-foreground font-semibold">
              <Clock className="w-3.5 h-3.5 text-primary" />
              <span>30-Minute Security Sandbox</span>
            </div>
            <p className="leading-normal">
              When you exit, navigate back, close the tab, or after 30 minutes, all temporary details you entered inside the generated website are <strong>permanently deleted</strong>.
            </p>
          </div>
          <div className="flex flex-col gap-3">
            <button
              type="button"
              onClick={() => navigate(`/sign-in?redirect=${encodeURIComponent(location.pathname + location.search)}`)}
              className="w-full py-2.5 px-4 rounded-xl font-semibold text-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-md flex items-center justify-center gap-2"
            >
              Sign In to Unlock Demo
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleBackToMarketplace}
              className="w-full py-2.5 px-4 rounded-xl font-medium text-sm border border-border hover:bg-accent transition-all text-muted-foreground"
            >
              Back to Marketplace
            </button>
          </div>
        </div>
      </div>
    );
  }

  const currentColorForIframe = sectionProps[currentSection?.id]?.themeColor || sectionProps.navbar?.themeColor || sectionProps.hero?.themeColor || brand?.primary_color || "";

  const liveServerUrl = effectiveTemplateId && effectiveTemplateId !== "default"
    ? `${API_BASE}/preview/live/${effectiveTemplateId}${pageRouteParam ? `/${pageRouteParam}` : "/"}?v=${iframeKey}${currentColorForIframe ? `&primaryColor=${encodeURIComponent(currentColorForIframe)}` : ""}`
    : null;

  return (
    <div className="sb-fullpage-root">
      {/* 30-Minute Demo Expired Kick-Back Modal */}
      {isDemoExpired && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-card border border-border rounded-2xl p-6 text-center shadow-2xl">
            <div className="w-12 h-12 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 flex items-center justify-center mx-auto mb-4">
              <Clock className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold mb-2">30-Minute Demo Ended</h3>
            <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
              Your interactive demo session has reached the 30-minute limit. All data, form submissions, and edits created inside the demo website have been permanently deleted.
            </p>
            <button
              type="button"
              onClick={() => navigate("/marketplace")}
              className="w-full py-2.5 px-4 rounded-xl font-semibold text-sm bg-primary text-primary-foreground hover:bg-primary/90 transition-all"
            >
              Return to Marketplace
            </button>
          </div>
        </div>
      )}
      {/* ═══════════════════════════════════════════════════════════════════════
         TOP HEADER: No "Storybook Studio" Name!
         Shows: Back button, Active Template Logo/Title, 2 Mode Buttons:
                [ 🛠️ 1. Manual Edit ] and [ 🤖 2. AI Edit ]
      ═════════════════════════════════════════════════════════════════════════ */}
      <header className="sb-fullpage-header">
        <div className="flex items-center gap-3">
          {/* Back Navigation Button */}
          {templateData?.template_origin === "studio" || templateData?.tags?.includes("studio-project") || searchParams.get("build") ? (
            <button
              type="button"
              onClick={() => navigate(`/studio/launch?template=${encodeURIComponent(effectiveTemplateId || "")}`)}
              className="sb-ghost-btn text-xs font-semibold py-1.5 px-3 border border-[#c89666]/30 text-[#dfb180] hover:text-white hover:bg-[#c89666]/20"
              title="Return to Launch Hub"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Back to Launch Hub</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleBackToMarketplace}
              className="sb-ghost-btn text-xs font-semibold py-1.5 px-3"
              title="Return to marketplace"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Back to Marketplace</span>
            </button>
          )}

          {/* Template Title & Logo (No Storybook Studio Branding!) */}
          <div className="flex items-center gap-2.5 pl-2 border-l border-border/50">
            <div className="sb-logo-box">
              <span className="text-white font-black text-xs tracking-tighter">
                {templateData?.title ? templateData.title.slice(0, 2).toUpperCase() : brand.logo_text.slice(0, 2)}
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="font-extrabold text-sm tracking-tight text-foreground">
                  {templateData?.title || brand.business_name}
                </h1>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  {templateData?.framework || "React"}
                </span>

                {/* 📸 Image Editor directly after the HTML badge */}
                <button
                  type="button"
                  onClick={() => {
                    setEditorMode(editorMode === "assets" ? "manual" : "assets");
                    if (mobilePanel === "sections") setMobilePanel("edit");
                  }}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border transition-all cursor-pointer select-none",
                    editorMode === "assets"
                      ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-300 shadow-sm"
                      : "bg-card/80 hover:bg-emerald-500/10 border-border hover:border-emerald-500/40 text-muted-foreground hover:text-emerald-400"
                  )}
                  title="Replace template photos & media assets"
                >
                  <Image className="w-3.5 h-3.5 text-emerald-400" />
                  <span>{editorMode === "assets" ? "Editing Photos" : "Change Photos"}</span>
                </button>

                {/* 🤖 Use AI to Change Code */}
                <button
                  type="button"
                  onClick={() => {
                    const userTier = (user?.subscription_tier || "free").toLowerCase();
                    const isExtreme = ["extreme", "agency", "enterprise"].includes(userTier);
                    const isAdmin = user?.role === "admin" || user?.role === "super_admin";
                    if (!isExtreme && !isAdmin) {
                      if (window.confirm("The Smart Synthesis Editor is an exclusive feature of the Extreme Plan. It allows conversational code refactoring, full-stack generation, and automated multi-site healing. Would you like to view the Extreme Plan now?")) {
                        navigate("/pricing");
                      }
                      return;
                    }
                    setEditorMode(editorMode === "ai" ? "manual" : "ai");
                    if (mobilePanel === "sections") setMobilePanel("edit");
                  }}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border transition-all cursor-pointer select-none",
                    editorMode === "ai"
                      ? "bg-[#c89666]/20 border-[#c89666]/50 text-[#dfb180] shadow-sm"
                      : "bg-card/80 hover:bg-[#c89666]/10 border-border hover:border-[#c89666]/40 text-muted-foreground hover:text-[#dfb180]"
                  )}
                  title="Automated Code Synthesis (Extreme Plan)"
                >
                  <Sparkles className="w-3.5 h-3.5 text-[#dfb180]" />
                  <span>{editorMode === "ai" ? "Synthesizing Code..." : "Automated Code Edit"}</span>
                  {!["extreme", "agency", "enterprise"].includes((user?.subscription_tier || "free").toLowerCase()) && !user?.is_admin && user?.role !== "admin" && (
                    <span className="text-[9px] uppercase px-1 py-0.5 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded font-black ml-0.5">Extreme</span>
                  )}
                </button>

                {/* Quick return button to manual content editor when in photo or AI mode */}
                {editorMode !== "manual" && (
                  <button
                    type="button"
                    onClick={() => setEditorMode("manual")}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-pink-500/15 hover:bg-pink-500/25 text-pink-400 border border-pink-500/30 transition-all cursor-pointer"
                    title="Return to section content editor"
                  >
                    <Sliders className="w-3.5 h-3.5" />
                    <span>Edit Content</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Notice Toast Banner */}
        {notice && (
          <div className="hidden md:flex px-3.5 py-1 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 text-xs font-semibold items-center gap-2 animate-fade-in">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>{notice}</span>
          </div>
        )}

        {/* Right Header Actions */}
        <div className="flex items-center gap-2">
          {/* DESKTOP ACTIONS */}
          <div className="hidden lg:flex items-center gap-2.5">
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

            {customDraftId || templateData?.status === "draft" ? (
              <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-bold" title="Working on your private draft copy. Marketplace master is protected.">
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                <span className="hidden md:inline">Private Draft (Protected)</span>
              </div>
            ) : (
              <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#c89666]/15 border border-[#c89666]/30 text-[#dfb180] text-xs font-semibold" title="Marketplace master preview. Edits auto-copy to your private draft.">
                <Sparkles className="w-3.5 h-3.5 text-[#dfb180]" />
                <span className="hidden md:inline">Marketplace Sandbox</span>
              </div>
            )}

            {hasUnfinalizedChanges && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 text-xs font-bold animate-pulse">
                <AlertCircle className="w-3.5 h-3.5" />
                <span className="hidden lg:inline">Draft Unsaved</span>
              </div>
            )}

            <button
              type="button"
              onClick={() => handleFinalizeChanges(false)}
              disabled={savingManual || savingWithAi}
              className="sb-primary-gradient-btn"
              title="Fast direct save: Saves your edits directly into files instantly"
            >
              <Zap className="w-3.5 h-3.5 text-amber-300 fill-amber-300" />
              <span>{savingManual ? "Saving..." : "Save"}</span>
            </button>

            <button
              type="button"
              onClick={() => handleFinalizeChanges(true)}
              disabled={savingManual || savingWithAi}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] text-xs font-bold shadow-lg shadow-black/40 transition-all border border-[#c89666]/30 cursor-pointer disabled:opacity-50"
              title="Deep Synthesis Save: Scans and verifies the entire codebase"
            >
              <Sparkles className={`w-3.5 h-3.5 text-amber-300 ${savingWithAi ? "animate-spin" : ""}`} />
              <span>{savingWithAi ? "Synthesizing..." : "Deep Save"}</span>
            </button>

            {hasUnfinalizedChanges && (
              <button
                type="button"
                onClick={handleRevokeChanges}
                disabled={isRevoking}
                className="sb-ghost-btn text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 border border-rose-500/20"
                title="Revoke changes and restore original template"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Revoke</span>
              </button>
            )}

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
                {/* Tech Stack Badge */}
                <span className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-white/5 border border-white/10 text-[11px] font-semibold text-slate-300">
                  <Code className="w-3.5 h-3.5 text-[#dfb180]" />
                  <span>{({ react: "React + FastAPI", vue: "Vue + FastAPI", angular: "Angular + FastAPI", nextjs: "Next.js + FastAPI" }[String(templateData?.framework || "html").toLowerCase()] || "HTML5 + CSS + JS")}</span>
                </span>

                <button
                  type="button"
                  onClick={handleBuyNow}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white text-xs font-bold shadow-lg shadow-amber-500/25 transition-all"
                  title="Buy Now"
                >
                  <ShoppingBag className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Buy Now</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    const targetId = customDraftId || activeTemplateId;
                    navigate(`/dashboard?tab=deployments&deployTemplate=${targetId}&autoOpen=true`);
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] text-xs font-bold shadow-lg shadow-emerald-500/20 transition-all border-0 cursor-pointer"
                  title="Deploy this website live with managed hosting"
                >
                  <Zap className="w-3.5 h-3.5 text-amber-300 fill-amber-300" />
                  <span className="hidden sm:inline">Deploy Live</span>
                </button>
              </>
            )}
          </div>

          {/* MOBILE COMPACT ACTIONS (Clean single-row controls) */}
          <div className="flex lg:hidden items-center gap-1.5">
            <button
              type="button"
              onClick={() => handleFinalizeChanges(false)}
              disabled={savingManual || savingWithAi}
              className="sb-primary-gradient-btn py-1.5 px-2.5 text-xs flex items-center gap-1"
              title="Fast direct save"
            >
              <Zap className="w-3.5 h-3.5 text-amber-300 fill-amber-300" />
              <span>{savingManual ? "Saving" : "Save"}</span>
            </button>
            <button
              type="button"
              onClick={() => handleFinalizeChanges(true)}
              disabled={savingManual || savingWithAi}
              className="py-1.5 px-2.5 rounded-xl bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] text-xs font-bold flex items-center gap-1 border border-[#c89666]/30 disabled:opacity-50"
              title="AI deep save across entire codebase"
            >
              <Sparkles className={`w-3 h-3 text-amber-300 ${savingWithAi ? "animate-spin" : ""}`} />
              <span>{savingWithAi ? "AI..." : "AI Save"}</span>
            </button>

            {templateData && (
              <button
                type="button"
                onClick={handleAddToCart}
                disabled={addedToCart || (templateData && isInCart?.(activeTemplateId))}
                className="p-2 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 transition-all disabled:opacity-60 relative"
                title="Add to Cart"
              >
                <ShoppingCart className="w-4 h-4" />
                {(addedToCart || isInCart?.(activeTemplateId)) && (
                  <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-emerald-400 rounded-full" />
                )}
              </button>
            )}
          </div>
        </div>
      </header>

      <nav className="sb-mobile-panel-switcher" aria-label="Editor panels">
        {[
          { id: "sections", label: "Sections", icon: Layers, count: sections.length },
          { id: "preview", label: "Live Preview", icon: Eye },
          { id: "edit", label: "Edit Fields", icon: Sliders },
        ].map(({ id, label, icon: Icon, count }) => (
          <button
            key={id}
            type="button"
            onClick={() => setMobilePanel(id)}
            className={cn("sb-mobile-panel-tab", mobilePanel === id && "active")}
            aria-pressed={mobilePanel === id}
          >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
            {count !== undefined && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted/80 font-mono">{count}</span>
            )}
          </button>
        ))}
      </nav>

      {/* ═══════════════════════════════════════════════════════════════════════
         MAIN 3-COLUMN STUDIO LAYOUT
      ═════════════════════════════════════════════════════════════════════════ */}
      <div className="sb-main-layout">

        {/* ─────────────────────────────────────────────────────────────────────
           LEFT COLUMN: Lively Filter Sections
           Inspects template code and only shows what is actually in this template!
        ───────────────────────────────────────────────────────────────────── */}
        <aside className={cn(
          "sb-sidebar-left transition-all duration-300",
          leftSidebarCollapsed && "w-0 min-w-0 border-0 p-0 overflow-hidden",
          mobilePanel !== "sections" && "sb-mobile-hidden"
        )}>
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
          <div className="px-4 py-2 flex items-center justify-between border-b border-border/40 text-[11px] font-bold uppercase tracking-wider text-muted-foreground select-none">
            <div className="flex items-center gap-1.5">
              <span>Template Sections ({sections.length})</span>
              <span className="text-[10px] text-pink-500 font-semibold">Detected</span>
            </div>
            <button
              type="button"
              onClick={() => setLeftSidebarCollapsed(true)}
              className="hidden lg:flex p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              title="Collapse Sections Sidebar"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Section List (Only Sections In This Template!) */}
          <div className="sb-sidebar-tree flex-1 overflow-y-auto p-2 pb-4">
            {loadingTemplate && (
              <p className="px-3 py-4 text-xs text-muted-foreground" role="status">
                Loading template sections…
              </p>
            )}
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
                      if (!isEditingThis) {
                        setEditorMode("manual");
                        setSelectedSectionId(sec.id);
                        dispatchLiveSectionScroll(sec.id);
                        if (mobilePanel === "sections") {
                          setMobilePanel("edit");
                        }
                      }
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
                            className="p-1 hover:bg-emerald-500/20 text-emerald-500 rounded cursor-pointer"
                            title="Save name"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleCancelRename(e)}
                            className="p-1 hover:bg-rose-500/20 text-rose-500 rounded cursor-pointer"
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
          </div>
        </aside>

        {/* ─────────────────────────────────────────────────────────────────────
           CENTER COLUMN: Expansive Stage
           Displays Real Designed Output View (or Real Running Live Demo IFrame)
        ───────────────────────────────────────────────────────────────────── */}
        <main className={cn("sb-center-stage relative", mobilePanel !== "preview" && "sb-mobile-hidden")}>
          {/* Floating Expand Pills for Collapsed Sidebars */}
          {leftSidebarCollapsed && (
            <button
              type="button"
              onClick={() => setLeftSidebarCollapsed(false)}
              className="hidden lg:flex absolute left-3 top-14 z-30 items-center gap-1.5 px-3 py-1.5 rounded-xl bg-card/95 backdrop-blur-md border border-border shadow-lg hover:border-primary/50 text-xs font-bold text-foreground transition-all cursor-pointer"
              title="Expand Sections"
            >
              <ChevronRight className="w-3.5 h-3.5 text-pink-500" />
              <span>Sections</span>
            </button>
          )}

          {rightSidebarCollapsed && (
            <button
              type="button"
              onClick={() => setRightSidebarCollapsed(false)}
              className="hidden lg:flex absolute right-3 top-14 z-30 items-center gap-1.5 px-3 py-1.5 rounded-xl bg-card/95 backdrop-blur-md border border-border shadow-lg hover:border-primary/50 text-xs font-bold text-foreground transition-all cursor-pointer"
              title="Expand Editor"
            >
              <span>Editor</span>
              <ChevronLeft className="w-3.5 h-3.5 text-pink-500" />
            </button>
          )}
          {/* Multi-Page Visual Switcher Bar */}
          <div className="sb-page-switcher-bar">
            <div className="flex items-center gap-1.5 overflow-x-auto py-1 scrollbar-none flex-1">
              <div className="flex items-center gap-1 text-[11px] font-extrabold uppercase tracking-wider text-muted-foreground mr-1 shrink-0">
                <Layers className="w-3.5 h-3.5 text-[#dfb180]" />
                <span className="hidden sm:inline">Pages ({pages.length}):</span>
              </div>
              {pages.map((p) => {
                const isActive = activePage === p.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => handleSelectPage(p)}
                    className={cn(
                      "sb-page-tab-btn",
                      isActive && "active"
                    )}
                    title={`Switch to ${p.title} (${p.path || p.id})`}
                  >
                    <span>{p.icon || "📄"}</span>
                    <span>{p.title}</span>
                    {p.isNew && (
                      <span className="text-[9px] px-1 py-0.2 rounded bg-[#c89666]/20 text-[#dfb180] font-bold">NEW</span>
                    )}
                  </button>
                );
              })}
              <button
                type="button"
                onClick={() => setShowAddPageModal(true)}
                className="sb-add-page-btn"
                title="Create a new subpage in this website"
              >
                <Plus className="w-3 h-3 text-[#dfb180]" />
                <span>+ Add Page</span>
              </button>
            </div>
            <div className="text-[11px] text-muted-foreground font-semibold px-2 py-0.5 rounded-md bg-muted/30 border border-border/40 shrink-0 hidden md:flex items-center gap-1">
              <span className="text-emerald-400">●</span>
              <span>Multi-Page Live Sync</span>
            </div>
          </div>

          {/* Stage Toolbar */}
          <div className="sb-stage-toolbar">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <h2 className="font-bold text-sm text-foreground flex items-center gap-2">
                <span>{currentSection.name}</span>
                <span className="text-xs text-pink-500 font-normal">
                  {viewMode === "live" ? "· Real Live Demo" : "· Designed Output View"}
                </span>
              </h2>
            </div>

            {/* Viewport Presets and Background Theme */}
            <div className="flex items-center gap-3">
              {/* Viewport Width Buttons & Device Indicators */}
              <div className="flex items-center gap-2">
                <div className="sb-viewport-switcher">
                  <button
                    type="button"
                    onClick={() => setCanvasViewport("desktop")}
                    className={cn("sb-tool-btn", canvasViewport === "desktop" && "active")}
                    title="Desktop Monitor (100% Fluid)"
                  >
                    <Monitor className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setCanvasViewport("laptop")}
                    className={cn("sb-tool-btn", canvasViewport === "laptop" && "active")}
                    title="MacBook Laptop (1024px)"
                  >
                    <Laptop className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setCanvasViewport("tablet")}
                    className={cn("sb-tool-btn", canvasViewport === "tablet" && "active")}
                    title="iPad Tablet (768px)"
                  >
                    <Tablet className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setCanvasViewport("mobile")}
                    className={cn("sb-tool-btn", canvasViewport === "mobile" && "active")}
                    title="iPhone Mobile (393px)"
                  >
                    <Smartphone className="w-3.5 h-3.5" />
                  </button>
                </div>
                <span className="text-[11px] font-semibold text-muted-foreground hidden lg:inline px-2 py-0.5 rounded-full bg-muted/60 border border-border/50 select-none">
                  {canvasViewport === "mobile" ? "iPhone 16 Pro (393 × 852)" :
                    canvasViewport === "tablet" ? "iPad Air (768 × 1024)" :
                      canvasViewport === "laptop" ? "MacBook Pro (1024 × 640)" :
                        "Desktop (Fluid)"}
                </span>
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

              {/* Desktop Right Sidebar Collapse Button */}
              {!rightSidebarCollapsed && (
                <button
                  type="button"
                  onClick={() => setRightSidebarCollapsed(true)}
                  className="hidden lg:flex sb-ghost-btn text-xs py-1 px-2 items-center gap-1 cursor-pointer"
                  title="Collapse Editor Panel"
                >
                  <span className="hidden xl:inline">Collapse</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Canvas Area with Smooth Resizing & Hardware Device Frames */}
          <div className={cn("sb-stage-canvas-area", `sb-bg-${canvasBg}`)}>
            {/* Viewport Outer Scroll & Alignment Container */}
            <div className={cn(
              "w-full h-full transition-all duration-300 flex flex-col items-center",
              canvasViewport === "desktop" ? "justify-start p-0 overflow-hidden" : "justify-start py-6 px-3 overflow-y-auto"
            )}>
              {/* Responsive Hardware Device Outer Wrapper */}
              <div
                className={cn(
                  "relative mx-auto transition-all duration-300 flex flex-col select-none",
                  canvasViewport === "mobile" && "bg-[#181d28] p-[10px] rounded-[52px] shadow-[0_25px_70px_-15px_rgba(0,0,0,0.85),0_0_0_1px_rgba(255,255,255,0.12),inset_0_0_0_2px_rgba(0,0,0,0.5)]",
                  canvasViewport === "tablet" && "bg-[#181d28] p-[14px] rounded-[38px] shadow-[0_25px_70px_-15px_rgba(0,0,0,0.85),0_0_0_1px_rgba(255,255,255,0.1)]",
                  canvasViewport === "laptop" && "w-full bg-[#0f172a] p-[10px] pb-0 rounded-t-2xl border-[2px] border-b-0 border-[#334155] shadow-2xl",
                  canvasViewport === "desktop" && "w-full h-full rounded-none border-0 shadow-none overflow-hidden bg-white"
                )}
                style={
                  canvasViewport === "mobile"
                    ? { width: "393px", height: "852px", maxWidth: "100%", maxHeight: "calc(100vh - 170px)" }
                    : canvasViewport === "tablet"
                    ? { width: "768px", height: "1024px", maxWidth: "100%", maxHeight: "calc(100vh - 170px)" }
                    : canvasViewport === "laptop"
                    ? { width: "100%", maxWidth: "1024px" }
                    : { width: "100%", height: "100%" }
                }
              >
                {/* 1. Mobile Physical Side Buttons */}
                {canvasViewport === "mobile" && (
                  <>
                    <div className="absolute -left-[12px] top-[115px] w-[3px] h-[26px] bg-slate-600 rounded-l-sm pointer-events-none" />
                    <div className="absolute -left-[12px] top-[155px] w-[3px] h-[48px] bg-slate-600 rounded-l-sm pointer-events-none" />
                    <div className="absolute -left-[12px] top-[215px] w-[3px] h-[48px] bg-slate-600 rounded-l-sm pointer-events-none" />
                    <div className="absolute -right-[12px] top-[165px] w-[3px] h-[72px] bg-slate-600 rounded-r-sm pointer-events-none" />
                  </>
                )}

                {/* 2. Laptop FaceTime Camera Notch */}
                {canvasViewport === "laptop" && (
                  <div className="absolute top-0 left-1/2 -translate-x-1/2 w-24 h-4 bg-black rounded-b-lg flex items-center justify-center gap-2 z-30 pointer-events-none">
                    <span className="w-2 h-2 rounded-full bg-[#111] border border-[#222]" />
                    <span className="w-1 h-1 rounded-full bg-emerald-500/80 shadow-[0_0_4px_#10b981]" />
                  </div>
                )}

                {/* 3. Inner Screen Display Box */}
                <div
                  className={cn(
                    "relative w-full overflow-hidden flex flex-col transition-all duration-300",
                    canvasViewport === "mobile" && "h-full bg-black rounded-[42px] border border-white/5 shadow-inner",
                    canvasViewport === "tablet" && "h-full bg-black rounded-[24px] border border-white/5 shadow-inner",
                    canvasViewport === "laptop" && "rounded-t-md bg-white shadow-inner",
                    canvasViewport === "desktop" && "h-full w-full bg-white rounded-none border-0 shadow-none"
                  )}
                  style={
                    canvasViewport === "laptop"
                      ? { height: "640px", maxHeight: "calc(100vh - 240px)" }
                      : undefined
                  }
                >
                  {/* Dynamic Island for Mobile */}
                  {canvasViewport === "mobile" && (
                    <>
                      <div className="absolute top-2.5 left-1/2 -translate-x-1/2 z-30 pointer-events-none flex items-center justify-between px-3 w-[120px] h-[26px] bg-black rounded-full border border-white/10 shadow-md">
                        <span className="w-2.5 h-2.5 rounded-full bg-[#0d131f] border border-[#1e293b]" />
                        <span className="w-2 h-2 rounded-full bg-[#052e16] border border-[#14532d]" />
                      </div>
                      <div className="absolute top-0 left-0 right-0 h-10 px-7 flex items-center justify-between text-white/90 text-[11px] font-semibold tracking-tight z-20 pointer-events-none select-none bg-gradient-to-b from-black/70 via-black/30 to-transparent">
                        <span>9:41</span>
                        <div className="flex items-center gap-1.5 text-white/80">
                          <span className="text-[10px]">5G</span>
                          <div className="w-4 h-2.5 border border-white/80 rounded-sm p-[1px] flex items-center">
                            <div className="w-full h-full bg-white rounded-2xs" />
                          </div>
                        </div>
                      </div>
                    </>
                  )}

                  {/* iPad Status Bar & Camera Dot for Tablet */}
                  {canvasViewport === "tablet" && (
                    <>
                      <div className="absolute top-[6px] left-1/2 -translate-x-1/2 z-30 pointer-events-none">
                        <div className="w-2.5 h-2.5 rounded-full bg-black border border-white/20" />
                      </div>
                      <div className="h-7 px-5 flex items-center justify-between text-white/80 text-[11px] font-semibold tracking-tight z-20 pointer-events-none select-none bg-gradient-to-b from-black/60 to-transparent">
                        <span>iPad &bull; 9:41 AM</span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px]">100%</span>
                          <div className="w-4 h-2.5 border border-white/80 rounded-sm p-[1px] flex items-center">
                            <div className="w-full h-full bg-emerald-400 rounded-2xs" />
                          </div>
                        </div>
                      </div>
                    </>
                  )}

                  {/* ── Screen Content Viewport (PERSISTENT IFRAME - NEVER RELOADS ON RESIZE) ── */}
                  <div
                    className={cn(
                      "w-full h-full overflow-hidden bg-white transition-all duration-300 flex-1",
                      canvasViewport === "mobile" && "pt-8 pb-3",
                      canvasViewport === "tablet" && "pb-2",
                      canvasViewport === "desktop" && "p-0 m-0"
                    )}
                  >
                    {viewMode === "live" && liveServerUrl ? (
                      <iframe
                        key={`${iframeKey}-${activePage}`}
                        src={liveServerUrl}
                        title="Live Demo Preview"
                        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
                        referrerPolicy="no-referrer"
                        className="w-full h-full border-none bg-white"
                      />
                    ) : (
                      <div className="w-full h-full overflow-y-auto">
                        {renderDesignedOutputView(currentSection.id, currentProps)}
                      </div>
                    )}
                  </div>

                  {/* Mobile Home Indicator */}
                  {canvasViewport === "mobile" && (
                    <div className="absolute bottom-1.5 left-1/2 -translate-x-1/2 z-30 pointer-events-none">
                      <div className="w-32 h-1 bg-white/50 rounded-full shadow-sm" />
                    </div>
                  )}

                  {/* Tablet Home Indicator */}
                  {canvasViewport === "tablet" && (
                    <div className="absolute bottom-1 left-1/2 -translate-x-1/2 z-30 pointer-events-none">
                      <div className="w-40 h-1 bg-white/40 rounded-full" />
                    </div>
                  )}
                </div>

                {/* Laptop Chassis Base Deck */}
                {canvasViewport === "laptop" && (
                  <div className="relative w-[104%] -ml-[2%] h-4 bg-gradient-to-b from-[#334155] via-[#1e293b] to-[#0f172a] rounded-b-xl border-t border-[#475569] shadow-2xl flex items-center justify-center pointer-events-none">
                    <div className="w-24 h-1.5 bg-[#475569] rounded-full shadow-inner -mt-1" />
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>

        {/* ─────────────────────────────────────────────────────────────────────
           RIGHT COLUMN:
             IF editorMode === "manual": Shows Template's Actual Components & Fields
             IF editorMode === "ai": Shows AI Prompt Assistant
        ───────────────────────────────────────────────────────────────────── */}
        <aside className={cn(
          "sb-sidebar-right transition-all duration-300",
          rightSidebarCollapsed && "w-0 min-w-0 border-0 p-0 overflow-hidden",
          mobilePanel !== "edit" && "sb-mobile-hidden"
        )}>
          {editorMode === "manual" ? (
            /* MANUAL EDIT PANEL: Template-Accurate Component Fields */
            <div className="flex flex-col h-full overflow-hidden">
              {/* Panel Header */}
              <div className="p-4 border-b border-border/50 bg-card/60 flex-shrink-0 flex items-center justify-between select-none">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between pr-2">
                    <h3 className="font-extrabold text-sm text-foreground flex items-center gap-1.5 min-w-0">
                      <Sliders className="w-4 h-4 text-pink-500 shrink-0" />
                      <span className="font-extrabold">{currentSection.name}</span>
                    </h3>
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => handleSaveSingleSection(currentSection.id)}
                        disabled={savingManual}
                        className="py-1 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center gap-1.5 shadow-sm cursor-pointer transition-all disabled:opacity-50"
                        title={`Save only ${currentSection.name} section`}
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Save Section</span>
                      </button>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">
                        Live Synced
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-1 leading-normal">
                    Click any field to edit. Use backspace &amp; typing to update live.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setRightSidebarCollapsed(true)}
                  className="hidden lg:flex p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer shrink-0 ml-1"
                  title="Collapse Editor Sidebar"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Status & Quick Action Banner */}
              {hasUnfinalizedChanges && (
                <div className="p-3 bg-amber-500/10 border-b border-amber-500/20 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                    <div>
                      <p className="text-[11px] font-bold text-amber-400 leading-tight">Testing Live Edits</p>
                      <p className="text-[10px] text-muted-foreground truncate">Verify in preview before finalizing</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={() => handleFinalizeChanges(false)}
                      disabled={savingManual || savingWithAi}
                      className="py-1 px-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[10px] flex items-center gap-1 shadow cursor-pointer transition-all disabled:opacity-50"
                      title="Fast direct save: Saves your edits directly into HTML/CSS files without invoking AI"
                    >
                      <Check className="w-3 h-3" />
                      <span>{savingManual ? "Saving..." : "Save"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleFinalizeChanges(true)}
                      disabled={savingManual || savingWithAi}
                      className="py-1 px-2 rounded-lg bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] font-bold text-[10px] flex items-center gap-1 shadow cursor-pointer border border-[#c89666]/30 transition-all disabled:opacity-50"
                      title="Deep Synthesis Save: Scans and verifies the entire codebase"
                    >
                      <Sparkles className={`w-3 h-3 text-amber-300 ${savingWithAi ? "animate-spin" : ""}`} />
                      <span>{savingWithAi ? "Synthesizing..." : "Deep Save"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleRevokeChanges}
                      disabled={isRevoking || savingManual || savingWithAi}
                      className="py-1 px-2 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 font-bold text-[10px] flex items-center gap-1 cursor-pointer transition-all disabled:opacity-50"
                      title="Revoke all changes and revert back to original state"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Revoke</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Editable Component Fields with Template-Accurate Names */}
              <div className="sb-right-content-body space-y-4 flex-1 overflow-y-auto p-4 pb-28">
                {renderFriendlyFields(currentSection.id, currentProps, handleFieldChange, effectiveTemplateId, handleApplyThemeColorToProject)}

                {/* Row Actions */}
                <div className="pt-4 border-t border-border/50 space-y-2">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleSaveSingleSection(currentSection.id)}
                      disabled={savingManual}
                      className="flex-1 py-2 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center justify-center gap-1.5 transition-all shadow-sm cursor-pointer disabled:opacity-50"
                      title={`Save ${currentSection.name} section to project`}
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Save This Section</span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleEraseSectionContent(currentSection.id, e)}
                      className="py-2 px-3 rounded-xl bg-muted/50 hover:bg-amber-500/15 text-amber-400 border border-border text-xs font-bold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                    >
                      <Eraser className="w-3.5 h-3.5" />
                      <span>Clear Text</span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleDeleteSection(currentSection.id, e)}
                      className="py-2 px-3 rounded-xl bg-muted/50 hover:bg-rose-500/15 text-rose-400 border border-border text-xs font-bold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Delete</span>
                    </button>
                  </div>

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
                        className="w-full py-2 px-3 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-60 cursor-pointer"
                      >
                        <ShoppingCart className="w-3.5 h-3.5" />
                        {addedToCart || isInCart?.(activeTemplateId) ? "In Cart ✓" : "Add to Cart"}
                      </button>
                      <button
                        type="button"
                        onClick={handleBuyNow}
                        className="w-full py-2 px-3 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white text-xs font-bold flex items-center justify-center gap-2 transition-all shadow-lg shadow-amber-500/20 cursor-pointer"
                      >
                        <ShoppingBag className="w-3.5 h-3.5" />
                        Buy Now — Go to Checkout
                      </button>
                      <button
                        type="button"
                        onClick={() => navigate("/dashboard")}
                        className="w-full py-2 px-3 rounded-xl border border-border bg-muted/40 hover:bg-muted/70 text-muted-foreground text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer"
                      >
                        <ArrowUpRight className="w-3.5 h-3.5" />
                        View My Dashboard
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* DOCKED STICKY BOTTOM ACTION BAR (Always visible at all times!) */}
              <div className="p-3 bg-card/95 backdrop-blur-md border-t border-border/60 shrink-0 z-20 space-y-1.5">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleSaveAllSections}
                    disabled={savingManual}
                    className="flex-1 py-2.5 px-3 rounded-xl bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] font-bold text-xs shadow-lg shadow-emerald-500/25 flex items-center justify-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
                    title="Save and permanently finalize all sections across the entire website at once"
                  >
                    <Zap className="w-4 h-4 fill-amber-300 text-amber-300" />
                    <span>{savingManual ? "Saving All Sections..." : "Save All Sections at Once"}</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleRevokeChanges}
                    disabled={isRevoking || !hasUnfinalizedChanges}
                    className="py-2.5 px-3 rounded-xl border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-bold text-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer disabled:opacity-40"
                    title="Revoke all changes and revert back to original state"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Revoke</span>
                  </button>
                </div>
              </div>
            </div>
          ) : editorMode === "assets" ? (
            /* REPLACE PHOTOS & MEDIA PANEL */
            <div className="flex flex-col h-full overflow-hidden">
              <div className="p-3.5 border-b border-border/50 bg-card/60 flex-shrink-0 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => setEditorMode("manual")}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-pink-500/15 hover:bg-pink-500/25 text-pink-400 border border-pink-500/30 text-xs font-bold transition-all shadow-sm cursor-pointer group"
                    title="Return to Section Content Editor"
                  >
                    <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
                    <span>Back to Content Editor</span>
                  </button>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 shrink-0">
                    {projectAssets.length} Images Detected
                  </span>
                </div>
                <div className="flex items-center gap-1.5 pt-0.5">
                  <Image className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span className="font-extrabold text-xs text-foreground">Replace Photos &amp; Media</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-tight">
                  Click any image to replace it with your own photo. Or click any section in the sidebar to return to content editing.
                </p>
              </div>

              {hasUnfinalizedChanges && (
                <div className="p-3 bg-amber-500/10 border-b border-amber-500/20 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span className="text-[11px] font-bold text-amber-400 truncate">Testing Photo Replacements</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={() => handleFinalizeChanges(false)}
                      disabled={savingManual || savingWithAi}
                      className="py-1 px-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[10px] flex items-center gap-1 shadow cursor-pointer transition-all disabled:opacity-50"
                      title="Save photo changes"
                    >
                      <Check className="w-3 h-3" />
                      <span>{savingManual ? "Saving..." : "Save"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleRevokeChanges}
                      disabled={isRevoking || savingManual || savingWithAi}
                      className="py-1 px-2 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 font-bold text-[10px] flex items-center gap-1 cursor-pointer transition-all disabled:opacity-50"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Revoke</span>
                    </button>
                  </div>
                </div>
              )}

              <div className="sb-right-content-body space-y-3 flex-1 overflow-y-auto p-4">
                {loadingAssets ? (
                  <div className="flex items-center justify-center p-8 text-xs text-muted-foreground gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
                    <span>Scanning project images...</span>
                  </div>
                ) : projectAssets.length === 0 ? (
                  <div className="text-center p-6 text-xs text-muted-foreground border border-dashed border-border rounded-xl">
                    <Image className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
                    <p className="font-semibold text-foreground">No media assets found</p>
                    <p className="text-[11px] mt-1">This template may use external CDN images or SVG icons.</p>
                  </div>
                ) : (
                  projectAssets.map((asset, idx) => (
                    <div key={idx} className="p-3 rounded-xl border border-border/70 bg-card/50 hover:border-emerald-500/40 transition-all space-y-2">
                      <div className="flex items-center gap-3">
                        <div className="w-14 h-14 rounded-lg overflow-hidden bg-black/40 border border-border flex items-center justify-center shrink-0">
                          <img
                            key={`${asset.rel_path}-${assetTimestamp}-${asset.timestamp || ""}`}
                            src={`${API_BASE}/preview/live/${templateId}/${asset.rel_path}?t=${asset.timestamp || assetTimestamp}`}
                            alt={asset.filename}
                            className="w-full h-full object-cover"
                            onError={(e) => { e.target.style.display = 'none'; }}
                          />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-foreground truncate">{asset.filename}</p>
                          <p className="text-[10px] text-muted-foreground truncate font-mono">{asset.rel_path}</p>
                          <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                            {asset.width && asset.height && <span>{asset.width} × {asset.height}</span>}
                            <span className="capitalize px-1.5 py-0.2 rounded bg-muted text-muted-foreground font-semibold">{asset.role || "Image"}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleTriggerReplaceAsset(asset)}
                          disabled={replacingAssetPath === asset.rel_path || restoringAssetPath === asset.rel_path}
                          className="flex-1 py-1.5 px-3 rounded-lg border border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
                        >
                          {replacingAssetPath === asset.rel_path ? (
                            <>
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                              <span>Uploading...</span>
                            </>
                          ) : (
                            <>
                              <Upload className="w-3.5 h-3.5" />
                              <span>Replace This Photo</span>
                            </>
                          )}
                        </button>

                        {(asset.has_backup || replacedAssetPaths.has(asset.rel_path)) && (
                          <button
                            type="button"
                            onClick={() => handleRestoreAsset(asset)}
                            disabled={restoringAssetPath === asset.rel_path || replacingAssetPath === asset.rel_path}
                            className="py-1.5 px-3 rounded-lg border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 text-xs font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer shrink-0 disabled:opacity-50"
                            title="Return photo back to original template state"
                          >
                            {restoringAssetPath === asset.rel_path ? (
                              <>
                                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                <span>Returning...</span>
                              </>
                            ) : (
                              <>
                                <RotateCcw className="w-3.5 h-3.5" />
                                <span>Return</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}

                <div className="pt-4 border-t border-border/50 space-y-2">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleFinalizeChanges}
                      disabled={savingManual || !hasUnfinalizedChanges}
                      className="flex-1 py-2.5 px-4 rounded-xl bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] font-bold text-xs shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-40"
                    >
                      <Check className="w-4 h-4" />
                      <span>Save &amp; Finalize Photos</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleRevokeChanges}
                      disabled={isRevoking || !hasUnfinalizedChanges}
                      className="py-2.5 px-3 rounded-xl border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-bold text-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer disabled:opacity-40"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>Revoke</span>
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => setEditorMode("manual")}
                    className="w-full py-2.5 px-3 rounded-xl border border-border bg-muted/40 hover:bg-muted/70 text-muted-foreground hover:text-foreground text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" />
                    <span>Back to Content Editor</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* AI EDIT PANEL: Full-Height Prompt Assistant with Bottom Message Sender */
            <div className="flex flex-col h-full overflow-hidden bg-card/40">
              {/* Header */}
              <div className="p-3.5 border-b border-border/50 bg-card/70 flex-shrink-0 space-y-2 select-none">
                <div className="flex items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => setEditorMode("manual")}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-pink-500/10 hover:bg-pink-500/20 text-pink-400 border border-pink-500/25 text-xs font-bold transition-all shadow-sm cursor-pointer group"
                    title="Return to Section Content Editor"
                  >
                    <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
                    <span>Content Editor</span>
                  </button>
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#c89666]/15 border border-[#c89666]/25 text-[#dfb180] text-[11px] font-bold">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <span>AI Ready</span>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-0.5">
                  <div className="flex items-center gap-1.5">
                    <div className="w-6 h-6 rounded-lg bg-[#c89666]/20 border border-[#c89666]/30 flex items-center justify-center text-[#dfb180]">
                      <Sparkles className="w-3.5 h-3.5" />
                    </div>
                    <h3 className="font-extrabold text-xs text-foreground tracking-tight">AI Prompt Assistant</h3>
                  </div>
                  {aiHistory.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setAiHistory([
                        {
                          id: "init",
                          role: "assistant",
                          text: "Hello! Tell me any changes you'd like to make, and I will refactor your template code and update the live demo in real time.",
                          timestamp: "Just now"
                        }
                      ])}
                      className="text-[10px] text-muted-foreground hover:text-foreground font-semibold px-2 py-0.5 rounded hover:bg-muted/50 transition-colors cursor-pointer"
                      title="Clear chat history"
                    >
                      Clear Chat
                    </button>
                  )}
                </div>
              </div>

              {/* Status / Unfinalized Changes Bar */}
              {hasUnfinalizedChanges && (
                <div className="p-2.5 px-3.5 bg-amber-500/10 border-b border-amber-500/20 flex items-center justify-between gap-2 flex-shrink-0 animate-in fade-in">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                    <span className="text-[11px] font-bold text-amber-400 truncate">Testing Synthesis Changes</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={() => handleFinalizeChanges(false)}
                      disabled={savingManual || savingWithAi}
                      className="py-1 px-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[10px] flex items-center gap-1 shadow cursor-pointer transition-all disabled:opacity-50"
                      title="Fast direct save: Saves your edits directly into files instantly"
                    >
                      <Check className="w-3 h-3" />
                      <span>{savingManual ? "Saving..." : "Save"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleFinalizeChanges(true)}
                      disabled={savingManual || savingWithAi}
                      className="py-1 px-2.5 rounded-lg bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] font-bold text-[10px] flex items-center gap-1 shadow cursor-pointer border border-[#c89666]/30 transition-all disabled:opacity-50"
                      title="Deep Synthesis Save: Scans and verifies the entire codebase"
                    >
                      <Sparkles className={`w-3 h-3 text-amber-300 ${savingWithAi ? "animate-spin" : ""}`} />
                      <span>{savingWithAi ? "Synthesizing..." : "Deep Save"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleRevokeChanges}
                      disabled={isRevoking || savingManual || savingWithAi}
                      className="py-1 px-2 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 font-bold text-[10px] flex items-center gap-1 cursor-pointer transition-all disabled:opacity-50"
                      title="Revert back to original code"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Revoke</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Middle Chat Area: Full-Height Scrollable Conversation Stream */}
              <div className="flex-1 overflow-y-auto p-3.5 space-y-3.5 min-h-0">
                {aiHistory.map((item) => (
                  item.id === "init" ? (
                    <div key={item.id} className="p-3.5 rounded-2xl bg-card/80 border border-border/80 text-foreground space-y-3 shadow-sm">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-lg bg-[#c89666] flex items-center justify-center text-white shadow-sm shrink-0">
                          <Bot className="w-3.5 h-3.5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-bold text-foreground">AI Code Assistant</div>
                          <div className="text-[10px] text-muted-foreground">Ready to edit template live in canvas</div>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Describe any changes in natural language. I will modify the template source code and update the center preview in real time.
                      </p>
                      <div className="space-y-1.5 pt-1 border-t border-border/40">
                        <span className="text-[10px] font-bold uppercase text-muted-foreground/80 block">Quick Suggestions:</span>
                        <div className="flex flex-col gap-1">
                          {[
                            "Change color theme to royal dark red",
                            "Change headline to Jordan Cole",
                            "Make background dark and buttons rounded",
                            "Add 3 new feature cards"
                          ].map((suggestion, sIdx) => (
                            <button
                              key={sIdx}
                              type="button"
                              onClick={() => {
                                setAiInput(suggestion);
                              }}
                              className="text-left text-[11px] px-2.5 py-1.5 rounded-lg bg-muted/40 hover:bg-[#c89666]/15 hover:text-[#dfb180] border border-border/60 hover:border-[#c89666]/30 text-foreground transition-all flex items-center gap-1.5 cursor-pointer"
                            >
                              <Sparkles className="w-2.5 h-2.5 text-[#dfb180] shrink-0" />
                              <span className="truncate">{suggestion}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div
                      key={item.id}
                      className={cn(
                        "flex flex-col text-xs leading-relaxed max-w-[90%]",
                        item.role === "assistant"
                          ? "mr-auto items-start"
                          : "ml-auto items-end"
                      )}
                    >
                      <div className="flex items-center gap-1.5 text-[10px] font-bold text-muted-foreground mb-1 px-1">
                        {item.role === "assistant" ? (
                          <>
                            <Sparkles className="w-3 h-3 text-[#dfb180]" />
                            <span>AI Assistant</span>
                          </>
                        ) : (
                          <span>You</span>
                        )}
                        <span className="text-muted-foreground/50 font-normal">• {item.timestamp}</span>
                      </div>

                      <div
                        className={cn(
                          "p-3 rounded-2xl shadow-sm text-xs font-normal whitespace-pre-wrap break-words",
                          item.role === "assistant"
                            ? "bg-muted/70 border border-border/80 text-foreground rounded-tl-xs"
                            : "bg-gradient-to-r from-[#c89666] to-[#b5804f] text-[#09090b] border border-[#c89666]/40 rounded-tr-xs shadow-black/40"
                        )}
                      >
                        {item.text}
                      </div>
                    </div>
                  )
                ))}

                {/* AI Refactoring / Thinking Spinner */}
                {isAiProcessing && (
                  <div className="mr-auto items-start max-w-[90%] space-y-1">
                    <div className="flex items-center gap-1.5 text-[10px] font-bold text-[#dfb180] px-1">
                      <Sparkles className="w-3 h-3 animate-spin" />
                      <span>AI Code Engine</span>
                    </div>
                    <div className="p-3 rounded-2xl rounded-tl-xs bg-[#c89666]/10 border border-[#c89666]/30 text-[#f4ecdf] text-xs flex items-center gap-2.5 shadow-sm animate-pulse">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#dfb180] flex-shrink-0" />
                      <div>
                        <div className="font-semibold">Refactoring template code...</div>
                        <div className="text-[10px] text-[#dfb180]/80">Updating live preview in center canvas</div>
                      </div>
                    </div>
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Bottom Message Sender: Docked at bottom */}
              <div className="p-3 pb-4 border-t border-border/60 bg-card/95 backdrop-blur-md flex-shrink-0 space-y-2">
                <div className="flex items-end gap-2 bg-background/90 border border-border/80 focus-within:border-[#c89666]/80 focus-within:ring-1 focus-within:ring-[#c89666]/30 rounded-2xl p-2 pl-3 shadow-inner transition-all">
                  <textarea
                    rows={1}
                    placeholder="Describe changes to synthesize..."
                    value={aiInput}
                    onChange={(e) => {
                      setAiInput(e.target.value);
                      e.target.style.height = "auto";
                      e.target.style.height = Math.min(e.target.scrollHeight, 80) + "px";
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        executeAiPrompt();
                      }
                    }}
                    disabled={isAiProcessing}
                    className="flex-1 bg-transparent border-0 outline-none resize-none text-xs text-foreground placeholder:text-muted-foreground/60 py-1 min-h-[32px] max-h-[80px] leading-relaxed"
                  />
                  <button
                    type="button"
                    onClick={() => executeAiPrompt()}
                    disabled={!aiInput.trim() || isAiProcessing}
                    className="h-8 w-8 rounded-xl bg-[#c89666] hover:bg-[#dfb180] text-white flex items-center justify-center shrink-0 shadow transition-all disabled:opacity-30 disabled:hover:bg-[#c89666] cursor-pointer"
                    title="Send (Enter ↵)"
                  >
                    {isAiProcessing ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Send className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
                <div className="flex items-center justify-between text-[10px] text-muted-foreground/75 px-1 font-mono">
                  <span>↵ Send</span>
                  <span>Shift + ↵ New line</span>
                </div>
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* Hidden File Input for Image Replacements */}
      <input
        type="file"
        ref={assetFileInputRef}
        onChange={handleAssetFileSelected}
        accept="image/*"
        className="hidden"
      />

      {/* Exit Confirmation Modal: Revoke vs Finalize */}
      {showExitConfirmModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-card border border-border/80 rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4 animate-in zoom-in-95">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 mx-auto">
              <AlertCircle className="w-6 h-6" />
            </div>
            <div className="text-center space-y-1">
              <h3 className="font-extrabold text-base text-foreground">Unfinalized Changes Detected</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                You have modified elements in the live preview that have not been finalized. Would you like to finalize and save them, or revoke all changes to return to the original state?
              </p>
            </div>

            <div className="space-y-2 pt-2">
              <button
                type="button"
                onClick={handleFinalizeAndExit}
                disabled={savingManual}
                className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] font-bold text-xs flex items-center justify-center gap-2 shadow-lg transition-all cursor-pointer"
              >
                <Check className="w-4 h-4" />
                <span>{savingManual ? "Saving..." : "Finalize & Save Changes, Then Exit"}</span>
              </button>

              <button
                type="button"
                onClick={handleRevokeAndExit}
                disabled={isRevoking}
                className="w-full py-2.5 px-4 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Revoke All Changes &amp; Exit to Marketplace</span>
              </button>

              <button
                type="button"
                onClick={() => setShowExitConfirmModal(false)}
                className="w-full py-2 px-4 rounded-xl border border-border bg-muted/40 hover:bg-muted text-muted-foreground text-xs font-semibold flex items-center justify-center gap-1 transition-all cursor-pointer"
              >
                <span>Keep Editing</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Multi-Page: Add Subpage Modal */}
      {showAddPageModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border/80 rounded-2xl shadow-2xl max-w-md w-full p-5 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-border/40 pb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-[#c89666]/15 border border-[#c89666]/30 flex items-center justify-center text-[#dfb180]">
                  <Plus className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-foreground">Add New Subpage</h3>
                  <p className="text-[11px] text-muted-foreground">Synthesize a new page route into your studio workspace</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowAddPageModal(false)}
                className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-muted-foreground mb-1.5">Page Title</label>
                <input
                  type="text"
                  value={newPageName}
                  onChange={(e) => setNewPageName(e.target.value)}
                  maxLength={50}
                  placeholder="e.g. Careers, Blog, FAQ, Features..."
                  className="sb-control-input text-xs w-full"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-muted-foreground mb-1.5">Page Preset / Blueprint</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: "content", label: "📄 Content / Story", desc: "Hero, story cards, text" },
                    { id: "features", label: "⚙️ Features & Grid", desc: "Bento cards, feature specs" },
                    { id: "pricing", label: "💳 Pricing & Plans", desc: "Tiers, FAQ, comparison" },
                    { id: "contact", label: "✉️ Contact & Lead Form", desc: "Form, map, direct info" },
                  ].map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => setNewPagePreset(preset.id)}
                      className={cn(
                        "p-2.5 rounded-xl border text-left transition-all text-xs",
                        newPagePreset === preset.id
                          ? "border-[#c89666] bg-[#c89666]/10 text-[#dfb180] font-bold"
                          : "border-border/60 hover:bg-muted/40 text-muted-foreground"
                      )}
                    >
                      <div className="font-semibold text-foreground">{preset.label}</div>
                      <div className="text-[10px] text-muted-foreground mt-0.5">{preset.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/40">
              <button
                type="button"
                onClick={() => setShowAddPageModal(false)}
                className="sb-ghost-btn text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmAddPage}
                disabled={!newPageName.trim()}
                className="sb-primary-gradient-btn text-xs disabled:opacity-50"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create Subpage</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function renderDesignedOutputView(sectionId, props) {
  const themeColor = props.themeColor || "#b5804f";
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
            "w-full px-5 sm:px-7 py-3.5 sm:py-4 rounded-2xl border flex items-center justify-between gap-4 shadow-2xl transition-all",
            props.stickyGlass ? "bg-card/85 backdrop-blur-xl border-border/80 shadow-black/10" : "bg-card border-border shadow-md"
          )}
        >
          {/* Left: Brand Monogram & Title */}
          <div className="flex items-center gap-3 min-w-0 flex-shrink-0">
            {props.logoText ? (
              <div
                className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center font-black text-xs sm:text-sm text-white shadow-lg tracking-wider uppercase flex-shrink-0"
                style={{
                  background: `linear-gradient(135deg, ${themeColor}, #0ea5e9)`,
                  boxShadow: `0 4px 14px ${themeColor}40`
                }}
              >
                {props.logoText.slice(0, 5)}
              </div>
            ) : null}
            <span className="font-extrabold text-sm sm:text-base tracking-tight text-foreground truncate block">
              {props.brandName || "Website Studio"}
            </span>
          </div>

          {/* Center: Dynamic Nav Links */}
          {navLinks.length > 0 && (
            <div className="hidden md:flex items-center gap-1 px-3 py-1.5 rounded-xl bg-muted/40 border border-border/40 text-xs font-semibold text-muted-foreground">
              {navLinks.map((lnk, i) => (
                <span
                  key={i}
                  className="px-3 py-1 rounded-lg hover:text-foreground hover:bg-background/80 transition-all cursor-pointer whitespace-nowrap"
                >
                  {lnk}
                </span>
              ))}
            </div>
          )}

          {/* Right: CTA Button */}
          <div className="flex items-center gap-3 flex-shrink-0">
            {props.ctaText ? (
              <button
                type="button"
                className="px-4 sm:px-5 py-2 sm:py-2.5 rounded-xl text-white font-bold text-xs shadow-lg transition-all hover:scale-105 active:scale-95 flex items-center gap-1.5"
                style={{
                  backgroundColor: themeColor,
                  boxShadow: `0 4px 16px ${themeColor}50`,
                  whiteSpace: "nowrap"
                }}
              >
                <span>{props.ctaText}</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            ) : null}
          </div>
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
            <span className="text-primary font-semibold">Site Studio</span>
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
      <div className="space-y-3">
        {props.badgeText && (
          <span className="text-xs font-bold text-pink-500 uppercase tracking-widest inline-block px-2.5 py-0.5 rounded bg-pink-500/10 border border-pink-500/20">{props.badgeText}</span>
        )}
        <h2 className="text-2xl sm:text-3xl font-black text-foreground tracking-tight">{props.title || props.headline || "Section"}</h2>
        {(props.subtitle || props.subheadline) && (
          <p className="text-xs sm:text-sm font-semibold text-pink-400 font-mono tracking-wide">
            {props.subtitle || props.subheadline}
          </p>
        )}
        {(props.story || props.description) && (
          <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
            {props.story || props.description}
          </p>
        )}
      </div>

      {/* Render Extracted Text Items / Records / Capabilities */}
      {Array.isArray(props.textItems) && props.textItems.length > 0 && (
        <div className="pt-6 border-t border-border/50 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-foreground uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-pink-500" />
              Extracted Template Items ({props.textItems.length})
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {props.textItems.map((ti, tIdx) => (
              <div
                key={ti.id || tIdx}
                className="p-4 rounded-xl border border-border bg-card/70 hover:border-pink-500/50 shadow-sm transition-all space-y-1.5"
              >
                <div className="flex items-center justify-between text-[11px]">
                  <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border font-mono font-bold text-[10px]">
                    {ti.label || "ITEM"}
                  </span>
                  <span className="text-muted-foreground/60 text-[10px] font-mono">#{tIdx + 1}</span>
                </div>
                <p className="text-xs font-bold text-foreground break-words leading-snug">{ti.text || "—"}</p>
              </div>
            ))}
          </div>
        </div>
      )}

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

// ─────────────────────────────────────────────────────────────────────────────
// Color System & Conversion Utilities
// ─────────────────────────────────────────────────────────────────────────────
function hexToRgb(hex) {
  if (!hex) return { r: 79, g: 70, b: 229 };
  let h = hex.trim().replace(/^#/, "");
  if (h.length === 3) {
    h = h.split("").map((c) => c + c).join("");
  }
  if (h.length < 6) return { r: 79, g: 70, b: 229 };
  const num = parseInt(h.substring(0, 6), 16);
  if (isNaN(num)) return { r: 79, g: 70, b: 229 };
  return {
    r: (num >> 16) & 255,
    g: (num >> 8) & 255,
    b: num & 255,
  };
}

function rgbToHex(r, g, b) {
  const toHex = (n) => {
    const clamped = Math.max(0, Math.min(255, Math.round(Number(n) || 0)));
    return clamped.toString(16).padStart(2, "0");
  };
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function rgbToHsl(r, g, b) {
  const rNorm = Math.max(0, Math.min(255, r)) / 255;
  const gNorm = Math.max(0, Math.min(255, g)) / 255;
  const bNorm = Math.max(0, Math.min(255, b)) / 255;
  const max = Math.max(rNorm, gNorm, bNorm);
  const min = Math.min(rNorm, gNorm, bNorm);
  const delta = max - min;

  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (delta !== 0) {
    s = l > 0.5 ? delta / (2 - max - min) : delta / (max + min);
    if (max === rNorm) {
      h = ((gNorm - bNorm) / delta + (gNorm < bNorm ? 6 : 0)) / 6;
    } else if (max === gNorm) {
      h = ((bNorm - rNorm) / delta + 2) / 6;
    } else {
      h = ((rNorm - gNorm) / delta + 4) / 6;
    }
  }

  return {
    h: Math.round(h * 360),
    s: Math.round(s * 100),
    l: Math.round(l * 100),
  };
}

function hslToRgb(h, s, l) {
  const hNorm = (((Number(h) % 360) + 360) % 360) / 360;
  const sNorm = Math.max(0, Math.min(100, Number(s) || 0)) / 100;
  const lNorm = Math.max(0, Math.min(100, Number(l) || 0)) / 100;

  if (sNorm === 0) {
    const val = Math.round(lNorm * 255);
    return { r: val, g: val, b: val };
  }

  const hue2rgb = (p, q, t) => {
    let tt = t;
    if (tt < 0) tt += 1;
    if (tt > 1) tt -= 1;
    if (tt < 1 / 6) return p + (q - p) * 6 * tt;
    if (tt < 1 / 2) return q;
    if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6;
    return p;
  };

  const q = lNorm < 0.5 ? lNorm * (1 + sNorm) : lNorm + sNorm - lNorm * sNorm;
  const p = 2 * lNorm - q;

  return {
    r: Math.round(hue2rgb(p, q, hNorm + 1 / 3) * 255),
    g: Math.round(hue2rgb(p, q, hNorm) * 255),
    b: Math.round(hue2rgb(p, q, hNorm - 1 / 3) * 255),
  };
}

function normalizeToHex(input) {
  if (!input) return "#b5804f";
  const str = input.trim();
  if (str.startsWith("#")) {
    const raw = str.replace(/[^0-9a-fA-F]/g, "");
    if (raw.length === 3) {
      return "#" + raw.split("").map((c) => c + c).join("").toLowerCase();
    }
    if (raw.length >= 6) {
      return "#" + raw.substring(0, 6).toLowerCase();
    }
    return str;
  }
  const rgbMatch = str.match(/rgba?\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})/i);
  if (rgbMatch) {
    return rgbToHex(rgbMatch[1], rgbMatch[2], rgbMatch[3]);
  }
  const hslMatch = str.match(/hsla?\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})%?\s*,\s*(\d{1,3})%?/i);
  if (hslMatch) {
    const { r, g, b } = hslToRgb(hslMatch[1], hslMatch[2], hslMatch[3]);
    return rgbToHex(r, g, b);
  }
  if (/^[0-9a-fA-F]{6}$/.test(str)) {
    return "#" + str.toLowerCase();
  }
  if (/^[0-9a-fA-F]{3}$/.test(str)) {
    return "#" + str.split("").map((c) => c + c).join("").toLowerCase();
  }
  return str;
}

function getFormattedColor(hex, format) {
  const cleanHex = normalizeToHex(hex);
  const rgb = hexToRgb(cleanHex);
  if (format === "RGB") {
    return `rgb(${rgb.r}, ${rgb.g}, ${rgb.b})`;
  }
  if (format === "HSL") {
    const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    return `hsl(${hsl.h}, ${hsl.s}%, ${hsl.l}%)`;
  }
  return cleanHex.toUpperCase();
}

// 12 Curated Vibrant Modern Web Palette Colors
const ADDITIONAL_COLOR_SWATCHES = [
  { name: "Emerald", hex: "#10b981", tag: "Success Emerald" },
  { name: "Royal Violet", hex: "#d4a373", tag: "Vibrant Violet" },
  { name: "Rose Pink", hex: "#ec4899", tag: "Modern Rose" },
  { name: "Sunset Amber", hex: "#f59e0b", tag: "Warm Gold" },
  { name: "Coral Orange", hex: "#f97316", tag: "Sunset Coral" },
  { name: "Crimson Red", hex: "#e11d48", tag: "Vivid Crimson" },
  { name: "Electric Blue", hex: "#2563eb", tag: "Tech Blue" },
  { name: "Cyan Aqua", hex: "#06b6d4", tag: "Neon Cyan" },
  { name: "Slate Navy", hex: "#1e293b", tag: "Dark Slate" },
  { name: "Obsidian", hex: "#09090b", tag: "Obsidian Black" },
  { name: "Plum Purple", hex: "#c89666", tag: "Deep Purple" },
  { name: "Classic Ruby", hex: "#c4222c", tag: "Classic Ruby" },
];

/**
 * Enhanced ThemeColorPicker — Supports Application Primary & Secondary presets,
 * 12 Curated Colors, and Format Switching (HEX, RGB, HSL).
 */
function ThemeColorPicker({
  value,
  onChange,
  label = "Theme Accent Color",
  templateId = null,
  onApplyColor = null
}) {
  const currentColor = value || "#b5804f";
  const [format, setFormat] = useState("HEX"); // "HEX" | "RGB" | "HSL"
  const [copied, setCopied] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [isApplied, setIsApplied] = useState(false);
  const [localInput, setLocalInput] = useState(() => getFormattedColor(currentColor, "HEX"));

  useEffect(() => {
    setLocalInput(getFormattedColor(currentColor, format));
  }, [currentColor, format]);

  const handleFormatChange = (fmt) => {
    setFormat(fmt);
    setLocalInput(getFormattedColor(currentColor, fmt));
  };

  const handleInputChange = (e) => {
    const raw = e.target.value;
    setLocalInput(raw);
    const parsedHex = normalizeToHex(raw);
    if (/^#[0-9a-fA-F]{6}$/.test(parsedHex)) {
      onChange("themeColor", parsedHex);
      dispatchLiveIframeColor(parsedHex);
    }
  };

  const handleInputBlur = () => {
    setLocalInput(getFormattedColor(currentColor, format));
  };

  const handleSelectColor = (hex) => {
    const cleanHex = normalizeToHex(hex);
    onChange("themeColor", cleanHex);
    setLocalInput(getFormattedColor(cleanHex, format));
    dispatchLiveIframeColor(cleanHex);
  };

  const handleApplyColorToCode = async (hexToApply) => {
    const cleanHex = normalizeToHex(hexToApply || currentColor);
    setIsApplying(true);
    try {
      if (onApplyColor) {
        await onApplyColor(cleanHex);
      } else if (templateId && templateId !== "default") {
        await api.post(`/preview/live/${templateId}/apply-theme-color`, {
          primary_color: cleanHex
        });
        dispatchLiveIframeColor(cleanHex);
      }
      setIsApplied(true);
      setTimeout(() => setIsApplied(false), 3000);
    } catch (err) {
      console.warn("Could not apply color to code:", err);
    } finally {
      setIsApplying(false);
    }
  };

  const handleCopy = () => {
    const textToCopy = getFormattedColor(currentColor, format);
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(textToCopy);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const currentHex = normalizeToHex(currentColor).toLowerCase();
  const isPrimaryActive = currentHex === "#b5804f" || currentHex === "#c89666";
  const isSecondaryActive = currentHex === "#0ea5e9" || currentHex === "#0284c7";

  return (
    <div className="space-y-3 pt-1">
      {/* Header & Format Switcher */}
      <div className="flex items-center justify-between">
        <label className="sb-control-label mb-0 flex items-center gap-1.5">
          <span>{label}</span>
        </label>
        {/* Format Selector Pills (HEX | RGB | HSL) */}
        <div className="flex items-center p-0.5 rounded-lg bg-muted/60 border border-border/60 text-[10px] font-semibold">
          {["HEX", "RGB", "HSL"].map((fmt) => (
            <button
              key={fmt}
              type="button"
              onClick={() => handleFormatChange(fmt)}
              className={cn(
                "px-2 py-0.5 rounded-md transition-all cursor-pointer",
                format === fmt
                  ? "bg-card text-foreground shadow-sm font-bold border border-border/40"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {fmt}
            </button>
          ))}
        </div>
      </div>

      {/* 1. Application Brand Color Presets (Primary & Secondary) */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
          <span>Application Brand Colors</span>
          <span className="font-mono text-[9px] text-[#c89666] font-bold bg-[#c89666]/10 px-1.5 py-0.5 rounded border border-[#c89666]/20">
            Design Tokens
          </span>
        </div>
        <div className="sb-color-brand-grid">
          {/* Primary Preset */}
          <button
            type="button"
            onClick={() => handleSelectColor("#b5804f")}
            className={cn(
              "sb-color-brand-item",
              isPrimaryActive
                ? "border-[#c89666] bg-[#c89666]/10 ring-2 ring-[#c89666]/30 shadow-sm"
                : "border-border/70 hover:bg-muted/40 hover:border-[#c89666]/40"
            )}
          >
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-1.5">
                <span
                  className="w-3.5 h-3.5 rounded-full shadow-sm flex-shrink-0 border border-white/20"
                  style={{ backgroundColor: "#b5804f" }}
                />
                <span className="text-xs font-bold text-foreground">Primary</span>
              </div>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30 uppercase">
                Brand
              </span>
            </div>
            <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground">
              <span>{format === "HEX" ? "#4F46E5" : format === "RGB" ? "rgb(79, 70, 229)" : "hsl(231, 58%, 55%)"}</span>
              {isPrimaryActive && <Check className="w-3.5 h-3.5 text-[#c89666] flex-shrink-0" />}
            </div>
          </button>

          {/* Secondary Preset */}
          <button
            type="button"
            onClick={() => handleSelectColor("#0ea5e9")}
            className={cn(
              "sb-color-brand-item",
              isSecondaryActive
                ? "border-sky-500 bg-sky-500/10 ring-2 ring-sky-500/30 shadow-sm"
                : "border-border/70 hover:bg-muted/40 hover:border-sky-500/40"
            )}
          >
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-1.5">
                <span
                  className="w-3.5 h-3.5 rounded-full shadow-sm flex-shrink-0 border border-white/20"
                  style={{ backgroundColor: "#0ea5e9" }}
                />
                <span className="text-xs font-bold text-foreground">Secondary</span>
              </div>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-sky-500/15 text-sky-400 border border-sky-500/30 uppercase">
                Accent
              </span>
            </div>
            <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground">
              <span>{format === "HEX" ? "#0EA5E9" : format === "RGB" ? "rgb(14, 165, 233)" : "hsl(197, 71%, 52%)"}</span>
              {isSecondaryActive && <Check className="w-3.5 h-3.5 text-sky-500 flex-shrink-0" />}
            </div>
          </button>
        </div>
      </div>

      {/* 2. Additional Curated Colors */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
          <span>Additional Curated Colors</span>
          <span className="text-[10px] text-muted-foreground font-mono">12 Colors</span>
        </div>
        <div className="sb-color-swatches-grid">
          {ADDITIONAL_COLOR_SWATCHES.map((sw) => {
            const isSelected = currentHex === sw.hex.toLowerCase();
            return (
              <button
                key={sw.hex}
                type="button"
                onClick={() => handleSelectColor(sw.hex)}
                title={`${sw.name} (${sw.hex})`}
                className={cn(
                  "sb-color-swatch-item",
                  isSelected
                    ? "ring-2 ring-foreground/80 ring-offset-2 ring-offset-background scale-105 shadow-md"
                    : "hover:scale-110 hover:shadow-sm"
                )}
                style={{ backgroundColor: sw.hex }}
              >
                {isSelected && (
                  <Check
                    className={cn(
                      "w-3.5 h-3.5 stroke-[3]",
                      sw.hex === "#09090b" || sw.hex === "#1e293b" || sw.hex === "#c89666" || sw.hex === "#c4222c" || sw.hex === "#e11d48" || sw.hex === "#2563eb"
                        ? "text-white"
                        : "text-white drop-shadow-[0_1px_1px_rgba(0,0,0,0.8)]"
                    )}
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. Formatted Live Input & Native Eyedropper / Color Picker */}
      <div className="space-y-1.5 pt-1">
        <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
          <span>Custom Value ({format})</span>
          {copied ? (
            <span className="text-emerald-500 font-bold flex items-center gap-1 text-[10px]">
              <Check className="w-3 h-3" /> Copied!
            </span>
          ) : (
            <span className="text-[10px] text-muted-foreground">Click swatch to fine-tune</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Visual Swatch & Native Color Wheel Trigger */}
          <div className="relative flex-shrink-0 group">
            <div
              className="w-9 h-9 rounded-xl border border-border shadow-sm flex items-center justify-center cursor-pointer transition-transform group-hover:scale-105"
              style={{ backgroundColor: currentHex }}
            />
            <input
              type="color"
              value={currentHex.length === 7 ? currentHex : "#b5804f"}
              onChange={(e) => handleSelectColor(e.target.value)}
              className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
              title="Click to open system color picker"
            />
          </div>

          {/* Formatted Text Input (Supports HEX, RGB, HSL) */}
          <div className="relative flex-1">
            <input
              type="text"
              value={localInput}
              onChange={handleInputChange}
              onBlur={handleInputBlur}
              placeholder={format === "HEX" ? "#4F46E5" : format === "RGB" ? "rgb(79, 70, 229)" : "hsl(231, 58%, 55%)"}
              className="sb-control-input text-xs font-mono w-full pr-8"
            />
            <button
              type="button"
              onClick={handleCopy}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground transition-colors rounded hover:bg-muted cursor-pointer"
              title={`Copy ${format} value`}
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-emerald-500" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* 4. Action: Apply Color to Website Code & Preview */}
      <div className="pt-2">
        <button
          type="button"
          onClick={() => handleApplyColorToCode(currentColor)}
          disabled={isApplying}
          className={cn(
            "w-full py-2.5 px-3 rounded-xl font-bold text-xs flex items-center justify-center gap-2 shadow-md transition-all cursor-pointer border",
            isApplied
              ? "bg-emerald-600 text-white border-emerald-500 shadow-emerald-500/20"
              : "bg-gradient-to-r from-[#c89666] to-[#b5804f] text-[#09090b] border-[#c89666]/30"
          )}
        >
          {isApplying ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Updating Website Code &amp; CSS...</span>
            </>
          ) : isApplied ? (
            <>
              <Check className="w-3.5 h-3.5 stroke-[3]" />
              <span>✓ Color Applied to Code (index.css) &amp; Live!</span>
            </>
          ) : (
            <>
              <Paintbrush className="w-3.5 h-3.5" />
              <span>Apply Color to Website Code</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function renderFriendlyFields(sectionId, props, onChange, templateId = null, onApplyThemeColor = null) {
  const sid = (sectionId || "").toLowerCase();

  // 🧭 1. NAVIGATION HEADER CONTROLS
  if (sid === "navbar" || sid.includes("nav")) {
    // Back-compat: convert old link1/link2/... keys → navLinks array
    let navLinks = Array.isArray(props.navLinks) ? [...props.navLinks] : [];
    if (navLinks.length === 0) {
      ["link1", "link2", "link3", "link4", "link5", "link6"].forEach((k) => {
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
        <div>
          <label className="sb-control-label">CTA Link / Target</label>
          <input
            type="text"
            value={props.ctaLink || ""}
            onChange={(e) => onChange("ctaLink", e.target.value)}
            placeholder="e.g. #contact or /pricing"
            className="sb-control-input text-xs font-mono"
          />
        </div>
        <ThemeColorPicker
          value={props.themeColor}
          onChange={onChange}
          label="Theme Accent Color"
          templateId={templateId}
          onApplyColor={onApplyThemeColor}
        />
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
        <ThemeColorPicker
          value={props.themeColor}
          onChange={onChange}
          label="Footer Accent Color"
          templateId={templateId}
          onApplyColor={onApplyThemeColor}
        />
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
            <div className="flex items-center justify-between mb-1.5">
              <label className="sb-control-label mb-0">Additional Info Texts ({props.textItems.length})</label>
              <button
                type="button"
                onClick={() => {
                  const lastItem = props.textItems[props.textItems.length - 1] || {};
                  const newItem = {
                    id: `text-${Date.now()}-${props.textItems.length}`,
                    label: lastItem.label || "<SPAN> TEXT",
                    text: `New content text #${props.textItems.length + 1}`,
                    originalText: "",
                    isNew: true
                  };
                  onChange("textItems", [...props.textItems, newItem]);
                }}
                className="flex items-center gap-1 text-[10px] font-bold text-pink-400 hover:text-pink-300 px-2 py-0.5 rounded-lg bg-pink-500/10 hover:bg-pink-500/20 transition-colors cursor-pointer"
                title="Add another text field with the same structure as the previous one"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Text</span>
              </button>
            </div>
            <div className="space-y-2">
              {props.textItems.map((ti, tIdx) => (
                <div key={ti.id || tIdx} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-muted-foreground uppercase font-mono">{ti.label || `Text #${tIdx + 1}`}</label>
                    <button
                      type="button"
                      onClick={() => {
                        const updated = props.textItems.filter((_, i) => i !== tIdx);
                        onChange("textItems", updated);
                      }}
                      className="p-1 text-muted-foreground hover:text-rose-400 hover:bg-rose-500/15 rounded transition-colors cursor-pointer"
                      title="Remove text"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                  <input
                    type="text"
                    value={ti.text || ""}
                    onChange={(e) => {
                      const updated = [...props.textItems];
                      updated[tIdx] = { ...updated[tIdx], text: e.target.value };
                      onChange("textItems", updated);
                    }}
                    placeholder={`Enter ${ti.label || "text"}...`}
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

    const addCardItem = () => {
      const lastCard = cardsList[cardsList.length - 1] || {};
      const newIdx = cardsList.length;
      // Replicate previous card's exact structure and keys ("like the previous one")
      const newCard = {};
      Object.keys(lastCard).forEach((k) => {
        if (k === "tag") {
          newCard[k] = `Item #${newIdx + 1}`;
        } else {
          newCard[k] = "";
        }
      });
      if (!("title" in newCard)) newCard.title = "";
      if (!("desc" in newCard)) newCard.desc = "";
      if ("stack" in lastCard && !("stack" in newCard)) newCard.stack = "";
      if ("tag" in lastCard && !("tag" in newCard)) newCard.tag = `Item #${newIdx + 1}`;

      const updated = [...cardsList, newCard];
      onChange("cards", updated);
      onChange(`card${newIdx + 1}_title`, newCard.title);
      onChange(`card${newIdx + 1}_desc`, newCard.desc);
      if (newCard.tag) onChange(`card${newIdx + 1}_tag`, newCard.tag);
      if (newCard.stack) onChange(`card${newIdx + 1}_stack`, newCard.stack);
    };

    const removeCardItem = (cardIdx) => {
      if (cardsList.length <= 1) return;
      const updated = cardsList.filter((_, idx) => idx !== cardIdx);
      onChange("cards", updated);
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
          <div className="flex items-center justify-between">
            <label className="sb-control-label mb-0">
              Content Cards &amp; Items ({cardsList.length})
            </label>
            <button
              type="button"
              onClick={addCardItem}
              className="flex items-center gap-1 text-[10px] font-bold text-pink-400 hover:text-pink-300 px-2 py-0.5 rounded-lg bg-pink-500/10 hover:bg-pink-500/20 transition-colors cursor-pointer"
              title="Add another card with the same structure as the previous one"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Item</span>
            </button>
          </div>

          {cardsList.map((card, idx) => (
            <div key={idx} className="p-3.5 rounded-xl border border-border/80 bg-card/60 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold uppercase text-pink-400 block">
                  {card.tag || `Item #${idx + 1}`}
                </span>
                {cardsList.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeCardItem(idx)}
                    className="p-1 rounded text-muted-foreground hover:text-rose-400 hover:bg-rose-500/15 transition-colors cursor-pointer"
                    title={`Delete item #${idx + 1}`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
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
              {/* Extra dynamic fields if previous item had other custom properties */}
              {Object.keys(card).filter((k) => !["tag", "title", "stack", "desc", "description"].includes(k)).map((extraKey) => (
                <div key={extraKey}>
                  <label className="sb-control-label capitalize">{extraKey.replace(/([A-Z])/g, " $1")}</label>
                  <input
                    type="text"
                    value={card[extraKey] || ""}
                    onChange={(e) => updateCardItem(idx, extraKey, e.target.value)}
                    placeholder={`Enter ${extraKey}...`}
                    className="sb-control-input text-xs"
                  />
                </div>
              ))}
            </div>
          ))}

          <button
            type="button"
            onClick={addCardItem}
            className="w-full py-2 px-3 rounded-xl border-2 border-dashed border-border hover:border-pink-500/50 hover:bg-pink-500/5 text-xs font-bold text-muted-foreground hover:text-pink-400 flex items-center justify-center gap-1.5 transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>+ Add Another Item</span>
          </button>
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
            <div className="flex items-center justify-between">
              <label className="sb-control-label mb-0">Additional Template Texts ({props.textItems.length})</label>
              <button
                type="button"
                onClick={() => {
                  const lastItem = props.textItems[props.textItems.length - 1] || {};
                  const newItem = {
                    id: `text-${Date.now()}-${props.textItems.length}`,
                    label: lastItem.label || "<SPAN> TEXT",
                    text: `New content text #${props.textItems.length + 1}`,
                    originalText: "",
                    isNew: true
                  };
                  onChange("textItems", [...props.textItems, newItem]);
                }}
                className="flex items-center gap-1 text-[10px] font-bold text-pink-400 hover:text-pink-300 px-2 py-0.5 rounded-lg bg-pink-500/10 hover:bg-pink-500/20 transition-colors cursor-pointer"
                title="Add another text field with the same structure as the previous one"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Text</span>
              </button>
            </div>
            <div className="space-y-2">
              {props.textItems.map((ti, tIdx) => (
                <div key={ti.id || tIdx} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-muted-foreground uppercase font-mono">{ti.label || `Text #${tIdx + 1}`}</label>
                    <button
                      type="button"
                      onClick={() => {
                        const updated = props.textItems.filter((_, i) => i !== tIdx);
                        onChange("textItems", updated);
                      }}
                      className="p-1 text-muted-foreground hover:text-rose-400 hover:bg-rose-500/15 rounded transition-colors cursor-pointer"
                      title="Remove text"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                  <input
                    type="text"
                    value={ti.text || ""}
                    onChange={(e) => {
                      const updated = [...props.textItems];
                      updated[tIdx] = { ...updated[tIdx], text: e.target.value };
                      onChange("textItems", updated);
                    }}
                    placeholder={`Enter ${ti.label || "text"}...`}
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

        <ThemeColorPicker
          value={props.themeColor}
          onChange={onChange}
          label="Hero Button & Accent Color"
          templateId={templateId}
          onApplyColor={onApplyThemeColor}
        />

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
          <div className="flex items-center justify-between">
            <label className="sb-control-label mb-0">Additional Template Texts ({props.textItems.length})</label>
            <button
              type="button"
              onClick={() => {
                const lastItem = props.textItems[props.textItems.length - 1] || {};
                const newItem = {
                  id: `text-${Date.now()}-${props.textItems.length}`,
                  label: lastItem.label || "<SPAN> TEXT",
                  text: "",
                  originalText: ""
                };
                onChange("textItems", [...props.textItems, newItem]);
              }}
              className="flex items-center gap-1 text-[10px] font-bold text-pink-400 hover:text-pink-300 px-2 py-0.5 rounded-lg bg-pink-500/10 hover:bg-pink-500/20 transition-colors cursor-pointer"
              title="Add another text field with the same structure as the previous one"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Text</span>
            </button>
          </div>
          <div className="space-y-2">
            {props.textItems.map((ti, tIdx) => (
              <div key={ti.id || tIdx} className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] text-muted-foreground uppercase font-mono">{ti.label || `Text #${tIdx + 1}`}</label>
                  <button
                    type="button"
                    onClick={() => {
                      const updated = props.textItems.filter((_, i) => i !== tIdx);
                      onChange("textItems", updated);
                    }}
                    className="p-1 text-muted-foreground hover:text-rose-400 hover:bg-rose-500/15 rounded transition-colors cursor-pointer"
                    title="Remove text"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
                <input
                  type="text"
                  value={ti.text || ""}
                  onChange={(e) => {
                    const updated = [...props.textItems];
                    updated[tIdx] = { ...updated[tIdx], text: e.target.value };
                    onChange("textItems", updated);
                  }}
                  placeholder={`Enter ${ti.label || "text"}...`}
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
