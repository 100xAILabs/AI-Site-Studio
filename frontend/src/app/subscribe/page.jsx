"use client";

import { useState, useEffect } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import {
  ShieldCheck,
  CheckCircle2,
  Sparkles,
  Zap,
  ArrowLeft,
  CreditCard,
  Loader2,
  Crown,
  Lock,
  Check,
  Cpu,
  Globe,
  HeartHandshake,
  ArrowRight,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useAppAuth, useAppUser } from "@/lib/auth";
import { api } from "@/lib/api";
import { formatPrice } from "@/lib/utils";
import "./Page.css";

const PLAN_DATA = {
  pro: {
    id: "pro",
    name: "Pro Plan",
    badge: "✦ Most Popular for Creators",
    description: "Ideal for web creators and freelancers who need clean, unbranded code, live edge deployments, and autonomous site healing.",
    monthlyPrice: 19,
    annualPrice: 15,
    tokens: 150,
    deployments: 3,
    color: "#c89666",
    features: [
      "Download all templates without watermarks (Clean Source Code)",
      "150 Gemini AI Credits / month for site generation & AI Fill edits",
      "Discounted AI token top-ups (40% OFF standard rates)",
      "Deploy up to 3 live websites on high-speed edge hosting",
      "Autonomous AI Site Doctor healing for 1 registered live site",
      "Full canvas editor access with unlimited copy & styling revisions",
      "Instant Studio subdomains (*.aisitestudio.com) with SSL",
      "Priority email & community developer support",
    ],
  },
  extreme: {
    id: "extreme",
    name: "Extreme Plan",
    badge: "⚡ Extreme — Full Platform Power",
    description: "Maximum power: generate multi-page sites with zero friction, unlimited hosting deployments, and resell your customized templates.",
    monthlyPrice: 50,
    annualPrice: 40,
    tokens: 1000,
    deployments: 999,
    color: "#10b981",
    features: [
      "1,000+ Gemini AI Credits / month (Zero credit friction)",
      "100% White-Label source code exports with full commercial rights",
      "Free hosting deployments (Unlimited live websites included)",
      "Resell your customized templates on the public marketplace",
      "Autonomous AI Site Doctor: Automatically heal unlimited websites",
      "Conversational AI Prompt Editor unlocked for real-time code changes",
      "Deepest token top-up discounts (60% OFF lowest rates)",
      "VIP Dedicated Support & direct engineering channel",
    ],
  },
};

