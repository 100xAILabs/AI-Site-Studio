"use client";

import { useState, useEffect, useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
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
import { useAuthStore } from "@/store/authStore";
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
  const [searchParams] = useSearchParams();
  const { user, isSignedIn, isLoaded } = useAppUser();

  const sellRedirectReason = searchParams.get("reason") || "";
  const redirectTarget = searchParams.get("redirect") || "";
  const retailTemplateId = searchParams.get("retailTemplate") || "";

  const isExtreme =
    Boolean(user?.can_retail_templates) ||
    Boolean(user?.is_extreme_subscriber) ||
    ["extreme", "agency", "enterprise"].includes(
      String(user?.subscription_tier || "").toLowerCase()
    ) ||
    user?.role === "admin" ||
    user?.role === "super_admin";

  const [isLoadingProfile, setIsLoadingProfile] = useState(true);
  const [profileData, setProfileData] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isProvisioningRazorpay, setIsProvisioningRazorpay] = useState(false);
  const [isProvisioningStripe, setIsProvisioningStripe] = useState(false);
  const [gatewayError, setGatewayError] = useState("");
  const [stripeOnboardingUrl, setStripeOnboardingUrl] = useState("");
  const [copiedLink, setCopiedLink] = useState(false);
  const [successData, setSuccessData] = useState(null);

  // Form State
  const [brandName, setBrandName] = useState("");
  const [creatorName, setCreatorName] = useState("");
  const [storeSlug, setStoreSlug] = useState("");
  const [phone, setPhone] = useState("");
  const [country, setCountry] = useState("IN");
  const [businessType, setBusinessType] = useState("individual");
  const [pan, setPan] = useState("");
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
  const [enabledMethods, setEnabledMethods] = useState(["razorpay"]);
  const [payoutMethod, setPayoutMethod] = useState("razorpay");
  
  // Gateway Detail Fields
  const [stripeEmail, setStripeEmail] = useState("");
  const [stripeAccountId, setStripeAccountId] = useState("");
  const [stripePaymentLink, setStripePaymentLink] = useState("");

  const [razorpayVpa, setRazorpayVpa] = useState("");
  const [razorpayAccountId, setRazorpayAccountId] = useState("");

  const [upiId, setUpiId] = useState("");

  const [bankName, setBankName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [confirmAccountNumber, setConfirmAccountNumber] = useState("");
  const [showAccountNumber, setShowAccountNumber] = useState(false);
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

  // Load existing creator profile (and sync live gateway return status if redirected back from Stripe)
  useEffect(() => {
    async function loadProfile() {
      if (!isSignedIn) {
        setIsLoadingProfile(false);
        return;
      }
      try {
        const isStripeReturn = searchParams.get("stripe_connected") === "1" || searchParams.get("stripe_refresh") === "1";
        const data = isStripeReturn
          ? await api.get("/creator/connect/status")
          : await api.get("/creator/profile");
        if (data) {
          setProfileData(data);
          if (data.creator_brand_name) setBrandName(data.creator_brand_name);
          if (data.full_name) setCreatorName(data.full_name);
          if (data.creator_store_slug) {
            setStoreSlug(data.creator_store_slug);
            setSlugAvailable(true);
          }
          if (data.phone) setPhone(data.phone);
          if (data.country) setCountry(data.country);
          if (data.business_type) setBusinessType(data.business_type);
          if (data.creator_payout_details?.pan) setPan(data.creator_payout_details.pan);
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
          if (data.payout_account_number) {
            setAccountNumber(data.payout_account_number);
            setConfirmAccountNumber(data.payout_account_number);
          } else if (data.payout_account_number_masked) {
            setAccountNumber(data.payout_account_number_masked);
            setConfirmAccountNumber(data.payout_account_number_masked);
          }
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

  // Live strict payout validation calculation
  const isPayoutGatewayReady = useMemo(() => {
    const serverConns = profileData?.gateway_connections || {};
    for (const method of enabledMethods) {
      if (method === "bank") {
        const hasBank =
          bankName.trim().length >= 2 &&
          accountNumber.trim().length >= 6 &&
          accountHolder.trim().length >= 2 &&
          (ifscCode.trim().length >= 4 || iban.trim().length >= 8 || swiftCode.trim().length >= 8);
        if (hasBank) return true;
      } else if (method === "upi") {
        if (/^[a-z0-9._-]{2,}@[a-z0-9]{2,}$/i.test(upiId.trim())) return true;
      } else if (method === "stripe") {
        const validLink = /^https:\/\/(buy|checkout)\.stripe\.com\/[A-Za-z0-9_-]+/i.test(stripePaymentLink.trim());
        const verifiedAcct = Boolean(serverConns.stripe && stripeAccountId.trim().startsWith("acct_"));
        if (validLink || verifiedAcct) return true;
      } else if (method === "razorpay") {
        const validRzp = Boolean(
          (razorpayAccountId.trim().startsWith("acc_") || razorpayAccountId.trim().startsWith("fa_")) &&
          profileData?.creator_payout_details?.razorpay_status !== "error"
        );
        if (validRzp) return true;
      } else if (method === "crypto") {
        if (cryptoAddress.trim().length >= 16) return true;
      } else if (method === "wise") {
        if (wiseEmail.trim().length >= 3) return true;
      } else if (method === "revolut") {
        if (revolutTag.trim().length >= 2) return true;
      } else if (method === "cashapp") {
        if (cashappTag.trim().length >= 2 || venmoTag.trim().length >= 2) return true;
      } else if (method === "paystack") {
        if (paystackCode.trim().length >= 3 || flutterwaveId.trim().length >= 3) return true;
      }
    }
    return false;
  }, [
    profileData,
    enabledMethods,
    bankName,
    accountNumber,
    accountHolder,
    ifscCode,
    iban,
    swiftCode,
    upiId,
    stripePaymentLink,
    stripeAccountId,
    razorpayAccountId,
    cryptoAddress,
    wiseEmail,
    revolutTag,
    cashappTag,
    venmoTag,
    paystackCode,
    flutterwaveId,
  ]);

  const handleAutoConnectRazorpay = async () => {
    setGatewayError("");
    if (!phone.trim() || phone.replace(/\D/g, "").length < 10) {
      const msg = "Please enter a valid 10-digit phone number in Step 1 before connecting Razorpay.";
      setGatewayError(msg);
      toast.error(msg);
      return;
    }
    const hasBank = bankName.trim().length >= 2 && accountNumber.trim().length >= 6 && ifscCode.trim().length >= 4;
    const hasVpa = /^[a-z0-9._-]{2,}@[a-z0-9]{2,}$/i.test((razorpayVpa || upiId || "").trim());
    if (!hasBank && !hasVpa) {
      const msg = "Please enter your Bank Account Number + IFSC Code (or a valid UPI VPA) so we can automatically create your Razorpay payout account.";
      setGatewayError(msg);
      toast.error(msg);
      return;
    }

    setIsProvisioningRazorpay(true);
    try {
      const res = await api.post("/creator/connect/razorpay", {
        brand_name: brandName.trim() || "Site Studio Creator",
        creator_name: creatorName.trim() || accountHolder.trim() || user?.full_name || "Creator",
        email: (supportEmail || user?.email || "").trim(),
        phone: phone.trim(),
        business_type: businessType,
        pan: pan.trim().toUpperCase() || null,
        bank_name: bankName.trim() || null,
        account_number: accountNumber.trim() || null,
        ifsc_code: ifscCode.trim().toUpperCase() || null,
        account_holder_name: (accountHolder || creatorName || brandName).trim(),
        upi_vpa: (razorpayVpa || upiId || "").trim().toLowerCase() || null,
        existing_account_id: razorpayAccountId.trim() || null,
      });

      if (res?.account_id) {
        setRazorpayAccountId(res.account_id);
        toast.success(res.message || `Razorpay account connected successfully (${res.account_id})!`);
        const refreshed = await api.get("/creator/profile");
        if (refreshed) setProfileData(refreshed);
      }
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "There is some issue connecting or creating your Razorpay account right now. Please try again later.";
      setGatewayError(msg);
      toast.error(msg);
    } finally {
      setIsProvisioningRazorpay(false);
    }
  };

  const handleAutoConnectStripe = async () => {
    setGatewayError("");
    setIsProvisioningStripe(true);
    try {
      const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost:5173";
      const res = await api.post("/creator/connect/stripe", {
        brand_name: brandName.trim() || "Site Studio Creator",
        email: (stripeEmail || supportEmail || user?.email || "").trim(),
        country: country || "US",
        existing_account_id: stripeAccountId.trim() || null,
        return_url: `${origin}/creator/setup?stripe_connected=1`,
        refresh_url: `${origin}/creator/setup?stripe_refresh=1`,
      });

      if (res?.account_id) {
        setStripeAccountId(res.account_id);
      }
      if (res?.onboarding_url) {
        setStripeOnboardingUrl(res.onboarding_url);
        toast.success("Stripe Connect account created! Redirecting to Stripe onboarding...");
        window.location.href = res.onboarding_url;
        return;
      }
      if (res?.connected) {
        toast.success(res.message || "Stripe Express account verified and connected!");
        const refreshed = await api.get("/creator/profile");
        if (refreshed) setProfileData(refreshed);
      }
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "There is some issue connecting your Stripe account right now. Please try again later.";
      setGatewayError(msg);
      toast.error(msg);
    } finally {
      setIsProvisioningStripe(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setGatewayError("");
    setStripeOnboardingUrl("");

    if (!brandName.trim()) {
      toast.error("Please enter your Studio or Brand Name");
      return;
    }

    if (!creatorName.trim()) {
      toast.error("Please enter your Creator / Legal Display Name");
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

    if ((enabledMethods.includes("razorpay") || enabledMethods.includes("stripe")) && (!phone.trim() || phone.replace(/\D/g, "").length < 10)) {
      const msg = "Please enter your valid contact phone number (with country code, e.g. +919876543210) to connect payment gateways.";
      setGatewayError(msg);
      toast.error(msg);
      return;
    }

    if ((enabledMethods.includes("bank") || enabledMethods.includes("razorpay")) && accountNumber.trim() && !accountNumber.includes("*")) {
      if (confirmAccountNumber.trim() && accountNumber.trim() !== confirmAccountNumber.trim()) {
        toast.error("Bank Account Number and Confirm Account Number do not match. Please verify.");
        return;
      }
    }

    setIsSubmitting(true);
    try {
      const allEnabledMethods = [...enabledMethods];
      if ((upiId.trim() || razorpayVpa.trim()) && !allEnabledMethods.includes("upi")) {
        allEnabledMethods.push("upi");
      }
      if (bankName.trim() && accountNumber.trim() && !allEnabledMethods.includes("bank")) {
        allEnabledMethods.push("bank");
      }

      const payload = {
        brand_name: brandName.trim(),
        creator_name: creatorName.trim() || null,
        store_slug: storeSlug.trim().toLowerCase(),
        phone: phone.trim() || null,
        country: country || "IN",
        business_type: businessType || "individual",
        pan: pan.trim().toUpperCase() || null,
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
        enabled_payment_methods: allEnabledMethods,
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
      setProfileData(res);
      if (res?.payout_razorpay_account_id) setRazorpayAccountId(res.payout_razorpay_account_id);
      if (res?.payout_stripe_account_id) setStripeAccountId(res.payout_stripe_account_id);

      // Sync user profile across all tabs and stores immediately
      try {
        await useAuthStore.getState().fetchProfile();
      } catch (syncErr) {
        console.warn("Global auth profile sync notice:", syncErr);
      }

      if (res?.stripe_onboarding_url && !res?.is_payout_setup_completed) {
        setStripeOnboardingUrl(res.stripe_onboarding_url);
        toast.info("Storefront saved! Redirecting you to Stripe to complete your real payout bank connection...");
        window.location.href = res.stripe_onboarding_url;
        return;
      }

      if (res?.is_payout_setup_completed) {
        setSuccessData(res);
        toast.success("Storefront & payment gateway connected! You can now sell templates.");
      } else {
        const msg = "Profile saved, but a verified payment gateway is still required before customer purchases or selling templates can go live.";
        setGatewayError(msg);
        toast.warning(msg);
      }
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "There is some issue connecting your storefront or payment method right now. Please try again later.";
      setGatewayError(msg);
      toast.error(msg);
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
              {(() => {
                const params = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
                const rawRedirect =
                  params.get("redirect") ||
                  params.get("redirectTarget") ||
                  params.get("next") ||
                  params.get("returnTo");
                const retailId =
                  params.get("retailTemplateId") ||
                  params.get("templateId") ||
                  params.get("template_id") ||
                  params.get("retail");
                const safeRedirect =
                  rawRedirect && rawRedirect.startsWith("/") && !rawRedirect.startsWith("//")
                    ? rawRedirect
                    : null;
                const sellTarget =
                  safeRedirect ||
                  (retailId
                    ? `/dashboard?tab=creator-studio&retail=${encodeURIComponent(retailId)}`
                    : "/dashboard?tab=creator-studio");
                return (
                  <Link to={sellTarget} className="creator-btn-primary">
                    <ShoppingBag className="w-4 h-4 mr-2" />
                    <span>
                      {safeRedirect || retailId
                        ? "Continue to Sell Template"
                        : "Go to Creator Studio to Sell Templates"}
                    </span>
                  </Link>
                );
              })()}
              <Link
                to={`/creator/${successData.creator_store_slug || storeSlug}`}
                className="creator-btn-secondary"
              >
                <Store className="w-4 h-4 mr-2" />
                <span>Visit My Storefront</span>
                <ExternalLink className="w-4 h-4 ml-1.5" />
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
                <span>Creator onboarding</span>
              </div>
              <div className="creator-hero-layout">
                <div>
                  <p className="creator-hero-kicker">YOUR CREATOR BUSINESS, READY TO LAUNCH</p>
                  <h1 className="creator-title">Build your storefront.</h1>
                  <p className="creator-subtitle">
                    Set up your brand, choose how buyers can pay, and decide where your templates appear.
                    You can update these details anytime.
                  </p>
                </div>
                <div className="creator-hero-note">
                  <span className="creator-hero-note-icon"><Store className="w-5 h-5" /></span>
                  <span><strong>One setup,</strong><br />ready for every launch.</span>
                </div>
              </div>
              <nav className="creator-setup-progress" aria-label="Setup sections">
                <a href="#creator-step-profile"><span>01</span><span>Brand &amp; profile</span><ChevronRight className="w-3.5 h-3.5" /></a>
                <a href="#creator-step-payout"><span>02</span><span>Payments</span><ChevronRight className="w-3.5 h-3.5" /></a>
                <a href="#creator-step-distribution"><span>03</span><span>Distribution</span><CheckCircle2 className="w-3.5 h-3.5" /></a>
              </nav>
            </div>

            {sellRedirectReason === "sell_requires_storefront" && (
              <div className="p-4 rounded-xl bg-[#dfb180]/10 border border-[#dfb180]/40 text-amber-100 flex items-start gap-3 mb-6">
                <Crown className="w-5 h-5 text-[#dfb180] shrink-0 mt-0.5" />
                <div className="flex-1 text-xs">
                  <h4 className="font-bold text-[#dfb180] text-sm">Complete Storefront &amp; Payment Connection First</h4>
                  <p className="text-slate-300 mt-1 leading-relaxed">
                    Before selling or listing templates on Site Studio, please enter your complete creator details, bank account information, and connect a verified payment gateway below.
                  </p>
                </div>
              </div>
            )}

            {gatewayError && (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/35 text-rose-200 flex items-start gap-3 mb-6">
                <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div className="flex-1 text-xs">
                  <h4 className="font-bold text-rose-300 text-sm">Payment Gateway Connection Issue</h4>
                  <p className="text-rose-200/90 mt-1 leading-relaxed">{gatewayError}</p>
                </div>
              </div>
            )}

            {stripeOnboardingUrl && (
              <div className="p-4 rounded-xl bg-indigo-500/15 border border-indigo-500/40 text-indigo-100 flex items-center justify-between gap-4 mb-6">
                <div className="text-xs">
                  <h4 className="font-bold text-indigo-300 text-sm">Finish Connecting Stripe Express Account</h4>
                  <p className="text-slate-300 mt-0.5">
                    Click to link your real bank account on Stripe hosted onboarding.
                  </p>
                </div>
                <a
                  href={stripeOnboardingUrl}
                  className="px-4 py-2 rounded-lg bg-indigo-500 hover:bg-indigo-400 text-white font-bold text-xs shrink-0 flex items-center gap-1.5"
                >
                  <span>Complete Stripe Onboarding</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            )}

            {/* Bank Connection Status Banner */}
            {profileData && !profileData.is_payout_setup_completed && (
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 flex items-start gap-3 mb-6">
                <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div className="flex-1 text-sm">
                  <h4 className="font-bold text-amber-200">Action Required: Payment Account Not Connected</h4>
                  <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                    Your storefront checkout is currently paused. Complete your creator details and connect Razorpay, Stripe Express, Bank Account, or UPI below to sell templates.
                  </p>
                </div>
              </div>
            )}
            {profileData && profileData.is_payout_setup_completed && (
              <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-200 flex items-center gap-3 mb-6">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                <div className="flex-1 text-xs">
                  <span className="font-semibold text-emerald-300">Real Payment Account Connected:</span>
                  <span className="text-slate-300 ml-1.5">Direct purchases are active on your storefront. Payments route securely to your verified account.</span>
                </div>
              </div>
            )}

            {/* ── SECTION 1: BRANDING & CREATOR IDENTITY ── */}
            <div className="creator-card" id="creator-step-profile">
              <div className="creator-card-header">
                <div className="creator-step-badge">Step 1</div>
                <div>
                  <h3 className="creator-card-title">Brand &amp; Creator Identity</h3>
                  <p className="creator-card-desc">
                    Required business, contact, and identity details for your storefront and payment gateway account creation.
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
                  <label className="creator-label">
                    Creator Legal / Display Name <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Alex Morgan"
                    value={creatorName}
                    onChange={(e) => setCreatorName(e.target.value)}
                    className="creator-input"
                  />
                  <span className="creator-field-hint">Required for Razorpay/Stripe account registration.</span>
                </div>
              </div>

              <div className="creator-grid-3">
                <div className="creator-field">
                  <label className="creator-label">
                    Contact Phone Number <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="tel"
                    placeholder="e.g. +919876543210"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="creator-input font-mono"
                  />
                  <span className="creator-field-hint">Required for Razorpay Linked Account auto-creation.</span>
                </div>

                <div className="creator-field">
                  <label className="creator-label">Country / Region</label>
                  <select
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="creator-input"
                  >
                    <option value="IN">India (INR / UPI / Razorpay)</option>
                    <option value="US">United States (USD / Stripe)</option>
                    <option value="GB">United Kingdom (GBP / Stripe)</option>
                    <option value="DE">European Union (EUR / SEPA)</option>
                    <option value="CA">Canada (CAD / Stripe)</option>
                    <option value="AU">Australia (AUD / Stripe)</option>
                    <option value="SG">Singapore (SGD / Stripe)</option>
                  </select>
                </div>

                <div className="creator-field">
                  <label className="creator-label">Business Entity Type</label>
                  <select
                    value={businessType}
                    onChange={(e) => setBusinessType(e.target.value)}
                    className="creator-input"
                  >
                    <option value="individual">Individual / Freelancer</option>
                    <option value="proprietorship">Sole Proprietorship</option>
                    <option value="llp">LLP / Partnership</option>
                    <option value="private_limited">Private Limited / LLC</option>
                  </select>
                </div>
              </div>

              {country === "IN" && (
                <div className="creator-field">
                  <label className="creator-label">PAN Number (Optional — speeds up Razorpay Route KYC)</label>
                  <input
                    type="text"
                    maxLength={10}
                    placeholder="e.g. ABCDE1234F"
                    value={pan}
                    onChange={(e) => setPan(e.target.value.toUpperCase())}
                    className="creator-input font-mono uppercase"
                  />
                </div>
              )}

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
            <div className="creator-card" id="creator-step-payout">
              <div className="creator-card-header">
                <div className="creator-step-badge">Step 2</div>
                <div>
                  <h3 className="creator-card-title">Payment Gateways &amp; Payout Methods</h3>
                  <p className="creator-card-desc">
                    Choose which payment methods you want to accept from your buyers. You can enable multiple methods for your customers and set your primary payout gateway!
                  </p>
                </div>
              </div>

              {/* Live Payout Status Card */}
              <div
                className={`p-4 rounded-xl border flex items-center justify-between gap-4 mb-6 transition-all ${
                  isPayoutGatewayReady
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-200"
                    : "bg-amber-500/10 border-amber-500/30 text-amber-200"
                }`}
              >
                <div className="flex items-center gap-3">
                  {isPayoutGatewayReady ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-amber-400 shrink-0" />
                  )}
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-sm">
                        {isPayoutGatewayReady
                          ? "Payout Gateway Configured & Ready"
                          : "Action Required: Complete Bank / Payout Details"}
                      </h4>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          isPayoutGatewayReady
                            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                            : "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                        }`}
                      >
                        {isPayoutGatewayReady ? "CHECKOUT ACTIVE" : "CHECKOUT PAUSED"}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 mt-0.5">
                      {isPayoutGatewayReady
                        ? "Direct purchases are active. Customer payments route directly to your verified payout gateway."
                        : "Your storefront checkout is paused. Fill in your Bank Account, UPI ID, or Stripe details below to enable buyer purchases."}
                    </p>
                  </div>
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
              <div className="creator-payout-details space-y-4 pt-2">
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
                  <div className="creator-payout-method-panel p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2 text-indigo-400 font-bold text-sm">
                        <CreditCard className="w-4 h-4" />
                        <span>Stripe Connect &amp; Direct Cards</span>
                        {payoutMethod === "stripe" && (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-normal">Primary Gateway</span>
                        )}
                        {profileData?.gateway_connections?.stripe && stripeAccountId && (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
                            ✓ Verified ({stripeAccountId})
                          </span>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={handleAutoConnectStripe}
                        disabled={isProvisioningStripe}
                        className="px-3 py-1.5 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-400/40 text-indigo-200 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
                      >
                        {isProvisioningStripe ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Connecting Stripe...</span>
                          </>
                        ) : (
                          <>
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span>{stripeAccountId ? "Verify / Resume Stripe Onboarding" : "Auto-Create & Connect Stripe Account"}</span>
                          </>
                        )}
                      </button>
                    </div>
                    <p className="text-[11px] text-zinc-400">
                      Auto-creating Express accounts requires your platform Stripe account to be activated at{" "}
                      <a
                        href="https://dashboard.stripe.com/account/onboarding"
                        target="_blank"
                        rel="noreferrer"
                        className="text-indigo-400 underline hover:text-indigo-300"
                      >
                        dashboard.stripe.com/account/onboarding
                      </a>
                      . Alternatively, you can enter your existing Stripe Account ID (<code>acct_...</code>), paste your direct Stripe Payment Link (<code>https://buy.stripe.com/...</code>), or connect with <strong>Razorpay Route / Direct UPI</strong> below.
                    </p>
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
                        <label className="creator-label">Stripe Connect Account ID</label>
                        <input
                          type="text"
                          placeholder="Auto-created via button or acct_1..."
                          value={stripeAccountId}
                          onChange={(e) => setStripeAccountId(e.target.value)}
                          className="creator-input font-mono"
                        />
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">Real Stripe Payment Link URL (Optional)</label>
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
                  <div className="creator-payout-method-panel p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2 text-blue-400 font-bold text-sm">
                        <Zap className="w-4 h-4" />
                        <span>Razorpay Route &amp; UPI Settlements</span>
                        {payoutMethod === "razorpay" && (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-normal">Primary Gateway</span>
                        )}
                        {razorpayAccountId && (razorpayAccountId.startsWith("acc_") || razorpayAccountId.startsWith("fa_")) && (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
                            ✓ Connected ({razorpayAccountId})
                          </span>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={handleAutoConnectRazorpay}
                        disabled={isProvisioningRazorpay}
                        className="px-3 py-1.5 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 border border-blue-400/40 text-blue-200 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
                      >
                        {isProvisioningRazorpay ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Creating Razorpay Account...</span>
                          </>
                        ) : (
                          <>
                            <Zap className="w-3.5 h-3.5" />
                            <span>{razorpayAccountId ? "Verify Razorpay Account" : "Auto-Create & Connect Razorpay Account"}</span>
                          </>
                        )}
                      </button>
                    </div>
                    <p className="text-[11px] text-zinc-400">
                      Fill in your phone number above and your Bank Account / IFSC below, then click <strong>Auto-Create &amp; Connect Razorpay Account</strong> (or Save). Site Studio will automatically register a real Razorpay payout account for you.
                    </p>
                    <div className="creator-grid-2">
                      <div className="creator-field">
                        <label className="creator-label">Razorpay UPI VPA ID (Optional Backup)</label>
                        <input
                          type="text"
                          placeholder="yourname@okhdfcbank"
                          value={razorpayVpa}
                          onChange={(e) => setRazorpayVpa(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">Razorpay Route / Linked Account ID (Auto-Generated)</label>
                        <input
                          type="text"
                          placeholder="Auto-created when connected (acc_... or fa_...)"
                          value={razorpayAccountId}
                          onChange={(e) => setRazorpayAccountId(e.target.value)}
                          className="creator-input font-mono"
                        />
                      </div>
                    </div>
                  </div>
                )}


                {/* UPI Details */}
                {enabledMethods.includes("upi") && (
                  <div className="creator-payout-method-panel p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-green-400 font-bold text-sm">
                        <Smartphone className="w-4 h-4" />
                        <span>Direct UPI (GPay, PhonePe, Paytm, BHIM)</span>
                        {payoutMethod === "upi" && (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-normal border border-emerald-500/30">
                            Primary Gateway
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-zinc-400">Zero-fee instant settlements</span>
                    </div>
                    <div className="creator-field">
                      <div className="flex items-center justify-between">
                        <label className="creator-label">
                          UPI Virtual Payment Address (VPA) <span className="text-rose-400">*</span>
                        </label>
                        {upiId && (
                          <span
                            className={`text-[10px] font-semibold ${
                              upiId.includes("@") ? "text-emerald-400" : "text-amber-400"
                            }`}
                          >
                            {upiId.includes("@") ? "✓ Valid UPI Format" : "⚠ Must include @handle"}
                          </span>
                        )}
                      </div>
                      <input
                        type="text"
                        placeholder="e.g. alexstudio@oksbi or 9876543210@paytm"
                        value={upiId}
                        onChange={(e) => setUpiId(e.target.value.trim().toLowerCase())}
                        className="creator-input font-mono"
                      />
                      <span className="creator-field-hint">
                        Instant peer-to-merchant payouts will be credited directly to this UPI ID.
                      </span>
                    </div>
                  </div>
                )}

                {/* Bank Wire Details (Always visible when Bank or Razorpay is enabled) */}
                {(enabledMethods.includes("bank") || enabledMethods.includes("razorpay")) && (
                  <div className="creator-payout-method-panel p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                        <Building2 className="w-4 h-4" />
                        <span>Direct Bank Wire / NEFT / IMPS / SWIFT</span>
                        {payoutMethod === "bank" && (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-normal border border-emerald-500/30">
                            Primary Gateway
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-zinc-400">Direct wire to your checking/business account</span>
                    </div>

                    <div className="creator-grid-2">
                      <div className="creator-field">
                        <label className="creator-label">
                          Bank Name <span className="text-rose-400">*</span>
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. JPMorgan Chase, HDFC Bank, HSBC, Barclays"
                          value={bankName}
                          onChange={(e) => setBankName(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">
                          Account Holder Full Name <span className="text-rose-400">*</span>
                        </label>
                        <input
                          type="text"
                          placeholder="Name as on official Bank Records"
                          value={accountHolder}
                          onChange={(e) => setAccountHolder(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                    </div>

                    <div className="creator-grid-2">
                      <div className="creator-field">
                        <label className="creator-label">
                          Account Number / IBAN <span className="text-rose-400">*</span>
                        </label>
                        <div className="creator-input-password-wrap">
                          <input
                            type={showAccountNumber ? "text" : "password"}
                            placeholder="Enter bank account number"
                            value={accountNumber}
                            onChange={(e) => setAccountNumber(e.target.value)}
                            className="creator-input pr-16"
                          />
                          <button
                            type="button"
                            onClick={() => setShowAccountNumber(!showAccountNumber)}
                            className="creator-password-toggle-btn"
                          >
                            {showAccountNumber ? "Hide" : "Show"}
                          </button>
                        </div>
                      </div>

                      <div className="creator-field">
                        <div className="flex items-center justify-between">
                          <label className="creator-label">
                            Confirm Account Number <span className="text-rose-400">*</span>
                          </label>
                          {confirmAccountNumber && (
                            <span
                              className={`text-[10px] font-semibold ${
                                accountNumber === confirmAccountNumber
                                  ? "text-emerald-400"
                                  : "text-rose-400"
                              }`}
                            >
                              {accountNumber === confirmAccountNumber
                                ? "✓ Matches"
                                : "⚠ Mismatch"}
                            </span>
                          )}
                        </div>
                        <input
                          type={showAccountNumber ? "text" : "password"}
                          placeholder="Re-enter account number to confirm"
                          value={confirmAccountNumber}
                          onChange={(e) => setConfirmAccountNumber(e.target.value)}
                          className="creator-input"
                        />
                      </div>
                    </div>

                    <div className="creator-grid-3">
                      <div className="creator-field">
                        <label className="creator-label">
                          IFSC / Routing Code <span className="text-rose-400">*</span>
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. HDFC0001234 or ABA Routing #"
                          value={ifscCode}
                          onChange={(e) => setIfscCode(e.target.value.toUpperCase())}
                          className="creator-input uppercase"
                        />
                        <span className="creator-field-hint">Required for domestic ACH / NEFT / IMPS</span>
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">SWIFT / BIC Code (Optional)</label>
                        <input
                          type="text"
                          placeholder="e.g. CHASUS33"
                          value={swiftCode}
                          onChange={(e) => setSwiftCode(e.target.value.toUpperCase())}
                          className="creator-input uppercase"
                        />
                        <span className="creator-field-hint">For international wire transfers</span>
                      </div>
                      <div className="creator-field">
                        <label className="creator-label">IBAN (Optional)</label>
                        <input
                          type="text"
                          placeholder="e.g. GB29NWBK60161331926819"
                          value={iban}
                          onChange={(e) => setIban(e.target.value.toUpperCase())}
                          className="creator-input uppercase"
                        />
                        <span className="creator-field-hint">For European &amp; SEPA accounts</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Crypto / Web3 Details */}
                {enabledMethods.includes("crypto") && (
                  <div className="creator-payout-method-panel p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
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
                  <div className="creator-payout-method-panel p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-3">
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
            <div className="creator-card" id="creator-step-distribution">
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
