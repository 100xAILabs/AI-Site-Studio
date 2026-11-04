"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link, useNavigate, useLocation } from "react-router-dom";
import {
  Home,
  Mail,
  Lock,
  Eye,
  EyeOff,
  User,
  Store,
  ShoppingCart,
  Sparkles,
  Zap,
  ShieldCheck,
  Headphones,
  ArrowRight,
  AlertCircle,
  Code2,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useAppUser } from "@/lib/auth";
import { SiteStudioLogoIcon } from "@/components/layout/SiteStudioLogo";
import "./Page.css";

export default function SignInPage({ isRegister = false }) {
  const navigate = useNavigate();
  const location = useLocation();
  const from = new URLSearchParams(location.search).get("from") || "/dashboard";
  const initialRole = new URLSearchParams(location.search).get("role") || "buyer";
  const urlError = new URLSearchParams(location.search).get("error") || "";

  const { isSignedIn, isLoaded } = useAppUser();

  const [role, setRole] = useState(initialRole.toLowerCase() === "seller" ? "seller" : "buyer");
  const [agreed, setAgreed] = useState(true);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState(urlError);
  const [oauthLoading, setOauthLoading] = useState(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [isLocked, setIsLocked] = useState(false);
  const [lockTimer, setLockTimer] = useState(0);
  const MAX_ATTEMPTS = 5;
  const [duplicateAccountInfo, setDuplicateAccountInfo] = useState(null);

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      navigate(from, { replace: true });
    }
  }, [isLoaded, isSignedIn, navigate, from]);

  // Sync role when initialRole query parameter changes
  useEffect(() => {
    if (initialRole) {
      setRole(initialRole.toLowerCase() === "seller" ? "seller" : "buyer");
    }
  }, [initialRole]);

  // Handle lock countdown timer
  useEffect(() => {
    if (lockTimer > 0) {
      const interval = setInterval(() => {
        setLockTimer((prev) => {
          if (prev <= 1) {
            setIsLocked(false);
            setFailedAttempts(0);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [lockTimer]);

  const beginGoogleAuth = useAuthStore((s) => s.beginGoogleAuth);
  const signInWithEmail = useAuthStore((s) => s.signInWithEmail);
  const registerWithEmail = useAuthStore((s) => s.registerWithEmail);

  const handleOAuth = async () => {
    setOauthLoading("google");
    beginGoogleAuth(role);
  };

  const handleEmailAuth = async (e) => {
    e.preventDefault();
    if (!email || !password) return;
    if (isLocked) {
      setError(`Account temporarily locked. Please wait ${lockTimer}s before trying again.`);
      return;
    }
    setError("");
    setAuthLoading(true);

    try {
      if (isRegister) {
        if (!agreed) {
          setError("You must agree to the Terms of Service and Privacy Policy to register.");
          setAuthLoading(false);
          return;
        }
        setDuplicateAccountInfo(null);
        const result = await registerWithEmail({ email, password, role });
        if (result?.requires_otp) {
          navigate(`/verify-otp?email=${encodeURIComponent(result.email || email)}`, {
            state: {
              email: result.email || email,
              role,
              sent: result.sent,
              message: result.message
            }
          });
          return;
        }
      } else {
        const result = await signInWithEmail({ email, password, role });
        if (result?.requires_otp) {
          navigate(`/verify-otp?email=${encodeURIComponent(result.email || email)}`, {
            state: {
              email: result.email || email,
              role,
              sent: result.sent,
              message: result.message
            }
          });
          return;
        }
        setFailedAttempts(0);
      }
    } catch (err) {
      console.error(err);

      if (err.status === 409) {
        setDuplicateAccountInfo({ signupMethod: err.signupMethod || "unknown", email });
        setError(err.message || "An account with this email already exists.");
        setAuthLoading(false);
        return;
      }

      const newAttempts = failedAttempts + 1;
      setFailedAttempts(newAttempts);

      if (err?.message?.includes("locked") || err?.message?.includes("429")) {
        setIsLocked(true);
        setLockTimer(60);
        setError("Account temporarily locked due to too many failed attempts. Please wait 60 seconds.");
      } else if (newAttempts >= MAX_ATTEMPTS) {
        setIsLocked(true);
        setLockTimer(60);
        setError("Too many failed attempts. Account temporarily locked for 60 seconds.");
      } else {
        const remaining = MAX_ATTEMPTS - newAttempts;
        const baseMsg = err?.response?.data?.detail || err?.message || "Authentication failed.";
        setError(
          `${baseMsg} ${!baseMsg.includes("registered as") && remaining > 0 ? `${remaining} attempt${remaining === 1 ? "" : "s"} remaining before lockout.` : ""}`
        );
      }
    } finally {
      setAuthLoading(false);
    }
  };

  if (!isLoaded) {
    return (
      <div className="auth-loading-state">
        <div className="loader-spinner-container">
          <div className="loader-spinner-bg" />
          <div className="loader-spinner-bar" />
        </div>
      </div>
    );
  }

  const roleLabel = role === "seller" ? "Seller" : "Buyer";

  return (
    <div className="auth-studio-page">
      {/* Dynamic ambient background glows */}
      <div className="auth-ambient-glow top-left" />
      <div className="auth-ambient-glow bottom-right" />
      <div className="auth-ambient-glow center-purple" />

      {/* Top Header Navigation */}
      <header className="auth-studio-header">
        <Link to="/" className="auth-header-brand" title="Site Studio Home">
          <SiteStudioLogoIcon className="w-8 h-8" />
          <span className="auth-header-title">Site Studio</span>
        </Link>

        <Link to="/" className="auth-back-home-link" title="Return to home page">
          <Home className="w-4 h-4 mr-1.5" />
          <span>Back to Home</span>
        </Link>
      </header>

      {/* Main Two-Column Showcase & Login Container */}
      <main className="auth-main-layout">
        {/* Left Column: Visual Showcase & 3D Interactive Device */}
        <section className="auth-showcase-column">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="auth-showcase-content"
          >
            {/* Eyebrow Pill */}
            <div className="auth-eyebrow-pill">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              <span>Build • Create • Grow</span>
            </div>

            {/* Main Headline */}
            <h1 className="auth-showcase-heading">
              <span className="heading-line-white">
                {isRegister ? "Join & Grow on" : "Welcome Back to"}
              </span>
              <span className="heading-line-purple">Site Studio</span>
            </h1>

            {/* Subtitle */}
            <p className="auth-showcase-desc">
              Your all-in-one platform to create stunning websites, explore premium
              templates and bring your ideas to life.
            </p>

            {/* 3D Realistic Device Mockup with Floating Elements */}
            <div className="auth-device-showcase-stage">
              {/* Floating Badge Top-Right: AI Powered Builder */}
              <div className="floating-ai-badge">
                <div className="ai-badge-icon-wrap">
                  <Sparkles className="w-3.5 h-3.5 text-purple-300" />
                </div>
                <div className="ai-badge-text-wrap">
                  <span className="ai-badge-title">AI Powered</span>
                  <span className="ai-badge-sub">Website Builder</span>
                </div>
              </div>

              {/* Floating Code Badge on Left */}
              <div className="floating-code-badge">
                <Code2 className="w-5 h-5 text-purple-300" />
              </div>

              {/* Realistic Sleek Laptop Body */}
              <div className="showcase-laptop-wrapper">
                <div className="laptop-screen-bezel">
                  {/* Laptop Camera dot */}
                  <div className="laptop-camera-dot" />

                  {/* Screen Content: Dark Studio Website Preview */}
                  <div className="laptop-screen-content">
                    {/* Mini Website Header */}
                    <div className="mini-web-header">
                      <div className="mini-web-brand">
                        <SiteStudioLogoIcon className="w-3.5 h-3.5" />
                      </div>
                      <div className="mini-web-nav">
                        <span>Home</span>
                        <span>Templates</span>
                        <span>Resources</span>
                      </div>
                      <div className="mini-web-cta">
                        <span>Get Started</span>
                      </div>
                    </div>

                    {/* Mini Website Hero Banner */}
                    <div className="mini-web-hero">
                      <div className="mini-hero-left">
                        <div className="mini-hero-headline">
                          <div>Dream.</div>
                          <div>Build. Grow.</div>
                        </div>
                        <p className="mini-hero-sub">
                          Create amazing websites with Site Studio.
                        </p>
                        <div className="mini-hero-btn">
                          <span>Get Started</span>
                          <ArrowRight className="w-2.5 h-2.5 ml-1" />
                        </div>
                      </div>

                      <div className="mini-hero-right">
                        <img
                          src="/landing/lock.jpg"
                          alt="Modern Villa Website Preview"
                          className="mini-hero-preview-img"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Laptop Keyboard Base & Hinge */}
                <div className="laptop-keyboard-base">
                  <div className="laptop-notch" />
                </div>
                <div className="laptop-reflection-glow" />
              </div>

              {/* Floating Glassmorphism Templates Card on Right */}
              <div className="floating-templates-card">
                <div className="floating-templates-grid">
                  <img src="/landing/lock.jpg" alt="Preview 1" className="floating-mini-thumb" />
                  <img src="/landing/modern_villa.jpg" alt="Preview 2" className="floating-mini-thumb" onError={(e) => { e.currentTarget.src = "/landing/lock.jpg"; }} />
                  <img src="/landing/template_ecommerce.png" alt="Preview 3" className="floating-mini-thumb" onError={(e) => { e.currentTarget.src = "/landing/lock.jpg"; }} />
                  <img src="/landing/template_saas.png" alt="Preview 4" className="floating-mini-thumb" onError={(e) => { e.currentTarget.src = "/landing/lock.jpg"; }} />
                </div>
              </div>
            </div>

            {/* Bottom 3 Feature Metrics */}
            <div className="auth-metrics-bar">
              <div className="auth-metric-item">
                <Zap className="w-4 h-4 text-purple-400" />
                <span className="metric-text">100+ Templates</span>
              </div>
              <div className="auth-metric-item">
                <ShieldCheck className="w-4 h-4 text-purple-400" />
                <span className="metric-text">Secure &amp; Reliable</span>
              </div>
              <div className="auth-metric-item">
                <Headphones className="w-4 h-4 text-purple-400" />
                <span className="metric-text">24/7 Support</span>
              </div>
            </div>


          </motion.div>
        </section>

        {/* Right Column: Sign In Glassmorphism Form Card */}
        <section className="auth-card-column">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.52 }}
            className="auth-glass-card"
          >
            {/* Card Header with Logo */}
            <div className="auth-glass-header">
              <div className="auth-glass-logo-wrap">
                <SiteStudioLogoIcon className="w-11 h-11" />
              </div>
              <h2 className="auth-glass-title">Site Studio</h2>
              <p className="auth-glass-subtitle">
                Choose how you want to access your account
              </p>
            </div>

            {/* Segmented Role Toggle Buttons */}
            <div className="auth-role-segmented-track">
              <button
                type="button"
                onClick={() => {
                  setRole("buyer");
                  setError("");
                }}
                className={`auth-role-segmented-btn ${role === "buyer" ? "active" : ""}`}
              >
                <User className="w-4 h-4" />
                <span>Buyer</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setRole("seller");
                  setError("");
                }}
                className={`auth-role-segmented-btn ${role === "seller" ? "active" : ""}`}
              >
                <Store className="w-4 h-4" />
                <span>Seller</span>
              </button>
            </div>

            {/* Dual Role Account Type Feature Cards */}
            <div className="auth-role-cards-grid">
              <div
                onClick={() => {
                  setRole("buyer");
                  setError("");
                }}
                className={`auth-role-card ${role === "buyer" ? "selected" : ""}`}
                role="button"
                tabIndex={0}
              >
                <div className="auth-role-card-icon-box">
                  <ShoppingCart className="w-5 h-5 text-purple-400" />
                </div>
                <div className="auth-role-card-text">
                  <h4 className="role-card-title">Buyer Account</h4>
                  <p className="role-card-desc">
                    Discover, purchase and manage website templates.
                  </p>
                </div>
              </div>

              <div
                onClick={() => {
                  setRole("seller");
                  setError("");
                }}
                className={`auth-role-card ${role === "seller" ? "selected" : ""}`}
                role="button"
                tabIndex={0}
              >
                <div className="auth-role-card-icon-box">
                  <Store className="w-5 h-5 text-purple-400" />
                </div>
                <div className="auth-role-card-text">
                  <h4 className="role-card-title">Seller Account</h4>
                  <p className="role-card-desc">
                    Upload, publish and sell your templates.
                  </p>
                </div>
              </div>
            </div>

            {/* Email & Password Authentication Form */}
            <form onSubmit={handleEmailAuth} className="auth-credentials-form">
              {/* Email Input - Any Email Address Supported */}
              <div className="auth-field-group">
                <div className="auth-input-container">
                  <Mail className="auth-field-icon" />
                  <input
                    id="auth-email-input"
                    type="email"
                    required
                    className="auth-text-input"
                    placeholder="Enter your email address"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>

              {/* Password Input */}
              <div className="auth-field-group">
                <div className="auth-input-container">
                  <Lock className="auth-field-icon" />
                  <input
                    id="auth-password-input"
                    type={showPassword ? "text" : "password"}
                    required
                    className="auth-text-input"
                    placeholder="Enter your password"
                    disabled={isLocked}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="auth-eye-toggle-btn"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Options Row: Remember Me & Forgot Password */}
              <div className="auth-options-row">
                <label className="auth-remember-checkbox-label">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="auth-custom-checkbox"
                  />
                  <span>Remember me</span>
                </label>

                {!isRegister && (
                  <Link to="/forgot-password" className="auth-forgot-password-link">
                    Forgot password?
                  </Link>
                )}
              </div>

              {/* Registration Terms Agreement */}
              {isRegister && (
                <div className="auth-terms-row">
                  <input
                    id="terms-agreed-checkbox"
                    type="checkbox"
                    checked={agreed}
                    onChange={(e) => setAgreed(e.target.checked)}
                    className="auth-custom-checkbox"
                  />
                  <label htmlFor="terms-agreed-checkbox" className="auth-terms-text">
                    I agree to the Terms of Service and Privacy Policy
                  </label>
                </div>
              )}

              {/* Failed Attempt Counter */}
              {!isRegister && failedAttempts > 0 && !isLocked && (
                <div className="auth-failed-attempts-box">
                  <div className="failed-attempts-header">
                    <span>Failed attempts</span>
                    <span className={failedAttempts >= 4 ? "text-rose-400" : "text-amber-400"}>
                      {failedAttempts}/{MAX_ATTEMPTS}
                    </span>
                  </div>
                  <div className="failed-attempts-track">
                    <div
                      className="failed-attempts-fill"
                      style={{ width: `${(failedAttempts / MAX_ATTEMPTS) * 100}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Primary Submit Button */}
              <button
                type="submit"
                disabled={authLoading || isLocked}
                className="auth-primary-submit-btn"
              >
                {isLocked ? (
                  <>
                    <Lock className="w-4 h-4 mr-2" />
                    <span>Locked ({lockTimer}s)</span>
                  </>
                ) : authLoading ? (
                  <span className="auth-spinner-sm" />
                ) : (
                  <>
                    <span>
                      {isRegister ? `Create ${roleLabel} Account` : `Sign In as ${roleLabel}`}
                    </span>
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </>
                )}
              </button>
            </form>

            {/* Lockout Warning Alert */}
            {isLocked && (
              <div className="auth-lockout-banner">
                <Lock className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <div>
                  <p className="lockout-title">Account Temporarily Locked</p>
                  <p className="lockout-text">
                    Too many failed attempts. Try again in <strong>{lockTimer}s</strong>.
                  </p>
                </div>
              </div>
            )}

            {/* Role Mismatch / Error Alert with Actionable Switch Button */}
            {error && !isLocked && (
              <div className="auth-inline-error">
                <div style={{ display: "flex", gap: "0.6rem", alignItems: "flex-start", width: "100%" }}>
                  <AlertCircle className="w-4 h-4 flex-shrink-0" style={{ marginTop: "2px" }} />
                  <div style={{ flex: 1 }}>
                    <span style={{ display: "block", lineHeight: 1.45 }}>{error}</span>
                    {error.toLowerCase().includes("switch to") && (
                      <button
                        type="button"
                        onClick={() => {
                          const target = error.toLowerCase().includes("seller") ? "seller" : "buyer";
                          setRole(target);
                          setError("");
                        }}
                        style={{
                          marginTop: "8px",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "5px 12px",
                          borderRadius: "6px",
                          fontSize: "0.76rem",
                          fontWeight: 700,
                          color: "#ffffff",
                          background: "#7c3aed",
                          border: "1px solid rgba(255, 255, 255, 0.2)",
                          cursor: "pointer",
                        }}
                      >
                        <span>Switch to {error.toLowerCase().includes("seller") ? "Seller" : "Buyer"} Login</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    )}
                    {error.toLowerCase().includes("google") && (
                      <button
                        type="button"
                        onClick={handleOAuth}
                        style={{
                          marginTop: "8px",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "8px",
                          padding: "6px 14px",
                          borderRadius: "6px",
                          fontSize: "0.78rem",
                          fontWeight: 700,
                          color: "#111827",
                          background: "#ffffff",
                          border: "none",
                          cursor: "pointer",
                          boxShadow: "0 2px 8px rgba(0,0,0,0.3)"
                        }}
                      >
                        <svg className="google-icon-svg" style={{ width: "16px", height: "16px" }} viewBox="0 0 48 48">
                          <path fill="#4285F4" d="M44.5 20H24v8.5h11.7C34.3 33.1 30 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 2.9l6-6C34.5 6.3 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20c11 0 20-9 20-20 0-1.3-.1-2.7-.4-4z" />
                          <path fill="#34A853" d="M6.3 14.7l7 5.1C15 16.8 19.2 14 24 14c3.1 0 5.8 1.1 8 2.9l6-6C34.5 6.3 29.6 4 24 4c-7.7 0-14.4 4.4-17.7 10.7z" />
                          <path fill="#FBBC05" d="M24 44c5.9 0 11-2 14.7-5.4l-6.8-5.5C30 34.6 27.1 36 24 36c-6 0-10.3-2.9-11.7-7.5l-7 5.4C8.5 40.1 15.6 44 24 44z" />
                          <path fill="#EA4335" d="M43.6 20H24v8.5h11.7c-1 2.7-2.7 5-5 6.6l6.8 5.5C41.7 37.5 44 31.2 44 24c0-1.3-.1-2.7-.4-4z" />
                        </svg>
                        <span>Continue with Google</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Duplicate Account Resolution Card */}
            {duplicateAccountInfo && (
              <div className="auth-duplicate-card">
                <div className="duplicate-card-header">
                  <AlertCircle className="w-4 h-4 text-purple-400 flex-shrink-0" />
                  <div>
                    <h5 className="duplicate-title">Account Already Exists</h5>
                    <p className="duplicate-desc">
                      An account with <strong>{duplicateAccountInfo.email}</strong> already exists.
                    </p>
                  </div>
                </div>
                {duplicateAccountInfo.signupMethod === "google" ? (
                  <button
                    type="button"
                    onClick={handleOAuth}
                    className="duplicate-action-btn"
                  >
                    Sign in with Google instead
                  </button>
                ) : (
                  <Link
                    to={`/sign-in?role=${role}`}
                    className="duplicate-action-btn"
                  >
                    Sign in to existing account
                  </Link>
                )}
              </div>
            )}

            {/* Divider: OR CONTINUE WITH */}
            <div className="auth-card-divider">
              <span className="divider-line" />
              <span className="divider-label">OR CONTINUE WITH</span>
              <span className="divider-line" />
            </div>

            {/* Google OAuth Button */}
            <button
              type="button"
              onClick={handleOAuth}
              disabled={!!oauthLoading}
              className="auth-google-oauth-btn"
            >
              {oauthLoading === "google" ? (
                <span className="auth-spinner-sm" />
              ) : (
                <svg className="google-icon-svg" viewBox="0 0 48 48">
                  <path fill="#4285F4" d="M44.5 20H24v8.5h11.7C34.3 33.1 30 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 2.9l6-6C34.5 6.3 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20c11 0 20-9 20-20 0-1.3-.1-2.7-.4-4z" />
                  <path fill="#34A853" d="M6.3 14.7l7 5.1C15 16.8 19.2 14 24 14c3.1 0 5.8 1.1 8 2.9l6-6C34.5 6.3 29.6 4 24 4c-7.7 0-14.4 4.4-17.7 10.7z" />
                  <path fill="#FBBC05" d="M24 44c5.9 0 11-2 14.7-5.4l-6.8-5.5C30 34.6 27.1 36 24 36c-6 0-10.3-2.9-11.7-7.5l-7 5.4C8.5 40.1 15.6 44 24 44z" />
                  <path fill="#EA4335" d="M43.6 20H24v8.5h11.7c-1 2.7-2.7 5-5 6.6l6.8 5.5C41.7 37.5 44 31.2 44 24c0-1.3-.1-2.7-.4-4z" />
                </svg>
              )}
              <span>Continue with Google</span>
            </button>

            {/* Bottom Footer Switch Link */}
            <div className="auth-card-footer">
              <span className="footer-lead-text">
                {isRegister ? "Already have an account?" : "Don't have an account?"}
              </span>{" "}
              <Link
                to={isRegister ? `/sign-in?role=${role}` : `/register?role=${role}`}
                className="footer-action-link"
              >
                {isRegister ? "Sign In" : "Create Account"}
              </Link>
            </div>
          </motion.div>
        </section>
      </main>
    </div>
  );
}
