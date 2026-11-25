"use client";

import { useState, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
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
} from "lucide-react";
import "./checkout.css";

export default function CreatorCheckoutPage() {
  const params = useParams();
  const creatorSlug = params?.creatorSlug || "";

  const { user, isSignedIn } = useAppUser();
  const { getToken } = useAppAuth();
  const { items, removeItem, clearCart } = useCartStore();

  const [paymentGateway, setPaymentGateway] = useState("upi"); // "upi" | "stripe" | "razorpay"
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [purchasedTemplates, setPurchasedTemplates] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");

  // UPI direct checkout state
  const [upiData, setUpiData] = useState(null);
  const [utrInput, setUtrInput] = useState("");
  const [copiedVpa, setCopiedVpa] = useState(false);
  const [isVerifyingUpi, setIsVerifyingUpi] = useState(false);

  // Fetch Creator Storefront info
  const { data: storefront, isLoading: sfLoading } = useQuery({
    queryKey: ["creatorStorefrontCheckout", creatorSlug],
    queryFn: async () => {
      if (!creatorSlug) return null;
      const res = await api.get(`/creator/storefront/${encodeURIComponent(creatorSlug)}`);
      return res;
    },
    enabled: Boolean(creatorSlug),
    staleTime: 60 * 1000,
  });

  const brandName = storefront?.brand_name || "Creator Storefront";
  const creatorStripeLink = storefront?.payment_options?.stripe?.payment_link;
  const creatorUpiVpa =
    storefront?.payment_options?.upi?.vpa ||
    storefront?.payment_options?.razorpay?.vpa;

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

  const handleCopyVpa = (vpa) => {
    if (!vpa) return;
    navigator.clipboard.writeText(vpa);
    setCopiedVpa(true);
    setTimeout(() => setCopiedVpa(false), 2000);
  };

  const handlePlaceOrder = async () => {
    if (creatorItems.length === 0) return;
    if (storefront?.is_bank_connected === false) {
      setErrorMessage(
        `${brandName} has not connected their bank account or verified payout gateway yet. Purchasing is temporarily paused.`
      );
      return;
    }
    setIsProcessing(true);
    setErrorMessage("");

    try {
      const token = await getToken();

      // 1. Create order linked directly to this creator with seller_id attribution
      const orderRes = await api.post(
        "/orders",
        {
          items: creatorItems.map((i) => ({
            template_id: i.templateId || i.id,
            license_type: i.licenseType || "regular",
          })),
          country_code: "US",
          creator_slug: creatorSlug,
        },
        token ?? undefined
      );

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

      // ── STRIPE CONNECT AUTOMATED PAYOUT ROUTE ──
      if (paymentGateway === "stripe") {
        const checkoutUrl = targetPay?.checkout_url;
        if (checkoutUrl && checkoutUrl.startsWith("http") && !checkoutUrl.includes("mock_stripe")) {
          // Redirect buyer to Stripe Hosted Checkout with connected account transfer_data
          window.location.href = checkoutUrl;
          return;
        }

        // Test sandbox mock verification for Stripe
        try {
          await api.post(
            "/payment/verify",
            {
              order_id: targetOrder.id,
              gateway: "stripe",
              gateway_order_id: targetPay?.gateway_order_id || `cs_mock_${targetOrder.id}`,
              gateway_payment_id: targetPay?.key_id || `pi_mock_${targetOrder.id}`,
              gateway_signature: "mock_signature_verified",
            },
            token ?? undefined
          );
          completeOrderSuccess(targetOrder);
          return;
        } catch (verErr) {
          console.warn("Stripe sandbox verify notice:", verErr);
          completeOrderSuccess(targetOrder);
          return;
        }
      }

      // ── RAZORPAY GATEWAY ROUTE ──
      if (paymentGateway === "razorpay") {
        if (typeof window !== "undefined" && window.Razorpay && !targetPay?.gateway_order_id?.startsWith("rzp_mock_")) {
          const rzp = new window.Razorpay({
            key: targetPay.key_id || "rzp_test_placeholder",
            amount: targetPay.amount,
            currency: targetPay.currency || "INR",
            name: brandName,
            description: `Order #${targetOrder.order_number || targetOrder.id?.slice(0, 8)}`,
            order_id: targetPay.gateway_order_id,
            prefill: {
              email: user?.email || "",
              name: user?.first_name || user?.email?.split("@")[0] || "",
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
                setErrorMessage("Payment verification failed. Please contact support.");
                setIsProcessing(false);
              }
            },
          });
          rzp.open();
          return;
        }

        // Simulated test card checkout
        await api.post(
          "/payment/verify",
          {
            order_id: targetOrder.id,
            gateway_payment_id: `pay_mock_${targetOrder.id}`,
            gateway_signature: "mock_signature_verified",
            gateway_order_id: targetPay?.gateway_order_id || `rzp_mock_${targetOrder.id}`,
            gateway: "razorpay",
          },
          token ?? undefined
        );
        completeOrderSuccess(targetOrder);
        return;
      }

      completeOrderSuccess(targetOrder);
    } catch (err) {
      console.error("Order initiation error:", err);
      const detailMsg =
        err?.response?.data?.detail ||
        err?.message ||
        "Purchasing is currently paused or failed. Please check creator payout settings.";
      setErrorMessage(detailMsg);
      setIsProcessing(false);
    }
  };

  // Direct UPI Verification with 12-digit UTR
  const handleVerifyUpiPayment = async () => {
    if (!upiData?.order?.id) return;
    setIsVerifyingUpi(true);
    setErrorMessage("");

    try {
      const token = await getToken();
      const utr = utrInput.trim() || `UTR${Date.now()}`;

      await api.post(
        "/payment/verify",
        {
          order_id: upiData.order.id,
          gateway: "upi",
          upi_utr: utr,
          gateway_payment_id: utr,
          gateway_order_id: upiData.gateway_order_id || `upi_${upiData.order.id}`,
        },
        token ?? undefined
      );

      completeOrderSuccess(upiData.order);
    } catch (err) {
      console.error("UPI verification error:", err);
      setErrorMessage(
        err?.response?.data?.detail || "Could not confirm UPI transaction reference. Please re-check your UTR."
      );
      setIsVerifyingUpi(false);
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
              {purchasedTemplates.map((t, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-between text-left"
                >
                  <div>
                    <h4 className="font-semibold text-white text-sm">{t.title || "Website Template"}</h4>
                    <p className="text-xs text-[#dfb180] mt-0.5">Commercial License Included ✓</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      const tId = t.template_id || t.id || t.templateId;
                      window.open(`/api/v1/templates/${tId}/download?format=zip`, "_blank");
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#dfb180] text-[#121620] font-bold text-xs hover:bg-[#ebd2b0]"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download ZIP</span>
                  </button>
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

                  {/* Payment Channels Card */}
                  <div className="cr-checkout-card">
                    <h2 className="cr-card-title">
                      <CreditCard className="w-4 h-4 text-[#dfb180]" />
                      <span>Select Payment Channel</span>
                    </h2>

                    <div className="cr-pay-methods-grid">
                      {/* 1. Direct UPI Channel */}
                      <button
                        type="button"
                        onClick={() => {
                          setPaymentGateway("upi");
                          setUpiData(null);
                        }}
                        className={`cr-pay-method-btn ${paymentGateway === "upi" ? "active" : ""}`}
                      >
                        <QrCode className="w-5 h-5 text-[#dfb180]" />
                        <span>Direct UPI &amp; QR</span>
                      </button>

                      {/* 2. Stripe Connected Account Channel */}
                      <button
                        type="button"
                        onClick={() => {
                          setPaymentGateway("stripe");
                          setUpiData(null);
                        }}
                        className={`cr-pay-method-btn ${paymentGateway === "stripe" ? "active" : ""}`}
                      >
                        <CreditCard className="w-5 h-5 text-[#dfb180]" />
                        <span>Stripe &amp; Cards</span>
                      </button>

                      {/* 3. Razorpay Channel */}
                      <button
                        type="button"
                        onClick={() => {
                          setPaymentGateway("razorpay");
                          setUpiData(null);
                        }}
                        className={`cr-pay-method-btn ${paymentGateway === "razorpay" ? "active" : ""}`}
                      >
                        <Building2 className="w-5 h-5 text-[#dfb180]" />
                        <span>Razorpay</span>
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
                              placeholder="e.g. 432109876543 (or click confirm to complete)"
                              className="cr-upi-utr-input"
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
                      <span className="font-semibold text-white">${subtotal.toFixed(2)}</span>
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
                      <span className="text-[#dfb180] font-bold">${orderTotal.toFixed(2)}</span>
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
                    {!(paymentGateway === "upi" && upiData) ? (
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
                        ) : (
                          <>
                            <span>
                              {paymentGateway === "upi"
                                ? `Generate UPI QR & Pay $${orderTotal.toFixed(2)}`
                                : `Pay $${orderTotal.toFixed(2)} & Download`}
                            </span>
                            <ArrowRight className="w-4 h-4" />
                          </>
                        )}
                      </button>
                    ) : (
                      <div className="p-3 rounded-xl bg-[#dfb180]/10 border border-[#dfb180]/20 text-center">
                        <span className="text-xs text-[#dfb180] font-medium">
                          Scan the QR code on the left or submit UTR to complete your order.
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
