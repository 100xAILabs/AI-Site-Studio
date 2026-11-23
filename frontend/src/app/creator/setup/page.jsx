"use client";

import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Sparkles,
  ShoppingBag,
  Store,
  Crown,
  CreditCard,
  DollarSign,
  Globe,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowRight,
  ExternalLink,
  Copy,
  Check,
  Building2,
  Mail,
  User,
  ShieldCheck,
  ChevronRight,
  Zap,
  Layers,
  ArrowLeft,
  Share2,
  Coins,
  Smartphone,
  Wallet,
  FileText,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import { useAppUser } from "@/lib/auth";
import { api } from "@/lib/api";
import { toast } from "sonner";
import "./Page.css";

const PAYOUT_METHODS = [
  {
    id: "stripe",
    name: "Stripe Connect",
    badge: "Cards, Apple Pay, SEPA",
    desc: "Receive direct payouts in 135+ currencies with low platform fees.",
    icon: CreditCard,
    color: "#635bff",
  },
  {
    id: "razorpay",
    name: "Razorpay",
    badge: "UPI, Netbanking, Cards",
    desc: "Instant settlements across India and APAC via UPI & NetBanking.",
    icon: Zap,
    color: "#0c2340",
  },
  {
    id: "upi",
    name: "UPI (GPay / PhonePe / Paytm)",
    badge: "Zero-Fee Instant VPA",
    desc: "Instant peer-to-merchant settlements directly to your UPI ID.",
    icon: Smartphone,
    color: "#16a34a",
  },
  {
    id: "bank",
    name: "Direct Bank Wire / NEFT",
    badge: "SWIFT / IBAN / ACH",
    desc: "Direct deposit to your business or personal bank account worldwide.",
    icon: Building2,
    color: "#10b981",
  },
  {
    id: "crypto",
    name: "Crypto / Web3",
    badge: "USDT / BTC / ETH",
    desc: "Direct wallet payouts in USDT (TRC-20/ERC-20), Bitcoin, or Ethereum.",
    icon: Coins,
    color: "#f59e0b",
  },
  {
    id: "wise",
    name: "Wise / TransferWise",
    badge: "Low-Fee Multi-Currency",
    desc: "Receive international payouts directly to your Wise account email or tag.",
    icon: Globe,
    color: "#22c55e",
  },
  {
    id: "revolut",
    name: "Revolut",
    badge: "Instant European",
    desc: "Direct settlements to your Revolut.me username or Revtag.",
    icon: Wallet,
    color: "#3b82f6",
  },
  {
    id: "cashapp",
    name: "Cash App / Venmo",
    badge: "US Mobile Payouts",
    desc: "Direct payouts to your verified $cashtag or @venmo handle.",
    icon: DollarSign,
    color: "#00d632",
  },
  {
    id: "paystack",
    name: "Paystack / Flutterwave",
    badge: "African & Emerging",
    desc: "Accept payments across Nigeria, Kenya, Ghana, South Africa & emerging markets.",
    icon: Layers,
    color: "#00c3f7",
  },
  {
    id: "custom",
    name: "Custom Payout Instructions",
    badge: "Flexible Terms",
    desc: "Custom instructions, offline terms, or direct directions displayed to buyers.",
    icon: FileText,
    color: "#8b5cf6",
  },
];

const DISTRIBUTION_OPTIONS = [
  {
    id: "both",
    title: "Dual Distribution (Recommended)",
    badge: "Maximum Reach",
    desc: "Sell in our Global Marketplace directory AND on your dedicated branded storefront on our domain.",
    highlight: true,
  },
  {
    id: "storefront",
    title: "My Dedicated Storefront Only",
    badge: "Private Collection on Our Domain",
    desc: "Sell exclusively at aisitestudio.com/creator/{slug}. Excluded from global marketplace searches for complete brand exclusivity.",
    highlight: false,
  },
  {
    id: "marketplace",
    title: "Global Marketplace Only",
    badge: "Public Discovery",
    desc: "List your AI-generated websites directly in the main marketplace directory alongside all other creators.",
    highlight: false,
  },
];

