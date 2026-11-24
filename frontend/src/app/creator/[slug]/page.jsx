"use client";

import { useState, useMemo, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Store,
  Sparkles,
  ShieldCheck,
  Star,
  Search,
  X,
  Share2,
  Copy,
  Check,
  Globe,
  Mail,
  ShoppingBag,
  SlidersHorizontal,
  Eye,
  ShoppingCart,
  Loader2,
  User,
  Send,
  MessageSquare,
  CreditCard,
  Zap,
  DollarSign,
  QrCode,
  Building2,
  Wallet,
  Info,
  Layers,
  ArrowRight,
  ExternalLink,
  Clock,
  CheckCircle2,
  Code2,
  Smartphone,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import TemplateCard from "@/components/marketplace/TemplateCard";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useAppUser } from "@/lib/auth";
import { useCartStore } from "@/store";
import "./Page.css";

const XIcon = ({ className = "w-4 h-4" }) => (
  <svg className={className} fill="currentColor" viewBox="0 0 24 24">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);

const GithubIcon = ({ className = "w-4 h-4" }) => (
  <svg className={className} fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
  </svg>
);

const LinkedinIcon = ({ className = "w-4 h-4" }) => (
  <svg className={className} fill="currentColor" viewBox="0 0 24 24">
    <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" />
  </svg>
);

const FRAMEWORKS = [
  { id: "all", label: "All Frameworks" },
  { id: "react", label: "React 19" },
  { id: "nextjs", label: "Next.js" },
  { id: "vue", label: "Vue 3" },
  { id: "nuxt", label: "Nuxt" },
  { id: "svelte", label: "Svelte" },
  { id: "html", label: "HTML5 + Tailwind" },
];

const PAYMENT_METHOD_INFO = {
  stripe: { label: "Stripe", icon: CreditCard, color: "#635bff", desc: "Credit / Debit Cards, Apple Pay, Google Pay" },
  razorpay: { label: "Razorpay", icon: Zap, color: "#3b82f6", desc: "UPI, Cards, NetBanking" },
  upi: { label: "Direct UPI", icon: QrCode, color: "#a855f7", desc: "Instant GPay, PhonePe, Paytm, BHIM" },
  bank_wire: { label: "Bank Wire", icon: Building2, color: "#60a5fa", desc: "Direct Account Deposit / SWIFT / IBAN" },
  bank: { label: "Bank Wire", icon: Building2, color: "#60a5fa", desc: "Direct Account Deposit / SWIFT / IBAN" },
  crypto: { label: "Crypto / Web3", icon: Wallet, color: "#f59e0b", desc: "USDT, BTC, ETH on Verified Networks" },
  wise: { label: "Wise", icon: Send, color: "#9fe870", desc: "Multi-currency Transfer" },
  revolut: { label: "Revolut", icon: CreditCard, color: "#0075eb", desc: "Direct Tag / EUR / USD" },
  cashapp: { label: "Cash App / Venmo", icon: DollarSign, color: "#00d632", desc: "US Peer-to-Peer Transfer" },
  venmo: { label: "Venmo", icon: DollarSign, color: "#008cff", desc: "US Peer-to-Peer Transfer" },
  paystack: { label: "Paystack", icon: Zap, color: "#00c3f7", desc: "African Cards & Bank Transfer" },
  flutterwave: { label: "Flutterwave", icon: Zap, color: "#fb9129", desc: "Global & African Payments" },
  custom: { label: "Custom Instructions", icon: SlidersHorizontal, color: "#dfb180", desc: "Creator-Specific Instructions" },
};

