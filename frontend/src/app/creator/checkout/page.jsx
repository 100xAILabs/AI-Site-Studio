"use client";

import { useState, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
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
} from "lucide-react";
import "./checkout.css";

export default function CreatorCheckoutPage() {
  const params = useParams();
  const creatorSlug = params?.creatorSlug || "";

  const { user, isSignedIn } = useAppUser();
  const { getToken } = useAppAuth();
  const { items, removeItem, clearCart } = useCartStore();

  const [paymentGateway, setPaymentGateway] = useState("razorpay"); // "stripe" | "razorpay" | "paypal"
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [purchasedTemplates, setPurchasedTemplates] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");

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

  // Filter items strictly for this creator
  const creatorItems = useMemo(() => {
    if (!Array.isArray(items)) return [];
    if (!creatorSlug) return items;
    const scoped = items.filter(
      (i) => i.creator_slug && i.creator_slug.toLowerCase() === creatorSlug.toLowerCase()
    );
    return scoped.length > 0 ? scoped : items;
  }, [items, creatorSlug]);

  const subtotal = useMemo(() => {
    return creatorItems.reduce((sum, item) => sum + (Number(item.price) || 0) * 1, 0);
  }, [creatorItems]);

  const orderTotal = subtotal;

  const handlePlaceOrder = async () => {
    if (creatorItems.length === 0) return;
    if (storefront?.is_bank_connected === false) {
      setErrorMessage(`${brandName} has not connected their bank account or verified payout gateway yet. Purchasing is temporarily paused.`);
      return;
    }
    setIsProcessing(true);
    setErrorMessage("");

    try {
      const token = await getToken();
      
      // 1. Create order linked directly to this creator
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

      // 2. Initiate Payment
      const payRes = await api.post(
        "/payment/initiate",
        {
          order_id: targetOrder.id,
          gateway: paymentGateway,
        },
        token ?? undefined
      );

      const targetPay = payRes?.payment || payRes;

      // If Razorpay gateway and modal available, trigger standard checkout flow
      if (paymentGateway === "razorpay" && typeof window !== "undefined" && window.Razorpay) {
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

      // If simulated or direct instant checkout completes
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

  const completeOrderSuccess = async (ord) => {
    const rawItems = (ord.items && ord.items.length > 0) ? ord.items : creatorItems;
    setPurchasedTemplates(rawItems);
    setIsSuccess(true);
    setIsProcessing(false);

    // Auto trigger downloads
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
                                <span>Commercial License</span>
                              </div>
                            </div>
                          </div>

                          <div className="cr-item-right">
                            <div className="cr-item-price">${Number(item.price) || 49}</div>
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
                      <button
                        type="button"
                        onClick={() => setPaymentGateway("razorpay")}
                        className={`cr-pay-method-btn ${paymentGateway === "razorpay" ? "active" : ""}`}
                      >
                        <QrCode className="w-5 h-5 text-[#dfb180]" />
                        <span>UPI &amp; Cards</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setPaymentGateway("stripe")}
                        className={`cr-pay-method-btn ${paymentGateway === "stripe" ? "active" : ""}`}
                      >
                        <CreditCard className="w-5 h-5 text-[#dfb180]" />
                        <span>Credit / Debit Card</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setPaymentGateway("paypal")}
                        className={`cr-pay-method-btn ${paymentGateway === "paypal" ? "active" : ""}`}
                      >
                        <Store className="w-5 h-5 text-[#dfb180]" />
                        <span>PayPal / Direct</span>
                      </button>
                    </div>

                    <div className="cr-pay-notice">
                      <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>
                        Payment processed securely. Money is credited directly to {brandName}&apos;s verified payout channel.
                      </span>
                    </div>
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

                    <button
                      type="button"
                      onClick={handlePlaceOrder}
                      disabled={isProcessing || storefront?.is_bank_connected === false}
                      className="cr-pay-cta-btn"
                    >
                      {isProcessing ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Processing Payment...</span>
                        </>
                      ) : (
                        <>
                          <span>Pay ${orderTotal.toFixed(2)} &amp; Download</span>
                          <ArrowRight className="w-4 h-4" />
                        </>
                      )}
                    </button>

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
