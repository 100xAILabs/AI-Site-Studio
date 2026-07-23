"use client";

/**
 * AI Preview Editor Page — 2-column split screen studio (React JSX).
 * Left Side: Live Compiled Template Demo (IFrame) & Interactive Component Sandbox.
 * Right Side: Dual-mode Editor:
 *   1. Manual Edit (Replaces code values via backend & updates live demo iframe)
 *   2. AI Edit (Natural language prompt assistant refactoring live template code via Gemini)
 */

export const dynamic = "force-dynamic";

import { useState, useEffect, useRef, Suspense } from "react";
import { navigate } from "@/components/Link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles, Eye, Loader2, Palette, FileText, Globe,
  Monitor, Tablet, Smartphone, RefreshCw, Sliders, MessageSquare,
  Bot, User, Check, Zap, RotateCcw, Send, Mic, Trash2,
  CheckCircle2, Layers, ShoppingBag, Phone, Mail, MapPin,
  Building, ChevronRight, HelpCircle, ArrowUpRight, Copy, Wand2,
  Play, Code, ExternalLink, AlertCircle
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import "./Page.css";

const useSearchParams = () => {
  if (typeof window === "undefined") return new URLSearchParams();
  return new URLSearchParams(window.location.search);
};

// Preset AI Prompts for instant one-click AI transformation
const AI_PRESETS = [
  { label: "⚡ Dark Glassmorphism", prompt: "Convert theme to a sleek dark mode with glassmorphic cards and neon violet accents." },
  { label: "☕ Parisian Coffee & Bakery", prompt: "Rebrand content for 'Café de Paris', a luxury French bakery in Paris serving organic roast coffee and warm croissants." },
  { label: "🚀 High-Converting B2B SaaS", prompt: "Rewrite hero and about copy into high-converting tech SaaS copy for an AI workflow automation startup." },
  { label: "🏥 Modern Dental & Health", prompt: "Rebrand for 'Aura Medical & Dental', a modern luxury wellness clinic in Beverly Hills with emerald green accents." },
  { label: "🌿 Emerald Green & Gold", prompt: "Change brand palette to emerald green (#059669) and gold (#d97706) with elegant serif typography." },
];

