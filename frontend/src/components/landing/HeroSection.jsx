"use client";

/**
 * HeroSection — animated hero with gradient glow, typewriter, and CTAs (React JSX).
 */

import { useEffect, useState } from "react";
import Link from "@/components/Link";
import { motion } from "framer-motion";
import { ArrowRight, Play, Sparkles, Zap, Shield, Star } from "lucide-react";
import "./HeroSection.css";

const TYPEWRITER_WORDS = [
  "your next client",
  "a coffee shop",
  "a tech startup",
  "a medical clinic",
  "your portfolio",
  "an online store",
];

function Typewriter() {
  const [idx, setIdx] = useState(0);
  const [char, setChar] = useState(0);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const word = TYPEWRITER_WORDS[idx];
    const speed = deleting ? 40 : 80;

    const timeout = setTimeout(() => {
      if (!deleting && char < word.length) {
        setChar((c) => c + 1);
      } else if (!deleting && char === word.length) {
        setTimeout(() => setDeleting(true), 1800);
      } else if (deleting && char > 0) {
        setChar((c) => c - 1);
      } else {
        setDeleting(false);
        setIdx((i) => (i + 1) % TYPEWRITER_WORDS.length);
      }
    }, speed);

    return () => clearTimeout(timeout);
  }, [char, deleting, idx]);

  return (
    <span className="gradient-text">
      {TYPEWRITER_WORDS[idx].slice(0, char)}
      <span className="animate-pulse">|</span>
    </span>
  );
}

const STATS = [
  { label: "Templates", value: "500+" },
  { label: "Happy Customers", value: "12K+" },
  { label: "Live Customizable", value: "100%" },
  { label: "Average Rating", value: "4.9 ★" },
];

export default function HeroSection() {
  return (
    <section className="hero-section">
      {/* Background glow */}
      <div className="hero-glow-overlay" />
      <div className="hero-float-glow-1 animate-float" />
      <div className="hero-float-glow-2 animate-float" style={{ animationDelay: "2s" }} />

      {/* Grid pattern */}
      <div
        className="hero-grid-pattern"
        style={{
          backgroundImage: "radial-gradient(circle, hsla(213, 83%, 66%, 1.00) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      />

      <div className="hero-container">
        <div className="hero-content-wrapper">
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="hero-badge"
          >
            <Sparkles className="hero-badge-sparkle" />
            <span className="hero-badge-text">Powered by Next-Gen Dynamic Design Engines</span>
            <span className="hero-badge-new-tag">NEW</span>
          </motion.div>

          {/* Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="hero-title"
          >
            The curated template
            <br />
            marketplace for{" "}
            <Typewriter />
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="hero-subtitle"
          >
            Browse professional website templates. Preview with your own brand,
            let Instant Fill craft your content, and download instantly for free.
          </motion.p>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="hero-ctas"
          >
            <Link
              href="/marketplace"
              className="hero-cta-primary btn-glow"
            >
              Browse Templates
              <ArrowRight className="hero-cta-arrow" />
            </Link>
          </motion.div>

          {/* Trust badges */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="hero-trust-badges"
          >
            {[
              { icon: <Shield className="w-4 h-4 trust-shield-icon" />, text: "100% Free Tool" },
              { icon: <Zap className="w-4 h-4 trust-zap-icon" />, text: "Instant Download" },
              { icon: <Star className="w-4 h-4 trust-star-icon" />, text: "Unlimited Access" },
            ].map(({ icon, text }) => (
              <span key={text} className="hero-trust-item">
                {icon} {text}
              </span>
            ))}
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="hero-stats-grid"
          >
            {STATS.map(({ label, value }) => (
              <div
                key={label}
                className="hero-stat-card glass"
              >
                <div className="hero-stat-val gradient-text">{value}</div>
                <div className="hero-stat-lbl">{label}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
