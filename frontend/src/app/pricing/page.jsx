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
import "./Page.css";

const PLANS = [
  {
    id: "free",
    badge: "Free Starter",
    badgeType: "free",
    name: "Free Tier",
    description: "Explore templates, inspect code, and purchase credits only when you want to build or edit.",
    monthlyPrice: 0,
    annualPrice: 0,
    tokensIncluded: 0,
    deploymentsIncluded: 0,
    features: [
      { text: "1 Free Website Generation included (Build your first site 100% free)", highlight: true, icon: "gemini" },
      { text: "Buy credits on-demand to create additional websites ($10 / 50 tokens)", highlight: true },
      { text: "1 Watermarked template download only (One-time test)", highlight: false },
      { text: "Option to buy templates clean without watermark", highlight: false },
      { text: "Deploy live websites with hosting charges ($12/mo)", highlight: false },
      { text: "Auto-heal (AI Site Doctor) is disabled", highlight: false },
      { text: "Inspect template code & sandbox preview", highlight: false },
    ],
    cta: "Start Free",
    ctaType: "outline",
    href: "/marketplace",
    popular: false,
  },
  {
    id: "pro",
    badge: "✦ Most Popular for Creators",
    badgeType: "pro",
    name: "Pro Plan",
    description: "For creators who want clean downloads, live deployments, and autonomous site healing.",
    monthlyPrice: 19,
    annualPrice: 15,
    tokensIncluded: 150,
    deploymentsIncluded: 3,
    features: [
      { text: "Download templates without watermark", highlight: true },
      { text: "150 Gemini AI Credits / month for template creation & edits", highlight: true, icon: "gemini" },
      { text: "Discounted token packs (40% OFF compared to Free users)", highlight: true },
      { text: "Deploy up to 3 live websites on high-speed edge", highlight: true },
      { text: "Free editor access with up to 2 image replacements per template", highlight: false },
      { text: "Auto-heal for 1 website (locked once registered, cannot change)", highlight: false },
      { text: "Instant Studio subdomains (*.aisitestudio.com)", highlight: false },
      { text: "Standard email & community support", highlight: false },
    ],
    cta: "Upgrade to Pro",
    ctaType: "primary",
    href: "/subscribe?plan=pro",
    popular: true,
  },
  {
    id: "extreme",
    badge: "⚡ Extreme — Full Power",
    badgeType: "agency",
    name: "Extreme Plan",
    description: "Total power: generate full-stack code without credit friction, free hosting deployments, and resell your templates.",
    monthlyPrice: 50,
    annualPrice: 40,
    tokensIncluded: 1000,
    deploymentsIncluded: 999,
    features: [
      { text: "Generate code without extra credit friction (1,000+ AI credits/mo)", highlight: true, icon: "gemini" },
      { text: "Free deployment charges (Unlimited live hosting included)", highlight: true },
      { text: "Resell your templates on the marketplace (platform fee applies)", highlight: true },
      { text: "Unlimited image & asset changes multiple times", highlight: true },
      { text: "AI Prompt Editor fully unlocked for conversational code edits", highlight: true },
      { text: "Autonomous AI Site Doctor: Heal unlimited websites automatically", highlight: true },
      { text: "Cheapest token top-ups (60% OFF lowest rates)", highlight: false },
      { text: "White-label exports & zero watermark on all source code", highlight: false },
    ],
    cta: "Get Extreme Plan",
    ctaType: "agency-btn",
    href: "/subscribe?plan=extreme",
    popular: false,
  },
];

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
    description: "50 Gemini AI Credits for section fills, component generation, and template customizations.",
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
    description: "200 Gemini AI Credits for multi-page builds, heavy copy revisions, and AI prompt edits.",
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
    description: "500 Gemini AI Credits for continuous multi-site production, heavy coding, and fleet scaling.",
    popular: false,
  },
];

