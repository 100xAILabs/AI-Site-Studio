import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Link, useNavigate, useLocation } from "react-router";
import { Sparkles, AlertCircle, Eye, EyeOff, Lock } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useAppUser } from "@/lib/auth";
import { cn } from "@/lib/utils";
import "./Page.css";

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0, transition: { delay, duration: 0.45 } },
});



export default function SignInPage({ isRegister = false }) {
  const navigate = useNavigate();
  const location = useLocation();
  const from = new URLSearchParams(location.search).get("from") || "/dashboard";
  const initialRole = new URLSearchParams(location.search).get("role") || "buyer";
  const urlError = new URLSearchParams(location.search).get("error") || "";

  const { isSignedIn, isLoaded } = useAppUser();

  const [role, setRole] = useState(initialRole);
  const [agreed, setAgreed] = useState(true);
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
  const [duplicateAccountInfo, setDuplicateAccountInfo] = useState(null); // { signupMethod, email }

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      navigate(from, { replace: true });
    }
  }, [isLoaded, isSignedIn, navigate, from]);

  // Sync role when initialRole query parameter changes
  useEffect(() => {
    if (initialRole) {
      setRole(initialRole);
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
        // Redirect to OTP page after successful registration
        if (result?.requires_otp) {
          navigate(`/verify-otp?email=${encodeURIComponent(result.email || email)}`);
          return;
        }
      } else {
        const result = await signInWithEmail({ email, password });
        // If backend requires OTP verification, redirect to OTP page
        if (result?.requires_otp) {
          navigate(`/verify-otp?email=${encodeURIComponent(email)}`);
          return;
        }
        // Reset attempt counter on success
        setFailedAttempts(0);
      }
    } catch (err) {
      console.error(err);

      // 409 = duplicate account — show a special card instead of generic error
      if (err.status === 409) {
        setDuplicateAccountInfo({ signupMethod: err.signupMethod || "unknown", email });
        setAuthLoading(false);
        return;
      }

      const newAttempts = failedAttempts + 1;
      setFailedAttempts(newAttempts);

      if (err?.message?.includes('locked') || err?.message?.includes('429')) {
        setIsLocked(true);
        setLockTimer(60);
        setError("Account temporarily locked due to too many failed attempts. Please wait 60 seconds.");
      } else if (newAttempts >= MAX_ATTEMPTS) {
        setIsLocked(true);
        setLockTimer(60);
        setError("Too many failed attempts. Account temporarily locked for 60 seconds.");
      } else {
        const remaining = MAX_ATTEMPTS - newAttempts;
        setError(
          `${err?.response?.data?.detail || err?.message || "Authentication failed."} ${remaining > 0 ? `${remaining} attempt${remaining === 1 ? '' : 's'} remaining before lockout.` : ''}`
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

  return (
    <div className="auth-page-container">
      {/* Left visual panel */}
      <div className="auth-left-panel">
        <div className="auth-glow-top" />
        <div className="auth-glow-bottom" />

        {/* Logo */}
        <div className="auth-brand-logo">
          <img
            src="/logo.png"
            alt="AI Site Studio Logo"
            className="navbar-logo-img"
            width={40}
            height={40}
          />
          <span className="auth-logo-text">
            AI Site Studio
          </span>
        </div>

        {/* Testimonial */}
        <div className="auth-testimonial-section">
          <blockquote className="auth-blockquote">
            "Launched my portfolio in{" "}
            <span style={{ color: "hsl(var(--primary))" }}>under 10 minutes</span> — AI
            filled in the copy and it looked stunning."
          </blockquote>
          <div className="auth-testimonial-author">
            <img
              src="https://picsum.photos/seed/testimonial1/48"
              alt="Sarah Chen"
              className="auth-testimonial-avatar"
            />
            <div>
              <p className="auth-testimonial-name">Sarah Chen</p>
              <p className="auth-testimonial-title">Freelance Designer</p>
            </div>
          </div>
        </div>

        {/* Stats row */}
        <div className="auth-stats-row">
          {[
            { label: "Templates", value: "500+" },
            { label: "Customers", value: "12K+" },
            { label: "Rating", value: "4.9 ★" },
          ].map((s) => (
            <div key={s.label}>
              <p className="auth-stat-value">{s.value}</p>
              <p className="auth-stat-label">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Right form panel */}
      <div className="auth-right-panel">
        <div className="auth-form-wrapper">
          {/* Mobile logo */}
          <div className="auth-brand-logo-mobile">
            <img src="/logo.png" alt="AI Site Studio Logo" className="navbar-logo-img" width={32} height={32} />
            <span className="auth-logo-text">
              AI Site Studio
            </span>
          </div>

          <motion.div {...fadeUp(0)}>
            <h1 className="auth-form-title">
              {isRegister ? "Create an account" : "Welcome back"}
            </h1>
            <p className="auth-form-subtitle">
              Sign in securely using Google. No extra passwords needed.
            </p>
          </motion.div>



          {/* Social Buttons */}
          <motion.div {...fadeUp(0.08)} className="auth-social-group">
            <button
              onClick={() => handleOAuth()}
              disabled={!!oauthLoading}
              className="social-btn"
            >
              {oauthLoading === "google" ? (
                <span className="auth-btn-loader social" />
              ) : (
                <svg className="social-svg-icon" viewBox="0 0 48 48">
                  <path fill="#4285F4" d="M44.5 20H24v8.5h11.7C34.3 33.1 30 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 2.9l6-6C34.5 6.3 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20c11 0 20-9 20-20 0-1.3-.1-2.7-.5-4z" />
                  <path fill="#34A853" d="M6.3 14.7l7 5.1C15 16.8 19.2 14 24 14c3.1 0 5.8 1.1 8 2.9l6-6C34.5 6.3 29.6 4 24 4c-7.7 0-14.4 4.4-17.7 10.7z" />
                  <path fill="#FBBC05" d="M24 44c5.9 0 11-2 14.7-5.4l-6.8-5.5C30 34.6 27.1 36 24 36c-6 0-10.3-2.9-11.7-7.5l-7 5.4C8.5 40.1 15.6 44 24 44z" />
                  <path fill="#EA4335" d="M43.6 20H24v8.5h11.7c-1 2.7-2.7 5-5 6.6l6.8 5.5C41.7 37.5 44 31.2 44 24c0-1.3-.1-2.7-.4-4z" />
                </svg>
              )}
              Continue with Google
            </button>
          </motion.div>
          {/* Divider */}
          <motion.div {...fadeUp(0.07)} className="auth-divider">
            <div className="auth-divider-line"></div>
            <span className="auth-divider-text">Or continue with</span>
          </motion.div>

          {/* Email/Password Form */}
          <motion.form {...fadeUp(0.12)} onSubmit={handleEmailAuth} className="auth-email-form">
            <div>
              <label className="auth-input-label" htmlFor="email-input">
                Email Address
              </label>
              <input
                id="email-input"
                type="email"
                required
                className="auth-input-field"
                placeholder={role === "seller" ? "username@company.com" : "you@example.com"}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <label className="auth-input-label" htmlFor="password-input">
                  Password
                </label>
                {!isRegister && (
                  <Link
                    to="/forgot-password"
                    className="auth-footer-link"
                    style={{ fontSize: "0.75rem", marginBottom: "0.25rem" }}
                  >
                    Forgot password?
                  </Link>
                )}
              </div>
              <div className="auth-password-wrapper">
                <input
                  id="password-input"
                  type={showPassword ? "text" : "password"}
                  required
                  className="auth-input-field"
                  placeholder="••••••••"
                  disabled={isLocked}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <EyeOff size={16} />
                  ) : (
                    <Eye size={16} />
                  )}
                </button>
              </div>
            </div>

            {isRegister && (
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.25rem", marginBottom: "0.25rem" }}>
                <input
                  id="agreed-checkbox"
                  type="checkbox"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  style={{ width: "1rem", height: "1rem", cursor: "pointer" }}
                />
                <label htmlFor="agreed-checkbox" style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", cursor: "pointer" }}>
                  I agree to the Terms of Service and Privacy Policy
                </label>
              </div>
            )}

            {/* Attempt counter progress bar */}
            {!isRegister && failedAttempts > 0 && !isLocked && (
              <div style={{ marginTop: "0.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", color: "hsl(var(--muted-foreground))", marginBottom: "0.25rem" }}>
                  <span>Failed attempts</span>
                  <span style={{ color: failedAttempts >= 4 ? "#ef4444" : failedAttempts >= 2 ? "#f59e0b" : "hsl(var(--muted-foreground))" }}>
                    {failedAttempts}/{MAX_ATTEMPTS}
                  </span>
                </div>
                <div style={{ height: "2px", background: "rgba(255,255,255,0.06)", borderRadius: "1px", overflow: "hidden" }}>
                  <div style={{
                    height: "100%",
                    width: `${(failedAttempts / MAX_ATTEMPTS) * 100}%`,
                    background: failedAttempts >= 4 ? "#ef4444" : failedAttempts >= 2 ? "#f59e0b" : "hsl(var(--primary))",
                    borderRadius: "1px",
                    transition: "width 0.3s ease"
                  }} />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={authLoading || isLocked}
              className="auth-submit-btn"
            >
              {isLocked ? (
                <>
                  <Lock size={14} />
                  Locked ({lockTimer}s)
                </>
              ) : authLoading ? (
                <span className="auth-btn-loader" />
              ) : isRegister ? (
                "Create Account"
              ) : (
                "Sign In"
              )}
            </button>
          </motion.form>

          {/* Lockout Banner */}
          {isLocked && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                background: "rgba(239, 68, 68, 0.08)",
                border: "1px solid rgba(239, 68, 68, 0.25)",
                borderRadius: "0.5rem",
                padding: "0.875rem",
                marginBottom: "0.75rem",
              }}
            >
              <Lock size={18} color="#ef4444" style={{ flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: "0.8rem", fontWeight: 600, color: "#ef4444", marginBottom: "0.15rem" }}>Account Temporarily Locked</p>
                <p style={{ fontSize: "0.72rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.4 }}>
                  Too many failed attempts. Try again in <strong style={{ color: "#ef4444" }}>{lockTimer}s</strong>.
                </p>
              </div>
            </motion.div>
          )}

          {/* Error */}
          {error && !isLocked && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="auth-error-alert"
            >
              <AlertCircle className="auth-error-icon" />
              {error}
            </motion.div>
          )}

          {/* Duplicate Account Card */}
          {duplicateAccountInfo && (
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{
                background: "rgba(99, 102, 241, 0.07)",
                border: "1px solid rgba(99, 102, 241, 0.25)",
                borderRadius: "0.75rem",
                padding: "1.1rem",
                marginBottom: "0.75rem",
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
              }}
            >
              <div style={{ display: "flex", gap: "0.625rem", alignItems: "flex-start" }}>
                <div style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: "rgba(99,102,241,0.15)",
                  display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                }}>
                  <AlertCircle size={16} color="hsl(var(--primary))" />
                </div>
                <div>
                  <p style={{ fontSize: "0.82rem", fontWeight: 700, color: "hsl(var(--foreground))", marginBottom: "0.2rem" }}>
                    Account Already Exists
                  </p>
                  <p style={{ fontSize: "0.75rem", color: "hsl(var(--muted-foreground))", lineHeight: 1.5 }}>
                    An account with <strong style={{ color: "hsl(var(--foreground))" }}>{duplicateAccountInfo.email}</strong> already exists.{" "}
                    {duplicateAccountInfo.signupMethod === "google"
                      ? "This account was created using Google Sign-In."
                      : duplicateAccountInfo.signupMethod === "email"
                      ? "This account uses email & password login."
                      : "This account was created using a social login."}
                  </p>
                </div>
              </div>

              {duplicateAccountInfo.signupMethod === "google" ? (
                <button
                  onClick={handleOAuth}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem",
                    padding: "0.6rem 1rem", borderRadius: "0.4rem",
                    background: "white", color: "#111", fontWeight: 600, fontSize: "0.8rem",
                    border: "none", cursor: "pointer", transition: "opacity 0.2s",
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 48 48">
                    <path fill="#4285F4" d="M44.5 20H24v8.5h11.7C34.3 33.1 30 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 2.9l6-6C34.5 6.3 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20c11 0 20-9 20-20 0-1.3-.1-2.7-.5-4z" />
                    <path fill="#34A853" d="M6.3 14.7l7 5.1C15 16.8 19.2 14 24 14c3.1 0 5.8 1.1 8 2.9l6-6C34.5 6.3 29.6 4 24 4c-7.7 0-14.4 4.4-17.7 10.7z" />
                    <path fill="#FBBC05" d="M24 44c5.9 0 11-2 14.7-5.4l-6.8-5.5C30 34.6 27.1 36 24 36c-6 0-10.3-2.9-11.7-7.5l-7 5.4C8.5 40.1 15.6 44 24 44z" />
                    <path fill="#EA4335" d="M43.6 20H24v8.5h11.7c-1 2.7-2.7 5-5 6.6l6.8 5.5C41.7 37.5 44 31.2 44 24c0-1.3-.1-2.7-.4-4z" />
                  </svg>
                  Sign in with Google instead
                </button>
              ) : (
                <Link
                  to={`/sign-in?role=${role}`}
                  style={{
                    display: "block", textAlign: "center", padding: "0.6rem 1rem",
                    borderRadius: "0.4rem", background: "hsl(var(--primary))",
                    color: "white", fontWeight: 600, fontSize: "0.8rem",
                    textDecoration: "none",
                  }}
                >
                  Sign in to existing account
                </Link>
              )}
            </motion.div>
          )}

          <motion.p {...fadeUp(0.16)} className="auth-footer-text">
            {isRegister ? (
              <>
                Already have an account?{" "}
                <Link
                  to={`/sign-in?role=${role}`}
                  className="auth-footer-link"
                >
                  Sign in
                </Link>
              </>
            ) : (
              <>
                Don't have an account?{" "}
                <Link
                  to={`/register?role=${role}`}
                  className="auth-footer-link"
                >
                  Create account
                </Link>
              </>
            )}
          </motion.p>
        </div>
      </div>
    </div>
  );
}
