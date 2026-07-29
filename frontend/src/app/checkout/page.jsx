"use client";

/**
 * Checkout Page - high-fidelity payment flow using Razorpay and Stripe gateways (React JSX).
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
  ShieldCheck,
  Trash2,
  Loader2,
  ArrowRight,
  Download,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useCartStore } from "@/store";
import { api } from "@/lib/api";
import { cn, formatPrice } from "@/lib/utils";
import Image from "@/components/Image";
import "./Page.css";
import Link from "@/components/Link";

function Checkout() {
  const qc = useQueryClient();
  const { getToken } = useAppAuth();
  const { user } = useAppUser();
  const router = useRouter();
  const { items, removeItem, clearCart, total } = useCartStore();
  const [paymentGateway, setPaymentGateway] = useState("stripe");
  const [authToken, setAuthToken] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentStep, setPaymentStep] = useState("cart"); // "cart" | "paying" | "success"
  const [initiatedOrder, setInitiatedOrder] = useState(null);
  const [initiatedPayment, setInitiatedPayment] = useState(null);

  // Simulated Card Info
  const [cardNumber, setCardNumber] = useState("4242 4242 4242 4242");
  const [cardExpiry, setCardExpiry] = useState("12/28");
  const [cardCvc, setCardCvc] = useState("123");
  const [errors, setErrors] = useState({ card: "", expiry: "", cvc: "" });

  const handleCardNumberChange = (val) => {
    const cleaned = val.replace(/\s+/g, '');
    if (/[^\d]/.test(cleaned)) {
      setErrors(prev => ({ ...prev, card: "Please enter numbers only." }));
      return;
    }
    setErrors(prev => ({ ...prev, card: "" }));
    const digitsOnly = cleaned.slice(0, 16);
    const formatted = digitsOnly.replace(/(\d{4})(?=\d)/g, '$1 ');
    setCardNumber(formatted);
  };

  const handleCardExpiryChange = (val) => {
    const cleaned = val.replace(/[^\d/]/g, '');
    if (cleaned !== val) {
      setErrors(prev => ({ ...prev, expiry: "Please enter numbers only." }));
      return;
    }
    setErrors(prev => ({ ...prev, expiry: "" }));
    let digits = val.replace(/[^\d]/g, '').slice(0, 4);
    if (digits.length > 2) {
      setCardExpiry(`${digits.slice(0, 2)}/${digits.slice(2)}`);
    } else {
      setCardExpiry(digits);
    }
  };

  const handleCardCvcChange = (val) => {
    if (/[^\d]/.test(val)) {
      setErrors(prev => ({ ...prev, cvc: "Please enter numbers only." }));
      return;
    }
    setErrors(prev => ({ ...prev, cvc: "" }));
    const digitsOnly = val.slice(0, 4);
    setCardCvc(digitsOnly);
  };



  const isSeller = user?.role === "seller" || user?.role === "SELLER";

  useEffect(() => {
    getToken().then(setAuthToken);
  }, [getToken]);

  if (isSeller) {
    return (
      <>
        <Navbar />
        <div className="checkout-restricted-page">
          <div className="checkout-restricted-banner">
            <div className="checkout-restricted-icon-box">
              <ShieldCheck className="w-8 h-8 text-red-500" />
            </div>
            <h1 className="checkout-restricted-title">Purchase Restricted</h1>
            <p className="checkout-restricted-desc">
              As a registered Seller on AI Site Studio, you cannot purchase templates. If you want to buy templates, please sign in with a Buyer account.
            </p>
            <Link
              href="/dashboard"
              className="checkout-restricted-btn"
            >
              Go to Dashboard
            </Link>
          </div>
        </div>
      </>
    );
  }

  // Create Order Mutation
  const createOrderMutation = useMutation({
    pointer: "createOrder",
    mutationFn: () =>
      api.post(
        "/orders",
        {
          items: items.map((i) => ({
            template_id: i.templateId,
            license_type: i.licenseType,
          })),
        },
        authToken ?? undefined
      ),
  });

  // Initiate Payment Mutation
  const initiatePaymentMutation = useMutation({
    pointer: "initiatePayment",
    mutationFn: ({ orderId, gateway }) =>
      api.post(
        "/payment/initiate",
        { order_id: orderId, gateway },
        authToken ?? undefined
      ),
  });

  // Verify Payment Mutation
  const verifyPaymentMutation = useMutation({
    pointer: "verifyPayment",
    mutationFn: (payload) => api.post("/payment/verify", payload, authToken ?? undefined),
  });

  const handleCheckout = async () => {
    if (items.length === 0 || !authToken) return;
    setIsProcessing(true);

    try {
      // 1. Create PENDING order
      const order = await createOrderMutation.mutateAsync();
      setInitiatedOrder(order);

      // 2. Initiate Payment Session
      const payInfo = await initiatePaymentMutation.mutateAsync({
        orderId: order.id,
        gateway: paymentGateway,
      });
      setInitiatedPayment(payInfo);

      // 3. Move to Payment Input step
      setPaymentStep("paying");
    } catch (err) {
      console.error(err);
      alert("Checkout initialization failed. Please try again.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleVerifyMockPayment = async () => {
    if (!initiatedOrder || !initiatedPayment) return;

    // Validate simulated card inputs before processing
    const cleanCard = cardNumber.replace(/\s+/g, '');
    const cleanExpiry = cardExpiry.replace(/\//g, '');
    
    let hasError = false;
    const newErrors = { card: "", expiry: "", cvc: "" };

    if (cleanCard.length < 16) {
      newErrors.card = "Card Number must be 16 digits.";
      hasError = true;
    }
    if (cleanExpiry.length < 4) {
      newErrors.expiry = "Expiration Date must be MM/YY.";
      hasError = true;
    } else {
      const month = parseInt(cleanExpiry.slice(0, 2), 10);
      if (month < 1 || month > 12) {
        newErrors.expiry = "Month must be between 01 and 12.";
        hasError = true;
      }
    }
    if (cardCvc.length < 3 || cardCvc.length > 4) {
      newErrors.cvc = "CVC must be 3 or 4 digits.";
      hasError = true;
    }

    if (hasError) {
      setErrors(newErrors);
      return;
    }

    setErrors({ card: "", expiry: "", cvc: "" });
    setIsProcessing(true);

    try {
      // Verify payment with mock transaction ID
      await verifyPaymentMutation.mutateAsync({
        order_id: initiatedOrder.id,
        gateway: paymentGateway,
        gateway_payment_id: paymentGateway === "stripe"
          ? "pi_mock_" + Math.random().toString(36).substring(7)
          : "pay_mock_" + Math.random().toString(36).substring(7),
        gateway_order_id: initiatedPayment.gateway_order_id,
        gateway_signature: "mock_signature_verified",
      });

      // Automatically download each item's source code ZIP
      for (const item of initiatedOrder.items) {
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

      // Invalidate react-query cache to force refetching of orders and dashboard stats
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["dashboard-stats"] });

      setPaymentStep("success");
      clearCart();
      setTimeout(() => {
        router.push("/dashboard?tab=buyer-templates");
      }, 3000);
    } catch (err) {
      console.error(err);
      alert("Simulated transaction failed. Please retry.");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <>
      <Navbar />
      <div className="checkout-page">
        <div className="checkout-container">
          {paymentStep === "success" ? (
            <div className="checkout-card" style={{ maxWidth: "600px", margin: "4rem auto", textAlign: "center", padding: "3rem", display: "flex", flexDirection: "column", gap: "1.5rem", alignItems: "center" }}>
              <div style={{ width: "4rem", height: "4rem", borderRadius: "50%", backgroundColor: "rgba(16, 185, 129, 0.1)", display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "center", color: "hsl(var(--success, 142.1 76.2% 36.3%))" }}>
                <ShieldCheck className="w-10 h-10 text-emerald-500" />
              </div>
              <h1 className="text-2xl font-bold text-foreground">Payment Successful!</h1>
              <p className="text-sm text-muted-foreground">
                Your order <strong>#{initiatedOrder?.order_number || "ASS-MOCK"}</strong> has been processed successfully.
              </p>
              <div className="p-4 bg-muted/20 border border-border/50 rounded-xl text-xs space-y-1 text-left w-full">
                <div className="flex justify-between"><strong>Status:</strong> <span className="text-emerald-500 font-bold">COMPLETED</span></div>
                <div className="flex justify-between"><strong>Transaction ID:</strong> <span className="font-mono text-muted-foreground">TXN-MOCK-{initiatedOrder?.id?.slice(0, 8)}</span></div>
                <div className="flex justify-between"><strong>Amount Paid:</strong> <span>{formatPrice(total())}</span></div>
              </div>
              <p className="text-xs text-muted-foreground animate-pulse">
                Your browser will automatically download the template source ZIP packages. Redirecting to your dashboard...
              </p>
              <Link href="/dashboard" className="checkout-browse-btn" style={{ width: "100%", textAlign: "center" }}>
                Go to Dashboard
              </Link>
            </div>
          ) : paymentStep === "paying" ? (
            <div className="checkout-grid" style={{ maxWidth: "800px", margin: "2rem auto" }}>
              <div className="checkout-left-block" style={{ gridColumn: "span 2" }}>
                <div className="checkout-card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                  <div className="flex items-center justify-between border-b border-border/50 pb-4">
                    <h3 className="font-bold text-lg flex items-center gap-2">
                      <CreditCard className="w-5 h-5 text-primary" /> Confirm Sandbox Checkout
                    </h3>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-bold uppercase">
                      {paymentGateway} Mode
                    </span>
                  </div>

                  <div className="p-4 bg-primary/5 border border-primary/20 rounded-xl space-y-2">
                    <p className="text-xs text-muted-foreground">
                      This platform is running in <strong>Sandbox Mode</strong>. Please use the simulated checkout card details below to complete your checkout flow:
                    </p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Card Number</label>
                      <input
                        type="text"
                        value={cardNumber}
                        onChange={(e) => handleCardNumberChange(e.target.value)}
                        className={cn(
                          "w-full px-3 py-2 rounded-lg glass border text-xs focus:outline-none bg-card text-foreground transition-all",
                          errors.card ? "border-red-500/80 focus:border-red-500 focus:ring-1 focus:ring-red-500" : "border-border/50 focus:border-primary"
                        )}
                      />
                      {errors.card && (
                        <p className="text-[10px] text-red-500 mt-1 font-semibold">{errors.card}</p>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Expiration Date</label>
                        <input
                          type="text"
                          value={cardExpiry}
                          onChange={(e) => handleCardExpiryChange(e.target.value)}
                          placeholder="MM/YY"
                          className={cn(
                            "w-full px-3 py-2 rounded-lg glass border text-xs focus:outline-none bg-card text-foreground transition-all",
                            errors.expiry ? "border-red-500/80 focus:border-red-500 focus:ring-1 focus:ring-red-500" : "border-border/50 focus:border-primary"
                          )}
                        />
                        {errors.expiry && (
                          <p className="text-[10px] text-red-500 mt-1 font-semibold">{errors.expiry}</p>
                        )}
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">CVC / CVV</label>
                        <input
                          type="password"
                          value={cardCvc}
                          onChange={(e) => handleCardCvcChange(e.target.value)}
                          placeholder="•••"
                          className={cn(
                            "w-full px-3 py-2 rounded-lg glass border text-xs focus:outline-none bg-card text-foreground transition-all",
                            errors.cvc ? "border-red-500/80 focus:border-red-500 focus:ring-1 focus:ring-red-500" : "border-border/50 focus:border-primary"
                          )}
                        />
                        {errors.cvc && (
                          <p className="text-[10px] text-red-500 mt-1 font-semibold">{errors.cvc}</p>
                        )}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
                    <button
                      onClick={() => setPaymentStep("cart")}
                      className="py-2.5 px-4 border border-border hover:border-slate-500 rounded-xl text-xs font-semibold transition-all"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleVerifyMockPayment}
                      disabled={isProcessing}
                      className="flex-1 py-2.5 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/95 transition-all flex items-center justify-center gap-1"
                    >
                      {isProcessing ? (
                        <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Verifying Payment...</>
                      ) : (
                        <>Pay {formatPrice(total())} and Download</>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="checkout-grid">
              {/* Left: Cart items & Gateway selection */}
              <div className="checkout-left-block">
                <div className="checkout-card">
                  <h1 className="checkout-header">
                    <ShoppingBag className="checkout-icon" /> Shopping Cart
                  </h1>

                  {items.length === 0 ? (
                    <div className="checkout-empty-state">
                      <p className="checkout-empty-msg">Your cart is empty.</p>
                      <Link href="/marketplace" className="checkout-browse-btn">
                        Browse Marketplace <ArrowRight className="checkout-arrow-icon" />
                      </Link>
                    </div>
                  ) : (
                    <div className="checkout-items-list">
                      {items.map((item) => (
                        <div key={item.templateId} className="checkout-item-row">
                          <div className="checkout-item-left">
                            <div className="checkout-thumbnail-box">
                              {item.thumbnail && (
                                <Image src={item.thumbnail} alt={item.title} fill className="checkout-thumb-img" />
                              )}
                            </div>
                            <div>
                              <h3 className="checkout-item-title">{item.title}</h3>
                              <span className="checkout-item-license">Lifetime Access</span>
                            </div>
                          </div>
                          <div className="checkout-item-right">
                            <span className="checkout-item-price">{formatPrice(item.price)}</span>
                            <button onClick={() => removeItem(item.templateId)} className="checkout-item-delete">
                              <Trash2 className="checkout-trash-icon" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {items.length > 0 && (
                  <div className="checkout-card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <h3 className="font-bold text-sm">Select Payment Gateway</h3>
                    <div className="grid grid-cols-2 gap-3">
                      <button
                        onClick={() => setPaymentGateway("stripe")}
                        className={cn(
                          "p-3 rounded-xl border text-xs font-semibold flex flex-col items-center gap-1.5 transition-all bg-card/40 hover:bg-card/75",
                          paymentGateway === "stripe" ? "border-primary text-primary bg-primary/5" : "border-border/50 text-muted-foreground"
                        )}
                      >
                        <CreditCard className="w-5 h-5" />
                        Stripe Payment
                      </button>
                      <button
                        onClick={() => setPaymentGateway("razorpay")}
                        className={cn(
                          "p-3 rounded-xl border text-xs font-semibold flex flex-col items-center gap-1.5 transition-all bg-card/40 hover:bg-card/75",
                          paymentGateway === "razorpay" ? "border-primary text-primary bg-primary/5" : "border-border/50 text-muted-foreground"
                        )}
                      >
                        <CreditCard className="w-5 h-5" />
                        Razorpay India
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Right: Summary Box */}
              <div className="checkout-right-block">
                <div className="checkout-card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                  <h3 className="font-bold text-base border-b border-border/50 pb-4">Order Summary</h3>
                  <div className="summary-items-list">
                    <div className="summary-item-row">
                      <span>Subtotal</span>
                      <span>{formatPrice(total())}</span>
                    </div>
                    <div className="summary-item-row">
                      <span>Taxes</span>
                      <span>$0.00</span>
                    </div>
                    <div className="summary-total-row">
                      <span>Total Amount</span>
                      <span>{formatPrice(total())}</span>
                    </div>
                  </div>

                  <button
                    onClick={handleCheckout}
                    disabled={items.length === 0 || isProcessing}
                    className="checkout-submit-btn"
                  >
                    {isProcessing ? (
                      <><Loader2 className="checkout-btn-loader animate-spin" /> Starting Payment Session…</>
                    ) : (
                      <><CreditCard className="checkout-btn-icon" /> Checkout & Pay</>
                    )}
                  </button>

                  <div className="checkout-security-badge">
                    <ShieldCheck className="security-shield-icon" />
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

export default Checkout;
