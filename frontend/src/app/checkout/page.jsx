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
import { QRCodeSVG } from "qrcode.react";
import {
  CreditCard,
  ShoppingBag,
  ShieldCheck,
  Trash2,
  Loader2,
  ArrowRight,
  Download,
  QrCode,
  ScanQrCode,
  CheckCircle2,
  Copy,
  ExternalLink,
  Smartphone,
  Check,
  Clock,
  RotateCcw,
  Lock,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useCartStore } from "@/store";
import { api } from "@/lib/api";
import { cn, formatPrice, formatConvertedPrice } from "@/lib/utils";
import { useCurrencyStore } from "@/store/currencyStore";
import Image from "@/components/Image";
import "./Page.css";
import Link from "@/components/Link";
import { TEMPLATE_DOWNLOADS_FREE } from "@/lib/marketplaceConfig";

// Toggle external card gateways (Razorpay / Stripe)
const ENABLE_EXTERNAL_GATEWAYS = true;

function Checkout() {
  const qc = useQueryClient();
  const { getToken } = useAppAuth();
  const { user } = useAppUser();
  const { userCurrency, rates } = useCurrencyStore();
  const router = useRouter();
  const { items, removeItem, clearCart, total } = useCartStore();
  const [paymentGateway, setPaymentGateway] = useState("upi"); // "upi" | "razorpay" | "stripe"
  const [paymentMethodType, setPaymentMethodType] = useState("upi"); // "upi" | "card"
  const [authToken, setAuthToken] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentStep, setPaymentStep] = useState("cart"); // "cart" | "paying" | "success"
  const [freeDownloads, setFreeDownloads] = useState([]);
  const [freeDownloadsComplete, setFreeDownloadsComplete] = useState(false);
  const [initiatedOrder, setInitiatedOrder] = useState(null);
  const [initiatedPayment, setInitiatedPayment] = useState(null);
  const [vpaCopied, setVpaCopied] = useState(false);
  const [upiUtr, setUpiUtr] = useState("");
  const [upiUtrSubmitted, setUpiUtrSubmitted] = useState(false);
  const [utrError, setUtrError] = useState("");

  // 5-minute QR Code timer & auto-refresh state
  const [qrTimerSeconds, setQrTimerSeconds] = useState(300); // 5 mins = 300s
  const [qrNonce, setQrNonce] = useState(Date.now());
  const [qrRefreshedNotice, setQrRefreshedNotice] = useState(false);

  useEffect(() => {
    if (paymentStep !== "paying" || paymentGateway !== "upi") {
      setQrTimerSeconds(300);
      return;
    }

    const interval = setInterval(() => {
      setQrTimerSeconds((prev) => {
        if (prev <= 1) {
          // Auto-refresh QR code after 5 minutes
          setQrNonce(Date.now());
          setQrRefreshedNotice(true);
          setTimeout(() => setQrRefreshedNotice(false), 4000);
          return 300; // Reset 5-minute timer
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [paymentStep, paymentGateway]);

  const handleManualRefreshQr = () => {
    setQrTimerSeconds(300);
    setQrNonce(Date.now());
    setQrRefreshedNotice(true);
    setTimeout(() => setQrRefreshedNotice(false), 4000);
  };

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

  const [liveRate, setLiveRate] = useState(95.48);

  useEffect(() => {
    getToken().then(setAuthToken).catch(() => {});
    api.get("/payment/exchange-rate")
      .then(res => {
        if (res?.rate) setLiveRate(res.rate);
      })
      .catch(() => {});
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
            setUtrError("The submitted payment reference was not approved. Check it and contact support if you believe this is incorrect.");
          }
        } catch (e) {
          // Silent catch for background polling
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [paymentStep, initiatedOrder, authToken, upiUtrSubmitted]);

  const copyVpaToClipboard = (vpaText) => {
    navigator.clipboard.writeText(vpaText);
    setVpaCopied(true);
    setTimeout(() => setVpaCopied(false), 2000);
  };

  const handleCompleteSuccessFlow = async (orderToProcess) => {
    const ord = orderToProcess || initiatedOrder;
    if (!ord) return;

    // Automatically download each item's source code ZIP
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
    }, 3000);
  };

  if (isSeller && !TEMPLATE_DOWNLOADS_FREE) {
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
              As a registered Seller on Site Studio, you cannot purchase templates. If you want to buy templates, please sign in with a Buyer account.
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

  // Load Razorpay Checkout SDK dynamically
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
      theme: {
        color: "#6366f1",
      },
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
          alert(
            err?.response?.data?.detail ||
            "Payment verification failed. Please try again or contact support."
          );
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
        alert(
          `Payment Failed: ${
            response.error?.description || response.error?.reason || "Transaction failed"
          }`
        );
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
    if (items.length === 0) return;
    if (TEMPLATE_DOWNLOADS_FREE) {
      if (!authToken) {
        router.push(`/sign-in?from=${encodeURIComponent("/checkout")}`);
        return;
      }
      setIsProcessing(true);
      try {
        const ready = [];
        for (const item of items) {
          const result = await api.post(`/templates/${item.templateId}/download?format=zip`, {}, authToken);
          if (!result?.download_url) throw new Error(`Could not prepare the download for ${item.title}.`);
          ready.push({ id: item.templateId, title: item.title, downloadUrl: result.download_url });
        }
        setFreeDownloads(ready);
        setFreeDownloadsComplete(true);
        clearCart();
      } catch (err) {
        console.error("Free template download preparation failed:", err);
        alert(err.message || "Could not prepare your free downloads. Please try again.");
      } finally {
        setIsProcessing(false);
      }
      return;
    }
    if (!authToken) {
      router.push("/login?redirect=/checkout");
      return;
    }
    setIsProcessing(true);

    const activeGateway = ENABLE_EXTERNAL_GATEWAYS ? paymentGateway : "upi";

    try {
      // 1. Create PENDING order
      const order = await createOrderMutation.mutateAsync();
      setInitiatedOrder(order);

      // 2. Initiate Payment Session
      const payInfo = await initiatePaymentMutation.mutateAsync({
        orderId: order.id,
        gateway: activeGateway,
      });
      setInitiatedPayment(payInfo);

      const isRealRazorpay =
        activeGateway === "razorpay" &&
        payInfo?.gateway_order_id &&
        !payInfo.gateway_order_id.startsWith("rzp_mock_");

      setPaymentStep("paying");

      // 3. If real Razorpay order, trigger Razorpay popup directly
      if (isRealRazorpay) {
        await handleOpenRazorpay(order, payInfo);
      }
    } catch (err) {
      console.error(err);
      alert("Checkout initialization failed. Please try again.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleUtrChange = (val) => {
    const cleaned = val.replace(/\D/g, "").slice(0, 12);
    setUpiUtr(cleaned);
    setUpiUtrSubmitted(false);
    if (cleaned.length === 12) {
      setUtrError("");
    }
  };

  const handleVerifyUpiPayment = async () => {
    if (!initiatedOrder || !initiatedPayment) return;
    if (upiUtr.length !== 12) {
      setUtrError("Please enter the complete 12-digit UPI Reference (UTR) number from your payment receipt.");
      return;
    }

    setIsProcessing(true);
    setUtrError("");
    try {
      await verifyPaymentMutation.mutateAsync({
        order_id: initiatedOrder.id,
        gateway: "upi",
        gateway_payment_id: "UTR:" + upiUtr,
        gateway_order_id: initiatedPayment.gateway_order_id,
        gateway_signature: "upi_utr_verified",
        upi_utr: upiUtr,
      });

      setUpiUtrSubmitted(true);
    } catch (err) {
      console.error("UPI verification error:", err);
      const errorMsg =
        err?.response?.data?.detail ||
        err?.message ||
        "Verification failed. Please check the 12-digit UTR and retry.";
      setUtrError(errorMsg);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleVerifyMockPayment = async () => {
    if (!initiatedOrder || !initiatedPayment) return;

    if (paymentGateway !== "upi") {
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
    }

    setErrors({ card: "", expiry: "", cvc: "" });
    setIsProcessing(true);

    try {
      // Verify payment with gateway transaction ID
      await verifyPaymentMutation.mutateAsync({
        order_id: initiatedOrder.id,
        gateway: paymentGateway,
        gateway_payment_id: paymentGateway === "stripe"
          ? "pi_mock_" + Math.random().toString(36).substring(7)
          : "pay_mock_" + Math.random().toString(36).substring(7),
        gateway_order_id: initiatedPayment.gateway_order_id,
        gateway_signature: "mock_signature_verified",
      });

      setUpiUtrSubmitted(true);
    } catch (err) {
      console.error(err);
      alert("Simulated transaction failed. Please retry.");
    } finally {
      setIsProcessing(false);
    }
  };

  const hasInrItems = items.some(i => (i.price_currency || "").toUpperCase() === "INR");
  const inrAmountVal = initiatedPayment?.amount
    ? (initiatedPayment.amount / 100)
    : hasInrItems
    ? total()
    : (total() * liveRate);
  const inrAmountString = `₹${inrAmountVal.toFixed(2)}`;
  const minutesLeft = Math.floor(qrTimerSeconds / 60);
  const secondsLeft = qrTimerSeconds % 60;
  const timerFormatted = `${String(minutesLeft).padStart(2, '0')}:${String(secondsLeft).padStart(2, '0')}`;
  const merchantVpa = initiatedPayment?.vpa || "";
  const merchantName = initiatedPayment?.merchant_name || "AI Site Studio";
  const defaultUpiUri = initiatedPayment?.upi_uri || `upi://pay?pa=${encodeURIComponent(merchantVpa)}&pn=${encodeURIComponent(merchantName)}&am=${inrAmountVal.toFixed(2)}&cu=INR&tn=Order%20${initiatedOrder?.id?.slice(0, 8) || "ASS"}&nonce=${qrNonce}`;
  const isRealRazorpay =
    paymentGateway === "razorpay" &&
    initiatedPayment?.gateway_order_id &&
    !initiatedPayment.gateway_order_id.startsWith("rzp_mock_");

  return (
    <>
      <Navbar />
      <div className="checkout-page">
        <div className="checkout-container">
          {freeDownloadsComplete ? (
            <div className="checkout-success-card">
              <div style={{ width: "4rem", height: "4rem", borderRadius: "50%", backgroundColor: "rgba(16, 185, 129, 0.1)", display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "center", color: "hsl(var(--success, 142.1 76.2% 36.3%))" }}>
                <CheckCircle2 className="w-10 h-10 text-emerald-500" />
              </div>
              <h1 className="text-2xl font-bold text-foreground">Your free downloads are ready</h1>
              <p className="text-sm text-muted-foreground">Choose a file below to download its template ZIP. No payment was taken.</p>
              <div className="w-full space-y-2">
                {freeDownloads.map((file) => (
                  <a key={file.id} href={file.downloadUrl} target="_blank" rel="noopener noreferrer" download className="checkout-browse-btn" style={{ width: "100%", justifyContent: "center", textDecoration: "none" }}>
                    <Download className="w-4 h-4" /> Download {file.title}
                  </a>
                ))}
              </div>
              <Link href="/marketplace" className="checkout-browse-btn" style={{ width: "100%", textAlign: "center", justifyContent: "center" }}>
                Back to Marketplace
              </Link>
            </div>
          ) : paymentStep === "success" ? (
            <div className="checkout-success-card">
              <div style={{ width: "4rem", height: "4rem", borderRadius: "50%", backgroundColor: "rgba(16, 185, 129, 0.1)", display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "center", color: "hsl(var(--success, 142.1 76.2% 36.3%))" }}>
                <ShieldCheck className="w-10 h-10 text-emerald-500" />
              </div>
              <h1 className="text-2xl font-bold text-foreground">Payment Successful!</h1>
              <p className="text-sm text-muted-foreground">
                Your order <strong>#{initiatedOrder?.order_number || "ASS-ORDER"}</strong> has been processed successfully.
              </p>
              <div className="p-4 bg-muted/20 border border-border/50 rounded-xl text-xs space-y-1.5 text-left w-full">
                <div className="flex justify-between"><strong>Status:</strong> <span className="text-emerald-500 font-bold">COMPLETED</span></div>
                <div className="flex justify-between"><strong>Gateway:</strong> <span className="font-semibold uppercase">{paymentGateway}</span></div>
                {upiUtr && (
                  <div className="flex justify-between">
                    <strong>UPI Ref (UTR):</strong> <span className="font-mono font-bold text-emerald-600">{upiUtr}</span>
                  </div>
                )}
                <div className="flex justify-between"><strong>Amount Paid:</strong> <span className="font-bold text-foreground">{inrAmountString}</span></div>
              </div>
              <p className="text-xs text-muted-foreground animate-pulse">
                Your browser will automatically download the template source ZIP packages. Redirecting to your dashboard...
              </p>
              <Link href="/dashboard" className="checkout-browse-btn" style={{ width: "100%", textAlign: "center", justifyContent: "center" }}>
                Go to Dashboard
              </Link>
            </div>
          ) : paymentStep === "paying" ? (
            <div className="checkout-paying-wrapper">
              {paymentGateway === "upi" ? (
                <div className="checkout-paying-card items-center text-center">
                  <div className="checkout-paying-header">
                    <h3 className="checkout-paying-title">
                      <ScanQrCode className="w-5 h-5 text-emerald-500 shrink-0" /> Pay via UPI QR Code / Apps
                    </h3>
                    <div className="checkout-paying-timer-bar">
                      <span className={cn(
                        "text-xs px-3 py-1 rounded-full font-bold flex items-center gap-1.5 border transition-all",
                        qrTimerSeconds > 60
                          ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/30"
                          : "bg-amber-500/10 text-amber-500 border-amber-500/30 animate-pulse"
                      )}>
                        <Clock className="w-3.5 h-3.5" />
                        QR Valid: {timerFormatted}
                      </span>
                      <button
                        type="button"
                        onClick={handleManualRefreshQr}
                        className="p-1.5 rounded-lg text-muted-foreground hover:text-emerald-400 bg-muted/20 hover:bg-emerald-500/10 border border-border/40 hover:border-emerald-500/30 transition-all cursor-pointer"
                        title="Refresh QR Code (Generate new 5-min session)"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="checkout-amount-badge">
                    <span className="text-muted-foreground font-medium">Amount Payable:</span>
                    <span className="text-base sm:text-lg font-bold text-emerald-500">{inrAmountString} <span className="text-xs text-muted-foreground font-normal">({formatPrice(total())})</span></span>
                  </div>

                  {/* QR Code Render Box */}
                  <div className="checkout-qr-box">
                    <div className="checkout-qr-svg-wrapper">
                      <QRCodeSVG
                        key={qrNonce}
                        value={defaultUpiUri}
                        size={190}
                        level="H"
                        includeMargin={true}
                      />
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-slate-700 font-semibold bg-slate-100 px-3 py-1 rounded-full">
                      <Smartphone className="w-3.5 h-3.5 text-emerald-600" /> Scan with any UPI App
                    </div>
                    {qrRefreshedNotice && (
                      <div className="text-xs text-emerald-600 font-semibold bg-emerald-50 border border-emerald-300 px-3 py-1 rounded-full animate-bounce">
                        ✨ QR Code refreshed for another 5 minutes!
                      </div>
                    )}
                  </div>

                  {/* VPA Copy Bar */}
                  <div className="checkout-vpa-box">
                    <div className="checkout-vpa-info">
                      <span className="checkout-vpa-label">UPI ID / VPA</span>
                      <span className="checkout-vpa-value">{merchantVpa}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => copyVpaToClipboard(merchantVpa)}
                      className="checkout-vpa-copy-btn"
                    >
                      {vpaCopied ? <><Check className="w-3.5 h-3.5 text-emerald-500" /> Copied!</> : <><Copy className="w-3.5 h-3.5" /> Copy VPA</>}
                    </button>
                  </div>

                  {/* Quick Launch UPI App Deep Links */}
                  <div className="checkout-upi-apps-section">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                        <Smartphone className="w-3.5 h-3.5 text-emerald-500" /> Pay Directly Using App:
                      </label>
                      <span className="text-[10px] text-emerald-600 font-semibold bg-emerald-500/10 px-2 py-0.5 rounded-full sm:hidden">
                        Tap to open app
                      </span>
                    </div>
                    <div className="checkout-upi-apps-grid">
                      <button
                        type="button"
                        onClick={() => window.open(defaultUpiUri, '_self')}
                        className="checkout-upi-app-btn"
                      >
                        <span className="checkout-upi-app-name text-blue-500">Google Pay</span>
                        <span className="checkout-upi-app-sub">Tap to Pay</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => window.open(defaultUpiUri, '_self')}
                        className="checkout-upi-app-btn"
                      >
                        <span className="checkout-upi-app-name text-purple-500">PhonePe</span>
                        <span className="checkout-upi-app-sub">Tap to Pay</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => window.open(defaultUpiUri, '_self')}
                        className="checkout-upi-app-btn"
                      >
                        <span className="checkout-upi-app-name text-sky-500">Paytm</span>
                        <span className="checkout-upi-app-sub">Tap to Pay</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => window.open(defaultUpiUri, '_self')}
                        className="checkout-upi-app-btn"
                      >
                        <span className="checkout-upi-app-name text-orange-500">BHIM UPI</span>
                        <span className="checkout-upi-app-sub">Tap to Pay</span>
                      </button>
                    </div>
                  </div>

                  {/* UPI Step 1 & 2 Explanatory Guide Banner */}
                  <div className="checkout-steps-banner">
                    <div className="flex items-center gap-2">
                      <Smartphone className="w-4 h-4 text-blue-500 shrink-0" />
                      <span><strong>1.</strong> Pay {inrAmountString} via UPI App • <strong>2.</strong> Submit the 12-digit UTR for review</span>
                    </div>
                    <span className="checkout-steps-pill">Manual Payment Review</span>
                  </div>

                  {/* Step 2: 12-Digit UTR Verification Form */}
                  <div className="checkout-utr-card">
                    {upiUtrSubmitted ? (
                      <div className="text-center py-6 space-y-3">
                        <Clock className="w-8 h-8 text-amber-500 mx-auto" />
                        <h3 className="font-bold">Payment reference submitted</h3>
                        <p className="text-sm text-muted-foreground">Your order is pending while an administrator checks the UTR against the merchant account. Downloads will be available after confirmation.</p>
                        <p className="text-xs text-muted-foreground">Reference: <span className="font-mono">{upiUtr}</span></p>
                      </div>
                    ) : (
                    <>
                    <div className="flex items-center justify-between flex-wrap gap-1">
                      <span className="checkout-utr-step-title">
                        <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" /> Step 2: Enter 12-Digit UPI Reference (UTR)
                      </span>
                      <span className={cn(
                        "checkout-utr-counter",
                        upiUtr.length === 12 && "is-complete"
                      )}>
                        {upiUtr.length} / 12 digits
                      </span>
                    </div>

                    <p className="checkout-utr-desc">
                      After completing the payment in <strong>Google Pay, PhonePe, Paytm, or BHIM</strong>, copy the <strong>12-digit UPI Ref / Transaction No. (UTR)</strong> from your app receipt and enter it below:
                    </p>

                    <div className="space-y-1.5">
                      <div className="relative">
                        <input
                          type="text"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          maxLength={12}
                          value={upiUtr}
                          onChange={(e) => handleUtrChange(e.target.value)}
                          placeholder="e.g. 428910293847"
                          className={cn(
                            "checkout-utr-input",
                            utrError
                              ? "is-error"
                              : upiUtr.length === 12
                              ? "is-valid"
                              : ""
                          )}
                        />
                        {upiUtr.length === 12 && (
                          <div className="checkout-utr-check-icon">
                            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                          </div>
                        )}
                      </div>

                      {utrError && (
                        <p className="checkout-utr-error-msg">
                          ⚠️ {utrError}
                        </p>
                      )}
                    </div>

                    <div className="checkout-action-row">
                      <button
                        type="button"
                        onClick={() => setPaymentStep("cart")}
                        className="checkout-cancel-btn"
                      >
                        Cancel / Change Method
                      </button>
                      <button
                        type="button"
                        onClick={handleVerifyUpiPayment}
                        disabled={upiUtr.length !== 12 || isProcessing}
                        className={cn(
                          "checkout-verify-btn",
                          upiUtr.length === 12 && !isProcessing && "active"
                        )}
                      >
                        {isProcessing ? (
                          <><Loader2 className="w-4 h-4 animate-spin" /> Submitting reference...</>
                        ) : (
                          <><ShieldCheck className="w-4 h-4" /> Submit UTR for Confirmation</>
                        )}
                      </button>
                    </div>
                    </>
                    )}
                  </div>
                </div>
              ) : isRealRazorpay ? (
                <div className="checkout-paying-card">
                  <div className="flex items-center justify-between border-b border-border/50 pb-4">
                    <h3 className="font-bold text-lg flex items-center gap-2">
                      <CreditCard className="w-5 h-5 text-primary" /> Razorpay Official Checkout
                    </h3>
                    <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-500 font-bold uppercase border border-emerald-500/30">
                      Live Gateway
                    </span>
                  </div>

                  <div className="p-4 bg-primary/5 border border-primary/20 rounded-xl space-y-3">
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Pay securely using <strong>UPI, Credit/Debit Cards, NetBanking, or Wallets</strong> via the official Razorpay checkout popup.
                    </p>
                    <div className="flex items-center justify-between pt-2 border-t border-primary/10 text-xs">
                      <span className="text-muted-foreground">Order ID:</span>
                      <span className="font-mono font-semibold">{initiatedOrder?.id?.slice(0, 13)}...</span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Amount Payable:</span>
                      <span className="font-bold text-primary text-sm">{inrAmountString}</span>
                    </div>
                  </div>

                  <div className="checkout-action-row">
                    <button
                      type="button"
                      onClick={() => setPaymentStep("cart")}
                      className="checkout-cancel-btn"
                    >
                      Back to Cart / Change Gateway
                    </button>
                    <button
                      type="button"
                      onClick={() => handleOpenRazorpay(initiatedOrder, initiatedPayment)}
                      disabled={isProcessing}
                      className="checkout-verify-btn active bg-primary hover:bg-primary/95 shadow-primary/25"
                    >
                      {isProcessing ? (
                        <><Loader2 className="w-4 h-4 animate-spin" /> Launching Razorpay...</>
                      ) : (
                        <><ShieldCheck className="w-4 h-4" /> Open Razorpay Payment Window ({inrAmountString})</>
                      )}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="checkout-paying-card">
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

                  <div className="checkout-action-row">
                    <button
                      type="button"
                      onClick={() => setPaymentStep("cart")}
                      className="checkout-cancel-btn"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleVerifyMockPayment}
                      disabled={isProcessing}
                      className="checkout-verify-btn active bg-primary hover:bg-primary/95 shadow-primary/25"
                    >
                      {isProcessing ? (
                        <><Loader2 className="w-4 h-4 animate-spin" /> Verifying Payment...</>
                      ) : (
                        <>Pay {formatPrice(total())} and Download</>
                      )}
                    </button>
                  </div>
                </div>
              )}
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
                            <span className="checkout-item-price">
                              {TEMPLATE_DOWNLOADS_FREE ? "Free" : formatConvertedPrice(item.price, item.price_currency || "USD", userCurrency, rates)}
                            </span>
                            <button onClick={() => removeItem(item.templateId)} className="checkout-item-delete">
                              <Trash2 className="checkout-trash-icon" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {items.length > 0 && !TEMPLATE_DOWNLOADS_FREE && (
                  <div className="checkout-card checkout-payment-card">
                    <div className="checkout-payment-header">
                      <h3 className="checkout-section-title">Select Payment Method</h3>
                      <span className="checkout-upi-active-badge">
                        <Check className="w-2.5 h-2.5 text-emerald-500" /> UPI payment
                      </span>
                    </div>

                    {/* 2 Primary Methods: Scanner for UPI, Card for others */}
                    <div className="checkout-gateway-grid">
                      <button
                        type="button"
                        onClick={() => {
                          setPaymentMethodType("upi");
                          setPaymentGateway("upi");
                        }}
                        className={cn(
                          "checkout-gateway-btn",
                          paymentMethodType === "upi" && "active-upi"
                        )}
                      >
                        <div className="checkout-gateway-left">
                          <ScanQrCode className="checkout-gateway-icon text-emerald-600" />
                          <span className="checkout-gateway-title">UPI QR & Apps</span>
                        </div>
                        <span className="checkout-gateway-badge-upi">
                          Manual review
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setPaymentMethodType("card");
                          if (paymentGateway === "upi") {
                            setPaymentGateway("razorpay");
                          }
                        }}
                        className={cn(
                          "checkout-gateway-btn",
                          paymentMethodType === "card" && "active-card"
                        )}
                      >
                        <div className="checkout-gateway-left">
                          <CreditCard className="checkout-gateway-icon text-indigo-600" />
                          <span className="checkout-gateway-title">Credit / Debit Card</span>
                        </div>
                        <span className="checkout-gateway-badge-card">
                          Cards & Global
                        </span>
                      </button>
                    </div>

                    {/* When Card is selected: show these 2 options to go to next step */}
                    {paymentMethodType === "card" && (
                      <div className="checkout-card-options-box">
                        <div className="checkout-card-options-header">
                          <span className="checkout-card-options-title">
                            Select Card Gateway:
                          </span>
                          <span className="text-[11px] text-muted-foreground">
                            Choose provider to proceed
                          </span>
                        </div>

                        <div className="checkout-card-subgrid">
                          <button
                            type="button"
                            onClick={() => setPaymentGateway("razorpay")}
                            className={cn(
                              "checkout-card-subbtn",
                              paymentGateway === "razorpay" && "active"
                            )}
                          >
                            <div className="checkout-card-subbtn-left">
                              <div className={cn(
                                "checkout-radio-circle",
                                paymentGateway === "razorpay" && "is-selected"
                              )}>
                                {paymentGateway === "razorpay" && <div className="checkout-radio-dot" />}
                              </div>
                              <div>
                                <div className="checkout-card-subbtn-name">
                                  Cards / Razorpay
                                </div>
                                <span className="checkout-card-subbtn-hint">
                                  Domestic & Global Cards, NetBanking
                                </span>
                              </div>
                            </div>
                            <span className="checkout-card-subbtn-badge badge-razorpay">
                              Popular
                            </span>
                          </button>

                          <button
                            type="button"
                            onClick={() => setPaymentGateway("stripe")}
                            className={cn(
                              "checkout-card-subbtn",
                              paymentGateway === "stripe" && "active"
                            )}
                          >
                            <div className="checkout-card-subbtn-left">
                              <div className={cn(
                                "checkout-radio-circle",
                                paymentGateway === "stripe" && "is-selected"
                              )}>
                                {paymentGateway === "stripe" && <div className="checkout-radio-dot" />}
                              </div>
                              <div>
                                <div className="checkout-card-subbtn-name">
                                  Stripe Payment
                                </div>
                                <span className="checkout-card-subbtn-hint">
                                  Visa, MasterCard, Amex & Global
                                </span>
                              </div>
                            </div>
                            <span className="checkout-card-subbtn-badge badge-stripe">
                              Global
                            </span>
                          </button>
                        </div>
                      </div>
                    )}

                    <p className="checkout-gateway-notice">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                      <span>
                        {paymentMethodType === "upi"
                          ? "UPI reference reviewed by an administrator before order completion"
                          : `Encrypted payment via ${paymentGateway === "razorpay" ? "Razorpay" : "Stripe"} • Click below to proceed`}
                      </span>
                    </p>
                  </div>
                )}
              </div>

              {/* Right: Summary Box */}
              <div className="checkout-right-block">
                <div className="checkout-card checkout-summary-card">
                  <h3 className="checkout-summary-title">Order Summary</h3>
                  <div className="summary-items-list">
                    <div className="summary-item-row">
                      <span>Subtotal</span>
                      <span className="font-semibold">{TEMPLATE_DOWNLOADS_FREE ? "Free" : hasInrItems ? `₹${total().toFixed(2)}` : formatConvertedPrice(total(), "USD", userCurrency, rates)}</span>
                    </div>
                    <div className="summary-item-row text-muted-foreground/75">
                      <span>Taxes</span>
                      <span>{TEMPLATE_DOWNLOADS_FREE ? "Included" : hasInrItems ? `₹0.00` : formatConvertedPrice(0, "USD", userCurrency, rates)}</span>
                    </div>
                    <div className="summary-total-row">
                      <span>Total Amount</span>
                      <span className="summary-total-amount">{TEMPLATE_DOWNLOADS_FREE ? "Free" : hasInrItems ? `₹${total().toFixed(2)}` : formatConvertedPrice(total(), "USD", userCurrency, rates)}</span>
                    </div>
                  </div>

                  <button
                    onClick={handleCheckout}
                    disabled={items.length === 0 || isProcessing}
                    className="checkout-submit-btn"
                  >
                    {isProcessing ? (
                      <><Loader2 className="checkout-btn-loader animate-spin" /> Starting Session…</>
                    ) : TEMPLATE_DOWNLOADS_FREE ? (
                      <><Download className="checkout-btn-icon" /> Download templates for free</>
                    ) : paymentMethodType === "upi" ? (
                      <><ScanQrCode className="checkout-btn-icon" /> Pay via UPI QR ({hasInrItems ? `₹${total().toFixed(2)}` : inrAmountString})</>
                    ) : paymentGateway === "stripe" ? (
                      <><CreditCard className="checkout-btn-icon" /> Continue with Stripe →</>
                    ) : (
                      <><CreditCard className="checkout-btn-icon" /> Continue with Razorpay →</>
                    )}
                  </button>

                  <div className="checkout-security-badge">
                    <ShieldCheck className="security-shield-icon" />
                    <span>{TEMPLATE_DOWNLOADS_FREE ? "Free downloads · no payment required" : "Secure 256-bit SSL encrypted checkout"}</span>
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
