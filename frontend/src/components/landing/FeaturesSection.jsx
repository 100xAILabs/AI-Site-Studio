"use client";

import { motion } from "framer-motion";
import {
  Brain, Search, Palette, Globe, Shield, Zap, Sparkles,
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
    title: "Export and Deploy",
    description: "Download your generated source as a ZIP, or deploy it through a Vercel provider configured by your site administrator.",
    gradient: "linear-gradient(135deg, #d946ef 0%, #ec4899 100%)",
  },
  {
    icon: Shield,
    title: "Accessible Source",
    description: "Export the source code and review or adapt it against your own accessibility requirements.",
    gradient: "linear-gradient(135deg, #10b981 0%, #14b8a6 100%)",
  }
];

export default function FeaturesSection() {
  return (
    <section id="features" className="section features-section">
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
            Core Platform Engine
          </motion.div>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.08 }}
            className="section-title"
          >
            Platform <span className="gradient-text">Features.</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.16 }}
            className="section-subtitle"
          >
            A complete toolset for finding, customising, and deploying professional website templates — without extra subscriptions or locked features.
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