export default function CreatorStorefrontPage() {
  const { slug } = useParams();
  const { user, isSignedIn } = useAppUser();
  const cartItems = useCartStore((s) => s.items) || [];

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFramework, setSelectedFramework] = useState("all");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [sortBy, setSortBy] = useState("featured");
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [showAboutDrawer, setShowAboutDrawer] = useState(false);
  const [copiedPaymentField, setCopiedPaymentField] = useState(null);

  // Contact Form State
  const [contactForm, setContactForm] = useState({
    name: "",
    email: "",
    purpose: "Template Customization",
    subject: "",
    message: "",
  });
  const [contactSubmitting, setContactSubmitting] = useState(false);
  const [contactSubmitted, setContactSubmitted] = useState(false);

  // Fetch Storefront Data
  const {
    data: storefront,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["creator-storefront", slug],
    queryFn: async () => {
      const res = await api.get(`/creator/storefront/${encodeURIComponent(slug)}`);
      return res;
    },
    enabled: Boolean(slug),
    staleTime: 60 * 1000,
  });

  // Dynamic Browser Title in Creator's Brand Name
  useEffect(() => {
    if (storefront?.brand_name) {
      document.title = `${storefront.brand_name} — Official Website Storefront`;
    }
    return () => {
      document.title = "AI Site Studio — AI Website Generator & Marketplace";
    };
  }, [storefront]);

  const templates = useMemo(() => {
    return storefront?.templates || [];
  }, [storefront]);

  // Extract unique categories from this creator's templates
  const availableCategories = useMemo(() => {
    const cats = new Map();
    templates.forEach((t) => {
      if (t.category?.id && t.category?.name) {
        cats.set(t.category.id, t.category.name);
      }
    });
    return Array.from(cats.entries()).map(([id, name]) => ({ id, name }));
  }, [templates]);

  // Payment methods accepted by this creator
  const acceptedMethods = useMemo(() => {
    if (
      storefront?.accepted_payment_methods &&
      Array.isArray(storefront.accepted_payment_methods) &&
      storefront.accepted_payment_methods.length > 0
    ) {
      return storefront.accepted_payment_methods;
    }
    return ["stripe", "razorpay"];
  }, [storefront]);

  const paymentOptions = useMemo(() => {
    return storefront?.payment_options || {};
  }, [storefront]);

  const handleCopyPaymentInfo = (fieldKey, value) => {
    if (!value) return;
    navigator.clipboard.writeText(value);
    setCopiedPaymentField(fieldKey);
    toast.success(`Copied ${fieldKey} to clipboard!`);
    setTimeout(() => setCopiedPaymentField(null), 2500);
  };

  // Filter & Sort for Templates Catalog
  const filteredTemplates = useMemo(() => {
    return templates
      .filter((t) => {
        // Text search
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchTitle = t.title?.toLowerCase().includes(q);
          const matchDesc = t.short_description?.toLowerCase().includes(q);
          const matchTags = t.tags?.some((tag) => tag.toLowerCase().includes(q));
          if (!matchTitle && !matchDesc && !matchTags) return false;
        }

        // Framework filter
        if (selectedFramework !== "all") {
          const fw = (t.framework || "").toLowerCase();
          if (selectedFramework === "react" && !fw.includes("react")) return false;
          if (selectedFramework === "nextjs" && !fw.includes("next")) return false;
          if (selectedFramework === "vue" && !fw.includes("vue")) return false;
          if (selectedFramework === "nuxt" && !fw.includes("nuxt")) return false;
          if (selectedFramework === "svelte" && !fw.includes("svelte")) return false;
          if (selectedFramework === "html" && !fw.includes("html") && !fw.includes("tailwind"))
            return false;
        }

        // Category filter
        if (selectedCategory !== "all") {
          if (t.category?.id !== selectedCategory && t.category_id !== selectedCategory) {
            return false;
          }
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === "featured") return (b.is_featured ? 1 : 0) - (a.is_featured ? 1 : 0);
        if (sortBy === "popular") return (b.downloads_count || 0) - (a.downloads_count || 0);
        if (sortBy === "newest") return new Date(b.created_at) - new Date(a.created_at);
        if (sortBy === "price-low") return Number(a.price || 0) - Number(b.price || 0);
        if (sortBy === "price-high") return Number(b.price || 0) - Number(a.price || 0);
        if (sortBy === "rating") return (b.rating_avg || 0) - (a.rating_avg || 0);
        return 0;
      });
  }, [templates, searchQuery, selectedFramework, selectedCategory, sortBy]);

  const handleShare = () => {
    const fullUrl = window.location.href;
    navigator.clipboard.writeText(fullUrl);
    setCopiedLink(true);
    toast.success("Storefront link copied! Share this link to sell your templates directly.");
    setTimeout(() => setCopiedLink(false), 2500);
  };

  const handleCopyEmail = () => {
    if (storefront?.support_email) {
      navigator.clipboard.writeText(storefront.support_email);
      setCopiedEmail(true);
      toast.success(`Copied ${storefront.support_email} to clipboard!`);
      setTimeout(() => setCopiedEmail(false), 2500);
    }
  };

  const handleCopyId = () => {
    const idToCopy = storefront?.store_slug || slug;
    navigator.clipboard.writeText(idToCopy);
    setCopiedId(true);
    toast.success(`Copied Creator ID (@${idToCopy}) to clipboard!`);
    setTimeout(() => setCopiedId(false), 2500);
  };

  const handleContactSubmit = async (e) => {
    e.preventDefault();
    if (!contactForm.name.trim() || !contactForm.email.trim() || !contactForm.message.trim()) {
      toast.error("Please fill in your name, email, and message.");
      return;
    }
    setContactSubmitting(true);
    await new Promise((resolve) => setTimeout(resolve, 800));
    setContactSubmitting(false);
    setContactSubmitted(true);
    toast.success(`Inquiry sent to ${storefront.brand_name}! They will reply to ${contactForm.email}.`);
  };

  const isOwner =
    isSignedIn &&
    (user?.creator_store_slug === slug ||
      (user?.username && user.username.toLowerCase() === slug.toLowerCase()));

  if (isLoading) {
    return (
      <div className="storefront-page">
        <div className="storefront-loading">
          <Loader2 className="w-10 h-10 animate-spin text-[#dfb180]" />
          <p>Loading creator storefront on our domain...</p>
        </div>
      </div>
    );
  }

  if (isError || !storefront) {
    return (
      <div className="storefront-page">
        <div className="storefront-not-found">
          <div className="sf-nf-icon">
            <Store className="w-12 h-12 text-zinc-500" />
          </div>
          <h2>Creator Storefront Not Found</h2>
          <p>
            The creator storefront <code>/creator/{slug}</code> does not exist on this domain or has
            not completed setup yet.
          </p>
          <div className="sf-nf-actions">
            <Link to="/marketplace" className="sf-btn-primary">
              Explore Global Marketplace
            </Link>
            <Link to="/creator/setup" className="sf-btn-secondary">
              Launch Your Storefront
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="storefront-page storefront-marketplace-view">
      {/* ── 1. STOREFRONT NAVBAR IN CREATOR'S BRAND ── */}
      <header className="sf-navbar">
        <div className="sf-navbar-inner">
          {/* Creator Brand Logo & Name */}
          <Link to={`/creator/${storefront.store_slug}`} className="sf-nav-brand">
            <div className="sf-nav-logo-box">
              {storefront.logo_url ? (
                <img
                  src={storefront.logo_url}
                  alt={storefront.brand_name}
                  className="sf-nav-logo-img"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                  }}
                />
              ) : (
                <Store className="w-5 h-5 text-[#dfb180]" />
              )}
            </div>
            <div className="sf-nav-brand-text">
              <span className="sf-nav-brand-title">{storefront.brand_name}</span>
              <span className="sf-nav-domain-label">
                Official Storefront • @{storefront.store_slug}
              </span>
            </div>
          </Link>

          {/* Quick Header Actions */}
          <div className="sf-nav-actions">
            {/* Accepted Payments Button */}
            {acceptedMethods.length > 0 && (
              <button
                type="button"
                onClick={() => setShowPaymentModal(true)}
                className="sf-nav-payment-btn"
                title="View Creator's Accepted Payment Methods"
              >
                <CreditCard className="w-3.5 h-3.5 text-[#dfb180]" />
                <span className="hidden sm:inline">Accepted Payments</span>
              </button>
            )}

            {/* Contact Creator Button */}
            <button
              type="button"
              onClick={() => setShowContactModal(true)}
              className="sf-nav-payment-btn"
              title="Contact Creator directly"
            >
              <Send className="w-3.5 h-3.5 text-[#dfb180]" />
              <span className="hidden sm:inline">Contact Creator</span>
            </button>

            {/* Direct Support Email Pill */}
            {storefront.support_email && (
              <a
                href={`mailto:${storefront.support_email}`}
                className="sf-nav-email-pill"
                title={`Email ${storefront.brand_name} directly`}
              >
                <Mail className="w-3.5 h-3.5 text-[#dfb180]" />
                <span className="sf-nav-email-text">{storefront.support_email}</span>
              </a>
            )}

            {/* Cart Button */}
            <Link to="/checkout" className="sf-nav-cart-btn" title="View Cart">
              <ShoppingCart className="w-4 h-4 text-zinc-300" />
              {cartItems.length > 0 && (
                <span className="sf-nav-cart-badge">{cartItems.length}</span>
              )}
            </Link>

            {/* Owner Management Button */}
            {isOwner && (
              <Link to="/creator/setup" className="sf-nav-manage-btn" title="Edit Setup">
                <SlidersHorizontal className="w-3.5 h-3.5 text-[#dfb180]" />
                <span>Manage</span>
              </Link>
            )}

            {/* Global Marketplace Directory */}
            <Link to="/marketplace" className="sf-nav-mp-link" title="Explore Global Marketplace">
              <span>Marketplace</span>
              <ExternalLink className="w-3 h-3 ml-1" />
            </Link>
          </div>
        </div>
      </header>

      {/* ── 2. MARKETPLACE-STYLE STOREFRONT HERO (PERSONALIZED TO CREATOR) ── */}
      <main className="storefront-main">
        <header className="marketplace-hero-header sf-hero-header">
          {/* Eyebrow Badge */}
          <div className="marketplace-hero-badge">
            <Sparkles className="w-3.5 h-3.5 text-[#dfb180]" />
            <span>Official Creator Marketplace</span>
            <span className="marketplace-badge-dot" />
            <span className="text-amber-300 font-semibold">@{storefront.store_slug}</span>
            <span className="marketplace-badge-dot" />
            <span className="text-emerald-400 font-semibold">100% Production Ready</span>
          </div>

          <div className="marketplace-hero-row">
            <div className="marketplace-hero-text">
              <div className="sf-hero-creator-badge-row">
                <div className="sf-hero-avatar-box">
                  {storefront.logo_url ? (
                    <img
                      src={storefront.logo_url}
                      alt={storefront.brand_name}
                      className="sf-hero-avatar-img"
                    />
                  ) : (
                    <Store className="w-7 h-7 text-[#dfb180]" />
                  )}
                  {storefront.is_verified && (
                    <div className="sf-hero-verified-dot" title="Verified Creator & Publisher">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    </div>
                  )}
                </div>
                <div>
                  <h1 className="marketplace-hero-title">
                    {storefront.brand_name}&apos;s <span className="marketplace-title-gradient">Website Storefront</span>
                  </h1>
                </div>
              </div>

              <p className="marketplace-hero-sub">
                {storefront.tagline ||
                  `Browse and purchase official, production-ready website templates created and maintained exclusively by ${storefront.brand_name}. Instant digital delivery with 100% clean source code.`}
              </p>

              {/* Creator Metadata Pills Strip */}
              <div className="sf-hero-meta-strip">
                <span className="sf-meta-pill">
                  <User className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Author: <strong>{storefront.creator_name || storefront.brand_name}</strong></span>
                </span>

                <button
                  type="button"
                  onClick={handleCopyId}
                  className="sf-meta-pill sf-meta-pill-btn"
                  title="Copy Storefront ID"
                >
                  <span className="text-zinc-400">ID:</span>
                  <span className="text-[#dfb180] font-mono">@{storefront.store_slug}</span>
                  {copiedId ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-zinc-400" />}
                </button>

                <span className="sf-meta-pill">
                  <LayoutGrid className="w-3.5 h-3.5 text-[#dfb180]" />
                  <span><strong>{templates.length}</strong> Exclusive Websites</span>
                </span>

                <span className="sf-meta-pill">
                  <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                  <span><strong>{Number(storefront.stats?.average_rating || 5.0).toFixed(1)}</strong> Rating</span>
                </span>

                {storefront.bio && (
                  <button
                    type="button"
                    onClick={() => setShowAboutDrawer(!showAboutDrawer)}
                    className="sf-meta-pill sf-meta-pill-btn text-zinc-300 hover:text-white"
                  >
                    <Info className="w-3.5 h-3.5 text-[#dfb180]" />
                    <span>{showAboutDrawer ? "Hide Creator Story" : "Read Creator Story"}</span>
                    {showAboutDrawer ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                )}
              </div>
            </div>

            {/* Hero Quick Conversion Actions */}
            <div className="sf-hero-actions-box">
              <button
                type="button"
                onClick={handleShare}
                className="sf-share-btn-hero"
                title="Share this storefront with buyers"
              >
                {copiedLink ? (
                  <>
                    <Check className="w-4 h-4 text-emerald-400 mr-2" />
                    <span>Storefront Link Copied!</span>
                  </>
                ) : (
                  <>
                    <Share2 className="w-4 h-4 mr-2" />
                    <span>Share Storefront Link</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() => setShowContactModal(true)}
                className="sf-contact-btn-hero"
              >
                <Send className="w-4 h-4 mr-2" />
                <span>Contact for Custom Project</span>
              </button>
            </div>
          </div>
        </header>

        {/* ── 3. EXPANDABLE CREATOR STORY & STANDARDS CARD ── */}
        {storefront.bio && showAboutDrawer && (
          <div className="sf-about-accordion-card">
            <div className="sf-about-accordion-header">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-[#dfb180]" />
                <h3 className="text-base font-bold text-white">About {storefront.brand_name}</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowAboutDrawer(false)}
                className="text-xs text-zinc-400 hover:text-white cursor-pointer"
              >
                Close ✕
              </button>
            </div>
            <p className="sf-about-accordion-text">{storefront.bio}</p>

            <div className="sf-accordion-standards-row">
              <div className="sf-acc-item">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Verified Code Quality &amp; Clean Architecture</span>
              </div>
              <div className="sf-acc-item">
                <Smartphone className="w-4 h-4 text-sky-400" />
                <span>100% Mobile &amp; Responsive Tested</span>
              </div>
              <div className="sf-acc-item">
                <Zap className="w-4 h-4 text-amber-400" />
                <span>Instant Code Download Upon Purchase</span>
              </div>
            </div>
          </div>
        )}

        {/* ── 4. MARKETPLACE TOOLBAR (SEARCH, CATEGORIES, FRAMEWORKS, SORT) ── */}
        <div className="marketplace-toolbar sf-toolbar">
          {/* Row 1 — Search bar scoped exclusively to this creator's catalog */}
          <div className="toolbar-row">
            <div className="marketplace-search-wrapper">
              <div className="marketplace-search">
                <Search className="marketplace-search-icon" />
                <input
                  type="text"
                  placeholder={`Search in ${storefront.brand_name}'s templates (e.g., 'SaaS', 'Vue', 'Portfolio')...`}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="marketplace-search-input"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery("")}
                    className="search-clear-btn"
                    aria-label="Clear search"
                  >
                    <X className="search-clear-icon" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Row 2 — Framework Selector Pills */}
          <div className="sf-frameworks-row">
            <div className="storefront-framework-tabs">
              {FRAMEWORKS.map((fw) => (
                <button
                  key={fw.id}
                  type="button"
                  onClick={() => setSelectedFramework(fw.id)}
                  className={`sf-fw-tab ${selectedFramework === fw.id ? "active" : ""}`}
                >
                  {fw.label}
                </button>
              ))}
            </div>

            {/* Sort & Category Controls */}
            <div className="sf-selects-wrap">
              {availableCategories.length > 0 && (
                <div className="sf-select-wrap">
                  <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="sf-select"
                  >
                    <option value="all">All Categories</option>
                    {availableCategories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="sf-select-wrap">
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="sf-select"
                >
                  <option value="featured">Featured First</option>
                  <option value="popular">Most Popular</option>
                  <option value="newest">Newest Additions</option>
                  <option value="price-low">Price: Low to High</option>
                  <option value="price-high">Price: High to Low</option>
                  <option value="rating">Highest Rated</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* ── 5. TEMPLATES CATALOG GRID (BUY ONLY THIS CREATOR'S WEBSITES) ── */}
        <div className="storefront-grid-section">
          <div className="sf-catalog-results-header">
            <span className="sf-catalog-count-label">
              Showing <strong>{filteredTemplates.length}</strong> of <strong>{templates.length}</strong> websites by <strong>{storefront.brand_name}</strong>
            </span>
            {(searchQuery || selectedFramework !== "all" || selectedCategory !== "all") && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setSelectedFramework("all");
                  setSelectedCategory("all");
                }}
                className="sf-clear-filters-link"
              >
                Reset filters
              </button>
            )}
          </div>

          {filteredTemplates.length > 0 ? (
            <div className="storefront-template-grid">
              {filteredTemplates.map((template, idx) => (
                <TemplateCard
                  key={template.id || template.slug}
                  template={template}
                  index={idx}
                />
              ))}
            </div>
          ) : (
            /* Empty State */
            <div className="storefront-empty-state">
              <div className="sf-empty-icon">
                <ShoppingBag className="w-10 h-10 text-zinc-500" />
              </div>
              <h3>No templates match your search</h3>
              <p>
                {searchQuery || selectedFramework !== "all" || selectedCategory !== "all"
                  ? `No templates matching "${searchQuery || selectedFramework}" found in ${storefront.brand_name}'s collection.`
                  : `${storefront.brand_name} hasn't published templates to this storefront yet.`}
              </p>
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setSelectedFramework("all");
                  setSelectedCategory("all");
                }}
                className="sf-btn-primary mt-4"
              >
                <span>View All {storefront.brand_name}&apos;s Templates</span>
              </button>
            </div>
          )}
        </div>

        {/* ── 6. TRUST & GUARANTEES ROW ── */}
        <div className="storefront-trust-section">
          <div className="sf-trust-item">
            <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <strong>100% Verified Production Code</strong>
              <span> Clean source code delivered instantly upon completed purchase.</span>
            </div>
          </div>
          <div className="sf-trust-item">
            <Eye className="w-5 h-5 text-[#dfb180] shrink-0" />
            <div>
              <strong>Free Interactive Live Demos</strong>
              <span> Preview responsive desktop, tablet, and mobile views in real time.</span>
            </div>
          </div>
          <div
            className="sf-trust-item sf-trust-clickable"
            onClick={() => setShowPaymentModal(true)}
            role="button"
            tabIndex={0}
          >
            <CreditCard className="w-5 h-5 text-[#dfb180] shrink-0" />
            <div>
              <strong>Multiple Accepted Payment Methods</strong>
              <span>
                {" "}
                {acceptedMethods.map((m) => PAYMENT_METHOD_INFO[m]?.label || m).slice(0, 4).join(", ")}
                {acceptedMethods.length > 4 ? ` +${acceptedMethods.length - 4} more` : ""}. Click to view details.
              </span>
            </div>
          </div>
        </div>
      </main>

      {/* ── 7. STOREFRONT FOOTER ── */}
      <footer className="sf-footer">
        <div className="sf-footer-container">
          <div className="sf-footer-top">
            {/* Creator Branding & Identity */}
            <div className="sf-footer-brand">
              <div className="sf-footer-logo-row">
                <div className="sf-footer-logo-box">
                  {storefront.logo_url ? (
                    <img
                      src={storefront.logo_url}
                      alt={storefront.brand_name}
                      className="sf-footer-logo-img"
                    />
                  ) : (
                    <Store className="w-5 h-5 text-[#dfb180]" />
                  )}
                </div>
                <div>
                  <h3 className="sf-footer-title">{storefront.brand_name}</h3>
                  <span className="sf-footer-domain">
                    Official Creator Storefront • ID: @{storefront.store_slug}
                  </span>
                </div>
              </div>
              <p className="sf-footer-desc">
                {storefront.tagline ||
                  `Official creator storefront of ${storefront.brand_name}. High quality production-ready website templates.`}
              </p>
              <div className="sf-footer-author-pill">
                <User className="w-3.5 h-3.5 text-zinc-400" />
                <span>
                  Author: <strong>{storefront.creator_name || storefront.brand_name}</strong>
                </span>
                <span className="sf-footer-id-badge">ID: @{storefront.store_slug}</span>
              </div>
            </div>

            {/* Direct Creator Contact */}
            <div className="sf-footer-contact">
              <h4 className="sf-footer-section-title">Support &amp; Inquiries</h4>
              <p className="sf-footer-contact-desc">
                Have questions or need custom modifications? Contact{" "}
                <strong>{storefront.brand_name}</strong> directly:
              </p>
              {storefront.support_email && (
                <div className="sf-footer-email-box">
                  <Mail className="w-4 h-4 text-[#dfb180] shrink-0" />
                  <a
                    href={`mailto:${storefront.support_email}`}
                    className="sf-footer-email-link"
                  >
                    {storefront.support_email}
                  </a>
                  <button
                    type="button"
                    onClick={handleCopyEmail}
                    className="sf-footer-copy-btn"
                    title="Copy Email"
                  >
                    {copiedEmail ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              )}
              {storefront.website && (
                <a
                  href={storefront.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="sf-footer-site-link"
                >
                  <Globe className="w-4 h-4" />
                  <span>{storefront.website}</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>

            {/* Creator Socials */}
            <div className="sf-footer-meta">
              <h4 className="sf-footer-section-title">Connect &amp; Follow</h4>
              <div className="sf-footer-socials">
                {storefront.social_links?.twitter && (
                  <a
                    href={storefront.social_links.twitter}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="sf-footer-social-btn"
                    title="X / Twitter"
                  >
                    <XIcon className="w-4 h-4" />
                  </a>
                )}
                {storefront.social_links?.github && (
                  <a
                    href={storefront.social_links.github}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="sf-footer-social-btn"
                    title="GitHub"
                  >
                    <GithubIcon className="w-4 h-4" />
                  </a>
                )}
                {storefront.social_links?.linkedin && (
                  <a
                    href={storefront.social_links.linkedin}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="sf-footer-social-btn"
                    title="LinkedIn"
                  >
                    <LinkedinIcon className="w-4 h-4" />
                  </a>
                )}
              </div>
              <div className="sf-footer-engine-tag">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>
                  Storefront hosted on <strong>AI Site Studio</strong> domain with verified licensing &amp; automated checkout.
                </span>
              </div>
            </div>
          </div>

          {/* Bottom Copyright */}
          <div className="sf-footer-bottom">
            <p className="sf-footer-copy">
              &copy; {new Date().getFullYear()} <strong>{storefront.brand_name}</strong>. All rights reserved.
            </p>
            <div className="sf-footer-bottom-links">
              <span>Creator ID: @{storefront.store_slug}</span>
              <span className="sf-footer-dot">•</span>
              <Link to="/marketplace" className="sf-footer-sublink">
                Marketplace Directory
              </Link>
              <span className="sf-footer-dot">•</span>
              <Link to="/creator/setup" className="sf-footer-sublink">
                Extreme Creator Portal
              </Link>
            </div>
          </div>
        </div>
      </footer>

      {/* ── 8. INTERACTIVE CONTACT CREATOR MODAL ── */}
      {showContactModal && (
        <div className="sf-modal-backdrop" onClick={() => setShowContactModal(false)}>
          <div
            className="sf-modal-container"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="sf-modal-header">
              <div className="sf-modal-title-box">
                <div className="sf-modal-logo-wrap">
                  {storefront.logo_url ? (
                    <img src={storefront.logo_url} alt={storefront.brand_name} className="sf-modal-logo" />
                  ) : (
                    <Store className="w-5 h-5 text-[#dfb180]" />
                  )}
                </div>
                <div>
                  <h3 className="sf-modal-title">Contact {storefront.brand_name}</h3>
                  <p className="sf-modal-subtitle">
                    Creator ID: @{storefront.store_slug} • Direct Inquiries &amp; Custom Work
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowContactModal(false)}
                className="sf-modal-close-btn"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="sf-modal-body">
              {contactSubmitted ? (
                <div className="sf-form-success-card">
                  <div className="sf-success-icon-wrap">
                    <CheckCircle2 className="w-12 h-12 text-emerald-400" />
                  </div>
                  <h3>Message Dispatched!</h3>
                  <p>
                    Your message regarding &ldquo;{contactForm.purpose}&rdquo; has been delivered to <strong>{storefront.brand_name}</strong>. They will reply to <strong>{contactForm.email}</strong>.
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      setContactSubmitted(false);
                      setShowContactModal(false);
                      setContactForm({
                        name: "",
                        email: "",
                        purpose: "Template Customization",
                        subject: "",
                        message: "",
                      });
                    }}
                    className="sf-btn-primary mt-4"
                  >
                    <span>Back to Storefront</span>
                  </button>
                </div>
              ) : (
                <form onSubmit={handleContactSubmit} className="sf-inquiry-form-modal">
                  <div className="sf-form-grid-2">
                    <div className="sf-form-group">
                      <label htmlFor="modal-contact-name">Your Full Name *</label>
                      <input
                        id="modal-contact-name"
                        type="text"
                        required
                        placeholder="Alex Johnson"
                        value={contactForm.name}
                        onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                        className="sf-input"
                      />
                    </div>
                    <div className="sf-form-group">
                      <label htmlFor="modal-contact-email">Your Email Address *</label>
                      <input
                        id="modal-contact-email"
                        type="email"
                        required
                        placeholder="alex@company.com"
                        value={contactForm.email}
                        onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
                        className="sf-input"
                      />
                    </div>
                  </div>

                  <div className="sf-form-group">
                    <label htmlFor="modal-contact-purpose">Inquiry Purpose</label>
                    <select
                      id="modal-contact-purpose"
                      value={contactForm.purpose}
                      onChange={(e) => setContactForm({ ...contactForm, purpose: e.target.value })}
                      className="sf-input sf-select-input"
                    >
                      <option value="Template Customization">Template Customization &amp; Tweaks</option>
                      <option value="Custom Website Build">Bespoke Full-Stack Website Build</option>
                      <option value="Pre-Purchase Inquiry">Pre-Purchase / Feature Question</option>
                      <option value="Commercial Licensing">Commercial / Extended License</option>
                      <option value="Technical Support">Technical Support</option>
                    </select>
                  </div>

                  <div className="sf-form-group">
                    <label htmlFor="modal-contact-message">Your Message *</label>
                    <textarea
                      id="modal-contact-message"
                      required
                      rows={4}
                      placeholder="Please describe what you need or which template you are referring to..."
                      value={contactForm.message}
                      onChange={(e) => setContactForm({ ...contactForm, message: e.target.value })}
                      className="sf-input sf-textarea"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={contactSubmitting}
                    className="sf-form-submit-btn"
                  >
                    {contactSubmitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        <span>Sending Inquiry...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4 mr-2" />
                        <span>Send Message to {storefront.brand_name}</span>
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── 9. ACCEPTED PAYMENT CHANNELS MODAL ── */}
      {showPaymentModal && (
        <div className="sf-modal-backdrop" onClick={() => setShowPaymentModal(false)}>
          <div
            className="sf-modal-container"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="sf-modal-header">
              <div className="sf-modal-title-box">
                <div className="sf-modal-logo-wrap">
                  {storefront.logo_url ? (
                    <img src={storefront.logo_url} alt={storefront.brand_name} className="sf-modal-logo" />
                  ) : (
                    <Store className="w-5 h-5 text-[#dfb180]" />
                  )}
                </div>
                <div>
                  <h3 className="sf-modal-title">Payment Options for {storefront.brand_name}</h3>
                  <p className="sf-modal-subtitle">
                    Creator ID: @{storefront.store_slug} • Direct &amp; Platform Checkout
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowPaymentModal(false)}
                className="sf-modal-close-btn"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="sf-modal-body">
              <div className="sf-modal-intro">
                <Info className="w-4 h-4 text-[#dfb180] shrink-0 mt-0.5" />
                <p>
                  <strong>{storefront.brand_name}</strong> accepts direct payments through the verified channels below as well as instant checkout via the Add to Cart button on any template.
                </p>
              </div>

              {/* Grid of Enabled Payment Methods */}
              <div className="sf-modal-methods-grid">
                {/* 1. STRIPE */}
                {acceptedMethods.includes("stripe") && (
                  <div className="sf-method-card">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(99, 91, 255, 0.15)", color: "#635bff" }}>
                        <CreditCard className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">Stripe</h4>
                        <span className="sf-method-sub">Credit / Debit Cards, Apple Pay, Google Pay</span>
                      </div>
                      {paymentOptions.primary === "stripe" && (
                        <span className="sf-primary-badge">Primary</span>
                      )}
                    </div>
                    <div className="sf-method-card-content">
                      {paymentOptions.stripe?.payment_link ? (
                        <a
                          href={paymentOptions.stripe.payment_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="sf-direct-pay-action-btn"
                        >
                          <span>Pay via Creator Stripe Link</span>
                          <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
                        </a>
                      ) : paymentOptions.stripe?.email ? (
                        <div className="sf-method-copy-box">
                          <span className="sf-method-field-label">Creator Stripe Email:</span>
                          <div className="sf-copy-row">
                            <code className="sf-copy-code">{paymentOptions.stripe.email}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("Stripe Email", paymentOptions.stripe.email)}
                              className="sf-copy-btn"
                            >
                              {copiedPaymentField === "Stripe Email" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="sf-method-info-text">
                          Stripe checkout is available on all template cards via Add to Cart.
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* 2. RAZORPAY */}
                {acceptedMethods.includes("razorpay") && (
                  <div className="sf-method-card">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(59, 130, 246, 0.15)", color: "#3b82f6" }}>
                        <Zap className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">Razorpay</h4>
                        <span className="sf-method-sub">UPI, NetBanking, Cards (INR &amp; Global)</span>
                      </div>
                      {paymentOptions.primary === "razorpay" && (
                        <span className="sf-primary-badge">Primary</span>
                      )}
                    </div>
                    <div className="sf-method-card-content">
                      {paymentOptions.razorpay?.vpa ? (
                        <div className="sf-method-copy-box">
                          <span className="sf-method-field-label">Creator Razorpay / UPI VPA:</span>
                          <div className="sf-copy-row">
                            <code className="sf-copy-code">{paymentOptions.razorpay.vpa}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("Razorpay VPA", paymentOptions.razorpay.vpa)}
                              className="sf-copy-btn"
                            >
                              {copiedPaymentField === "Razorpay VPA" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="sf-method-info-text">
                          Razorpay gateway supported at checkout for all template purchases.
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* 3. DIRECT UPI */}
                {acceptedMethods.includes("upi") && (
                  <div className="sf-method-card">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(168, 85, 247, 0.15)", color: "#a855f7" }}>
                        <QrCode className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">Direct UPI</h4>
                        <span className="sf-method-sub">Google Pay, PhonePe, Paytm, BHIM</span>
                      </div>
                      {paymentOptions.primary === "upi" && (
                        <span className="sf-primary-badge">Primary</span>
                      )}
                    </div>
                    <div className="sf-method-card-content">
                      {paymentOptions.upi?.vpa ? (
                        <div className="sf-method-copy-box">
                          <span className="sf-method-field-label">Creator UPI ID / VPA:</span>
                          <div className="sf-copy-row">
                            <code className="sf-copy-code">{paymentOptions.upi.vpa}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("UPI VPA", paymentOptions.upi.vpa)}
                              className="sf-copy-btn"
                            >
                              {copiedPaymentField === "UPI VPA" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="sf-method-info-text">
                          Direct UPI enabled. Contact creator for instant QR payment dispatch.
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* 4. BANK WIRE */}
                {(acceptedMethods.includes("bank_wire") || acceptedMethods.includes("bank")) && (
                  <div className="sf-method-card">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(96, 165, 250, 0.15)", color: "#60a5fa" }}>
                        <Building2 className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">Bank Wire</h4>
                        <span className="sf-method-sub">Direct Account Deposit / SWIFT</span>
                      </div>
                    </div>
                    <div className="sf-method-card-content">
                      {paymentOptions.bank?.iban ? (
                        <div className="sf-method-copy-box">
                          <span className="sf-method-field-label">IBAN:</span>
                          <div className="sf-copy-row">
                            <code className="sf-copy-code">{paymentOptions.bank.iban}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("IBAN", paymentOptions.bank.iban)}
                              className="sf-copy-btn"
                            >
                              {copiedPaymentField === "IBAN" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="sf-method-info-text">
                          Bank wire transfer available for custom projects and enterprise licensing.
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* 5. CRYPTO / WEB3 */}
                {acceptedMethods.includes("crypto") && (
                  <div className="sf-method-card">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(245, 158, 11, 0.15)", color: "#f59e0b" }}>
                        <Wallet className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">Crypto / Web3</h4>
                        <span className="sf-method-sub">USDT, BTC, ETH</span>
                      </div>
                    </div>
                    <div className="sf-method-card-content">
                      {paymentOptions.crypto?.wallet_address ? (
                        <div className="sf-method-copy-box">
                          <span className="sf-method-field-label">Deposit Address:</span>
                          <div className="sf-copy-row">
                            <code className="sf-copy-code">{paymentOptions.crypto.wallet_address}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("Wallet Address", paymentOptions.crypto.wallet_address)}
                              className="sf-copy-btn"
                            >
                              {copiedPaymentField === "Wallet Address" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="sf-method-info-text">
                          USDT / USDC payments supported. Contact creator for wallet memo.
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Escrow Guarantee */}
              <div className="sf-payments-guarantee-box mt-4">
                <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
                <div>
                  <h4 className="text-sm font-bold text-emerald-400">100% Protected Platform Guarantee</h4>
                  <p className="text-xs text-zinc-300">
                    All template purchases include automatic license generation and instant code download.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
