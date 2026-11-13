"use client";

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check,
  Zap,
  Sparkles,
  Cpu,
  Globe,
  ShieldCheck,
  ArrowRight,
  Coins,
  Receipt,
  Activity,
  ChevronDown,
  Layers,
  Wand2,
  Lock,
  Loader2,
  ExternalLink,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/lib/api";
import { PLANS_LIST } from "@/lib/plans";
import "./Page.css";

const TOKEN_PACKS = [
  {
    id: "tokens_50",
    name: "Starter Compute Pack",
    credits: 50,
    freePrice: 10,
    proPrice: 6,
    extremePrice: 4,
    badge: "Entry Pack",
    unitPrice: "$0.20 (Free) · $0.12 (Pro) · $0.08 (Extreme) / token",
    description: "50 Studio Automation Credits for section fills, component generation, and template customizations.",
    popular: false,
  },
  {
    id: "tokens_200",
    name: "Creator Compute Pack",
    credits: 200,
    freePrice: 30,
    proPrice: 18,
    extremePrice: 12,
    badge: "Save 40% on Pro · 60% on Extreme",
    unitPrice: "$0.15 (Free) · $0.09 (Pro) · $0.06 (Extreme) / token",
    description: "200 Studio Automation Credits for multi-page builds, heavy copy revisions, and automated prompt edits.",
    popular: true,
  },
  {
    id: "tokens_500",
    name: "Extreme Studio Fleet Pack",
    credits: 500,
    freePrice: 60,
    proPrice: 35,
    extremePrice: 24,
    badge: "Best Value Pack",
    unitPrice: "$0.12 (Free) · $0.07 (Pro) · $0.048 (Extreme) / token",
    description: "500 Studio Automation Credits for continuous multi-site production, heavy coding, and fleet scaling.",
    popular: false,
  },
];

const FAQS = [
  {
    q: "How do monthly automation credits work?",
    a: "Every month, Pro subscribers receive 150 Automation compute credits and Extreme subscribers receive 1,000 Automation compute credits. Operations consume credits predictably (e.g. 5 credits per automated site generation or full Auto-Heal repair, 1 credit per Smart Fill copy revision or SEO generation). If you need more, you can purchase top-up packs anytime at a 40% (Pro) or 60% (Extreme) discount.",
  },
  {
    q: "How does managed website hosting work across tiers?",
    a: "Free users receive a 7-day trial deployment on our *.site-studio.live subdomain. Pro includes 1 active hosted website with custom domain connection (additional hosted sites are $12/month). Extreme includes 3 active hosted websites with custom domain connections (additional sites $12/month). All hosted websites receive global edge CDN delivery, automated TLS certificates, and DDoS shielding.",
  },
  {
    q: "How does autonomous Auto-Heal work?",
    a: "Auto-Heal continuously monitors your live site for runtime errors, broken assets, and layout regressions, automatically generating verified repair patches. Pro users can register 1 live deployment for Auto-Heal (up to 10 automated repairs/month). Extreme users can register up to 3 live deployments (up to 30 automated repairs/month).",
  },
  {
    q: "Can I use custom domains?",
    a: "Yes! Pro plans allow you to connect your custom domain to your 1 included hosted website. Extreme plans allow custom domain connections for up to 3 included hosted websites, and annual Extreme subscribers receive a promotional domain credit up to $15 for their first year.",
  },
  {
    q: "What payment gateways are supported?",
    a: "We support Stripe (international credit/debit cards, Apple Pay, Google Pay) and Razorpay (cards, UPI, NetBanking). All subscription cycles, invoices, and credit balances are updated automatically via secure webhooks.",
  },
];

