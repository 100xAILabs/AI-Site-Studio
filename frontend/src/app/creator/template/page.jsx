"use client";

import { useState, useMemo } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, API_URL } from "@/lib/api";
import { useCartStore } from "@/store";
import CreatorStorefrontNavbar from "@/components/layout/CreatorStorefrontNavbar";
import {
  ArrowLeft,
  ArrowRight,
  Monitor,
  Tablet,
  Smartphone,
  ExternalLink,
  ShoppingCart,
  Check,
  ShieldCheck,
  Code2,
  Sparkles,
  Zap,
  Download,
  Store,
  Layers,
  Star,
  CheckCircle2,
  Mail,
  Rocket,
} from "lucide-react";
import "./template.css";

export default function CreatorTemplateDetailsPage() {
  const params = useParams();
  const navigate = useNavigate();

  const creatorSlug = params?.creatorSlug || "";
  const templateSlug = params?.slug || "";

  const [deviceMode, setDeviceMode] = useState("desktop"); // "desktop" | "tablet" | "mobile"
  const [activeTab, setActiveTab] = useState("preview");

  const { items, addItem } = useCartStore();

  // 1. Fetch Creator Storefront Info
  const { data: storefront } = useQuery({
    queryKey: ["creatorStorefrontTplPage", creatorSlug],
    queryFn: async () => {
      if (!creatorSlug) return null;
      const res = await api.get(`/creator/storefront/${encodeURIComponent(creatorSlug)}`);
      return res;
    },
    enabled: Boolean(creatorSlug),
    staleTime: 60 * 1000,
  });

  // 2. Fetch Template Details
  const { data: template, isLoading: tplLoading } = useQuery({
    queryKey: ["creatorTemplateDetails", templateSlug],
    queryFn: async () => {
      if (!templateSlug) return null;
      const res = await api.get(`/templates/${encodeURIComponent(templateSlug)}`);
      return res;
    },
    enabled: Boolean(templateSlug),
    staleTime: 60 * 1000,
  });

  const brandName = storefront?.brand_name || template?.seller?.creator_brand_name || "Creator Storefront";

  const isItemInCart = useMemo(() => {
    if (!template) return false;
    return items.some((i) => i.templateId === template.id || i.id === template.id || i.slug === template.slug);
  }, [items, template]);

  const creatorScopedCart = useMemo(() => {
    if (!Array.isArray(items)) return [];
    if (!creatorSlug) return items;
    return items.filter(
      (i) => i.creator_slug && i.creator_slug.toLowerCase() === creatorSlug.toLowerCase()
    );
  }, [items, creatorSlug]);

  const effectivePrice = Number(template?.price) || 39;
  const originalPrice = template?.original_price ? Number(template.original_price) : Math.round(effectivePrice * 1.5);

  const handleAddToCart = () => {
    if (!template) return;
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
  };

  const handleBuyNow = () => {
    handleAddToCart();
    navigate(`/creator/${creatorSlug}/checkout`);
  };

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const targetId = template?.id || template?.slug || templateSlug;

  // Direct raw live preview HTML without platform shell
  const rawPreviewUrl = targetId
    ? `${API_URL}/preview/live/${encodeURIComponent(targetId)}${token ? `?token=${encodeURIComponent(token)}` : ""}`
    : "";

  // Dedicated creator live demo page
  const creatorDemoUrl = `/creator/${encodeURIComponent(creatorSlug)}/demo/${encodeURIComponent(template?.slug || templateSlug)}`;

  return (
    <div className="cr-tpl-page">
      <div className="cr-tpl-glow" />

      {/* Branded Creator Navbar */}
      <CreatorStorefrontNavbar
        storefront={storefront}
        creatorSlug={creatorSlug}
        cartItems={creatorScopedCart}
      />

      <div className="cr-tpl-container">
        {/* Navigation Breadcrumb */}
        <div className="cr-tpl-top-nav">
          <Link to={`/creator/${creatorSlug}`} className="cr-tpl-back-link">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to {brandName}&apos;s Storefront</span>
          </Link>
        </div>

        {/* Template Header Banner */}
        <header className="cr-tpl-header">
          <div className="cr-tpl-header-left">
            <div className="cr-tpl-badges-row">
              <span className="cr-tpl-badge-primary">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Verified Production Code</span>
              </span>
              <span className="cr-tpl-badge-meta">
                {template?.framework || "React 19 + Tailwind"}
              </span>
              <span className="cr-tpl-badge-meta">
                {template?.category?.name || "Premium Template"}
              </span>
              {template?.rating_avg && (
                <span className="cr-tpl-badge-meta flex items-center gap-1 text-amber-400">
                  <Star className="w-3 h-3 fill-amber-400" />
                  <span>{template.rating_avg.toFixed(1)}</span>
                </span>
              )}
            </div>

            <h1 className="cr-tpl-title">{template?.title || "Exclusive Website Template"}</h1>
            <p className="cr-tpl-desc">
              {template?.short_description ||
                template?.description ||
                "A high-converting, fully responsive web application template crafted with clean architecture and production-grade components."}
            </p>

            <div className="cr-tpl-author-pill">
              <div className="cr-tpl-author-avatar">
                {(brandName || "C").charAt(0).toUpperCase()}
              </div>
              <span className="cr-tpl-author-name">Created by {brandName}</span>
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            </div>
          </div>
        </header>

        {/* Main Showcase Layout */}
        <div className="cr-tpl-layout">
          {/* Left: Interactive Preview Frame */}
          <div className="cr-preview-box">
            <div className="cr-preview-topbar">
              <div className="cr-preview-dots">
                <span className="cr-preview-dot red" />
                <span className="cr-preview-dot yellow" />
                <span className="cr-preview-dot green" />
              </div>

              {/* Responsive Device Switcher */}
              <div className="cr-device-switch">
                <button
                  type="button"
                  onClick={() => setDeviceMode("desktop")}
                  className={`cr-device-btn ${deviceMode === "desktop" ? "active" : ""}`}
                >
                  <Monitor className="w-3.5 h-3.5" />
                  <span>Desktop</span>
                </button>
                <button
                  type="button"
                  onClick={() => setDeviceMode("tablet")}
                  className={`cr-device-btn ${deviceMode === "tablet" ? "active" : ""}`}
                >
                  <Tablet className="w-3.5 h-3.5" />
                  <span>Tablet</span>
                </button>
                <button
                  type="button"
                  onClick={() => setDeviceMode("mobile")}
                  className={`cr-device-btn ${deviceMode === "mobile" ? "active" : ""}`}
                >
                  <Smartphone className="w-3.5 h-3.5" />
                  <span>Mobile</span>
                </button>
              </div>

              {/* Fullscreen Dedicated Creator Demo Link */}
              <Link
                to={creatorDemoUrl}
                className="cr-fullscreen-btn"
                title="Open dedicated creator interactive demo"
              >
                <span>Live Demo</span>
                <ExternalLink className="w-3 h-3" />
              </Link>
            </div>

            {/* Iframe Frame - Clean Template Preview */}
            <div className="cr-preview-frame-wrapper">
              <iframe
                src={rawPreviewUrl || "about:blank"}
                title={template?.title || "Template Preview"}
                className={`cr-preview-frame ${deviceMode}`}
                sandbox="allow-scripts allow-forms allow-popups allow-modals allow-same-origin"
                loading="lazy"
              />
            </div>
          </div>

          {/* Right: Pricing & Buy Card */}
          <aside className="cr-buy-card">
            <div>
              <div className="cr-price-row">
                <span className="cr-price-val">${effectivePrice}</span>
                {originalPrice > effectivePrice && (
                  <>
                    <span className="cr-price-original">${originalPrice}</span>
                    <span className="cr-discount-pill">
                      Save {Math.round(((originalPrice - effectivePrice) / originalPrice) * 100)}%
                    </span>
                  </>
                )}
              </div>
              <div className="cr-license-info mt-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Commercial License (Full Ownership)</span>
              </div>
            </div>

            <div className="flex flex-col gap-2.5">
              {storefront?.is_bank_connected === false && (
                <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-amber-300 text-xs flex items-center gap-2 mb-1">
                  <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>Purchases paused: Creator has not completed bank verification yet.</span>
                </div>
              )}
              <button
                type="button"
                onClick={handleBuyNow}
                disabled={storefront?.is_bank_connected === false}
                className="cr-buy-btn-primary"
              >
                <span>{storefront?.is_bank_connected === false ? "Purchases Paused (Bank Not Linked)" : "Buy Template Now"}</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={handleAddToCart}
                disabled={storefront?.is_bank_connected === false}
                className={`cr-cart-btn-secondary ${isItemInCart ? "in-cart" : ""}`}
              >
                {isItemInCart ? (
                  <>
                    <Check className="w-4 h-4 text-emerald-400" />
                    <span>In Cart (View Checkout)</span>
                  </>
                ) : (
                  <>
                    <ShoppingCart className="w-4 h-4" />
                    <span>Add to Cart</span>
                  </>
                )}
              </button>
            </div>

            {/* Feature Perks List */}
            <div className="cr-perks-list">
              <div className="cr-perk-item">
                <Zap className="cr-perk-icon w-4 h-4" />
                <span>Instant ZIP package code download immediately after purchase.</span>
              </div>
              <div className="cr-perk-item">
                <Code2 className="cr-perk-icon w-4 h-4" />
                <span>100% clean, unminified source code with component architecture.</span>
              </div>
              <div className="cr-perk-item">
                <ShieldCheck className="cr-perk-icon w-4 h-4" />
                <span>No watermarks, no recurring platform fees, lifetime usage rights.</span>
              </div>
              {storefront?.support_email && (
                <div className="cr-perk-item">
                  <Mail className="cr-perk-icon w-4 h-4" />
                  <span>
                    Direct creator support: <strong>{storefront.support_email}</strong>
                  </span>
                </div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
