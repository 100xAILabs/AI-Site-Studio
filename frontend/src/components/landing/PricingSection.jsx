"use client";

import { motion } from "framer-motion";
import { Check, Zap, Sparkles, ArrowRight } from "lucide-react";
import Link from "@/components/Link";
import { PLANS_LIST } from "@/lib/plans";
import "./PricingSection.css";

export default function PricingSection() {
  return (
    <section id="pricing" className="section pricing-section-wrap">
      <div className="container-xl">
        {/* Header */}
        <div className="section-header">
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4 }}
            className="section-badge"
          >
            <Sparkles className="section-badge-icon" />
            Transparent Studio Pricing
          </motion.div>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.08 }}
            className="section-title"
          >
            Predictable Plans for <span className="gradient-text">Developers &amp; Studios.</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.16 }}
            className="section-subtitle"
          >
            Test full generation free, deploy live websites with custom domains, and let autonomous Auto-Heal protect your sites.
          </motion.p>
        </div>

        {/* 3-Tier Plans Grid */}
        <div className="pricing-grid">
          {PLANS_LIST.map((plan) => (
            <motion.div
              key={plan.id}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className={`pricing-card ${plan.popular ? "popular" : ""}`}
            >
              {plan.popular && (
                <div className="popular-badge-wrapper">
                  <span className="popular-badge">✦ Recommended for Most Studios</span>
                </div>
              )}

              <div className="pricing-header">
                <h3>{plan.name}</h3>
                <p>{plan.description}</p>
              </div>

              <div className="pricing-price-wrapper">
                <span className="pricing-price">
                  ${plan.monthlyPrice}
                </span>
                <span className="pricing-period">
                  {plan.monthlyPrice === 0 ? " / forever" : " / month"}
                </span>
              </div>
              {plan.annualPrice > 0 && (
                <div className="text-xs text-muted-foreground mt-1 mb-4">
                  ${plan.annualPrice}/yr billed annually (2 months free)
                </div>
              )}

              <ul className="pricing-features-grid mt-4">
                {plan.features.slice(0, 5).map((feature, fIdx) => (
                  <li key={fIdx} className="pricing-feature-item">
                    <Check className="pricing-check-icon" />
                    <span className="text-sm">{feature.text}</span>
                  </li>
                ))}
              </ul>

              <Link
                href={plan.href}
                className={`pricing-cta ${plan.popular ? "popular" : ""}`}
              >
                {plan.cta} <ArrowRight className="w-4 h-4 ml-1.5 inline" />
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
