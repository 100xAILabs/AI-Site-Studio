"use client";

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check,
  Coins,
  Sparkles,
  ArrowRight,
  ChevronDown,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { PLANS_LIST } from "@/lib/plans";
import "./Page.css";

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
    q: "Can I sell and retail the websites I generate?",
    a: "Yes! Subscribers on the Extreme Plan ($50/mo) receive an exclusive Marketplace Retailer License. You can list your AI-generated websites directly on the Site Studio global marketplace, set your custom retail price in USD, and receive creator payouts for every sale.",
  },
  {
    q: "What payment gateways are supported?",
    a: "We support Stripe (international credit/debit cards, Apple Pay, Google Pay) and Razorpay (cards, UPI, NetBanking). All subscription cycles, invoices, and credit balances are updated automatically via secure webhooks.",
  },
];

export default function PricingPage() {
  const navigate = useNavigate();

  const [billingCycle, setBillingCycle] = useState("annual"); // "monthly" | "annual"
  const [openFaq, setOpenFaq] = useState(0);

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
              <span>Clear, flexible pricing</span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.08 }}
              className="pricing-hero-title"
            >
              The right plan for <br />
              <span className="gradient-text">every stage of your studio</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.16 }}
              className="pricing-hero-sub"
            >
              Start free, then upgrade when you need more AI credits, hosted sites, and hands-off maintenance.
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

          {/* ── FAQ ── */}
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
