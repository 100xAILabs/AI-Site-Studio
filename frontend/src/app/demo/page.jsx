"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import Link from "@/components/Link";
import {
  ArrowLeft, Monitor, Tablet, Smartphone, RefreshCw,
  ExternalLink, Zap, Clock, ShoppingCart, Lock, Sparkles
} from "lucide-react";
import { useTemplate } from "@/hooks/useTemplates";
import { API_URL } from "@/lib/api";
import { cn, formatPrice } from "@/lib/utils";
import { useCartStore } from "@/store";
import "./Page.css";

// Demo duration: 5 minutes = 300 seconds
const DEMO_DURATION_SECONDS = 300;

function formatTime(totalSec) {
  const m = Math.floor(Math.max(0, totalSec) / 60);
  const s = Math.max(0, totalSec) % 60;
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

export default function LiveDemoPage() {
  const { slug: routeSlug } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const targetIdentifier = routeSlug || searchParams.get("template") || searchParams.get("slug") || "";
  const { data: template, isLoading: isTemplateLoading } = useTemplate(targetIdentifier);

  const [device, setDevice] = useState("desktop");
  const [iframeKey, setIframeKey] = useState(0);
  const [isIframeLoading, setIsIframeLoading] = useState(true);

  // ── 5-Minute Demo Timer ──────────────────────────────────────────────────
  const storageKey = `demo_started_${targetIdentifier}`;
  const getElapsed = () => {
    try {
      const startedAt = parseInt(sessionStorage.getItem(storageKey) || "0", 10);
      if (!startedAt) return 0;
      return Math.floor((Date.now() - startedAt) / 1000);
    } catch {
      return 0;
    }
  };

  const initRemaining = () => {
    const elapsed = getElapsed();
    return elapsed > 0 ? Math.max(0, DEMO_DURATION_SECONDS - elapsed) : DEMO_DURATION_SECONDS;
  };

  const [remaining, setRemaining] = useState(initRemaining);
  const [isDemoExpired, setIsDemoExpired] = useState(() => getElapsed() >= DEMO_DURATION_SECONDS);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!targetIdentifier) return;
    // Stamp start time on first visit
    try {
      if (!sessionStorage.getItem(storageKey)) {
        sessionStorage.setItem(storageKey, String(Date.now()));
      }
    } catch {}

    if (isDemoExpired) return;

    timerRef.current = setInterval(() => {
      const elapsed = getElapsed();
      const rem = Math.max(0, DEMO_DURATION_SECONDS - elapsed);
      setRemaining(rem);
      if (rem <= 0) {
        clearInterval(timerRef.current);
        setIsDemoExpired(true);
      }
    }, 1000);

    return () => clearInterval(timerRef.current);
  }, [targetIdentifier]);

  // ── Cart & Buy ───────────────────────────────────────────────────────────
  const items = useCartStore((s) => s.items) || [];
  const addItem = useCartStore((s) => s.addItem);
  const templateId = template?.id || targetIdentifier;

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const previewUrl = targetIdentifier
    ? `${API_URL}/preview/live/${targetIdentifier}/${token ? `?token=${encodeURIComponent(token)}` : ""}`
    : "";

  const handleRefresh = () => {
    if (isDemoExpired) return;
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

  // urgency color: green > yellow > orange > red
  const timerColor =
    remaining > 180 ? "#34d399" :
    remaining > 90  ? "#fbbf24" :
    remaining > 30  ? "#f97316" : "#ef4444";

  return (
    <div className="demo-showcase-container">
      {/* ── Demo Expired Overlay ──────────────────────────────────────────── */}
      {isDemoExpired && (
        <div className="demo-expired-overlay">
          <div className="demo-expired-card">
            <div className="demo-expired-icon">
              <Lock className="w-7 h-7" />
            </div>
            <div className="demo-expired-badge">5-Minute Demo Ended</div>
            <h2 className="demo-expired-title">Your free demo has expired</h2>
            <p className="demo-expired-desc">
              Your 5-minute live demo window has ended. Purchase the template to get
              unlimited access to the Studio Editor, AI personalizer, and source code.
            </p>
            <div className="demo-expired-actions">
              <button
                type="button"
                onClick={handleBuyNow}
                className="demo-expired-buy-btn"
              >
                <Zap className="w-4 h-4 fill-current" />
                {template ? `Buy Now • ${formatPrice(template.price, "USD")}` : "Buy Template"}
              </button>
              <Link
                href={targetIdentifier ? `/marketplace/${targetIdentifier}` : "/marketplace"}
                className="demo-expired-back-link"
              >
                ← Back to Template Details
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* ── Top Navigation Bar ───────────────────────────────────────────── */}
      <header className="demo-topbar">
        {/* Left: Back & Title */}
        <div className="demo-topbar-left">
          <Link
            href={targetIdentifier ? `/marketplace/${targetIdentifier}` : "/marketplace"}
            className="demo-back-btn"
            title="Return to Template Details"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="demo-back-label">Back</span>
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

        {/* Center: Device Switcher */}
        <div className="demo-topbar-center">
          <div className="demo-device-tabs">
            {[
              { id: "desktop", Icon: Monitor, label: "Desktop" },
              { id: "tablet",  Icon: Tablet,  label: "Tablet"  },
              { id: "mobile",  Icon: Smartphone, label: "Mobile" },
            ].map(({ id, Icon, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setDevice(id)}
                disabled={isDemoExpired}
                className={cn("demo-device-btn", device === id && "active")}
                title={`${label} View`}
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={isDemoExpired}
            className="demo-refresh-btn"
            title="Reload Demo"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", isIframeLoading && !isDemoExpired && "animate-spin")} />
          </button>
        </div>

        {/* Right: Timer + Buy */}
        <div className="demo-topbar-right">
          {/* Countdown Timer */}
          <div
            className={cn("demo-timer-pill", isDemoExpired && "expired")}
            style={!isDemoExpired ? { "--timer-color": timerColor } : {}}
            title="Demo time remaining"
          >
            <Clock className="w-3.5 h-3.5" />
            <span className="demo-timer-value">
              {isDemoExpired ? "Ended" : formatTime(remaining)}
            </span>
          </div>

          {template && !isDemoExpired && (
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
            <span>{isDemoExpired ? "Buy to Continue" : "Buy Template"}</span>
          </button>
        </div>
      </header>

      {/* ── Main Canvas Viewport ─────────────────────────────────────────── */}
      <main className="demo-viewport-area">
        {isIframeLoading && !isDemoExpired && (
          <div className="demo-loading-overlay">
            <div className="demo-loading-card">
              <RefreshCw className="w-6 h-6 animate-spin text-primary" />
              <span>Loading Live Interactive Website…</span>
            </div>
          </div>
        )}

        <div className={cn("demo-frame-wrapper", `device-${device}`, isDemoExpired && "demo-frame-blurred")}>
          {previewUrl ? (
            <iframe
              key={iframeKey}
              src={isDemoExpired ? "about:blank" : previewUrl}
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
