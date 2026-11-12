"use client";

/**
 * Checkout & Shopping Cart Page - High-fidelity marketplace cart matching design mockup.
 * Supports automated country tax calculation, UPI QR, Razorpay, and Stripe checkout.
 */

export const dynamic = "force-dynamic";

import { useState, useEffect } from "react";
import { useAppAuth, useAppUser } from "@/lib/auth";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { navigate } from "@/components/Link";
const useRouter = () => ({
  push: (to) => navigate(to),
  replace: (to) => navigate(to),
});
import {
  CreditCard,
  ShoppingBag,
  ShoppingCart,
  ShieldCheck,
  ShieldAlert,
  Trash2,
  Loader2,
  ArrowRight,
  ArrowLeft,
  Download,
  ScanQrCode,
  CheckCircle2,
  Copy,
  Smartphone,
  Check,
  Clock,
  RotateCcw,
  Lock,
  Globe,
  MapPin,
  Tag,
  Sparkles,
  Crown,
  HelpCircle,
  Shield,
  Zap,
  Headphones,
  ChevronRight,
  X,
  AlertCircle,
  Plus,
  Minus,
  ClipboardList,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useCartStore } from "@/store";
import { api } from "@/lib/api";
import { cn, formatPrice, formatConvertedPrice } from "@/lib/utils";
import { useCurrencyStore } from "@/store/currencyStore";
import { COUNTRY_TAX_RATES, detectBrowserCountry } from "@/lib/tax";
import Image from "@/components/Image";
import Link from "@/components/Link";
import "./Page.css";

const ENABLE_EXTERNAL_GATEWAYS = true;

