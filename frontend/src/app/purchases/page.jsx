"use client";

import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Key,
  Copy,
  Check,
  ExternalLink,
  Rocket,
  Sparkles,
  Download,
  ArrowRight,
  Search,
  ShoppingBag,
  Layers,
  ShieldCheck,
  RefreshCw,
  Loader2,
  Store,
  FileCode,
  Globe,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useAppAuth, useAppUser } from "@/lib/auth";
import { api } from "@/lib/api";
import { toast } from "sonner";
import "./Purchases.css";

export default function PurchasesPage() {
  const navigate = useNavigate();
  const { getToken } = useAppAuth();
  const { user } = useAppUser();
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState("");
  const [copiedKeyId, setCopiedKeyId] = useState(null);

  // Fetch all purchased templates with verified deployment keys from backend
  const {
    data: purchases = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["myPurchasedTemplates", user?.id],
    queryFn: async () => {
      const token = await getToken();
      const res = await api.get("/licenses/my-purchases", token);
      return Array.isArray(res) ? res : [];
    },
    enabled: Boolean(user?.id),
    staleTime: 30 * 1000,
  });

  // Filtered by search
  const filteredPurchases = useMemo(() => {
    if (!searchQuery.trim()) return purchases;
    const q = searchQuery.toLowerCase().trim();
    return purchases.filter(
      (p) =>
        p.template_title?.toLowerCase().includes(q) ||
        p.deployment_key?.toLowerCase().includes(q) ||
        p.license_key?.toLowerCase().includes(q) ||
        p.framework?.toLowerCase().includes(q) ||
        p.order_number?.toLowerCase().includes(q)
    );
  }, [purchases, searchQuery]);

  // Copy key with feedback toast
  const handleCopyKey = (keyString, licenseId) => {
    if (!keyString) return;
    navigator.clipboard.writeText(keyString);
    setCopiedKeyId(licenseId);
    toast.success(`Deployment Key ${keyString} copied! Paste it in the Deployment Dashboard to import.`);
    setTimeout(() => {
      setCopiedKeyId(null);
    }, 2500);
  };

  // Generate / refresh deployment key mutation
  const generateKeyMutation = useMutation({
    mutationFn: async ({ templateId, licenseId }) => {
      const token = await getToken();
      return await api.post("/licenses/generate-key", { template_id: templateId, license_id: licenseId }, token);
    },
    onSuccess: (data) => {
      toast.success(data?.message || "Deployment key generated!");
      queryClient.invalidateQueries({ queryKey: ["myPurchasedTemplates"] });
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || err?.message || "Could not generate key.");
    },
  });

  return (
    <div className="purchases-page">
      <Navbar />
      <div className="purchases-glow" />

      <div className="purchases-container">
        {/* Breadcrumb Navigation */}
        <div className="purchases-breadcrumb">
          <Link to="/dashboard">Dashboard</Link>
          <span>/</span>
          <span className="text-white font-medium">Purchased Templates &amp; Deployment Keys</span>
        </div>

        {/* Header Hero */}
        <div className="purchases-header">
          <div className="purchases-header-info">
            <h1>
              <Key className="w-7 h-7 text-[#dfb180]" />
              <span>Purchased Templates &amp; Deployment Keys</span>
            </h1>
            <p>
              Every website you purchase carries a verified <strong>Cloud Deployment Key</strong>.
              Copy this key and paste it into your <strong>Deployment Dashboard</strong> to instantly import the template,
              customize the code in Studio, and deploy live with 1-click cloud hosting.
            </p>
          </div>

          <div className="purchases-header-actions">
            <Link to="/dashboard?tab=deployments" className="purchases-btn-primary">
              <Rocket className="w-4 h-4" />
              <span>Deployment Dashboard</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
            <Link to="/marketplace" className="purchases-btn-secondary">
              <ShoppingBag className="w-4 h-4" />
              <span>Marketplace</span>
            </Link>
          </div>
        </div>

        {/* Search & Statistics Bar */}
        <div className="purchases-toolbar">
          <div className="purchases-search">
            <Search className="purchases-search-icon" />
            <input
              type="text"
              placeholder="Search by template name, deployment key, or framework..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-3 text-xs text-zinc-400">
            <span>
              Total Owned: <strong className="text-white">{purchases.length}</strong>
            </span>
            <span>•</span>
            <span className="flex items-center gap-1 text-emerald-400">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Commercial Lifetime Licenses Active</span>
            </span>
          </div>
        </div>

        {/* Content View */}
        {isLoading ? (
          <div className="py-24 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#dfb180]" />
            <p className="text-xs text-zinc-400 mt-3 font-semibold">Loading your purchased templates &amp; keys...</p>
          </div>
        ) : purchases.length === 0 ? (
          <div className="purchases-empty-card">
            <div className="purchases-empty-icon">
              <ShoppingBag className="w-7 h-7" />
            </div>
            <h3 className="purchases-empty-title">No Purchased Templates Yet</h3>
            <p className="purchases-empty-desc">
              When you purchase a template from our marketplace or any creator storefront,
              your verified deployment key will automatically appear here so you can import and launch it.
            </p>
            <Link to="/marketplace" className="purchases-btn-primary inline-flex">
              <Sparkles className="w-4 h-4" />
              <span>Explore Marketplace Catalog</span>
            </Link>
          </div>
        ) : filteredPurchases.length === 0 ? (
          <div className="py-16 text-center text-xs text-zinc-400 border border-white/10 rounded-2xl bg-white/[0.02]">
            <p>No purchased templates match &ldquo;{searchQuery}&rdquo;</p>
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="mt-3 text-[#dfb180] underline font-bold bg-transparent border-0 cursor-pointer"
            >
              Clear Search Filter
            </button>
          </div>
        ) : (
          <div className="purchases-grid">
            {filteredPurchases.map((item) => {
              const isCopied = copiedKeyId === item.license_id;
              const depKey = item.token_id || item.deployment_key || item.license_key;

              return (
                <div key={item.license_id} className="purchases-card">
                  {/* Thumbnail Banner */}
                  <div className="purchases-thumb-box">
                    <img
                      src={item.thumbnail_url || "/landing/template_saas.png"}
                      alt={item.template_title}
                      className="purchases-thumb-img"
                      onError={(e) => {
                        e.currentTarget.src = "/landing/template_saas.png";
                      }}
                    />
                    <div className="purchases-badge-row">
                      <span className="purchases-badge-pill">
                        Purchased ✓
                      </span>
                      {item.order_number && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-black/60 text-zinc-300 border border-white/10">
                          #{item.order_number}
                        </span>
                      )}
                    </div>
                    <span className="purchases-framework-pill">
                      {item.framework || "HTML"}
                    </span>
                  </div>

                  {/* Body Content */}
                  <div className="purchases-card-body">
                    <h3 className="purchases-card-title" title={item.template_title}>
                      {item.template_title}
                    </h3>
                    <div className="purchases-card-meta">
                      <span>By {item.seller_name}</span>
                      <span className="text-emerald-400 font-semibold capitalize">
                        {item.license_type || "Commercial"} License
                      </span>
                    </div>

                    {/* Dedicated Cloud Deployment Key Box */}
                    <div className="purchases-key-box">
                      <div className="purchases-key-header">
                        <span className="flex items-center gap-1">
                          <Key className="w-3 h-3" />
                          <span>Cloud Deployment Key</span>
                        </span>
                        <button
                          type="button"
                          onClick={() => generateKeyMutation.mutate({ licenseId: item.license_id, templateId: item.template_id })}
                          disabled={generateKeyMutation.isPending}
                          className="text-[10px] text-[#dfb180] hover:underline bg-transparent border-none cursor-pointer flex items-center gap-1 font-semibold"
                          title="Refresh or regenerate activation key"
                        >
                          <RefreshCw className={`w-2.5 h-2.5 ${generateKeyMutation.isPending ? "animate-spin" : ""}`} />
                          <span>Refresh</span>
                        </button>
                      </div>

                      <div className="purchases-key-input-row">
                        <div className="purchases-key-display" title={depKey}>
                          {depKey}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleCopyKey(depKey, item.license_id)}
                          className={`purchases-key-copy-btn ${isCopied ? "copied" : ""}`}
                          title="Copy deployment key to clipboard"
                        >
                          {isCopied ? (
                            <>
                              <Check className="w-3.5 h-3.5" />
                              <span>Copied!</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5" />
                              <span>Copy Key</span>
                            </>
                          )}
                        </button>
                      </div>

                      <p className="purchases-key-help">
                        Paste this key into the <strong>Deployment Dashboard</strong> to import this website, edit files in Studio, and deploy live.
                      </p>
                    </div>

                    {/* Action Buttons Stack */}
                    <div className="purchases-actions-stack">
                      {/* 1-Click Import directly to Deployments */}
                      <button
                        type="button"
                        onClick={() => {
                          navigate(`/dashboard?tab=deployments&importKey=${encodeURIComponent(depKey)}`);
                        }}
                        className="purchases-action-btn-primary"
                      >
                        <Rocket className="w-4 h-4" />
                        <span>Paste &amp; Import to Deployments ➔</span>
                      </button>

                      <div className="purchases-actions-sub-row">
                        {/* Redesign / Edit in Studio */}
                        <Link
                          to={item.studio_edit_url || `/preview?template=${item.custom_draft_id || item.template_id}&mode=live`}
                          className="purchases-sub-btn"
                          title="Open in AI Studio Visual Editor"
                        >
                          <Sparkles className="w-3.5 h-3.5 text-[#dfb180]" />
                          <span>Edit in Studio</span>
                        </Link>

                        {/* Direct Deploy Page */}
                        <Link
                          to={item.deploy_url || `/studio/deploy?template=${item.custom_draft_id || item.template_id}`}
                          className="purchases-sub-btn"
                          title="Configure & Launch to Edge CDN"
                        >
                          <Globe className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Deploy Live</span>
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