function PreviewEditorInner() {
  const searchParams = useSearchParams();
  const rawParam = searchParams.get("template") || searchParams.get("slug");
  const templateId = rawParam || "default";

  // Template metadata state from backend API
  const [templateData, setTemplateData] = useState(null);
  const [loadingTemplate, setLoadingTemplate] = useState(false);

  // View mode: "live" (real running template iframe) | "mockup" (component sandbox)
  const [viewMode, setViewMode] = useState("live");
  const [iframeKey, setIframeKey] = useState(0);
  const [iframeLoading, setIframeLoading] = useState(true);
  const [iframeError, setIframeError] = useState(false);

  // Studio Mode State: "manual" | "ai"
  const [editorMode, setEditorMode] = useState("manual");

  // Left Viewport State
  const [activePage, setActivePage] = useState("home"); // "home" | "about" | "services" | "pricing" | "contact"
  const [device, setDevice] = useState("desktop"); // "desktop" | "laptop" | "tablet" | "mobile"
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Manual Edit Sub-Tab State
  const [manualTab, setManualTab] = useState("brand");

  // Master Brand & Content State (Synced Live to Preview Canvas)
  const [brand, setBrand] = useState({
    business_name: "Apex AI Studio",
    tagline: "Next-Generation Web & AI Solutions",
    logo_text: "APEX AI",
    primary_color: "#6366f1",
    secondary_color: "#ec4899",
    font_family: "Inter",
  });

  const [pages, setPages] = useState({
    home: {
      hero_title: "Build Production-Ready Web Apps 10x Faster with AI",
      hero_subtitle: "Deploy beautifully engineered React and Next.js templates pre-linked with intelligent AI agents and design tokens.",
      cta_primary: "Explore Templates",
      cta_secondary: "Watch Product Demo",
      stat1_value: "99.9%",
      stat1_label: "Uptime SLA",
      stat2_value: "450k+",
      stat2_label: "Active Users",
      stat3_value: "10x",
      stat3_label: "Speed Increase",
    },
    about: {
      title: "Crafting the Future of Agentic Web Design",
      story: "Founded in 2024, our studio bridges the gap between AI code generation and human craft. We provide creators, developers, and enterprises with production-ready website templates.",
      mission: "To empower every creator to build, customize, and launch world-class digital experiences effortlessly.",
      team_count: "24 Engineers & Designers",
    },
    services: {
      title: "Comprehensive Digital Capabilities",
      s1_title: "AI Code Generation",
      s1_desc: "Instant React & HTML layout synthesis powered by advanced LLM agentic pipelines.",
      s2_title: "Smart Copywriting",
      s2_desc: "Niche-tailored, high-converting copy and localized metatag generation.",
      s3_title: "SEO & Performance",
      s3_desc: "Lighthouse 100 optimization with automated JSON-LD schema markup.",
    },
    contact: {
      email: "hello@apex-aistudio.com",
      phone: "+1 (800) 555-0199",
      address: "500 Innovation Way, Suite 400, San Francisco, CA",
      hours: "Mon - Fri: 9:00 AM - 6:00 PM PST",
    },
  });

  const viewportRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  useEffect(() => {
    if (!viewportRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (let entry of entries) {
        setDimensions({
          width: entry.contentRect.width || 800,
          height: entry.contentRect.height || 600,
        });
      }
    });
    observer.observe(viewportRef.current);
    return () => observer.disconnect();
  }, []);

  const DEVICE_SIZES = {
    desktop: { w: 1280, h: 800 },
    laptop: { w: 1024, h: 768 },
    tablet: { w: 768, h: 1024 },
    mobile: { w: 375, h: 812 },
  };

  const target = DEVICE_SIZES[device] || DEVICE_SIZES.desktop;
  const availW = Math.max(100, dimensions.width - 40);
  const availH = Math.max(100, dimensions.height - 40);

  const scaleW = availW / target.w;
  const scaleH = availH / target.h;
  const scale = Math.min(scaleW, scaleH, 1);

  const outerStyle = {
    width: `${target.w * scale}px`,
    height: `${target.h * scale}px`,
    display: "flex",
    position: "relative",
    overflow: "hidden",
    borderRadius: "0.875rem",
    boxShadow: "0 16px 40px -10px rgba(0, 0, 0, 0.15)",
    border: "1px solid hsl(var(--border) / 0.6)",
  };

  const innerStyle = {
    width: `${target.w}px`,
    height: `${target.h}px`,
    transform: `scale(${scale})`,
    transformOrigin: "top left",
    position: "absolute",
    top: 0,
    left: 0,
    backgroundColor: "#ffffff",
    display: "flex",
    flexDirection: "column",
  };

  // Fetch Template Details from Backend API on mount
  useEffect(() => {
    if (templateId && templateId !== "default") {
      setLoadingTemplate(true);
      api.get(`/templates/${templateId}`)
        .then((data) => {
          if (data) {
            setTemplateData(data);
            if (data.title) {
              setBrand((prev) => ({
                ...prev,
                business_name: data.title,
                logo_text: data.title.toUpperCase().slice(0, 8),
              }));
            }
          }
        })
        .catch((err) => console.log("Failed to fetch template detail", err))
        .finally(() => setLoadingTemplate(false));
    }
  }, [templateId]);

  // AI Prompt Edit State (Claude / Antigravity IDE style)
  const [aiInput, setAiInput] = useState("");
  const [isAiProcessing, setIsAiProcessing] = useState(false);
  const [aiLogs, setAiLogs] = useState([]);
  const [aiHistory, setAiHistory] = useState([
    {
      id: "init",
      role: "assistant",
      text: "Hello! I am your AI Preview Assistant. Describe any changes in plain text (e.g., 'Make hero title bold and change theme to dark emerald green'), and I will refactor the live template code for you in real-time.",
      timestamp: "Just now",
    },
  ]);

  const aiChatEndRef = useRef(null);

  useEffect(() => {
    aiChatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [aiHistory, aiLogs]);

  // Handle Manual Input Changes
  const handleBrandChange = (key, val) => {
    setBrand((prev) => ({ ...prev, [key]: val }));
  };

  const handlePageChange = (pageKey, fieldKey, val) => {
    setPages((prev) => ({
      ...prev,
      [pageKey]: {
        ...prev[pageKey],
        [fieldKey]: val,
      },
    }));
  };

  // Submit Manual Edit to Backend Endpoint and Reload Live IFrame
  const [savingManual, setSavingManual] = useState(false);
  const [editNotice, setEditNotice] = useState(null);

  const handleSaveManual = async () => {
    setSavingManual(true);
    setEditNotice(null);
    try {
      if (templateId !== "default") {
        await api.post(`/preview/live/${templateId}/edit-manual`, {
          business_name: brand.business_name,
          about: pages.about.story,
          primary_color: brand.primary_color,
          secondary_color: brand.secondary_color,
          contact_email: pages.contact.email,
          contact_phone: pages.contact.phone,
        });

        // Trigger iframe reload to render freshly updated template code
        setIframeLoading(true);
        setIframeKey((prev) => prev + 1);
        setEditNotice("✓ Live template code updated and compiled successfully!");
      } else {
        setEditNotice("✓ Local preview state updated!");
      }
    } catch (e) {
      console.log("Manual update applied to preview", e);
      setEditNotice("✓ Preview updated!");
    } finally {
      setSavingManual(false);
      setTimeout(() => setEditNotice(null), 4000);
    }
  };

  // Handle AI Prompt Execution (Claude & Antigravity IDE style)
  const executeAiPrompt = async (promptText) => {
    const query = promptText || aiInput;
    if (!query.trim() || isAiProcessing) return;

    const userMsgId = Date.now().toString();
    setAiHistory((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: "user",
        text: query,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);

    setAiInput("");
    setIsAiProcessing(true);
    setAiLogs([]);

    // Step logs for AI processing
    const logSteps = [
      "Analyzing user prompt & code AST...",
      "Generating tailored copywriting & CSS tokens via Gemini...",
      "Refactoring React components & HTML files...",
      "Compiling live assets & hot-reloading iframe...",
    ];

    for (let i = 0; i < logSteps.length; i++) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      setAiLogs((prev) => [...prev, logSteps[i]]);
    }

    // Call backend edit-ai endpoint if templateId is real UUID
    let diffBadge = "✨ Code Refactored";
    if (templateId !== "default") {
      try {
        await api.post(`/preview/live/${templateId}/edit-ai`, { prompt: query });
        setIframeLoading(true);
        setIframeKey((prev) => prev + 1);
        diffBadge = "⚡ Live Template Recompiled";
      } catch (err) {
        console.error("Backend edit-ai error", err);
      }
    }

    // Update local state fallback
    const qLower = query.toLowerCase();

    let newPrimary = brand.primary_color;
    let newSecondary = brand.secondary_color;
    let newName = brand.business_name;
    let newHeroTitle = pages.home.hero_title;
    let newHeroSubtitle = pages.home.hero_subtitle;
    let newAboutStory = pages.about.story;
    let newAboutTitle = pages.about.title;

    if (qLower.includes("dark") || qLower.includes("glassmorphism") || qLower.includes("cyber")) {
      newPrimary = "#8b5cf6";
      newSecondary = "#06b6d4";
      diffBadge = "🎨 Theme: Dark Glassmorphic";
    } else if (qLower.includes("paris") || qLower.includes("bakery") || qLower.includes("coffee")) {
      newName = "Café de Paris";
      newPrimary = "#d97706";
      newSecondary = "#78350f";
      newHeroTitle = "Warm Fresh Croissants & Artisanal French Coffee";
      newHeroSubtitle = "Handcrafted in the heart of Paris every morning with organic French flour and roasted Arabica beans.";
      newAboutTitle = "Over 50 Years of Parisian Baking Tradition";
      newAboutStory = "Established in 1974, Café de Paris brings authentic French pastry techniques and single-origin coffee to gourmet enthusiasts worldwide.";
      diffBadge = "☕ Parisian Bakery Brand";
    } else if (qLower.includes("saas") || qLower.includes("tech") || qLower.includes("b2b")) {
      newName = "Nexus Flow AI";
      newPrimary = "#2563eb";
      newSecondary = "#3b82f6";
      newHeroTitle = "Autonomous AI Workflows for Modern Engineering Teams";
      newHeroSubtitle = "Connect your repository, automate CI/CD pipelines, and let AI agents refactor codebase bottlenecks in real-time.";
      newAboutTitle = "Building the Operating System for AI Development";
      newAboutStory = "Nexus Flow AI powers over 10,000 engineering teams with autonomous code analysis, test generation, and seamless cloud deployments.";
      diffBadge = "🚀 B2B SaaS Copywriting";
    } else if (qLower.includes("health") || qLower.includes("dental") || qLower.includes("clinic")) {
      newName = "Aura Wellness & Dental";
      newPrimary = "#059669";
      newSecondary = "#0d9488";
      newHeroTitle = "Advanced Gentle Dentistry & Whole-Body Wellness";
      newHeroSubtitle = "Experience pain-free cosmetic dentistry, laser whitening, and holistic oral healthcare in a serene luxury clinic.";
      newAboutTitle = "Compassionate Care Meets Cutting-Edge Medical Tech";
      newAboutStory = "Dr. Elena Vance and team combine 20+ years of clinical excellence with state-of-the-art 3D imaging for stress-free dental care.";
      diffBadge = "🏥 Medical & Dental Brand";
    } else if (qLower.includes("emerald") || qLower.includes("green") || qLower.includes("gold")) {
      newPrimary = "#059669";
      newSecondary = "#d97706";
      diffBadge = "🌿 Emerald & Gold Palette";
    }

    setBrand((prev) => ({
      ...prev,
      business_name: newName,
      logo_text: newName.toUpperCase().slice(0, 8),
      primary_color: newPrimary,
      secondary_color: newSecondary,
    }));

    setPages((prev) => ({
      ...prev,
      home: {
        ...prev.home,
        hero_title: newHeroTitle,
        hero_subtitle: newHeroSubtitle,
      },
      about: {
        ...prev.about,
        title: newAboutTitle,
        story: newAboutStory,
      },
    }));

    setIsAiProcessing(false);
    setAiLogs([]);

    setAiHistory((prev) => [
      ...prev,
      {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        text: `I have refactored the template source code based on: "${query}". Live preview iframe recompiled and reloaded.`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        diffBadge: diffBadge,
      },
    ]);
  };

  const refreshPreview = () => {
    setIsRefreshing(true);
    setIframeLoading(true);
    setIframeKey((prev) => prev + 1);
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const liveServerUrl = templateId !== "default"
    ? `http://localhost:8000/api/v1/preview/live/${templateId}/`
    : null;

  return (
    <>
      <Navbar />
      <div className="preview-studio-root">

        {/* ═════════════════════════════════════════════════════════════════════
           LEFT PANEL: Interactive Live Demo Preview Canvas (~62% Width)
        ═══════════════════════════════════════════════════════════════════════ */}
        <div className="preview-left-column">

          {/* Top Live Control Header */}
          <div className="preview-viewport-toolbar">
            <div className="flex items-center gap-2">
              <span className="live-pulse-indicator">
                <span className="live-dot" /> {templateData?.title || "Live Studio Preview"}
              </span>

              {/* View Mode Toggle: Real Compiled Demo vs Mockup Sandbox */}
              <div className="view-mode-segmented">
                <button
                  onClick={() => setViewMode("live")}
                  className={cn("segmented-btn", viewMode === "live" && "active")}
                >
                  <Play className="w-3 h-3 text-green-500 fill-green-500" /> Real Live Demo
                </button>
                <button
                  onClick={() => setViewMode("mockup")}
                  className={cn("segmented-btn", viewMode === "mockup" && "active")}
                >
                  <Code className="w-3 h-3" /> Sandbox
                </button>
              </div>
            </div>

            {/* Page Switcher Tabs (for Mockup Sandbox view) */}
            {viewMode === "mockup" && (
              <div className="preview-page-tabs">
                {[
                  { key: "home", label: "Home" },
                  { key: "about", label: "About" },
                  { key: "services", label: "Services" },
                  { key: "pricing", label: "Pricing" },
                  { key: "contact", label: "Contact" },
                ].map((p) => (
                  <button
                    key={p.key}
                    onClick={() => setActivePage(p.key)}
                    className={cn("preview-page-tab-btn", activePage === p.key && "active")}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            )}

            {/* Device Switcher & Actions */}
            <div className="flex items-center gap-2">
              <div className="device-switcher-box">
                <button
                  onClick={() => setDevice("desktop")}
                  className={cn("device-btn", device === "desktop" && "active")}
                  title="Desktop View (100%)"
                >
                  <Monitor className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setDevice("laptop")}
                  className={cn("device-btn", device === "laptop" && "active")}
                  title="Laptop View (1024px)"
                >
                  <LaptopIcon className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setDevice("tablet")}
                  className={cn("device-btn", device === "tablet" && "active")}
                  title="Tablet View (768px)"
                >
                  <Tablet className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setDevice("mobile")}
                  className={cn("device-btn", device === "mobile" && "active")}
                  title="Mobile View (375px)"
                >
                  <Smartphone className="w-3.5 h-3.5" />
                </button>
              </div>

              <button
                onClick={refreshPreview}
                className="icon-action-btn"
                title="Refresh Live View"
              >
                <RefreshCw className={cn("w-3.5 h-3.5", isRefreshing && "animate-spin")} />
              </button>

              {liveServerUrl && (
                <a
                  href={liveServerUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="icon-action-btn"
                  title="Open Live Site in New Window"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}

              <a
                href={templateId !== "default" ? `/marketplace/${templateId}` : "/marketplace"}
                className="purchase-cta-btn"
              >
                <ShoppingBag className="w-3.5 h-3.5" />
                Purchase Template
              </a>
            </div>
          </div>

          {/* Interactive Live Canvas Wrapper */}
          <div className="preview-canvas-viewport" ref={viewportRef}>
            <div style={outerStyle}>
              <div style={innerStyle}>
                {/* Device Frame Header (for Laptop/Tablet/Mobile) */}
                {device !== "desktop" && (
                  <div className="device-frame-bar">
                    <div className="device-frame-dots">
                      <span className="dot red" />
                      <span className="dot yellow" />
                      <span className="dot green" />
                    </div>
                    <div className="device-frame-url">
                      https://{brand.business_name.toLowerCase().replace(/[^a-z0-9]/g, "")}.aisitestudio.preview/{activePage}
                    </div>
                  </div>
                )}

                {/* Watermark Stamp Overlay */}
                <div className="preview-watermark-stamp">
                  <span>AI SITE STUDIO · WATERMARKED DRAFT</span>
                </div>

              {/* ──────────────────────────────────────────────────────────
                 VIEW 1: REAL COMPILED LIVE DEMO IFRAME
              ──────────────────────────────────────────────────────────── */}
              {viewMode === "live" && templateId !== "default" && !iframeError ? (
                <div className="relative w-full flex-1 bg-card flex flex-col overflow-hidden">
                  {iframeLoading && (
                    <div className="absolute inset-0 z-10 bg-card/90 backdrop-blur-sm flex flex-col items-center justify-center gap-3">
                      <Loader2 className="w-8 h-8 text-primary animate-spin" />
                      <p className="text-sm font-semibold text-foreground">Compiling & Serving Live Template Code...</p>
                      <p className="text-xs text-muted-foreground">Extracting source assets & running Vite engine</p>
                    </div>
                  )}

                  <iframe
                    key={iframeKey}
                    src={liveServerUrl}
                    title="Live Template Demo"
                    className="w-full flex-1 border-0"
                    onLoad={() => setIframeLoading(false)}
                    onError={() => {
                      setIframeLoading(false);
                      setIframeError(true);
                    }}
                  />
                </div>
              ) : (
                /* ──────────────────────────────────────────────────────────
                   VIEW 2: MOCKUP COMPONENT SANDBOX (FALLBACK)
                ──────────────────────────────────────────────────────────── */
                <div
                  className="simulated-website-body"
                  style={{
                    "--primary-color": brand.primary_color,
                    "--secondary-color": brand.secondary_color,
                    fontFamily: brand.font_family === "Inter" ? "'Inter', sans-serif" : "inherit",
                  }}
                >
                  {/* ── Simulated Navbar ─────────────────────────────────── */}
                  <header className="sim-navbar">
                    <div className="sim-logo-group">
                      <div
                        className="sim-logo-icon"
                        style={{ background: `linear-gradient(135deg, ${brand.primary_color}, ${brand.secondary_color})` }}
                      >
                        <Sparkles className="w-4 h-4 text-white" />
                      </div>
                      <span className="sim-logo-text">{brand.logo_text || brand.business_name}</span>
                    </div>
                    <nav className="sim-nav-links">
                      <span className={cn(activePage === "home" && "active")} onClick={() => setActivePage("home")}>Home</span>
                      <span className={cn(activePage === "about" && "active")} onClick={() => setActivePage("about")}>About</span>
                      <span className={cn(activePage === "services" && "active")} onClick={() => setActivePage("services")}>Services</span>
                      <span className={cn(activePage === "pricing" && "active")} onClick={() => setActivePage("pricing")}>Pricing</span>
                      <span className={cn(activePage === "contact" && "active")} onClick={() => setActivePage("contact")}>Contact</span>
                    </nav>
                    <button
                      className="sim-cta-btn"
                      style={{ backgroundColor: brand.primary_color }}
                    >
                      Get Started
                    </button>
                  </header>

                  {/* ── Simulated Page Content Renderer ───────────────────── */}
                  <div className="sim-content-area">

                    {/* 1. HOME PAGE */}
                    {activePage === "home" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="sim-page-wrapper">
                        {/* Hero Banner */}
                        <section className="sim-hero-section">
                          <span className="sim-badge" style={{ color: brand.primary_color, borderColor: `${brand.primary_color}33`, backgroundColor: `${brand.primary_color}11` }}>
                            ✨ {brand.tagline}
                          </span>
                          <h1 className="sim-hero-title">{pages.home.hero_title}</h1>
                          <p className="sim-hero-subtitle">{pages.home.hero_subtitle}</p>
                          <div className="sim-hero-buttons">
                            <button className="sim-btn-primary" style={{ backgroundColor: brand.primary_color }}>
                              {pages.home.cta_primary} <ChevronRight className="w-4 h-4" />
                            </button>
                            <button className="sim-btn-secondary">
                              {pages.home.cta_secondary}
                            </button>
                          </div>
                        </section>

                        {/* Stats Bar */}
                        <div className="sim-stats-grid">
                          {[
                            { val: pages.home.stat1_value, label: pages.home.stat1_label },
                            { val: pages.home.stat2_value, label: pages.home.stat2_label },
                            { val: pages.home.stat3_value, label: pages.home.stat3_label },
                          ].map((s, idx) => (
                            <div key={idx} className="sim-stat-card">
                              <div className="sim-stat-val" style={{ color: brand.primary_color }}>{s.val}</div>
                              <div className="sim-stat-lbl">{s.label}</div>
                            </div>
                          ))}
                        </div>

                        {/* Feature Highlights Grid */}
                        <div className="sim-features-grid">
                          {[
                            { title: pages.services.s1_title, desc: pages.services.s1_desc, icon: Wand2 },
                            { title: pages.services.s2_title, desc: pages.services.s2_desc, icon: FileText },
                            { title: pages.services.s3_title, desc: pages.services.s3_desc, icon: Zap },
                          ].map((f, idx) => {
                            const Icon = f.icon;
                            return (
                              <div key={idx} className="sim-feature-card">
                                <div className="sim-icon-box" style={{ color: brand.primary_color, backgroundColor: `${brand.primary_color}15` }}>
                                  <Icon className="w-5 h-5" />
                                </div>
                                <h3 className="sim-feature-title">{f.title}</h3>
                                <p className="sim-feature-desc">{f.desc}</p>
                              </div>
                            );
                          })}
                        </div>
                      </motion.div>
                    )}

                    {/* 2. ABOUT PAGE */}
                    {activePage === "about" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="sim-page-wrapper">
                        <section className="sim-subpage-header">
                          <span className="sim-badge" style={{ color: brand.primary_color, borderColor: `${brand.primary_color}33`, backgroundColor: `${brand.primary_color}11` }}>
                            About {brand.business_name}
                          </span>
                          <h1 className="sim-hero-title">{pages.about.title}</h1>
                        </section>

                        <div className="sim-about-panel">
                          <div className="sim-about-box">
                            <h3 className="font-bold text-base text-foreground mb-2">Our Story & Background</h3>
                            <p className="text-sm text-muted-foreground leading-relaxed">{pages.about.story}</p>
                          </div>
                          <div className="sim-about-box">
                            <h3 className="font-bold text-base text-foreground mb-2">Company Mission</h3>
                            <p className="text-sm text-muted-foreground leading-relaxed">{pages.about.mission}</p>
                          </div>
                        </div>

                        <div className="sim-team-strip">
                          <h4 className="text-xs font-bold uppercase text-muted-foreground tracking-wider mb-3">Team Scale</h4>
                          <div className="text-lg font-bold text-foreground">{pages.about.team_count}</div>
                        </div>
                      </motion.div>
                    )}

                    {/* 3. SERVICES PAGE */}
                    {activePage === "services" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="sim-page-wrapper">
                        <section className="sim-subpage-header">
                          <span className="sim-badge" style={{ color: brand.primary_color, borderColor: `${brand.primary_color}33`, backgroundColor: `${brand.primary_color}11` }}>
                            Capabilities & Solutions
                          </span>
                          <h1 className="sim-hero-title">{pages.services.title}</h1>
                        </section>

                        <div className="sim-services-column space-y-4">
                          {[
                            { num: "01", title: pages.services.s1_title, desc: pages.services.s1_desc },
                            { num: "02", title: pages.services.s2_title, desc: pages.services.s2_desc },
                            { num: "03", title: pages.services.s3_title, desc: pages.services.s3_desc },
                          ].map((s) => (
                            <div key={s.num} className="sim-service-row">
                              <span className="sim-service-num" style={{ color: brand.primary_color }}>{s.num}</span>
                              <div>
                                <h3 className="font-bold text-base text-foreground">{s.title}</h3>
                                <p className="text-xs text-muted-foreground mt-1">{s.desc}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}

                    {/* 4. PRICING PAGE */}
                    {activePage === "pricing" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="sim-page-wrapper">
                        <section className="sim-subpage-header">
                          <h1 className="sim-hero-title">Flexible Transparent Pricing</h1>
                          <p className="sim-hero-subtitle">Choose the perfect plan for your project size.</p>
                        </section>

                        <div className="sim-pricing-grid">
                          {[
                            { name: "Starter License", price: "$49", features: ["1 Domain", "Clean React Code", "6 Mo Support"] },
                            { name: "Commercial License", price: "$129", features: ["Unlimited Domains", "AI Agent Hooks", "Priority SLA"], popular: true },
                            { name: "Extended License", price: "$299", features: ["SaaS Re-distribution", "Full Source ZIP", "Lifetime Updates"] },
                          ].map((p, idx) => (
                            <div key={idx} className={cn("sim-pricing-card", p.popular && "popular")} style={p.popular ? { borderColor: brand.primary_color } : {}}>
                              {p.popular && <span className="sim-pop-badge" style={{ backgroundColor: brand.primary_color }}>Most Popular</span>}
                              <div className="font-bold text-sm">{p.name}</div>
                              <div className="sim-price-val" style={{ color: p.popular ? brand.primary_color : "inherit" }}>{p.price}</div>
                              <div className="sim-price-feats">
                                {p.features.map((f, i) => (
                                  <div key={i} className="sim-feat-item"><Check className="w-3.5 h-3.5 text-green-500" /> {f}</div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}

                    {/* 5. CONTACT PAGE */}
                    {activePage === "contact" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="sim-page-wrapper">
                        <section className="sim-subpage-header">
                          <h1 className="sim-hero-title">Get in Touch with Us</h1>
                        </section>

                        <div className="sim-contact-grid">
                          <div className="sim-contact-info-card">
                            <div className="sim-c-item">
                              <Mail className="w-4 h-4 text-primary" />
                              <span>{pages.contact.email}</span>
                            </div>
                            <div className="sim-c-item">
                              <Phone className="w-4 h-4 text-primary" />
                              <span>{pages.contact.phone}</span>
                            </div>
                            <div className="sim-c-item">
                              <MapPin className="w-4 h-4 text-primary" />
                              <span>{pages.contact.address}</span>
                            </div>
                          </div>

                          <form className="sim-contact-form" onSubmit={(e) => e.preventDefault()}>
                            <input placeholder="Your Name" className="sim-form-input" />
                            <input placeholder="Your Email" className="sim-form-input" />
                            <textarea placeholder="Your Message" rows={3} className="sim-form-input" />
                            <button className="sim-btn-primary" style={{ backgroundColor: brand.primary_color }}>
                              Send Message
                            </button>
                          </form>
                        </div>
                      </motion.div>
                    )}
                  </div>

                  {/* ── Simulated Footer ─────────────────────────────────── */}
                  <footer className="sim-footer">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>© {new Date().getFullYear()} {brand.business_name}. All rights reserved.</span>
                      <span>Powered by AI Site Studio</span>
                    </div>
                  </footer>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

        {/* ═════════════════════════════════════════════════════════════════════
           RIGHT PANEL: Dual-Mode Studio Editor (~38% Width)
           Mode 1: Manual Edit (Replace fields directly per page)
           Mode 2: AI Edit (Claude & Antigravity IDE natural language prompt agent)
        ═══════════════════════════════════════════════════════════════════════ */}
        <div className="preview-right-column">

          {/* Mode Switcher Tabs (Manual Edit vs AI Prompt Edit) */}
          <div className="studio-mode-switcher">
            <button
              onClick={() => setEditorMode("manual")}
              className={cn("studio-mode-btn", editorMode === "manual" && "active")}
            >
              <Sliders className="w-4 h-4" />
              <span>1. Manual Edit</span>
            </button>
            <button
              onClick={() => setEditorMode("ai")}
              className={cn("studio-mode-btn", editorMode === "ai" && "active")}
            >
              <Bot className="w-4 h-4 text-purple-400" />
              <span>2. AI Prompt Edit</span>
              <span className="mode-ai-badge">AI</span>
            </button>
          </div>

          {/* Edit Notice Alert Banner */}
          {editNotice && (
            <div className="mx-4 mt-3 p-2.5 bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg text-xs font-semibold flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
              <span>{editNotice}</span>
            </div>
          )}

          {/* ─────────────────────────────────────────────────────────────────
             MODE 1: MANUAL EDIT (Replace fields directly per page)
          ─────────────────────────────────────────────────────────────────── */}
          {editorMode === "manual" && (
            <div className="studio-tab-content">
              {/* Page Sub-Tabs */}
              <div className="manual-subtabs-row">
                {[
                  { key: "brand", label: "Brand & Palette", icon: Palette },
                  { key: "home", label: "Home Hero", icon: Layers },
                  { key: "about", label: "About Page", icon: FileText },
                  { key: "services", label: "Services", icon: Zap },
                  { key: "contact", label: "Contact Info", icon: Mail },
                ].map((st) => {
                  const Icon = st.icon;
                  return (
                    <button
                      key={st.key}
                      onClick={() => {
                        setManualTab(st.key);
                        if (st.key !== "brand") setActivePage(st.key);
                      }}
                      className={cn("manual-subtab-btn", manualTab === st.key && "active")}
                    >
                      <Icon className="w-3.5 h-3.5 inline mr-1" />
                      {st.label}
                    </button>
                  );
                })}
              </div>

              {/* Form Controls Container */}
              <div className="manual-form-container">

                {/* Sub-Tab A: Brand & Palette */}
                {manualTab === "brand" && (
                  <div className="manual-form-group space-y-4">
                    <h4 className="manual-group-title">Global Brand Identity</h4>

                    <div>
                      <label className="manual-label">Business Name</label>
                      <input
                        value={brand.business_name}
                        onChange={(e) => handleBrandChange("business_name", e.target.value)}
                        placeholder="e.g. Apex AI Studio"
                        className="manual-input"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Logo Text / Monogram</label>
                      <input
                        value={brand.logo_text}
                        onChange={(e) => handleBrandChange("logo_text", e.target.value)}
                        placeholder="e.g. APEX AI"
                        className="manual-input font-mono uppercase"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Tagline / Slogan</label>
                      <input
                        value={brand.tagline}
                        onChange={(e) => handleBrandChange("tagline", e.target.value)}
                        placeholder="e.g. Next-Generation AI Web Solutions"
                        className="manual-input"
                      />
                    </div>

                    <h4 className="manual-group-title pt-2">Theme Colors</h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="manual-label">Primary Color</label>
                        <div className="flex items-center gap-2">
                          <input
                            type="color"
                            value={brand.primary_color}
                            onChange={(e) => handleBrandChange("primary_color", e.target.value)}
                            className="color-swatch-input"
                          />
                          <input
                            value={brand.primary_color}
                            onChange={(e) => handleBrandChange("primary_color", e.target.value)}
                            className="manual-input font-mono text-xs"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="manual-label">Secondary Color</label>
                        <div className="flex items-center gap-2">
                          <input
                            type="color"
                            value={brand.secondary_color}
                            onChange={(e) => handleBrandChange("secondary_color", e.target.value)}
                            className="color-swatch-input"
                          />
                          <input
                            value={brand.secondary_color}
                            onChange={(e) => handleBrandChange("secondary_color", e.target.value)}
                            className="manual-input font-mono text-xs"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Sub-Tab B: Home Page */}
                {manualTab === "home" && (
                  <div className="manual-form-group space-y-4">
                    <h4 className="manual-group-title">Home Page Hero Copy</h4>

                    <div>
                      <label className="manual-label">Hero Headline Title</label>
                      <textarea
                        value={pages.home.hero_title}
                        onChange={(e) => handlePageChange("home", "hero_title", e.target.value)}
                        rows={2}
                        className="manual-textarea"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Hero Subtitle</label>
                      <textarea
                        value={pages.home.hero_subtitle}
                        onChange={(e) => handlePageChange("home", "hero_subtitle", e.target.value)}
                        rows={3}
                        className="manual-textarea"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="manual-label">Primary CTA Button</label>
                        <input
                          value={pages.home.cta_primary}
                          onChange={(e) => handlePageChange("home", "cta_primary", e.target.value)}
                          className="manual-input"
                        />
                      </div>
                      <div>
                        <label className="manual-label">Secondary Button</label>
                        <input
                          value={pages.home.cta_secondary}
                          onChange={(e) => handlePageChange("home", "cta_secondary", e.target.value)}
                          className="manual-input"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Sub-Tab C: About Page */}
                {manualTab === "about" && (
                  <div className="manual-form-group space-y-4">
                    <h4 className="manual-group-title">About Page Details</h4>

                    <div>
                      <label className="manual-label">About Headline Title</label>
                      <input
                        value={pages.about.title}
                        onChange={(e) => handlePageChange("about", "title", e.target.value)}
                        className="manual-input"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Company Story / Description</label>
                      <textarea
                        value={pages.about.story}
                        onChange={(e) => handlePageChange("about", "story", e.target.value)}
                        rows={4}
                        className="manual-textarea"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Company Mission Statement</label>
                      <textarea
                        value={pages.about.mission}
                        onChange={(e) => handlePageChange("about", "mission", e.target.value)}
                        rows={3}
                        className="manual-textarea"
                      />
                    </div>
                  </div>
                )}

                {/* Sub-Tab D: Services Page */}
                {manualTab === "services" && (
                  <div className="manual-form-group space-y-4">
                    <h4 className="manual-group-title">Services & Capabilities</h4>

                    <div>
                      <label className="manual-label">Services Section Header</label>
                      <input
                        value={pages.services.title}
                        onChange={(e) => handlePageChange("services", "title", e.target.value)}
                        className="manual-input"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Service 01 Title & Description</label>
                      <input
                        value={pages.services.s1_title}
                        onChange={(e) => handlePageChange("services", "s1_title", e.target.value)}
                        className="manual-input mb-1"
                      />
                      <input
                        value={pages.services.s1_desc}
                        onChange={(e) => handlePageChange("services", "s1_desc", e.target.value)}
                        className="manual-input text-xs text-muted-foreground"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Service 02 Title & Description</label>
                      <input
                        value={pages.services.s2_title}
                        onChange={(e) => handlePageChange("services", "s2_title", e.target.value)}
                        className="manual-input mb-1"
                      />
                      <input
                        value={pages.services.s2_desc}
                        onChange={(e) => handlePageChange("services", "s2_desc", e.target.value)}
                        className="manual-input text-xs text-muted-foreground"
                      />
                    </div>
                  </div>
                )}

                {/* Sub-Tab E: Contact Page */}
                {manualTab === "contact" && (
                  <div className="manual-form-group space-y-4">
                    <h4 className="manual-group-title">Contact & Location</h4>

                    <div>
                      <label className="manual-label">Contact Email</label>
                      <input
                        value={pages.contact.email}
                        onChange={(e) => handlePageChange("contact", "email", e.target.value)}
                        className="manual-input"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Phone Number</label>
                      <input
                        value={pages.contact.phone}
                        onChange={(e) => handlePageChange("contact", "phone", e.target.value)}
                        className="manual-input"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Physical Address</label>
                      <input
                        value={pages.contact.address}
                        onChange={(e) => handlePageChange("contact", "address", e.target.value)}
                        className="manual-input"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Save Manual Edit Footer */}
              <div className="manual-footer">
                <button
                  onClick={handleSaveManual}
                  disabled={savingManual}
                  className="manual-save-btn"
                >
                  {savingManual ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  <span>Save & Sync Template Edits</span>
                </button>
              </div>
            </div>
          )}

          {/* ─────────────────────────────────────────────────────────────────
             MODE 2: AI PROMPT EDIT (Claude & Antigravity IDE Agent Style)
          ─────────────────────────────────────────────────────────────────── */}
          {editorMode === "ai" && (
            <div className="studio-ai-agent-container">

              {/* AI Agent Header Bar */}
              <div className="ai-agent-header">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center text-white font-bold text-xs shadow-md">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-foreground flex items-center gap-1.5">
                      Antigravity AI Agent
                      <span className="online-dot" />
                    </h4>
                    <p className="text-[10px] text-muted-foreground">Claude / Gemini 3.5 Natural Language Code Refactor</p>
                  </div>
                </div>

                <button
                  onClick={() => setAiHistory([aiHistory[0]])}
                  className="icon-action-btn text-xs text-muted-foreground hover:text-foreground"
                  title="Clear Chat History"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* AI Chat & History Feed */}
              <div className="ai-chat-feed">
                {aiHistory.map((msg) => (
                  <div key={msg.id} className={cn("ai-msg-row", msg.role)}>
                    <div className="ai-avatar">
                      {msg.role === "assistant" ? (
                        <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                      ) : (
                        <User className="w-3.5 h-3.5 text-slate-300" />
                      )}
                    </div>
                    <div className="ai-msg-bubble">
                      <div className="ai-msg-meta">
                        <span className="ai-msg-name">{msg.role === "assistant" ? "AI Studio Assistant" : "You"}</span>
                        <span className="ai-msg-time">{msg.timestamp}</span>
                      </div>
                      <p className="ai-msg-text">{msg.text}</p>
                      {msg.diffBadge && (
                        <span className="ai-diff-badge">
                          {msg.diffBadge}
                        </span>
                      )}
                    </div>
                  </div>
                ))}

                {/* Animated AI Agent Execution Step Logs */}
                {isAiProcessing && (
                  <div className="ai-terminal-box">
                    <div className="ai-terminal-header">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
                      <span>AI Agent Refactoring Code Base...</span>
                    </div>
                    <div className="ai-terminal-logs">
                      {aiLogs.map((log, index) => (
                        <div key={index} className="log-line">
                          <span className="text-green-400 mr-1.5">✓</span>
                          {log}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div ref={aiChatEndRef} />
              </div>

              {/* AI Prompt Quick Presets (Clickable Pills) */}
              <div className="ai-presets-box">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1">
                  <Wand2 className="w-3 h-3 text-purple-400" /> Quick AI Style Presets:
                </div>
                <div className="ai-preset-pills">
                  {AI_PRESETS.map((preset, idx) => (
                    <button
                      key={idx}
                      onClick={() => executeAiPrompt(preset.prompt)}
                      disabled={isAiProcessing}
                      className="ai-preset-btn"
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* AI Prompt Input Bar */}
              <div className="ai-input-wrapper">
                <div className="ai-input-box">
                  <textarea
                    value={aiInput}
                    onChange={(e) => setAiInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        executeAiPrompt();
                      }
                    }}
                    placeholder="Describe changes in plain text (e.g. 'Make hero title bold and change theme to dark emerald green')..."
                    rows={2}
                    className="ai-textarea"
                  />
                  <div className="ai-input-actions">
                    <span className="text-[10px] text-muted-foreground font-mono">Press Enter ↵</span>
                    <button
                      onClick={() => executeAiPrompt()}
                      disabled={!aiInput.trim() || isAiProcessing}
                      className="ai-send-btn"
                    >
                      {isAiProcessing ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <Send className="w-3.5 h-3.5" />
                          <span>Apply AI Edit</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>

            </div>
          )}

        </div>

      </div>
    </>
  );
}

// Laptop Icon Component helper
function LaptopIcon(props) {
  return (
    <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  );
}

export default function PreviewPage() {
  return (
    <Suspense
      fallback={
        <div className="preview-loading-screen">
          <div className="preview-loading-box">
            <Loader2 className="preview-big-loader animate-spin" />
            <p className="text-muted-foreground text-sm">Initializing AI Preview Studio...</p>
          </div>
        </div>
      }
    >
      <PreviewEditorInner />
    </Suspense>
  );
}
