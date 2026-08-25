/**
 * Onboarding page — collects profile details after social (Google/Facebook) login.
 * Forces even OAuth users to provide their full name, phone, and role before proceeding.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate, useLocation } from "react-router-dom";
import {
  User, Phone, Sparkles, ArrowRight, Building2, Globe, AlertCircle,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";
import "./Page.css";

const isCompanyEmail = (email) => {
  if (!email || !email.includes("@")) return false;
  const domain = email.split("@").pop().toLowerCase();
  const publicDomains = new Set([
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "zoho.com", "protonmail.com", "proton.me", "mail.com",
    "yandex.com", "gmx.com", "live.com", "msn.com"
  ]);
  return !publicDomains.has(domain);
};

export default function OnboardingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const from = params.get("from") || "/dashboard";
  const defaultRole = params.get("role") || "buyer";

  const user = useAuthStore((s) => s.user);
  const userEmail = user?.primaryEmailAddress?.emailAddress || user?.email || "";

  const completeOnboarding = useAuthStore((s) => s.completeOnboarding);
  const pendingOAuthData = useAuthStore((s) => s.pendingOAuthData);
  const providerLabel = useAuthStore((s) =>
    s.pendingProvider === "google" ? "Google" : s.pendingProvider === "github" ? "GitHub" : "Social"
  );

  const [role, setRole] = useState(defaultRole);
  const [form, setForm] = useState({
    firstName: pendingOAuthData?.firstName || "",
    lastName: pendingOAuthData?.lastName || "",
    phone: "",
    businessName: "",
    portfolio: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Automatically select Seller role if user email is a company email (e.g. name@company.com)
  useEffect(() => {
    if (userEmail && isCompanyEmail(userEmail)) {
      setRole("seller");
    }
  }, [userEmail]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.firstName || !form.lastName) {
      setError("Please enter your full name.");
      return;
    }
    if (role === "seller" && !isCompanyEmail(userEmail)) {
      setError("To register as a seller, your connected social account email must be a company email address (not public domains like Gmail).");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await completeOnboarding({ ...form, role });
      navigate(from, { replace: true });
    } catch (err) {
      setError(err?.message || "Failed to save profile. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="onboarding-page">
      {/* Ambient */}
      <div className="onboarding-glow-top" />
      <div className="onboarding-glow-bottom" />

      <div className="onboarding-form-box">
        {/* Logo */}
        <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          className="onboarding-logo-row"
        >
          <img src="/logo.png" alt="Site Studio Logo" className="navbar-logo-img" width={36} height={36} />
          <span className="logo-text">
            Site Studio
          </span>
        </motion.div>

        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.05 } }}
          className="onboarding-header-wrapper"
        >
          <div className="onboarding-connection-pill">
            <svg className="connected-check-icon" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            {providerLabel} connected
          </div>
          <h1 className="onboarding-title">Almost there!</h1>
          <p className="onboarding-subtitle">
            We just need a few more details to complete your profile.
          </p>
        </motion.div>

        {/* Form */}
        <motion.form
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.12 } }}
          onSubmit={handleSubmit}
          className="onboarding-form"
        >
          {/* Role */}
          <div>
            <label className="onboarding-label">
              I am a…
            </label>
            <div className="onboarding-role-group">
              {[
                { value: "buyer", label: "🛍️ Buyer" },
                { value: "seller", label: "📤 Seller" },
              ].map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setRole(value)}
                  className={cn(
                    "onboarding-role-btn",
                    role === value && "active"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            {role === "seller" && !isCompanyEmail(userEmail) && (
              <p style={{ color: "#ef4444", fontSize: "0.8rem", marginTop: "0.5rem" }}>
                ⚠️ Your email ({userEmail || "unknown"}) is not a company email address. You cannot register as a seller with this email.
              </p>
            )}
          </div>

          {/* Name row */}
          <div className="onboarding-name-row">
            <div className="onboarding-input-wrap name-field">
              <User className="onboarding-icon" />
              <input
                type="text"
                placeholder="First name"
                value={form.firstName}
                onChange={set("firstName")}
                className="onboarding-input has-icon"
                required
              />
            </div>
            <div className="onboarding-input-wrap name-field">
              <input
                type="text"
                placeholder="Last name"
                value={form.lastName}
                onChange={set("lastName")}
                className="onboarding-input"
                required
              />
            </div>
          </div>

          {/* Phone */}
          <div className="onboarding-input-wrap">
            <Phone className="onboarding-icon" />
            <input
              type="tel"
              placeholder="Phone number (optional)"
              value={form.phone}
              onChange={set("phone")}
              className="onboarding-input has-icon"
            />
          </div>

          {/* Seller extras */}
          {role === "seller" && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="onboarding-seller-extras"
            >
              <div className="onboarding-input-wrap">
                <Building2 className="onboarding-icon" />
                <input
                  type="text"
                  placeholder="Business / Studio name"
                  value={form.businessName}
                  onChange={set("businessName")}
                  className="onboarding-input has-icon"
                  required={role === "seller"}
                />
              </div>
              <div className="onboarding-input-wrap">
                <Globe className="onboarding-icon" />
                <input
                  type="url"
                  placeholder="Portfolio URL (optional)"
                  value={form.portfolio}
                  onChange={set("portfolio")}
                  className="onboarding-input has-icon"
                />
              </div>
            </motion.div>
          )}

          {/* Error */}
          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="onboarding-error-alert"
            >
              <AlertCircle className="onboarding-error-icon" /> {error}
            </motion.div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="onboarding-submit-btn"
          >
            {loading ? (
              <span className="onboarding-btn-loader" />
            ) : (
              <>
                Complete Setup <ArrowRight className="onboarding-submit-arrow" />
              </>
            )}
          </button>
        </motion.form>
      </div>
    </div>
  );
}
