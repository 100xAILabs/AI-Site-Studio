import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import {
  Sparkles, ArrowLeft, ArrowRight, Loader2, CheckCircle2, Image as ImageIcon,
  Globe, Layers, FileText, LayoutGrid, Plus, Trash2, Info, Building2, Palette,
  Phone, Mail, MapPin, Share2, Wand2, Edit3, Check, RefreshCw, Eye, Upload, Link as LinkIcon, ShoppingBag, X, Zap,
  Download, ShoppingCart, Folder
} from "lucide-react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { useCartStore } from "@/store";
import Navbar from "@/components/layout/Navbar";
import "./Page.css";

const GENERATION_STEPS = [
  {
    id: 1,
    agent: "Agent 1/8 (Planning Agent)",
    icon: "📋",
    name: "Planning Agent",
    title: "Analyzing domain requirements & architectural site breakdown...",
    detail: "Synthesizing page hierarchy, multi-page routes, and business specifications.",
    duration: 2400,
  },
  {
    id: 2,
    agent: "Agent 2/8 (UI Designer Agent)",
    icon: "🎨",
    name: "UI Designer Agent",
    title: "Establishing typography, color palette & design tokens...",
    detail: "Configuring tailored HSL tokens, dark theme contrast, and font styling.",
    duration: 2400,
  },
  {
    id: 3,
    agent: "Agent 3/8 (Frontend Agent)",
    icon: "💻",
    name: "Frontend Agent",
    title: "Synthesizing multi-page React components & responsive layouts...",
    detail: "Engineering clean React 18 + Tailwind layout with interactive navigation.",
    duration: 4200,
  },
  {
    id: 4,
    agent: "Agent 4/8 (Backend Agent)",
    icon: "⚙️",
    name: "Backend Agent",
    title: "Synthesizing dedicated standalone REST API endpoints...",
    detail: "Generating endpoints: /api/contact, /api/leads, /api/health.",
    duration: 2500,
  },
  {
    id: 5,
    agent: "Agent 5/8 (Database Agent)",
    icon: "🗄️",
    name: "Database Agent",
    title: "Initializing isolated SQLite database & seed fixtures...",
    detail: "Scaffolding data tables, indexes, and initial demo data models.",
    duration: 2200,
  },
  {
    id: 6,
    agent: "Agent 6/8 (SEO Agent)",
    icon: "🔍",
    name: "SEO Agent",
    title: "Synthesizing Schema.org JSON-LD & OpenGraph meta tags...",
    detail: "Configuring structured data, semantic headers, and robots.txt rules.",
    duration: 2000,
  },
  {
    id: 7,
    agent: "Agent 7/8 (Testing Agent)",
    icon: "🧪",
    name: "Testing Agent",
    title: "Running AST syntax repair & autonomous AI compiler audit...",
    detail: "Validating JSX balancing, resolving imports, and checking build integrity.",
    duration: 2400,
  },
  {
    id: 8,
    agent: "Agent 8/8 (Deployment Agent)",
    icon: "📦",
    name: "Deployment Agent",
    title: "Packaging full-stack ZIP & registering Studio Project...",
    detail: "Persisting standalone archive in database and initializing live preview.",
    duration: 2000,
  },
];

const PRESET_COLOR_PALETTES = [
  { id: "emerald_slate", name: "Emerald & Slate", primary: "#10b981", secondary: "#0f172a", accent: "#38bdf8", bgGradient: "linear-gradient(135deg, #0f172a 0%, #064e3b 100%)" },
  { id: "cyber_neon", name: "Cyberpunk Neon", primary: "#8b5cf6", secondary: "#090d16", accent: "#f43f5e", bgGradient: "linear-gradient(135deg, #090d16 0%, #4c1d95 100%)" },
  { id: "electric_blue", name: "Electric Blue & Indigo", primary: "#3b82f6", secondary: "#030712", accent: "#6366f1", bgGradient: "linear-gradient(135deg, #030712 0%, #1e3a8a 100%)" },
  { id: "parisian_bakery", name: "Warm Parisian Bakery", primary: "#d97706", secondary: "#1c1917", accent: "#f59e0b", bgGradient: "linear-gradient(135deg, #1c1917 0%, #78350f 100%)" },
  { id: "gold_obsidian", name: "Luxury Gold & Obsidian", primary: "#eab308", secondary: "#09090b", accent: "#fde047", bgGradient: "linear-gradient(135deg, #09090b 0%, #422006 100%)" },
  { id: "oceanic_azure", name: "Oceanic Azure & Teal", primary: "#06b6d4", secondary: "#0f172a", accent: "#3b82f6", bgGradient: "linear-gradient(135deg, #0f172a 0%, #164e63 100%)" },
  { id: "sage_forest", name: "Sage Forest Green", primary: "#059669", secondary: "#064e3b", accent: "#10b981", bgGradient: "linear-gradient(135deg, #064e3b 0%, #022c22 100%)" },
  { id: "crimson_cyber", name: "Crimson Cyber Red", primary: "#dc2626", secondary: "#0f172a", accent: "#f87171", bgGradient: "linear-gradient(135deg, #0f172a 0%, #7f1d1d 100%)" },
  { id: "pastel_lavender", name: "Pastel Lavender & Pink", primary: "#a855f7", secondary: "#111827", accent: "#ec4899", bgGradient: "linear-gradient(135deg, #111827 0%, #581c87 100%)" },
  { id: "royal_purple", name: "Royal Purple & Amber", primary: "#7e22ce", secondary: "#0f172a", accent: "#f59e0b", bgGradient: "linear-gradient(135deg, #0f172a 0%, #3b0764 100%)" },
  { id: "sunset_citrus", name: "Sunset Citrus Orange", primary: "#f97316", secondary: "#18181b", accent: "#fbbf24", bgGradient: "linear-gradient(135deg, #18181b 0%, #7c2d12 100%)" },
  { id: "custom", name: "Custom Studio Mode", primary: "#10b981", secondary: "#0f172a", accent: "#38bdf8", bgGradient: "linear-gradient(135deg, #0f172a 0%, #10b981 100%)" },
];

const POPULAR_INDUSTRIES = [
  "SaaS & Tech Platform",
  "Creative Studio & Agency",
  "E-Commerce & Retail Store",
  "Restaurant & Cafe",
  "Personal Developer Portfolio",
  "Corporate & Financial Firm",
  "Healthcare & Wellness",
  "Real Estate & Luxury Living",
  "Other (Custom)"
];

// Helper: Convert HSV to Hex string
function hsvToHex(h, s, v) {
  s /= 100;
  v /= 100;
  let c = v * s;
  let x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  let m = v - c;
  let r = 0, g = 0, b = 0;
  if (0 <= h && h < 60) { r = c; g = x; b = 0; }
  else if (60 <= h && h < 120) { r = x; g = c; b = 0; }
  else if (120 <= h && h < 180) { r = 0; g = c; b = x; }
  else if (180 <= h && h < 240) { r = 0; g = x; b = c; }
  else if (240 <= h && h < 300) { r = x; g = 0; b = c; }
  else if (300 <= h && h < 360) { r = c; g = 0; b = x; }

  r = Math.round((r + m) * 255).toString(16).padStart(2, '0');
  g = Math.round((g + m) * 255).toString(16).padStart(2, '0');
  b = Math.round((b + m) * 255).toString(16).padStart(2, '0');

  return `#${r}${g}${b}`;
}

// Helper: Convert Hex string to HSV object {h, s, v}
function hexToHsv(hex) {
  if (!hex) return { h: 230, s: 80, v: 90 };
  let c = hex.replace('#', '');
  if (c.length === 3) c = c.split('').map(x => x + x).join('');
  if (c.length !== 6) return { h: 230, s: 80, v: 90 };
  let r = parseInt(c.substring(0, 2), 16) / 255;
  let g = parseInt(c.substring(2, 4), 16) / 255;
  let b = parseInt(c.substring(4, 6), 16) / 255;

  let max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h, s, v = max;
  let d = max - min;
  s = max === 0 ? 0 : d / max;

  if (max === min) {
    h = 0;
  } else {
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }

  return {
    h: Math.round(h * 360),
    s: Math.round(s * 100),
    v: Math.round(v * 100)
  };
}