export default function CreatorSetupPage() {
  const navigate = useNavigate();
  const { user, isSignedIn, isLoaded } = useAppUser();

  const isExtreme =
    Boolean(user?.can_retail_templates) ||
    Boolean(user?.is_extreme_subscriber) ||
    ["extreme", "agency", "enterprise"].includes(
      String(user?.subscription_tier || "").toLowerCase()
    ) ||
    user?.role === "admin" ||
    user?.role === "super_admin";

  const [isLoadingProfile, setIsLoadingProfile] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [successData, setSuccessData] = useState(null);

  // Form State
  const [brandName, setBrandName] = useState("");
  const [creatorName, setCreatorName] = useState("");
  const [storeSlug, setStoreSlug] = useState("");
  const [tagline, setTagline] = useState("");
  const [bio, setBio] = useState("");
  const [supportEmail, setSupportEmail] = useState("");
  const [website, setWebsite] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [bannerUrl, setBannerUrl] = useState("");
  const [twitterUrl, setTwitterUrl] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");

  // Payout State - Multi-Gateway & Primary Choice
  const [enabledMethods, setEnabledMethods] = useState(["stripe", "razorpay"]);
  const [payoutMethod, setPayoutMethod] = useState("stripe");
  
  // Gateway Detail Fields
  const [stripeEmail, setStripeEmail] = useState("");
  const [stripeAccountId, setStripeAccountId] = useState("");
  const [stripePaymentLink, setStripePaymentLink] = useState("");

  const [razorpayVpa, setRazorpayVpa] = useState("");
  const [razorpayAccountId, setRazorpayAccountId] = useState("");

  const [upiId, setUpiId] = useState("");

  const [bankName, setBankName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [accountHolder, setAccountHolder] = useState("");
  const [ifscCode, setIfscCode] = useState("");
  const [swiftCode, setSwiftCode] = useState("");
  const [iban, setIban] = useState("");

  const [cryptoCurrency, setCryptoCurrency] = useState("USDT");
  const [cryptoNetwork, setCryptoNetwork] = useState("TRC20");
  const [cryptoAddress, setCryptoAddress] = useState("");

  const [wiseEmail, setWiseEmail] = useState("");
  const [revolutTag, setRevolutTag] = useState("");
  const [cashappTag, setCashappTag] = useState("");
  const [venmoTag, setVenmoTag] = useState("");
  const [flutterwaveId, setFlutterwaveId] = useState("");
  const [paystackCode, setPaystackCode] = useState("");
  const [customInstructions, setCustomInstructions] = useState("");

  const toggleMethod = (id) => {
    setEnabledMethods((prev) => {
      const exists = prev.includes(id);
      if (exists) {
        if (prev.length === 1) {
          toast.warning("You must enable at least one payment method for your customers.");
          return prev;
        }
        const updated = prev.filter((m) => m !== id);
        if (payoutMethod === id) {
          setPayoutMethod(updated[0]);
        }
        return updated;
      } else {
        return [...prev, id];
      }
    });
  };

  // Distribution State
  const [storefrontDistribution, setStorefrontDistribution] = useState("both");

  // Slug check
  const [slugChecking, setSlugChecking] = useState(false);
  const [slugAvailable, setSlugAvailable] = useState(null);
  const [slugReason, setSlugReason] = useState("");

  // Load existing creator profile
  useEffect(() => {
    async function loadProfile() {
      if (!isSignedIn) {
        setIsLoadingProfile(false);
        return;
      }
      try {
        const data = await api.get("/creator/profile");
        if (data) {
          if (data.creator_brand_name) setBrandName(data.creator_brand_name);
          if (data.full_name) setCreatorName(data.full_name);
          if (data.creator_store_slug) {
            setStoreSlug(data.creator_store_slug);
            setSlugAvailable(true);
          }
          if (data.creator_tagline) setTagline(data.creator_tagline);
          if (data.creator_bio) setBio(data.creator_bio);
          if (data.creator_support_email) setSupportEmail(data.creator_support_email);
          if (data.creator_website) setWebsite(data.creator_website);
          if (data.creator_logo_url) setLogoUrl(data.creator_logo_url);
          if (data.creator_banner_url) setBannerUrl(data.creator_banner_url);
          if (data.payout_method) setPayoutMethod(data.payout_method);
          if (data.enabled_payment_methods && Array.isArray(data.enabled_payment_methods) && data.enabled_payment_methods.length > 0) {
            setEnabledMethods(data.enabled_payment_methods);
          } else if (data.payout_method) {
            setEnabledMethods([data.payout_method]);
          }

          if (data.payout_stripe_email) setStripeEmail(data.payout_stripe_email);
          if (data.payout_stripe_account_id) setStripeAccountId(data.payout_stripe_account_id);
          if (data.payout_stripe_payment_link) setStripePaymentLink(data.payout_stripe_payment_link);

          if (data.payout_razorpay_vpa) setRazorpayVpa(data.payout_razorpay_vpa);
          if (data.payout_razorpay_account_id) setRazorpayAccountId(data.payout_razorpay_account_id);

          if (data.payout_upi_id) setUpiId(data.payout_upi_id);

          if (data.payout_bank_name) setBankName(data.payout_bank_name);
          if (data.payout_ifsc_code) setIfscCode(data.payout_ifsc_code);
          if (data.payout_swift_code) setSwiftCode(data.payout_swift_code);
          if (data.payout_iban) setIban(data.payout_iban);
          if (data.payout_account_holder_name) setAccountHolder(data.payout_account_holder_name);

          if (data.payout_crypto_currency) setCryptoCurrency(data.payout_crypto_currency);
          if (data.payout_crypto_network) setCryptoNetwork(data.payout_crypto_network);
          if (data.payout_crypto_address) setCryptoAddress(data.payout_crypto_address);

          if (data.payout_wise_email) setWiseEmail(data.payout_wise_email);
          if (data.payout_revolut_tag) setRevolutTag(data.payout_revolut_tag);
          if (data.payout_cashapp_tag) setCashappTag(data.payout_cashapp_tag);
          if (data.payout_venmo_tag) setVenmoTag(data.payout_venmo_tag);
          if (data.payout_flutterwave_id) setFlutterwaveId(data.payout_flutterwave_id);
          if (data.payout_paystack_code) setPaystackCode(data.payout_paystack_code);
          if (data.payout_custom_instructions) setCustomInstructions(data.payout_custom_instructions);

          if (data.storefront_distribution) setStorefrontDistribution(data.storefront_distribution);

          if (data.creator_social_links) {
            setTwitterUrl(data.creator_social_links.twitter || "");
            setGithubUrl(data.creator_social_links.github || "");
            setLinkedinUrl(data.creator_social_links.linkedin || "");
          }
        }
      } catch (err) {
        // Fallback to user object defaults
        if (user) {
          setCreatorName(user.full_name || user.username || "");
          setSupportEmail(user.email || "");
          if (user.username) {
            const clean = user.username.toLowerCase().replace(/[^a-z0-9]/g, "-").replace(/-+/g, "-");
            setStoreSlug(clean);
          }
        }
      } finally {
        setIsLoadingProfile(false);
      }
    }
    loadProfile();
  }, [isSignedIn, user]);

  // Debounced slug check
  useEffect(() => {
    if (!storeSlug || storeSlug.length < 3) {
      setSlugAvailable(null);
      setSlugReason("");
      return;
    }
    const timer = setTimeout(async () => {
      setSlugChecking(true);
      try {
        const res = await api.get(`/creator/check-slug?slug=${encodeURIComponent(storeSlug)}`);
        setSlugAvailable(res.available);
        setSlugReason(res.reason || "");
      } catch (e) {
        setSlugAvailable(null);
      } finally {
        setSlugChecking(false);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [storeSlug]);

  const handleBrandNameChange = (val) => {
    setBrandName(val);
    if (!storeSlug || storeSlug === brandName.toLowerCase().replace(/[^a-z0-9]/g, "-")) {
      const generated = val
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 40);
      setStoreSlug(generated);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!brandName.trim()) {
      toast.error("Please enter your Studio or Brand Name");
      return;
    }

    if (!storeSlug.trim() || storeSlug.length < 3) {
      toast.error("Please enter a valid storefront URL slug (at least 3 characters)");
      return;
    }

    if (slugAvailable === false) {
      toast.error(slugReason || "This storefront slug is not available. Please choose another.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        brand_name: brandName.trim(),
        creator_name: creatorName.trim() || null,
        store_slug: storeSlug.trim().toLowerCase(),
        tagline: tagline.trim() || null,
        bio: bio.trim() || null,
        support_email: supportEmail.trim() || null,
        website: website.trim() || null,
        logo_url: logoUrl.trim() || null,
        banner_url: bannerUrl.trim() || null,
        social_links: {
          twitter: twitterUrl.trim() || undefined,
          github: githubUrl.trim() || undefined,
          linkedin: linkedinUrl.trim() || undefined,
        },
        payout_method: payoutMethod,
        enabled_payment_methods: enabledMethods,
        payout_stripe_email: stripeEmail.trim() || null,
        payout_stripe_account_id: stripeAccountId.trim() || null,
        payout_stripe_payment_link: stripePaymentLink.trim() || null,
        payout_razorpay_vpa: razorpayVpa.trim() || null,
        payout_razorpay_account_id: razorpayAccountId.trim() || null,
        payout_upi_id: upiId.trim() || null,
        payout_bank_name: bankName.trim() || null,
        payout_account_number: accountNumber.trim() || null,
        payout_ifsc_code: ifscCode.trim() || null,
        payout_swift_code: swiftCode.trim() || null,
        payout_iban: iban.trim() || null,
        payout_account_holder_name: accountHolder.trim() || null,
        payout_crypto_currency: cryptoCurrency.trim() || "USDT",
        payout_crypto_network: cryptoNetwork.trim() || "TRC20",
        payout_crypto_address: cryptoAddress.trim() || null,
        payout_wise_email: wiseEmail.trim() || null,
        payout_revolut_tag: revolutTag.trim() || null,
        payout_cashapp_tag: cashappTag.trim() || null,
        payout_venmo_tag: venmoTag.trim() || null,
        payout_flutterwave_id: flutterwaveId.trim() || null,
        payout_paystack_code: paystackCode.trim() || null,
        payout_custom_instructions: customInstructions.trim() || null,
        storefront_distribution: storefrontDistribution,
      };

      const res = await api.put("/creator/profile", payload);
      toast.success("Creator Storefront & Payout Settings Saved!");
      setSuccessData(res);
    } catch (err) {
      toast.error(err.message || "Failed to update creator profile.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyStorefrontLink = () => {
    const origin = typeof window !== "undefined" ? window.location.origin : "https://aisitestudio.com";
    const fullUrl = `${origin}/creator/${storeSlug}`;
    navigator.clipboard.writeText(fullUrl);
    setCopiedLink(true);
    toast.success("Storefront link copied to clipboard!");
    setTimeout(() => setCopiedLink(false), 2500);
  };

  if (!isLoaded || isLoadingProfile) {
    return (
      <div className="creator-setup-page">
        <Navbar />
        <div className="creator-loading-state">
          <Loader2 className="w-10 h-10 animate-spin text-[#dfb180]" />
          <p>Loading creator profile...</p>
        </div>
        <Footer />
      </div>
    );
  }

  return (
    <div className="creator-setup-page">
      <Navbar />

      <main className="creator-setup-container">
        {/* Breadcrumb Navigation */}
        <div className="creator-breadcrumb">
          <Link to="/marketplace" className="creator-crumb-link">
            Marketplace
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
          <Link to="/dashboard?tab=creator-studio" className="creator-crumb-link">
            Creator Studio
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
          <span className="creator-crumb-current">Storefront Setup</span>
        </div>

        {/* ── CASE 1: NON-EXTREME USER UPGRADE GATE ── */}
        {!isExtreme ? (
          <div className="creator-gate-card">
            <div className="creator-gate-header">
              <div className="creator-gate-badge">
                <Crown className="w-4 h-4 text-amber-400" />
                <span>Extreme Plan Exclusive</span>
              </div>
              <h1 className="creator-gate-title">
                Launch Your Dedicated Storefront <br />
                on Our Domain
              </h1>
              <p className="creator-gate-subtitle">
                Selling templates under your brand with your custom storefront on our domain
                is an exclusive privilege of the <strong>Extreme Plan ($50/mo)</strong>.
              </p>
            </div>

            <div className="creator-perks-grid">
              <div className="creator-perk-card">
                <div className="creator-perk-icon-wrap">
                  <Store className="w-6 h-6 text-amber-400" />
                </div>
                <h3>Your Own Storefront on Our Domain</h3>
                <p>
                  Host your branded storefront at{" "}
                  <code>aisitestudio.com/creator/your-brand</code>. Powered by our high-performance
                  marketplace engine, responsive viewports, and interactive live demos.
                </p>
              </div>

              <div className="creator-perk-card">
                <div className="creator-perk-icon-wrap">
                  <CreditCard className="w-6 h-6 text-emerald-400" />
                </div>
                <h3>Multi-Gateway Payouts</h3>
                <p>
                  Get paid however you prefer. Receive earnings directly via Stripe, Razorpay
                  (UPI/Netbanking), or direct Bank Wire Transfer.
                </p>
              </div>

              <div className="creator-perk-card">
                <div className="creator-perk-icon-wrap">
                  <Globe className="w-6 h-6 text-blue-400" />
                </div>
                <h3>Distribution Freedom</h3>
                <p>
                  Choose where to sell: in our Global Marketplace directory, exclusively on your
                  dedicated storefront on our domain, or both for maximum reach!
                </p>
              </div>

              <div className="creator-perk-card">
                <div className="creator-perk-icon-wrap">
                  <ShoppingBag className="w-6 h-6 text-purple-400" />
                </div>
                <h3>Retail AI-Generated Websites</h3>
                <p>
                  Generate full-stack, responsive websites with the AI Studio and retail them as
                  commercial products at your own prices ($19 - $499+).
                </p>
              </div>
            </div>

            <div className="creator-gate-actions">
              <button
                type="button"
                onClick={() => navigate("/pricing")}
                className="creator-btn-upgrade"
              >
                <Crown className="w-4 h-4 mr-2" />
                <span>Upgrade to Extreme Plan ($50/mo)</span>
                <ArrowRight className="w-4 h-4 ml-2" />
              </button>
              <Link to="/marketplace" className="creator-btn-secondary">
                Explore Marketplace First
              </Link>
            </div>
          </div>
        ) : successData ? (
          /* ── CASE 2: SUCCESS STATE AFTER SAVING ── */
          <div className="creator-success-card">
            <div className="creator-success-icon-wrap">
              <CheckCircle2 className="w-12 h-12 text-emerald-400" />
            </div>
            <h2 className="creator-success-title">Your Storefront is Configured!</h2>
            <p className="creator-success-desc">
              Your branded storefront is now live on our domain. Customers can browse your
              templates, experience live interactive demos, and make instant purchases.
            </p>

            <div className="creator-url-banner">
              <div className="creator-url-info">
                <span className="creator-url-label">Your Live Storefront URL</span>
                <div className="creator-url-display">
                  <Globe className="w-4 h-4 text-[#dfb180] shrink-0" />
                  <span className="creator-url-text">
                    {typeof window !== "undefined" ? window.location.origin : "https://aisitestudio.com"}
                    /creator/{successData.creator_store_slug || storeSlug}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={copyStorefrontLink}
                className="creator-copy-btn"
                title="Copy Storefront Link"
              >
                {copiedLink ? (
                  <>
                    <Check className="w-4 h-4 text-emerald-400 mr-1" />
                    <span>Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4 mr-1" />
                    <span>Copy Link</span>
                  </>
                )}
              </button>
            </div>

            <div className="creator-success-actions">
              <Link
                to={`/creator/${successData.creator_store_slug || storeSlug}`}
                className="creator-btn-primary"
              >
                <Store className="w-4 h-4 mr-2" />
                <span>Visit My Storefront</span>
                <ExternalLink className="w-4 h-4 ml-1.5" />
              </Link>
              <Link to="/dashboard?tab=creator-studio" className="creator-btn-secondary">
                <ShoppingBag className="w-4 h-4 mr-2" />
                <span>Go to Creator Studio to Sell Templates</span>
              </Link>
              <button
                type="button"
                onClick={() => setSuccessData(null)}
                className="creator-btn-text"
              >
                Edit Setup Again
              </button>
            </div>
          </div>
        ) : (
          /* ── CASE 3: EXTREME CREATOR QUESTIONNAIRE FORM ── */
          <form onSubmit={handleSubmit} className="creator-form-wrap">
            {/* Header */}
            <div className="creator-header">
              <div className="creator-badge">
                <Sparkles className="w-3.5 h-3.5 text-[#dfb180]" />
                <span>Extreme Creator Portal</span>
              </div>
              <h1 className="creator-title">Creator Storefront &amp; Payout Setup</h1>
              <p className="creator-subtitle">
                Configure your brand identity, dedicated storefront on our domain, and select your
                preferred payout gateway to start selling your AI-generated websites.
              </p>
            </div>

            {/* ── SECTION 1: BRANDING & CREATOR IDENTITY ── */}
            <div className="creator-card">
              <div className="creator-card-header">
                <div className="creator-step-badge">Step 1</div>
                <div>
                  <h3 className="creator-card-title">Brand &amp; Creator Identity</h3>
                  <p className="creator-card-desc">
                    How you and your studio will appear on our domain and to customers.
                  </p>
                </div>
              </div>

              <div className="creator-grid-2">
                <div className="creator-field">
                  <label className="creator-label">
                    Studio / Branding Name <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Apex Digital Studios, Velox Themes"
                    value={brandName}
                    onChange={(e) => handleBrandNameChange(e.target.value)}
                    className="creator-input"
                  />
                  <span className="creator-field-hint">
                    This will be the headline brand on your storefront and template cards.
                  </span>
                </div>

                <div className="creator-field">
                  <label className="creator-label">Creator's Name (Display Name)</label>
                  <input
                    type="text"
                    placeholder="e.g. Alex Morgan"
                    value={creatorName}
                    onChange={(e) => setCreatorName(e.target.value)}
                    className="creator-input"
                  />
                  <span className="creator-field-hint">Your personal creator display name.</span>
                </div>
              </div>

              {/* Dedicated Storefront URL on our domain */}
              <div className="creator-field">
                <label className="creator-label">
                  Your Dedicated Storefront URL on Our Domain{" "}
                  <span className="text-rose-400">*</span>
                </label>
                <div className="creator-slug-input-wrap">
                  <span className="creator-slug-prefix">
                    {typeof window !== "undefined"
                      ? window.location.host
                      : "aisitestudio.com"}
                    /creator/
                  </span>
                  <input
                    type="text"
                    required
                    placeholder="your-brand-slug"
                    value={storeSlug}
                    onChange={(e) =>
                      setStoreSlug(
                        e.target.value
                          .toLowerCase()
                          .replace(/[^a-z0-9-]/g, "")
                      )
                    }
                    className="creator-slug-input"
                  />
                  <div className="creator-slug-status">
                    {slugChecking ? (
                      <span className="creator-status-pill checking">
                        <Loader2 className="w-3 h-3 animate-spin mr-1" /> Checking
                      </span>
                    ) : slugAvailable === true ? (
                      <span className="creator-status-pill available">
                        <Check className="w-3 h-3 mr-1 text-emerald-400" /> Available
                      </span>
                    ) : slugAvailable === false ? (
                      <span className="creator-status-pill taken">
                        <AlertCircle className="w-3 h-3 mr-1 text-rose-400" /> Taken
                      </span>
                    ) : null}
                  </div>
                </div>
                {slugReason && <span className="creator-field-error">{slugReason}</span>}
                <span className="creator-field-hint">
                  Your storefront will be hosted directly on our domain at this custom slug.
                </span>
              </div>

              <div className="creator-field">
                <label className="creator-label">Tagline / Motto</label>
                <input
                  type="text"
                  placeholder="e.g. Next-generation production-ready templates for SaaS &amp; E-commerce"
                  value={tagline}
                  onChange={(e) => setTagline(e.target.value)}
                  className="creator-input"
                />
              </div>

              <div className="creator-field">
                <label className="creator-label">Bio / Studio Story</label>
                <textarea
                  rows={3}
                  placeholder="Tell buyers about your design philosophy, specialties, and the experience behind your websites..."
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  className="creator-textarea"
                />
              </div>

              <div className="creator-grid-2">
                <div className="creator-field">
                  <label className="creator-label">Support / Contact Email</label>
                  <input
                    type="email"
                    placeholder="support@yourstudio.com"
                    value={supportEmail}
                    onChange={(e) => setSupportEmail(e.target.value)}
                    className="creator-input"
                  />
                </div>
                <div className="creator-field">
                  <label className="creator-label">Official Website / Portfolio</label>
                  <input
                    type="url"
                    placeholder="https://yourbrand.com"
                    value={website}
                    onChange={(e) => setWebsite(e.target.value)}
                    className="creator-input"
                  />
                </div>
              </div>

              <div className="creator-grid-2">
                <div className="creator-field">
                  <label className="creator-label">Brand Logo Image URL</label>
                  <input
                    type="url"
                    placeholder="https://.../logo.png"
                    value={logoUrl}
                    onChange={(e) => setLogoUrl(e.target.value)}
                    className="creator-input"
                  />
                  {logoUrl && (
                    <div className="creator-preview-logo">
                      <img
                        src={logoUrl}
                        alt="Logo Preview"
                        onError={(e) => (e.currentTarget.style.display = "none")}
                      />
                      <span>Logo Preview</span>
                    </div>
                  )}
                </div>
                <div className="creator-field">
                  <label className="creator-label">Hero Banner Image URL</label>
                  <input
                    type="url"
                    placeholder="https://.../banner.jpg"
                    value={bannerUrl}
                    onChange={(e) => setBannerUrl(e.target.value)}
                    className="creator-input"
                  />
                </div>
              </div>

              {/* Social links */}
              <div className="creator-field">
                <label className="creator-label">Social Handles (Optional)</label>
                <div className="creator-grid-3">
                  <input
                    type="text"
                    placeholder="Twitter/X profile URL"
                    value={twitterUrl}
                    onChange={(e) => setTwitterUrl(e.target.value)}
                    className="creator-input"
                  />
                  <input
                    type="text"
                    placeholder="GitHub profile URL"
                    value={githubUrl}
                    onChange={(e) => setGithubUrl(e.target.value)}
                    className="creator-input"
                  />
                  <input
                    type="text"
                    placeholder="LinkedIn profile URL"
                    value={linkedinUrl}
                    onChange={(e) => setLinkedinUrl(e.target.value)}
                    className="creator-input"
                  />
                </div>
              </div>
            </div>

            {/* ── SECTION 2: PAYMENT SECTION ── */}
            <div className="creator-card">
              <div className="creator-card-header">
                <div className="creator-step-badge">Step 2</div>
                <div>
                  <h3 className="creator-card-title">Payment Gateways &amp; Payout Methods</h3>
                  <p className="creator-card-desc">
                    Choose which payment methods you want to accept from your buyers. You can enable multiple methods for your customers and set your primary payout gateway!
                  </p>
                </div>
              </div>

              {/* Payment Method Cards */}
              <div className="creator-payment-grid">
                {PAYOUT_METHODS.map((method) => {
                  const Icon = method.icon;
                  const isEnabled = enabledMethods.includes(method.id);
                  const isPrimary = payoutMethod === method.id;
                  return (
                    <div
                      key={method.id}
                      onClick={() => toggleMethod(method.id)}
                      className={`creator-payment-card ${isEnabled ? "selected" : ""}`}
                    >
                      <div className="creator-payment-card-top">
                        <div
                          className="creator-payment-icon"
                          style={{ color: method.color }}
                        >
                          <Icon className="w-5 h-5" />
                        </div>
                        <div className="flex items-center gap-1.5">
                          {isPrimary && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                              Primary
                            </span>
                          )}
                          <span className="creator-payment-badge">{method.badge}</span>
                        </div>
                      </div>
                      <h4 className="creator-payment-name">{method.name}</h4>
                      <p className="creator-payment-desc">{method.desc}</p>
                      
                      <div className="flex items-center justify-between mt-3 pt-2 border-t border-white/5">
                        <span className={`text-xs font-semibold ${isEnabled ? "text-[#dfb180]" : "text-zinc-500"}`}>
                          {isEnabled ? "✓ Enabled" : "+ Enable"}
                        </span>
                        {isEnabled && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setPayoutMethod(method.id);
                              toast.success(`Set ${method.name} as primary payout method!`);
                            }}
                            className={`text-[11px] px-2 py-0.5 rounded cursor-pointer transition-colors ${
                              isPrimary
                                ? "bg-[#dfb180]/20 text-[#dfb180] font-bold"
                                : "bg-white/5 text-zinc-400 hover:text-white"
                            }`}
                          >
                            {isPrimary ? "★ Default" : "Set Default"}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Dynamic Payout Fields for all enabled gateways */}
              <div className="space-y-4 pt-2">
                <div className="border-t border-white/10 pt-4">
                  <h4 className="text-sm font-bold text-foreground mb-1">
                    Payout &amp; Account Details ({enabledMethods.length} method{enabledMethods.length === 1 ? "" : "s"} enabled)
                  </h4>
                  <p className="text-xs text-muted-foreground mb-4">
                    Fill in the details for each enabled payment method so buyers can pay you directly and platform settlements route seamlessly.
                  </p>
                </div>

                {/* Stripe Details */}
                {enabledMethods.includes("stripe") && (
                  <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
                    <div className="flex items-center gap-2 text-indigo-400 font-bold text-sm">
                      <CreditCard className="w-4 h-4" />
                      <span>Stripe Connect &amp; Direct Cards</span>
                      {payoutMethod === "stripe" && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-normal">Primary Gateway</span>
                      )}
                    </div>
                    <div className="creator-grid-3">
                      <div className="creator-field">
                        <label className="creator-label">Stripe Account Email</label>
                        <input
                          type="email"
                          placeholder="your-stripe@email.com"
                          value={stripeEmail}
                          onChange={(e) => setStripeEmail(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">Stripe Connect Account ID (Optional)</label>
                        <input
                          type="text"
                          placeholder="acct_1N..."
                          value={stripeAccountId}
                          onChange={(e) => setStripeAccountId(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">Stripe Payment Link URL (Optional)</label>
                        <input
                          type="url"
                          placeholder="https://buy.stripe.com/..."
                          value={stripePaymentLink}
                          onChange={(e) => setStripePaymentLink(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Razorpay Details */}
                {enabledMethods.includes("razorpay") && (
                  <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
                    <div className="flex items-center gap-2 text-blue-400 font-bold text-sm">
                      <Zap className="w-4 h-4" />
                      <span>Razorpay &amp; UPI Settlements</span>
                      {payoutMethod === "razorpay" && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-normal">Primary Gateway</span>
                      )}
                    </div>
                    <div className="creator-grid-2">
                      <div className="creator-field">
                        <label className="creator-label">Razorpay UPI VPA ID</label>
                        <input
                          type="text"
                          placeholder="yourname@okhdfcbank"
                          value={razorpayVpa}
                          onChange={(e) => setRazorpayVpa(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">Razorpay Route / Linked Account ID</label>
                        <input
                          type="text"
                          placeholder="acc_xxxxxx"
                          value={razorpayAccountId}
                          onChange={(e) => setRazorpayAccountId(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                    </div>
                  </div>
                )}


                {/* UPI Details */}
                {enabledMethods.includes("upi") && (
                  <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
                    <div className="flex items-center gap-2 text-green-400 font-bold text-sm">
                      <Smartphone className="w-4 h-4" />
                      <span>Direct UPI (GPay, PhonePe, Paytm, BHIM)</span>
                      {payoutMethod === "upi" && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-normal">Primary Gateway</span>
                      )}
                    </div>
                    <div className="creator-field">
                      <label className="creator-label">UPI Virtual Payment Address (VPA)</label>
                      <input
                        type="text"
                        placeholder="e.g. alexstudio@oksbi or 9876543210@paytm"
                        value={upiId}
                        onChange={(e) => setUpiId(e.target.value)}
                        className="creator-input"
                      />
                    </div>
                  </div>
                )}

                {/* Bank Wire Details */}
                {enabledMethods.includes("bank") && (
                  <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
                    <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                      <Building2 className="w-4 h-4" />
                      <span>Direct Bank Wire / NEFT / IMPS / SWIFT</span>
                      {payoutMethod === "bank" && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-normal">Primary Gateway</span>
                      )}
                    </div>
                    <div className="creator-grid-2">
                      <div className="creator-field">
                        <label className="creator-label">Bank Name</label>
                        <input
                          type="text"
                          placeholder="e.g. JPMorgan Chase, HDFC Bank, HSBC"
                          value={bankName}
                          onChange={(e) => setBankName(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">Account Holder Full Name</label>
                        <input
                          type="text"
                          placeholder="Name as on official Bank Records"
                          value={accountHolder}
                          onChange={(e) => setAccountHolder(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                    </div>
                    <div className="creator-grid-3">
                      <div className="creator-field">
                        <label className="creator-label">Account Number / IBAN</label>
                        <input
                          type="text"
                          placeholder="Account Number or IBAN"
                          value={accountNumber}
                          onChange={(e) => setAccountNumber(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">IFSC / Routing Code</label>
                        <input
                          type="text"
                          placeholder="e.g. HDFC0001234 or ABA Routing #"
                          value={ifscCode}
                          onChange={(e) => setIfscCode(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">SWIFT / BIC Code (Optional)</label>
                        <input
                          type="text"
                          placeholder="e.g. CHASUS33"
                          value={swiftCode}
                          onChange={(e) => setSwiftCode(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Crypto / Web3 Details */}
                {enabledMethods.includes("crypto") && (
                  <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
                    <div className="flex items-center gap-2 text-amber-400 font-bold text-sm">
                      <Coins className="w-4 h-4" />
                      <span>Crypto / Web3 Wallet Settlements</span>
                      {payoutMethod === "crypto" && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-normal">Primary Gateway</span>
                      )}
                    </div>
                    <div className="creator-grid-3">
                      <div className="creator-field">
                        <label className="creator-label">Preferred Currency</label>
                        <select
                          value={cryptoCurrency}
                          onChange={(e) => setCryptoCurrency(e.target.value)}
                          className="creator-input"
                        >
                          <option value="USDT">USDT (Tether USD)</option>
                          <option value="USDC">USDC (USD Coin)</option>
                          <option value="BTC">Bitcoin (BTC)</option>
                          <option value="ETH">Ethereum (ETH)</option>
                          <option value="SOL">Solana (SOL)</option>
                        </select>
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">Blockchain Network</label>
                        <select
                          value={cryptoNetwork}
                          onChange={(e) => setCryptoNetwork(e.target.value)}
                          className="creator-input"
                        >
                          <option value="TRC20">TRON (TRC-20) - Low Fee</option>
                          <option value="ERC20">Ethereum (ERC-20)</option>
                          <option value="Polygon">Polygon (MATIC)</option>
                          <option value="Solana">Solana Network</option>
                          <option value="Native">Native Blockchain</option>
                        </select>
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">Wallet Address</label>
                        <input
                          type="text"
                          placeholder="0x... or T..."
                          value={cryptoAddress}
                          onChange={(e) => setCryptoAddress(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Wise / Revolut / Cash App / Paystack / Custom */}
                {(enabledMethods.includes("wise") ||
                  enabledMethods.includes("revolut") ||
                  enabledMethods.includes("cashapp") ||
                  enabledMethods.includes("paystack") ||
                  enabledMethods.includes("custom")) && (
                  <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
                    <div className="text-zinc-300 font-bold text-sm">Global Peer-to-Peer &amp; Regional Options</div>
                    <div className="creator-grid-2">
                      {enabledMethods.includes("wise") && (
                        <div className="creator-field">
                          <label className="creator-label">Wise Email / Tag</label>
                          <input
                            type="text"
                            placeholder="wise@email.com or @wisetag"
                            value={wiseEmail}
                            onChange={(e) => setWiseEmail(e.target.value)}
                            className="creator-input"
                          />
                        </div>
                      )}
                      {enabledMethods.includes("revolut") && (
                        <div className="creator-field">
                          <label className="creator-label">Revolut.me Username</label>
                          <input
                            type="text"
                            placeholder="e.g. @revtag or revolut.me/user"
                            value={revolutTag}
                            onChange={(e) => setRevolutTag(e.target.value)}
                            className="creator-input"
                          />
                        </div>
                      )}
                      {enabledMethods.includes("cashapp") && (
                        <div className="creator-field">
                          <label className="creator-label">Cash App ($cashtag) / Venmo (@handle)</label>
                          <input
                            type="text"
                            placeholder="$cashtag or @venmo"
                            value={cashappTag}
                            onChange={(e) => setCashappTag(e.target.value)}
                            className="creator-input"
                          />
                        </div>
                      )}
                      {enabledMethods.includes("paystack") && (
                        <div className="creator-field">
                          <label className="creator-label">Paystack / Flutterwave Subaccount</label>
                          <input
                            type="text"
                            placeholder="ACCT_xxxxxx or subaccount code"
                            value={paystackCode}
                            onChange={(e) => setPaystackCode(e.target.value)}
                            className="creator-input"
                          />
                        </div>
                      )}
                    </div>
                    {enabledMethods.includes("custom") && (
                      <div className="creator-field">
                        <label className="creator-label">Custom Payment Instructions (Displayed to Buyers)</label>
                        <textarea
                          rows={2}
                          placeholder="e.g. Please include your Order ID in transaction notes and allow up to 10 minutes for automated verification..."
                          value={customInstructions}
                          onChange={(e) => setCustomInstructions(e.target.value)}
                          className="creator-textarea"
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* ── SECTION 3: STOREFRONT & DISTRIBUTION CHOICE ── */}
            <div className="creator-card">
              <div className="creator-card-header">
                <div className="creator-step-badge">Step 3</div>
                <div>
                  <h3 className="creator-card-title">Storefront Distribution Choice</h3>
                  <p className="creator-card-desc">
                    Where would you like to sell your templates? You can sell on our main
                    marketplace, or your separated dedicated place on our domain in your own name!
                  </p>
                </div>
              </div>

              <div className="creator-dist-grid">
                {DISTRIBUTION_OPTIONS.map((opt) => {
                  const isSelected = storefrontDistribution === opt.id;
                  return (
                    <div
                      key={opt.id}
                      onClick={() => setStorefrontDistribution(opt.id)}
                      className={`creator-dist-card ${isSelected ? "selected" : ""} ${
                        opt.highlight ? "highlight" : ""
                      }`}
                    >
                      <div className="creator-dist-card-top">
                        <span className="creator-dist-badge">{opt.badge}</span>
                        <div
                          className={`creator-radio-dot ${isSelected ? "active" : ""}`}
                        />
                      </div>
                      <h4 className="creator-dist-title">{opt.title}</h4>
                      <p className="creator-dist-desc">{opt.desc}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Submit Action Bar */}
            <div className="creator-submit-bar">
              <div className="creator-submit-note">
                <ShieldCheck className="w-4 h-4 text-emerald-400 mr-2 shrink-0" />
                <span>
                  All transactions and live demos are securely hosted on our domain under your
                  chosen brand.
                </span>
              </div>
              <div className="creator-submit-buttons">
                <button
                  type="button"
                  onClick={() => navigate("/dashboard?tab=creator-studio")}
                  className="creator-btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || slugAvailable === false}
                  className="creator-btn-primary"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      <span>Saving Storefront...</span>
                    </>
                  ) : (
                    <>
                      <Store className="w-4 h-4 mr-2" />
                      <span>Save &amp; Launch My Storefront</span>
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        )}
      </main>

      <Footer />
    </div>
  );
}