const FAQS = [
  {
    q: "How many tokens does a website typically consume?",
    a: "On AI Site Studio, 1 active website consumes approximately 15 to 20 Gemini AI credits per month: ~5 credits for initial multi-page synthesis, ~5 credits for autonomous AI Site Doctor error & link healing, and ~5-10 credits for live AI Fill copywriting and brand customization. A Pro plan (150 credits/mo) comfortably powers 5 to 8 live websites.",
  },
  {
    q: "What happens if I run out of monthly AI tokens?",
    a: "Your deployed websites will continue serving traffic at 100% uptime with zero interruption! Only autonomous self-healing and AI Fill copy refinements will pause until your monthly quota renews or you grab an on-demand token top-up pack starting at just $5.",
  },
  {
    q: "How does managed website hosting billing work?",
    a: "Managed hosting is $12.00/month per live website on our High-speed Local Edge Tier, or included with our Pro (3 sites included) and Agency (unlimited sites) subscription plans. Every deployment receives sub-millisecond edge routing, DDoS shielding, and automated TLS 1.3 certificates.",
  },
  {
    q: "Where can I view my full payment history, invoices, and receipts?",
    a: "You can view your complete payment report anytime under Dashboard > Billing & Payment Report. Every single charge generates an official, downloadable tax invoice with itemized VAT/GST breakdown and 256-bit transaction verification.",
  },
  {
    q: "What payment gateways are supported?",
    a: "We support Stripe (international credit/debit cards, Apple Pay, Google Pay), Razorpay (domestic & international cards, NetBanking), and instant UPI QR payments with 12-digit bank reference verification.",
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
  let recommendedReason = "Ideal for exploring templates, code inspections, and on-demand credit purchases.";
  if (siteCount >= 2 && siteCount <= 3) {
    recommendedPlan = "Pro Plan ($15/mo)";
    recommendedReason = `Includes 150 monthly tokens + 3 live website deployments with 40% OFF token pack discounts!`;
  } else if (siteCount > 3) {
    recommendedPlan = "Extreme Plan ($40/mo)";
    recommendedReason = `Includes 1,000+ monthly tokens, free deployments, unlimited auto-heal, and template reselling.`;
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
              <span>Transparent Gemini Compute Architecture</span>
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
              Deploy production websites, personalize copy in real-time with Gemini AI Fill, and let autonomous AI Doctor heal errors with zero downtime.
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
            {PLANS.map((plan, idx) => {
              const price = billingCycle === "annual" ? plan.annualPrice : plan.monthlyPrice;
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
                      ✦ Recommended for Most Studios
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
                          {price}
                        </span>
                        <span className="tier-period">/ month</span>
                      </div>
                      {billingCycle === "annual" && plan.monthlyPrice > 0 && (
                        <div className="tier-sub-billing">
                          Billed annually (${price * 12}/year) · 2 months free
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
                How many tokens does a website get and consume? Check how Gemini AI tokens power initial website synthesis, autonomous AI Doctor healing, and live copy personalizations.
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

              {/* Item 2: AI Doctor Auto-healing */}
              <div className="calc-breakdown-card">
                <div>
                  <div className="calc-icon-title">
                    <Activity className="w-4 h-4 text-emerald-400" />
                    <span>AI Site Doctor Healing</span>
                  </div>
                  <p className="calc-card-desc">
                    Autonomous error recovery, broken image 404 healing, CSS repairs, and health monitoring.
                  </p>
                </div>
                <div className="calc-val-box">
                  <span className="calc-val-num">~{healingTokens}</span>
                  <span className="calc-val-unit">tokens / month</span>
                </div>
              </div>

              {/* Item 3: AI Fill Personalization */}
              <div className="calc-breakdown-card">
                <div>
                  <div className="calc-icon-title">
                    <Sparkles className="w-4 h-4 text-[#dfb180]" />
                    <span>AI Fill Copy Refinements</span>
                  </div>
                  <p className="calc-card-desc">
                    Targeted domain copywriting, localized translations, color theme generation, and SEO tags.
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

          {/* ── 4. On-Demand Gemini AI Token Packs (Top-Ups) ── */}
          <div className="token-packs-section">
            <div className="token-packs-header">
              <div className="pricing-pill-badge" style={{ margin: "0 auto 1rem auto" }}>
                <Coins className="w-3.5 h-3.5 text-[#dfb180]" />
                <span>Pay-As-You-Go Credits</span>
              </div>
              <h2 className="estimator-title" style={{ fontSize: "1.85rem" }}>
                Gemini AI Compute Token Packs
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
                Access all completed template transactions, recurring monthly hosting subscriptions, AI compute purchases, and official tax invoice receipts in one verified dashboard.
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
