"use client";

import { useState, useEffect } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { useAppUser } from "@/lib/auth";
import {
  Store,
  Mail,
  Lock,
  Eye,
  EyeOff,
  User,
  ArrowLeft,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import "./auth.css";

export default function CreatorClientAuthPage({ isRegister: defaultRegister = false }) {
  const navigate = useNavigate();
  const params = useParams();
  const [searchParams] = useSearchParams();

  const routeSlug = params?.creatorSlug || params?.slug;
  const querySlug = searchParams.get("creator");
  const creatorSlug = routeSlug || querySlug || "";

  const [isRegister, setIsRegister] = useState(defaultRegister);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { isSignedIn, user } = useAppUser();
  const signInWithEmail = useAuthStore((s) => s.signInWithEmail);
  const registerWithEmail = useAuthStore((s) => s.registerWithEmail);

  // Fetch creator storefront profile for whitelabel branding
  const { data: storefront, isLoading: sfLoading } = useQuery({
    queryKey: ["creatorStorefrontAuth", creatorSlug],
    queryFn: async () => {
      if (!creatorSlug) return null;
      const res = await api.get(`/creator/storefront/${encodeURIComponent(creatorSlug)}`);
      return res;
    },
    enabled: Boolean(creatorSlug),
    staleTime: 60 * 1000,
  });

  const brandName = storefront?.brand_name || "Creator Storefront";

  // If already signed in, redirect straight back to the creator storefront
  useEffect(() => {
    if (isSignedIn && user) {
      navigate(`/creator/${creatorSlug}`, { replace: true });
    }
  }, [isSignedIn, user, creatorSlug, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Please fill in both email and password.");
      return;
    }
    if (isRegister && !agreeTerms) {
      setError("Please accept the terms to create an account.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      if (isRegister) {
        const res = await registerWithEmail({
          email: email.trim().toLowerCase(),
          password,
          role: "buyer",
          creator_slug: creatorSlug,
        });

        if (res?.requires_otp) {
          navigate(`/verify-otp?email=${encodeURIComponent(email)}&creator=${encodeURIComponent(creatorSlug)}`, {
            state: {
              email: email.trim().toLowerCase(),
              role: "buyer",
              sent: res.sent,
              message: res.message,
              creator_slug: creatorSlug,
            },
          });
          return;
        }

        // Auto-attributed and logged in
        navigate(`/creator/${creatorSlug}`, { replace: true });
      } else {
        const res = await signInWithEmail({
          email: email.trim().toLowerCase(),
          password,
          role: "buyer",
          creator_slug: creatorSlug,
        });

        if (res?.requires_otp) {
          navigate(`/verify-otp?email=${encodeURIComponent(email)}&creator=${encodeURIComponent(creatorSlug)}`, {
            state: {
              email: email.trim().toLowerCase(),
              role: "buyer",
              sent: res.sent,
              message: res.message,
              creator_slug: creatorSlug,
            },
          });
          return;
        }

        navigate(`/creator/${creatorSlug}`, { replace: true });
      }
    } catch (err) {
      setError(err?.message || "Authentication failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="creator-auth-page">
      <div className="creator-auth-glow-top" />

      {/* Top Header */}
      <header className="creator-auth-header">
        <Link to={`/creator/${creatorSlug}`} className="creator-auth-brand-badge">
          <div className="creator-auth-brand-logo">
            {storefront?.logo_url ? (
              <img src={storefront.logo_url} alt={brandName} />
            ) : (
              <Store className="w-5 h-5 text-[#dfb180]" />
            )}
          </div>
          <div>
            <div className="creator-auth-brand-title">{brandName}</div>
            <div className="creator-auth-brand-sub">
              <ShieldCheck className="w-3 h-3" />
              <span>Official Creator Portal</span>
            </div>
          </div>
        </Link>

        <Link to={`/creator/${creatorSlug}`} className="creator-auth-back-btn">
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to {brandName}</span>
        </Link>
      </header>

      {/* Auth Card Body */}
      <main className="creator-auth-body">
        <div className="creator-auth-card">
          <div className="creator-auth-card-hero">
            <div className="creator-auth-icon-circle">
              <User className="w-5 h-5" />
            </div>
            <h1 className="creator-auth-heading">
              {isRegister ? `Join ${brandName}` : `Welcome Back`}
            </h1>
            <p className="creator-auth-subtext">
              {isRegister
                ? `Create a client account to download templates and receive direct updates from ${brandName}.`
                : `Sign in to access your purchased templates and license keys from ${brandName}.`}
            </p>
          </div>

          {/* Tab Switcher */}
          <div className="creator-auth-tabs">
            <button
              type="button"
              className={`creator-auth-tab ${!isRegister ? "active" : ""}`}
              onClick={() => {
                setIsRegister(false);
                setError("");
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`creator-auth-tab ${isRegister ? "active" : ""}`}
              onClick={() => {
                setIsRegister(true);
                setError("");
              }}
            >
              Create Client Account
            </button>
          </div>

          {error && (
            <div className="creator-auth-error mb-4">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="creator-auth-form">
            <div className="creator-auth-field">
              <label className="creator-auth-label">Email Address</label>
              <div className="creator-auth-input-box">
                <Mail className="creator-auth-input-icon w-4 h-4" />
                <input
                  type="email"
                  required
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="creator-auth-input"
                  autoComplete="email"
                />
              </div>
            </div>

            <div className="creator-auth-field">
              <label className="creator-auth-label">Password</label>
              <div className="creator-auth-input-box">
                <Lock className="creator-auth-input-icon w-4 h-4" />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="creator-auth-input"
                  autoComplete={isRegister ? "new-password" : "current-password"}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="creator-auth-eye-btn"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {isRegister && (
              <label className="creator-auth-checkbox-row">
                <input
                  type="checkbox"
                  checked={agreeTerms}
                  onChange={(e) => setAgreeTerms(e.target.checked)}
                />
                <span>
                  I agree to the template license agreement and customer privacy policy.
                </span>
              </label>
            )}

            <button
              type="submit"
              disabled={loading}
              className="creator-auth-submit-btn"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{isRegister ? "Creating Account..." : "Signing In..."}</span>
                </>
              ) : (
                <>
                  <span>{isRegister ? "Create Account & Continue" : "Sign In to Client Portal"}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="creator-auth-footer">
            {isRegister ? (
              <p>
                Already have a client account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setIsRegister(false);
                    setError("");
                  }}
                  className="text-[#dfb180] font-semibold bg-transparent border-none cursor-pointer"
                >
                  Sign In
                </button>
              </p>
            ) : (
              <p>
                Need an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setIsRegister(true);
                    setError("");
                  }}
                  className="text-[#dfb180] font-semibold bg-transparent border-none cursor-pointer"
                >
                  Create Client Account
                </button>
              </p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
