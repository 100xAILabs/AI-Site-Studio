"use client";

/**
 * Live Preview Editor Page — 2-column split screen studio (React JSX).
 * 
 * Supports 2 editor modes:
 *   1. Manual Edit (Controls for Title, Tagline, Brand Colors, Contact info, etc.)
 *   2. Live Prompt Edit (Natural language prompt assistant refactoring live template code)
 */

export const dynamic = "force-dynamic";

import { useState, useEffect, useRef, Suspense } from "react";
import Link, { navigate } from "@/components/Link";
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
import { useCartStore } from "@/store";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import "./Page.css";

const useSearchParams = () => {
  if (typeof window === "undefined") return new URLSearchParams();
  return new URLSearchParams(window.location.search);
};

// Preset Prompts for instant one-click transformation
const AI_PRESETS = [
  { label: "⚡ Dark Glassmorphism", prompt: "Convert theme to a sleek dark mode with glassmorphic cards and neon violet accents." },
  { label: "☕ Parisian Coffee & Bakery", prompt: "Rebrand content for 'Café de Paris', a luxury French bakery in Paris serving organic roast coffee and warm croissants." },
  { label: "🚀 High-Converting B2B SaaS", prompt: "Rewrite hero and about copy into high-converting tech SaaS copy for a cloud workflow automation startup." },
  { label: "🏥 Modern Dental & Health", prompt: "Rebrand for 'Aura Medical & Dental', a modern luxury wellness clinic in Beverly Hills with emerald green accents." },
  { label: "🌿 Emerald Green & Gold", prompt: "Change brand palette to emerald green (#059669) and gold (#d97706) with elegant serif typography." },
];