// Visual Color Picker Popup Component matching user screenshot
function VisualColorPickerModal({ isOpen, colorItem, onClose, onChange }) {
  const [hex, setHex] = useState(colorItem?.hex || "#6366f1");
  const [hue, setHue] = useState(230);
  const [sat, setSat] = useState(80);
  const [val, setVal] = useState(90);
  const canvasRef = useRef(null);
  const isDraggingRef = useRef(false);

  // Sync state & calculate exact Hue when color item opens
  useEffect(() => {
    if (colorItem?.hex) {
      setHex(colorItem.hex);
      const hsv = hexToHsv(colorItem.hex);
      setHue(hsv.h);
      setSat(hsv.s);
      setVal(hsv.v);
    }
  }, [colorItem]);

  if (!isOpen || !colorItem) return null;

  const updateColorFromCanvas = (e) => {
    if (!canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;

    const x = Math.max(0, Math.min(rect.width, clientX - rect.left));
    const y = Math.max(0, Math.min(rect.height, clientY - rect.top));

    const newSat = Math.round((x / rect.width) * 100);
    const newVal = Math.round((1 - y / rect.height) * 100);

    setSat(newSat);
    setVal(newVal);

    const newHex = hsvToHex(hue, newSat, newVal);
    setHex(newHex);
    onChange(colorItem.id, newHex);
  };

  const handleMouseDown = (e) => {
    isDraggingRef.current = true;
    updateColorFromCanvas(e);
  };

  const handleMouseMove = (e) => {
    if (isDraggingRef.current) {
      updateColorFromCanvas(e);
    }
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  const handleHueChange = (e) => {
    const newHue = parseInt(e.target.value, 10);
    setHue(newHue);
    const newHex = hsvToHex(newHue, sat, val);
    setHex(newHex);
    onChange(colorItem.id, newHex);
  };

  const handleSwatchClick = (swatchHex) => {
    setHex(swatchHex);
    const hsv = hexToHsv(swatchHex);
    setHue(hsv.h);
    setSat(hsv.s);
    setVal(hsv.v);
    onChange(colorItem.id, swatchHex);
  };

  const modalContent = (
    <div
      className="color-picker-overlay animate-fade-in"
      onMouseUp={handleMouseUp}
      onTouchEnd={handleMouseUp}
    >
      <div className="color-picker-dialog">
        {/* Header Bar */}
        <div className="color-picker-header" style={{ backgroundColor: hex }}>
          <div className="flex items-center gap-2 drop-shadow-md">
            <span className="w-4 h-4 rounded-full border border-white/60 inline-block bg-white/30" />
            <span>{hex}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-md bg-slate-950/80 text-white font-sans font-semibold border border-white/20">
              {colorItem.label}
            </span>
            <button type="button" onClick={onClose} className="p-1 text-white hover:text-white/80 transition-opacity">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="color-picker-body">
          {/* 2D Saturation / Value Canvas Box (Shows all shades for active Hue line!) */}
          <div>
            <div className="color-picker-section-label">
              <span>Shade & Tint Canvas</span>
              <span className="font-mono text-indigo-400">Hue: {hue}°</span>
            </div>

            <div
              ref={canvasRef}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onTouchStart={handleMouseDown}
              onTouchMove={updateColorFromCanvas}
              className="color-picker-canvas-box"
              style={{
                backgroundColor: `hsl(${hue}, 100%, 50%)`,
                backgroundImage: `
                  linear-gradient(to top, #000, transparent),
                  linear-gradient(to right, #fff, transparent)
                `
              }}
            >
              {/* Pointer circle indicator */}
              <div
                className="absolute w-5 h-5 rounded-full border-2 border-white shadow-lg pointer-events-none -translate-x-1/2 -translate-y-1/2"
                style={{
                  left: `${sat}%`,
                  top: `${100 - val}%`,
                  backgroundColor: hex
                }}
              />
            </div>
          </div>

          {/* Hue Rainbow Slider Bar */}
          <div>
            <div className="color-picker-section-label">
              <span>Hue Color Line</span>
              <span className="text-[10px] text-slate-400 font-normal">Slide to change color family</span>
            </div>
            <input
              type="range"
              min="0"
              max="360"
              value={hue}
              onChange={handleHueChange}
              className="color-picker-hue-range"
              style={{
                background: `linear-gradient(to right, #ff0000 0%, #ffff00 17%, #00ff00 33%, #00ffff 50%, #0000ff 67%, #ff00ff 83%, #ff0000 100%)`
              }}
            />
          </div>

          {/* Quick Swatches Grid */}
          <div>
            <label className="color-picker-section-label">Quick Swatches</label>
            <div className="color-picker-swatch-grid">
              {[
                { hex: "#3b82f6", name: "Blue" },
                { hex: "#6366f1", name: "Indigo" },
                { hex: "#8b5cf6", name: "Violet" },
                { hex: "#ec4899", name: "Pink" },
                { hex: "#f43f5e", name: "Rose" },
                { hex: "#ef4444", name: "Red" },
                { hex: "#f97316", name: "Orange" },
                { hex: "#f59e0b", name: "Amber" },
                { hex: "#10b981", name: "Emerald" },
                { hex: "#06b6d4", name: "Cyan" },
                { hex: "#0f172a", name: "Dark Slate" },
                { hex: "#ffffff", name: "White" }
              ].map((swatch) => (
                <button
                  key={swatch.hex}
                  type="button"
                  onClick={() => handleSwatchClick(swatch.hex)}
                  className="color-picker-swatch-btn"
                  style={{ backgroundColor: swatch.hex }}
                  title={swatch.name}
                />
              ))}
            </div>
          </div>

          {/* Hex Input & Done Button */}
          <div className="color-picker-footer">
            <div className="color-picker-hex-input-wrapper">
              <span className="text-slate-400 font-bold">Hex:</span>
              <input
                type="text"
                value={hex}
                onChange={(e) => {
                  const val = e.target.value;
                  setHex(val);
                  if (val.length === 7 && val.startsWith("#")) {
                    const hsv = hexToHsv(val);
                    setHue(hsv.h);
                    setSat(hsv.s);
                    setVal(hsv.v);
                    onChange(colorItem.id, val);
                  }
                }}
                className="color-picker-hex-input"
              />
            </div>
            <button
              type="button"
              onClick={onClose}
              className="color-picker-done-btn"
            >
              Done
            </button>
          </div>
        </div>

      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}

export default function GenerateTemplatePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const token = useAuthStore((s) => s.token);

  // Main Mode State
  const [creatorMode, setCreatorMode] = useState("creator"); // "creator" | "quick"

  // Structured Business Fields
  const [businessName, setBusinessName] = useState("");
  const [businessType, setBusinessType] = useState("SaaS & Tech Platform");
  const [customBusinessType, setCustomBusinessType] = useState("");
  const [businessDescription, setBusinessDescription] = useState("");

  // Dynamic Brand Colors List (Supports + Add Color)
  const [selectedColorPreset, setSelectedColorPreset] = useState("emerald_slate");
  const [themeMode, setThemeMode] = useState("dark"); // "dark" | "light"
  const [brandColorsList, setBrandColorsList] = useState([
    { id: "primary", label: "Primary Accent", hex: "#10b981", isDefault: true },
    { id: "secondary", label: "Secondary Surface", hex: "#0f172a", isDefault: true },
    { id: "accent", label: "Highlight Accent", hex: "#38bdf8", isDefault: true },
  ]);

  // Active Picker Modal ID
  const [activePickerColorId, setActivePickerColorId] = useState(null);
  const activePickerItem = brandColorsList.find((c) => c.id === activePickerColorId);

  // Logo
  const [logoType, setLogoType] = useState("upload"); // "upload" | "url" | "ai"
  const [logoPrompt, setLogoPrompt] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);

  // Contact Details
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactAddress, setContactAddress] = useState("");
  const [socialTwitter, setSocialTwitter] = useState("");
  const [socialLinkedin, setSocialLinkedin] = useState("");
  const [socialGithub, setSocialGithub] = useState("");
  const [socialInstagram, setSocialInstagram] = useState("");

  // Prompt & Generation States
  const [prompt, setPrompt] = useState(location.state?.prompt || "");
  const [framework, setFramework] = useState("html");
  const [backendFramework, setBackendFramework] = useState("fastapi");
  const [cssEngine, setCssEngine] = useState("tailwind");
  const [techTab, setTechTab] = useState("framework"); // "framework" | "backend" | "css"
  const [projectScope, setProjectScope] = useState("fullstack"); // "frontend" | "fullstack"
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [error, setError] = useState("");
  const [generatedTemplate, setGeneratedTemplate] = useState(null);

  // Advanced Prompt Analysis and Customization States
  const [step, setStep] = useState("prompt"); // "prompt" | "questions"
  const [modelTier, setModelTier] = useState("pro"); // "pro" | "flash"
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [enhancedSpecs, setEnhancedSpecs] = useState(null);
  const [architectureType, setArchitectureType] = useState("multi_page"); // "single_page" | "multi_page"
  const [isMultipage, setIsMultipage] = useState(true);
  const [architectureReasoning, setArchitectureReasoning] = useState("");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [pages, setPages] = useState([]);
  const [multiPageCache, setMultiPageCache] = useState([]);
  const [newPageName, setNewPageName] = useState("");
  const [isPreparing, setIsPreparing] = useState(false);
  const [isGeneratingPalette, setIsGeneratingPalette] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  // Cart hooks
  const addToCart = useCartStore((s) => s.addItem);
  const isInCart = useCartStore((s) => s.isInCart(generatedTemplate?.id));

  // Download Generated Template ZIP handler
  const handleDownloadSource = async () => {
    if (!generatedTemplate?.id) return;
    setIsDownloading(true);
    try {
      const res = await api.post(`/templates/${generatedTemplate.id}/download?format=zip`, {}, token);
      if (res?.download_url) {
        window.open(res.download_url, "_blank");
      }
    } catch (err) {
      console.error("Failed to download template:", err);
      alert("Failed to download template zip. Please try again.");
    } finally {
      setIsDownloading(false);
    }
  };

  // Handle Dynamic Brand Colors
  const handleAddCustomColor = () => {
    const newId = `color_${Date.now()}`;
    const newColor = {
      id: newId,
      label: `Brand Color ${brandColorsList.length + 1}`,
      hex: "#8b5cf6",
      isDefault: false,
    };
    setBrandColorsList((prev) => [...prev, newColor]);
    setActivePickerColorId(newId);
  };

  const handleRemoveCustomColor = (id) => {
    setBrandColorsList((prev) => prev.filter((c) => c.id !== id));
  };

  const handleUpdateColor = (id, newHex) => {
    setBrandColorsList((prev) =>
      prev.map((c) => (c.id === id ? { ...c, hex: newHex } : c))
    );
  };

  const handleUpdateColorLabel = (id, newLabel) => {
    setBrandColorsList((prev) =>
      prev.map((c) => (c.id === id ? { ...c, label: newLabel } : c))
    );
  };

  // Handle Preset Palette Selection
  const handleSelectPalettePreset = (preset) => {
    setSelectedColorPreset(preset.id);
    if (preset.id !== "custom") {
      setBrandColorsList((prev) =>
        prev.map((c) => {
          if (c.id === "primary") return { ...c, hex: preset.primary };
          if (c.id === "secondary") return { ...c, hex: preset.secondary };
          if (c.id === "accent") return { ...c, hex: preset.accent };
          return c;
        })
      );
    }
  };

  // Dynamic Random Palette Generator
  const handleGenerateRandomPalette = () => {
    const hue = Math.floor(Math.random() * 360);
    const priHex = hsvToHex(hue, 85, 55);
    const secHex = hsvToHex((hue + 210) % 360, 65, 10);
    const accHex = hsvToHex((hue + 60) % 360, 90, 60);

    setBrandColorsList((prev) =>
      prev.map((c) => {
        if (c.id === "primary") return { ...c, hex: priHex };
        if (c.id === "secondary") return { ...c, hex: secHex };
        if (c.id === "accent") return { ...c, hex: accHex };
        return c;
      })
    );
    setSelectedColorPreset("custom");
  };

  // Dynamic Studio Palette Generator (Calls AI API or falls back to harmonic generation)
  const handleGenerateStudioPalette = async () => {
    setIsGeneratingPalette(true);
    try {
      const res = await api.post("/ai/color-palette", {
        industry: businessType === "Other (Custom)" ? (customBusinessType || "General") : (businessType || "SaaS & Tech Platform"),
        mood: "professional"
      }, token);
      if (res && res.primary) {
        setBrandColorsList((prev) =>
          prev.map((c) => {
            if (c.id === "primary") return { ...c, hex: res.primary || res.primary_color || "#10b981" };
            if (c.id === "secondary") return { ...c, hex: res.secondary || res.secondary_color || "#0f172a" };
            if (c.id === "accent") return { ...c, hex: res.accent || res.accent_color || "#38bdf8" };
            return c;
          })
        );
        setSelectedColorPreset("custom");
      } else {
        handleGenerateRandomPalette();
      }
    } catch (err) {
      console.warn("AI palette generator fallback to harmonic palette:", err);
      handleGenerateRandomPalette();
    } finally {
      setIsGeneratingPalette(false);
    }
  };

  // Upload Logo File Handler
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setError("File size exceeds 10MB limit.");
      return;
    }

    setIsUploadingLogo(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const API_URL = import.meta.env.VITE_API_URL ?? import.meta.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
      const res = await fetch(`${API_URL}/files/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to upload logo image file");
      }

      const data = await res.json();
      if (data?.url) {
        setLogoUrl(data.url);
      }
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to upload logo image file");
    } finally {
      setIsUploadingLogo(false);
    }
  };

  // Synthesize creator inputs into prompt string
  const buildSynthesizedPrompt = () => {
    const activeIndustry = businessType === "Other (Custom)" ? customBusinessType : businessType;
    let parts = [];
    if (businessName.trim()) {
      parts.push(`Create a high-fidelity website template for "${businessName.trim()}"`);
    } else {
      parts.push("Create a high-fidelity website template");
    }
    if (activeIndustry.trim()) {
      parts.push(`Industry/Niche: ${activeIndustry.trim()}`);
    }
    if (businessDescription.trim()) {
      parts.push(`Overview & Vision: ${businessDescription.trim()}`);
    }

    const colorsSummary = brandColorsList.map((c) => `${c.label}: ${c.hex}`).join(", ");
    parts.push(`Brand Color Specifications (${themeMode} theme): ${colorsSummary}`);

    if (logoType === "upload" && logoUrl.trim()) {
      parts.push(`Uploaded Brand Logo URL: ${logoUrl.trim()}`);
    } else if (logoType === "url" && logoUrl.trim()) {
      parts.push(`Brand Logo URL: ${logoUrl.trim()}`);
    } else if (logoType === "ai" && logoPrompt.trim()) {
      parts.push(`Logo Concept: ${logoPrompt.trim()}`);
    }

    let contacts = [];
    if (contactEmail.trim()) contacts.push(`Email: ${contactEmail.trim()}`);
    if (contactPhone.trim()) contacts.push(`Phone: ${contactPhone.trim()}`);
    if (contactAddress.trim()) contacts.push(`Location: ${contactAddress.trim()}`);
    if (socialTwitter.trim()) contacts.push(`Twitter: ${socialTwitter.trim()}`);
    if (socialLinkedin.trim()) contacts.push(`LinkedIn: ${socialLinkedin.trim()}`);
    if (socialGithub.trim()) contacts.push(`GitHub: ${socialGithub.trim()}`);
    if (socialInstagram.trim()) contacts.push(`Instagram: ${socialInstagram.trim()}`);

    if (contacts.length > 0) {
      parts.push(`Contact Details: ${contacts.join(", ")}`);
    }

    return parts.join(". ") + ".";
  };

  // Sync creator inputs into prompt editor
  const handleSyncToPrompt = () => {
    const synth = buildSynthesizedPrompt();
    setPrompt(synth);
  };

  // Handle Prompt Enhancement
  const handleEnhancePrompt = async () => {
    const activePrompt = prompt.trim() || buildSynthesizedPrompt();
    if (!activePrompt || activePrompt.length < 5) {
      setError("Please write a short description or fill in business details first.");
      return;
    }
    setError("");
    setIsEnhancing(true);
    try {
      const res = await api.post("/ai/enhance-prompt", { prompt: activePrompt }, token);
      if (res?.enhanced_prompt) {
        setPrompt(res.enhanced_prompt);
        setEnhancedSpecs(res);
      }
    } catch (err) {
      console.error(err);
      setError("Something error happens please try again later");
    } finally {
      setIsEnhancing(false);
    }
  };

  // Handle steps animation during generation
  useEffect(() => {
    if (!isGenerating || currentStep >= GENERATION_STEPS.length) return;

    const step = GENERATION_STEPS[currentStep];
    const timer = setTimeout(() => {
      setCompletedSteps((prev) => [...prev, step.id]);
      if (currentStep < GENERATION_STEPS.length - 1) {
        setCurrentStep((prev) => prev + 1);
      }
    }, step.duration);

    return () => clearTimeout(timer);
  }, [isGenerating, currentStep]);

  const handlePrepare = async (e) => {
    e.preventDefault();

    let finalPrompt = prompt.trim();
    if (!finalPrompt && creatorMode === "creator") {
      finalPrompt = buildSynthesizedPrompt();
      setPrompt(finalPrompt);
    }

    if (!finalPrompt || finalPrompt.length < 10) {
      setError("Please provide at least 10 characters of website description or business details.");
      return;
    }

    setError("");
    setIsPreparing(true);

    const activeIndustry = businessType === "Other (Custom)" ? customBusinessType : businessType;

    const payload = {
      prompt: finalPrompt,
      model_tier: modelTier,
      business_name: businessName.trim() || undefined,
      business_type: activeIndustry.trim() || undefined,
      brand_colors: {
        preset: selectedColorPreset,
        theme: themeMode,
        colors_list: brandColorsList,
        primary: brandColorsList.find((c) => c.id === "primary")?.hex || "#10b981",
        secondary: brandColorsList.find((c) => c.id === "secondary")?.hex || "#0f172a",
        accent: brandColorsList.find((c) => c.id === "accent")?.hex || "#38bdf8",
      },
      logo_info: {
        type: logoType,
        url: (logoType === "url" || logoType === "upload") ? logoUrl.trim() : "",
        prompt: logoType === "ai" ? logoPrompt.trim() : "",
      },
      contact_details: {
        email: contactEmail.trim(),
        phone: contactPhone.trim(),
        address: contactAddress.trim(),
        socials: {
          twitter: socialTwitter.trim(),
          linkedin: socialLinkedin.trim(),
          github: socialGithub.trim(),
          instagram: socialInstagram.trim(),
        },
      },
    };

    try {
      const res = await api.post("/templates/generate/prepare", payload, token);
      const arch = res.architecture_type || "multi_page";
      setArchitectureType(arch);
      setIsMultipage(res.is_multipage !== false);
      setArchitectureReasoning(res.architecture_reasoning || "");
      setQuestions(res.questions || []);

      const defaultAnswers = {};
      res.questions?.forEach((q) => {
        if (q.options && q.options.length > 0) {
          defaultAnswers[q.id] = q.options[0];
        }
      });
      setAnswers(defaultAnswers);

      const fetchedPages = res.suggested_pages || [];
      setPages(fetchedPages);
      setMultiPageCache(fetchedPages);
      setStep("questions");
    } catch (err) {
      console.error(err);
      setError(err?.message || "Prompt analysis failed. Please check your settings and try again.");
    } finally {
      setIsPreparing(false);
    }
  };

  const handleToggleArchitecture = (targetType) => {
    if (targetType === architectureType) return;
    setArchitectureType(targetType);

    if (targetType === "single_page") {
      setIsMultipage(false);
      if (pages.length > 1) {
        setMultiPageCache(pages);
      }
      setPages([
        {
          name: "Home Landing Page",
          filename: "index.html",
          content_summary: "Unified single-page layout featuring Hero header, Features grid, Showcase cards, Interactive tabs, Pricing tiers, and Contact section.",
          selected: true
        }
      ]);
    } else {
      setIsMultipage(true);
      if (multiPageCache.length > 1) {
        setPages(multiPageCache);
      } else {
        setPages([
          { name: "Home Page", filename: "index.html", content_summary: "Hero section, primary features grid, CTA banner, and multi-column footer.", selected: true },
          { name: "About Details", filename: "about.html", content_summary: "Company mission, vision, team profiles, and story timeline.", selected: true },
          { name: "Services", filename: "services.html", content_summary: "Service offerings, pricing cards, features list, and inquiry form.", selected: true },
          { name: "Contact Page", filename: "contact.html", content_summary: "Interactive contact form, location details, map placeholder, and FAQs.", selected: true }
        ]);
      }
    }
  };

  const handleAddCustomPage = (e) => {
    e.preventDefault();
    if (!newPageName.trim()) return;

    const name = newPageName.trim();
    const filename = `${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}.html`;

    const newPage = {
      name,
      filename,
      content_summary: `Custom ${name} page layout tailored to your specific business requirements.`,
      selected: true
    };

    setPages((prev) => [...prev, newPage]);
    if (architectureType === "multi_page") {
      setMultiPageCache((prev) => [...prev, newPage]);
    }
    setNewPageName("");
  };

  const handleRemovePage = (filename) => {
    if (filename === "index.html") return;
    setPages((prev) => prev.filter((p) => p.filename !== filename));
    setMultiPageCache((prev) => prev.filter((p) => p.filename !== filename));
  };

  const handleGenerate = async () => {
    setError("");
    setIsGenerating(true);
    setCurrentStep(0);
    setCompletedSteps([]);
    setGeneratedTemplate(null);

    const selectedPages = pages.filter((p) => p.selected !== false);
    const activeIndustry = businessType === "Other (Custom)" ? customBusinessType : businessType;

    try {
      const response = await api.post(
        "/templates/generate",
        {
          prompt,
          framework,
          backend_framework: backendFramework,
          css_engine: cssEngine,
          project_scope: projectScope,
          answers,
          pages: selectedPages,
          architecture_type: architectureType,
          is_multipage: isMultipage,
          model_tier: modelTier,
          business_name: businessName.trim() || undefined,
          business_type: activeIndustry.trim() || undefined,
          brand_colors: {
            preset: selectedColorPreset,
            theme: themeMode,
            colors_list: brandColorsList,
            primary: brandColorsList.find((c) => c.id === "primary")?.hex || "#10b981",
            secondary: brandColorsList.find((c) => c.id === "secondary")?.hex || "#0f172a",
            accent: brandColorsList.find((c) => c.id === "accent")?.hex || "#38bdf8",
          },
          logo_info: {
            type: logoType,
            url: (logoType === "url" || logoType === "upload") ? logoUrl.trim() : "",
            prompt: logoType === "ai" ? logoPrompt.trim() : "",
          },
          contact_details: {
            email: contactEmail.trim(),
            phone: contactPhone.trim(),
            address: contactAddress.trim(),
            socials: {
              twitter: socialTwitter.trim(),
              linkedin: socialLinkedin.trim(),
              github: socialGithub.trim(),
              instagram: socialInstagram.trim(),
            },
          },
        },
        token
      );

      setGeneratedTemplate(response);
      setCompletedSteps([1, 2, 3, 4, 5, 6, 7, 8]);
      setCurrentStep(GENERATION_STEPS.length);
    } catch (err) {
      console.error(err);
      setError(err?.message || "Template generation failed. Please check your AI provider configuration and try again.");
      setIsGenerating(false);
    }
  };

  const isGenerationComplete = generatedTemplate && completedSteps.length === GENERATION_STEPS.length;
  const primaryHex = brandColorsList.find((c) => c.id === "primary")?.hex || "#10b981";
  const secondaryHex = brandColorsList.find((c) => c.id === "secondary")?.hex || "#0f172a";
  const accentHex = brandColorsList.find((c) => c.id === "accent")?.hex || "#38bdf8";

  return (
    <>
      <Navbar />

      {/* Visual Color Picker Popup Modal */}
      <VisualColorPickerModal
        isOpen={!!activePickerItem}
        colorItem={activePickerItem}
        onClose={() => setActivePickerColorId(null)}
        onChange={handleUpdateColor}
      />

      <div className="generate-page">
        <div className="generate-container">

          {/* Header */}
          <div className="generate-header">
            <Link to="/marketplace" className="back-link">
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Marketplace</span>
            </Link>
            <h1 className="generate-title">
              <Sparkles className="title-icon text-primary animate-pulse" />
              <span>Website Studio Creator & Builder</span>
            </h1>
            <p className="generate-subtitle">
              Enter your exact business details, brand colors, logo, and contact info. Our studio pipeline synthesizes your inputs and builds a hyper-personalized production template.
            </p>
          </div>

          <div className="generate-card-wrapper">
            {error && (
              <div className="p-4 mb-6 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-300 text-sm flex items-center justify-between animate-fade-in shadow-lg">
                <span className="font-medium flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-rose-500 animate-ping" />
                  {error}
                </span>
                <button
                  type="button"
                  onClick={() => setError("")}
                  className="text-rose-500 hover:underline text-xs ml-4 font-medium"
                >
                  Dismiss
                </button>
              </div>
            )}

            {!isGenerating && !generatedTemplate && step === "prompt" && (
              /* Prompt Input Form */
              <form onSubmit={handlePrepare} className="prompt-form glass-panel animate-fade-in">

                {/* Top Mode Selector: Studio Creator vs Quick Prompt */}
                <div className="creator-mode-tabs">
                  <button
                    type="button"
                    onClick={() => setCreatorMode("creator")}
                    className={`mode-tab-btn ${creatorMode === "creator" ? "active" : ""}`}
                  >
                    <Building2 className="w-4 h-4 text-primary" />
                    <span>Detailed Studio Creator Mode</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setCreatorMode("quick")}
                    className={`mode-tab-btn ${creatorMode === "quick" ? "active" : ""}`}
                  >
                    <Wand2 className="w-4 h-4 text-secondary" />
                    <span>Quick Prompt Mode</span>
                  </button>
                </div>

                {/* Structured Studio Creator Inputs */}
                {creatorMode === "creator" && (
                  <div className="business-details-section animate-fade-in">
                    <div className="business-section-header">
                      <div className="business-section-title">
                        <Building2 className="w-5 h-5 text-primary" />
                        <span>Business & Brand Specification</span>
                      </div>
                      <span className="business-section-subtitle">Values embedded directly in template code</span>
                    </div>

                    {/* Business Name & Type */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="prompt-label text-xs uppercase tracking-wider text-muted-foreground font-semibold">Business Name</label>
                        <input
                          type="text"
                          value={businessName}
                          onChange={(e) => setBusinessName(e.target.value)}
                          placeholder="e.g. Acme Cybernetics Inc."
                          className="prompt-textarea !py-2.5"
                        />
                      </div>

                      <div>
                        <label className="prompt-label text-xs uppercase tracking-wider text-muted-foreground font-semibold">Business Type / Industry</label>
                        <select
                          value={businessType}
                          onChange={(e) => setBusinessType(e.target.value)}
                          className="prompt-textarea !py-2.5 cursor-pointer"
                        >
                          {POPULAR_INDUSTRIES.map((ind) => (
                            <option key={ind} value={ind}>
                              {ind}
                            </option>
                          ))}
                        </select>
                        {businessType === "Other (Custom)" && (
                          <input
                            type="text"
                            value={customBusinessType}
                            onChange={(e) => setCustomBusinessType(e.target.value)}
                            placeholder="Specify custom industry..."
                            className="prompt-textarea !py-2.5 mt-2"
                          />
                        )}
                      </div>
                    </div>

                    {/* Business Description */}
                    <div>
                      <label className="prompt-label text-xs uppercase tracking-wider text-muted-foreground font-semibold">Business Overview & Vision</label>
                      <textarea
                        value={businessDescription}
                        onChange={(e) => setBusinessDescription(e.target.value)}
                        placeholder="Describe key services, target audience, core offerings, unique selling points, and design preferences..."
                        className="prompt-textarea"
                        rows={3}
                      />
                    </div>

                    {/* Brand Colors & Theme (Ultra-Clean Single-Button Multi-Color Selector) */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <label className="prompt-label text-xs uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1.5 mb-0">
                          <Palette className="w-4 h-4 text-primary" />
                          <span>Brand Colors & Theme</span>
                        </label>

                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={handleGenerateStudioPalette}
                            disabled={isGeneratingPalette}
                            className="btn-studio-palette"
                            title="Generate harmonic palette"
                          >
                            <Sparkles className={`w-3.5 h-3.5 ${isGeneratingPalette ? "animate-spin" : ""}`} />
                            <span>Dynamic Palette</span>
                          </button>
                        </div>
                      </div>

                      {/* Sleek Color Chips Bar with Click-to-Pick Canvas Modal & "+ Add Color" */}
                      <div className="p-3.5 bg-card rounded-xl border border-border flex flex-wrap items-center gap-2.5">
                        {brandColorsList.map((c) => (
                          <div
                            key={c.id}
                            onClick={() => setActivePickerColorId(c.id)}
                            className="flex items-center gap-2 p-1.5 pl-2.5 pr-2 rounded-xl border border-border bg-muted/60 hover:border-primary/50 hover:bg-muted transition-all cursor-pointer shadow-sm group"
                            title="Click to open visual color picker popup"
                          >
                            <span
                              className="w-5 h-5 rounded-full border border-white/30 shadow-inner shrink-0 group-hover:scale-110 transition-transform"
                              style={{ backgroundColor: c.hex }}
                            />
                            <div className="flex flex-col text-left">
                              <input
                                type="text"
                                value={c.label}
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) => handleUpdateColorLabel(c.id, e.target.value)}
                                className="text-[11px] font-bold text-foreground bg-transparent border-0 focus:outline-none focus:underline p-0 leading-tight w-24"
                                placeholder="Color Name..."
                              />
                              <span className="text-[10px] font-mono text-muted-foreground leading-none">{c.hex}</span>
                            </div>
                            {!c.isDefault && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleRemoveCustomColor(c.id);
                                }}
                                className="text-muted-foreground hover:text-rose-500 p-0.5 ml-1 transition-colors"
                                title="Remove color"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        ))}

                        <button
                          type="button"
                          onClick={handleAddCustomColor}
                          className="p-2 px-3 rounded-xl border border-dashed border-primary/50 text-primary hover:bg-primary/10 transition-all flex items-center gap-1.5 text-xs font-bold shadow-sm"
                          title="Add another brand color"
                        >
                          <Plus className="w-4 h-4" />
                          <span>Add Color</span>
                        </button>
                      </div>

                      {/* Real-time Component Preview Card */}
                      <div
                        className="p-3 rounded-xl border border-border/80 flex items-center justify-between gap-3 shadow-inner transition-all"
                        style={{ backgroundColor: secondaryHex }}
                      >
                        <div className="flex items-center gap-2">
                          <div className="w-3.5 h-3.5 rounded-full" style={{ backgroundColor: primaryHex }} />
                          <span className="text-xs font-bold text-white">Live Hero Palette Preview</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="px-2.5 py-0.5 rounded text-[10px] font-semibold text-white" style={{ backgroundColor: accentHex }}>
                            Accent Tag
                          </span>
                          <button
                            type="button"
                            className="px-3 py-1 rounded-md text-xs font-bold text-white shadow-sm"
                            style={{ backgroundColor: primaryHex }}
                          >
                            CTA Button
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Logo Specification (Upload vs Link URL vs Dynamic Generator) */}
                    <div>
                      <label className="prompt-label text-xs uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1.5">
                        <ImageIcon className="w-4 h-4 text-primary" />
                        <span>Brand Logo Option</span>
                      </label>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                        <button
                          type="button"
                          onClick={() => setLogoType("upload")}
                          className={`p-3 rounded-xl border text-left flex items-center gap-2 transition-all ${
                            logoType === "upload"
                              ? "bg-primary/10 border-primary text-foreground font-semibold shadow-sm"
                              : "bg-card border-border text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          <Upload className="w-4 h-4 text-primary" />
                          <span className="text-xs">Upload File</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => setLogoType("url")}
                          className={`p-3 rounded-xl border text-left flex items-center gap-2 transition-all ${
                            logoType === "url"
                              ? "bg-primary/10 border-primary text-foreground font-semibold shadow-sm"
                              : "bg-card border-border text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          <LinkIcon className="w-4 h-4 text-secondary" />
                          <span className="text-xs">Image URL Link</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => setLogoType("ai")}
                          className={`p-3 rounded-xl border text-left flex items-center gap-2 transition-all ${
                            logoType === "ai"
                              ? "bg-primary/10 border-primary text-foreground font-semibold shadow-sm"
                              : "bg-card border-border text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          <Sparkles className="w-4 h-4 text-primary" />
                          <span className="text-xs">Dynamic Logo Generator</span>
                        </button>
                      </div>

                      {logoType === "upload" && (
                        <div className="flex flex-col gap-2">
                          <div className="relative border-2 border-dashed border-border rounded-xl p-4 text-center bg-card hover:border-primary/50 transition-colors">
                            <input
                              type="file"
                              accept="image/*"
                              onChange={handleFileUpload}
                              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                              disabled={isUploadingLogo}
                            />
                            {isUploadingLogo ? (
                              <div className="flex items-center justify-center gap-2 text-xs text-primary font-medium py-2">
                                <Loader2 className="w-4 h-4 animate-spin" />
                                <span>Uploading logo image file...</span>
                              </div>
                            ) : logoUrl ? (
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <img src={logoUrl} alt="Logo Preview" className="w-10 h-10 object-contain rounded-lg border border-border bg-slate-900/5 p-1" />
                                  <div className="text-left">
                                    <p className="text-xs font-semibold text-foreground">Logo File Uploaded</p>
                                    <p className="text-[10px] text-muted-foreground truncate max-w-[250px]">{logoUrl}</p>
                                  </div>
                                </div>
                                <span className="text-xs text-primary font-medium hover:underline">Change File</span>
                              </div>
                            ) : (
                              <div className="flex flex-col items-center gap-1.5 py-1">
                                <Upload className="w-5 h-5 text-muted-foreground" />
                                <p className="text-xs text-foreground font-medium">Click or drag & drop logo image file here</p>
                                <p className="text-[10px] text-muted-foreground">PNG, JPG, WEBP, or SVG up to 10MB</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {logoType === "url" && (
                        <div className="flex flex-col gap-2">
                          <input
                            type="url"
                            value={logoUrl}
                            onChange={(e) => setLogoUrl(e.target.value)}
                            placeholder="https://example.com/brand-logo.png"
                            className="prompt-textarea !py-2.5"
                          />
                          {logoUrl && (
                            <div className="flex items-center gap-2 p-2 bg-card rounded-lg border border-border">
                              <img src={logoUrl} alt="Logo URL Preview" className="w-8 h-8 object-contain rounded border border-border bg-slate-900/5 p-0.5" onError={(e) => { e.target.style.display = 'none'; }} />
                              <span className="text-xs text-muted-foreground truncate">{logoUrl}</span>
                            </div>
                          )}
                        </div>
                      )}

                      {logoType === "ai" && (
                        <input
                          type="text"
                          value={logoPrompt}
                          onChange={(e) => setLogoPrompt(e.target.value)}
                          placeholder="e.g. Minimalist neon geometric cyber-shield icon logo..."
                          className="prompt-textarea !py-2.5"
                        />
                      )}
                    </div>

                    {/* Contact Details Grid */}
                    <div>
                      <label className="prompt-label text-xs uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1.5">
                        <Phone className="w-4 h-4 text-secondary" />
                        <span>Contact Information (Embedded in Footer & Contact Form)</span>
                      </label>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                        <input
                          type="email"
                          value={contactEmail}
                          onChange={(e) => setContactEmail(e.target.value)}
                          placeholder="contact@business.com"
                          className="prompt-textarea !py-2 text-xs"
                        />
                        <input
                          type="tel"
                          value={contactPhone}
                          onChange={(e) => setContactPhone(e.target.value)}
                          placeholder="+1 (555) 019-2834"
                          className="prompt-textarea !py-2 text-xs"
                        />
                        <input
                          type="text"
                          value={contactAddress}
                          onChange={(e) => setContactAddress(e.target.value)}
                          placeholder="San Francisco, CA"
                          className="prompt-textarea !py-2 text-xs"
                        />
                      </div>

                      {/* Socials Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        <input
                          type="text"
                          value={socialTwitter}
                          onChange={(e) => setSocialTwitter(e.target.value)}
                          placeholder="Twitter @handle"
                          className="prompt-textarea !py-1.5 text-[11px]"
                        />
                        <input
                          type="text"
                          value={socialLinkedin}
                          onChange={(e) => setSocialLinkedin(e.target.value)}
                          placeholder="LinkedIn URL"
                          className="prompt-textarea !py-1.5 text-[11px]"
                        />
                        <input
                          type="text"
                          value={socialGithub}
                          onChange={(e) => setSocialGithub(e.target.value)}
                          placeholder="GitHub profile"
                          className="prompt-textarea !py-1.5 text-[11px]"
                        />
                        <input
                          type="text"
                          value={socialInstagram}
                          onChange={(e) => setSocialInstagram(e.target.value)}
                          placeholder="Instagram handle"
                          className="prompt-textarea !py-1.5 text-[11px]"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Prompt Textarea & Live Prompt Editor */}
                <div className="form-group">
                  <div className="flex items-center justify-between mb-2">
                    <label htmlFor="prompt" className="prompt-label mb-0 flex items-center gap-2">
                      <Edit3 className="w-4 h-4 text-primary" />
                      <span>{creatorMode === "creator" ? "Live Prompt & Architecture Spec Editor" : "Describe your dream website template"}</span>
                    </label>
                    <div className="flex items-center gap-2">
                      {creatorMode === "creator" && (
                        <button
                          type="button"
                          onClick={handleSyncToPrompt}
                          className="px-3 py-1 bg-secondary/10 hover:bg-secondary/20 text-secondary border border-secondary/30 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
                          title="Compile entered business fields into prompt editor text"
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                          <span>Sync Fields to Prompt</span>
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={handleEnhancePrompt}
                        disabled={isEnhancing}
                        className="px-3 py-1 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors disabled:opacity-50"
                        title="Refine simple prompt ideas into detailed architectural design specs"
                      >
                        {isEnhancing ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Enhancing Brief...</span>
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-3.5 h-3.5" />
                            <span>Enhance Prompt Spec</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  <textarea
                    id="prompt"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="e.g., 'A premium glassmorphic website for Apex Cybernetics, featuring dark neon-blue styling, interactive terminal blog section, showcase grid, and contact page...'"
                    className="prompt-textarea"
                    rows={5}
                  />
                  {error && <p className="error-text mt-2">{error}</p>}
                </div>

                {/* Enhanced Prompt Specs Pill Summary */}
                {enhancedSpecs && (
                  <div className="p-3 mb-6 bg-primary/5 border border-primary/20 rounded-xl text-xs text-foreground">
                    <div className="flex items-center gap-2 mb-1 text-primary font-semibold">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Design Brief Applied</span>
                    </div>
                    <p className="text-muted-foreground mb-2">{enhancedSpecs.enhanced_prompt}</p>
                    <div className="flex flex-wrap gap-2 text-[11px]">
                      {enhancedSpecs.industry && (
                        <span className="px-2 py-0.5 bg-primary/10 text-primary rounded-md border border-primary/20">
                          Industry: {enhancedSpecs.industry}
                        </span>
                      )}
                      {enhancedSpecs.color_scheme && (
                        <span className="px-2 py-0.5 bg-secondary/10 text-secondary rounded-md border border-secondary/20">
                          Theme: {enhancedSpecs.color_scheme}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* 2-BUTTON TAB SWITCHER BAR (FRAMEWORK & CSS TOOL) */}
                <div className="form-group mb-6">
                  {/* Tab Navigation Buttons */}
                  <div className="flex items-center gap-2 p-1.5 bg-muted/60 backdrop-blur-md rounded-2xl border border-border/80 mb-4 shadow-inner">
                    <button
                      type="button"
                      onClick={() => setTechTab("framework")}
                      className={`flex-1 py-2.5 px-4 rounded-xl font-bold text-xs transition-all duration-200 flex items-center justify-center gap-2 select-none ${
                        techTab === "framework"
                          ? "bg-primary text-primary-foreground shadow-md ring-1 ring-primary/40"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                      }`}
                    >
                      <Layers className="w-4 h-4" />
                      <span>Frontend Frameworks</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary-foreground/20 text-current font-mono">
                        {framework.toUpperCase()}
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setTechTab("backend")}
                      className={`flex-1 py-2.5 px-4 rounded-xl font-bold text-xs transition-all duration-200 flex items-center justify-center gap-2 select-none ${
                        techTab === "backend"
                          ? "bg-indigo-600 text-white shadow-md ring-1 ring-indigo-500/40"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                      }`}
                    >
                      <Building2 className="w-4 h-4" />
                      <span>Backend Frameworks</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/20 text-current font-mono">
                        {backendFramework.toUpperCase()}
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setTechTab("css")}
                      className={`flex-1 py-2.5 px-4 rounded-xl font-bold text-xs transition-all duration-200 flex items-center justify-center gap-2 select-none ${
                        techTab === "css"
                          ? "bg-secondary text-secondary-foreground shadow-md ring-1 ring-secondary/40"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                      }`}
                    >
                      <Palette className="w-4 h-4" />
                      <span>CSS & Designing Tools</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-secondary-foreground/20 text-current font-mono">
                        {cssEngine.toUpperCase()}
                      </span>
                    </button>
                  </div>

                  {/* TAB CONTENT 1: FRONTEND FRAMEWORKS */}
                  {techTab === "framework" && (
                    <div className="animate-in fade-in slide-in-from-bottom-2 duration-200">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5 text-primary" />
                          <span>Select Frontend Framework (8 Options)</span>
                        </span>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          Active: {framework.toUpperCase()}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                        {[
                          { id: "react", name: "React 18 & Vite", icon: Layers, badge: "React SPA", color: "from-sky-500/20 to-blue-600/20 text-sky-400 border-sky-500/30", desc: "React 18 SPA with state router & Vite bundle" },
                          { id: "nextjs", name: "Next.js 14", icon: LayoutGrid, badge: "App Router", color: "from-slate-700/30 to-slate-900/40 text-slate-200 border-slate-600/30", desc: "Next.js 14 App Router layout structure" },
                          { id: "vue", name: "Vue 3 & Vite", icon: Sparkles, badge: "Vue 3 SFC", color: "from-emerald-500/20 to-teal-600/20 text-emerald-400 border-emerald-500/30", desc: "Vue 3 SFC setup with Lucide Vue & Vite" },
                          { id: "nuxt", name: "Nuxt 3 Studio", icon: Wand2, badge: "Nuxt 3 SSR", color: "from-green-500/20 to-emerald-700/20 text-emerald-300 border-emerald-500/30", desc: "Nuxt 3 Vue SSR framework with auto-imports" },
                          { id: "svelte", name: "SvelteKit", icon: Sparkles, badge: "Svelte 4", color: "from-orange-500/20 to-red-600/20 text-orange-400 border-orange-500/30", desc: "Svelte 4 reactive component architecture" },
                          { id: "astro", name: "Astro 4 Studio", icon: Wand2, badge: "Astro 4", color: "from-purple-500/20 to-indigo-600/20 text-purple-400 border-purple-500/30", desc: "Ultra-fast static site with Astro 4 islands" },
                          { id: "angular", name: "Angular 17", icon: Layers, badge: "Angular CLI", color: "from-red-500/20 to-rose-700/20 text-rose-400 border-rose-500/30", desc: "Angular 17 enterprise component setup" },
                          { id: "html", name: "HTML5 Multi-Page", icon: Globe, badge: "Multi-Page", color: "from-amber-500/20 to-yellow-600/20 text-amber-400 border-amber-500/30", desc: "Production HTML5 multi-page site package" },
                        ].map((fw) => {
                          const IconComp = fw.icon;
                          const isSelected = framework === fw.id;
                          return (
                            <div
                              key={fw.id}
                              onClick={() => setFramework(fw.id)}
                              className={`group relative p-3 rounded-xl border text-left transition-all duration-200 cursor-pointer flex flex-col justify-between overflow-hidden select-none ${
                                isSelected
                                  ? "bg-primary/10 border-primary shadow-lg ring-2 ring-primary/40 -translate-y-0.5"
                                  : "bg-card/80 backdrop-blur-sm border-border hover:border-primary/40 hover:bg-muted/40 hover:-translate-y-0.5"
                              }`}
                            >
                              {isSelected && (
                                <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent pointer-events-none" />
                              )}

                              <div className="relative z-10">
                                <div className="flex items-center justify-between mb-2">
                                  <div className={`p-1.5 rounded-lg border bg-gradient-to-br ${fw.color} shadow-sm group-hover:scale-105 transition-transform`}>
                                    <IconComp className="w-3.5 h-3.5" />
                                  </div>

                                  <div className="flex items-center gap-1.5">
                                    {isSelected ? (
                                      <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-primary text-primary-foreground font-bold shadow-sm">
                                        <Check className="w-3 h-3" />
                                        <span>Active</span>
                                      </span>
                                    ) : (
                                      <span className="text-[10px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground font-mono font-medium border border-border/60">
                                        {fw.badge}
                                      </span>
                                    )}
                                  </div>
                                </div>

                                <h3 className="font-bold text-xs text-foreground mb-0.5 group-hover:text-primary transition-colors">
                                  {fw.name}
                                </h3>
                                <p className="text-[10px] text-muted-foreground leading-snug">
                                  {fw.desc}
                                </p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* TAB CONTENT 2: BACKEND FRAMEWORKS */}
                  {techTab === "backend" && (
                    <div className="animate-in fade-in slide-in-from-bottom-2 duration-200">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                          <Building2 className="w-3.5 h-3.5 text-indigo-400" />
                          <span>Select Dedicated Backend API Framework (8 Options)</span>
                        </span>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          Active: {backendFramework.toUpperCase()}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                        {[
                          { id: "fastapi", name: "FastAPI (Python 3.12)", icon: Building2, badge: "Async Python", color: "from-emerald-500/20 to-teal-600/20 text-emerald-400 border-emerald-500/30", desc: "Ultra-fast async Python API with Pydantic & OpenAPI docs" },
                          { id: "express", name: "Express.js (Node.js)", icon: Layers, badge: "Node.js", color: "from-amber-500/20 to-yellow-600/20 text-amber-400 border-amber-500/30", desc: "Lightweight, unopinionated Node.js REST API server" },
                          { id: "nestjs", name: "NestJS (TypeScript)", icon: Sparkles, badge: "TypeScript", color: "from-rose-500/20 to-pink-600/20 text-rose-400 border-rose-500/30", desc: "Progressive enterprise TypeScript microservices framework" },
                          { id: "django", name: "Django (Python 5)", icon: Wand2, badge: "Django ORM", color: "from-green-600/20 to-emerald-800/20 text-green-300 border-green-500/30", desc: "High-level Python web framework with built-in ORM & admin" },
                          { id: "springboot", name: "Spring Boot 3 (Java)", icon: LayoutGrid, badge: "Java 21", color: "from-sky-500/20 to-blue-600/20 text-sky-400 border-sky-500/30", desc: "Production-grade Java 21 REST API server & JPA data layer" },
                          { id: "rails", name: "Ruby on Rails 7", icon: Layers, badge: "Ruby MVC", color: "from-red-500/20 to-rose-700/20 text-rose-300 border-rose-500/30", desc: "Full-stack Ruby MVC engine with ActiveRecord SQLite" },
                          { id: "laravel", name: "Laravel 11 (PHP 8.3)", icon: Wand2, badge: "PHP Eloquent", color: "from-red-600/20 to-orange-600/20 text-orange-400 border-orange-500/30", desc: "Elegant PHP 8.3 web framework with Eloquent ORM" },
                          { id: "actix", name: "Actix Web (Rust)", icon: Globe, badge: "Rust Async", color: "from-orange-500/20 to-amber-700/20 text-orange-300 border-orange-500/30", desc: "Blazing-fast, memory-safe Rust HTTP REST server" },
                        ].map((be) => {
                          const IconComp = be.icon;
                          const isSelected = backendFramework === be.id;
                          return (
                            <div
                              key={be.id}
                              onClick={() => setBackendFramework(be.id)}
                              className={`group relative p-3 rounded-xl border text-left transition-all duration-200 cursor-pointer flex flex-col justify-between overflow-hidden select-none ${
                                isSelected
                                  ? "bg-indigo-500/10 border-indigo-500 shadow-lg ring-2 ring-indigo-500/40 -translate-y-0.5"
                                  : "bg-card/80 backdrop-blur-sm border-border hover:border-indigo-500/40 hover:bg-muted/40 hover:-translate-y-0.5"
                              }`}
                            >
                              {isSelected && (
                                <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 via-transparent to-transparent pointer-events-none" />
                              )}

                              <div className="relative z-10">
                                <div className="flex items-center justify-between mb-2">
                                  <div className={`p-1.5 rounded-lg border bg-gradient-to-br ${be.color} shadow-sm group-hover:scale-105 transition-transform`}>
                                    <IconComp className="w-3.5 h-3.5" />
                                  </div>

                                  <div className="flex items-center gap-1.5">
                                    {isSelected ? (
                                      <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-indigo-600 text-white font-bold shadow-sm">
                                        <Check className="w-3 h-3" />
                                        <span>Active</span>
                                      </span>
                                    ) : (
                                      <span className="text-[10px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground font-mono font-medium border border-border/60">
                                        {be.badge}
                                      </span>
                                    )}
                                  </div>
                                </div>

                                <h3 className="font-bold text-xs text-foreground mb-0.5 group-hover:text-indigo-400 transition-colors">
                                  {be.name}
                                </h3>
                                <p className="text-[10px] text-muted-foreground leading-snug">
                                  {be.desc}
                                </p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* TAB CONTENT 3: CSS & STYLING TOOLS */}
                  {techTab === "css" && (
                    <div className="animate-in fade-in slide-in-from-bottom-2 duration-200">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                          <Palette className="w-3.5 h-3.5 text-secondary" />
                          <span>Select CSS & Styling Engine (8 Options)</span>
                        </span>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          Active: {cssEngine.toUpperCase()}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                        {[
                          { id: "tailwind", name: "Tailwind CSS Studio", icon: Palette, badge: "Tailwind JIT", color: "from-cyan-500/20 to-blue-500/20 text-cyan-400 border-cyan-500/30", desc: "Utility-first CSS engine with custom theme config & JIT compiler" },
                          { id: "vanillacss", name: "Vanilla CSS & Modules", icon: Wand2, badge: "Pure CSS3", color: "from-pink-500/20 to-rose-600/20 text-pink-400 border-pink-500/30", desc: "Pure CSS3 custom properties (:root) & keyframe animations" },
                          { id: "styledcomponents", name: "Styled Components", icon: Sparkles, badge: "CSS-in-JS", color: "from-violet-500/20 to-purple-600/20 text-violet-400 border-violet-500/30", desc: "Component-scoped CSS-in-JS styling with theme providers" },
                          { id: "bootstrap", name: "Bootstrap 5 Studio", icon: LayoutGrid, badge: "Bootstrap 5", color: "from-indigo-500/20 to-purple-700/20 text-indigo-300 border-indigo-500/30", desc: "Responsive flexbox grid system & pre-built UI utility suite" },
                          { id: "sass", name: "Sass / SCSS Studio", icon: Layers, badge: "Sass SCSS", color: "from-rose-500/20 to-pink-700/20 text-rose-300 border-rose-500/30", desc: "Nesting, mixins, math functions & modular SCSS architecture" },
                          { id: "chakra", name: "Chakra UI / Emotion", icon: Sparkles, badge: "Chakra UI", color: "from-teal-500/20 to-emerald-600/20 text-teal-300 border-teal-500/30", desc: "Accessible component-first styling with design token primitives" },
                          { id: "cssgrid", name: "CSS Grid Studio", icon: LayoutGrid, badge: "CSS Grid", color: "from-blue-500/20 to-indigo-600/20 text-blue-300 border-blue-500/30", desc: "Advanced 2D layout grid system with CSS custom properties" },
                          { id: "glassmorphism", name: "Glassmorphic CSS", icon: Palette, badge: "Glassmorphism", color: "from-sky-500/20 to-cyan-600/20 text-sky-300 border-sky-500/30", desc: "Translucent frosted-glass aesthetic & backdrop blur filters" },
                        ].map((styleEngine) => {
                          const IconComp = styleEngine.icon;
                          const isSelected = cssEngine === styleEngine.id;
                          return (
                            <div
                              key={styleEngine.id}
                              onClick={() => setCssEngine(styleEngine.id)}
                              className={`group relative p-3 rounded-xl border text-left transition-all duration-200 cursor-pointer flex flex-col justify-between overflow-hidden select-none ${
                                isSelected
                                  ? "bg-secondary/10 border-secondary shadow-lg ring-2 ring-secondary/40 -translate-y-0.5"
                                  : "bg-card/80 backdrop-blur-sm border-border hover:border-secondary/40 hover:bg-muted/40 hover:-translate-y-0.5"
                              }`}
                            >
                              {isSelected && (
                                <div className="absolute inset-0 bg-gradient-to-br from-secondary/10 via-transparent to-transparent pointer-events-none" />
                              )}

                              <div className="relative z-10">
                                <div className="flex items-center justify-between mb-2">
                                  <div className={`p-1.5 rounded-lg border bg-gradient-to-br ${styleEngine.color} shadow-sm group-hover:scale-105 transition-transform`}>
                                    <IconComp className="w-3.5 h-3.5" />
                                  </div>

                                  <div className="flex items-center gap-1.5">
                                    {isSelected ? (
                                      <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground font-bold shadow-sm">
                                        <Check className="w-3 h-3" />
                                        <span>Active</span>
                                      </span>
                                    ) : (
                                      <span className="text-[10px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground font-mono font-medium border border-border/60">
                                        {styleEngine.badge}
                                      </span>
                                    )}
                                  </div>
                                </div>

                                <h3 className="font-bold text-xs text-foreground mb-0.5 group-hover:text-secondary transition-colors">
                                  {styleEngine.name}
                                </h3>
                                <p className="text-[10px] text-muted-foreground leading-snug">
                                  {styleEngine.desc}
                                </p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* BUYER PROJECT ARCHITECTURE SCOPE (FRONTEND vs FULL-STACK BUNDLE) */}
                <div className="form-group mb-6">
                  <div className="flex items-center justify-between mb-2">
                    <label className="prompt-label m-0 text-sm font-bold text-foreground flex items-center gap-2">
                      <Zap className="w-4 h-4 text-primary" />
                      <span>Template Architecture & Backend Bundle</span>
                    </label>
                    <span className="text-[11px] text-muted-foreground font-mono bg-muted/60 px-2 py-0.5 rounded-md border border-border">
                      Buyer Option
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div
                      onClick={() => setProjectScope("fullstack")}
                      className={`group relative p-4 rounded-xl border text-left transition-all duration-200 cursor-pointer flex flex-col justify-between overflow-hidden select-none ${
                        projectScope === "fullstack"
                          ? "bg-primary/10 border-primary shadow-lg ring-2 ring-primary/40 -translate-y-0.5"
                          : "bg-card/80 backdrop-blur-sm border-border hover:border-primary/40 hover:bg-muted/40 hover:-translate-y-0.5"
                      }`}
                    >
                      {projectScope === "fullstack" && (
                        <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent pointer-events-none" />
                      )}

                      <div className="relative z-10">
                        <div className="flex items-center justify-between mb-2">
                          <div className="p-2 rounded-lg border bg-gradient-to-br from-indigo-500/20 to-purple-600/20 text-indigo-400 border-indigo-500/30 shadow-sm group-hover:scale-105 transition-transform">
                            <Zap className="w-4 h-4" />
                          </div>
                          {projectScope === "fullstack" ? (
                            <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-primary text-primary-foreground font-bold shadow-sm">
                              <Check className="w-3 h-3" />
                              <span>Selected</span>
                            </span>
                          ) : (
                            <span className="text-[10px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground font-mono font-medium border border-border/60">
                              RECOMMENDED
                            </span>
                          )}
                        </div>

                        <h3 className="font-bold text-xs text-foreground mb-1 group-hover:text-primary transition-colors">
                          🚀 Full-Stack App (Frontend + Dedicated API + Isolated DB)
                        </h3>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">
                          Includes standalone Frontend app + dedicated backend API server (`backend/main.py`) + isolated local database (`app.db`).
                        </p>
                      </div>
                    </div>

                    <div
                      onClick={() => setProjectScope("frontend")}
                      className={`group relative p-4 rounded-xl border text-left transition-all duration-200 cursor-pointer flex flex-col justify-between overflow-hidden select-none ${
                        projectScope === "frontend"
                          ? "bg-secondary/10 border-secondary shadow-lg ring-2 ring-secondary/40 -translate-y-0.5"
                          : "bg-card/80 backdrop-blur-sm border-border hover:border-secondary/40 hover:bg-muted/40 hover:-translate-y-0.5"
                      }`}
                    >
                      {projectScope === "frontend" && (
                        <div className="absolute inset-0 bg-gradient-to-br from-secondary/10 via-transparent to-transparent pointer-events-none" />
                      )}

                      <div className="relative z-10">
                        <div className="flex items-center justify-between mb-2">
                          <div className="p-2 rounded-lg border bg-gradient-to-br from-sky-500/20 to-blue-600/20 text-sky-400 border-sky-500/30 shadow-sm group-hover:scale-105 transition-transform">
                            <Layers className="w-4 h-4" />
                          </div>
                          {projectScope === "frontend" ? (
                            <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground font-bold shadow-sm">
                              <Check className="w-3 h-3" />
                              <span>Selected</span>
                            </span>
                          ) : (
                            <span className="text-[10px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground font-mono font-medium border border-border/60">
                              UI ONLY
                            </span>
                          )}
                        </div>

                        <h3 className="font-bold text-xs text-foreground mb-1 group-hover:text-secondary transition-colors">
                          🎨 Frontend UI Only (Standalone Component Package)
                        </h3>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">
                          Clean UI website codebase package (`package.json`, responsive components, styling engine, and Vite configuration).
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <button type="submit" disabled={isPreparing} className="submit-btn group">
                  {isPreparing ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin mr-2" />
                      <span>Analyzing Prompt & Scope...</span>
                    </>
                  ) : (
                    <>
                      <span>Next: Analyze Prompt & Customize Architecture</span>
                      <ArrowRight className="submit-btn-icon group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </button>
              </form>
            )}

            {!isGenerating && !generatedTemplate && step === "questions" && (
              /* Custom Questions Form */
              <div className="prompt-form glass-panel animate-fade-in">

                {/* Prompt Analysis & Rationale Banner */}
                <div className="ai-analysis-banner">
                  <div className="ai-analysis-header">
                    <div className="ai-badge">
                      <Sparkles className="w-4 h-4 text-primary" />
                      <span>Prompt & Architecture Analysis</span>
                    </div>
                    <span className="arch-recommendation-tag">
                      Recommended: {architectureType === "single_page" ? "Single Page (SPA)" : "Multi-Page Site"}
                    </span>
                  </div>

                  {architectureReasoning && (
                    <p className="ai-reasoning-text">
                      <Info className="w-4 h-4 text-secondary shrink-0 inline-block mr-1.5 -mt-0.5" />
                      {architectureReasoning}
                    </p>
                  )}

                  {/* Architecture Mode Selector */}
                  <div className="arch-toggle-container">
                    <label className="arch-toggle-label">Select Page Architecture:</label>
                    <div className="arch-toggle-buttons">
                      <button
                        type="button"
                        onClick={() => handleToggleArchitecture("single_page")}
                        className={`arch-toggle-btn ${architectureType === "single_page" ? "active" : ""}`}
                      >
                        <FileText className="w-4 h-4 mr-1.5" />
                        <span>Single Page</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleToggleArchitecture("multi_page")}
                        className={`arch-toggle-btn ${architectureType === "multi_page" ? "active" : ""}`}
                      >
                        <Layers className="w-4 h-4 mr-1.5" />
                        <span>Multi-Page ({pages.length > 1 ? pages.length : multiPageCache.length} Pages)</span>
                      </button>
                    </div>
                  </div>
                </div>

                {error && <p className="error-text mb-4">{error}</p>}

                {/* Questions */}
                {questions.length > 0 && (
                  <div className="questions-container mt-6">
                    <h3 className="section-subtitle">Styling & Design Preferences</h3>
                    {questions.map((q) => (
                      <div key={q.id} className="question-group">
                        <label className="prompt-label">{q.question}</label>
                        <div className="options-grid">
                          {q.options.map((opt) => (
                            <button
                              key={opt}
                              type="button"
                              onClick={() => setAnswers(prev => ({ ...prev, [q.id]: opt }))}
                              className={`option-button ${answers[q.id] === opt ? "active" : ""}`}
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Pages checklist & Content Summary */}
                <div className="form-group mb-6 mt-6">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="section-subtitle font-semibold">Planned Page & Content Breakdown</h3>
                    <span className="text-xs text-muted-foreground">{pages.length} page(s) configured</span>
                  </div>

                  <div className="pages-list-container">
                    {pages.map((p, idx) => (
                      <div key={p.filename} className="page-item-card">
                        <div className="page-item-top">
                          <label className="page-item-label">
                            <input
                              type="checkbox"
                              checked={p.selected !== false}
                              disabled={p.filename === "index.html" || architectureType === "single_page"}
                              onChange={(e) => {
                                const updated = [...pages];
                                updated[idx] = { ...updated[idx], selected: e.target.checked };
                                setPages(updated);
                              }}
                              className="page-item-checkbox"
                            />
                            <span className="font-semibold text-foreground">{p.name}</span>
                          </label>

                          <div className="flex items-center space-x-2">
                            <span className="page-item-filename">{p.filename}</span>
                            {p.filename !== "index.html" && architectureType === "multi_page" && (
                              <button
                                type="button"
                                onClick={() => handleRemovePage(p.filename)}
                                className="remove-page-btn"
                                title="Remove Page"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </div>

                        {p.content_summary && (
                          <div className="page-summary-box">
                            <LayoutGrid className="w-3.5 h-3.5 text-secondary shrink-0 mt-0.5" />
                            <p className="text-xs text-muted-foreground">{p.content_summary}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Custom Page Adder for Multi-Page mode */}
                  {architectureType === "multi_page" && (
                    <div className="add-page-row mt-3">
                      <input
                        type="text"
                        value={newPageName}
                        onChange={(e) => setNewPageName(e.target.value)}
                        placeholder="Add another page (e.g. 'Pricing', 'Blog', 'Portfolio')..."
                        className="add-page-input"
                      />
                      <button
                        type="button"
                        onClick={handleAddCustomPage}
                        disabled={!newPageName.trim()}
                        className="add-page-btn"
                      >
                        <Plus className="w-4 h-4 mr-1" />
                        <span>Add Page</span>
                      </button>
                    </div>
                  )}
                </div>

                {/* Navigation Buttons */}
                <div className="flex space-x-3 mt-8">
                  <button
                    type="button"
                    onClick={() => setStep("prompt")}
                    className="flex-1 px-4 py-3 bg-muted hover:bg-muted/80 border border-border rounded-xl font-medium text-foreground transition-colors"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={handleGenerate}
                    className="flex-1 submit-btn group"
                  >
                    <span>Generate Template ({pages.filter(p => p.selected !== false).length} Pages)</span>
                    <Sparkles className="submit-btn-icon group-hover:rotate-12 transition-transform" />
                  </button>
                </div>
              </div>
            )}

            {isGenerating && !isGenerationComplete && (
              /* Autonomous Multi-Agent Progress Step Indicator */
              <div className="generation-loading-panel glass-panel">
                <div className="loading-title-row flex items-center justify-between gap-4 border-b border-border/30 pb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                      <Sparkles className="w-5 h-5 animate-pulse" />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-foreground">Autonomous Multi-Agent Synthesis</h2>
                      <p className="text-xs text-muted-foreground">
                        Coordinated 8-Agent pipeline is engineering, auditing, and packaging your full-stack project in real time.
                      </p>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <span className="text-xs font-mono font-bold text-cyan-400">
                      {Math.min(100, Math.round((completedSteps.length / GENERATION_STEPS.length) * 100))}% Completed
                    </span>
                  </div>
                </div>

                {/* Overall Top Progress Bar */}
                <div className="w-full bg-muted/40 rounded-full h-2 overflow-hidden my-4 border border-border/20">
                  <div
                    className="bg-gradient-to-r from-cyan-500 via-primary to-emerald-500 h-full transition-all duration-500 rounded-full"
                    style={{
                      width: `${Math.min(100, Math.max(8, Math.round((completedSteps.length / GENERATION_STEPS.length) * 100)))}%`
                    }}
                  />
                </div>

                {/* 8 Agent Live Execution Cards */}
                <div className="steps-list">
                  {GENERATION_STEPS.map((step, idx) => {
                    const isCompleted = completedSteps.includes(step.id);
                    const isActive = currentStep === idx && !isCompleted;
                    const isPending = !isCompleted && !isActive;

                    return (
                      <div
                        key={step.id}
                        className={`agent-pipeline-card ${
                          isCompleted ? "agent-completed" : isActive ? "agent-active" : "agent-pending"
                        }`}
                      >
                        <div className="agent-status-icon-wrapper">
                          {isCompleted ? (
                            <div className="agent-icon-completed">
                              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                            </div>
                          ) : isActive ? (
                            <div className="agent-icon-active">
                              <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
                            </div>
                          ) : (
                            <div className="agent-icon-pending">
                              <span className="text-xs text-muted-foreground font-mono font-bold">{idx + 1}</span>
                            </div>
                          )}
                        </div>

                        <div className="agent-content-area">
                          <div className="agent-title-row">
                            <div className="flex items-center gap-2">
                              <span className="text-base">{step.icon}</span>
                              <span className="agent-name">
                                {step.agent}
                              </span>
                            </div>
                            {isCompleted && (
                              <span className="agent-badge completed">
                                <Check className="w-3 h-3" /> Completed (200 OK)
                              </span>
                            )}
                            {isActive && (
                              <span className="agent-badge active">
                                <Sparkles className="w-3 h-3 animate-spin" /> Active Running...
                              </span>
                            )}
                            {isPending && (
                              <span className="agent-badge pending">
                                Queued
                              </span>
                            )}
                          </div>

                          <p className="agent-headline text-xs mt-1">
                            {step.title}
                          </p>

                          <p className="agent-detail-text text-[11px] mt-0.5">
                            {isCompleted ? step.detail : isActive ? "Executing live AI synthesis stage..." : "Waiting for preceding agent..."}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {isGenerationComplete && (
              /* Success template preview card */
              <div className="success-panel glass-panel">
                <div className="success-header">
                  <CheckCircle2 className="success-icon text-emerald-500 animate-bounce" />
                  <h2>Project Successfully Created!</h2>
                  <p>Your custom website project has been generated and saved in your Dashboard under Studio Projects. You can preview and edit it in the live canvas editor, or add it to cart to unlock full source code download and deployment.</p>
                </div>

                <div
                  className="generated-preview-card cursor-pointer hover:border-primary/50 transition-all group"
                  onClick={() => navigate(`/preview?template=${generatedTemplate.slug || generatedTemplate.id}`)}
                  title="Click to launch live template viewer & canvas editor"
                >
                  <div className="card-media">
                    <img
                      src={generatedTemplate.thumbnail_url}
                      alt={generatedTemplate.title}
                      className="card-image group-hover:scale-105 transition-transform duration-300"
                    />
                    <div className="card-badge">Studio Project</div>
                  </div>
                  <div className="card-info">
                    <div className="card-meta">
                      <span className="category-tag">{generatedTemplate.industry}</span>
                      <span className="price-tag">${generatedTemplate.price || 49}</span>
                    </div>
                    <h3 className="card-title flex items-center justify-between">
                      <span>{generatedTemplate.title}</span>
                      <Eye className="w-4 h-4 text-primary opacity-0 group-hover:opacity-100 transition-opacity" />
                    </h3>
                    <p className="card-desc">{generatedTemplate.short_description}</p>
                    <div className="card-tags">
                      {generatedTemplate.tags?.slice(0, 3).map((tag) => (
                        <span key={tag} className="meta-tag">#{tag}</span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="success-actions flex flex-wrap items-center justify-center gap-3 mt-6">
                  <button
                    type="button"
                    onClick={() => {
                      addToCart({
                        templateId: generatedTemplate.id,
                        title: generatedTemplate.title,
                        price: generatedTemplate.price || 49,
                        thumbnail: generatedTemplate.thumbnail_url,
                        licenseType: "regular",
                      });
                    }}
                    className={`px-5 py-3 font-bold rounded-xl flex items-center gap-2 transition-all cursor-pointer shadow-md ${
                      isInCart
                        ? "bg-emerald-500/20 text-emerald-500 border border-emerald-500/40"
                        : "bg-primary text-primary-foreground hover:opacity-90 shadow-primary/20"
                    }`}
                  >
                    <ShoppingCart className="w-4 h-4" />
                    <span>{isInCart ? "In Cart (Proceed to Checkout)" : "Add to Cart ($" + (generatedTemplate.price || 49) + ")"}</span>
                  </button>

                  <Link
                    to="/dashboard?tab=studio-projects"
                    className="secondary-action-btn border border-border bg-card text-foreground hover:bg-muted font-semibold py-3 px-4 rounded-xl flex items-center gap-2"
                  >
                    <Folder className="w-4 h-4 text-muted-foreground" />
                    <span>View in Studio Projects</span>
                  </Link>

                  <Link
                    to={`/preview?template=${generatedTemplate.slug || generatedTemplate.id}`}
                    className="secondary-action-btn border border-border bg-card text-foreground hover:bg-muted font-semibold py-3 px-4 rounded-xl flex items-center gap-2"
                  >
                    <Eye className="w-4 h-4" />
                    <span>Open Live Canvas Editor</span>
                    <ArrowRight className="w-4 h-4" />
                  </Link>

                  <button
                    type="button"
                    onClick={() => {
                      setIsGenerating(false);
                      setGeneratedTemplate(null);
                      setPrompt("");
                      setStep("prompt");
                    }}
                    className="secondary-action-btn border border-border bg-card text-foreground hover:bg-muted font-medium py-3 px-4 rounded-xl flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4 text-muted-foreground" />
                    <span>Generate Another</span>
                  </button>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  );
}
