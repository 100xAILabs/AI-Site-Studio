"use client";

import { useState, useMemo, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
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
  paypal: { label: "PayPal", icon: DollarSign, color: "#38bdf8", desc: "PayPal.me & Direct Account" },
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
  const [copiedPaymentField, setCopiedPaymentField] = useState(null);

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
      document.title = `${storefront.brand_name} — Official Storefront`;
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
    if (storefront?.accepted_payment_methods && Array.isArray(storefront.accepted_payment_methods) && storefront.accepted_payment_methods.length > 0) {
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

  // Filter & Sort
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
    <div className="storefront-page">
      {/* ── 1. DEDICATED STOREFRONT NAVBAR IN CREATOR'S OWN BRAND ── */}
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
                {typeof window !== "undefined" ? window.location.host : "aisitestudio.com"}/creator/{storefront.store_slug}
              </span>
            </div>
          </Link>

          {/* Center Links */}
          <nav className="sf-nav-links">
            <a href="#catalog" className="sf-nav-link active">
              Templates ({templates.length})
            </a>
            {storefront.bio && (
              <a href="#about" className="sf-nav-link">
                About {storefront.brand_name}
              </a>
            )}
            {storefront.support_email && (
              <a href={`mailto:${storefront.support_email}`} className="sf-nav-link">
                Contact Creator
              </a>
            )}
          </nav>

          {/* Right Action Group */}
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

            {/* Jump to Marketplace Directory */}
            <Link to="/marketplace" className="sf-nav-mp-link" title="Explore Marketplace Directory">
              <span>Marketplace</span>
              <ExternalLink className="w-3 h-3 ml-1" />
            </Link>
          </div>
        </div>
      </header>

      <main className="storefront-main">
        {/* ── 2. CREATOR HERO BANNER SECTION ── */}
        <div className="storefront-hero">
          {storefront.banner_url && (
            <div
              className="storefront-hero-banner"
              style={{ backgroundImage: `url(${storefront.banner_url})` }}
            />
          )}
          <div className="storefront-hero-overlay" />

          <div className="storefront-hero-content">
            <div className="storefront-brand-row">
              {/* Creator Logo */}
              <div className="storefront-logo-wrap">
                {storefront.logo_url ? (
                  <img
                    src={storefront.logo_url}
                    alt={storefront.brand_name}
                    className="storefront-logo-img"
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                    }}
                  />
                ) : (
                  <div className="storefront-logo-fallback">
                    <Store className="w-10 h-10 text-[#dfb180]" />
                  </div>
                )}
                {storefront.is_verified && (
                  <div className="storefront-verified-badge" title="Verified Creator & Publisher">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  </div>
                )}
              </div>

              {/* Brand Meta */}
              <div className="storefront-brand-meta">
                <div className="storefront-domain-pill">
                  <Globe className="w-3.5 h-3.5 text-[#dfb180]" />
                  <span>
                    {typeof window !== "undefined" ? window.location.host : "aisitestudio.com"}
                    /creator/{storefront.store_slug}
                  </span>
                </div>

                <h1 className="storefront-brand-title">{storefront.brand_name}</h1>

                {/* Creator Name & Creator ID */}
                <div className="storefront-creator-identity-row">
                  {storefront.creator_name && (
                    <span className="storefront-creator-display">
                      <User className="w-3.5 h-3.5 text-zinc-400" />
                      Created by <strong>{storefront.creator_name}</strong>
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={handleCopyId}
                    className="storefront-creator-id-btn"
                    title="Click to copy Creator ID"
                  >
                    <span className="text-zinc-500 font-mono">ID:</span>
                    <span className="text-[#dfb180] font-mono">@{storefront.store_slug}</span>
                    {copiedId ? (
                      <Check className="w-3 h-3 text-emerald-400" />
                    ) : (
                      <Copy className="w-3 h-3 text-zinc-500" />
                    )}
                  </button>
                </div>

                {storefront.tagline && (
                  <p className="storefront-tagline">{storefront.tagline}</p>
                )}
              </div>

              {/* Share & Direct Email Action */}
              <div className="storefront-header-actions">
                {storefront.support_email && (
                  <a
                    href={`mailto:${storefront.support_email}`}
                    className="storefront-contact-btn"
                    title={`Send an email to ${storefront.support_email}`}
                  >
                    <Send className="w-3.5 h-3.5 mr-1.5" />
                    <span>Contact Creator</span>
                  </a>
                )}

                <button
                  type="button"
                  onClick={handleShare}
                  className="storefront-share-btn"
                  title="Share Storefront URL"
                >
                  {copiedLink ? (
                    <>
                      <Check className="w-4 h-4 text-emerald-400 mr-1.5" />
                      <span>Link Copied</span>
                    </>
                  ) : (
                    <>
                      <Share2 className="w-4 h-4 mr-1.5" />
                      <span>Share Storefront</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Creator Bio / Story Card */}
            {storefront.bio && (
              <div id="about" className="storefront-bio-wrap">
                <div className="storefront-bio-header">
                  <MessageSquare className="w-4 h-4 text-[#dfb180]" />
                  <span>About {storefront.brand_name}</span>
                </div>
                <p>{storefront.bio}</p>
              </div>
            )}

            {/* Creator Details Bar (Email ID, ID, Website, Socials) */}
            <div className="storefront-contact-bar">
              <div className="storefront-contact-items">
                {/* Official Email ID with one-click copy */}
                {storefront.support_email && (
                  <div className="sf-contact-chip">
                    <Mail className="w-4 h-4 text-[#dfb180] shrink-0" />
                    <div className="flex flex-col">
                      <span className="sf-chip-label">Direct Creator Email</span>
                      <a
                        href={`mailto:${storefront.support_email}`}
                        className="sf-chip-value hover:underline"
                      >
                        {storefront.support_email}
                      </a>
                    </div>
                    <button
                      type="button"
                      onClick={handleCopyEmail}
                      className="sf-chip-copy"
                      title="Copy email address"
                    >
                      {copiedEmail ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5 text-zinc-400" />
                      )}
                    </button>
                  </div>
                )}

                {/* Creator ID Chip */}
                <div className="sf-contact-chip">
                  <Store className="w-4 h-4 text-[#dfb180] shrink-0" />
                  <div className="flex flex-col">
                    <span className="sf-chip-label">Storefront ID</span>
                    <span className="sf-chip-value font-mono">@{storefront.store_slug}</span>
                  </div>
                </div>

                {/* Official Website */}
                {storefront.website && (
                  <a
                    href={storefront.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="sf-contact-chip sf-chip-link"
                    title="Visit Creator's Website"
                  >
                    <Globe className="w-4 h-4 text-blue-400 shrink-0" />
                    <div className="flex flex-col">
                      <span className="sf-chip-label">Official Website</span>
                      <span className="sf-chip-value truncate max-w-[180px]">
                        {storefront.website.replace(/^https?:\/\//, "")}
                      </span>
                    </div>
                    <ExternalLink className="w-3.5 h-3.5 text-zinc-500" />
                  </a>
                )}
              </div>

              {/* Socials Group */}
              <div className="storefront-socials-group">
                {storefront.social_links?.twitter && (
                  <a
                    href={storefront.social_links.twitter}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="sf-social-link"
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
                    className="sf-social-link"
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
                    className="sf-social-link"
                    title="LinkedIn"
                  >
                    <LinkedinIcon className="w-4 h-4" />
                  </a>
                )}
              </div>
            </div>

            {/* Stats Bar */}
            <div className="storefront-stats-bar">
              <div className="storefront-stats-group">
                <div className="sf-stat-item">
                  <span className="sf-stat-value">{storefront.stats?.total_templates || 0}</span>
                  <span className="sf-stat-label">Published Templates</span>
                </div>
                <div className="sf-stat-divider" />
                <div className="sf-stat-item">
                  <span className="sf-stat-value flex items-center gap-1">
                    <Star className="w-4 h-4 fill-amber-400 text-amber-400 inline" />
                    {Number(storefront.stats?.average_rating || 5.0).toFixed(1)}
                  </span>
                  <span className="sf-stat-label">
                    Rating ({storefront.stats?.reviews_count || 0})
                  </span>
                </div>
                <div className="sf-stat-divider" />
                <div className="sf-stat-item">
                  <span className="sf-stat-value">{storefront.stats?.total_sales || 0}+</span>
                  <span className="sf-stat-label">Happy Customers &amp; Sales</span>
                </div>
              </div>
            </div>

            {/* Accepted Creator Payments Banner */}
            {acceptedMethods.length > 0 && (
              <div className="storefront-payments-banner">
                <div className="sf-payments-banner-left">
                  <div className="sf-payments-title-row">
                    <CreditCard className="w-4 h-4 text-[#dfb180]" />
                    <span className="sf-payments-title">Accepted Payment Methods:</span>
                  </div>
                  <div className="sf-payments-chips">
                    {acceptedMethods.map((m) => {
                      const info = PAYMENT_METHOD_INFO[m] || { label: m, icon: Check };
                      const Icon = info.icon;
                      return (
                        <span key={m} className="sf-payment-chip" title={info.desc || info.label}>
                          <Icon className="w-3.5 h-3.5 text-[#dfb180]" />
                          <span>{info.label}</span>
                        </span>
                      );
                    })}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setShowPaymentModal(true)}
                  className="sf-payments-modal-btn"
                >
                  <Wallet className="w-4 h-4 mr-1.5" />
                  <span>View Details &amp; Direct Pay</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ── 3. FILTER & SEARCH BAR (OUR MARKETPLACE TEMPLATE ENGINE) ── */}
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

        {/* ── 4. TEMPLATE GRID (CREATOR'S OWN TEMPLATES ONLY) ── */}
        <div className="storefront-grid-section">
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

        {/* ── 5. STOREFRONT TRUST & ENGINE GUARANTEES ── */}
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

      {/* ── 6. DEDICATED CREATOR STOREFRONT FOOTER (IN THEIR NAME & ID) ── */}
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
              &copy; {new Date().getFullYear()} <strong>{storefront.brand_name}</strong>. All
              rights reserved.
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

      {/* ── 7. CREATOR PAYMENT METHODS & DIRECT PAY MODAL ── */}
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
                    Creator ID: @{storefront.store_slug} • Direct &amp; Platform Payments
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
                  <strong>{storefront.brand_name}</strong> supports multiple payment avenues for purchasing templates and custom work. You can use direct payment channels below or our unified cart checkout.
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
                          Stripe checkout available directly via Add to Cart &amp; Checkout on this storefront.
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
                        <span className="sf-method-sub">UPI, NetBanking, Cards (INR / Global)</span>
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

                {/* 3. PAYPAL */}
                {acceptedMethods.includes("paypal") && (
                  <div className="sf-method-card">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(56, 189, 248, 0.15)", color: "#38bdf8" }}>
                        <DollarSign className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">PayPal</h4>
                        <span className="sf-method-sub">PayPal.me, Balance &amp; Credit</span>
                      </div>
                      {paymentOptions.primary === "paypal" && (
                        <span className="sf-primary-badge">Primary</span>
                      )}
                    </div>
                    <div className="sf-method-card-content">
                      {paymentOptions.paypal?.paypal_me ? (
                        <a
                          href={paymentOptions.paypal.paypal_me.startsWith("http") ? paymentOptions.paypal.paypal_me : `https://${paymentOptions.paypal.paypal_me}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="sf-direct-pay-action-btn"
                        >
                          <span>Open PayPal.me Profile</span>
                          <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
                        </a>
                      ) : paymentOptions.paypal?.email ? (
                        <div className="sf-method-copy-box">
                          <span className="sf-method-field-label">Creator PayPal Email:</span>
                          <div className="sf-copy-row">
                            <code className="sf-copy-code">{paymentOptions.paypal.email}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("PayPal Email", paymentOptions.paypal.email)}
                              className="sf-copy-btn"
                            >
                              {copiedPaymentField === "PayPal Email" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="sf-method-info-text">Direct PayPal payments supported upon inquiry.</p>
                      )}
                    </div>
                  </div>
                )}

                {/* 4. DIRECT UPI */}
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
                              onClick={() => handleCopyPaymentInfo("UPI ID", paymentOptions.upi.vpa)}
                              className="sf-copy-btn"
                            >
                              {copiedPaymentField === "UPI ID" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                          <span className="sf-field-subhint">Zero platform fee • Instant bank settlement</span>
                        </div>
                      ) : (
                        <p className="sf-method-info-text">UPI accepted via Razorpay gateway at checkout.</p>
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
                        <span className="sf-method-sub">
                          {paymentOptions.crypto?.currency || "USDT"} ({paymentOptions.crypto?.network || "TRC20"})
                        </span>
                      </div>
                      {paymentOptions.primary === "crypto" && (
                        <span className="sf-primary-badge">Primary</span>
                      )}
                    </div>
                    <div className="sf-method-card-content">
                      {paymentOptions.crypto?.address ? (
                        <div className="sf-method-copy-box">
                          <span className="sf-method-field-label">
                            Deposit Address ({paymentOptions.crypto.currency} - {paymentOptions.crypto.network}):
                          </span>
                          <div className="sf-copy-row">
                            <code className="sf-copy-code truncate">{paymentOptions.crypto.address}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("Crypto Address", paymentOptions.crypto.address)}
                              className="sf-copy-btn"
                            >
                              {copiedPaymentField === "Crypto Address" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                          <span className="sf-field-subhint text-amber-400">
                            Send only {paymentOptions.crypto.currency} via {paymentOptions.crypto.network} network.
                          </span>
                        </div>
                      ) : (
                        <p className="sf-method-info-text">Crypto wallet details available on request.</p>
                      )}
                    </div>
                  </div>
                )}

                {/* 6. BANK WIRE */}
                {(acceptedMethods.includes("bank") || acceptedMethods.includes("bank_wire")) && (
                  <div className="sf-method-card sf-method-card-wide">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(96, 165, 250, 0.15)", color: "#60a5fa" }}>
                        <Building2 className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">Bank Wire / SWIFT / IBAN</h4>
                        <span className="sf-method-sub">Direct Account Deposit</span>
                      </div>
                      {paymentOptions.primary === "bank" && (
                        <span className="sf-primary-badge">Primary</span>
                      )}
                    </div>
                    <div className="sf-method-card-content sf-bank-grid">
                      {paymentOptions.bank_transfer?.bank_name && (
                        <div className="sf-bank-field">
                          <span className="sf-bank-label">Bank Name</span>
                          <span className="sf-bank-val">{paymentOptions.bank_transfer.bank_name}</span>
                        </div>
                      )}
                      {paymentOptions.bank_transfer?.account_holder_name && (
                        <div className="sf-bank-field">
                          <span className="sf-bank-label">Account Holder</span>
                          <span className="sf-bank-val">{paymentOptions.bank_transfer.account_holder_name}</span>
                        </div>
                      )}
                      {paymentOptions.bank_transfer?.ifsc_code && (
                        <div className="sf-bank-field">
                          <span className="sf-bank-label">IFSC Code</span>
                          <div className="flex items-center gap-1.5">
                            <code className="sf-copy-code">{paymentOptions.bank_transfer.ifsc_code}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("IFSC Code", paymentOptions.bank_transfer.ifsc_code)}
                              className="sf-copy-btn-sm"
                            >
                              {copiedPaymentField === "IFSC Code" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                            </button>
                          </div>
                        </div>
                      )}
                      {paymentOptions.bank_transfer?.swift_code && (
                        <div className="sf-bank-field">
                          <span className="sf-bank-label">SWIFT / BIC</span>
                          <div className="flex items-center gap-1.5">
                            <code className="sf-copy-code">{paymentOptions.bank_transfer.swift_code}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("SWIFT Code", paymentOptions.bank_transfer.swift_code)}
                              className="sf-copy-btn-sm"
                            >
                              {copiedPaymentField === "SWIFT Code" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                            </button>
                          </div>
                        </div>
                      )}
                      {paymentOptions.bank_transfer?.iban && (
                        <div className="sf-bank-field">
                          <span className="sf-bank-label">IBAN</span>
                          <div className="flex items-center gap-1.5">
                            <code className="sf-copy-code">{paymentOptions.bank_transfer.iban}</code>
                            <button
                              type="button"
                              onClick={() => handleCopyPaymentInfo("IBAN", paymentOptions.bank_transfer.iban)}
                              className="sf-copy-btn-sm"
                            >
                              {copiedPaymentField === "IBAN" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 7. WISE */}
                {acceptedMethods.includes("wise") && paymentOptions.wise?.email && (
                  <div className="sf-method-card">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(159, 232, 112, 0.15)", color: "#9fe870" }}>
                        <Send className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">Wise (TransferWise)</h4>
                        <span className="sf-method-sub">Multi-currency International Transfer</span>
                      </div>
                    </div>
                    <div className="sf-method-card-content">
                      <div className="sf-copy-row">
                        <code className="sf-copy-code">{paymentOptions.wise.email}</code>
                        <button
                          type="button"
                          onClick={() => handleCopyPaymentInfo("Wise Email", paymentOptions.wise.email)}
                          className="sf-copy-btn"
                        >
                          {copiedPaymentField === "Wise Email" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* 8. REVOLUT */}
                {acceptedMethods.includes("revolut") && paymentOptions.revolut?.tag && (
                  <div className="sf-method-card">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(0, 117, 235, 0.15)", color: "#0075eb" }}>
                        <CreditCard className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">Revolut</h4>
                        <span className="sf-method-sub">Direct Revtag Transfer</span>
                      </div>
                    </div>
                    <div className="sf-method-card-content">
                      <div className="sf-copy-row">
                        <code className="sf-copy-code">@{paymentOptions.revolut.tag.replace(/^@/, "")}</code>
                        <button
                          type="button"
                          onClick={() => handleCopyPaymentInfo("Revolut Tag", paymentOptions.revolut.tag)}
                          className="sf-copy-btn"
                        >
                          {copiedPaymentField === "Revolut Tag" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* 9. CASH APP / VENMO */}
                {acceptedMethods.includes("cashapp") && (paymentOptions.cashapp?.tag || paymentOptions.venmo?.tag) && (
                  <div className="sf-method-card">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(0, 214, 50, 0.15)", color: "#00d632" }}>
                        <DollarSign className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">Cash App / Venmo</h4>
                        <span className="sf-method-sub">US Peer-to-Peer</span>
                      </div>
                    </div>
                    <div className="sf-method-card-content">
                      {paymentOptions.cashapp?.tag && (
                        <div className="sf-copy-row mb-2">
                          <span className="text-xs text-zinc-400 mr-2">Cash App:</span>
                          <code className="sf-copy-code">${paymentOptions.cashapp.tag.replace(/^\$/, "")}</code>
                          <button
                            type="button"
                            onClick={() => handleCopyPaymentInfo("Cash App", paymentOptions.cashapp.tag)}
                            className="sf-copy-btn"
                          >
                            {copiedPaymentField === "Cash App" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      )}
                      {paymentOptions.venmo?.tag && (
                        <div className="sf-copy-row">
                          <span className="text-xs text-zinc-400 mr-2">Venmo:</span>
                          <code className="sf-copy-code">@{paymentOptions.venmo.tag.replace(/^@/, "")}</code>
                          <button
                            type="button"
                            onClick={() => handleCopyPaymentInfo("Venmo", paymentOptions.venmo.tag)}
                            className="sf-copy-btn"
                          >
                            {copiedPaymentField === "Venmo" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 10. CUSTOM INSTRUCTIONS */}
                {(acceptedMethods.includes("custom") || paymentOptions.custom_instructions) && paymentOptions.custom_instructions && (
                  <div className="sf-method-card sf-method-card-wide">
                    <div className="sf-method-card-header">
                      <div className="sf-method-icon-box" style={{ background: "rgba(223, 177, 128, 0.15)", color: "#dfb180" }}>
                        <SlidersHorizontal className="w-5 h-5" />
                      </div>
                      <div className="sf-method-meta">
                        <h4 className="sf-method-name">Custom Payment Instructions</h4>
                        <span className="sf-method-sub">Direct terms from {storefront.brand_name}</span>
                      </div>
                    </div>
                    <div className="sf-method-card-content">
                      <div className="sf-custom-instructions-box">
                        <p>{paymentOptions.custom_instructions}</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Platform Unified Checkout Banner */}
              <div className="sf-modal-platform-checkout">
                <div className="sf-mpc-left">
                  <ShoppingCart className="w-5 h-5 text-[#dfb180] shrink-0" />
                  <div>
                    <h5 className="sf-mpc-title">Standard Automated Checkout</h5>
                    <p className="sf-mpc-desc">
                      Add any template to cart and check out securely via Stripe or Razorpay with instant zip download &amp; license generation.
                    </p>
                  </div>
                </div>
                <Link
                  to="/checkout"
                  onClick={() => setShowPaymentModal(false)}
                  className="sf-mpc-btn"
                >
                  <span>Go to Checkout</span>
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
