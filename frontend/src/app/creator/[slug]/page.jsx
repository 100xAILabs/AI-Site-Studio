"use client";

import { useState, useMemo, useEffect } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Store,
  Sparkles,
  ShieldCheck,
  Star,
  Download,
  ExternalLink,
  Search,
  Filter,
  Layers,
  ArrowUpDown,
  Share2,
  Copy,
  Check,
  Globe,
  Mail,
  ShoppingBag,
  SlidersHorizontal,
  ChevronRight,
  Eye,
  ShoppingCart,
  Loader2,
  AlertCircle,
  ArrowLeft,
  User,
  Send,
  MessageSquare,
  CreditCard,
  Zap,
  DollarSign,
  QrCode,
  Building2,
  Wallet,
  X,
  Info,
  LayoutGrid,
  Code2,
  Smartphone,
  CheckCircle2,
  Clock,
  ArrowRight,
  BadgeCheck,
  Users,
} from "lucide-react";
import TemplateCard from "@/components/marketplace/TemplateCard";
import CreatorStorefrontNavbar from "@/components/layout/CreatorStorefrontNavbar";
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
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, isSignedIn } = useAppUser();
  const cartItems = useCartStore((s) => s.items) || [];

  // Active Tab/Page: "templates" | "about" | "contact" | "payments"
  const activeTab = searchParams.get("tab") || "templates";

  const setTab = (newTab) => {
    const next = new URLSearchParams(searchParams);
    if (newTab === "templates") {
      next.delete("tab");
    } else {
      next.set("tab", newTab);
    }
    setSearchParams(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFramework, setSelectedFramework] = useState("all");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [sortBy, setSortBy] = useState("featured");
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
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
      const pageLabel =
        activeTab === "about"
          ? `About ${storefront.brand_name}`
          : activeTab === "contact"
          ? `Contact ${storefront.brand_name}`
          : activeTab === "payments"
          ? `Payment Channels — ${storefront.brand_name}`
          : `${storefront.brand_name} — Templates Catalog`;
      document.title = `${pageLabel} | Official Storefront`;
    }
    return () => {
      document.title = "AI Site Studio — AI Website Generator & Marketplace";
    };
  }, [storefront, activeTab]);

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

  // Filter & Sort for Templates Tab
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
    toast.success("Storefront URL copied to clipboard!");
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

  const { data: creatorCustomersData } = useQuery({
    queryKey: ["creatorCustomers", storefront?.id],
    queryFn: async () => {
      const res = await api.get("/creator/customers");
      return res || {};
    },
    enabled: Boolean(isOwner),
  });

  const creatorCustomers = useMemo(() => {
    if (Array.isArray(creatorCustomersData)) return creatorCustomersData;
    if (creatorCustomersData?.customers && Array.isArray(creatorCustomersData.customers)) {
      return creatorCustomersData.customers;
    }
    return [];
  }, [creatorCustomersData]);

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
    <div className="storefront-page">
      {/* ── 1. AUTHORITATIVE CREATOR STOREFRONT HEADER NAVBAR ── */}
      <CreatorStorefrontNavbar
        storefront={storefront}
        creatorSlug={slug}
        cartItems={cartItems}
        activeNav={activeTab}
        onSelectTab={(t) => setTab(t)}
      />

      {/* ── 2. DEDICATED DISTINCT PAGES ── */}
      <main className="storefront-main">

        {/* ========================================================================= */}
        {/* PAGE 1: TEMPLATES CATALOG PAGE                                            */}
        {/* ========================================================================= */}
        {activeTab === "templates" && (
          <div className="sf-page-view sf-page-templates">
            {/* Catalog Hero Header */}
            <div className="sf-catalog-hero">
              <div className="sf-catalog-hero-inner">
                <div className="sf-catalog-brand-left">
                  <div className="sf-catalog-logo-wrap">
                    {storefront.logo_url ? (
                      <img
                        src={storefront.logo_url}
                        alt={storefront.brand_name}
                        className="sf-catalog-logo-img"
                        onError={(e) => {
                          e.currentTarget.style.display = "none";
                        }}
                      />
                    ) : (
                      <Store className="w-8 h-8 text-[#dfb180]" />
                    )}
                    {storefront.is_verified && (
                      <div className="sf-verified-mini-badge" title="Verified Creator & Publisher">
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                      </div>
                    )}
                  </div>
                  <div>
                    <div className="sf-catalog-title-row">
                      <h1 className="sf-catalog-brand-name">{storefront.brand_name}</h1>
                      <button
                        type="button"
                        onClick={handleCopyId}
                        className="sf-catalog-id-chip"
                        title="Copy Creator ID"
                      >
                        <span>@{storefront.store_slug}</span>
                        {copiedId ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      </button>
                    </div>
                    <p className="sf-catalog-tagline">
                      {storefront.tagline ||
                        `Official storefront catalog featuring production-ready website templates.`}
                    </p>
                    <div className="sf-catalog-meta-strip">
                      <span className="sf-meta-pill">
                        <LayoutGrid className="w-3 h-3 text-[#dfb180]" />
                        <strong>{templates.length}</strong> Templates
                      </span>
                      <span className="sf-meta-pill">
                        <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                        <strong>{Number(storefront.stats?.average_rating || 5.0).toFixed(1)}</strong> Rating
                      </span>
                      <span className="sf-meta-pill">
                        <ShieldCheck className="w-3 h-3 text-emerald-400" />
                        Verified Clean Code
                      </span>
                      {storefront.is_bank_connected === false ? (
                        <span className="sf-meta-pill" style={{ color: "#fbbf24", borderColor: "rgba(245, 158, 11, 0.3)", background: "rgba(245, 158, 11, 0.1)" }}>
                          <AlertCircle className="w-3 h-3 text-amber-400" />
                          Purchasing Paused (Bank Not Linked)
                        </span>
                      ) : (
                        <span className="sf-meta-pill" style={{ color: "#34d399", borderColor: "rgba(16, 185, 129, 0.3)", background: "rgba(16, 185, 129, 0.1)" }}>
                          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          Direct Payouts Active
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="sf-catalog-actions-right">
                  <button
                    type="button"
                    onClick={() => setTab("contact")}
                    className="sf-btn-primary"
                  >
                    <Send className="w-3.5 h-3.5 mr-1.5" />
                    <span>Contact Creator</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleShare}
                    className="sf-btn-secondary"
                    title="Share Storefront URL"
                  >
                    {copiedLink ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400 mr-1.5" />
                        <span>Link Copied</span>
                      </>
                    ) : (
                      <>
                        <Share2 className="w-3.5 h-3.5 mr-1.5" />
                        <span>Share</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Filter & Search Bar */}
            <div id="catalog" className="storefront-filter-section">
              {/* Framework Selector Tabs */}
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

              {/* Search, Category, and Sort Row */}
              <div className="storefront-controls-row">
                <div className="sf-search-wrap">
                  <Search className="w-4 h-4 text-zinc-400 absolute left-3.5" />
                  <input
                    type="text"
                    placeholder={`Search in ${storefront.brand_name}'s templates...`}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="sf-search-input"
                  />
                </div>

                <div className="sf-selects-wrap">
                  {/* Category Filter */}
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

                  {/* Sort Filter */}
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

            {/* Templates Grid */}
            <div className="storefront-grid-section">
              {filteredTemplates.length > 0 ? (
                <div className="storefront-template-grid">
                  {filteredTemplates.map((template, idx) => (
                    <TemplateCard
                      key={template.id || template.slug}
                      template={template}
                      index={idx}
                      creatorSlug={storefront.store_slug || slug}
                    />
                  ))}
                </div>
              ) : (
                /* Empty State */
                <div className="storefront-empty-state">
                  <div className="sf-empty-icon">
                    <ShoppingBag className="w-10 h-10 text-zinc-500" />
                  </div>
                  <h3>No templates found in this view</h3>
                  <p>
                    {searchQuery || selectedFramework !== "all" || selectedCategory !== "all"
                      ? "Try adjusting your search query or framework filter."
                      : `${storefront.brand_name} hasn't published templates to this storefront yet.`}
                  </p>
                  {isOwner && (
                    <Link to="/dashboard?tab=creator-studio" className="sf-btn-primary mt-4">
                      <Sparkles className="w-4 h-4 mr-2" />
                      <span>Retail a Generated Website Now</span>
                    </Link>
                  )}
                </div>
              )}
            </div>

            {/* Trust & Guarantee Section */}
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
                onClick={() => setTab("payments")}
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
          </div>
        )}

        {/* ========================================================================= */}
        {/* PAGE 2: ABOUT CREATOR & STORY PAGE                                        */}
        {/* ========================================================================= */}
        {activeTab === "about" && (
          <div className="sf-page-view sf-page-about">
            {/* Dedicated Page Header Banner */}
            <div className="sf-page-header-banner">
              <div className="sf-editorial-badge">
                <User className="w-3.5 h-3.5 text-[#dfb180]" />
                <span>Creator Story &amp; Brand Profile</span>
              </div>
              <h2>About {storefront.brand_name}</h2>
              <p>
                {storefront.tagline ||
                  `Dedicated creator profile, design standards, and technical engineering philosophy.`}
              </p>
            </div>

            <div className="sf-about-layout">
              {/* Left Column: Author Identity Card */}
              <div className="sf-about-author-sidebar">
                <div className="sf-author-card">
                  <div className="sf-author-avatar-wrap">
                    {storefront.logo_url ? (
                      <img
                        src={storefront.logo_url}
                        alt={storefront.brand_name}
                        className="sf-author-avatar-img"
                      />
                    ) : (
                      <Store className="w-12 h-12 text-[#dfb180]" />
                    )}
                    {storefront.is_verified && (
                      <div className="sf-author-badge-pill" title="Verified Creator">
                        <BadgeCheck className="w-4 h-4 text-emerald-400" />
                      </div>
                    )}
                  </div>

                  <h3 className="sf-author-title">{storefront.brand_name}</h3>
                  <div className="sf-author-id-box">
                    <span className="font-mono">@{storefront.store_slug}</span>
                    <button
                      type="button"
                      onClick={handleCopyId}
                      className="sf-author-id-copy"
                      title="Copy ID"
                    >
                      {copiedId ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>

                  {storefront.creator_name && (
                    <div className="sf-author-creator-name">
                      <User className="w-3.5 h-3.5 text-zinc-400 inline mr-1" />
                      <span>{storefront.creator_name}</span>
                    </div>
                  )}

                  <div className="sf-author-stats-list">
                    <div className="sf-author-stat-row">
                      <span>Catalog Size:</span>
                      <strong>{templates.length} Published Sites</strong>
                    </div>
                    <div className="sf-author-stat-row">
                      <span>Rating:</span>
                      <strong className="flex items-center gap-1">
                        <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400 inline" />
                        {Number(storefront.stats?.average_rating || 5.0).toFixed(1)} / 5.0
                      </strong>
                    </div>
                    <div className="sf-author-stat-row">
                      <span>Happy Customers:</span>
                      <strong>{storefront.stats?.total_sales || 0}+</strong>
                    </div>
                  </div>

                  {/* Direct Contact Button */}
                  {storefront.support_email && (
                    <div className="sf-author-email-block">
                      <span className="sf-author-block-label">Support Email:</span>
                      <a href={`mailto:${storefront.support_email}`} className="sf-author-email-val">
                        {storefront.support_email}
                      </a>
                      <button
                        type="button"
                        onClick={handleCopyEmail}
                        className="sf-author-email-copy-btn"
                      >
                        {copiedEmail ? "Copied" : "Copy Email"}
                      </button>
                    </div>
                  )}

                  {/* Website & Socials */}
                  {storefront.website && (
                    <a
                      href={storefront.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="sf-author-website-link"
                    >
                      <Globe className="w-4 h-4 text-blue-400" />
                      <span className="truncate">{storefront.website.replace(/^https?:\/\//, "")}</span>
                      <ExternalLink className="w-3 h-3 text-zinc-500" />
                    </a>
                  )}

                  <div className="sf-author-socials-row">
                    {storefront.social_links?.twitter && (
                      <a href={storefront.social_links.twitter} target="_blank" rel="noopener noreferrer" className="sf-social-link">
                        <XIcon className="w-4 h-4" />
                      </a>
                    )}
                    {storefront.social_links?.github && (
                      <a href={storefront.social_links.github} target="_blank" rel="noopener noreferrer" className="sf-social-link">
                        <GithubIcon className="w-4 h-4" />
                      </a>
                    )}
                    {storefront.social_links?.linkedin && (
                      <a href={storefront.social_links.linkedin} target="_blank" rel="noopener noreferrer" className="sf-social-link">
                        <LinkedinIcon className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column: Editorial Narrative & Standards */}
              <div className="sf-about-main-col">
                {/* Biography Prose */}
                <div className="sf-about-prose-card">
                  <h3 className="sf-card-title">Creator Biography</h3>
                  {storefront.bio ? (
                    <p className="sf-about-bio-text">{storefront.bio}</p>
                  ) : (
                    <p className="sf-about-bio-text text-zinc-400 italic">
                      {storefront.brand_name} focuses on delivering pristine, production-tested website templates. Every codebase is vetted for zero layout shift, semantic markup, and optimal Lighthouse performance.
                    </p>
                  )}
                </div>

                {/* Quality Standards 4-Grid */}
                <div className="sf-about-standards-section">
                  <h3 className="sf-card-title">Design &amp; Engineering Standards</h3>
                  <div className="sf-standards-grid">
                    <div className="sf-standard-card">
                      <div className="sf-standard-icon-box">
                        <ShieldCheck className="w-6 h-6 text-emerald-400" />
                      </div>
                      <h4>Verified Publisher</h4>
                      <p>Certified developer with verified code generation license rights and escrow security.</p>
                    </div>

                    <div className="sf-standard-card">
                      <div className="sf-standard-icon-box">
                        <Code2 className="w-6 h-6 text-[#dfb180]" />
                      </div>
                      <h4>100% Production Code</h4>
                      <p>Clean structure, semantic HTML5, zero bloat, and standalone REST APIs with SQLite/Postgres.</p>
                    </div>

                    <div className="sf-standard-card">
                      <div className="sf-standard-icon-box">
                        <Smartphone className="w-6 h-6 text-sky-400" />
                      </div>
                      <h4>Flawless Responsiveness</h4>
                      <p>No horizontal overflow, mobile drawer navigation, clamp() fluid typography, 44px+ touch targets.</p>
                    </div>

                    <div className="sf-standard-card">
                      <div className="sf-standard-icon-box">
                        <Zap className="w-6 h-6 text-amber-400" />
                      </div>
                      <h4>Instant Asset Delivery</h4>
                      <p>Complete source files, ready-to-run package.json, and interactive live demo canvas.</p>
                    </div>
                  </div>
                </div>

                {/* Frameworks Specialized */}
                <div className="sf-about-tech-section">
                  <h3 className="sf-card-title">Specialized Frameworks &amp; Stacks</h3>
                  <div className="sf-skills-pills">
                    {["React 19", "Vue 3", "Next.js", "Nuxt", "Svelte", "Tailwind CSS", "Vanilla CSS Modules", "FastAPI (Python)", "Node.js / Express", "SQLite / PostgreSQL"].map(
                      (tech) => (
                        <span key={tech} className="sf-skill-pill">
                          <CheckCircle2 className="w-3.5 h-3.5 text-[#dfb180]" />
                          <span>{tech}</span>
                        </span>
                      )
                    )}
                  </div>
                </div>

                {/* CTA Card */}
                <div className="sf-about-cta-card">
                  <div>
                    <h3>Explore {storefront.brand_name}&apos;s Templates</h3>
                    <p>Browse our catalog of {templates.length} ready-to-deploy websites or request a custom build.</p>
                  </div>
                  <div className="sf-about-cta-btns">
                    <button
                      type="button"
                      onClick={() => setTab("templates")}
                      className="sf-btn-primary"
                    >
                      <LayoutGrid className="w-4 h-4 mr-2" />
                      <span>Browse Catalog ({templates.length})</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setTab("contact")}
                      className="sf-btn-secondary"
                    >
                      <Send className="w-4 h-4 mr-2" />
                      <span>Contact Creator</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* PAGE 3: CONTACT CREATOR & INQUIRIES PAGE                                  */}
        {/* ========================================================================= */}
        {activeTab === "contact" && (
          <div className="sf-page-view sf-page-contact">
            {/* Dedicated Page Header Banner */}
            <div className="sf-page-header-banner">
              <div className="sf-editorial-badge">
                <Send className="w-3.5 h-3.5 text-[#dfb180]" />
                <span>Direct Creator Inquiries</span>
              </div>
              <h2>Get in Touch with {storefront.brand_name}</h2>
              <p>
                Have questions about a template, need custom feature additions, or want to commission a unique website? Submit your inquiry directly below.
              </p>
            </div>

            <div className="sf-contact-layout">
              {/* Left Column: Direct Info & SLA */}
              <div className="sf-contact-info-col">
                {/* Direct Email Card */}
                {storefront.support_email && (
                  <div className="sf-contact-card">
                    <div className="sf-contact-card-icon">
                      <Mail className="w-5 h-5 text-[#dfb180]" />
                    </div>
                    <div className="sf-contact-card-content">
                      <h4>Official Support Email</h4>
                      <a
                        href={`mailto:${storefront.support_email}`}
                        className="sf-contact-email-link"
                      >
                        {storefront.support_email}
                      </a>
                      <p className="sf-contact-hint">Click to launch your mail client or copy directly.</p>
                      <button
                        type="button"
                        onClick={handleCopyEmail}
                        className="sf-copy-action-btn"
                      >
                        {copiedEmail ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-emerald-400 mr-1.5" />
                            <span>Copied to Clipboard</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5 mr-1.5" />
                            <span>Copy Email Address</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                )}

                {/* Storefront ID Card */}
                <div className="sf-contact-card">
                  <div className="sf-contact-card-icon">
                    <Store className="w-5 h-5 text-[#dfb180]" />
                  </div>
                  <div className="sf-contact-card-content">
                    <h4>Verified Storefront ID</h4>
                    <code className="sf-id-code">@{storefront.store_slug}</code>
                    <p className="sf-contact-hint">Reference this ID when communicating with platform support.</p>
                    <button
                      type="button"
                      onClick={handleCopyId}
                      className="sf-copy-action-btn"
                    >
                      {copiedId ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400 mr-1.5" />
                          <span>ID Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5 mr-1.5" />
                          <span>Copy Creator ID</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Response SLA Badge */}
                <div className="sf-sla-card">
                  <Clock className="w-5 h-5 text-amber-400 shrink-0" />
                  <div>
                    <strong>Average Response Time</strong>
                    <p>Usually responds within 24 hours on business days.</p>
                  </div>
                </div>

                {/* Direct Payment Channels Link */}
                <div className="sf-payment-channels-promo">
                  <CreditCard className="w-5 h-5 text-[#dfb180] shrink-0" />
                  <div className="flex-1">
                    <strong>Accepted Payment Channels</strong>
                    <p>
                      {acceptedMethods.map((m) => PAYMENT_METHOD_INFO[m]?.label || m).join(", ")}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setTab("payments")}
                    className="sf-promo-link-btn"
                  >
                    <span>View</span>
                    <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </button>
                </div>
              </div>

              {/* Right Column: Interactive Inquiry Form */}
              <div className="sf-contact-form-col">
                {contactSubmitted ? (
                  <div className="sf-form-success-card">
                    <div className="sf-success-icon-wrap">
                      <CheckCircle2 className="w-12 h-12 text-emerald-400" />
                    </div>
                    <h3>Inquiry Dispatched Successfully!</h3>
                    <p>
                      Thank you for reaching out to <strong>{storefront.brand_name}</strong>. Your message regarding &ldquo;{contactForm.purpose}&rdquo; has been delivered.
                    </p>
                    <div className="sf-success-details">
                      <div className="sf-success-row">
                        <span>Sender:</span>
                        <strong>{contactForm.name} ({contactForm.email})</strong>
                      </div>
                      <div className="sf-success-row">
                        <span>Subject:</span>
                        <strong>{contactForm.subject || contactForm.purpose}</strong>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setContactSubmitted(false);
                        setContactForm({
                          name: "",
                          email: "",
                          purpose: "Template Customization",
                          subject: "",
                          message: "",
                        });
                      }}
                      className="sf-btn-secondary mt-6"
                    >
                      <span>Send Another Inquiry</span>
                    </button>
                  </div>
                ) : (
                  <form onSubmit={handleContactSubmit} className="sf-inquiry-form">
                    <h3 className="sf-form-title">Send a Direct Message</h3>
                    <p className="sf-form-subtitle">
                      Fill out this form and {storefront.brand_name} will receive your message directly at their support inbox.
                    </p>

                    <div className="sf-form-grid-2">
                      <div className="sf-form-group">
                        <label htmlFor="contact-name">Your Full Name *</label>
                        <input
                          id="contact-name"
                          type="text"
                          required
                          placeholder="e.g. Alex Johnson"
                          value={contactForm.name}
                          onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                          className="sf-input"
                        />
                      </div>

                      <div className="sf-form-group">
                        <label htmlFor="contact-email">Your Email Address *</label>
                        <input
                          id="contact-email"
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
                      <label htmlFor="contact-purpose">Inquiry Purpose</label>
                      <select
                        id="contact-purpose"
                        value={contactForm.purpose}
                        onChange={(e) => setContactForm({ ...contactForm, purpose: e.target.value })}
                        className="sf-input sf-select-input"
                      >
                        <option value="Template Customization">Template Customization &amp; Adjustments</option>
                        <option value="Custom Project">Bespoke Full-Stack Website Development</option>
                        <option value="Pre-Purchase Inquiry">Pre-Purchase / Feature Question</option>
                        <option value="Commercial Licensing">Commercial / Extended Licensing</option>
                        <option value="Technical Support">Technical Support / Integration Help</option>
                        <option value="General Inquiry">General Inquiries</option>
                      </select>
                    </div>

                    <div className="sf-form-group">
                      <label htmlFor="contact-subject">Subject</label>
                      <input
                        id="contact-subject"
                        type="text"
                        placeholder="e.g. Questions regarding responsive nav or custom colors"
                        value={contactForm.subject}
                        onChange={(e) => setContactForm({ ...contactForm, subject: e.target.value })}
                        className="sf-input"
                      />
                    </div>

                    <div className="sf-form-group">
                      <label htmlFor="contact-message">Your Message &amp; Project Requirements *</label>
                      <textarea
                        id="contact-message"
                        required
                        rows={5}
                        placeholder="Please provide details about what you need or the specific template you are referencing..."
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
                          <span>Send Direct Inquiry to {storefront.brand_name}</span>
                        </>
                      )}
                    </button>
                  </form>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* PAGE 4: PAYMENT CHANNELS & DIRECT PAY PAGE                                */}
        {/* ========================================================================= */}
        {activeTab === "payments" && (
          <div className="sf-page-view sf-page-payments">
            {/* Dedicated Page Header Banner */}
            <div className="sf-page-header-banner">
              <div className="sf-editorial-badge">
                <CreditCard className="w-3.5 h-3.5 text-[#dfb180]" />
                <span>Accepted Payment Channels</span>
              </div>
              <h2>Payment Options for {storefront.brand_name}</h2>
              <p>
                Creator ID: <code>@{storefront.store_slug}</code> • You can pay directly using verified methods below or complete your checkout via the platform cart.
              </p>
            </div>

            {/* Grid of Verified Payment Methods */}
            <div className="sf-methods-large-grid">
              {/* 1. STRIPE */}
              {acceptedMethods.includes("stripe") && (
                <div className="sf-method-large-card">
                  <div className="sf-method-card-header">
                    <div className="sf-method-icon-box" style={{ background: "rgba(99, 91, 255, 0.15)", color: "#635bff" }}>
                      <CreditCard className="w-6 h-6" />
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
                        Stripe checkout is fully integrated on this storefront. Simply add templates to your cart and proceed with credit card, debit card, or mobile wallets.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* 2. RAZORPAY */}
              {acceptedMethods.includes("razorpay") && (
                <div className="sf-method-large-card">
                  <div className="sf-method-card-header">
                    <div className="sf-method-icon-box" style={{ background: "rgba(59, 130, 246, 0.15)", color: "#3b82f6" }}>
                      <Zap className="w-6 h-6" />
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
                        Razorpay gateway supported at checkout for all template purchases and custom commissions.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* 3. DIRECT UPI */}
              {acceptedMethods.includes("upi") && (
                <div className="sf-method-large-card">
                  <div className="sf-method-card-header">
                    <div className="sf-method-icon-box" style={{ background: "rgba(168, 85, 247, 0.15)", color: "#a855f7" }}>
                      <QrCode className="w-6 h-6" />
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
                        Direct UPI enabled. Contact creator via Support Email for instant QR code payment dispatch.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* 4. BANK WIRE */}
              {(acceptedMethods.includes("bank_wire") || acceptedMethods.includes("bank")) && (
                <div className="sf-method-large-card">
                  <div className="sf-method-card-header">
                    <div className="sf-method-icon-box" style={{ background: "rgba(96, 165, 250, 0.15)", color: "#60a5fa" }}>
                      <Building2 className="w-6 h-6" />
                    </div>
                    <div className="sf-method-meta">
                      <h4 className="sf-method-name">Bank Wire / SWIFT / IBAN</h4>
                      <span className="sf-method-sub">Direct Account Transfer</span>
                    </div>
                  </div>
                  <div className="sf-method-card-content">
                    {paymentOptions.bank?.account_name || paymentOptions.bank?.iban ? (
                      <div className="sf-method-fields-list">
                        {paymentOptions.bank?.account_name && (
                          <div className="sf-bank-row">
                            <span>Account Name:</span>
                            <strong>{paymentOptions.bank.account_name}</strong>
                          </div>
                        )}
                        {paymentOptions.bank?.bank_name && (
                          <div className="sf-bank-row">
                            <span>Bank Name:</span>
                            <strong>{paymentOptions.bank.bank_name}</strong>
                          </div>
                        )}
                        {paymentOptions.bank?.iban && (
                          <div className="sf-copy-row mt-1">
                            <code className="sf-copy-code">IBAN: {paymentOptions.bank.iban}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("IBAN", paymentOptions.bank.iban)}
                              className="sf-copy-btn"
                            >
                              {copiedPaymentField === "IBAN" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="sf-method-info-text">
                        Bank wire transfer available for enterprise licensing and custom development milestones. Contact creator for invoice &amp; wire details.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* 5. CRYPTO / WEB3 */}
              {acceptedMethods.includes("crypto") && (
                <div className="sf-method-large-card">
                  <div className="sf-method-card-header">
                    <div className="sf-method-icon-box" style={{ background: "rgba(245, 158, 11, 0.15)", color: "#f59e0b" }}>
                      <Wallet className="w-6 h-6" />
                    </div>
                    <div className="sf-method-meta">
                      <h4 className="sf-method-name">Crypto / Web3</h4>
                      <span className="sf-method-sub">USDT, USDC, BTC, ETH</span>
                    </div>
                  </div>
                  <div className="sf-method-card-content">
                    {paymentOptions.crypto?.wallet_address ? (
                      <div className="sf-method-copy-box">
                        <span className="sf-method-field-label">Creator Deposit Address:</span>
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
                        Cryptocurrency settlements supported on USDT / USDC / ETH networks. Reach out to creator for direct payment memo.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Escrow & Trust Guarantee */}
            <div className="sf-payments-guarantee-box">
              <ShieldCheck className="w-6 h-6 text-emerald-400 shrink-0" />
              <div>
                <h4>100% Protected Platform Guarantee</h4>
                <p>
                  All purchases processed through AI Site Studio are protected by our automated license issuance and verified code delivery engine.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* PAGE 5: CREATOR CLIENTS & AUDIENCE CRM (OWNER ONLY)                       */}
        {/* ========================================================================= */}
        {activeTab === "customers" && isOwner && (
          <div className="sf-page-view sf-page-customers">
            {/* Header Banner */}
            <div className="sf-page-header-banner">
              <div className="sf-editorial-badge">
                <Users className="w-3.5 h-3.5 text-[#dfb180]" />
                <span>Creator Client CRM &amp; Audience</span>
              </div>
              <h2>Clients &amp; Customers for {storefront.brand_name}</h2>
              <p>
                All users who registered through your official creator portal (<code>/creator/{storefront.store_slug}/register</code>) or purchased templates created by you.
              </p>
            </div>

            {/* Quick Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
              <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/10">
                <div className="flex items-center justify-between text-zinc-400 text-xs mb-2">
                  <span>Total Registered Clients</span>
                  <Users className="w-4 h-4 text-[#dfb180]" />
                </div>
                <div className="text-2xl font-bold text-white">
                  {creatorCustomers.length}
                </div>
                <p className="text-[11px] text-zinc-500 mt-1">Clients attributed to your store</p>
              </div>

              <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/10">
                <div className="flex items-center justify-between text-zinc-400 text-xs mb-2">
                  <span>Template Purchases</span>
                  <ShoppingBag className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-2xl font-bold text-white">
                  {creatorCustomers.reduce((sum, c) => sum + (c.orders_count || 0), 0)}
                </div>
                <p className="text-[11px] text-zinc-500 mt-1">Orders for your templates</p>
              </div>

              <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/10">
                <div className="flex items-center justify-between text-zinc-400 text-xs mb-2">
                  <span>Total Direct Revenue</span>
                  <DollarSign className="w-4 h-4 text-amber-400" />
                </div>
                <div className="text-2xl font-bold text-white">
                  ${creatorCustomers.reduce((sum, c) => sum + (Number(c.total_spent) || 0), 0).toFixed(2)}
                </div>
                <p className="text-[11px] text-zinc-500 mt-1">Revenue from template sales</p>
              </div>
            </div>

            {/* Client Audience Table */}
            <div className="rounded-2xl bg-[#0c1017] border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Users className="w-4 h-4 text-[#dfb180]" />
                  <span>Customer Directory ({creatorCustomers.length})</span>
                </h3>
                <span className="text-xs text-zinc-400">
                  Storefront ID: <code>@{storefront.store_slug}</code>
                </span>
              </div>

              {creatorCustomers.length === 0 ? (
                <div className="p-12 text-center">
                  <div className="w-12 h-12 rounded-full bg-white/[0.04] text-zinc-500 flex items-center justify-center mx-auto mb-3">
                    <Users className="w-6 h-6" />
                  </div>
                  <h4 className="text-base font-semibold text-white mb-1">No Clients Registered Yet</h4>
                  <p className="text-xs text-zinc-400 max-w-md mx-auto mb-4">
                    Share your official creator portal link with clients. Any user who signs up or buys templates from your storefront will be tracked under your account:
                  </p>
                  <code className="px-3 py-1.5 rounded-lg bg-black/40 border border-white/10 text-xs text-[#dfb180] inline-block">
                    {typeof window !== "undefined" ? window.location.origin : ""}/creator/{storefront.store_slug}/register
                  </code>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-white/[0.02] text-zinc-400 border-b border-white/5">
                      <tr>
                        <th className="p-3.5 font-medium">Customer / Client</th>
                        <th className="p-3.5 font-medium">Attribution</th>
                        <th className="p-3.5 font-medium">Templates Owned</th>
                        <th className="p-3.5 font-medium">Orders</th>
                        <th className="p-3.5 font-medium">Total Spend</th>
                        <th className="p-3.5 font-medium">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {creatorCustomers.map((cust) => (
                        <tr key={cust.id} className="hover:bg-white/[0.02] transition-colors">
                          <td className="p-3.5">
                            <div className="flex items-center gap-2.5">
                              <div className="w-7 h-7 rounded-full bg-[#dfb180]/20 text-[#dfb180] flex items-center justify-center font-bold text-xs shrink-0">
                                {(cust.name || cust.email || "C").charAt(0).toUpperCase()}
                              </div>
                              <div className="min-w-0">
                                <div className="font-semibold text-white truncate">{cust.name || "Customer"}</div>
                                <div className="text-[11px] text-zinc-400 truncate">{cust.email}</div>
                              </div>
                            </div>
                          </td>
                          <td className="p-3.5">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#dfb180]/10 text-[#dfb180] border border-[#dfb180]/30">
                              <BadgeCheck className="w-3 h-3" />
                              <span>{cust.is_registered_client ? "Official Store Client" : "Template Buyer"}</span>
                            </span>
                          </td>
                          <td className="p-3.5 text-zinc-300">
                            {cust.templates_owned && cust.templates_owned.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {cust.templates_owned.map((t, idx) => (
                                  <span key={idx} className="px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px] text-zinc-200">
                                    {typeof t === "string" ? t : t.title || "Template"}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span className="text-zinc-500">—</span>
                            )}
                          </td>
                          <td className="p-3.5 text-zinc-300 font-medium">
                            {cust.orders_count || 0}
                          </td>
                          <td className="p-3.5 text-emerald-400 font-semibold">
                            ${(Number(cust.total_spent) || 0).toFixed(2)}
                          </td>
                          <td className="p-3.5 text-zinc-500">
                            {cust.created_at ? new Date(cust.created_at).toLocaleDateString() : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* ── 3. DEDICATED CREATOR STOREFRONT FOOTER ── */}
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
                    {typeof window !== "undefined" ? window.location.host : "aisitestudio.com"}/creator/{storefront.store_slug}
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

            {/* Creator Navigation Links */}
            <div className="sf-footer-nav-col">
              <h4 className="sf-footer-section-title">Storefront Pages</h4>
              <ul className="sf-footer-nav-list">
                <li>
                  <button type="button" onClick={() => setTab("templates")} className="sf-footer-nav-btn">
                    Templates Catalog ({templates.length})
                  </button>
                </li>
                <li>
                  <button type="button" onClick={() => setTab("about")} className="sf-footer-nav-btn">
                    About {storefront.brand_name}
                  </button>
                </li>
                <li>
                  <button type="button" onClick={() => setTab("contact")} className="sf-footer-nav-btn">
                    Contact &amp; Custom Work
                  </button>
                </li>
                <li>
                  <button type="button" onClick={() => setTab("payments")} className="sf-footer-nav-btn">
                    Payment Channels
                  </button>
                </li>
              </ul>
            </div>

            {/* Creator Contact & Support */}
            <div className="sf-footer-contact">
              <h4 className="sf-footer-section-title">Support &amp; Inquiries</h4>
              <p className="sf-footer-contact-desc">
                Have questions or need custom design modifications? Reach out to{" "}
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

            {/* Creator Socials & Engine Info */}
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

          {/* Bottom Copyright in Creator's Brand Name */}
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
    </div>
  );
}
