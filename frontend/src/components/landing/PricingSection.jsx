"use client";

import { motion } from "framer-motion";
import { Check, Zap } from "lucide-react";
import Link from "@/components/Link";
import "./PricingSection.css";

const PLANS = [
  {
    name: "Community Edition",
    price: 0,
    description: "Everything you need to analyze, customize, and export website templates.",
    features: [
      "Browse professional frontend templates",
      "Unlimited ZIP uploads & automated code analysis",
      "Dynamic interactive live browser previews",
      "One-click direct source ZIP downloads",
      "Derive brand CSS templates & color schemes",
      "Lighthouse SEO and accessibility scanning",
      "100% free and open-source utility",
    ],
    cta: "Explore the Marketplace",
    href: "/marketplace",
    popular: true,
  },
];

export default function PricingSection() {
  return (
    <section id="pricing" className="section">
      <div className="container-xl">
        {/* Header */}
        <div className="section-header">
          <div className="section-badge">
            <Zap className="section-badge-icon" />
            100% Free Platform
          </div>
          <h2 className="section-title">
            No Fees. No Signups required to browse. <span className="gradient-text">Just Build.</span>
          </h2>
          <p className="section-subtitle">
            Site Studio is a free utility platform for frontend developers to analyze, live preview, and download templates.
          </p>
        </div>

        {/* Plans */}
        <div className="pricing-grid" style={{ gridTemplateColumns: "1fr", maxWidth: "600px", margin: "0 auto" }}>
          {PLANS.map((plan) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="pricing-card popular"
              style={{ padding: "3rem" }}
            >
              <div className="pricing-header">
                <h3>{plan.name}</h3>
                <p>{plan.description}</p>
              </div>

              <div className="pricing-price-wrapper">
                <span className="pricing-price" style={{ color: "var(--emerald-500)" }}>
                  $0
                </span>
                <span className="pricing-period">/ forever</span>
              </div>

              <ul className="pricing-features" style={{ gridTemplateColumns: "1fr 1fr", display: "grid", gap: "0.75rem", margin: "2rem 0" }}>
                {plan.features.map((feature) => (
                  <li key={feature} className="pricing-feature-item" style={{ margin: 0 }}>
                    <Check className="pricing-check-icon" />
                    <span className="text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <Link
                href={plan.href}
                className="pricing-cta popular"
              >
                {plan.cta}
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
