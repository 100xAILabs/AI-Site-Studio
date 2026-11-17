"use client";

import { useState, useEffect } from "react";
import {
  ShieldCheck,
  Lock,
  CreditCard,
  QrCode,
  Building2,
  CheckCircle2,
  Loader2,
  X,
  Sparkles,
  Smartphone,
  Check,
} from "lucide-react";
import "./InteractivePaymentModal.css";

const POPULAR_BANKS = [
  { id: "hdfc", name: "HDFC Bank" },
  { id: "icici", name: "ICICI Bank" },
  { id: "sbi", name: "State Bank of India" },
  { id: "axis", name: "Axis Bank" },
  { id: "kotak", name: "Kotak Mahindra" },
  { id: "other", name: "Other Banks" },
];

export default function InteractivePaymentModal({
  isOpen,
  onClose,
  gateway = "razorpay", // "razorpay" | "stripe"
  orderNumber = "ORD-12345",
  title = "Site Studio Subscription",
  amountFormatted = "$19.00 USD",
  amountSubtext = "",
  userEmail = "",
  userName = "",
  onConfirmPayment,
}) {
  const [activeTab, setActiveTab] = useState("card"); // "card" | "upi" | "netbanking"
  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvc, setCardCvc] = useState("");
  const [cardName, setCardName] = useState(userName || "");
  const [upiId, setUpiId] = useState("");
  const [selectedBank, setSelectedBank] = useState("hdfc");
  const [isAuthorizing, setIsAuthorizing] = useState(false);
  const [authStep, setAuthStep] = useState(1);
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    if (userName && !cardName) {
      setCardName(userName);
    }
  }, [userName, cardName]);

  if (!isOpen) return null;

  // Format Card Number (XXXX XXXX XXXX XXXX)
  const handleCardNumberChange = (e) => {
    setValidationError("");
    let raw = e.target.value.replace(/\D/g, "").slice(0, 16);
    let formatted = raw.match(/.{1,4}/g)?.join(" ") || raw;
    setCardNumber(formatted);
  };

  // Format Expiry (MM/YY)
  const handleExpiryChange = (e) => {
    setValidationError("");
    let raw = e.target.value.replace(/\D/g, "").slice(0, 4);
    if (raw.length >= 3) {
      setCardExpiry(`${raw.slice(0, 2)}/${raw.slice(2)}`);
    } else {
      setCardExpiry(raw);
    }
  };

  const handleCvcChange = (e) => {
    setValidationError("");
    setCardCvc(e.target.value.replace(/\D/g, "").slice(0, 4));
  };

  // Quick fill test credentials
  const handleAutoFillTestCard = () => {
    setCardNumber("4242 4242 4242 4242");
    setCardExpiry("12/28");
    setCardCvc("123");
    setCardName(userName || "Alex Johnson");
    setValidationError("");
  };

  const handleAutoFillUPI = () => {
    setUpiId(userEmail ? `${userEmail.split("@")[0]}@okhdfcbank` : "alex@okhdfcbank");
    setValidationError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError("");

    if (activeTab === "card") {
      const cleanNum = cardNumber.replace(/\s/g, "");
      if (cleanNum.length < 15) {
        setValidationError("Please enter a valid 16-digit card number.");
        return;
      }
      if (cardExpiry.length < 5) {
        setValidationError("Please enter card expiration date (MM/YY).");
        return;
      }
      if (cardCvc.length < 3) {
        setValidationError("Please enter card CVC/CVV.");
        return;
      }
    } else if (activeTab === "upi") {
      if (!upiId || !upiId.includes("@")) {
        setValidationError("Please enter a valid UPI VPA address (e.g. yourname@okhdfcbank).");
        return;
      }
    }

    setIsAuthorizing(true);
    setAuthStep(1);

    try {
      // Step 1: Connecting to Gateway
      await new Promise((r) => setTimeout(r, 600));
      setAuthStep(2);

      // Step 2: 3D Secure / OTP Simulation
      await new Promise((r) => setTimeout(r, 800));
      setAuthStep(3);

      // Step 3: Authorization & Tokenization
      await new Promise((r) => setTimeout(r, 600));

      // Call parent handler to complete the verified order
      await onConfirmPayment({
        method: activeTab,
        cardNumber: cardNumber.slice(-4),
        upiId: activeTab === "upi" ? upiId : null,
        bank: activeTab === "netbanking" ? selectedBank : null,
      });
    } catch (err) {
      console.error("Payment authorization error:", err);
      setValidationError(err?.message || "Payment authorization declined by issuing bank.");
      setIsAuthorizing(false);
    }
  };

  const isRazorpay = gateway === "razorpay";

  return (
    <div className="ipm-overlay">
      <div className="ipm-modal" role="dialog" aria-modal="true">
        {/* Header */}
        <div className="ipm-header">
          <div className="ipm-brand-wrap">
            <div className={`ipm-brand-icon ${isRazorpay ? "razorpay" : "stripe"}`}>
              {isRazorpay ? <CreditCard className="w-5 h-5" /> : <Lock className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="ipm-brand-title">
                {isRazorpay ? "Razorpay Trusted Checkout" : "Stripe Secure Payment"}
              </h3>
              <span className="ipm-brand-sub">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                256-Bit Bank Grade Encryption
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isAuthorizing}
            className="ipm-close-btn"
            title="Cancel"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Order Strip */}
        <div className="ipm-order-strip">
          <div className="ipm-order-info">
            <span className="ipm-order-title">{title}</span>
            <span className="ipm-order-meta">
              Order #{orderNumber?.slice(0, 12)} • {userEmail || "Account Checkout"}
            </span>
          </div>
          <div className="ipm-order-price">
            <div className="ipm-order-amount">{amountFormatted}</div>
            {amountSubtext && <div className="ipm-order-currency">{amountSubtext}</div>}
          </div>
        </div>

        {/* Body */}
        <div className="ipm-body">
          {/* Method Tabs */}
          <div className="ipm-tabs">
            <button
              type="button"
              onClick={() => {
                setActiveTab("card");
                setValidationError("");
              }}
              className={`ipm-tab-btn ${activeTab === "card" ? "active" : ""}`}
            >
              <CreditCard className="w-3.5 h-3.5" />
              <span>Card</span>
            </button>

            {isRazorpay && (
              <button
                type="button"
                onClick={() => {
                  setActiveTab("upi");
                  setValidationError("");
                }}
                className={`ipm-tab-btn ${activeTab === "upi" ? "active" : ""}`}
              >
                <Smartphone className="w-3.5 h-3.5" />
                <span>UPI / QR</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => {
                setActiveTab("netbanking");
                setValidationError("");
              }}
              className={`ipm-tab-btn ${activeTab === "netbanking" ? "active" : ""}`}
            >
              <Building2 className="w-3.5 h-3.5" />
              <span>NetBanking</span>
            </button>
          </div>

          {/* Form Content */}
          <form id="ipm-payment-form" onSubmit={handleSubmit} className="ipm-form">
            {activeTab === "card" && (
              <>
                <div className="ipm-field">
                  <div className="ipm-label">
                    <span>Card Number</span>
                    <button
                      type="button"
                      onClick={handleAutoFillTestCard}
                      className="ipm-test-fill-pill"
                    >
                      ⚡ Auto-fill Test Card
                    </button>
                  </div>
                  <div className="ipm-input-wrap">
                    <input
                      type="text"
                      inputMode="numeric"
                      placeholder="4242 4242 4242 4242"
                      value={cardNumber}
                      onChange={handleCardNumberChange}
                      disabled={isAuthorizing}
                      className="ipm-input with-icon"
                      required
                    />
                    <CreditCard className="ipm-input-icon w-4 h-4" />
                  </div>
                </div>

                <div className="ipm-row-2">
                  <div className="ipm-field">
                    <label className="ipm-label">Expires</label>
                    <input
                      type="text"
                      placeholder="MM/YY"
                      value={cardExpiry}
                      onChange={handleExpiryChange}
                      disabled={isAuthorizing}
                      className="ipm-input"
                      required
                    />
                  </div>

                  <div className="ipm-field">
                    <label className="ipm-label">CVC / CVV</label>
                    <input
                      type="password"
                      placeholder="123"
                      maxLength={4}
                      value={cardCvc}
                      onChange={handleCvcChange}
                      disabled={isAuthorizing}
                      className="ipm-input"
                      required
                    />
                  </div>
                </div>

                <div className="ipm-field">
                  <label className="ipm-label">Cardholder Name</label>
                  <input
                    type="text"
                    placeholder="Full name as printed on card"
                    value={cardName}
                    onChange={(e) => setCardName(e.target.value)}
                    disabled={isAuthorizing}
                    className="ipm-input"
                    required
                  />
                </div>
              </>
            )}

            {activeTab === "upi" && (
              <div className="ipm-upi-wrap">
                <div className="ipm-field" style={{ width: "100%" }}>
                  <div className="ipm-label">
                    <span>UPI ID / VPA</span>
                    <button
                      type="button"
                      onClick={handleAutoFillUPI}
                      className="ipm-test-fill-pill"
                    >
                      ⚡ Fill Test UPI
                    </button>
                  </div>
                  <div className="ipm-input-wrap">
                    <input
                      type="text"
                      placeholder="username@okhdfcbank"
                      value={upiId}
                      onChange={(e) => {
                        setValidationError("");
                        setUpiId(e.target.value);
                      }}
                      disabled={isAuthorizing}
                      className="ipm-input with-icon"
                    />
                    <Smartphone className="ipm-input-icon w-4 h-4 text-emerald-400" />
                  </div>
                </div>

                <div className="text-xs text-muted-foreground">― OR SCAN INSTANT QR ―</div>

                <div className="ipm-qr-box">
                  <QrCode className="w-24 h-24 text-slate-900" />
                </div>

                <div className="ipm-upi-apps">
                  <span className="ipm-upi-app-badge">Google Pay</span>
                  <span className="ipm-upi-app-badge">PhonePe</span>
                  <span className="ipm-upi-app-badge">Paytm</span>
                  <span className="ipm-upi-app-badge">BHIM</span>
                </div>
              </div>
            )}

            {activeTab === "netbanking" && (
              <div className="ipm-field">
                <label className="ipm-label">Select Your Bank</label>
                <div className="ipm-banks-grid">
                  {POPULAR_BANKS.map((b) => (
                    <button
                      key={b.id}
                      type="button"
                      onClick={() => setSelectedBank(b.id)}
                      className={`ipm-bank-btn ${selectedBank === b.id ? "active" : ""}`}
                    >
                      <Building2 className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                      <span className="truncate">{b.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Validation Error Banner */}
            {validationError && (
              <div style={{ color: "#f87171", fontSize: "0.775rem", fontWeight: 600 }}>
                ⚠️ {validationError}
              </div>
            )}

            {/* Security notice */}
            <div className="ipm-security-notice">
              <Lock className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span>
                Simulated Sandbox Checkout • Authenticates 3D Secure without real charges.
              </span>
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="ipm-footer">
          <button
            type="submit"
            form="ipm-payment-form"
            disabled={isAuthorizing}
            className={`ipm-submit-btn ${isRazorpay ? "razorpay-btn" : ""}`}
          >
            {isAuthorizing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>
                  {authStep === 1 && "Connecting to bank gateway..."}
                  {authStep === 2 && "Verifying 3D Secure / OTP..."}
                  {authStep === 3 && "Finalizing & capturing payment..."}
                </span>
              </>
            ) : (
              <>
                <Lock className="w-4 h-4" />
                <span>Authorize &amp; Pay {amountFormatted}</span>
              </>
            )}
          </button>

          <div className="ipm-badges-row">
            <span className="ipm-badge-item">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" /> PCI-DSS Compliant
            </span>
            <span className="ipm-badge-item">
              <ShieldCheck className="w-3 h-3 text-sky-400" /> Verified Merchant
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
