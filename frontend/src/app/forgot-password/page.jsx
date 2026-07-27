import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Link as RouterLink } from "react-router-dom";
import {
  KeyRound, ArrowLeft, AlertCircle, Eye, EyeOff, CheckCircle2, ShieldCheck, Mail,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import "./Page.css";

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0, transition: { delay, duration: 0.45 } },
});

export default function ForgotPasswordPage() {
  const navigate = useNavigate();

  const forgotPassword = useAuthStore((s) => s.forgotPassword);
  const resetPassword = useAuthStore((s) => s.resetPassword);

  // Steps: "email" → "otp" → "success"
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendTimer, setResendTimer] = useState(0);

  const inputRefs = useRef([]);

  useEffect(() => {
    let interval;
    if (resendTimer > 0) {
      interval = setInterval(() => {
        setResendTimer((prev) => prev - 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [resendTimer]);

  // Step 1: Send reset code
  const handleSendCode = async (e) => {
    e.preventDefault();
    if (!email) return;
    setError("");
    setLoading(true);
    try {
      await forgotPassword({ email });
      setStep("otp");
      setResendTimer(30);
    } catch (err) {
      setError(err?.message || "Failed to send reset code.");
    } finally {
      setLoading(false);
    }
  };

  // OTP input handlers
  const handleOtpChange = (index, value) => {
    if (!/^\d*$/.test(value)) return;
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (index, e) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handleOtpPaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData("text").slice(0, 6).split("");
    if (pastedData.some((char) => !/^\d$/.test(char))) return;
    const newOtp = [...otp];
    pastedData.forEach((char, i) => {
      newOtp[i] = char;
    });
    setOtp(newOtp);
    const nextIndex = Math.min(pastedData.length, 5);
    inputRefs.current[nextIndex]?.focus();
  };

  // Step 2: Verify OTP + Reset password
  const handleResetPassword = async (e) => {
    e.preventDefault();
    const code = otp.join("");
    if (code.length !== 6) {
      setError("Please enter all 6 digits.");
      return;
    }
    if (!newPassword) {
      setError("Please enter a new password.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await resetPassword({ email, otp: code, newPassword });
      setStep("success");
    } catch (err) {
      setError(err?.message || "Failed to reset password.");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendTimer > 0) return;
    try {
      await forgotPassword({ email });
      setResendTimer(30);
      setError("");
    } catch (err) {
      setError("Failed to resend code.");
    }
  };

  return (
    <div className="forgot-page-container">
      <div className="forgot-glow-top" />
      <div className="forgot-glow-bottom" />

      <motion.div {...fadeUp(0)} className="forgot-card">
        {/* Back button */}
        <Link to="/sign-in" className="forgot-back-btn">
          <ArrowLeft size={20} />
        </Link>

        {/* ─── Step 1: Enter Email ─── */}
        {step === "email" && (
          <>
            <div className="forgot-icon-container">
              <Mail size={32} />
            </div>

            <h1 className="forgot-title">Forgot Password?</h1>
            <p className="forgot-subtitle">
              Enter your email address and we'll send you a verification code to reset your password.
            </p>

            {error && (
              <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="forgot-error-alert">
                <AlertCircle size={16} />
                {error}
              </motion.div>
            )}

            <form onSubmit={handleSendCode} className="forgot-form">
              <div>
                <label className="forgot-input-label" htmlFor="reset-email">Email Address</label>
                <input
                  id="reset-email"
                  type="email"
                  required
                  className="forgot-input-field"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <button type="submit" disabled={loading} className="forgot-submit-btn">
                {loading ? (
                  <div className="forgot-spinner" />
                ) : (
                  "Send Reset Code"
                )}
              </button>
            </form>

            <p className="forgot-footer-text">
              Remember your password?{" "}
              <Link to="/sign-in" className="forgot-footer-link">Sign in</Link>
            </p>
          </>
        )}

        {/* ─── Step 2: Enter OTP + New Password ─── */}
        {step === "otp" && (
          <>
            <div className="forgot-icon-container">
              <ShieldCheck size={32} />
            </div>

            <h1 className="forgot-title">Reset Password</h1>
            <p className="forgot-subtitle">
              Enter the 6-digit code sent to <br />
              <span className="forgot-email-highlight">{email}</span>
            </p>

            {error && (
              <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="forgot-error-alert">
                <AlertCircle size={16} />
                {error}
              </motion.div>
            )}

            <form onSubmit={handleResetPassword} className="forgot-form">
              {/* OTP Inputs */}
              <div className="forgot-otp-group" onPaste={handleOtpPaste}>
                {otp.map((digit, index) => (
                  <input
                    key={index}
                    ref={(el) => (inputRefs.current[index] = el)}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleOtpChange(index, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(index, e)}
                    className={`forgot-otp-box ${error ? "error" : ""}`}
                    autoComplete="one-time-code"
                  />
                ))}
              </div>

              {/* New Password */}
              <div>
                <label className="forgot-input-label" htmlFor="new-password">New Password</label>
                <div className="forgot-password-wrapper">
                  <input
                    id="new-password"
                    type={showPassword ? "text" : "password"}
                    required
                    className="forgot-input-field"
                    placeholder="••••••••"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="forgot-password-toggle"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Confirm Password */}
              <div>
                <label className="forgot-input-label" htmlFor="confirm-password">Confirm Password</label>
                <input
                  id="confirm-password"
                  type={showPassword ? "text" : "password"}
                  required
                  className="forgot-input-field"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>

              {/* Password strength hint */}
              <p className="forgot-password-hint">
                Must be 8+ characters with uppercase, lowercase, number, and special character.
              </p>

              <button type="submit" disabled={loading} className="forgot-submit-btn">
                {loading ? (
                  <div className="forgot-spinner" />
                ) : (
                  "Reset Password"
                )}
              </button>
            </form>

            <div className="forgot-resend-wrapper">
              Didn't receive the code?{" "}
              <button
                type="button"
                className="forgot-resend-btn"
                onClick={handleResend}
                disabled={resendTimer > 0}
              >
                {resendTimer > 0 ? `Resend in ${resendTimer}s` : "Resend"}
              </button>
            </div>
          </>
        )}

        {/* ─── Step 3: Success ─── */}
        {step === "success" && (
          <>
            <div className="forgot-icon-container success">
              <CheckCircle2 size={32} />
            </div>

            <h1 className="forgot-title">Password Reset!</h1>
            <p className="forgot-subtitle">
              Your password has been successfully reset. You can now sign in with your new password.
            </p>

            <Link to="/sign-in" className="forgot-submit-btn" style={{ textDecoration: "none", textAlign: "center" }}>
              Back to Sign In
            </Link>
          </>
        )}
      </motion.div>
    </div>
  );
}
