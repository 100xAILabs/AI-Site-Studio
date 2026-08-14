"use client";

import { motion } from "framer-motion";
import {
  Brain, Search, Palette, Globe, Shield, Zap, MessageSquare,
} from "lucide-react";
import "./FeaturesSection.css";

const FEATURES = [
  {
    icon: Brain,
    title: "Instant Content Generator",
    description: "Describe your business and let our studio engine craft all your website copy — headlines, about us, services, and more.",
    gradient: "linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)",
  },
  {
    icon: Search,
    title: "Semantic Search",
    description: 'Search naturally: "I need a website for a coffee shop" returns the most relevant templates automatically.',
    gradient: "linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)",
  },
  {
    icon: Palette,
    title: "Dynamic Palette Engine",
    description: "Tell us your brand mood and industry to generate a harmonic color palette for your business.",
    gradient: "linear-gradient(135deg, #ec4899 0%, #f43f5e 100%)",
  },
  {
    icon: Globe,
    title: "Live Preview",
    description: "Preview any template customized with your actual logo, colors, and content — before you buy.",
    gradient: "linear-gradient(135deg, #14b8a6 0%, #22c55e 100%)",
  },
  {
    icon: Zap,
    title: "One-Click Deployments",
    description: "Export clean React or HTML source code, or deploy directly to Vercel, Netlify, and GitHub Pages in seconds.",
    gradient: "linear-gradient(135deg, #d946ef 0%, #ec4899 100%)",
  },
  {
    icon: Shield,
    title: "Accessibility Audit",
    description: "Automated auditing scans your template for WCAG compliance and suggests improvements for better accessibility.",
    gradient: "linear-gradient(135deg, #10b981 0%, #14b8a6 100%)",
  }
];

export default function FeaturesSection() {
  return (
    <section id="features" className="section">
      <div className="container-xl">
        {/* Header */}
        <div className="section-header">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="section-badge"
          >
            <Zap className="section-badge-icon" />
            Studio Platform Features
          </motion.div>
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="section-title"
          >
            Everything you need to{" "}
            <span className="gradient-text">launch faster</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="section-subtitle"
          >
            Site Studio is not just a template marketplace — it's a complete
            modern website launch platform.
          </motion.p>
        </div>

        {/* Feature grid */}
        <div className="features-grid">
          {FEATURES.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.05 }}
                className="feature-card"
              >
                <div
                  className="feature-icon-wrapper"
                  style={{ background: feature.gradient }}
                >
                  <Icon className="feature-icon" />
                </div>
                <h3 className="feature-title">
                  {feature.title}
                </h3>
                <p className="feature-desc">
                  {feature.description}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
