"use client";

/**
 * HowItWorksSection — replaces fake testimonials with a concrete 3-step process.
 */

import { motion } from "framer-motion";
import { Workflow } from "lucide-react";
import "./TestimonialsSection.css";

const STEPS = [
  {
    step: "01",
    title: "Browse the Marketplace",
    description:
      "Use natural-language semantic search to find templates that match your business type, industry, or visual style. No endless category filtering.",
  },
  {
    step: "02",
    title: "Preview With Your Brand",
    description:
      "Open any template in the live canvas. Paste your logo, pick brand colors, and run Instant Fill to generate realistic copy tailored to your business.",
  },
  {
    step: "03",
    title: "Download and Deploy",
    description:
      "Download the generated source as a ZIP, or publish it through a Vercel provider configured by your site administrator.",
  },
];

export default function HowItWorksSection() {
  return (
    <section className="section how-it-works-section">
      <div className="container-xl">
        <div className="section-header">
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4 }}
            className="section-badge"
          >
            <Workflow className="section-badge-icon" />
            Seamless 3-Step Flow
          </motion.div>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.08 }}
            className="section-title"
          >
            How Site Studio <span className="gradient-text">works.</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.16 }}
            className="section-subtitle"
          >
            Three straightforward steps from discovery to a live website.
          </motion.p>
        </div>

        <div className="how-it-works-grid">
          {STEPS.map((s, idx) => (
            <motion.div
              key={s.step}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: idx * 0.1 }}
              whileHover={{ y: -6, transition: { duration: 0.2 } }}
              className="how-step-card"
            >
              <div className="how-step-card-glow" />
              <div className="how-step-number">{s.step}</div>
              <h3 className="how-step-title">{s.title}</h3>
              <p className="how-step-desc">{s.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
