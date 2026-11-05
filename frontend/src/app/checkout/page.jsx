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
import { QRCodeSVG } from "qrcode.react";
import {
  CreditCard,
  ShoppingBag,
  ShoppingCart,
  ShieldCheck,
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

  const [paymentGateway, setPaymentGateway] = useState("upi"); // "upi" | "razorpay" | "stripe"
  const [authToken, setAuthToken] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentStep, setPaymentStep] = useState("cart"); // "cart" | "paying" | "success"
  const [freeDownloadsComplete, setFreeDownloadsComplete] = useState(false);
  const [initiatedOrder, setInitiatedOrder] = useState(null);
  const [initiatedPayment, setInitiatedPayment] = useState(null);
  const [vpaCopied, setVpaCopied] = useState(false);
  const [upiUtr, setUpiUtr] = useState("");
  const [upiUtrSubmitted, setUpiUtrSubmitted] = useState(false);
  const [utrError, setUtrError] = useState("");
  const [promoInput, setPromoInput] = useState("");

  // 5-minute QR Code timer & auto-refresh state
  const [qrTimerSeconds, setQrTimerSeconds] = useState(300);
  const [qrNonce, setQrNonce] = useState(`${Date.now()}_${Math.random().toString(36).substring(2, 7)}`);
  const [qrRefreshedNotice, setQrRefreshedNotice] = useState(false);
  const [isRefreshingQr, setIsRefreshingQr] = useState(false);

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

  // Sync active payment gateway with detected region
  useEffect(() => {
    if (countryCode && countryCode !== "IN") {
      setPaymentGateway("stripe");
    } else if (countryCode === "IN") {
      setPaymentGateway("upi");
    }
  }, [countryCode]);

  useEffect(() => {
    getToken().then(setAuthToken).catch(() => { });
    api
      .get("/payment/exchange-rate")
      .then((res) => {
        if (res?.rate) setLiveRate(res.rate);
      })
      .catch(() => { });

    // Check if returning from Stripe Checkout
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const paymentParam = params.get("payment");
      const orderIdParam = params.get("order_id");
      const sessionIdParam = params.get("session_id");

      if (paymentParam === "stripe_success" && orderIdParam) {
        getToken().then(async (token) => {
          if (!token) return;
          setIsProcessing(true);
          try {
            const verifyRes = await api.post(
              "/payment/verify",
              {
                gateway: "stripe",
                gateway_payment_id: sessionIdParam || "stripe_checkout",
                gateway_order_id: sessionIdParam || orderIdParam,
                order_id: orderIdParam,
              },
              token
            );
            if (verifyRes?.success) {
              const statusRes = await api.get(`/payment/status/${orderIdParam}`, token);
              handleCompleteSuccessFlow({ id: orderIdParam, items: statusRes?.items || [] });
            }
          } catch (e) {
            console.error("Stripe return verification error", e);
          } finally {
            setIsProcessing(false);
          }
        });
      }
    }
  }, []);

  // Real-time polling effect for UPI payment status
  useEffect(() => {
    let interval;
    if (paymentStep === "paying" && initiatedOrder?.id && authToken) {
      interval = setInterval(async () => {
        try {
          const res = await api.get(`/payment/status/${initiatedOrder.id}`, authToken);
          if (res?.is_paid) {
            handleCompleteSuccessFlow(initiatedOrder);
          } else if (res?.payment_status === "failed" && upiUtrSubmitted) {
            setUpiUtrSubmitted(false);
            setUtrError(
              "The submitted payment reference was not approved. Check it and contact support if you believe this is incorrect."
            );
          }
        } catch (e) {
          // Silent catch for background polling
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [paymentStep, initiatedOrder, authToken, upiUtrSubmitted]);

  // QR Timer Countdown
  useEffect(() => {
    if (paymentStep !== "paying" || paymentGateway !== "upi") {
      setQrTimerSeconds(300);
      return;
    }

    const interval = setInterval(() => {
      setQrTimerSeconds((prev) => {
        if (prev <= 1) {
          const freshNonce = `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
          setQrNonce(freshNonce);
          setQrRefreshedNotice(true);
          setTimeout(() => setQrRefreshedNotice(false), 4000);
          return 300;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [paymentStep, paymentGateway]);

  const handleManualRefreshQr = async () => {
    setIsRefreshingQr(true);
    const freshNonce = `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    setQrNonce(freshNonce);
    setQrTimerSeconds(300);
    setQrRefreshedNotice(true);

    try {
      const res = await api.get("/payment/exchange-rate");
      if (res?.rate) setLiveRate(res.rate);
    } catch (e) {
      // ignore
    }

    setTimeout(() => {
      setIsRefreshingQr(false);
    }, 400);

    setTimeout(() => {
      setQrRefreshedNotice(false);
    }, 4000);
  };

  const copyVpaToClipboard = (vpaText) => {
    navigator.clipboard.writeText(vpaText);
    setVpaCopied(true);
    setTimeout(() => setVpaCopied(false), 2000);
  };

  const handleCompleteSuccessFlow = async (orderToProcess) => {
    const ord = orderToProcess || initiatedOrder;
    if (!ord) return;

    for (const item of ord.items || []) {
      try {
        const res = await api.post(`/templates/${item.template_id}/download?format=zip`, {}, authToken);
        if (res?.download_url) {
          const link = document.createElement("a");
          link.href = res.download_url;
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
    const loaded = await loadRazorpayScript();
    if (!loaded) {
      alert("Failed to load Razorpay SDK. Please check your internet connection.");
      setIsProcessing(false);
      return;
    }

    const options = {
      key: targetPay.key_id,
      amount: targetPay.amount,
      currency: targetPay.currency || "INR",
      name: "AI Site Studio",
      description: `Order #${targetOrder.id?.slice(0, 8)}`,
      order_id: targetPay.gateway_order_id,
      prefill: {
        name: user?.name || user?.email?.split("@")[0] || "",
        email: user?.email || "",
      },
      theme: { color: "#8b5cf6" },
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

    const activeGateway = ENABLE_EXTERNAL_GATEWAYS ? paymentGateway : "upi";

    try {
      // 1. Direct Subscription Plan Checkout
      if (directCheckoutItem?.type === "plan") {
        const payInfo = await api.post("/payment/purchase-plan", {
          plan_id: directCheckoutItem.id,
          billing_cycle: directCheckoutItem.billingCycle || "monthly",
          gateway: activeGateway,
        }, authToken);

        const orderObj = { id: payInfo.order_id, order_number: payInfo.order_number, total: payInfo.price };
        setInitiatedOrder(orderObj);
        setInitiatedPayment(payInfo);

        if (activeGateway === "razorpay") {
          await handleOpenRazorpay(orderObj, payInfo);
        } else if (activeGateway === "stripe") {
          if (payInfo?.checkout_url) {
            window.location.href = payInfo.checkout_url;
          } else {
            alert("Stripe checkout session creation failed.");
            setIsProcessing(false);
          }
        } else {
          // UPI QR
          setPaymentStep("paying");
          setIsProcessing(false);
        }
        return;
      }

      // 2. Direct Compute Token Pack Checkout
      if (directCheckoutItem?.type === "pack") {
        const payInfo = await api.post("/payment/purchase-tokens", {
          pack_id: directCheckoutItem.id,
          gateway: activeGateway,
        }, authToken);

        const orderObj = { id: payInfo.order_id, order_number: payInfo.order_number, total: payInfo.price };
        setInitiatedOrder(orderObj);
        setInitiatedPayment(payInfo);

        if (activeGateway === "razorpay") {
          await handleOpenRazorpay(orderObj, payInfo);
        } else if (activeGateway === "stripe") {
          if (payInfo?.checkout_url) {
            window.location.href = payInfo.checkout_url;
          } else {
            alert("Stripe checkout session creation failed.");
            setIsProcessing(false);
          }
        } else {
          // UPI QR
          setPaymentStep("paying");
          setIsProcessing(false);
        }
        return;
      }

      // 3. Regular Marketplace Templates Checkout
      const order = await createOrderMutation.mutateAsync();
      setInitiatedOrder(order);

      const payInfo = await initiatePaymentMutation.mutateAsync({
        orderId: order.id,
        gateway: activeGateway,
      });
      setInitiatedPayment(payInfo);

      if (activeGateway === "razorpay") {
        await handleOpenRazorpay(order, payInfo);
      } else if (activeGateway === "stripe") {
        if (payInfo?.checkout_url) {
          window.location.href = payInfo.checkout_url;
        } else {
          alert("Stripe checkout session creation failed.");
          setIsProcessing(false);
        }
      } else {
        // UPI QR
        setPaymentStep("paying");
        setIsProcessing(false);
      }
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
  if (planParam && ["pro", "agency"].includes(planParam.toLowerCase())) {
    const isPro = planParam.toLowerCase() === "pro";
    const isAnnual = billingParam.toLowerCase() === "annual";
    const monthlyRate = isPro ? (isAnnual ? 15.00 : 19.00) : (isAnnual ? 39.00 : 49.00);
    const totalPrice = isAnnual ? monthlyRate * 12 : monthlyRate;

    directCheckoutItem = {
      type: "plan",
      id: planParam.toLowerCase(),
      billingCycle: isAnnual ? "annual" : "monthly",
      title: isPro ? "Pro Creator Subscription Plan" : "Agency & Scale Subscription Plan",
      subtitle: isPro
        ? `150 Gemini AI Credits / mo · 3 Live Deployments · AI Doctor Healing (${isAnnual ? "Billed Annually ($180/yr)" : "$19.00 / month"})`
        : `500 Gemini AI Credits / mo · Unlimited Deployments · Custom Domains + SSL (${isAnnual ? "Billed Annually ($468/yr)" : "$49.00 / month"})`,
      price: totalPrice,
      monthlyPrice: monthlyRate,
      badge: isPro ? "✦ Pro Creator Subscription" : "✦ Agency & Scale Subscription",
      thumbnail: isPro
        ? "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80"
        : "https://images.unsplash.com/photo-1634017839464-5c339ebe3cb4?w=600&auto=format&fit=crop&q=80",
    };
  } else if (packParam && ["tokens_50", "tokens_200", "tokens_500"].includes(packParam.toLowerCase())) {
    const packsMap = {
      tokens_50: {
        price: 5.00,
        credits: 50,
        title: "Starter Compute Pack (50 Gemini Tokens)",
        subtitle: "50 Gemini AI Credits for autonomous repairs, code analysis, and AI Fill edits",
        badge: "AI Compute Pack",
      },
      tokens_200: {
        price: 15.00,
        credits: 200,
        title: "Pro Creator Compute Pack (200 Gemini Tokens)",
        subtitle: "200 Gemini AI Credits for heavy multi-site workflows and instant healing (Save 25%)",
        badge: "Popular Compute Pack",
      },
      tokens_500: {
        price: 30.00,
        credits: 500,
        title: "Studio Enterprise Pack (500 Gemini Tokens)",
        subtitle: "500 Gemini AI Credits for high-volume agency builds and multi-agent synthesis (Save 40%)",
        badge: "Enterprise Compute Pack",
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

  // Tax and pricing calculation
  const cartSubtotal = directCheckoutItem ? directCheckoutItem.price : subtotal();
  const taxDetails = getTaxDetails();
  const cartTax = directCheckoutItem ? 0 : taxDetails.taxAmount;
  const cartTotal = directCheckoutItem ? directCheckoutItem.price : taxDetails.totalAmount;
  const totalItemCount = directCheckoutItem ? 1 : items.reduce((sum, i) => sum + (i.quantity || 1), 0);

  // Active currency dynamically based on detected country (or UPI gateway)
  const activeCurrency = (
    paymentGateway === "upi"
      ? "INR"
      : taxDetails?.currency || userCurrency || "USD"
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
  const minutesLeft = Math.floor(qrTimerSeconds / 60);
  const secondsLeft = qrTimerSeconds % 60;
  const timerFormatted = `${String(minutesLeft).padStart(2, "0")}:${String(secondsLeft).padStart(2, "0")}`;
  const merchantVpa = initiatedPayment?.vpa || "sitestudio@icici";
  const merchantName = initiatedPayment?.merchant_name || "AI Site Studio";
  
  // Dynamic UPI URI ensuring refreshed nonce, unique transaction ref (tr) & timestamp are always included
  const activeUpiUri = (() => {
    const rawBase = initiatedPayment?.upi_uri;
    const orderRef = initiatedOrder?.order_number || initiatedOrder?.id?.slice(0, 8) || "ASS";
    if (rawBase) {
      const clean = rawBase
        .replace(/[?&](nonce|ts|tr)=[^&]*/g, "");
      const delimiter = clean.includes("?") ? "&" : "?";
      return `${clean}${delimiter}tr=${encodeURIComponent(orderRef + "_" + qrNonce)}&nonce=${encodeURIComponent(qrNonce)}&ts=${Date.now()}`;
    }
    return `upi://pay?pa=${encodeURIComponent(merchantVpa)}&pn=${encodeURIComponent(
      merchantName
    )}&am=${inrAmountVal.toFixed(2)}&cu=INR&tn=Order%20${encodeURIComponent(orderRef)}&tr=${encodeURIComponent(
      orderRef + "_" + qrNonce
    )}&nonce=${encodeURIComponent(qrNonce)}&ts=${Date.now()}`;
  })();

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
              {paymentStep === "paying" ? (
                <button
                  type="button"
                  onClick={() => setPaymentStep("cart")}
                  className="cart-continue-btn"
                >
                  <ArrowLeft size={13} />
                  <span>Back to Cart</span>
                </button>
              ) : (
                <Link href="/marketplace" className="cart-continue-btn">
                  <ArrowLeft size={13} />
                  <span>Continue Shopping</span>
                </Link>
              )}
              <div className="cart-title-inline-group">
                <h1 className="cart-heading-title">
                  {paymentStep === "paying" ? "UPI QR Payment" : "Your Shopping Cart"}
                </h1>
                <span className="cart-heading-separator">•</span>
                <p className="cart-heading-subtitle">
                  <span>
                    {paymentStep === "paying"
                      ? "Scan QR code or use UPI ID to complete your order"
                      : "Review your items before proceeding to checkout"}
                  </span>
                  <Sparkles size={13} className="cart-sparkle-icon" />
                </p>
              </div>
            </div>
          </div>

          {/* Paying Flow (UPI QR) */}
          {paymentStep === "paying" ? (
            <div className="checkout-paying-wrapper">
              <div className="checkout-paying-card">
                {/* Header with Title and Expiry Timer */}
                <div className="checkout-paying-header">
                  <div className="checkout-paying-title-group">
                    <div className="checkout-paying-icon-wrap">
                      <ScanQrCode className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                      <h3 className="checkout-paying-title">Pay via UPI QR Code / Apps</h3>
                      <p className="checkout-paying-sub">
                        Scan with GPay, PhonePe, Paytm, or BHIM UPI
                      </p>
                    </div>
                  </div>

                  <div className="checkout-paying-timer-bar">
                    <span
                      className={cn(
                        "checkout-timer-pill",
                        qrTimerSeconds > 60 ? "timer-active" : "timer-expiring"
                      )}
                    >
                      <Clock className="w-3.5 h-3.5" />
                      <span>{timerFormatted}</span>
                    </span>
                    <button
                      type="button"
                      onClick={handleManualRefreshQr}
                      disabled={isRefreshingQr}
                      className={cn("checkout-timer-refresh-btn", isRefreshingQr && "refreshing")}
                      title="Refresh QR Code (Generate fresh session)"
                    >
                      <RotateCcw className={cn("w-3.5 h-3.5", isRefreshingQr && "animate-spin text-purple-400")} />
                    </button>
                  </div>
                </div>

                {/* QR Refreshed Notice */}
                {qrRefreshedNotice && (
                  <div className="checkout-qr-refreshed-banner">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>QR Code &amp; 5-min session refreshed successfully!</span>
                  </div>
                )}

                {/* Amount Payable Highlight Box */}
                <div className="checkout-amount-box">
                  <div className="checkout-amount-left">
                    <span className="checkout-amount-label">Total Amount Payable</span>
                    <span className="checkout-amount-val">{formattedTotalString}</span>
                  </div>
                  <div className="checkout-order-ref-badge">
                    <span>Order #{initiatedOrder?.order_number || initiatedOrder?.id?.slice(0, 8) || "ASS-ORDER"}</span>
                  </div>
                </div>

                {/* QR Code Container */}
                <div className="checkout-qr-stage">
                  <div className={cn("checkout-qr-white-frame", isRefreshingQr && "qr-refreshing-pulse")}>
                    <QRCodeSVG
                      key={qrNonce}
                      value={activeUpiUri}
                      size={180}
                      level="H"
                      includeMargin={true}
                    />
                  </div>
                  <div className="checkout-qr-actions-row">
                    <div className="checkout-qr-scan-badge">
                      <Smartphone className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Scan with Any UPI App</span>
                    </div>
                    <button
                      type="button"
                      onClick={handleManualRefreshQr}
                      disabled={isRefreshingQr}
                      className={cn("checkout-qr-refresh-pill-btn", isRefreshingQr && "refreshing")}
                      title="Refresh QR Code & Session"
                    >
                      <RotateCcw className={cn("w-3 h-3", isRefreshingQr && "animate-spin text-purple-400")} />
                      <span>{isRefreshingQr ? "Refreshing..." : "Refresh QR"}</span>
                    </button>
                  </div>
                </div>

                {/* VPA Copy Bar */}
                <div className="checkout-vpa-row">
                  <div className="checkout-vpa-left">
                    <span className="checkout-vpa-label">UPI ID / VPA</span>
                    <span className="checkout-vpa-value">{merchantVpa}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => copyVpaToClipboard(merchantVpa)}
                    className="checkout-vpa-copy-btn"
                  >
                    {vpaCopied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy VPA</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Quick Launch UPI App Buttons */}
                <div className="checkout-upi-apps-section">
                  <span className="checkout-upi-apps-label">Or Tap to Open UPI App:</span>
                  <div className="checkout-upi-apps-grid">
                    <button
                      type="button"
                      onClick={() => window.open(activeUpiUri, "_self")}
                      className="checkout-upi-app-btn"
                    >
                      <span className="app-dot blue" />
                      <span>Google Pay</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => window.open(activeUpiUri, "_self")}
                      className="checkout-upi-app-btn"
                    >
                      <span className="app-dot purple" />
                      <span>PhonePe</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => window.open(activeUpiUri, "_self")}
                      className="checkout-upi-app-btn"
                    >
                      <span className="app-dot sky" />
                      <span>Paytm</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => window.open(activeUpiUri, "_self")}
                      className="checkout-upi-app-btn"
                    >
                      <span className="app-dot amber" />
                      <span>BHIM UPI</span>
                    </button>
                  </div>
                </div>

                {/* Step 2: UTR Reference Form */}
                <div className="checkout-utr-box">
                  {upiUtrSubmitted ? (
                    <div className="checkout-utr-success-state">
                      <CheckCircle2 className="w-7 h-7 text-emerald-400 mx-auto" />
                      <h4 className="utr-success-title">UTR Reference Submitted</h4>
                      <p className="utr-success-desc">
                        UTR <strong>{upiUtr}</strong> is recorded. An administrator will verify your transaction shortly.
                      </p>
                      <Link href="/dashboard" className="cart-browse-btn inline-block mt-2">
                        Go to Dashboard →
                      </Link>
                    </div>
                  ) : (
                    <div className="checkout-utr-form-group">
                      <div className="checkout-utr-header">
                        <span className="checkout-utr-step-tag">Step 2</span>
                        <label className="checkout-utr-title">
                          Enter 12-Digit UPI Reference (UTR)
                        </label>
                      </div>
                      <p className="checkout-utr-helper">
                        After completing the payment in your UPI app, paste the 12-digit transaction UTR number to complete:
                      </p>
                      <div className="checkout-utr-input-row">
                        <input
                          type="text"
                          maxLength={16}
                          placeholder="e.g. 431289123456"
                          value={upiUtr}
                          onChange={(e) => setUpiUtr(e.target.value.replace(/\D/g, ""))}
                          className="checkout-utr-input"
                        />
                        <button
                          type="button"
                          disabled={upiUtr.length < 10 || isProcessing}
                          onClick={async () => {
                            if (!initiatedOrder?.id) return;
                            setIsProcessing(true);
                            try {
                              await api.post(
                                "/payment/verify",
                                {
                                  gateway: "upi",
                                  gateway_payment_id: upiUtr,
                                  gateway_order_id: initiatedOrder.id,
                                  order_id: initiatedOrder.id,
                                },
                                authToken
                              );
                              setUpiUtrSubmitted(true);
                            } catch (e) {
                              alert("Failed to submit UTR reference.");
                            } finally {
                              setIsProcessing(false);
                            }
                          }}
                          className="checkout-utr-submit-btn"
                        >
                          {isProcessing ? "Verifying..." : "Submit UTR →"}
                        </button>
                      </div>
                      {utrError && <p className="text-xs text-rose-400 mt-1">{utrError}</p>}
                    </div>
                  )}
                </div>

                {/* Footer / Return Button */}
                <div className="checkout-paying-footer">
                  <button
                    type="button"
                    onClick={() => setPaymentStep("cart")}
                    className="checkout-return-cart-btn"
                  >
                    ← Return to Cart &amp; Change Payment Method
                  </button>
                  <div className="checkout-paying-ssl-badge">
                    <ShieldCheck size={13} className="text-emerald-400" />
                    <span>256-Bit SSL Encrypted &amp; Verified</span>
                  </div>
                </div>
              </div>
            </div>
          ) : paymentStep === "success" ? (
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
                          className="px-4 py-2 rounded-xl text-xs font-semibold text-purple-300 bg-purple-500/10 border border-purple-500/30 hover:bg-purple-500/20 cursor-pointer"
                        >
                          + Add Sample Items from Mockup
                        </button>
                      </div>
                    </div>
                  ) : directCheckoutItem ? (
                    <div className="cart-items-stack">
                      <div className="cart-item-card" style={{ borderColor: "rgba(168, 85, 247, 0.4)", background: "rgba(18, 14, 38, 0.85)" }}>
                        <div className="cart-item-info-group">
                          <div className="cart-item-thumb">
                            <img
                              src={directCheckoutItem.thumbnail}
                              alt={directCheckoutItem.title}
                            />
                          </div>
                          <div className="cart-item-details">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-purple-500/15 text-purple-300 border border-purple-500/30">
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
                                <Zap size={12} className="text-purple-400" />
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
                {hasCartItems && (
                  <div className="cart-glass-card cart-payment-methods-card">
                    <div className="cart-payment-header">
                      <div className="cart-payment-title">
                        <CreditCard size={18} className="text-purple-400" />
                        <span>Select Payment Method</span>
                      </div>
                      <div className="cart-payment-secure-badge">
                        <Check size={14} />
                        <span>Secure & Encrypted</span>
                      </div>
                    </div>

                    <div className="cart-payment-tabs-grid">
                      {/* Tab 1: UPI QR & Apps */}
                      <button
                        type="button"
                        onClick={() => setPaymentGateway("upi")}
                        className={cn("cart-payment-tab-btn", paymentGateway === "upi" && "active")}
                      >
                        {countryCode === "IN" && (
                          <span className="cart-recommended-pill">Recommended</span>
                        )}
                        <ScanQrCode size={18} className="text-emerald-400 shrink-0" />
                        <span>UPI QR {countryCode !== "IN" ? "(India Only)" : "& Apps"}</span>
                      </button>

                      {/* Tab 2: Credit / Debit Card (Razorpay) */}
                      <button
                        type="button"
                        onClick={() => setPaymentGateway("razorpay")}
                        className={cn("cart-payment-tab-btn", paymentGateway === "razorpay" && "active")}
                      >
                        <CreditCard size={18} className="text-indigo-400 shrink-0" />
                        <span>Credit / Debit Card</span>
                      </button>

                      {/* Tab 3: Cards & Global (Stripe) */}
                      <button
                        type="button"
                        onClick={() => setPaymentGateway("stripe")}
                        className={cn("cart-payment-tab-btn", paymentGateway === "stripe" && "active")}
                      >
                        {countryCode !== "IN" && (
                          <span className="cart-recommended-pill">Recommended</span>
                        )}
                        <Globe size={18} className="text-sky-400 shrink-0" />
                        <span>Cards & Global</span>
                      </button>
                    </div>

                    <p className="cart-payment-notice">
                      <HelpCircle size={14} className="text-purple-400 shrink-0" />
                      <span>
                        {paymentGateway === "upi"
                          ? "UPI reference will be reviewed by an administrator before order completion."
                          : paymentGateway === "razorpay"
                            ? "Instant activation via Domestic & International Visa, MasterCard, RuPay, and NetBanking."
                            : "Encrypted global checkout via Stripe with instant license delivery."}
                      </span>
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
                        <stop offset="0%" stopColor="#9333ea" />
                        <stop offset="50%" stopColor="#7c3aed" />
                        <stop offset="100%" stopColor="#4f46e5" />
                      </linearGradient>
                      <linearGradient id="bag-front-sheen" x1="50" y1="50" x2="110" y2="140" gradientUnits="userSpaceOnUse">
                        <stop offset="0%" stopColor="#c084fc" stopOpacity="0.8" />
                        <stop offset="60%" stopColor="#7c3aed" stopOpacity="0.4" />
                        <stop offset="100%" stopColor="#312e81" stopOpacity="0.9" />
                      </linearGradient>
                      <linearGradient id="bag-handle-grad" x1="45" y1="10" x2="115" y2="50" gradientUnits="userSpaceOnUse">
                        <stop offset="0%" stopColor="#f3e8ff" />
                        <stop offset="40%" stopColor="#c084fc" />
                        <stop offset="100%" stopColor="#6366f1" />
                      </linearGradient>
                      <filter id="bag-shadow" x="0" y="0" width="160" height="160" filterUnits="userSpaceOnUse">
                        <feDropShadow dx="0" dy="8" stdDeviation="10" floodColor="#7c3aed" floodOpacity="0.5" />
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
                    <ClipboardList size={20} className="text-purple-400" />
                    <span>Order Summary</span>
                  </div>

                  {/* Delivering To / Location Box - Auto-detected */}
                  <div className="cart-delivery-box">
                    <div className="cart-delivery-left">
                      <div className="cart-delivery-pin-box">
                        <MapPin size={16} />
                      </div>
                      <div className="cart-delivery-content">
                        <div className="cart-delivery-top-row">
                          <span className="cart-delivery-label">Delivering to</span>
                          <span className="cart-auto-detect-pill">Auto-detected</span>
                        </div>
                        <span className="cart-delivery-country">
                          {taxDetails.flag} {taxDetails.countryName}
                        </span>
                        <span className="cart-delivery-sub">
                          {taxDetails.label} &bull; Applied automatically based on your location
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

                    <div className="cart-summary-line">
                      <span className="flex items-center gap-1">
                        <span>Country Tax ({taxDetails.label})</span>
                        <HelpCircle size={13} className="text-slate-400" />
                      </span>
                      <span className="cart-summary-tax-val">
                        + {formatMoney(cartTax)}
                      </span>
                    </div>

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
                    ) : paymentGateway === "upi" ? (
                      <>
                        <Lock size={16} />
                        <span>Pay via UPI QR ({formattedTotalString})</span>
                        <ChevronRight size={16} />
                      </>
                    ) : paymentGateway === "razorpay" ? (
                      <>
                        <Lock size={16} />
                        <span>Pay with Card ({formattedTotalString})</span>
                        <ChevronRight size={16} />
                      </>
                    ) : (
                      <>
                        <Lock size={16} />
                        <span>Pay with Stripe ({formattedTotalString})</span>
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
