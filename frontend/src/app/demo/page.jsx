"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import Link from "@/components/Link";
import {
  ArrowLeft, Monitor, Tablet, Smartphone, RefreshCw,
  ExternalLink, Zap, Check, ShoppingCart, Sparkles, ShieldCheck
} from "lucide-react";
import { useTemplate } from "@/hooks/useTemplates";
import { API_URL } from "@/lib/api";
import { cn, formatPrice } from "@/lib/utils";
import { useCartStore } from "@/store";
import "./Page.css";

export default function LiveDemoPage() {
  const { slug: routeSlug } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const targetIdentifier = routeSlug || searchParams.get("template") || searchParams.get("slug") || "";
  const { data: template, isLoading: isTemplateLoading } = useTemplate(targetIdentifier);

  const [device, setDevice] = useState("desktop"); // "desktop" | "tablet" | "mobile"
  const [iframeKey, setIframeKey] = useState(0);
  const [isIframeLoading, setIsIframeLoading] = useState(true);

  const items = useCartStore((s) => s.items) || [];
  const addItem = useCartStore((s) => s.addItem);

  const templateId = template?.id || targetIdentifier;
  const isInCart = items.some((item) => (item.id === templateId || item.template_id === templateId));

  const previewUrl = targetIdentifier
    ? `${API_URL}/preview/live/${targetIdentifier}/`
    : "";

  const handleRefresh = () => {
    setIsIframeLoading(true);
    setIframeKey((prev) => prev + 1);
  };

  const handleBuyNow = () => {
    if (template) {
      if (addItem) {
        addItem({
          id: template.id,
          title: template.title,
          price: template.price,
          thumbnail_url: template.thumbnail_url,
          category: template.category,
        });
      }
      navigate("/checkout");
    } else {
      navigate(`/marketplace/${targetIdentifier}`);
    }
  };

  return (
    <div className="demo-showcase-container">
      {/* ── Top Navigation Bar ────────────────────────────────────────── */}
      <header className="demo-topbar">
        {/* Left: Back & Title */}
        <div className="demo-topbar-left">
          <Link
            href={targetIdentifier ? `/marketplace/${targetIdentifier}` : "/marketplace"}
            className="demo-back-btn"
            title="Return to Template Details"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="demo-back-label">Back to Details</span>
          </Link>

          <div className="demo-brand-separator" />

          <div className="demo-title-group">
            <span className="demo-template-title">
              {template?.title || targetIdentifier || "Live Template Demo"}
            </span>
            <span className="demo-badge-live">Live Demo</span>
            {template?.framework && (
              <span className="demo-badge-framework">{template.framework}</span>
            )}
          </div>
        </div>

        {/* Center: Device Viewport Switcher */}
        <div className="demo-topbar-center">
          <div className="demo-device-tabs">
            <button
              type="button"
              onClick={() => setDevice("desktop")}
              className={cn("demo-device-btn", device === "desktop" && "active")}
              title="Desktop View (100% Fullscreen)"
            >
              <Monitor className="w-4 h-4" />
              <span>Desktop</span>
            </button>
            <button
              type="button"
              onClick={() => setDevice("tablet")}
              className={cn("demo-device-btn", device === "tablet" && "active")}
              title="Tablet View (768px)"
            >
              <Tablet className="w-4 h-4" />
              <span>Tablet</span>
            </button>
            <button
              type="button"
              onClick={() => setDevice("mobile")}
              className={cn("demo-device-btn", device === "mobile" && "active")}
              title="Mobile View (390px)"
            >
              <Smartphone className="w-4 h-4" />
              <span>Mobile</span>
            </button>
          </div>

          <button
            type="button"
            onClick={handleRefresh}
            className="demo-refresh-btn"
            title="Reload Demo"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", isIframeLoading && "animate-spin")} />
          </button>
        </div>

        {/* Right: Actions */}
        <div className="demo-topbar-right">
          {previewUrl && (
            <a
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="demo-fullscreen-btn"
              title="Open full page in a new browser tab without the top bar"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="demo-hide-mobile">Full Page ↗</span>
            </a>
          )}

          {template && (
            <div className="demo-price-badge">
              {formatPrice(template.price, "USD")}
            </div>
          )}

          <button
            type="button"
            onClick={handleBuyNow}
            className="demo-buy-btn"
          >
            <Zap className="w-3.5 h-3.5 fill-current" />
            <span>Buy Template</span>
          </button>
        </div>
      </header>

      {/* ── Main Canvas Viewport ───────────────────────────────────────── */}
      <main className="demo-viewport-area">
        {isIframeLoading && (
          <div className="demo-loading-overlay">
            <div className="demo-loading-card">
              <RefreshCw className="w-6 h-6 animate-spin text-primary" />
              <span>Loading Live Interactive Website…</span>
            </div>
          </div>
        )}

        <div className={cn("demo-frame-wrapper", `device-${device}`)}>
          {previewUrl ? (
            <iframe
              key={iframeKey}
              src={previewUrl}
              title={`${template?.title || targetIdentifier} Live Demo`}
              className="demo-iframe"
              sandbox="allow-scripts allow-forms allow-popups allow-modals allow-same-origin"
              onLoad={() => setIsIframeLoading(false)}
            />
          ) : (
            <div className="demo-error-notice">
              <h3>No template selected</h3>
              <p>Please select a template from the marketplace to view its live interactive demo.</p>
              <Link href="/marketplace" className="demo-back-btn mt-4">
                Browse Marketplace
              </Link>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