export default function Checkout() {
  const qc = useQueryClient();
  const { getToken } = useAppAuth();
  const { user } = useAppUser();
  const { userCurrency, rates } = useCurrencyStore();
  const router = useRouter();

  const {
    items,
    addItem,
    removeItem,
    clearCart,
    updateQuantity,
    grossSubtotal,
    discountAmount,
    subtotal,
    getTaxDetails,
    total,
    countryCode,
    setCountryCode,
    couponCode,
    couponDiscount,
    couponError,
    couponSuccess,
    applyCoupon,
    removeCoupon,
  } = useCartStore();

  const [paymentGateway, setPaymentGateway] = useState("razorpay"); // Strictly Razorpay
  const [authToken, setAuthToken] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentStep, setPaymentStep] = useState("cart"); // "cart" | "paying" | "success"
  const [freeDownloadsComplete, setFreeDownloadsComplete] = useState(false);
  const [initiatedOrder, setInitiatedOrder] = useState(null);
  const [initiatedPayment, setInitiatedPayment] = useState(null);
  const [promoInput, setPromoInput] = useState("");

  const [liveRate, setLiveRate] = useState(94.834);

  // Auto-detect user country from URL param, profile, or browser locale
  useEffect(() => {
    if (typeof window !== "undefined") {
      const qCountry = new URLSearchParams(window.location.search).get("country");
      if (qCountry && COUNTRY_TAX_RATES[qCountry.toUpperCase()]) {
        setCountryCode(qCountry.toUpperCase());
        return;
      }
    }
    const detected = (user?.country_code || user?.country || detectBrowserCountry() || "IN").toUpperCase();
    if (detected && detected !== countryCode) {
      setCountryCode(detected);
    }
  }, [user]);

  useEffect(() => {
    getToken().then(setAuthToken).catch(() => { });
    api
      .get("/payment/exchange-rate")
      .then((res) => {
        if (res?.rate) setLiveRate(res.rate);
      })
      .catch(() => { });
  }, []);

  const handleCompleteSuccessFlow = async (orderToProcess) => {
    const ord = orderToProcess || initiatedOrder;
    if (!ord) return;

    for (const item of ord.items || []) {
      try {
        const res = await api.post(`/templates/${item.template_id}/download?format=zip`, {}, authToken);
        if (res?.download_url) {
          let downloadUrl = res.download_url;
          if (authToken && !downloadUrl.includes("token=")) {
            const sep = downloadUrl.includes("?") ? "&" : "?";
            downloadUrl = `${downloadUrl}${sep}token=${encodeURIComponent(authToken)}`;
          }
          const link = document.createElement("a");
          link.href = downloadUrl;
          link.download = "";
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        }
      } catch (e) {
        console.error("Auto-download failed for template " + item.template_id, e);
      }
    }

    qc.invalidateQueries({ queryKey: ["orders"] });
    qc.invalidateQueries({ queryKey: ["dashboard-stats"] });

    setPaymentStep("success");
    clearCart();
    setTimeout(() => {
      router.push("/dashboard?tab=buyer-templates");
    }, 3500);
  };

  // Create Order Mutation with automatic country_code
  const createOrderMutation = useMutation({
    mutationFn: () =>
      api.post(
        "/orders",
        {
          items: items.map((i) => ({
            template_id: i.templateId || i.id,
            license_type: i.licenseType || "regular",
          })),
          coupon_code: couponCode || undefined,
          country_code: countryCode,
        },
        authToken ?? undefined
      ),
  });

  // Initiate Payment Mutation
  const initiatePaymentMutation = useMutation({
    mutationFn: ({ orderId, gateway }) =>
      api.post("/payment/initiate", { order_id: orderId, gateway }, authToken ?? undefined),
  });

  // Verify Payment Mutation
  const verifyPaymentMutation = useMutation({
    mutationFn: (payload) => api.post("/payment/verify", payload, authToken ?? undefined),
  });

  // Load Razorpay Script
  const loadRazorpayScript = () => {
    return new Promise((resolve) => {
      if (typeof window !== "undefined" && window.Razorpay) {
        resolve(true);
        return;
      }
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
  };

  const handleOpenRazorpay = async (order, payInfo) => {
    const targetOrder = order || initiatedOrder;
    const targetPay = payInfo || initiatedPayment;
    if (!targetOrder || !targetPay) return;

    setIsProcessing(true);

    const isMock = targetPay.key_id === "rzp_test_mockkey" || String(targetPay.gateway_order_id || "").startsWith("rzp_mock_");

    const loaded = await loadRazorpayScript();
    if (!loaded && !isMock) {
      alert("Failed to load Razorpay SDK. Please check your internet connection.");
      setIsProcessing(false);
      return;
    }

    if (isMock || !window.Razorpay) {
      try {
        await verifyPaymentMutation.mutateAsync({
          order_id: targetOrder.id,
          gateway: "razorpay",
          gateway_payment_id: `pay_mock_${Date.now()}`,
          gateway_order_id: targetPay.gateway_order_id || `rzp_mock_${Date.now()}`,
          gateway_signature: "mock_signature_verified",
        });
        await handleCompleteSuccessFlow(targetOrder);
      } catch (err) {
        console.error("Payment verification failed:", err);
        alert(err?.response?.data?.detail || "Payment verification failed. Please try again.");
      } finally {
        setIsProcessing(false);
      }
      return;
    }

    const options = {
      key: targetPay.key_id,
      amount: targetPay.amount,
      currency: targetPay.currency || "INR",
      name: "AI Site Studio",
      description: `Order #${targetOrder.order_number || targetOrder.id?.slice(0, 8)}`,
      order_id: targetPay.gateway_order_id,
      prefill: {
        name: user?.name || user?.full_name || user?.email?.split("@")[0] || "",
        email: user?.email || "",
      },
      theme: { color: "#c89666" },
      handler: async function (response) {
        setIsProcessing(true);
        try {
          await verifyPaymentMutation.mutateAsync({
            order_id: targetOrder.id,
            gateway: "razorpay",
            gateway_payment_id: response.razorpay_payment_id,
            gateway_order_id: response.razorpay_order_id,
            gateway_signature: response.razorpay_signature,
          });
          await handleCompleteSuccessFlow(targetOrder);
        } catch (err) {
          console.error("Payment verification failed:", err);
          alert(err?.response?.data?.detail || "Payment verification failed. Please try again.");
        } finally {
          setIsProcessing(false);
        }
      },
      modal: {
        ondismiss: function () {
          setIsProcessing(false);
        },
      },
    };

    try {
      const rzp = new window.Razorpay(options);
      rzp.on("payment.failed", function (response) {
        alert(`Payment Failed: ${response.error?.description || "Transaction failed"}`);
        setIsProcessing(false);
      });
      rzp.open();
    } catch (e) {
      console.error("Razorpay initialization error:", e);
      setIsProcessing(false);
      alert("Could not launch Razorpay checkout modal.");
    }
  };

  const handleCheckout = async () => {
    if (!hasCartItems) return;
    if (!authToken) {
      const returnUrl = typeof window !== "undefined" ? (window.location.pathname + window.location.search) : "/checkout";
      router.push(`/sign-in?from=${encodeURIComponent(returnUrl)}`);
      return;
    }
    setIsProcessing(true);

    try {
      // 1. Direct Compute Token Pack Checkout via Razorpay
      if (directCheckoutItem?.type === "pack") {
        const payInfo = await api.post("/payment/purchase-tokens", {
          pack_id: directCheckoutItem.id,
          gateway: "razorpay",
        }, authToken);

        const orderObj = { id: payInfo.order_id, order_number: payInfo.order_number, total: payInfo.price };
        setInitiatedOrder(orderObj);
        setInitiatedPayment(payInfo);

        await handleOpenRazorpay(orderObj, payInfo);
        return;
      }

      // 2. Regular Marketplace Templates Checkout via Razorpay
      const order = await createOrderMutation.mutateAsync();
      setInitiatedOrder(order);

      // If order is free or completed, skip payment gateway entirely
      if (order?.status === "completed" || Number(order?.total || 0) === 0 || Number(cartTotal || 0) === 0) {
        clearCart();
        setPaymentStep("success");
        setIsProcessing(false);
        return;
      }

      const payInfo = await initiatePaymentMutation.mutateAsync({
        orderId: order.id,
        gateway: "razorpay",
      });
      setInitiatedPayment(payInfo);

      if (payInfo?.status === "completed" || payInfo?.free) {
        clearCart();
        setPaymentStep("success");
        setIsProcessing(false);
        return;
      }

      await handleOpenRazorpay(order, payInfo);
    } catch (err) {
      console.error("Checkout submission failed:", err);
      alert(err?.response?.data?.detail || err?.message || "Order creation failed. Please try again.");
      setIsProcessing(false);
    }
  };

  // Direct plan or token pack checkout extraction
  const searchParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();
  const planParam = searchParams.get("plan");
  const billingParam = searchParams.get("billing") || "annual";
  const packParam = searchParams.get("pack");

  let directCheckoutItem = null;
  const userTier = (user?.subscription_tier || "free").toLowerCase();
  const isExtremeUser = ["extreme", "agency", "enterprise"].includes(userTier);
  const isProUser = userTier === "pro";

  if (planParam && ["pro", "agency", "extreme"].includes(planParam.toLowerCase())) {
    const isPro = planParam.toLowerCase() === "pro";
    const isAnnual = billingParam.toLowerCase() === "annual";
    const monthlyRate = isPro ? (isAnnual ? 15.00 : 19.00) : (isAnnual ? 40.00 : 50.00);
    const totalPrice = isAnnual ? monthlyRate * 12 : monthlyRate;

    directCheckoutItem = {
      type: "plan",
      id: planParam.toLowerCase(),
      billingCycle: isAnnual ? "annual" : "monthly",
      title: isPro ? "Pro Creator Subscription Plan" : "Extreme Plan Subscription",
      subtitle: isPro
        ? `150 Gemini AI Credits / mo · 3 Live Deployments · 1 Site Auto-Heal · 40% Token Discount (${isAnnual ? "Billed Annually ($180/yr)" : "$19.00 / month"})`
        : `1,000+ Gemini AI Credits / mo · Free Deployments · Unlimited Auto-Heal · Template Reselling (${isAnnual ? "Billed Annually ($480/yr)" : "$50.00 / month"})`,
      price: totalPrice,
      monthlyPrice: monthlyRate,
      badge: isPro ? "✦ Pro Creator Subscription" : "⚡ Extreme Plan Subscription",
      thumbnail: isPro
        ? "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80"
        : "https://images.unsplash.com/photo-1634017839464-5c339ebe3cb4?w=600&auto=format&fit=crop&q=80",
    };
  } else if (packParam && ["tokens_50", "tokens_200", "tokens_500"].includes(packParam.toLowerCase())) {
    const packsMap = {
      tokens_50: {
        price: isExtremeUser ? 4.00 : isProUser ? 6.00 : 10.00,
        credits: 50,
        title: "Starter Compute Pack (50 Gemini Tokens)",
        subtitle: isExtremeUser
          ? "50 Gemini AI Credits (Extreme Tier 60% Discount Applied)"
          : isProUser
          ? "50 Gemini AI Credits (Pro Tier 40% Discount Applied)"
          : "50 Gemini AI Credits for section fills, code generation, and repairs",
        badge: isExtremeUser ? "Extreme 60% OFF" : isProUser ? "Pro 40% OFF" : "AI Compute Pack",
      },
      tokens_200: {
        price: isExtremeUser ? 12.00 : isProUser ? 18.00 : 30.00,
        credits: 200,
        title: "Creator Compute Pack (200 Gemini Tokens)",
        subtitle: isExtremeUser
          ? "200 Gemini AI Credits (Extreme Tier 60% Discount Applied)"
          : isProUser
          ? "200 Gemini AI Credits (Pro Tier 40% Discount Applied)"
          : "200 Gemini AI Credits for continuous multi-site builds and revisions",
        badge: isExtremeUser ? "Extreme 60% OFF" : isProUser ? "Pro 40% OFF" : "Popular Compute Pack",
      },
      tokens_500: {
        price: isExtremeUser ? 24.00 : isProUser ? 35.00 : 60.00,
        credits: 500,
        title: "Studio Fleet Pack (500 Gemini Tokens)",
        subtitle: isExtremeUser
          ? "500 Gemini AI Credits (Extreme Tier 60% Discount Applied)"
          : isProUser
          ? "500 Gemini AI Credits (Pro Tier 40% Discount Applied)"
          : "500 Gemini AI Credits for high-volume builds and full-scale deployments",
        badge: isExtremeUser ? "Extreme 60% OFF" : isProUser ? "Pro 40% OFF" : "Fleet Compute Pack",
      },
    };
    const p = packsMap[packParam.toLowerCase()];
    if (p) {
      directCheckoutItem = {
        type: "pack",
        id: packParam.toLowerCase(),
        title: p.title,
        subtitle: p.subtitle,
        price: p.price,
        credits: p.credits,
        badge: p.badge,
        thumbnail: "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=600&auto=format&fit=crop&q=80",
      };
    }
  }

  const hasCartItems = Boolean(directCheckoutItem || items.length > 0);

  // Pricing calculation - strictly template fee (zero extra tax)
  const cartSubtotal = directCheckoutItem ? directCheckoutItem.price : subtotal();
  const cartTax = 0;
  const cartTotal = cartSubtotal;
  const totalItemCount = directCheckoutItem ? 1 : items.reduce((sum, i) => sum + (i.quantity || 1), 0);
  const taxDetails = typeof getTaxDetails === "function" ? getTaxDetails() : null;

  // Active currency dynamically based on detected country (or UPI gateway)
  const activeCurrency = (
    paymentGateway === "upi"
      ? "INR"
      : userCurrency || taxDetails?.currency || "USD"
  ).toUpperCase();

  // Exchange rates with fallback support
  const exchangeRates = {
    USD: 1.0,
    INR: liveRate || 94.834,
    EUR: rates?.EUR || 0.92,
    GBP: rates?.GBP || 0.78,
    CAD: rates?.CAD || 1.36,
    AUD: rates?.AUD || 1.52,
    JPY: rates?.JPY || 154.20,
    AED: rates?.AED || 3.67,
    SGD: rates?.SGD || 1.34,
    BRL: rates?.BRL || 5.65,
  };

  // Currency Formatter - dynamically converts and formats according to country currency
  const formatMoney = (usdAmount) => {
    const num = Number(usdAmount) || 0;
    const curr = activeCurrency;
    const rate = exchangeRates[curr] || 1.0;
    const converted = num * rate;

    if (curr === "INR") {
      return `₹${converted.toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }
    if (curr === "EUR") {
      return `€${converted.toLocaleString("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }
    if (curr === "GBP") {
      return `£${converted.toLocaleString("en-GB", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }
    if (curr === "CAD") {
      return `CA$${converted.toLocaleString("en-CA", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }
    if (curr === "AUD") {
      return `AU$${converted.toLocaleString("en-AU", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }
    if (curr === "JPY") {
      return `¥${Math.round(converted).toLocaleString("ja-JP")}`;
    }
    if (curr === "SGD") {
      return `S$${converted.toLocaleString("en-SG", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }
    if (curr === "AED") {
      return `AED ${converted.toLocaleString("en-AE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }
    // Default USD
    return `$${converted.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const formattedTotalString = formatMoney(cartTotal);
  const inrAmountVal = cartTotal * liveRate;
  const inrAmountString = `₹${inrAmountVal.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;


  // Helper to add sample templates if cart is empty for immediate testing
  const addSampleTemplates = () => {
    addItem({
      templateId: "luxury-hotel-exclusive-accommodations",
      title: "Luxury Hotel - RR Residency",
      subtitle: "Exclusive Accommodation Website Template",
      price: 49,
      price_currency: "USD",
      thumbnail: "/landing/modern_villa.jpg",
      framework: "HTML5 / CSS / JS",
      licenseType: "Lifetime Access",
    });
    addItem({
      templateId: "crime-designed-portfolio",
      title: "Crime Designed Portfolio",
      subtitle: "Modern Portfolio Template",
      price: 5,
      price_currency: "USD",
      thumbnail: "/landing/template_ecommerce.png",
      framework: "HTML5 / CSS / JS",
      licenseType: "Lifetime Access",
    });
  };

  return (
    <>
      <Navbar />
      <div className="checkout-page">
        {/* Ambient Radial Background Glows */}
        <div className="cart-ambient-glow top-left" />
        <div className="cart-ambient-glow top-right" />
        <div className="cart-ambient-glow center" />

        <div className="checkout-container">
          {/* Top Bar Navigation */}
          <div className="cart-top-bar">
            <div className="cart-top-left-group">
              <Link href="/marketplace" className="cart-continue-btn">
                <ArrowLeft size={13} />
                <span>Continue Shopping</span>
              </Link>
              <div className="cart-title-inline-group">
                <h1 className="cart-heading-title">Your Shopping Cart</h1>
                <span className="cart-heading-separator">•</span>
                <p className="cart-heading-subtitle">
                  <span>Review your items before proceeding to checkout</span>
                  <Sparkles size={13} className="cart-sparkle-icon" />
                </p>
              </div>
            </div>
          </div>

          {paymentStep === "success" ? (
            <div className="checkout-success-card">
              <div
                style={{
                  width: "4rem",
                  height: "4rem",
                  borderRadius: "50%",
                  backgroundColor: "rgba(16, 185, 129, 0.1)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#10b981",
                }}
              >
                <ShieldCheck className="w-10 h-10 text-emerald-500" />
              </div>
              <h1 className="text-2xl font-bold text-foreground">Payment Successful!</h1>
              <p className="text-sm text-muted-foreground">
                Your order <strong>#{initiatedOrder?.order_number || "ASS-ORDER"}</strong> has been processed
                successfully.
              </p>
              <div className="p-3 my-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-200 text-center max-w-md mx-auto">
                <strong>✦ Lifetime Download Access:</strong> Your template files are permanently available with unlimited lifetime re-downloads directly from your Dashboard.
              </div>
              <div className="p-3.5 my-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-200 text-left max-w-lg mx-auto">
                <div className="font-bold text-emerald-300 flex items-center gap-1.5 mb-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" /> Commercial License Active (Zero Watermarks):
                </div>
                <ul className="space-y-1 text-[11.5px] text-emerald-100/90 list-disc pl-4">
                  <li><strong>100% Clean Source:</strong> All watermarks and platform attribution badges are completely removed.</li>
                  <li><strong>Commercial Client Rights:</strong> Deploy for unlimited personal, business, or client production projects.</li>
                  <li><strong>Lifetime Access:</strong> Re-download anytime directly from your Purchases dashboard.</li>
                </ul>
              </div>
              <p className="text-xs text-muted-foreground animate-pulse">
                Templates are being downloaded automatically. Redirecting to your dashboard...
              </p>
              <Link href="/dashboard" className="cart-browse-btn" style={{ width: "200px" }}>
                Go to Dashboard
              </Link>
            </div>
          ) : (
            /* Main Cart 2-Column Grid Layout */
            <div className="cart-main-grid">
              {/* Left Column: Cart Items, Promo Code, Payment Selection */}
              <div className="cart-left-col">
                {/* 1. Cart Items Box */}
                <div className="cart-glass-card">
                  <div className="cart-card-header">
                    <div className="cart-card-title-wrap">
                      <ShoppingCart className="w-5 h-5 cart-card-title-icon" />
                      <span>Cart Items ({totalItemCount})</span>
                    </div>
                    {hasCartItems && (
                      <button
                        type="button"
                        onClick={() => { if (directCheckoutItem) { window.location.href = "/checkout"; } else { clearCart(); } }}
                        className="cart-clear-all-btn"
                        title="Remove all items from cart"
                      >
                        <Trash2 size={14} />
                        <span>Clear Cart</span>
                      </button>
                    )}
                  </div>

                  {!hasCartItems ? (
                    <div className="cart-empty-box">
                      <div className="cart-empty-icon">
                        <ShoppingBag size={28} />
                      </div>
                      <h3 className="cart-empty-title">Your cart is empty</h3>
                      <p className="cart-empty-subtitle">
                        Discover top-selling templates and bring your dream website to life.
                      </p>
                      <div className="flex gap-3 flex-wrap justify-center">
                        <Link href="/marketplace" className="cart-browse-btn">
                          Browse Marketplace →
                        </Link>
                        <button
                          type="button"
                          onClick={addSampleTemplates}
                          className="px-4 py-2 rounded-xl text-xs font-semibold text-[#dfb180] bg-[#c89666]/10 border border-[#c89666]/30 hover:bg-[#c89666]/20 cursor-pointer"
                        >
                          + Add Sample Items from Mockup
                        </button>
                      </div>
                    </div>
                  ) : directCheckoutItem ? (
                    <div className="cart-items-stack">
                      <div className="cart-item-card" style={{ borderColor: "rgba(200, 150, 102, 0.4)", background: "rgba(18, 18, 22, 0.85)" }}>
                        <div className="cart-item-info-group">
                          <div className="cart-item-thumb">
                            <img
                              src={directCheckoutItem.thumbnail}
                              alt={directCheckoutItem.title}
                            />
                          </div>
                          <div className="cart-item-details">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30">
                                {directCheckoutItem.badge}
                              </span>
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                                Authenticated & Locked
                              </span>
                            </div>
                            <h3 className="cart-item-title text-base">{directCheckoutItem.title}</h3>
                            <p className="cart-item-subtitle">{directCheckoutItem.subtitle}</p>
                            <div className="cart-item-badges mt-2">
                              <span className="cart-badge-lifetime">
                                <Zap size={12} className="text-[#dfb180]" />
                                <span>Instant Activation</span>
                              </span>
                              <span className="cart-badge-framework">
                                {directCheckoutItem.type === "plan" ? "Monthly Subscription" : "Gemini AI Tokens"}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="cart-item-actions-group">
                          <span className="cart-item-price-val text-xl font-bold text-white">
                            {formatMoney(directCheckoutItem.price)}
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="cart-items-stack">
                      {items.map((item) => {
                        const itemTotalUsd = (Number(item.price) || 0) * (item.quantity || 1);
                        return (
                          <div key={item.templateId || item.id} className="cart-item-card">
                            <div className="cart-item-info-group">
                              <div className="cart-item-thumb">
                                <img
                                  src={item.thumbnail || item.thumbnail_url || "/landing/template_saas.png"}
                                  alt={item.title}
                                  onError={(e) => {
                                    e.target.onerror = null;
                                    e.target.src = "/landing/modern_villa.jpg";
                                  }}
                                />
                              </div>
                              <div className="cart-item-details">
                                <h3 className="cart-item-title">{item.title}</h3>
                                <p className="cart-item-subtitle">
                                  {item.subtitle || "Exclusive Accommodation Website Template"}
                                </p>
                                <div className="cart-item-badges">
                                  <span className="cart-badge-lifetime">
                                    <Crown size={12} className="text-amber-400" />
                                    <span>Lifetime Access</span>
                                  </span>
                                  <span className="cart-badge-framework">
                                    {item.framework || "HTML5 / CSS / JS"}
                                  </span>
                                  <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                                    ✦ Commercial License (Zero Watermark)
                                  </span>
                                </div>
                              </div>
                            </div>

                            <div className="cart-item-actions-group">
                              <span className="cart-item-price-val">
                                {formatMoney(itemTotalUsd)}
                              </span>

                              <button
                                type="button"
                                onClick={() => removeItem(item.templateId || item.id)}
                                className="cart-delete-item-btn"
                                title="Remove template"
                              >
                                <Trash2 size={16} />
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>


                {/* 3. Select Payment Method Card */}
                {hasCartItems && Number(cartTotal || 0) === 0 ? (
                  <div className="cart-glass-card p-5 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 space-y-2">
                    <div className="flex items-center gap-2 text-emerald-400 font-bold text-base">
                      <Check className="w-5 h-5 shrink-0" />
                      <span>100% Free Marketplace Download</span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      All marketplace templates are currently available with direct source code download access.
                      No credit card, UPI, or payment details are needed. Click <strong>Confirm &amp; Download Templates</strong> below to complete your order and download immediately.
                    </p>
                  </div>
                ) : hasCartItems && (
                  <div className="cart-glass-card cart-payment-methods-card p-5 rounded-2xl border border-primary/30 bg-primary/5 space-y-3">
                    <div className="flex items-center justify-between pb-3 border-b border-border/50">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                          <CreditCard className="w-4 h-4" />
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-foreground">Razorpay Secure Checkout</h4>
                          <p className="text-[11px] text-muted-foreground">Domestic &amp; International Payment Processing</p>
                        </div>
                      </div>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3" /> 256-Bit SSL
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-xs text-muted-foreground">
                      <div className="flex items-center gap-1.5 p-2 rounded-lg bg-background/50 border border-border/60">
                        <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span>Credit / Debit Cards</span>
                      </div>
                      <div className="flex items-center gap-1.5 p-2 rounded-lg bg-background/50 border border-border/60">
                        <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span>UPI (GPay / PhonePe)</span>
                      </div>
                      <div className="flex items-center gap-1.5 p-2 rounded-lg bg-background/50 border border-border/60">
                        <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span>NetBanking (50+ Banks)</span>
                      </div>
                      <div className="flex items-center gap-1.5 p-2 rounded-lg bg-background/50 border border-border/60">
                        <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span>Digital Wallets</span>
                      </div>
                    </div>

                    <p className="text-[11px] text-muted-foreground leading-relaxed pt-1">
                      Clicking <strong>Pay with Razorpay</strong> will securely launch the Razorpay modal. All purchases instantly unlock 100% clean, watermark-free source code with full commercial rights.
                    </p>
                  </div>
                )}
              </div>

              {/* Right Column: 3D Bag Graphic + Order Summary Card */}
              <div className="cart-right-col">
                {/* 3D Glowing Purple Bag Illustration */}
                <div className="cart-3d-bag-wrap">
                  <div className="cart-bag-glow-aura" />
                  <span className="cart-sparkle-particle p1">✦</span>
                  <span className="cart-sparkle-particle p2">✦</span>
                  <span className="cart-sparkle-particle p3">★</span>
                  <svg
                    width="105"
                    height="105"
                    viewBox="0 0 160 160"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    className="cart-3d-bag-svg"
                  >
                    <defs>
                      <linearGradient id="bag-body-grad" x1="20" y1="40" x2="140" y2="150" gradientUnits="userSpaceOnUse">
                        <stop offset="0%" stopColor="#dfb180" />
                        <stop offset="50%" stopColor="#c89666" />
                        <stop offset="100%" stopColor="#b5804f" />
                      </linearGradient>
                      <linearGradient id="bag-front-sheen" x1="50" y1="50" x2="110" y2="140" gradientUnits="userSpaceOnUse">
                        <stop offset="0%" stopColor="#f4ecdf" stopOpacity="0.8" />
                        <stop offset="60%" stopColor="#dfb180" stopOpacity="0.4" />
                        <stop offset="100%" stopColor="#29180b" stopOpacity="0.9" />
                      </linearGradient>
                      <linearGradient id="bag-handle-grad" x1="45" y1="10" x2="115" y2="50" gradientUnits="userSpaceOnUse">
                        <stop offset="0%" stopColor="#faf7f2" />
                        <stop offset="40%" stopColor="#e8d7be" />
                        <stop offset="100%" stopColor="#c89666" />
                      </linearGradient>
                      <filter id="bag-shadow" x="0" y="0" width="160" height="160" filterUnits="userSpaceOnUse">
                        <feDropShadow dx="0" dy="8" stdDeviation="10" floodColor="#000000" floodOpacity="0.5" />
                      </filter>
                    </defs>

                    {/* Handle */}
                    <path
                      d="M56 50 C56 22, 104 22, 104 50"
                      stroke="url(#bag-handle-grad)"
                      strokeWidth="8"
                      strokeLinecap="round"
                      fill="none"
                    />

                    {/* Bag Main Body */}
                    <g filter="url(#bag-shadow)">
                      <path
                        d="M32 50 L128 50 L140 142 C140 148, 134 152, 126 152 L34 152 C26 152, 20 148, 20 142 Z"
                        fill="url(#bag-body-grad)"
                      />
                      {/* Front Facet / 3D Bevel */}
                      <path
                        d="M36 54 L124 54 L132 144 C132 148, 128 150, 122 150 L38 150 C32 150, 28 148, 28 144 Z"
                        fill="url(#bag-front-sheen)"
                      />
                      {/* Specular Highlight Streak */}
                      <path
                        d="M42 60 L65 60 L55 142 L38 142 Z"
                        fill="#ffffff"
                        fillOpacity="0.18"
                      />
                    </g>
                  </svg>
                </div>

                {/* Order Summary Card */}
                <div className="cart-glass-card cart-summary-card">
                  <div className="cart-summary-header">
                    <ClipboardList size={20} className="text-[#dfb180]" />
                    <span>Order Summary</span>
                  </div>

                  {/* Digital Delivery Guarantee Banner */}
                  <div className="cart-delivery-box">
                    <div className="cart-delivery-left">
                      <div className="cart-delivery-pin-box">
                        <Download size={16} />
                      </div>
                      <div className="cart-delivery-content">
                        <div className="cart-delivery-top-row">
                          <span className="cart-delivery-label">Instant Delivery</span>
                          <span className="cart-auto-detect-pill text-emerald-400">All-Inclusive</span>
                        </div>
                        <span className="cart-delivery-country">
                          Zero Extra Fees &bull; Instant Code Download
                        </span>
                        <span className="cart-delivery-sub">
                          Full source code archive available immediately upon checkout
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Summary Breakdown */}
                  <div className="cart-summary-lines">
                    <div className="cart-summary-line">
                      <span>Subtotal ({totalItemCount} {totalItemCount === 1 ? "item" : "items"})</span>
                      <span className="cart-summary-line-val">
                        {formatMoney(grossSubtotal())}
                      </span>
                    </div>

                    {discountAmount() > 0 && (
                      <div className="cart-summary-line text-emerald-400">
                        <span>Discount ({couponCode})</span>
                        <span className="font-bold">- {formatMoney(discountAmount())}</span>
                      </div>
                    )}

                    <div className="cart-summary-divider" />

                    <div className="cart-summary-total-line">
                      <span className="cart-summary-total-label">Total Amount</span>
                      <div className="cart-summary-total-group">
                        <span className="cart-summary-total-amount">
                          {formattedTotalString}
                        </span>
                        <span className="cart-summary-approx-hint">
                          Approx. {formattedTotalString} {activeCurrency}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Pay Button */}
                  <button
                    type="button"
                    onClick={handleCheckout}
                    disabled={!hasCartItems || isProcessing}
                    className="cart-checkout-cta-btn"
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="animate-spin" size={18} />
                        <span>Processing Session…</span>
                      </>
                    ) : !authToken ? (
                      <>
                        <Lock size={16} />
                        <span>Sign In to Complete Order ({formattedTotalString})</span>
                        <ChevronRight size={16} />
                      </>
                    ) : Number(cartTotal || 0) === 0 ? (
                      <>
                        <Download size={18} />
                        <span>Confirm &amp; Download Templates (Free)</span>
                        <ChevronRight size={16} />
                      </>
                    ) : (
                      <>
                        <Lock size={16} />
                        <span>Pay with Razorpay ({formattedTotalString})</span>
                        <ChevronRight size={16} />
                      </>
                    )}
                  </button>

                  {/* SSL Guarantee */}
                  <div className="cart-ssl-guarantee">
                    <ShieldCheck size={14} className="cart-ssl-icon" />
                    <span>Secure 256-bit SSL encrypted checkout</span>
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