export default function PricingPage() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);

  const [billingCycle, setBillingCycle] = useState("annual"); // "monthly" | "annual"
  const [siteCount, setSiteCount] = useState(3);
  const [purchasingPack, setPurchasingPack] = useState(null);
  const [openFaq, setOpenFaq] = useState(0);

  // Compute token estimator metrics
  const synthesisTokens = siteCount * 5;
  const healingTokens = siteCount * 5;
  const copyTokens = siteCount * 10;
  const totalEstimatedTokens = synthesisTokens + healingTokens + copyTokens;

  // Recommended plan logic
  let recommendedPlan = "Free Tier ($0)";
  let recommendedReason = "Ideal for exploring templates, code inspections, and trying 1 free website generation.";
  if (siteCount >= 1 && siteCount <= 3) {
    recommendedPlan = "Pro Plan ($19/mo or $190/yr)";
    recommendedReason = `Includes 150 monthly automation credits, 1 hosted site, up to 3 deployment slots, and 1 Auto-Heal site (10 repairs/mo)!`;
  } else if (siteCount > 3) {
    recommendedPlan = "Extreme Plan ($50/mo or $500/yr)";
    recommendedReason = `Includes 1,000 monthly automation credits, 3 hosted sites, up to 3 Auto-Heal sites (30 repairs/mo), and $15 domain credit!`;
  }

  // Handle Token Top-Up Purchase -> Takes user to checkout payment options
  const handlePurchaseTokens = (packId) => {
    navigate(`/checkout?pack=${packId}`);
  };

  return (
    <>
      <Navbar />

      <main className="pricing-page-container">
        <div className="pricing-page-inner">

          {/* ── 1. Hero Header & Billing Toggle ── */}
          <div className="pricing-hero">
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="pricing-pill-badge"
            >
              <Sparkles className="w-4 h-4 text-[#dfb180]" />
              <span>Transparent Automated Compute Architecture</span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.08 }}
              className="pricing-hero-title"
            >
              Simple, Predictable Plans for <br />
              <span className="gradient-text">Developers & Digital Studios</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.16 }}
              className="pricing-hero-sub"
            >
              Deploy production websites, personalize copy in real-time with Smart Fill, and let autonomous Auto-Heal resolve errors with zero downtime.
            </motion.p>

            {/* Billing Toggle Switch */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, delay: 0.22 }}
              className="pricing-toggle-wrap"
            >
              <button
                type="button"
                onClick={() => setBillingCycle("monthly")}
                className={`pricing-toggle-btn ${billingCycle === "monthly" ? "active" : ""}`}
              >
                Monthly Billing
              </button>
              <button
                type="button"
                onClick={() => setBillingCycle("annual")}
                className={`pricing-toggle-btn ${billingCycle === "annual" ? "active" : ""}`}
              >
                Annual Billing
                <span className="pricing-save-badge">Save 20%</span>
              </button>
            </motion.div>
          </div>

          {/* ── 2. Pricing Tiers Cards ── */}
          <div className="pricing-cards-grid">
            {PLANS_LIST.map((plan, idx) => {
              const displayMonthlyPrice = billingCycle === "annual" ? (plan.annualEffectiveMonthly || plan.monthlyPrice) : plan.monthlyPrice;
              return (
                <motion.div
                  key={plan.id}
                  initial={{ opacity: 0, y: 25 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, delay: 0.1 * idx }}
                  className={`pricing-tier-card ${plan.popular ? "featured" : ""}`}
                >
                  {plan.popular && (
                    <div className="pricing-featured-ribbon">
                      ✦ Recommended for Most Creators
                    </div>
                  )}

                  <div>
                    <div className="tier-top-meta">
                      <span className={`tier-badge ${plan.badgeType}`}>
                        {plan.badge}
                      </span>
                      <h3 className="tier-name">{plan.name}</h3>
                      <p className="tier-desc">{plan.description}</p>
                    </div>

                    <div className="tier-price-box">
                      <div className="tier-price-row">
                        <span className="tier-currency">$</span>
                        <span className={`tier-amount ${plan.popular ? "highlight" : ""}`}>
                          {displayMonthlyPrice}
                        </span>
                        <span className="tier-period">/ month</span>
                      </div>
                      {billingCycle === "annual" && plan.monthlyPrice > 0 && (
                        <div className="tier-sub-billing">
                          Billed annually (${plan.annualPrice}/year) · 2 months free
                        </div>
                      )}
                    </div>

                    <ul className="tier-features-list">
                      {plan.features.map((feat, fIdx) => (
                        <li key={fIdx} className="tier-feature-item">
                          {feat.icon === "gemini" ? (
                            <Coins className="tier-feature-icon gemini" />
                          ) : (
                            <Check className="tier-feature-icon check" />
                          )}
                          <span>
                            {feat.highlight ? <strong>{feat.text}</strong> : feat.text}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    {plan.monthlyPrice === 0 ? (
                      <Link to="/marketplace" className={`tier-cta-btn ${plan.ctaType}`}>
                        <span>{plan.cta}</span>
                        <ArrowRight className="w-4 h-4" />
                      </Link>
                    ) : (
                      <button
                        type="button"
                        onClick={() => navigate(`/subscribe?plan=${plan.id}&billing=${billingCycle}`)}
                        className={`tier-cta-btn ${plan.ctaType}`}
                      >
                        <span>{plan.cta}</span>
                        <ArrowRight className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>

          {/* ── 3. Interactive Website Token & Compute Estimator ── */}
          <div className="estimator-card">
            <div className="estimator-header">
              <div className="pricing-pill-badge" style={{ margin: "0 auto 1rem auto" }}>
                <Activity className="w-3.5 h-3.5 text-[#dfb180]" />
                <span>Real Compute Architecture</span>
              </div>
              <h2 className="estimator-title">Website Compute & Token Estimator</h2>
              <p className="estimator-sub">
                How many tokens does a website get and consume? Check how automation compute tokens power initial website synthesis, autonomous Auto-Heal, and live copy personalizations.
              </p>
            </div>

            {/* Stepper Selector */}
            <div className="estimator-controls">
              <span className="estimator-control-label">How many active websites do you manage?</span>
              <div className="estimator-buttons-row">
                {[1, 3, 5, 10, 25].map((count) => (
                  <button
                    key={count}
                    type="button"
                    onClick={() => setSiteCount(count)}
                    className={`site-count-btn ${siteCount === count ? "active" : ""}`}
                  >
                    {count} {count === 1 ? "Website" : "Websites"}
                  </button>
                ))}
              </div>
            </div>

            {/* Calculator Grid */}
            <div className="estimator-calc-grid">
              {/* Item 1: Multi-agent generation */}
              <div className="calc-breakdown-card">
                <div>
                  <div className="calc-icon-title">
                    <Wand2 className="w-4 h-4 text-[#dfb180]" />
                    <span>Synthesis & Architecture</span>
                  </div>
                  <p className="calc-card-desc">
                    Full multi-page synthesis, semantic audits, responsive reflow, and framework generation.
                  </p>
                </div>
                <div className="calc-val-box">
                  <span className="calc-val-num">~{synthesisTokens}</span>
                  <span className="calc-val-unit">tokens (5 / site)</span>
                </div>
              </div>

              {/* Item 2: Auto-healing */}
              <div className="calc-breakdown-card">
                <div>
                  <div className="calc-icon-title">
                    <Activity className="w-4 h-4 text-emerald-400" />
                    <span>Autonomous Site Healing</span>
                  </div>
                  <p className="calc-card-desc">
                    Autonomous error recovery, broken image 404 healing, CSS repairs, and continuous health monitoring.
                  </p>
                </div>
                <div className="calc-val-box">
                  <span className="calc-val-num">~{healingTokens}</span>
                  <span className="calc-val-unit">tokens / month</span>
                </div>
              </div>

              {/* Item 3: Smart Fill Personalization */}
              <div className="calc-breakdown-card">
                <div>
                  <div className="calc-icon-title">
                    <Sparkles className="w-4 h-4 text-[#dfb180]" />
                    <span>Smart Fill Copy Refinements</span>
                  </div>
                  <p className="calc-card-desc">
                    Targeted domain copywriting, localized translations, color theme generation, and automated SEO tags.
                  </p>
                </div>
                <div className="calc-val-box">
                  <span className="calc-val-num">~{copyTokens}</span>
                  <span className="calc-val-unit">tokens / month</span>
                </div>
              </div>

              {/* Item 4: Total & Recommended Plan */}
              <div className="calc-total-card">
                <div>
                  <span className="calc-total-header">Total Monthly Compute Need</span>
                  <div className="calc-total-number">
                    {totalEstimatedTokens} <span>Tokens / mo</span>
                  </div>
                </div>

                <div className="calc-rec-banner">
                  <strong>Recommended: {recommendedPlan}</strong>
                  <div style={{ marginTop: "0.25rem", fontSize: "0.75rem", opacity: 0.9 }}>
                    {recommendedReason}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── 4. On-Demand Compute Token Packs (Top-Ups) ── */}
          <div className="token-packs-section">
            <div className="token-packs-header">
              <div className="pricing-pill-badge" style={{ margin: "0 auto 1rem auto" }}>
                <Coins className="w-3.5 h-3.5 text-[#dfb180]" />
                <span>Pay-As-You-Go Credits</span>
              </div>
              <h2 className="estimator-title" style={{ fontSize: "1.85rem" }}>
                Studio Automation Token Packs
              </h2>
              <p className="estimator-sub">
                Need extra compute power without upgrading your monthly subscription? Add credits instantly with 1-click token packs. Credits never expire.
              </p>
            </div>

            <div className="token-packs-grid">
              {TOKEN_PACKS.map((pack) => {
                const userTier = (user?.subscription_tier || "free").toLowerCase();
                const isExtreme = ["extreme", "agency", "enterprise"].includes(userTier);
                const isPro = userTier === "pro";
                const userPrice = isExtreme ? pack.extremePrice : isPro ? pack.proPrice : pack.freePrice;

                return (
                  <div
                    key={pack.id}
                    className={`token-pack-card ${pack.popular ? "popular" : ""}`}
                  >
                    <span className="token-pack-tag">{pack.badge}</span>
                    <h4 className="token-pack-title">{pack.name}</h4>
                    <p className="token-pack-desc">{pack.description}</p>

                    <div className="token-pack-price-row">
                      <div>
                        <span className="token-pack-price">${userPrice}</span>
                        <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}> USD</span>
                        {isExtreme && (
                          <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", color: "#34d399", fontWeight: 600 }}>
                            (60% Extreme Tier Discount)
                          </span>
                        )}
                        {isPro && (
                          <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", color: "#c89666", fontWeight: 600 }}>
                            (40% Pro Tier Discount)
                          </span>
                        )}
                      </div>
                      <span className="token-pack-unitPrice">{pack.unitPrice}</span>
                    </div>

                    <button
                      type="button"
                      onClick={() => handlePurchaseTokens(pack.id)}
                      disabled={purchasingPack === pack.id}
                      className="token-buy-btn"
                    >
                      {purchasingPack === pack.id ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Processing Order...</span>
                        </>
                      ) : (
                        <>
                          <Coins className="w-4 h-4 text-[#dfb180]" />
                          <span>Get {pack.credits} Tokens for ${userPrice}</span>
                        </>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── 5. Full Payment & Subscription Report Banner ── */}
          <div className="billing-report-cta-card">
            <div className="report-cta-text">
              <h3>View Your Full Payment & Subscription Report</h3>
              <p>
                Access all completed template transactions, recurring monthly hosting subscriptions, automation compute purchases, and official tax invoice receipts in one verified dashboard.
              </p>
            </div>

            <div className="report-cta-actions">
              <Link
                to={user ? "/dashboard?tab=orders" : "/sign-in?redirect=/dashboard?tab=orders"}
                className="report-btn-view"
              >
                <Receipt className="w-4 h-4" />
                <span>Open Payment Report</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>

          {/* ── 6. FAQ Accordion ── */}
          <div className="pricing-faq-section">
            <h2 className="faq-title">Frequently Asked Questions</h2>
            <div className="faq-list">
              {FAQS.map((faq, idx) => {
                const isOpen = openFaq === idx;
                return (
                  <div key={idx} className="faq-item">
                    <button
                      type="button"
                      onClick={() => setOpenFaq(isOpen ? null : idx)}
                      className="faq-question"
                    >
                      <span>{faq.q}</span>
                      <ChevronDown
                        className="w-4 h-4 text-[#dfb180] transition-transform duration-200"
                        style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0deg)" }}
                      />
                    </button>
                    <AnimatePresence>
                      {isOpen && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.2 }}
                          className="faq-answer"
                        >
                          {faq.a}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          </div>

        </div>
      </main>
    </>
  );
}
