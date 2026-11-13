"use client";

import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Link from "@/components/Link";
import { useAuthStore } from "@/store/authStore";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  Play,
  Sparkles,
  Zap,
  LayoutGrid,
  ShoppingBag,
  Sliders,
  CloudUpload,
  RotateCcw,
  X,
} from "lucide-react";
import {
  GoogleLogo,
  MicrosoftLogo,
  MetaLogo,
  NotionLogo,
  FigmaLogo,
} from "./StudioBrandLogos";
import "./HeroSection.css";

// 4 high quality creator avatars
const AVATARS = [
  "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80",
  "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=120&q=80",
  "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=120&q=80",
  "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=120&q=80",
];

// 5 studio features revealed step-by-step with interactive arrows
const STUDIO_CARD_FEATURES = [
  {
    id: "sell",
    stepNum: "01",
    arrowLabel: "Sell",
    title: "Sell your website",
    subtitle: "Turn your built templates into recurring creator revenue.",
    description:
      "Upload complete websites, landing pages, or UI component packages. Set your own pricing, reach thousands of global developers, and get paid directly with secure automated Stripe payouts.",
    points: [
      "Instant seller verification & creator dashboard",
      "Keep up to 90% of every sale with direct payouts",
      "Automated license generation and zip delivery",
    ],
    ctaText: "Start Selling Templates",
    ctaLink: "/marketplace",
    icon: ShoppingBag,
    badge: "Creator Payouts",
    accent: "#c084fc",
    glow: "rgba(223, 177, 128, 0.35)",
    bgGradient: "rgba(223, 177, 128, 0.12)",
    borderGradient: "rgba(223, 177, 128, 0.45)",
  },
  {
    id: "create",
    stepNum: "02",
    arrowLabel: "Create",
    title: "Create your own website as you thought",
    subtitle: "Natural language prompt-to-site automated synthesis engine.",
    description:
      "Describe your dream business in plain words. Our studio automation generates custom layouts, high-conversion marketing copy, responsive sections, and harmonic color schemes tailored to your vision.",
    points: [
      "Smart semantic prompt matching & instant generation",
      "Dynamic copywriting tailored to your exact industry",
      "Harmonic mood palettes generated on the fly",
    ],
    ctaText: "Build Your Website Automatically",
    ctaLink: "/get-started",
    icon: Sparkles,
    badge: "Studio Builder",
    accent: "#f472b6",
    glow: "rgba(244, 114, 182, 0.35)",
    bgGradient: "rgba(244, 114, 182, 0.12)",
    borderGradient: "rgba(244, 114, 182, 0.45)",
  },
  {
    id: "buy",
    stepNum: "03",
    arrowLabel: "Buy",
    title: "Buy high quality websites",
    subtitle: "Production-ready, developer-audited templates with full code.",
    description:
      "Explore 100+ vetted templates built with React, Vite, and Tailwind CSS. Every template comes with complete unminified source code, zero placeholder dead-ends, and 100% mobile responsiveness.",
    points: [
      "Zero missing pages & 100% working relative links",
      "Standalone REST APIs (FastAPI, Express) included",
      "Commercial license with free lifetime updates",
    ],
    ctaText: "Explore Marketplace",
    ctaLink: "/marketplace",
    icon: LayoutGrid,
    badge: "Curated Store",
    accent: "#38bdf8",
    glow: "rgba(223, 177, 128, 0.35)",
    bgGradient: "rgba(223, 177, 128, 0.12)",
    borderGradient: "rgba(223, 177, 128, 0.45)",
  },
  {
    id: "deploy",
    stepNum: "04",
    arrowLabel: "Deploy",
    title: "Deploy instantly",
    subtitle: "1-Click edge hosting with custom domains & global CDN.",
    description:
      "Launch your website live to the world in seconds. Automatic worldwide CDN caching, SSL certificates, continuous deployment, and instant custom domain setup with zero server management.",
    points: [
      "Global sub-second edge distribution network",
      "Automatic SSL certificate provisioning & renewal",
      "Zero-config continuous git and zip deployment",
    ],
    ctaText: "See Deployment Options",
    ctaLink: "/get-started",
    icon: CloudUpload,
    badge: "Instant Cloud",
    accent: "#34d399",
    glow: "rgba(52, 211, 153, 0.35)",
    bgGradient: "rgba(52, 211, 153, 0.12)",
    borderGradient: "rgba(52, 211, 153, 0.45)",
  },
  {
    id: "edit",
    stepNum: "05",
    arrowLabel: "Edit",
    title: "Edit & customize live",
    subtitle: "Interactive visual live canvas studio with hot reload.",
    description:
      "Personalize every detail visually with zero code. Swap colors, rewrite headlines with Smart Fill automation, swap photos, adjust typography, and see your live changes reflected instantly inside our sandboxed canvas.",
    points: [
      "Real-time interactive canvas with instant hot reload",
      "Smart Fill: 1-click rebrand with your company info",
      "Live mobile, tablet, and desktop preview simulator",
    ],
    ctaText: "Open Studio Canvas",
    ctaLink: "/marketplace",
    icon: Sliders,
    badge: "Visual Canvas",
    accent: "#fb923c",
    glow: "rgba(251, 146, 60, 0.35)",
    bgGradient: "rgba(251, 146, 60, 0.12)",
    borderGradient: "rgba(251, 146, 60, 0.45)",
  },
];