export default function SubscribePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { getToken } = useAppAuth();
  const { user, isSignedIn, isLoaded } = useAppUser();

  const searchParams = new URLSearchParams(location.search);
  const initialPlan = searchParams.get("plan")?.toLowerCase() === "extreme" ? "extreme" : "pro";
  const initialBilling = searchParams.get("billing")?.toLowerCase() === "monthly" ? "monthly" : "annual";

  const [selectedPlanId, setSelectedPlanId] = useState(initialPlan);
  const [billingCycle, setBillingCycle] = useState(initialBilling);
  const [exchangeRate, setExchangeRate] = useState(95.48);
  const [isProcessing, setIsProcessing] = useState(false);
  const [subscribedPlan, setSubscribedPlan] = useState(null);

  const plan = PLAN_DATA[selectedPlanId] || PLAN_DATA.pro;
  const isAnnual = billingCycle === "annual";
  const unitMonthlyPrice = isAnnual ? plan.annualPrice : plan.monthlyPrice;
  const totalUsd = isAnnual ? plan.annualPrice * 12 : plan.monthlyPrice;
  const totalInr = Math.round(totalUsd * exchangeRate);

  useEffect(() => {
    api.get("/payment/exchange-rate")
      .then((res) => {
        if (res?.rate) setExchangeRate(res.rate);
      })
      .catch(() => {});
  }, []);

  // Load Razorpay Script dynamically
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

  const handleSubscribe = async () => {
    if (!isSignedIn) {
      navigate(`/sign-in?from=${encodeURIComponent(location.pathname + location.search)}`);
      return;
    }

    setIsProcessing(true);
    try {
      const token = await getToken();

      // 1. Initiate subscription payment order via backend
      const res = await api.post(
        "/payment/purchase-plan",
        {
          plan_id: selectedPlanId,
          billing_cycle: billingCycle,
          gateway: "razorpay",
        },
        token
      );

      if (!res?.order_id) {
        throw new Error(res?.detail || "Could not initialize subscription order.");
      }

      // Check if sandbox mock mode or already completed
      const isMock = String(res.gateway_order_id || "").startsWith("rzp_mock_") || res.key_id === "rzp_test_mockkey";

      const rzpLoaded = await loadRazorpayScript();
      if (!rzpLoaded && !isMock) {
        throw new Error("Razorpay payment gateway failed to load. Please check your internet connection.");
      }

      if (isMock || !window.Razorpay) {
        // Fast test verification for sandbox / local development
        const verifyRes = await api.post(
          "/payment/verify",
          {
            gateway: "razorpay",
            order_id: res.order_id,
            gateway_order_id: res.gateway_order_id || `rzp_mock_${Date.now()}`,
            gateway_payment_id: `pay_mock_${Date.now()}`,
            gateway_signature: "mock_signature_verified",
          },
          token
        );

        if (verifyRes?.success) {
          setSubscribedPlan({
            id: selectedPlanId,
            name: plan.name,
            credits: plan.tokens,
            billingCycle,
            totalUsd,
          });
          setIsProcessing(false);
          return;
        }
      }

      // 2. Open official Razorpay Checkout Modal
      const options = {
        key: res.key_id,
        amount: res.amount,
        currency: res.currency || "INR",
        name: "AI Site Studio",
        description: `${plan.name} (${billingCycle.toUpperCase()})`,
        order_id: res.gateway_order_id,
        prefill: {
          name: user?.name || user?.full_name || user?.email?.split("@")[0] || "",
          email: user?.email || "",
        },
        theme: {
          color: selectedPlanId === "extreme" ? "#10b981" : "#c89666",
        },
        handler: async function (response) {
          setIsProcessing(true);
          try {
            const verifyRes = await api.post(
              "/payment/verify",
              {
                gateway: "razorpay",
                order_id: res.order_id,
                gateway_order_id: response.razorpay_order_id,
                gateway_payment_id: response.razorpay_payment_id,
                gateway_signature: response.razorpay_signature,
              },
              token
            );

            if (verifyRes?.success) {
              setSubscribedPlan({
                id: selectedPlanId,
                name: plan.name,
                credits: plan.tokens,
                billingCycle,
                totalUsd,
              });
            } else {
              alert(verifyRes?.message || "Payment verification failed.");
            }
          } catch (verErr) {
            console.error("Verification error:", verErr);
            alert(verErr?.response?.data?.detail || "Could not verify payment signature.");
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

      const rzpInstance = new window.Razorpay(options);
      rzpInstance.on("payment.failed", function (response) {
        alert(`Payment Failed: ${response.error?.description || "Transaction failed"}`);
        setIsProcessing(false);
      });
      rzpInstance.open();
    } catch (err) {
      console.error("Subscription initiation error:", err);
      alert(err?.response?.data?.detail || err.message || "Failed to process subscription.");
      setIsProcessing(false);
    }
  };

  // SUCCESS SCREEN
  if (subscribedPlan) {
    return (
      <div className="sub-page-wrapper">
        <Navbar />
        <div className="sub-success-container">
          <div className="sub-success-card">
            <div className="sub-success-icon-wrap">
              <Sparkles className="w-8 h-8 text-emerald-400" />
            </div>

            <span className="sub-success-pill">Subscription Active</span>
            <h1 className="sub-success-title">Welcome to {subscribedPlan.name}!</h1>
            <p className="sub-success-desc">
              Your payment has been successfully captured and verified via Razorpay. Your account is now upgraded with full access to clean white-label downloads, AI Gemini credits, and live hosting.
            </p>

            <div className="sub-success-features-grid">
              <div className="sub-success-feature-box">
                <span className="text-xs text-muted-foreground uppercase font-bold">Monthly Credits</span>
                <span className="text-xl font-extrabold text-foreground mt-1">+{subscribedPlan.credits} Tokens</span>
              </div>
              <div className="sub-success-feature-box">
                <span className="text-xs text-muted-foreground uppercase font-bold">Source Code</span>
                <span className="text-xl font-extrabold text-emerald-400 mt-1">100% Watermark Free</span>
              </div>
            </div>

            <div className="sub-success-actions">
              <Link to="/marketplace" className="sub-success-btn primary">
                Browse Marketplace <ArrowRight className="w-4 h-4 ml-1.5" />
              </Link>
              <Link to="/studio" className="sub-success-btn secondary">
                Launch AI Studio
              </Link>
              <Link to="/dashboard" className="sub-success-btn ghost">
                View Account Dashboard
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="sub-page-wrapper">
      <Navbar />

      <div className="sub-container">
        {/* Top Breadcrumb */}
        <div className="sub-top-nav">
          <Link to="/pricing" className="sub-back-link">
            <ArrowLeft className="w-4 h-4" /> Back to Pricing
          </Link>
          <div className="sub-secure-badge">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>256-Bit Razorpay Encrypted Checkout</span>
          </div>
        </div>

        {/* Header */}
        <div className="sub-header text-center">
          <div className="sub-plan-badge">{plan.badge}</div>
          <h1 className="sub-main-title">Complete Your {plan.name} Subscription</h1>
          <p className="sub-main-sub">
            Direct subscription activation via Razorpay. Instant white-label source code access and monthly AI Gemini compute tokens.
          </p>

          {/* Plan Selector Pills */}
          <div className="sub-tier-selector">
            <button
              type="button"
              onClick={() => setSelectedPlanId("pro")}
              className={`sub-tier-btn ${selectedPlanId === "pro" ? "active" : ""}`}
            >
              <Crown className="w-4 h-4" /> Pro Plan ($19/mo)
            </button>
            <button
              type="button"
              onClick={() => setSelectedPlanId("extreme")}
              className={`sub-tier-btn ${selectedPlanId === "extreme" ? "active" : ""}`}
            >
              <Zap className="w-4 h-4" /> Extreme Plan ($50/mo)
            </button>
          </div>

          {/* Billing Cycle Toggle */}
          <div className="sub-cycle-toggle-wrap">
            <button
              type="button"
              onClick={() => setBillingCycle("monthly")}
              className={`sub-cycle-btn ${billingCycle === "monthly" ? "active" : ""}`}
            >
              Monthly Billing
            </button>
            <button
              type="button"
              onClick={() => setBillingCycle("annual")}
              className={`sub-cycle-btn ${billingCycle === "annual" ? "active" : ""}`}
            >
              <span>Annual Billing</span>
              <span className="sub-save-pill">Save 20%</span>
            </button>
          </div>
        </div>

        {/* 2-Column Checkout Layout */}
        <div className="sub-grid-layout">
          {/* Left Column: Plan Benefits & Features */}
          <div className="sub-left-col">
            <div className="sub-card">
              <div className="sub-card-header">
                <h3 className="sub-card-title">Everything Included in {plan.name}</h3>
                <p className="sub-card-sub">{plan.description}</p>
              </div>

              <div className="sub-features-list">
                {plan.features.map((feature, idx) => (
                  <div key={idx} className="sub-feature-item">
                    <div className="sub-check-icon">
                      <Check className="w-3.5 h-3.5" />
                    </div>
                    <span className="sub-feature-text">{feature}</span>
                  </div>
                ))}
              </div>

              <div className="sub-guarantee-box">
                <HeartHandshake className="w-5 h-5 text-indigo-400 shrink-0" />
                <div className="text-xs text-muted-foreground leading-relaxed">
                  <strong className="text-foreground block mb-0.5">Cancel Anytime Guarantee</strong>
                  Subscriptions renew on a recurring basis. You can cancel or change your plan at any time with one click from your user dashboard.
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Order Summary & Razorpay Trigger */}
          <div className="sub-right-col">
            <div className="sub-card sub-summary-card">
              <div className="sub-summary-header">
                <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Order Summary</span>
                <span className="sub-gateway-pill">Razorpay Secure</span>
              </div>

              <div className="sub-price-display">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-foreground tracking-tight">
                    ${unitMonthlyPrice}
                  </span>
                  <span className="text-sm font-semibold text-muted-foreground">
                    / month
                  </span>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {isAnnual ? `Billed annually at $${totalUsd}.00 / year` : `Billed monthly at $${totalUsd}.00 / month`}
                </div>
              </div>

              {/* Converted INR Preview for Razorpay */}
              <div className="sub-currency-conversion">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-muted-foreground">Amount in USD:</span>
                  <span className="font-semibold text-foreground">${totalUsd}.00 USD</span>
                </div>
                <div className="flex justify-between items-center text-xs mt-1.5 pt-1.5 border-t border-border/40">
                  <span className="text-emerald-400 font-semibold">Razorpay Total (INR):</span>
                  <strong className="text-sm font-bold text-emerald-400">
                    ₹{totalInr.toLocaleString("en-IN")}
                  </strong>
                </div>
                <div className="text-[10px] text-muted-foreground/80 mt-1">
                  Live conversion applied at ₹{exchangeRate.toFixed(2)} per USD. Supports all Indian &amp; Global UPI, Cards, and NetBanking.
                </div>
              </div>

              {/* User Account Pill */}
              <div className="sub-user-box">
                <div className="text-xs text-muted-foreground">Account:</div>
                <div className="text-xs font-bold text-foreground truncate">
                  {isSignedIn ? user?.email : "Guest (Sign in required)"}
                </div>
              </div>

              {/* Pay Button */}
              <button
                type="button"
                onClick={handleSubscribe}
                disabled={isProcessing}
                className={`sub-pay-btn ${isProcessing ? "loading" : ""}`}
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    <span>Connecting to Razorpay...</span>
                  </>
                ) : (
                  <>
                    <Lock className="w-4 h-4 mr-2" />
                    <span>Pay ₹{totalInr.toLocaleString("en-IN")} with Razorpay</span>
                  </>
                )}
              </button>

              <div className="sub-security-footer">
                <CreditCard className="w-3.5 h-3.5 text-muted-foreground" />
                <span>Powered by Razorpay • UPI, Visa, Mastercard, RuPay &amp; NetBanking</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

