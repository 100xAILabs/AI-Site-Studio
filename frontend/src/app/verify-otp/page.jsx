import { useState, useRef, useEffect } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  ArrowLeft,
  Mail,
  AlertCircle,
  Edit3,
  RefreshCw,
  Home
} from "lucide-react";
import { motion } from "framer-motion";
import { useAuthStore } from "@/store/authStore";
import { useAppUser } from "@/lib/auth";
import { SiteStudioLogoIcon } from "@/components/layout/SiteStudioLogo";
import "./otp.css";

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { delay, duration: 0.4 } },
});

export default function VerifyOTPPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const queryEmail = new URLSearchParams(location.search).get("email");
  const email = queryEmail || location.state?.email || "";
  const role = location.state?.role || "buyer";

  // Delivery status passed from backend: false means SMTP bounced, missing credentials, or unconfirmed
  const initialSent = location.state?.sent;
  const initialMessage = location.state?.message;

  const { isSignedIn, isLoaded } = useAppUser();

  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(
    initialSent === false
      ? (initialMessage || "Could not deliver email. Please check that your email address is correct.")
      : ""
  );
  const [deliveryFailed, setDeliveryFailed] = useState(initialSent === false);
  const [loading, setLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [resendTimer, setResendTimer] = useState(30);

  const inputRefs = useRef([]);
  const verifyOtp = useAuthStore((s) => s.verifyOtp);
  const resendOtp = useAuthStore((s) => s.resendOtp);

  // If already authenticated, route straight to dashboard
  useEffect(() => {
    if (isLoaded && isSignedIn) {
      navigate("/dashboard", { replace: true });
    }
  }, [isLoaded, isSignedIn, navigate]);

  // If no email query or state was supplied, redirect to sign-in
  useEffect(() => {
    if (!email) {
      navigate("/sign-in", { replace: true });
    } else {
      // Focus first input field on load
      inputRefs.current[0]?.focus();
    }
  }, [email, navigate]);

  // Resend countdown timer
  useEffect(() => {
    let interval;
    if (resendTimer > 0) {
      interval = setInterval(() => {
        setResendTimer((prev) => prev - 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [resendTimer]);

  const handleChange = (index, value) => {
    // Only accept numeric digits
    if (!/^\d*$/.test(value)) return;

    const newOtp = [...otp];
    newOtp[index] = value ? value.slice(-1) : "";
    setOtp(newOtp);
    setError("");

    // Auto-advance to the next input box
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index, e) => {
    if (e.key === "Backspace") {
      if (!otp[index] && index > 0) {
        inputRefs.current[index - 1]?.focus();
      }
    } else if (e.key === "ArrowLeft" && index > 0) {
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === "ArrowRight" && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pastedData) return;

    const newOtp = [...otp];
    for (let i = 0; i < 6; i++) {
      newOtp[i] = pastedData[i] || "";
    }
    setOtp(newOtp);
    setError("");

    // Focus next empty input or the final digit
    const nextIdx = Math.min(pastedData.length, 5);
    inputRefs.current[nextIdx]?.focus();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const code = otp.join("");
    if (code.length !== 6) {
      setError("Please enter the complete 6-digit verification code.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      await verifyOtp({ email, code });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err?.message || "Invalid or expired verification code. Please try again.");
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendTimer > 0 || isResending) return;
    setIsResending(true);
    setError("");
    setNotice("");

    try {
      const res = await resendOtp({ email });
      setResendTimer(45);
      if (res?.sent === false) {
        setDeliveryFailed(true);
        setNotice(res?.message || "Could not deliver email. Please check that your email address is correct.");
      } else {
        setDeliveryFailed(false);
        setNotice("A fresh 6-digit verification code has been dispatched to your email!");
      }
    } catch (err) {
      setError(err?.message || "Failed to resend code. Please try again later.");
    } finally {
      setIsResending(false);
    }
  };

  const handleWrongEmail = () => {
    navigate(role === "seller" ? "/register?role=seller" : "/register?role=buyer");
  };

  return (
    <div className="otp-page-container">
      {/* Background Neon Ambient Glows */}
      <div className="otp-glow-top" />
      <div className="otp-glow-bottom" />
      <div className="otp-glow-purple" />

      {/* Top Header */}
      <header className="otp-nav-header">
        <Link to="/" className="otp-brand-logo">
          <SiteStudioLogoIcon className="w-8 h-8" />
          <span className="otp-brand-text">Site Studio</span>
        </Link>
        <Link to="/" className="otp-home-btn">
          <Home size={15} />
          <span>Back to Home</span>
        </Link>
      </header>

      {/* Verification Card */}
      <motion.div {...fadeUp(0.1)} className="otp-card">
        <button
          onClick={() => navigate(-1)}
          className="otp-back-action"
          title="Go back"
          type="button"
        >
          <ArrowLeft size={18} />
          <span>Back</span>
        </button>

        <div className="otp-icon-container">
          <ShieldCheck size={32} />
        </div>

        <h1 className="otp-title">Security Verification</h1>
        <p className="otp-subtitle">
          Please enter the 6-digit one-time code sent to:
        </p>

        {/* Email Pill with inline Edit / Change Option */}
        <div className="otp-email-box">
          <Mail size={15} className="otp-email-icon" />
          <span className="otp-email-text">{email}</span>
          <button
            type="button"
            onClick={handleWrongEmail}
            className="otp-edit-email-btn"
            title="Spelled wrong? Change email address"
          >
            <Edit3 size={13} />
            <span>Change</span>
          </button>
        </div>

        {/* Delivery Warning (when email delivery failed or unconfirmed) */}
        {deliveryFailed && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            className="otp-delivery-warning"
          >
            <AlertTriangle size={18} className="otp-delivery-warning-icon" />
            <div className="otp-delivery-warning-content">
              <strong>Check your email address</strong>
              <p>
                We could not deliver the email to this address. Please ensure that{" "}
                <strong className="text-white">{email}</strong> is spelled correctly and is an active inbox.
              </p>
              <div className="otp-warning-actions">
                <button
                  type="button"
                  onClick={handleWrongEmail}
                  className="otp-warning-change-btn"
                >
                  <Edit3 size={13} /> Edit Email Address
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Notice Message (Resend / Info) */}
        {notice && !deliveryFailed && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="otp-notice-alert"
          >
            <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
            <span>{notice}</span>
          </motion.div>
        )}

        {/* Error Alert */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="otp-error-alert"
          >
            <AlertCircle size={16} className="shrink-0" />
            <span>{error}</span>
          </motion.div>
        )}

        {/* 6-Digit Code Form */}
        <form onSubmit={handleSubmit} className="otp-form">
          <div className="otp-input-group" onPaste={handlePaste}>
            {otp.map((digit, index) => (
              <input
                key={index}
                ref={(el) => (inputRefs.current[index] = el)}
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={1}
                value={digit}
                onChange={(e) => handleChange(index, e.target.value)}
                onKeyDown={(e) => handleKeyDown(index, e)}
                className={`otp-input-box ${digit ? "filled" : ""} ${error ? "error" : ""}`}
                autoComplete="one-time-code"
                aria-label={`Digit ${index + 1}`}
              />
            ))}
          </div>

          <button
            type="submit"
            disabled={loading || otp.join("").length !== 6}
            className="otp-submit-btn"
          >
            {loading ? (
              <div className="otp-spinner" />
            ) : (
              <span>Verify & Continue</span>
            )}
          </button>
        </form>

        {/* Resend Section */}
        <div className="otp-resend-wrapper">
          <span className="otp-resend-text">Didn't receive the code?</span>
          <button
            type="button"
            className="otp-resend-btn"
            onClick={handleResend}
            disabled={resendTimer > 0 || isResending}
          >
            {isResending ? (
              <span className="otp-resending-inline">
                <RefreshCw size={12} className="otp-spin-icon" /> Sending...
              </span>
            ) : resendTimer > 0 ? (
              `Resend code in ${resendTimer}s`
            ) : (
              "Resend Code"
            )}
          </button>
        </div>

        {/* Helpful Tips Card */}
        <div className="otp-tips-container">
          <div className="otp-tip-item">
            <span className="otp-tip-dot" />
            <span>Check your spam, junk, or promotions folder.</span>
          </div>
          <div className="otp-tip-item">
            <span className="otp-tip-dot" />
            <span>Codes expire after 5 minutes for security.</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