// 5 core highlight features in the horizontal bar
const FEATURE_BAR_ITEMS = [
  {
    icon: Zap,
    title: "Automated Studio Builder",
    desc: "Turn ideas into production websites with intelligent automation.",
  },
  {
    icon: LayoutGrid,
    title: "Premium Templates",
    desc: "100+ stunning templates for every niche.",
  },
  {
    icon: ShoppingBag,
    title: "Marketplace",
    desc: "Buy & Sell templates, components and more.",
  },
  {
    icon: Sliders,
    title: "Advanced Customization",
    desc: "Total control with zero coding required.",
  },
  {
    icon: CloudUpload,
    title: "One-Click Publishing",
    desc: "Go live instantly with reliable hosting.",
  },
];

export default function HeroSection() {
  const navigate = useNavigate();
  const signOut = useAuthStore((s) => s.signOut);

  const handleSellTemplateClick = (e) => {
    if (e) e.preventDefault();
    signOut();
    navigate("/sign-in?role=seller&from=/dashboard");
  };

  const [isFlipped, setIsFlipped] = useState(false);
  // visibleCount tracks how many feature CTA buttons have been revealed (0–5)
  const [visibleCount, setVisibleCount] = useState(0);
  // shootIdx holds the index of the arrow currently shooting (-1 = none)
  const [shootIdx, setShootIdx] = useState(-1);
  const autoRef = useRef(null);

  // When card flips to back, start the sequential reveal from scratch
  useEffect(() => {
    if (isFlipped) {
      setVisibleCount(0);
      setShootIdx(-1);
      runSequence(0);
    } else {
      clearTimeout(autoRef.current);
      setVisibleCount(0);
      setShootIdx(-1);
    }
    return () => clearTimeout(autoRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFlipped]);

  // Reveal feature at `idx` by shooting an arrow then showing the button
  const runSequence = (idx) => {
    if (idx >= STUDIO_CARD_FEATURES.length) return;
    // 1. Shoot arrow for this index
    setShootIdx(idx);
    // 2. After arrow finishes (400ms), reveal the button
    autoRef.current = setTimeout(() => {
      setVisibleCount(idx + 1);
      setShootIdx(-1);
      // 3. After a brief pause, trigger the next arrow
      autoRef.current = setTimeout(() => {
        runSequence(idx + 1);
      }, 320);
    }, 420);
  };

  const handleCardClick = () => {
    setIsFlipped((prev) => !prev);
  };

  return (
    <section className="studio-hero-section">
      {/* Ambient Radial Nebula Background Glows */}
      <div className="hero-nebula-glow hero-nebula-right" />
      <div className="hero-nebula-glow hero-nebula-left" />

      <div className="hero-main-container">
        {/* Top Hero Row: Left Headlines/CTAs & Right 3D Rotating Card */}
        <div className="hero-split-grid hero-grid-card-right">
          {/* LEFT COLUMN: Headlines, CTAs, Social Proof */}
          <div className="hero-text-column">
            {/* Pill Badge */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="hero-pill-badge"
            >
              <span className="badge-sparkle-dot">✦</span>
              <span className="badge-text">Build • Customize • Launch</span>
            </motion.div>

            {/* Main Headline */}
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.08 }}
              className="hero-main-title"
            >
              <div className="title-white">Your Vision.</div>
              <div className="title-purple-gradient">Our Studio.</div>
            </motion.h1>

            {/* Subtitle */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.16 }}
              className="hero-main-subtitle"
            >
              Create stunning websites, landing pages and more with Site Studio —
              the next-generation website builder for everyone.
            </motion.p>

            {/* Action Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.24 }}
              className="hero-cta-group"
            >
              <Link href="/marketplace" className="hero-btn-primary">
                <span>Let's Build Your Website</span>
                <ArrowRight className="w-4 h-4 hero-btn-arrow" />
              </Link>

              <button
                type="button"
                onClick={handleSellTemplateClick}
                className="hero-btn-seller"
                title="Go to Seller Login & Portal"
              >
                <ShoppingBag className="w-4 h-4 text-[#dfb180]" />
                <span>Sell Your Template</span>
                <ArrowRight className="w-3.5 h-3.5 hero-btn-seller-arrow" />
              </button>
            </motion.div>

          </div>

          {/* RIGHT COLUMN: 3D Interactive Rotating Studio Card with Arrow Stepper */}
          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 24 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.65, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
            className="hero-card-column hero-card-on-right"
          >
            {/* Glowing Backdrop behind card */}
            <div className="mockup-glow-orb" />

            {/* 3D Perspective Stage */}
            <div className="studio-card-perspective-stage">
              {/* Clickable 3D Flip Card */}
              <motion.div
                className={`studio-3d-flip-card ${isFlipped ? "is-flipped" : ""}`}
                animate={{
                  rotateY: isFlipped ? 180 : 0,
                  rotateX: isFlipped ? 2 : 3.5,
                }}
                transition={{
                  duration: 0.75,
                  ease: [0.16, 1, 0.3, 1],
                }}
                onClick={handleCardClick}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleCardClick();
                  }
                }}
                aria-label={isFlipped ? "Flip back to preview image" : "Flip card to view studio features"}
              >
                {/* FRONT FACE: Surprise Mystery Canvas */}
                <div className="card-face card-face-front">
                  <div className="front-image-wrap">
                    <img
                      src="/landing/Hero.png"
                      alt="Site Studio Canvas"
                      className="canvas-clean-photo"
                      loading="lazy"
                    />

                    {/* Vignette border glow */}
                    <div className="front-glow-vignette" />

                    {/* Bottom gradient fade so badge reads clearly over the photo */}
                    <div className="front-bottom-fade" />

                    {/* Surprise badge — pinned to bottom of card */}
                    <div className="surprise-bottom-badge">
                      {/* Pulsing click ring */}
                      <motion.div
                        className="surprise-click-ring"
                        animate={{ scale: [1, 1.6, 1], opacity: [0.6, 0, 0.6] }}
                        transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
                      />
                      <div className="surprise-click-dot" />

                      {/* Gift emoji */}
                      <motion.span
                        className="surprise-gift-sm"
                        animate={{ rotate: [0, -6, 6, -3, 3, 0] }}
                        transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut", repeatDelay: 1 }}
                      >
                        {'🎁'}
                      </motion.span>

                      {/* Text */}
                      <div className="surprise-badge-text">
                        <span className="surprise-badge-title">Click to see a Surprise</span>
                        <span className="surprise-badge-sub">Something special awaits you</span>
                      </div>


                    </div>

                    {/* Floating sparkles (top area, so image is still visible) */}
                    <div className="surprise-sparkle surprise-sparkle-1">+</div>
                    <div className="surprise-sparkle surprise-sparkle-2">*</div>
                    <div className="surprise-sparkle surprise-sparkle-3">+</div>
                  </div>
                </div>

                {/* BACK FACE: Sequential Arrow-Shot Feature CTA Links */}
                <div className="card-face card-face-back">
                  <div className="back-features-container">
                    {/* Header */}
                    <div className="back-card-header">
                      <div className="back-header-brand">
                        <span className="back-header-star">✦</span>
                        <span className="back-header-title">What you can do</span>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setIsFlipped(false);
                        }}
                        className="back-rotate-btn"
                        title="Rotate back to preview"
                      >
                        <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                        <span>Flip back</span>
                      </button>
                    </div>

                    {/* Feature CTA list — each revealed by a shooting arrow */}
                    <div className="feat-cta-list" onClick={(e) => e.stopPropagation()}>
                      {STUDIO_CARD_FEATURES.map((feat, idx) => {
                        const isRevealed = idx < visibleCount;
                        const isShooting = shootIdx === idx;

                        return (
                          <div key={feat.id} className="feat-cta-row">
                            {/* Shooting arrow beam */}
                            <AnimatePresence>
                              {isShooting && (
                                <motion.div
                                  className="feat-row-shoot-beam"
                                  style={{
                                    background: `linear-gradient(90deg, transparent 0%, ${feat.accent} 55%, ${feat.accent}bb 85%, transparent 100%)`,
                                    boxShadow: `0 0 14px 3px ${feat.glow}`,
                                  }}
                                  initial={{ x: "-60px", scaleX: 0.2, opacity: 0 }}
                                  animate={{ x: "110%", scaleX: 1, opacity: [0, 1, 1, 0] }}
                                  exit={{ opacity: 0 }}
                                  transition={{ duration: 0.38, ease: [0.2, 0.9, 0.4, 1] }}
                                >
                                  <span
                                    className="feat-beam-tip"
                                    style={{ color: feat.accent, textShadow: `0 0 8px ${feat.glow}` }}
                                  >
                                    ➔
                                  </span>
                                </motion.div>
                              )}
                            </AnimatePresence>

                            {/* CTA link — slides in after arrow passes */}
                            <AnimatePresence>
                              {isRevealed && (
                                <motion.div
                                  className="feat-cta-motion-wrap"
                                  initial={{ opacity: 0, x: 32, scale: 0.92 }}
                                  animate={{ opacity: 1, x: 0, scale: 1 }}
                                  transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
                                >
                                  <Link
                                    href={feat.ctaLink}
                                    className="feat-cta-link-btn"
                                    onClick={(e) => {
                                      if (feat.id === "sell") {
                                        handleSellTemplateClick(e);
                                      }
                                    }}
                                  >
                                    {/* Arrow LEFT of label */}
                                    <ArrowRight
                                      className="feat-cta-arrow-left"
                                      style={{ color: feat.accent }}
                                    />
                                    {/* High-Contrast Bold Feature Label */}
                                    <span className="feat-cta-label">
                                      {feat.arrowLabel}
                                    </span>
                                  </Link>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          </motion.div>
        </div>

        {/* Horizontal 5-Column Feature Bar */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.55, delay: 0.2 }}
          className="studio-feature-strip"
        >
          {FEATURE_BAR_ITEMS.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div key={idx} className="feature-strip-column">
                <div className="feature-strip-icon-box">
                  <Icon className="feature-strip-icon" />
                </div>
                <div className="feature-strip-info">
                  <h3 className="feature-strip-title">{item.title}</h3>
                  <p className="feature-strip-desc">{item.desc}</p>
                </div>
              </div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
