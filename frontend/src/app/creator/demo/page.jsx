"use client";

import { useState, useMemo } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, API_URL } from "@/lib/api";
import { useCartStore } from "@/store";
import {
  ArrowLeft,
  Monitor,
  Tablet,
  Smartphone,
  RefreshCw,
  Zap,
  Store,
  ShieldCheck,
  ExternalLink,
  ShoppingCart,
} from "lucide-react";
import "./demo.css";

export default function CreatorDemoPage() {
  const params = useParams();
  const navigate = useNavigate();

  const creatorSlug = params?.creatorSlug || "";
  const templateSlug = params?.slug || "";

  const [device, setDevice] = useState("desktop"); // "desktop" | "tablet" | "mobile"
  const [iframeKey, setIframeKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  const addItem = useCartStore((s) => s.addItem);

  // 1. Fetch Creator Storefront Data
  const { data: storefront } = useQuery({
    queryKey: ["creatorStorefrontDemo", creatorSlug],
    queryFn: async () => {
      if (!creatorSlug) return null;
      const res = await api.get(`/creator/storefront/${encodeURIComponent(creatorSlug)}`);
      return res;
    },
    enabled: Boolean(creatorSlug),
    staleTime: 60 * 1000,
  });

  // 2. Fetch Template Details
  const { data: template } = useQuery({
    queryKey: ["creatorDemoTemplate", templateSlug],
    queryFn: async () => {
      if (!templateSlug) return null;
      const res = await api.get(`/templates/${encodeURIComponent(templateSlug)}`);
      return res;
    },
    enabled: Boolean(templateSlug),
    staleTime: 60 * 1000,
  });

  const brandName = storefront?.brand_name || template?.seller?.creator_brand_name || "Creator Storefront";
  const effectivePrice = Number(template?.price) || 39;

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const targetId = template?.slug || template?.id || templateSlug;

  // Direct raw live preview HTML without platform shell
  const livePreviewUrl = targetId
    ? `${API_URL}/preview/live/${encodeURIComponent(targetId)}/${token ? `?token=${encodeURIComponent(token)}` : ""}`
    : "";

  const handleBuyNow = () => {
    if (template) {
      addItem({
        templateId: template.id || template.slug,
        id: template.id || template.slug,
        title: template.title,
        price: effectivePrice,
        price_currency: template.price_currency || "USD",
        thumbnail: template.thumbnail_url || template.thumbnail || "/landing/template_saas.png",
        framework: template.framework || "React 19 + Tailwind",
        licenseType: "commercial",
        seller_id: template.seller_id,
        creator_slug: creatorSlug || template.seller?.creator_store_slug,
        creator_brand_name: brandName,
      });
    }
    navigate(`/creator/${creatorSlug}/checkout`);
  };

  const handleRefresh = () => {
    setIsLoading(true);
    setIframeKey((prev) => prev + 1);
  };

  const backUrl = `/creator/${creatorSlug}/template/${templateSlug}`;

  return (
    <div className="cr-demo-page">
      {/* ── 1. Top Navigation Bar (100% Creator Branded) ── */}
      <header className="cr-demo-topbar">
        {/* Left: Back & Creator Brand Badge */}
        <div className="cr-demo-topbar-left">
          <Link to={backUrl} className="cr-demo-back-btn">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Store</span>
          </Link>

          <div className="cr-demo-divider" />

          <Link to={`/creator/${creatorSlug}`} className="cr-demo-brand-pill">
            <div className="cr-demo-brand-logo">
              {storefront?.logo_url ? (
                <img src={storefront.logo_url} alt={brandName} />
              ) : (
                <Store className="w-3.5 h-3.5 text-[#dfb180]" />
              )}
            </div>
            <span className="font-semibold text-xs text-white">{brandName}</span>
          </Link>

          <div className="cr-demo-title-group">
            <span className="cr-demo-title">{template?.title || templateSlug}</span>
            <span className="cr-demo-badge-live">Live Demo</span>
            {template?.framework && (
              <span className="cr-demo-badge-framework">{template.framework}</span>
            )}
          </div>
        </div>

        {/* Center: Device Switcher */}
        <div className="cr-demo-topbar-center">
          <div className="cr-demo-device-tabs">
            <button
              type="button"
              onClick={() => setDevice("desktop")}
              className={`cr-demo-device-btn ${device === "desktop" ? "active" : ""}`}
            >
              <Monitor className="w-3.5 h-3.5" />
              <span>Desktop</span>
            </button>
            <button
              type="button"
              onClick={() => setDevice("tablet")}
              className={`cr-demo-device-btn ${device === "tablet" ? "active" : ""}`}
            >
              <Tablet className="w-3.5 h-3.5" />
              <span>Tablet</span>
            </button>
            <button
              type="button"
              onClick={() => setDevice("mobile")}
              className={`cr-demo-device-btn ${device === "mobile" ? "active" : ""}`}
            >
              <Smartphone className="w-3.5 h-3.5" />
              <span>Mobile</span>
            </button>
          </div>

          <button
            type="button"
            onClick={handleRefresh}
            className="cr-demo-refresh-btn"
            title="Reload Demo"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {/* Right: Price & Creator Buy CTA */}
        <div className="cr-demo-topbar-right">
          <span className="cr-demo-price">${effectivePrice}</span>
          {storefront?.is_bank_connected === false ? (
            <button
              type="button"
              disabled
              className="cr-demo-buy-btn opacity-60 cursor-not-allowed bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs px-3"
              title="Purchases temporarily paused: Creator bank account not yet linked"
            >
              <span>Purchases Paused</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleBuyNow}
              className="cr-demo-buy-btn"
            >
              <Zap className="w-3.5 h-3.5 fill-current" />
              <span>Buy Template</span>
            </button>
          )}
        </div>
      </header>

      {/* ── 2. Viewport Canvas & Iframe ── */}
      <main className="cr-demo-viewport">
        {isLoading && (
          <div className="cr-demo-loading">
            <RefreshCw className="w-6 h-6 animate-spin text-[#dfb180]" />
            <span className="cr-demo-loading-text">Loading Live Interactive Website…</span>
          </div>
        )}

        <div className={`cr-demo-frame-container ${device}`}>
          {livePreviewUrl ? (
            <iframe
              key={iframeKey}
              src={livePreviewUrl}
              title={`${template?.title || templateSlug} Demo`}
              className="cr-demo-iframe"
              sandbox="allow-scripts allow-forms allow-popups allow-modals allow-same-origin"
              onLoad={() => setIsLoading(false)}
            />
          ) : (
            <div className="flex flex-col items-center justify-center w-full h-full text-zinc-400 gap-3">
              <span>Preview not available</span>
              <Link to={backUrl} className="cr-demo-back-btn">
                Return to Template
              </Link>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
