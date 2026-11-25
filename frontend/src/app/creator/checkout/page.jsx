"use client";

import { useState, useMemo, useEffect } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useCartStore } from "@/store";
import { useAppUser, useAppAuth } from "@/lib/auth";
import CreatorStorefrontNavbar from "@/components/layout/CreatorStorefrontNavbar";
import {
  ShoppingCart,
  Trash2,
  ArrowLeft,
  ArrowRight,
  ShieldCheck,
  CreditCard,
  QrCode,
  Download,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Store,
  Layers,
  Sparkles,
  Copy,
  Check,
  ExternalLink,
  Smartphone,
  Building2,
  Lock,
  Rocket,
  User,
  Mail,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import "./checkout.css";

export default function CreatorCheckoutPage() {
  const params = useParams();
  const navigate = useNavigate();
  const creatorSlug = params?.creatorSlug || "";

  const { user, isSignedIn } = useAppUser();
  const { getToken } = useAppAuth();
  const { items, removeItem, clearCart } = useCartStore();

  const [guestEmail, setGuestEmail] = useState("");
  const [guestName, setGuestName] = useState("");

  const [paymentGateway, setPaymentGateway] = useState("upi"); // "upi" | "stripe" | "razorpay" | "bank_transfer"
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [purchasedTemplates, setPurchasedTemplates] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");

  // UPI direct checkout state
  const [upiData, setUpiData] = useState(null);
  const [utrInput, setUtrInput] = useState("");
  const [copiedVpa, setCopiedVpa] = useState(false);
  const [isVerifyingUpi, setIsVerifyingUpi] = useState(false);
  const [bankTransferData, setBankTransferData] = useState(null);
  const [bankTransferReference, setBankTransferReference] = useState("");
  const [isSubmittingBankReference, setIsSubmittingBankReference] = useState(false);
  const [bankTransferSubmitted, setBankTransferSubmitted] = useState(false);

  // Fetch Creator Storefront info
  const { data: storefront, isLoading: sfLoading } = useQuery({
    queryKey: ["creatorStorefrontCheckout", creatorSlug],
    queryFn: async () => {
      if (!creatorSlug) return null;
      const res = await api.get(`/creator/storefront/${encodeURIComponent(creatorSlug)}`);
      return res;
    },
    enabled: Boolean(creatorSlug),
    staleTime: 5 * 1000,
  });

  const brandName = storefront?.brand_name || "Creator Storefront";
  const creatorStripeLink = storefront?.payment_options?.stripe?.payment_link;
  const creatorUpiVpa =
    storefront?.payment_options?.upi?.vpa ||
    storefront?.payment_options?.razorpay?.vpa;

  const paymentOpts = storefront?.payment_options || null;
  const upiEnabled = paymentOpts ? Boolean(paymentOpts.upi?.enabled || creatorUpiVpa) : Boolean(creatorUpiVpa);
  const stripeEnabled = paymentOpts ? Boolean(paymentOpts.stripe?.enabled) : false;
  const razorpayEnabled = paymentOpts ? Boolean(paymentOpts.razorpay?.enabled) : false;
  const bankTransferEnabled = paymentOpts ? Boolean(paymentOpts.bank_transfer?.enabled) : false;
  const anyGatewayEnabled = upiEnabled || stripeEnabled || razorpayEnabled || bankTransferEnabled;

  useEffect(() => {
    if (!storefront?.payment_options) return;
    if (paymentGateway === "upi" && !upiEnabled) {
      if (razorpayEnabled) setPaymentGateway("razorpay");
      else if (stripeEnabled) setPaymentGateway("stripe");
      else if (bankTransferEnabled) setPaymentGateway("bank_transfer");
    } else if (paymentGateway === "stripe" && !stripeEnabled) {
      if (razorpayEnabled) setPaymentGateway("razorpay");
      else if (upiEnabled) setPaymentGateway("upi");
      else if (bankTransferEnabled) setPaymentGateway("bank_transfer");
    } else if (paymentGateway === "razorpay" && !razorpayEnabled) {
      if (stripeEnabled) setPaymentGateway("stripe");
      else if (upiEnabled) setPaymentGateway("upi");
      else if (bankTransferEnabled) setPaymentGateway("bank_transfer");
    } else if (paymentGateway === "bank_transfer" && !bankTransferEnabled) {
      if (razorpayEnabled) setPaymentGateway("razorpay");
      else if (stripeEnabled) setPaymentGateway("stripe");
      else if (upiEnabled) setPaymentGateway("upi");
    }
  }, [storefront, paymentGateway, upiEnabled, stripeEnabled, razorpayEnabled, bankTransferEnabled]);

  // Filter items strictly for this creator, enforcing single-license per template
  const creatorItems = useMemo(() => {
    if (!Array.isArray(items)) return [];
    if (!creatorSlug) return items.map((i) => ({ ...i, quantity: 1 }));
    const scoped = items.filter(
      (i) => i.creator_slug && i.creator_slug.toLowerCase() === creatorSlug.toLowerCase()
    );
    const targetList = scoped.length > 0 ? scoped : items;
    return targetList.map((i) => ({ ...i, quantity: 1 }));
  }, [items, creatorSlug]);

  const subtotal = useMemo(() => {
    return creatorItems.reduce((sum, item) => sum + (parseFloat(item.price) || 0) * 1, 0);
  }, [creatorItems]);

  const orderTotal = subtotal;
  const orderCurrency = String(creatorItems[0]?.price_currency || creatorItems[0]?.currency || "USD").toUpperCase();
  const formatOrderAmount = (amount) => new Intl.NumberFormat(undefined, { style: "currency", currency: orderCurrency }).format(amount);

  // Authoritative store owner detection
  const isOwner = Boolean(
    (user?.id && (storefront?.creator_id || storefront?.user_id) && (String(user.id) === String(storefront.creator_id) || String(user.id) === String(storefront.user_id))) ||
    (user?.email && (storefront?.support_email || storefront?.email) && user.email.toLowerCase() === (storefront.support_email || storefront.email).toLowerCase()) ||
    (user?.creator_store_slug && creatorSlug && user.creator_store_slug.toLowerCase() === creatorSlug.toLowerCase())
  );

  const handleCopyVpa = (vpa) => {
    if (!vpa) return;
    navigator.clipboard.writeText(vpa);
    setCopiedVpa(true);
    setTimeout(() => setCopiedVpa(false), 2000);
  };

  // Dynamically load Razorpay Checkout JS SDK on demand
  const loadRazorpaySdk = () =>
    new Promise((resolve) => {
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

  // Handle return from external Stripe Checkout redirect (strict cryptographic session verification)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const searchParams = new URLSearchParams(window.location.search);
    const orderId = searchParams.get("order_id");
    const isStripeSuccess = searchParams.get("success") === "true";
    const sessionId = searchParams.get("session_id");

    if (orderId && isStripeSuccess && sessionId) {
      const verifyReturnOrder = async () => {
        setIsProcessing(true);
        setErrorMessage("");
        try {
          const token = await getToken();
          await api.post(
            "/payment/verify",
            {
              order_id: orderId,
              gateway: "stripe",
              gateway_order_id: sessionId,
              gateway_payment_id: sessionId,
              gateway_signature: "stripe_session_retrieve",
            },
            token ?? undefined
          );
          completeOrderSuccess({ id: orderId });
        } catch (vErr) {
          console.error("Stripe verification error:", vErr);
          setErrorMessage(
            vErr?.response?.data?.detail ||
              vErr?.message ||
              "Could not confirm Stripe payment. Please contact support or try again."
          );
          setIsProcessing(false);
        }
      };
      verifyReturnOrder();
    }
  }, []);

  // Auto-select creator's primary configured gateway
  useEffect(() => {
    const primary = storefront?.payment_options?.primary;
    const accepted = storefront?.accepted_payment_methods || storefront?.payment_options?.accepted_methods || [];
    if (primary === "upi" && upiEnabled) {
      setPaymentGateway("upi");
    } else if (primary === "bank" && bankTransferEnabled) {
      setPaymentGateway("bank_transfer");
    } else if (primary === "razorpay" && razorpayEnabled) {
      setPaymentGateway("razorpay");
    } else if (primary === "stripe" && stripeEnabled) {
      setPaymentGateway("stripe");
    } else if (upiEnabled) {
      setPaymentGateway("upi");
    } else if (accepted.includes("razorpay") && razorpayEnabled) {
      setPaymentGateway("razorpay");
    } else if (accepted.includes("stripe") && stripeEnabled) {
      setPaymentGateway("stripe");
    } else if (bankTransferEnabled) {
      setPaymentGateway("bank_transfer");
    }
  }, [storefront, upiEnabled, razorpayEnabled, stripeEnabled, bankTransferEnabled]);

  const handlePlaceOrder = async () => {
    if (creatorItems.length === 0) return;
    if (isOwner) {
      setErrorMessage(
        "You are currently signed in as the creator of this store. Creators already have full access to their source code and cannot purchase their own template. To test purchasing, please use an incognito window or sign in with a client account."
      );
      return;
    }
    if (storefront?.is_bank_connected === false) {
      setErrorMessage(
        `${brandName} has not connected their bank account or verified payout gateway yet. Purchasing is temporarily paused.`
      );
      return;
    }
    if (!isSignedIn && (!guestEmail || !guestEmail.includes("@"))) {
      setErrorMessage("Please enter your delivery email address below to receive your template downloads and license.");
      return;
    }
    setIsProcessing(true);
    setErrorMessage("");

    try {
      let token = await getToken();

      const orderPayload = {
        items: creatorItems.map((i) => ({
          template_id: i.templateId || i.id,
          license_type: i.licenseType || "regular",
        })),
        country_code: "US",
        creator_slug: creatorSlug,
      };

      if (!token && guestEmail) {
        orderPayload.buyer_email = guestEmail.trim().toLowerCase();
        orderPayload.buyer_name = guestName.trim() || undefined;
      }

      // 1. Create order linked directly to this creator with seller_id attribution
      const orderRes = await api.post(
        "/orders",
        orderPayload,
        token ?? undefined
      );

      // Auto-authenticate guest client if backend returned session token
      if (orderRes?.auth_token && !token) {
        try {
          useAuthStore.getState().setSession(orderRes.auth_token, orderRes.user);
          token = orderRes.auth_token;
        } catch (authErr) {
          console.warn("Auto session set notice:", authErr);
        }
      }

      const targetOrder = orderRes?.order || orderRes;

      // 2. Initiate Payment through Selected Marketplace Route
      const payRes = await api.post(
        "/payment/initiate",
        {
          order_id: targetOrder.id,
          gateway: paymentGateway,
        },
        token ?? undefined
      );

      const targetPay = payRes?.payment || payRes;

      // ── DIRECT UPI ROUTE ──
      if (paymentGateway === "upi") {
        setUpiData({
          ...targetPay,
          order: targetOrder,
          brandName,
        });
        setIsProcessing(false);
        return;
      }

      if (paymentGateway === "bank_transfer") {
        setBankTransferData({ ...targetPay, order: targetOrder, brandName });
        setBankTransferReference("");
        setBankTransferSubmitted(false);
        setIsProcessing(false);
        return;
      }

      // ── STRIPE CONNECT AUTOMATED PAYOUT ROUTE ──
      if (paymentGateway === "stripe") {
        const checkoutUrl = targetPay?.checkout_url;
        if (checkoutUrl && checkoutUrl.startsWith("http") && !checkoutUrl.includes("mock_stripe")) {
          window.location.href = checkoutUrl;
          return;
        }
        setErrorMessage("There is some issue processing your Stripe payment right now. Please try again later.");
        setIsProcessing(false);
        return;
      }

      // ── RAZORPAY GATEWAY ROUTE ──
      if (paymentGateway === "razorpay") {
        const loaded = await loadRazorpaySdk();
        if (!loaded || typeof window === "undefined" || !window.Razorpay || !targetPay?.gateway_order_id || String(targetPay.gateway_order_id).startsWith("rzp_mock_") || targetPay?.key_id === "rzp_test_mockkey") {
          setErrorMessage("There is some issue connecting to Razorpay right now. Please try again later.");
          setIsProcessing(false);
          return;
        }

        const rzp = new window.Razorpay({
          key: targetPay.key_id,
          amount: targetPay.amount,
          currency: targetPay.currency || "INR",
          name: brandName,
          description: `Order #${targetOrder.order_number || targetOrder.id?.slice(0, 8)}`,
          order_id: targetPay.gateway_order_id,
          prefill: {
            email: user?.email || guestEmail || "",
            name: user?.first_name || guestName || user?.email?.split("@")[0] || "",
          },
          theme: { color: "#dfb180" },
          handler: async (resp) => {
            try {
              await api.post(
                "/payment/verify",
                {
                  order_id: targetOrder.id,
                  gateway_payment_id: resp.razorpay_payment_id,
                  gateway_signature: resp.razorpay_signature,
                  gateway_order_id: resp.razorpay_order_id,
                  gateway: "razorpay",
                },
                token ?? undefined
              );
              completeOrderSuccess(targetOrder);
            } catch (verErr) {
              setErrorMessage(
                verErr?.response?.data?.detail || "Payment verification failed. Please contact support."
              );
              setIsProcessing(false);
            }
          },
          modal: {
            ondismiss: () => {
              setIsProcessing(false);
            },
          },
        });
        rzp.on("payment.failed", (resp) => {
          setErrorMessage(`Razorpay payment failed: ${resp?.error?.description || "Please try again."}`);
          setIsProcessing(false);
        });
        rzp.open();
        return;
      }

      setErrorMessage("Please select a valid connected payment channel.");
      setIsProcessing(false);
    } catch (err) {
      console.error("Order initiation error:", err);
      if (err?.status === 401 || err?.message?.includes("401") || err?.message?.toLowerCase().includes("not authenticated") || err?.message?.toLowerCase().includes("unauthorized")) {
        setErrorMessage("Authentication required. Please enter your email address below or sign in to complete your purchase.");
        setIsProcessing(false);
        return;
      }
      const detailMsg =
        err?.response?.data?.detail ||
        err?.message ||
        "There is some issue processing your payment right now. Please try again later.";
      setErrorMessage(detailMsg);
      setIsProcessing(false);
    }
  };

  // Strict Direct UPI Verification with genuine 12-digit UTR
  const handleVerifyUpiPayment = async () => {
    if (!upiData?.order?.id) return;
    const cleanUtr = utrInput.trim();
    if (!cleanUtr || !/^[A-Za-z0-9]{10,35}$/.test(cleanUtr)) {
      setErrorMessage("Please enter your genuine 12-digit UPI UTR / Transaction Reference number after completing the transfer.");
      return;
    }
    setIsVerifyingUpi(true);
    setErrorMessage("");

    try {
      const token = await getToken();
      await api.post(
        "/payment/verify",
        {
          order_id: upiData.order.id,
          gateway: "upi",
          upi_utr: cleanUtr,
          gateway_payment_id: cleanUtr,
          gateway_order_id: upiData.gateway_order_id || `upi_${upiData.order.id}`,
        },
        token ?? undefined
      );

      completeOrderSuccess(upiData.order);
    } catch (err) {
      console.error("UPI verification error:", err);
      setErrorMessage(
        err?.response?.data?.detail || "Could not confirm UPI transaction reference. Please verify your UTR."
      );
      setIsVerifyingUpi(false);
    }
  };

  const handleSubmitBankTransferReference = async () => {
    if (!bankTransferData?.order?.id || !/^[A-Za-z0-9-]{8,40}$/.test(bankTransferReference.trim())) {
      setErrorMessage("Enter the 8–40 character transfer reference provided by your bank.");
      return;
    }
    setIsSubmittingBankReference(true);
    setErrorMessage("");
    try {
      const token = await getToken();
      await api.post("/payment/verify", {
        order_id: bankTransferData.order.id,
        gateway: "bank_transfer",
        gateway_order_id: bankTransferData.gateway_order_id,
        gateway_payment_id: bankTransferReference.trim(),
      }, token ?? undefined);
      setBankTransferSubmitted(true);
    } catch (err) {
      setErrorMessage(err?.response?.data?.detail || err?.message || "Could not submit the transfer reference.");
    } finally {
      setIsSubmittingBankReference(false);
    }
  };

  const completeOrderSuccess = async (ord) => {
    const rawItems = ord.items && ord.items.length > 0 ? ord.items : creatorItems;
    setPurchasedTemplates(rawItems);
    setIsSuccess(true);
    setIsProcessing(false);
    setIsVerifyingUpi(false);

    // Auto trigger instant package downloads
    const token = await getToken();
    for (const item of rawItems) {
      try {
        const tId = item.template_id || item.id || item.templateId;
        const res = await api.post(`/templates/${tId}/download?format=zip`, {}, token);
        if (res?.download_url) {
          const link = document.createElement("a");
          link.href = res.download_url;
          link.download = "";
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        }
      } catch (dlErr) {
        console.warn("Auto-download notice for template:", dlErr);
      }
    }

    clearCart();
  };

  return (
    <div className="cr-checkout-page">
      <div className="cr-checkout-glow" />

      {/* Branded Creator Navbar */}
      <CreatorStorefrontNavbar
        storefront={storefront}
        creatorSlug={creatorSlug}
        cartItems={creatorItems}
      />

      <div className="cr-checkout-container">
        {/* Navigation Breadcrumb */}
        <div className="cr-checkout-top-nav">
          <Link to={`/creator/${creatorSlug}`} className="cr-checkout-back-link">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to {brandName}</span>
          </Link>
        </div>

        {isSuccess ? (
          /* Order Complete Success View */
          <div className="cr-success-box">
            <div className="cr-success-icon">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h1 className="cr-success-title">Order Confirmed!</h1>
            <p className="cr-success-sub">
              Thank you for purchasing directly from <strong>{brandName}</strong>. Your full production codebase has been generated with zero watermark and commercial licensing.
            </p>

            <div className="cr-success-actions">
              {/* Primary 1-Click Site Studio Deployment Hero Card */}
              {purchasedTemplates.length > 0 && (
                <div className="p-5 rounded-2xl bg-gradient-to-r from-[#dfb180]/15 via-purple-500/10 to-[#dfb180]/10 border border-[#dfb180]/35 text-left flex flex-col md:flex-row items-center justify-between gap-4 mb-2 shadow-xl">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-[#dfb180] text-[#121620]">
                        Ready to Launch
                      </span>
                      <span className="text-xs text-[#dfb180] font-medium">Site Studio Cloud Deployment</span>
                    </div>
                    <h3 className="text-base font-bold text-white mt-1">
                      Deploy Your Website Live with 1-Click
                    </h3>
                    <p className="text-xs text-slate-300 mt-1 max-w-md leading-relaxed">
                      Publish directly inside Site Studio. Your live website will automatically carry {brandName}&apos;s verified creator signature: <strong className="text-[#dfb180]">&quot;Deployed by {brandName}&quot;</strong>.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      const firstT = purchasedTemplates[0];
                      const tId = firstT?.slug || firstT?.template_id || firstT?.id || firstT?.templateId;
                      navigate(`/studio/deploy?template=${encodeURIComponent(tId)}&creatorSlug=${encodeURIComponent(creatorSlug)}`);
                    }}
                    className="w-full md:w-auto shrink-0 inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-[#dfb180] text-[#121620] font-bold text-sm hover:bg-[#ebd2b0] hover:scale-[1.02] active:scale-[0.98] transition-all shadow-lg cursor-pointer"
                  >
                    <Rocket className="w-4 h-4" />
                    <span>Launch in Site Studio ↗</span>
                  </button>
                </div>
              )}

              {purchasedTemplates.map((t, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-between text-left"
                >
                  <div>
                    <h4 className="font-semibold text-white text-sm">{t.title || "Website Template"}</h4>
                    <p className="text-xs text-[#dfb180] mt-0.5">Commercial License Included ✓</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        const tId = t.slug || t.template_id || t.id || t.templateId;
                        navigate(`/studio/deploy?template=${encodeURIComponent(tId)}&creatorSlug=${encodeURIComponent(creatorSlug)}`);
                      }}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#dfb180] text-[#121620] font-bold text-xs hover:bg-[#ebd2b0] transition-all shadow-md cursor-pointer"
                    >
                      <Rocket className="w-3.5 h-3.5" />
                      <span>Deploy in Site Studio ↗</span>
                    </button>
                    <button
                      type="button"
                      onClick={async () => {
                        const tId = t.template_id || t.id || t.templateId;
                        const userToken = (await getToken()) || localStorage.getItem("token") || "";
                        window.open(
                          `/api/v1/templates/${tId}/download-package?format=zip${userToken ? `&token=${encodeURIComponent(userToken)}` : ""}`,
                          "_blank"
                        );
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 text-white font-medium text-xs hover:bg-white/20 transition-all border border-white/15 cursor-pointer"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>ZIP</span>
                    </button>
                  </div>
                </div>
              ))}

              <Link
                to={`/creator/${creatorSlug}`}
                className="cr-browse-btn justify-center mt-4"
              >
                <span>Return to {brandName}&apos;s Storefront</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        ) : (
          <>
            {/* Page Header */}
            <header className="cr-checkout-header">
              <div className="cr-checkout-title-row">
                <h1 className="cr-checkout-title">{brandName}&apos;s Checkout</h1>
                <span className="cr-checkout-badge">
                  <Store className="w-3.5 h-3.5" />
                  <span>Direct Creator Purchase</span>
                </span>
              </div>
              <p className="cr-checkout-subtitle">
                Review your items and complete your purchase directly with {brandName}.
              </p>
            </header>

            {creatorItems.length === 0 ? (
              <div className="cr-checkout-card cr-empty-cart">
                <div className="cr-empty-icon">
                  <ShoppingCart className="w-6 h-6" />
                </div>
                <h2 className="cr-empty-heading">Your Cart is Empty</h2>
                <p className="cr-empty-subtext">
                  You don&apos;t have any templates from {brandName} in your cart yet.
                </p>
                <Link to={`/creator/${creatorSlug}`} className="cr-browse-btn">
                  <span>Browse {brandName}&apos;s Templates</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            ) : (
              <div className="cr-checkout-grid">
                {/* Left: Cart Items & Payment Method Selector */}
                <div className="cr-checkout-left">
                  {/* Cart Items Card */}
                  <div className="cr-checkout-card">
                    <h2 className="cr-card-title">
                      <Layers className="w-4 h-4 text-[#dfb180]" />
                      <span>Templates to Purchase ({creatorItems.length})</span>
                    </h2>

                    <div className="cr-items-stack">
                      {creatorItems.map((item) => (
                        <div key={item.templateId || item.id} className="cr-item-row">
                          <div className="cr-item-left">
                            <div className="cr-item-thumb">
                              <img
                                src={item.thumbnail || item.thumbnail_url || "/landing/template_saas.png"}
                                alt={item.title}
                                onError={(e) => {
                                  e.currentTarget.src = "/landing/template_saas.png";
                                }}
                              />
                            </div>
                            <div className="cr-item-info">
                              <h3 className="cr-item-name">{item.title}</h3>
                              <div className="cr-item-meta">
                                <span className="cr-item-badge">{item.framework || "React / HTML"}</span>
                                <span>Commercial License (Single License)</span>
                              </div>
                            </div>
                          </div>

                          <div className="cr-item-right">
                            <div className="cr-item-price">${parseFloat(item.price) || 39}</div>
                            <button
                              type="button"
                              onClick={() => removeItem(item.templateId || item.id)}
                              className="cr-item-del-btn"
                              title="Remove item"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Owner Banner */}
                  {isOwner && (
                    <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/25 text-purple-300 text-xs flex flex-col gap-1.5 mb-4">
                      <div className="flex items-center gap-2 font-semibold text-purple-200">
                        <Store className="w-4 h-4 shrink-0 text-purple-400" />
                        <span>Creator Storefront Owner Account</span>
                      </div>
                      <p className="text-slate-300 leading-relaxed">
                        You are signed in as <strong>{user?.email}</strong> (the owner/creator of {brandName}). You already have complete owner access to all source files and cannot purchase your own templates.
                      </p>
                      <p className="text-[11px] text-zinc-400">
                        To test purchasing as a customer, please open an incognito window or sign in with a client account.
                      </p>
                    </div>
                  )}

                  {/* Client Status or Guest Email Delivery Box */}
                  {!isSignedIn ? (
                    <div className="cr-checkout-card">
                      <div className="flex items-center justify-between mb-2">
                        <h2 className="cr-card-title !mb-0">
                          <Mail className="w-4 h-4 text-[#dfb180]" />
                          <span>Delivery Email &amp; Client Account</span>
                        </h2>
                        <Link
                          to={`/creator/${creatorSlug}/login?redirect=${encodeURIComponent(`/creator/${creatorSlug}/checkout`)}`}
                          className="text-xs text-[#dfb180] hover:underline flex items-center gap-1 font-medium"
                        >
                          <User className="w-3.5 h-3.5" />
                          <span>Already a client? Sign In</span>
                        </Link>
                      </div>
                      <p className="text-xs text-zinc-400 mb-3">
                        Enter your email address to receive your instant ZIP code download, commercial license, and cloud deployment access.
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-[11px] font-medium text-zinc-300 mb-1">
                            Your Email Address <span className="text-rose-400">*</span>
                          </label>
                          <input
                            type="email"
                            placeholder="you@example.com"
                            value={guestEmail}
                            onChange={(e) => setGuestEmail(e.target.value)}
                            className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.04] border border-white/10 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-[#dfb180] transition-all"
                            required
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-medium text-zinc-300 mb-1">
                            Your Full Name <span className="text-zinc-500">(Optional)</span>
                          </label>
                          <input
                            type="text"
                            placeholder="John Doe"
                            value={guestName}
                            onChange={(e) => setGuestName(e.target.value)}
                            className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.04] border border-white/10 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-[#dfb180] transition-all"
                          />
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 mb-4 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-full bg-[#dfb180]/20 text-[#dfb180] flex items-center justify-center font-bold text-xs">
                          {(user?.first_name || user?.email || "U").charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div className="font-semibold text-white">{user?.email}</div>
                          <div className="text-[11px] text-[#dfb180]">
                            {isOwner ? "Store Owner & Creator ✦" : `Client Account of ${brandName}`}
                          </div>
                        </div>
                      </div>
                      <span className="text-emerald-400 text-[11px] font-medium flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Ready to Checkout</span>
                      </span>
                    </div>
                  )}

                  {/* Payment Channels Card */}
                  <div className="cr-checkout-card">
                    <h2 className="cr-card-title">
                      <CreditCard className="w-4 h-4 text-[#dfb180]" />
                      <span>Select Payment Channel</span>
                    </h2>

                    {storefront && (!anyGatewayEnabled || storefront.is_bank_connected === false) && (
                      <div className="mb-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs flex items-start gap-2.5">
                        <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        <span>
                          {storefront.payout_status_message ||
                            "This creator has not connected a verified payment gateway yet. Checkout is temporarily unavailable."}
                        </span>
                      </div>
                    )}

                    <div className="cr-pay-methods-grid">
                      {/* 1. Direct UPI Channel */}
                      <button
                        type="button"
                        disabled={!upiEnabled}
                        onClick={() => {
                          if (!upiEnabled) return;
                          setPaymentGateway("upi");
                          setUpiData(null);
                        }}
                        className={`cr-pay-method-btn ${paymentGateway === "upi" ? "active" : ""} ${!upiEnabled ? "opacity-45 cursor-not-allowed" : ""}`}
                      >
                        <QrCode className="w-5 h-5 text-[#dfb180]" />
                        <span>Direct UPI &amp; QR</span>
                        {!upiEnabled && (
                          <span className="text-[10px] text-zinc-400 font-normal">Not connected</span>
                        )}
                      </button>

                      {/* 2. Stripe Connected Account Channel */}
                      <button
                        type="button"
                        disabled={!stripeEnabled}
                        onClick={() => {
                          if (!stripeEnabled) return;
                          setPaymentGateway("stripe");
                          setUpiData(null);
                        }}
                        className={`cr-pay-method-btn ${paymentGateway === "stripe" ? "active" : ""} ${!stripeEnabled ? "opacity-45 cursor-not-allowed" : ""}`}
                      >
                        <CreditCard className="w-5 h-5 text-[#dfb180]" />
                        <span>Stripe &amp; Cards</span>
                        {!stripeEnabled && (
                          <span className="text-[10px] text-zinc-400 font-normal">Not connected</span>
                        )}
                      </button>

                      {/* 3. Razorpay Channel */}
                      <button
                        type="button"
                        disabled={!razorpayEnabled}
                        onClick={() => {
                          if (!razorpayEnabled) return;
                          setPaymentGateway("razorpay");
                          setUpiData(null);
                        }}
                        className={`cr-pay-method-btn ${paymentGateway === "razorpay" ? "active" : ""} ${!razorpayEnabled ? "opacity-45 cursor-not-allowed" : ""}`}
                      >
                        <Building2 className="w-5 h-5 text-[#dfb180]" />
                        <span>Razorpay</span>
                        {!razorpayEnabled && (
                          <span className="text-[10px] text-zinc-400 font-normal">Not connected</span>
                        )}
                      </button>

                      <button
                        type="button"
                        disabled={!bankTransferEnabled}
                        onClick={() => {
                          if (!bankTransferEnabled) return;
                          setPaymentGateway("bank_transfer");
                          setUpiData(null);
                        }}
                        className={`cr-pay-method-btn ${paymentGateway === "bank_transfer" ? "active" : ""} ${!bankTransferEnabled ? "opacity-45 cursor-not-allowed" : ""}`}
                      >
                        <Building2 className="w-5 h-5 text-[#dfb180]" />
                        <span>Bank Transfer</span>
                        {!bankTransferEnabled && (
                          <span className="text-[10px] text-zinc-400 font-normal">Not connected</span>
                        )}
                      </button>
                    </div>

                    {/* Method Description Pill */}
                    <div className="cr-pay-notice">
                      <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>
                        {paymentGateway === "upi" &&
                          `Direct payment to ${brandName}'s verified UPI. Zero platform fee, instant automated credit.`}
                        {paymentGateway === "stripe" &&
                          `Automated instant payout to ${brandName}'s Stripe Connected Account with dynamic payment methods.`}
                        {paymentGateway === "razorpay" &&
                          `Pay securely with Cards, Netbanking, or Wallets via Razorpay gateway.`}
                        {paymentGateway === "bank_transfer" &&
                          `Transfer the exact order amount to ${brandName}'s bank account. Your order is delivered after the transfer is reviewed.`}
                      </span>
                    </div>

                    {/* Direct Creator Stripe Link Option */}
                    {creatorStripeLink && (
                      <div className="cr-stripe-link-banner">
                        <div className="flex items-center gap-2 text-xs text-white">
                          <Store className="w-4 h-4 text-[#dfb180]" />
                          <span>Prefer seller&apos;s direct Stripe checkout page?</span>
                        </div>
                        <a
                          href={creatorStripeLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="cr-stripe-direct-btn"
                        >
                          <span>Open {brandName}&apos;s Stripe Page</span>
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    )}

                    {/* Active UPI Interactive Box */}
                    {paymentGateway === "upi" && upiData && (
                      <div className="cr-upi-checkout-box">
                        <div className="cr-upi-header">
                          <div className="flex items-center gap-2">
                            <QrCode className="w-4 h-4 text-[#dfb180]" />
                            <h3 className="font-bold text-white text-sm">Scan UPI QR to Pay Directly</h3>
                          </div>
                          <span className="cr-upi-inr-tag">
                            ₹{(upiData.amount / 100).toFixed(2)} INR
                          </span>
                        </div>

                        {/* Centered Dynamic QR Code */}
                        <div className="cr-upi-qr-wrapper">
                          <img
                            src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&margin=8&data=${encodeURIComponent(
                              upiData.upi_uri || `upi://pay?pa=${upiData.vpa}&pn=${brandName}&am=${(upiData.amount / 100).toFixed(2)}&cu=INR`
                            )}`}
                            alt="UPI QR Code"
                            className="cr-upi-qr-img"
                          />
                          <p className="text-[11px] text-zinc-400 mt-2">
                            Scan with GPay, PhonePe, Paytm, BHIM, or any UPI App
                          </p>
                        </div>

                        {/* UPI VPA Pill with Copy Button */}
                        <div className="cr-upi-vpa-row">
                          <div className="cr-upi-vpa-info">
                            <span className="text-[11px] text-zinc-400">Verified Seller UPI ID</span>
                            <span className="font-mono text-xs font-bold text-white">{upiData.vpa || creatorUpiVpa}</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleCopyVpa(upiData.vpa || creatorUpiVpa)}
                            className="cr-upi-copy-btn"
                          >
                            {copiedVpa ? (
                              <>
                                <Check className="w-3.5 h-3.5 text-emerald-400" />
                                <span className="text-emerald-400">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-3.5 h-3.5" />
                                <span>Copy VPA</span>
                              </>
                            )}
                          </button>
                        </div>

                        {/* Mobile Direct UPI Intent Button */}
                        {upiData.upi_uri && (
                          <a
                            href={upiData.upi_uri}
                            className="cr-upi-intent-link"
                          >
                            <Smartphone className="w-4 h-4" />
                            <span>Pay directly in UPI App (Mobile)</span>
                          </a>
                        )}

                        {/* UTR / Transaction Reference Confirmation Box */}
                        <div className="cr-upi-confirm-box">
                          <label className="text-xs font-semibold text-white block mb-1">
                            Confirm Your Payment (12-digit UPI Ref / UTR)
                          </label>
                          <div className="flex gap-2">
                            <input
                              type="text"
                              value={utrInput}
                              onChange={(e) => setUtrInput(e.target.value)}
                              placeholder="Enter 12-digit UTR / Ref ID from your UPI app"
                              className="cr-upi-utr-input"
                              required
                            />
                            <button
                              type="button"
                              onClick={handleVerifyUpiPayment}
                              disabled={isVerifyingUpi}
                              className="cr-upi-verify-btn"
                            >
                              {isVerifyingUpi ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <>
                                  <span>Confirm</span>
                                  <Check className="w-4 h-4" />
                                </>
                              )}
                            </button>
                          </div>
                          <p className="text-[11px] text-zinc-400 mt-1.5">
                            Once payment is made in your UPI app, submit the UTR reference to unlock your instant downloads immediately.
                          </p>
                        </div>
                      </div>
                    )}

                    {paymentGateway === "bank_transfer" && bankTransferData && (
                      <div className="cr-bank-transfer-box">
                        {bankTransferSubmitted ? (
                          <div className="cr-bank-transfer-pending">
                            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                            <div>
                              <h3>Transfer reference submitted</h3>
                              <p>Your order stays pending until the creator’s bank confirms the payment. We’ll enable your downloads after review.</p>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="cr-bank-transfer-header">
                              <div>
                                <h3>Pay by bank transfer</h3>
                                <p>These details are shown only for your order. Send the exact amount below.</p>
                              </div>
                              <strong>{bankTransferData.currency} {(bankTransferData.amount / 100).toFixed(2)}</strong>
                            </div>
                            <div className="cr-bank-transfer-details">
                              {[
                                ["Account holder", bankTransferData.bank_transfer_details?.account_holder_name],
                                ["Bank", bankTransferData.bank_transfer_details?.bank_name],
                                ["Account number", bankTransferData.bank_transfer_details?.account_number],
                                ["IFSC / Routing", bankTransferData.bank_transfer_details?.ifsc_code],
                                ["SWIFT / BIC", bankTransferData.bank_transfer_details?.swift_code],
                                ["IBAN", bankTransferData.bank_transfer_details?.iban],
                              ].filter(([, value]) => Boolean(value)).map(([label, value]) => (
                                <div className="cr-bank-transfer-row" key={label}>
                                  <span>{label}</span><code>{value}</code>
                                </div>
                              ))}
                            </div>
                            <label className="cr-bank-transfer-label" htmlFor="bank-transfer-reference">Bank transfer reference</label>
                            <div className="cr-bank-transfer-submit">
                              <input
                                id="bank-transfer-reference"
                                type="text"
                                autoComplete="off"
                                value={bankTransferReference}
                                onChange={(event) => setBankTransferReference(event.target.value)}
                                placeholder="Reference / UTR from your bank"
                              />
                              <button type="button" onClick={handleSubmitBankTransferReference} disabled={isSubmittingBankReference}>
                                {isSubmittingBankReference ? <Loader2 className="w-4 h-4 animate-spin" /> : "Submit reference"}
                              </button>
                            </div>
                            <p className="cr-bank-transfer-footnote">We only ask for the transfer reference. Never enter your bank password, card number, or login code here.</p>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: Order Summary */}
                <div className="cr-checkout-right">
                  <div className="cr-summary-card">
                    <h2 className="cr-card-title">
                      <Sparkles className="w-4 h-4 text-[#dfb180]" />
                      <span>Summary</span>
                    </h2>

                    <div className="cr-summary-row">
                      <span>Subtotal ({creatorItems.length} {creatorItems.length === 1 ? "item" : "items"})</span>
                      <span className="font-semibold text-white">{formatOrderAmount(subtotal)}</span>
                    </div>

                    <div className="cr-summary-row">
                      <span>Platform Service Fee</span>
                      <span className="text-emerald-400 font-medium">$0.00 (Waived)</span>
                    </div>

                    <div className="cr-summary-row">
                      <span>Source Delivery</span>
                      <span className="text-emerald-400 font-medium">Instant ZIP Download</span>
                    </div>

                    <div className="cr-summary-row total">
                      <span>Total</span>
                      <span className="text-[#dfb180] font-bold">{formatOrderAmount(orderTotal)}</span>
                    </div>

                    {storefront?.is_bank_connected === false && (
                      <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex flex-col gap-1.5 my-3">
                        <div className="flex items-center gap-2 font-semibold text-amber-200">
                          <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
                          <span>Purchasing Temporarily Paused</span>
                        </div>
                        <p className="text-slate-300 leading-relaxed">
                          {brandName} has not completed their bank account or payout verification yet. Checkout is temporarily paused until their bank details are connected.
                        </p>
                      </div>
                    )}

                    {errorMessage && (
                      <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>{errorMessage}</span>
                      </div>
                    )}

                    {/* Primary Action Button */}
                    {isOwner ? (
                      <div className="p-3.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-center text-xs text-purple-300 font-medium">
                        You are logged in as the creator of this store. You already have owner access to all files.
                      </div>
                    ) : !(paymentGateway === "upi" && upiData) && !(paymentGateway === "bank_transfer" && bankTransferData) ? (
                      <button
                        type="button"
                        onClick={handlePlaceOrder}
                        disabled={isProcessing || storefront?.is_bank_connected === false}
                        className="cr-pay-cta-btn"
                      >
                        {isProcessing ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span>Routing Payment to Creator...</span>
                          </>
                        ) : !isSignedIn && (!guestEmail || !guestEmail.includes("@")) ? (
                          <>
                            <span>Enter Email to Pay {formatOrderAmount(orderTotal)} &amp; Download</span>
                            <ArrowRight className="w-4 h-4" />
                          </>
                        ) : (
                          <>
                            <span>
                              {paymentGateway === "upi"
                                ? `Generate UPI QR & Pay ${formatOrderAmount(orderTotal)}`
                                : paymentGateway === "bank_transfer"
                                  ? `Continue with bank transfer ${formatOrderAmount(orderTotal)}`
                                  : `Pay ${formatOrderAmount(orderTotal)} & Download`}
                            </span>
                            <ArrowRight className="w-4 h-4" />
                          </>
                        )}
                      </button>
                    ) : (
                      <div className="p-3 rounded-xl bg-[#dfb180]/10 border border-[#dfb180]/20 text-center">
                        <span className="text-xs text-[#dfb180] font-medium">
                          {paymentGateway === "upi"
                            ? "Scan the QR code on the left, pay, and submit your UTR."
                            : bankTransferSubmitted
                              ? "Your bank transfer reference is submitted for review."
                              : "Use the bank details above, then submit your transfer reference for review."}
                        </span>
                      </div>
                    )}

                    <div className="cr-guarantee-pill">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                      <span>256-Bit SSL Encrypted Direct Checkout</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
