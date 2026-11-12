"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Globe,
  Monitor,
  Cpu,
  Activity,
  Layers,
  ShieldCheck,
  CheckCircle2,
  Sparkles,
  Zap,
  Smartphone,
  ArrowRight,
  Info,
} from "lucide-react";

export default function TemplateArchitectureDiagram({ template }) {
  const [activeNode, setActiveNode] = useState(2); // Default to Source Architecture

  const pagesCount = template?.pages_count || (template?.included_pages?.length ?? 1);
  const frameworkName = template?.framework || "HTML5 / Vanilla CSS";
  const categoryName = template?.category?.name || template?.industry || "Website Template";

  const NODES = [
    {
      id: 0,
      title: "Client Reflow & Viewport",
      tag: "Device Adaptive",
      icon: Monitor,
      color: "#38bdf8",
      accentBg: "rgba(223, 177, 128, 0.12)",
      borderColor: "rgba(223, 177, 128, 0.35)",
      telemetry: "Reflow: 100% Responsive",
      metrics: [
        { label: "Target Viewports", val: "320px – 1920px" },
        { label: "Touch Targets", val: ">= 44px × 44px" },
        { label: "Horizontal Overflow", val: "0px (Zero overflow-x)" },
        { label: "Reflow Engine", val: "CSS clamp() + Fluid Grids" },
      ],
      description: "Client devices dynamically adapt across Desktop, Tablet, and Mobile with fluid typography and hardware-accelerated drawer menus.",
    },
    {
      id: 1,
      title: "Atomic Edge CDN & Routing",
      tag: "Edge Infrastructure",
      icon: Globe,
      color: "#dfb180",
      accentBg: "rgba(129, 140, 248, 0.12)",
      borderColor: "rgba(129, 140, 248, 0.35)",
      telemetry: "Latency: < 12ms Edge Response",
      metrics: [
        { label: "DNS Propagation", val: "Instant Subdomain / CNAME" },
        { label: "Security & TLS", val: "TLS 1.3 / HSTS Enforced" },
        { label: "Compression", val: "Brotli + Gzip Stream" },
        { label: "Global Edge Nodes", val: "Multi-region CDN" },
      ],
      description: "Sub-millisecond static asset delivery and edge caching ensure high Google Lighthouse performance scores worldwide.",
    },
    {
      id: 2,
      title: "Physical Source Bundle",
      tag: "Production Codebase",
      icon: Layers,
      color: "#c89666",
      accentBg: "rgba(200, 150, 102, 0.15)",
      borderColor: "rgba(200, 150, 102, 0.45)",
      telemetry: `Files: ${pagesCount} Pages Verified`,
      metrics: [
        { label: "Architecture", val: frameworkName },
        { label: "Category", val: categoryName },
        { label: "Pages Physical Count", val: `${pagesCount} Verified Pages` },
        { label: "Package Structure", val: "Clean Frontend ZIP" },
      ],
      description: "100% physical code delivery with zero broken links. Every page shown in navigation physically exists with complete content.",
    },
    {
      id: 3,
      title: "Gemini AI Fill Engine",
      tag: "Semantic Personalization",
      icon: Sparkles,
      color: "#c084fc",
      accentBg: "rgba(223, 177, 128, 0.12)",
      borderColor: "rgba(223, 177, 128, 0.35)",
      telemetry: "Model: Gemini 1.5 Flash",
      metrics: [
        { label: "AI Copy Generation", val: "1 Credit / Section" },
        { label: "Color Palette Harmonizer", val: "Active" },
        { label: "SEO Meta Derivation", val: "Domain-Specific" },
        { label: "Contextual Refinement", val: "Zero Hallucination" },
      ],
      description: "Live canvas personalization allows real-time rewriting of hero copy, value propositions, and branding without editing code manually.",
    },
    {
      id: 4,
      title: "AI Site Doctor Self-Healing",
      tag: "Runtime Health Audit",
      icon: Activity,
      color: "#34d399",
      accentBg: "rgba(52, 211, 153, 0.12)",
      borderColor: "rgba(52, 211, 153, 0.35)",
      telemetry: "Status: 100% Healthy",
      metrics: [
        { label: "Error Detection", val: "Real-time Telemetry" },
        { label: "Image 404 Recovery", val: "Autonomous Repair" },
        { label: "Link Validation", val: "Relative Path Audit" },
        { label: "Healing Cost", val: "1 Credit / Repair" },
      ],
      description: "Autonomous background watcher monitors site requests and automatically heals missing assets or broken anchors before visitors notice.",
    },
  ];

  const current = NODES[activeNode] || NODES[2];

  return (
    <div className="architecture-diagram-container">
      {/* Header */}
      <div className="architecture-header">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-[#c89666]/15 border border-[#c89666]/30 text-[#dfb180]">
            <Zap className="w-4 h-4" />
          </div>
          <h3 className="section-title" style={{ margin: 0 }}>
            Live Architecture & Request Flow Lifecycle
          </h3>
        </div>
        <span className="text-xs text-[#dfb180] font-mono bg-[#c89666]/15 px-2.5 py-1 rounded-full border border-[#c89666]/30">
          Interactive Pipeline Map
        </span>
      </div>

      <p className="text-xs text-muted-foreground mb-6 leading-relaxed">
        Trace how this website template executes from visitor client reflow through the Studio Edge CDN, physical source bundle, Gemini AI Fill engine, and autonomous error healing.
      </p>

      {/* Animated Flow Nodes Ribbon */}
      <div className="architecture-flow-ribbon">
        {NODES.map((node, idx) => {
          const IconComponent = node.icon;
          const isSelected = activeNode === node.id;
          return (
            <div key={node.id} className="architecture-node-wrapper">
              <button
                type="button"
                onClick={() => setActiveNode(node.id)}
                className={`architecture-node-card ${isSelected ? "active" : ""}`}
                style={{
                  borderColor: isSelected ? node.borderColor : "rgba(255, 255, 255, 0.08)",
                  background: isSelected ? node.accentBg : "rgba(18, 18, 22, 0.65)",
                }}
              >
                <div
                  className="architecture-node-icon-box"
                  style={{ color: node.color, background: "rgba(0, 0, 0, 0.4)" }}
                >
                  <IconComponent className="w-4 h-4" />
                </div>
                <div className="text-left min-w-0">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider block" style={{ color: node.color }}>
                    {node.tag}
                  </span>
                  <h5 className="text-xs font-bold text-white truncate max-w-[130px]">
                    {node.title}
                  </h5>
                </div>
              </button>

              {/* Connecting Connector Arrow (except last) */}
              {idx < NODES.length - 1 && (
                <div className="architecture-connector">
                  <div className="architecture-pulse-line">
                    <span className="architecture-pulse-dot" style={{ background: node.color }} />
                  </div>
                  <ArrowRight className="w-3 h-3 text-muted-foreground/60 shrink-0" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Selected Node Deep Dive Telemetry Box */}
      <motion.div
        key={current.id}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="architecture-detail-box"
        style={{ borderColor: current.borderColor, background: "rgba(11, 15, 30, 0.9)" }}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl" style={{ background: current.accentBg, color: current.color }}>
              <current.icon className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                <span>{current.title}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full uppercase" style={{ background: current.accentBg, color: current.color }}>
                  {current.telemetry}
                </span>
              </h4>
              <p className="text-xs text-muted-foreground mt-0.5">{current.description}</p>
            </div>
          </div>
        </div>

        {/* 4 Telemetry Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3">
          {current.metrics.map((m, i) => (
            <div key={i} className="p-2.5 rounded-lg bg-black/40 border border-white/5">
              <span className="text-[10px] uppercase font-bold text-muted-foreground block">
                {m.label}
              </span>
              <span className="text-xs font-bold text-white font-mono mt-0.5 block truncate" style={{ color: current.color }}>
                {m.val}
              </span>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

