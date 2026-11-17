"use client";

import { useState, useEffect } from "react";
import {
  X,
  Sparkles,
  ShoppingBag,
  DollarSign,
  Tag,
  Layers,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Lock,
  Globe,
  ExternalLink,
  Crown,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import "./RetailTemplateModal.css";

const QUICK_PRICES = [19, 29, 49, 79];

export default function RetailTemplateModal({
  isOpen,
  onClose,
  template,
  user,
  authToken,
  onSuccess,
}) {
  const navigate = useNavigate();

  const isExtreme =
    user?.can_retail_templates ||
    user?.is_extreme_subscriber ||
    ["extreme", "agency", "enterprise"].includes(String(user?.subscription_tier || "").toLowerCase()) ||
    user?.role === "admin" ||
    user?.role === "super_admin";

  const [retailPrice, setRetailPrice] = useState("29");
  const [title, setTitle] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [shortDesc, setShortDesc] = useState("");
  const [tags, setTags] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [retailedResult, setRetailedResult] = useState(null);

  // Fetch Categories for selection
  const { data: categories = [] } = useQuery({
    queryKey: ["marketplace-categories"],
    queryFn: async () => {
      const res = await api.get("/categories");
      return Array.isArray(res) ? res : res?.items || [];
    },
    staleTime: 1000 * 60 * 10,
  });

  useEffect(() => {
    if (template) {
      setTitle(template.title || "Custom AI Generated Website");
      setShortDesc(
        template.short_description ||
        template.description?.slice(0, 200) ||
        "Turnkey AI-generated website ready for high-conversion production deployment."
      );
      setCategoryId(template.category_id || (categories[0]?.id || ""));
      const initialTags = Array.isArray(template.tags)
        ? template.tags.filter((t) => t !== "studio-project" && t !== "custom-draft").join(", ")
        : "";
      setTags(initialTags || "modern, responsive, fast");
      setRetailPrice(template.price && Number(template.price) > 0 ? String(template.price) : "29");
      setRetailedResult(null);
      setErrorMsg("");
    }
  }, [template, categories]);

  if (!isOpen || !template) return null;

  const handlePublish = async (e) => {
    e?.preventDefault();
    if (!retailPrice || isNaN(Number(retailPrice)) || Number(retailPrice) < 1) {
      setErrorMsg("Please enter a valid retail price (minimum $1.00 USD).");
      return;
    }
    if (!title.trim()) {
      setErrorMsg("Please provide a title for the marketplace listing.");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg("");

    try {
      const cleanTags = tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);

      const payload = {
        template_id: template.id,
        retail_price: Number(retailPrice),
        title: title.trim(),
        category_id: categoryId || categories[0]?.id || undefined,
        short_description: shortDesc.trim(),
        description: template.description || shortDesc.trim(),
        tags: cleanTags,
        industry: template.industry || "Technology",
      };

      const res = await api.post("/templates/retail", payload, authToken);
      setRetailedResult(res);
      if (onSuccess) {
        onSuccess(res);
      }
    } catch (err) {
      console.error("Retail listing error:", err);
      setErrorMsg(
        err?.response?.data?.detail ||
        err?.message ||
        "Could not list template for retail. Please check your connection and try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rtm-backdrop" onClick={onClose}>
      <div className="rtm-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="rtm-header">
          <div className="rtm-header-left">
            <div className="rtm-icon-badge">
              <ShoppingBag className="w-5 h-5 text-[#dfb180]" />
            </div>
            <div>
              <h3 className="rtm-title">Retail on Marketplace</h3>
              <p className="rtm-subtitle">
                List your AI-generated website for other creators & businesses to purchase
              </p>
            </div>
          </div>
          <button type="button" onClick={onClose} className="rtm-close-btn" aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* ── CASE 1: SUCCESS CONFIRMATION ── */}
        {retailedResult ? (
          <div className="rtm-body rtm-success-state">
            <div className="rtm-success-icon-wrap">
              <CheckCircle2 className="w-10 h-10 text-emerald-400" />
            </div>
            <h4 className="rtm-success-title">Successfully Listed for Retail!</h4>
            <p className="rtm-success-desc">
              <strong>{retailedResult.title || title}</strong> is now live on the Site Studio global marketplace priced at <strong>${Number(retailPrice).toFixed(2)} USD</strong>.
            </p>

            <div className="rtm-success-card">
              <div className="rtm-success-meta">
                <span className="rtm-meta-label">Status</span>
                <span className="rtm-status-pill">Published &amp; Active</span>
              </div>
              <div className="rtm-success-meta">
                <span className="rtm-meta-label">Retail Price</span>
                <span className="rtm-price-highlight">${Number(retailPrice).toFixed(2)} USD</span>
              </div>
              <div className="rtm-success-meta">
                <span className="rtm-meta-label">Marketplace URL</span>
                <span className="rtm-url-text">/marketplace/{retailedResult.slug}</span>
              </div>
            </div>

            <div className="rtm-actions-row">
              <button
                type="button"
                onClick={() => {
                  onClose();
                  navigate(`/marketplace/${retailedResult.slug || retailedResult.id}`);
                }}
                className="rtm-btn-primary"
              >
                <span>View Live Marketplace Listing</span>
                <ExternalLink className="w-4 h-4 ml-1.5" />
              </button>
              <button type="button" onClick={onClose} className="rtm-btn-secondary">
                Done
              </button>
            </div>
          </div>
        ) : !isExtreme ? (
          /* ── CASE 2: NON-EXTREME UPGRADE GATE ── */
          <div className="rtm-body rtm-gate-state">
            <div className="rtm-gate-badge">
              <Crown className="w-5 h-5 text-emerald-400" />
              <span>Exclusive Extreme Plan Privilege</span>
            </div>

            <h4 className="rtm-gate-title">
              Turn Your AI-Generated Websites <br />
              Into Commercial Products
            </h4>
            <p className="rtm-gate-desc">
              Selling and retailing generated websites on the marketplace is an exclusive feature of the <strong>Extreme Plan ($50/mo)</strong>.
            </p>

            <div className="rtm-perks-grid">
              <div className="rtm-perk-item">
                <ShoppingBag className="w-4 h-4 text-emerald-400 shrink-0" />
                <div>
                  <strong>Marketplace Retailer License:</strong>
                  <span> Retail unlimited AI-generated websites directly to buyers worldwide.</span>
                </div>
              </div>
              <div className="rtm-perk-item">
                <Zap className="w-4 h-4 text-emerald-400 shrink-0" />
                <div>
                  <strong>1,000 Monthly AI Credits:</strong>
                  <span> Continuous compute power to generate bespoke full-stack templates.</span>
                </div>
              </div>
              <div className="rtm-perk-item">
                <Globe className="w-4 h-4 text-emerald-400 shrink-0" />
                <div>
                  <strong>Automated Payouts:</strong>
                  <span> Earn creator revenue deposited directly into your bank or Stripe account.</span>
                </div>
              </div>
            </div>

            <div className="rtm-gate-actions">
              <button
                type="button"
                onClick={() => {
                  onClose();
                  navigate("/subscribe?plan=extreme");
                }}
                className="rtm-btn-upgrade"
              >
                <Crown className="w-4 h-4 mr-2" />
                <span>Upgrade to Extreme Plan ($50/mo)</span>
                <ArrowRight className="w-4 h-4 ml-2" />
              </button>
              <button type="button" onClick={onClose} className="rtm-btn-secondary">
                Maybe Later
              </button>
            </div>
          </div>
        ) : (
          /* ── CASE 3: RETAIL FORM FOR EXTREME SUBSCRIBERS ── */
          <form onSubmit={handlePublish} className="rtm-body rtm-form-state">
            {/* Generated Site Snapshot */}
            <div className="rtm-template-preview-bar">
              <div className="rtm-preview-img-wrap">
                {template.thumbnail_url ? (
                  <img src={template.thumbnail_url} alt={template.title} className="rtm-preview-img" />
                ) : (
                  <span className="text-xl">💻</span>
                )}
              </div>
              <div className="rtm-preview-info">
                <span className="rtm-preview-badge">AI-Generated Studio Site</span>
                <h5 className="rtm-preview-title">{template.title || "Custom Generated Project"}</h5>
                <p className="rtm-preview-tech">
                  Framework: <strong>{template.framework || "HTML / React"}</strong> • ID: #{String(template.id || "").slice(0, 8)}
                </p>
              </div>
            </div>

            {errorMsg && (
              <div className="rtm-error-banner">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Retail Price Input & Quick Pills */}
            <div className="rtm-field-group">
              <label className="rtm-label">
                <span>Set Retail Price (USD)</span>
                <span className="rtm-label-sub">You set your own price per template</span>
              </label>
              <div className="rtm-price-input-row">
                <div className="rtm-price-input-wrap">
                  <span className="rtm-currency-symbol">$</span>
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    step="1"
                    required
                    value={retailPrice}
                    onChange={(e) => setRetailPrice(e.target.value)}
                    className="rtm-text-input rtm-price-input"
                    placeholder="29"
                  />
                  <span className="rtm-currency-code">USD</span>
                </div>
                <div className="rtm-quick-prices">
                  {QUICK_PRICES.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setRetailPrice(String(p))}
                      className={`rtm-quick-pill ${retailPrice === String(p) ? "active" : ""}`}
                    >
                      ${p}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Title Input */}
            <div className="rtm-field-group">
              <label className="rtm-label">Marketplace Listing Title</label>
              <input
                type="text"
                required
                maxLength={255}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="rtm-text-input"
                placeholder="e.g. Apex Strategy - Modern Consulting SaaS"
              />
            </div>

            {/* Category Selector */}
            <div className="rtm-field-group">
              <label className="rtm-label">Marketplace Category</label>
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="rtm-text-input rtm-select"
              >
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Short Description */}
            <div className="rtm-field-group">
              <label className="rtm-label">Short Description</label>
              <textarea
                rows={2}
                maxLength={500}
                value={shortDesc}
                onChange={(e) => setShortDesc(e.target.value)}
                className="rtm-text-input rtm-textarea"
                placeholder="Brief summary of what this website provides..."
              />
            </div>

            {/* Tags Input */}
            <div className="rtm-field-group">
              <label className="rtm-label">Tags (comma separated)</label>
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                className="rtm-text-input"
                placeholder="saas, landing, modern, tailwind"
              />
            </div>

            {/* Submit Action */}
            <div className="rtm-form-footer">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="rtm-btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="rtm-btn-primary"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    <span>Publishing to Marketplace…</span>
                  </>
                ) : (
                  <>
                    <ShoppingBag className="w-4 h-4 mr-1.5" />
                    <span>Publish &amp; Retail for ${Number(retailPrice || 0).toFixed(2)}</span>
                    <ArrowRight className="w-4 h-4 ml-1.5" />
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
