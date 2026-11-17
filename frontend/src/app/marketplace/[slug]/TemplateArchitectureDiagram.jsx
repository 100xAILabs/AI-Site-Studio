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
      color: "#0ea5e9",
      accentBg: "rgba(14, 165, 233, 0.12)",
      borderColor: "rgba(14, 165, 233, 0.35)",
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
      color: "#f59e0b",
      accentBg: "rgba(245, 158, 11, 0.12)",
      borderColor: "rgba(245, 158, 11, 0.35)",
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
      title: "Smart Fill Automation Engine",
      tag: "Semantic Personalization",
      icon: Sparkles,
      color: "#a855f7",
      accentBg: "rgba(168, 85, 247, 0.12)",
      borderColor: "rgba(168, 85, 247, 0.35)",
      telemetry: "Engine: Real-Time Synthesis",
      metrics: [
        { label: "Copy Generation", val: "1 Credit / Section" },
        { label: "Color Palette Harmonizer", val: "Active" },
        { label: "SEO Meta Derivation", val: "Domain-Specific" },
        { label: "Contextual Refinement", val: "Precision Mode" },
      ],
      description: "Live canvas personalization allows real-time rewriting of hero copy, value propositions, and branding without editing code manually.",
    },
    {
      id: 4,
      title: "Autonomous Site Self-Healing",
      tag: "Runtime Health Audit",
      icon: Activity,
      color: "#10b981",
      accentBg: "rgba(16, 185, 129, 0.12)",
      borderColor: "rgba(16, 185, 129, 0.35)",
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
          <div className="p-1.5 rounded-lg border flex items-center justify-center shrink-0" style={{ background: 'hsla(var(--primary) / 0.12)', borderColor: 'hsla(var(--primary) / 0.25)', color: 'hsl(var(--primary))' }}>
            <Zap className="w-4 h-4" />
          </div>
          <h3 className="section-title text-foreground" style={{ margin: 0 }}>
            Live Architecture & Request Flow Lifecycle
          </h3>
        </div>
        <span className="text-xs font-mono px-2.5 py-1 rounded-full border font-bold" style={{ background: 'hsla(var(--primary) / 0.12)', borderColor: 'hsla(var(--primary) / 0.25)', color: 'hsl(var(--primary))' }}>
          Interactive Pipeline Map
        </span>
      </div>

      <p className="text-xs text-muted-foreground mb-6 leading-relaxed">
        Trace how this website template executes from visitor client reflow through the Studio Edge CDN, physical source bundle, automated Smart Fill engine, and autonomous error healing.
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
                  borderColor: isSelected ? node.color : undefined,
                  boxShadow: isSelected ? `0 4px 16px ${node.color}33` : undefined,
                }}
              >
                <div
                  className="architecture-node-icon-box"
                  style={{
                    color: node.color,
                    background: isSelected ? `${node.color}15` : undefined,
                    borderColor: isSelected ? `${node.color}40` : undefined,
                  }}
                >
                  <IconComponent className="w-4 h-4" />
                </div>
                <div className="text-left min-w-0">
                  <span className="architecture-node-tag" style={{ color: node.color }}>
                    {node.tag}
                  </span>
                  <h5 className="architecture-node-title truncate max-w-[130px]">
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
        style={{ borderColor: `${current.color}60` }}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div
              className="p-2.5 rounded-xl border shrink-0"
              style={{
                color: current.color,
                background: `${current.color}18`,
                borderColor: `${current.color}40`,
              }}
            >
              <current.icon className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-foreground flex items-center gap-2 flex-wrap">
                <span>{current.title}</span>
                <span
                  className="architecture-detail-telemetry"
                  style={{
                    color: current.color,
                    background: `${current.color}15`,
                    borderColor: `${current.color}35`,
                  }}
                >
                  {current.telemetry}
                </span>
              </h4>
              <p className="architecture-detail-desc">{current.description}</p>
            </div>
          </div>
        </div>

        {/* 4 Telemetry Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3">
          {current.metrics.map((m, i) => (
            <div key={i} className="architecture-metric-card">
              <span className="architecture-metric-label">
                {m.label}
              </span>
              <span className="architecture-metric-val">
                {m.val}
              </span>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

