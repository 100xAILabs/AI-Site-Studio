"use client";

import { useState } from "react";
import {
  ShoppingBag,
  Sparkles,
  ExternalLink,
  Crown,
  Zap,
  Coins,
  ArrowRight,
  Cpu,
  Globe,
  CheckCircle2,
  Tag,
  DollarSign,
  TrendingUp,
} from "lucide-react";
import Link from "@/components/Link";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export const isStudioProjectItem = (item) => {
  if (!item) return false;
  const origin = item.template_origin || "";
  if (
    origin === "studio" ||
    origin === "custom_draft" ||
    (Array.isArray(item.tags) && (item.tags.includes("studio-project") || item.tags.includes("ai-generated")))
  ) {
    return true;
  }
  return false;
};

export default function MarketplaceRetailHub({
  user,
  isExtreme,
  isAdmin,
  templateResponse,
  onRetailClick,
  navigate,
}) {
  const allUserTemplates = Array.isArray(templateResponse) ? templateResponse : [];

  // Filter templates generated in Studio that are not yet published to marketplace
  const readyToRetail = allUserTemplates.filter(
    (item) => isStudioProjectItem(item) && !item.is_marketplace
  );

  // Filter templates published/retailed on marketplace
  const retailedListings = allUserTemplates.filter(
    (item) =>
      item.is_marketplace &&
      (String(item.seller_id) === String(user?.id) || String(item.status).toLowerCase() === "published")
  );

  const canRetail = isExtreme || isAdmin;

  return (
    <div className="glass-premium p-6 sm:p-8 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#c89666]/15 border border-[#c89666]/30 flex items-center justify-center shrink-0">
            <ShoppingBag className="w-5 h-5 text-[#dfb180]" />
          </div>
          <div>
            <h3 className="font-extrabold text-xl text-foreground">Marketplace Retailing Hub</h3>
            <p className="text-xs text-muted-foreground font-medium">
              Retail your AI-generated websites directly on Site Studio to earn creator revenue.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/studio"
            className="px-3.5 py-2 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30 text-xs font-bold flex items-center gap-1.5 transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Generate New Website</span>
          </Link>
          <Link
            href="/marketplace"
            className="px-3.5 py-2 rounded-xl bg-card hover:bg-card/80 border border-border/50 text-xs font-bold text-foreground flex items-center gap-1.5 transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span>View Marketplace</span>
          </Link>
        </div>
      </div>

      {/* Privilege Status Banner */}
      {canRetail ? (
        <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs">
          <div className="flex items-center gap-2.5">
            <Crown className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <strong className="font-bold">⚡ Extreme Plan Retailing Privilege Active:</strong>
              <span className="text-emerald-200/90 ml-1">
                You hold an active license to retail unlimited AI-generated websites directly to buyers across the globe.
              </span>
            </div>
          </div>
          <span className="text-[10px] font-black uppercase tracking-wider px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shrink-0">
            Extreme Retailer Active
          </span>
        </div>
      ) : (
        <div className="p-6 rounded-2xl bg-gradient-to-br from-[#c89666]/15 via-black/40 to-emerald-500/10 border border-[#c89666]/30 text-center space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-bold">
            <Crown className="w-4 h-4" />
            <span>Exclusive Extreme Plan Privilege</span>
          </div>
          <div className="max-w-xl mx-auto space-y-2">
            <h4 className="text-xl font-extrabold text-foreground">
              Turn Your AI-Generated Websites Into Commercial Products
            </h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Retailing websites on the marketplace is an exclusive feature of the <strong>Extreme Plan ($50/mo)</strong>. Upgrade to Extreme to list and sell your AI-generated websites directly to buyers with automated payouts and licensing.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl mx-auto pt-2 text-left">
            <div className="p-3.5 rounded-xl bg-black/40 border border-white/5 space-y-1">
              <ShoppingBag className="w-4 h-4 text-emerald-400" />
              <h6 className="text-xs font-bold text-foreground">Sell Unlimited Sites</h6>
              <p className="text-[11px] text-muted-foreground">List as many generated templates as you want and set your custom USD price.</p>
            </div>
            <div className="p-3.5 rounded-xl bg-black/40 border border-white/5 space-y-1">
              <Zap className="w-4 h-4 text-emerald-400" />
              <h6 className="text-xs font-bold text-foreground">1,000 AI Credits / Mo</h6>
              <p className="text-[11px] text-muted-foreground">Continuous compute power to synthesize complete multi-page websites.</p>
            </div>
            <div className="p-3.5 rounded-xl bg-black/40 border border-white/5 space-y-1">
              <Coins className="w-4 h-4 text-emerald-400" />
              <h6 className="text-xs font-bold text-foreground">Direct Creator Payouts</h6>
              <p className="text-[11px] text-muted-foreground">Receive automated payouts directly to your bank account or Stripe.</p>
            </div>
          </div>

          <div className="pt-2">
            <button
              type="button"
              onClick={() => navigate("/subscribe?plan=extreme")}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-extrabold text-xs shadow-lg transition-all cursor-pointer inline-flex items-center gap-2"
            >
              <Crown className="w-4 h-4" />
              <span>Upgrade to Extreme Plan ($50/mo)</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ── SECTION 1: AI-GENERATED WEBSITES READY TO RETAIL ── */}
      <div className="space-y-4 pt-2">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-base font-bold text-foreground flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#dfb180]" />
              <span>AI-Generated Websites Ready to Retail</span>
              <span className="px-2 py-0.5 rounded-full bg-[#c89666]/20 text-[#dfb180] text-[10px] font-bold">
                {readyToRetail.length}
              </span>
            </h4>
            <p className="text-xs text-muted-foreground">
              Websites synthesized in your Studio workspace. Click &ldquo;Retail on Marketplace&rdquo; to publish them for sale.
            </p>
          </div>
        </div>

        {readyToRetail.length === 0 ? (
          <div className="p-8 text-center rounded-2xl border border-dashed border-border/50 bg-card/20 space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-card border border-border/40 flex items-center justify-center mx-auto text-muted-foreground">
              <Cpu className="w-6 h-6 text-[#dfb180]" />
            </div>
            <div className="space-y-1">
              <h5 className="text-sm font-bold text-foreground">No Unlisted Generated Websites</h5>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                All of your generated websites are either already retailed or you haven&apos;t created one yet.
              </p>
            </div>
            <Link
              href="/studio"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#c89666] hover:bg-[#dfb180] text-black text-xs font-bold transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Open Studio Creator</span>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {readyToRetail.map((item) => (
              <div
                key={item.id}
                className="rounded-2xl border border-border/50 bg-card/40 hover:border-[#c89666]/40 transition-all p-4 flex flex-col justify-between space-y-3 group"
              >
                <div className="space-y-3">
                  <div className="aspect-video rounded-xl overflow-hidden bg-black/60 relative border border-white/5">
                    {item.thumbnail_url ? (
                      <img
                        src={item.thumbnail_url}
                        alt={item.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-2xl">
                        💻
                      </div>
                    )}
                    <span className="absolute top-2 left-2 px-2 py-0.5 rounded-full bg-black/70 backdrop-blur text-[9px] font-bold text-[#dfb180] border border-white/10 uppercase">
                      {item.framework || "HTML"}
                    </span>
                  </div>
                  <div>
                    <h5 className="font-bold text-sm text-foreground truncate" title={item.title}>
                      {item.title || "Untitled Generated Site"}
                    </h5>
                    <p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5">
                      {item.short_description || item.description || "Turnkey AI-generated website."}
                    </p>
                  </div>
                </div>

                <div className="pt-2 border-t border-border/40 flex items-center justify-between gap-2">
                  <a
                    href={`${API_BASE}/preview/live/${item.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[11px] font-bold text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
                  >
                    <Globe className="w-3 h-3" /> Demo
                  </a>

                  <button
                    type="button"
                    onClick={() => onRetailClick(item)}
                    className="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-[#c89666] to-[#b5804f] text-[#09090b] text-xs font-bold flex items-center gap-1.5 hover:opacity-95 transition cursor-pointer shadow-sm"
                  >
                    <ShoppingBag className="w-3.5 h-3.5" />
                    <span>Retail Site</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── SECTION 2: CURRENTLY RETAILED MARKETPLACE LISTINGS ── */}
      <div className="space-y-4 pt-6 border-t border-border/40">
        <div>
          <h4 className="text-base font-bold text-foreground flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Active Marketplace Retail Listings</span>
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 text-[10px] font-bold">
              {retailedListings.length}
            </span>
          </h4>
          <p className="text-xs text-muted-foreground">
            Templates you have retailed on the global marketplace. Other creators and clients can buy them.
          </p>
        </div>

        {retailedListings.length === 0 ? (
          <div className="p-6 text-center rounded-2xl border border-dashed border-border/40 bg-card/10 text-xs text-muted-foreground">
            No templates retailed yet. Select an AI-generated site above to retail it on the marketplace!
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {retailedListings.map((listing) => (
              <div
                key={listing.id}
                className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.03] p-4 flex flex-col justify-between space-y-3"
              >
                <div className="space-y-3">
                  <div className="aspect-video rounded-xl overflow-hidden bg-black/60 relative border border-white/5">
                    {listing.thumbnail_url ? (
                      <img
                        src={listing.thumbnail_url}
                        alt={listing.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-2xl">
                        🛍️
                      </div>
                    )}
                    <span className="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-black border border-emerald-500/30">
                      ${Number(listing.price || 0).toFixed(2)} USD
                    </span>
                  </div>
                  <div>
                    <h5 className="font-bold text-sm text-foreground truncate" title={listing.title}>
                      {listing.title}
                    </h5>
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-1">
                      <span>Downloads: <strong className="text-foreground">{listing.downloads_count || 0}</strong></span>
                      <span>Rating: <strong className="text-amber-400">★ {listing.rating_avg ? listing.rating_avg.toFixed(1) : "5.0"}</strong></span>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-border/30 flex items-center justify-between gap-2">
                  <Link
                    href={`/marketplace/${listing.slug || listing.id}`}
                    className="text-xs font-bold text-emerald-400 hover:text-emerald-300 inline-flex items-center gap-1"
                  >
                    <span>Live on Marketplace</span>
                    <ExternalLink className="w-3 h-3" />
                  </Link>

                  <button
                    type="button"
                    onClick={() => onRetailClick(listing)}
                    className="text-xs text-muted-foreground hover:text-foreground font-semibold px-2.5 py-1 rounded-lg bg-card border border-border/50 cursor-pointer"
                  >
                    Edit Listing
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