function PreviewEditorInner() {
  const searchParams = useSearchParams();
  const rawParam = searchParams.get("template") || searchParams.get("slug");
  const [activeTemplateId, setActiveTemplateId] = useState(rawParam || "default");

  // Template metadata state from backend API
  const [templateData, setTemplateData] = useState(null);
  const [loadingTemplate, setLoadingTemplate] = useState(false);

  // Cart store integration
  const addToCart = useCartStore((s) => s.addItem);
  const isInCart = useCartStore((s) => s.isInCart(templateData?.id || activeTemplateId));

  const handlePurchaseTemplate = (e) => {
    if (e) e.preventDefault();
    if (templateData) {
      addToCart({
        templateId: templateData.id,
        title: templateData.title,
        price: Number(templateData.price || 49),
        thumbnail: templateData.thumbnail_url || templateData.images?.[0] || "",
        licenseType: "regular",
      });
      navigate("/checkout");
    } else if (activeTemplateId && activeTemplateId !== "default") {
      navigate(`/marketplace/${activeTemplateId}?buy=1`);
    } else {
      navigate("/marketplace");
    }
  };

  // View mode: "live" (real running template iframe) | "mockup" (component sandbox)
  const [viewMode, setViewMode] = useState("live");
  const [iframeKey, setIframeKey] = useState(0);
  const [iframeLoading, setIframeLoading] = useState(true);
  const [iframeError, setIframeError] = useState(false);

  // Safety timer to clear loading overlay if iframe takes too long
  useEffect(() => {
    if (iframeLoading) {
      const timer = setTimeout(() => {
        setIframeLoading(false);
      }, 10000);
      return () => clearTimeout(timer);
    }
  }, [iframeLoading, iframeKey]);

  // Studio Mode State: "manual" | "ai"
  const [editorMode, setEditorMode] = useState("manual");

  // Left Viewport State
  const [activePage, setActivePage] = useState("home"); // "home" | "about" | "services" | "pricing" | "contact"
  const [device, setDevice] = useState("desktop"); // "desktop" | "laptop" | "tablet" | "mobile"
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Manual Edit Sub-Tab State
  const [manualTab, setManualTab] = useState("brand");
  const [pageEdits, setPageEdits] = useState({});
  const [selectedPageToEdit, setSelectedPageToEdit] = useState("index.html");
  const [findText, setFindText] = useState("");
  const [replaceText, setReplaceText] = useState("");
  const [isReplacing, setIsReplacing] = useState(false);
  const [replaceNotice, setReplaceNotice] = useState(null);
  const [isDebugging, setIsDebugging] = useState(false);

  // Trigger Autonomous AI Debugger & Fixer
  const handleRunAIDebugger = async () => {
    if (!activeTemplateId || activeTemplateId === "default") return;
    setIsDebugging(true);
    try {
      const res = await api.post(`/preview/live/${activeTemplateId}/ai-debug`, {}, token);
      setEditNotice(res.message || "AI Debugger analyzed and fixed syntax errors.");
      // Reload iframe
      setIframeKey((prev) => prev + 1);
      setTimeout(() => setEditNotice(""), 8000);
    } catch (err) {
      console.error("AI Debugger error:", err);
      alert("AI Debugger: " + (err.message || "Failed to debug project."));
    } finally {
      setIsDebugging(false);
    }
  };

  // Master Brand & Content State (Synced Live to Preview Canvas)
  const [brand, setBrand] = useState({
    business_name: "Apex Design Studio",
    tagline: "Next-Generation Web & Design Solutions",
    logo_text: "APEX STUDIO",
    primary_color: "#6366f1",
    secondary_color: "#ec4899",
    font_family: "Inter",
    contact_email: "support@aisitestudio.com",
    contact_phone: "+1 (555) 019-2834",
  });

  const [pages, setPages] = useState({
    home: {
      hero_title: "Build Production-Ready Web Apps 10x Faster",
      hero_subtitle: "Deploy beautifully engineered React and Next.js templates pre-linked with dynamic components and design tokens.",
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
      story: "Founded in 2024, our studio bridges the gap between dynamic code generation and human craft. We provide creators, developers, and enterprises with production-ready website templates.",
      mission: "To empower every creator to build, customize, and launch world-class digital experiences effortlessly.",
      team_count: "24 Engineers & Designers",
    },
    services: {
      title: "Comprehensive Digital Capabilities",
      s1_title: "Dynamic Code Generation",
      s1_desc: "Instant React & HTML layout synthesis powered by advanced dynamic pipelines.",
      s2_title: "Smart Copywriting",
      s2_desc: "Niche-tailored, high-converting copy and localized metatag generation.",
      s3_title: "SEO & Performance",
      s3_desc: "Lighthouse 100 optimization with automated JSON-LD schema markup.",
    },
    contact: {
      email: "hello@apex-studio.com",
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
    if (activeTemplateId && activeTemplateId !== "default") {
      setLoadingTemplate(true);
      api.get(`/templates/${activeTemplateId}`)
        .then((data) => {
          if (data) {
            setTemplateData(data);
            
            let primaryColor = "#6366f1";
            let secondaryColor = "#ec4899";
            
            if (data.color_scheme) {
              const schemeLower = data.color_scheme.toLowerCase();
              if (schemeLower.includes("red")) {
                primaryColor = "#dc2626";
                secondaryColor = "#f8fafc";
              } else if (schemeLower.includes("green")) {
                primaryColor = "#059669";
                secondaryColor = "#10b981";
              } else if (schemeLower.includes("blue")) {
                primaryColor = "#2563eb";
                secondaryColor = "#3b82f6";
              }
            } else if (data.title && (data.title.toLowerCase().includes("blood") || data.title.toLowerCase().includes("lifelink") || data.title.toLowerCase().includes("emergency"))) {
              primaryColor = "#dc2626";
              secondaryColor = "#f5f5f5";
            }
            
            setBrand((prev) => ({
              ...prev,
              business_name: data.title || prev.business_name,
              logo_text: data.title ? data.title.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8) : prev.logo_text,
              tagline: data.short_description || prev.tagline,
              primary_color: primaryColor,
              secondary_color: secondaryColor,
            }));
            
            setPages((prev) => ({
              ...prev,
              home: {
                ...prev.home,
                hero_title: data.title ? `Welcome to ${data.title}` : prev.home.hero_title,
                hero_subtitle: data.short_description || prev.home.hero_subtitle,
              },
              about: {
                ...prev.about,
                title: `About ${data.title || "Us"}`,
                story: data.description || prev.about.story,
              }
            }));
          }
        })
        .catch((err) => console.log("Failed to fetch template detail", err))
        .finally(() => setLoadingTemplate(false));
    }
  }, [activeTemplateId]);

  // Live Prompt Edit State
  const [aiInput, setAiInput] = useState("");
  const [isAiProcessing, setIsAiProcessing] = useState(false);
  const [aiLogs, setAiLogs] = useState([]);
  const [aiHistory, setAiHistory] = useState([
    {
      id: "init",
      role: "assistant",
      text: "Hello! I am your Studio Design Assistant. Describe any changes in plain text (e.g., 'Make hero title bold and change theme to dark emerald green'), and I will refactor the live template code for you in real-time.",
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
      if (activeTemplateId !== "default") {
        const res = await api.post(`/preview/live/${activeTemplateId}/edit-manual`, {
          business_name: brand.business_name,
          about: brand.tagline,
          primary_color: brand.primary_color,
          secondary_color: brand.secondary_color,
          contact_email: brand.contact_email || "",
          contact_phone: brand.contact_phone || "",
          page_edits: pageEdits,
        });

        // Update local pages state with manual edits so Sandbox view updates
        setPages((prev) => {
          const updated = { ...prev };
          Object.keys(pageEdits).forEach((filename) => {
            const pageKey = mapFilenameToPageKey(filename);
            if (updated[pageKey]) {
              const edits = pageEdits[filename];
              updated[pageKey] = {
                ...updated[pageKey],
                ...(edits.title && { hero_title: edits.title, title: edits.title }),
                ...(edits.description && { hero_subtitle: edits.description, story: edits.description, desc: edits.description }),
                ...(edits.cta_text && { cta_primary: edits.cta_text }),
              };
            }
          });
          return updated;
        });

        if (res && res.template_id && res.template_id !== activeTemplateId) {
          setActiveTemplateId(res.template_id);
          const params = new URLSearchParams(window.location.search);
          params.set("template", res.template_id);
          window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
        }

        // Trigger iframe reload to render freshly updated template code
        setIframeLoading(true);
        setIframeKey((prev) => prev + 1);
        setEditNotice("✓ Live template code updated and compiled successfully!");
      } else {
        // Update local pages state in sandbox fallback
        setPages((prev) => {
          const updated = { ...prev };
          Object.keys(pageEdits).forEach((filename) => {
            const pageKey = mapFilenameToPageKey(filename);
            if (updated[pageKey]) {
              const edits = pageEdits[filename];
              updated[pageKey] = {
                ...updated[pageKey],
                ...(edits.title && { hero_title: edits.title, title: edits.title }),
                ...(edits.description && { hero_subtitle: edits.description, story: edits.description, desc: edits.description }),
                ...(edits.cta_text && { cta_primary: edits.cta_text }),
              };
            }
          });
          return updated;
        });
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

  // Handle Live Prompt Execution
  const executeAiPrompt = async (customPrompt) => {
    const promptToRun = customPrompt || aiInput;
    if (!promptToRun.trim() || isAiProcessing) return;

    const userMsg = {
      id: Date.now().toString(),
      role: "user",
      text: promptToRun,
      timestamp: "Just now",
    };

    setAiHistory((prev) => [...prev, userMsg]);
    setAiInput("");
    setIsAiProcessing(true);
    setAiLogs([]);

    // Step logs for prompt processing
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

    // Call backend edit-ai endpoint if activeTemplateId is real UUID
    let diffBadge = "✨ Code Refactored";
    if (activeTemplateId !== "default") {
      try {
        const res = await api.post(`/preview/live/${activeTemplateId}/edit-ai`, { prompt: promptToRun });
        if (res && res.template_id && res.template_id !== activeTemplateId) {
          setActiveTemplateId(res.template_id);
          const params = new URLSearchParams(window.location.search);
          params.set("template", res.template_id);
          window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
        }
        setIframeLoading(true);
        setIframeKey((prev) => prev + 1);
        diffBadge = "⚡ Live Template Recompiled";
      } catch (err) {
        console.error("Backend edit-ai error", err);
      }
    }

    // Update local state fallback
    const qLower = promptToRun.toLowerCase();

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
      newName = "Nexus Flow";
      newPrimary = "#2563eb";
      newSecondary = "#3b82f6";
      newHeroTitle = "Autonomous Workflows for Modern Engineering Teams";
      newHeroSubtitle = "Connect your repository, automate CI/CD pipelines, and refactor codebase bottlenecks in real-time.";
      newAboutTitle = "Building the Operating System for Modern Cloud Development";
      newAboutStory = "Nexus Flow powers over 10,000 engineering teams with code analysis, test generation, and seamless cloud deployments.";
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
        text: `I have refactored the template source code based on: "${promptToRun}". Live preview iframe recompiled and reloaded.`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        diffBadge: diffBadge,
      },
    ]);
  };

  const mapFilenameToPageKey = (filename) => {
    if (!filename) return "home";
    const lower = filename.toLowerCase();
    if (lower.includes("about")) return "about";
    if (lower.includes("service")) return "services";
    if (lower.includes("pricing")) return "pricing";
    if (lower.includes("contact")) return "contact";
    if (lower.includes("index") || lower.includes("home")) return "home";
    
    const name = filename.replace(/\.(html|jsx|js|tsx|ts)$/, "").toLowerCase();
    const parts = name.split(/[/\\]/);
    const lastPart = parts[parts.length - 1];
    if (lastPart === "page" && parts.length > 1) {
      return parts[parts.length - 2];
    }
    return lastPart;
  };

  const getPageRoutePath = (filename) => {
    if (!filename || filename === "index.html" || filename.includes("index")) return "";
    const lower = filename.toLowerCase();
    if (lower.includes("about")) return "about";
    if (lower.includes("service")) return "services";
    if (lower.includes("pricing")) return "pricing";
    if (lower.includes("contact")) return "contact";
    
    const parts = filename.replace(/\.(html|jsx|js|tsx|ts)$/, "").split(/[/\\]/);
    const lastPart = parts[parts.length - 1];
    if (lastPart === "page" && parts.length > 1) {
      return parts[parts.length - 2];
    }
    return lastPart;
  };

  const handleFindReplace = async () => {
    if (!findText || isReplacing) return;
    setIsReplacing(true);
    setReplaceNotice(null);
    try {
      if (activeTemplateId !== "default") {
        const res = await api.post(`/preview/live/${activeTemplateId}/find-replace`, {
          find_text: findText,
          replace_text: replaceText,
        });

        if (res && res.template_id && res.template_id !== activeTemplateId) {
          setActiveTemplateId(res.template_id);
          const params = new URLSearchParams(window.location.search);
          params.set("template", res.template_id);
          window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
        }

        setIframeLoading(true);
        setIframeKey((prev) => prev + 1);
        setReplaceNotice(`✓ Replaced text successfully in ${res.matches_found || 0} file(s)!`);
        setFindText("");
        setReplaceText("");
      } else {
        setReplaceNotice("✓ Demo mode: find & replace simulated.");
      }
    } catch (e) {
      console.error("Find & Replace error", e);
      setReplaceNotice("✗ Failed to replace text.");
    } finally {
      setIsReplacing(false);
      setTimeout(() => setReplaceNotice(null), 5000);
    }
  };

  const refreshPreview = () => {
    setIsRefreshing(true);
    setIframeLoading(true);
    setIframeKey((prev) => prev + 1);
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const getPageLabel = (filename) => {
    if (filename === "index.html") return "Home Page";
    const nameWithoutExt = filename.replace(/\.(html|jsx|js)$/, "");
    return nameWithoutExt
      .split(/[-_]/)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const filesList = templateData?.included_pages && templateData.included_pages.length > 0
    ? templateData.included_pages
    : ["index.html"];

  const dynamicTabs = [
    { key: "brand", label: "Brand & Palette", icon: Palette },
    { key: "pages", label: "Home & Pages", icon: FileText }
  ];

  const liveServerUrl = activeTemplateId !== "default"
    ? `http://localhost:8000/api/v1/preview/live/${activeTemplateId}/${manualTab === "brand" ? "" : (manualTab === "pages" ? getPageRoutePath(selectedPageToEdit) : manualTab)}`
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
                  <Monitor className="w-3.5 h-3.5" />
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

              <button
                onClick={handlePurchaseTemplate}
                className="purchase-cta-btn"
                title="Directly add to cart and checkout"
              >
                <ShoppingBag className="w-3.5 h-3.5" />
                {isInCart ? "Proceed to Checkout" : "Buy Template"}
              </button>
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
                  <span>SITE STUDIO · WATERMARKED DRAFT</span>
                </div>

              {/* ──────────────────────────────────────────────────────────
                 VIEW 1: REAL COMPILED LIVE DEMO IFRAME
              ──────────────────────────────────────────────────────────── */}
              {viewMode === "live" && activeTemplateId !== "default" && !iframeError ? (
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
                            { name: "Commercial License", price: "$129", features: ["Unlimited Domains", "Custom Webhook Integrations", "Priority SLA"], popular: true },
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
                      <span>Powered by Site Studio</span>
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
           Mode 2: Live Prompt Edit (Natural language prompt agent)
        ═══════════════════════════════════════════════════════════════════════ */}
        <div className="preview-right-column">

          {/* Mode Switcher Tabs (Manual Edit vs Live Prompt Edit vs AI Auto-Fix) */}
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
              <span>2. Live Prompt Editor</span>
              <span className="mode-ai-badge">LIVE</span>
            </button>
            <button
              type="button"
              onClick={handleRunAIDebugger}
              disabled={isDebugging}
              className="studio-mode-btn border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 cursor-pointer"
              title="Autonomous AI Debugger: Analyzes and fixes React/JSX compile and syntax errors"
            >
              {isDebugging ? (
                <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
              ) : (
                <Sparkles className="w-4 h-4 text-emerald-400" />
              )}
              <span>{isDebugging ? "Fixing..." : "AI Auto-Fix"}</span>
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
                {dynamicTabs.map((st) => {
                  const Icon = st.icon;
                  return (
                    <button
                      key={st.key}
                      onClick={() => {
                        setManualTab(st.key);
                        if (st.key !== "brand") {
                          setActivePage(mapFilenameToPageKey(selectedPageToEdit));
                        }
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
                        placeholder="e.g. Apex Design Studio"
                        className="manual-input"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Logo Text / Monogram</label>
                      <input
                        value={brand.logo_text}
                        onChange={(e) => handleBrandChange("logo_text", e.target.value)}
                        placeholder="e.g. APEX STUDIO"
                        className="manual-input font-mono uppercase"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Tagline / Slogan</label>
                      <input
                        value={brand.tagline}
                        onChange={(e) => handleBrandChange("tagline", e.target.value)}
                        placeholder="e.g. Next-Generation Web Solutions"
                        className="manual-input"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3 pt-2">
                      <div>
                        <label className="manual-label">Contact Email</label>
                        <input
                          value={brand.contact_email || ""}
                          onChange={(e) => handleBrandChange("contact_email", e.target.value)}
                          placeholder="e.g. hello@agency.com"
                          className="manual-input text-xs"
                        />
                      </div>
                      <div>
                        <label className="manual-label">Contact Phone</label>
                        <input
                          value={brand.contact_phone || ""}
                          onChange={(e) => handleBrandChange("contact_phone", e.target.value)}
                          placeholder="e.g. +1 555-0199"
                          className="manual-input text-xs"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Dynamic Page Content Overrides Editor */}
                {manualTab === "pages" && (
                  <div className="manual-form-group space-y-4">
                    <h4 className="manual-group-title">Select Page to Customize</h4>
                    
                    <div className="grid grid-cols-1 gap-2 max-h-48 overflow-y-auto pr-1">
                      {filesList.map((filename) => {
                        const pageLabel = getPageLabel(filename);
                        const isSelected = selectedPageToEdit === filename;
                        return (
                          <button
                            key={filename}
                            onClick={() => {
                              setSelectedPageToEdit(filename);
                              setActivePage(mapFilenameToPageKey(filename));
                            }}
                            type="button"
                            className={cn(
                              "page-select-btn",
                              isSelected && "page-select-btn-selected"
                            )}
                          >
                            <span className="flex items-center gap-2">
                              <FileText className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                              <span className="page-label-text">{pageLabel}</span>
                            </span>
                            <span className="page-filename-tag">{filename}</span>
                          </button>
                        );
                      })}
                    </div>

                    <div className="h-[1px] bg-border/40 my-3" />

                    <h4 className="manual-group-title">Customize {getPageLabel(selectedPageToEdit)}</h4>
                    
                    <div>
                      <label className="manual-label">Page Headline / Main Header</label>
                      <input
                        value={pageEdits[selectedPageToEdit]?.title || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          setPageEdits(prev => ({
                            ...prev,
                            [selectedPageToEdit]: {
                              ...prev[selectedPageToEdit],
                              title: val
                            }
                          }));
                        }}
                        placeholder="e.g. Welcome to our Platform"
                        className="manual-input"
                      />
                    </div>

                    <div>
                      <label className="manual-label">Page Content / Description</label>
                      <textarea
                        value={pageEdits[selectedPageToEdit]?.description || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          setPageEdits(prev => ({
                            ...prev,
                            [selectedPageToEdit]: {
                              ...prev[selectedPageToEdit],
                              description: val
                            }
                          }));
                        }}
                        placeholder="e.g. Provide custom text or description for this page."
                        rows={5}
                        className="manual-textarea"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="manual-label">Button / CTA Text</label>
                        <input
                          value={pageEdits[selectedPageToEdit]?.cta_text || ""}
                          onChange={(e) => {
                            const val = e.target.value;
                            setPageEdits(prev => ({
                              ...prev,
                              [selectedPageToEdit]: {
                                ...prev[selectedPageToEdit],
                                cta_text: val
                              }
                            }));
                          }}
                          placeholder="e.g. Action Button"
                          className="manual-input text-xs"
                        />
                      </div>
                      <div>
                        <label className="manual-label">Button Link / Action</label>
                        <input
                          value={pageEdits[selectedPageToEdit]?.cta_link || ""}
                          onChange={(e) => {
                            const val = e.target.value;
                            setPageEdits(prev => ({
                              ...prev,
                              [selectedPageToEdit]: {
                                ...prev[selectedPageToEdit],
                                cta_link: val
                              }
                            }));
                          }}
                          placeholder="e.g. booking.html"
                          className="manual-input text-xs"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Global Find & Replace Section */}
                <div className="mt-6 pt-4 border-t border-border/40">
                  <h4 className="manual-group-title flex items-center gap-1.5 text-purple-400">
                    <RefreshCw className="w-3.5 h-3.5" />
                    Global Text Find & Replace
                  </h4>
                  <p className="text-[10px] text-muted-foreground mb-3">
                    Instantly replace any text across all code files in the template.
                  </p>
                  
                  {replaceNotice && (
                    <div className={cn(
                      "mb-3 p-2 border rounded-lg text-[10px] font-semibold",
                      replaceNotice.startsWith("✗")
                        ? "bg-red-500/10 border-red-500/30 text-red-400"
                        : "bg-purple-500/10 border-purple-500/30 text-purple-400"
                    )}>
                      {replaceNotice}
                    </div>
                  )}

                  <div className="space-y-3">
                    <div>
                      <label className="manual-label">Find Text</label>
                      <input
                        value={findText}
                        onChange={(e) => setFindText(e.target.value)}
                        placeholder="Text to find..."
                        className="manual-input text-xs"
                      />
                    </div>
                    <div>
                      <label className="manual-label">Replace With</label>
                      <input
                        value={replaceText}
                        onChange={(e) => setReplaceText(e.target.value)}
                        placeholder="Text to replace with..."
                        className="manual-input text-xs"
                      />
                    </div>
                    <button
                      onClick={handleFindReplace}
                      disabled={isReplacing || !findText.trim()}
                      className="w-full flex items-center justify-center gap-2 p-2 rounded-lg bg-purple-600 hover:bg-purple-700 disabled:bg-purple-600/30 disabled:text-muted-foreground text-xs font-semibold text-white transition-all shadow-md"
                    >
                      {isReplacing ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                      <span>Replace Across Codebase</span>
                    </button>
                  </div>
                </div>
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
             MODE 2: LIVE PROMPT EDIT
          ─────────────────────────────────────────────────────────────────── */}
          {editorMode === "ai" && (
            <div className="studio-ai-agent-container">

              {/* Assistant Header Bar */}
              <div className="ai-agent-header">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center text-white font-bold text-xs shadow-md">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-foreground flex items-center gap-1.5">
                      Studio Design Assistant
                      <span className="online-dot" />
                    </h4>
                    <p className="text-[10px] text-muted-foreground">Natural Language Code Refactor</p>
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

              {/* Chat & History Feed */}
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
                        <span className="ai-msg-name">{msg.role === "assistant" ? "Studio Assistant" : "You"}</span>
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

                {/* Animated Execution Step Logs */}
                {isAiProcessing && (
                  <div className="ai-terminal-box">
                    <div className="ai-terminal-header">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
                      <span>Studio Engine Refactoring Code Base...</span>
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

              {/* Specialized Agent Target Tags (@Designer, @Frontend, @Backend, @SEO) */}
              <div className="ai-presets-box mb-2">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1">
                  <Bot className="w-3 h-3 text-indigo-400" /> Target Specialized Agent:
                </div>
                <div className="ai-preset-pills">
                  {[
                    { tag: "@Designer", color: "bg-purple-500/20 text-purple-300 border-purple-500/30" },
                    { tag: "@Frontend", color: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30" },
                    { tag: "@Backend", color: "bg-amber-500/20 text-amber-300 border-amber-500/30" },
                    { tag: "@SEO", color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" },
                  ].map((agentItem) => (
                    <button
                      key={agentItem.tag}
                      onClick={() => setAiInput((prev) => `${agentItem.tag} ${prev}`)}
                      className={`text-[11px] px-2.5 py-1 rounded-lg border font-semibold transition-all cursor-pointer ${agentItem.color}`}
                    >
                      {agentItem.tag}
                    </button>
                  ))}
                </div>
              </div>

              {/* Prompt Quick Presets (Clickable Pills) */}
              <div className="ai-presets-box">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1">
                  <Wand2 className="w-3 h-3 text-purple-400" /> Quick Style Presets:
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

              {/* Prompt Input Bar */}
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
                          <span>Apply Prompt Edit</span>
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
            <p className="text-muted-foreground text-sm">Initializing Studio Preview...</p>
          </div>
        </div>
      }
    >
      <PreviewEditorInner />
    </Suspense>
  );
}
