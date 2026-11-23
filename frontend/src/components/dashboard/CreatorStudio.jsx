"use client";

import { useState, useMemo } from "react";
import {
  ShoppingBag,
  Store,
  Sparkles,
  ExternalLink,
  Crown,
  Zap,
  ArrowRight,
  Globe,
  CheckCircle2,
  Tag,
  DollarSign,
  TrendingUp,
  LayoutDashboard,
  Folder,
  PlusCircle,
  FileText,
  Wallet,
  BarChart3,
  Building2,
  Settings,
  Clock,
  AlertCircle,
  XCircle,
  Lock,
  ChevronRight,
  Eye,
  Download,
  Receipt,
  Loader2,
  RefreshCw,
  Search,
  Filter,
  Smartphone,
  CreditCard,
  Check,
  Copy,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import Link from "@/components/Link";
import RetailTemplateModal from "@/components/modals/RetailTemplateModal";
import "./CreatorStudio.css";

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

export default function CreatorStudio({
  user,
  authToken,
  onOpenPreview,
  initialTab = "overview",
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const isExtreme =
    user?.can_retail_templates ||
    user?.is_extreme_subscriber ||
    ["extreme", "agency", "enterprise"].includes(String(user?.subscription_tier || "").toLowerCase()) ||
    user?.role === "admin" ||
    user?.role === "super_admin";

  const [activeTab, setActiveTab] = useState(initialTab);
  const [templateFilter, setTemplateFilter] = useState("all");
  const [templateSearch, setTemplateSearch] = useState("");
  const [selectedTemplateForRetail, setSelectedTemplateForRetail] = useState(null);
  const [isRetailModalOpen, setIsRetailModalOpen] = useState(false);
  const [copiedStorefront, setCopiedStorefront] = useState(false);

  const handleCopyStorefront = (url) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(url);
      setCopiedStorefront(true);
      setTimeout(() => setCopiedStorefront(false), 2000);
    }
  };

  // Payout request modal state
  const [isPayoutModalOpen, setIsPayoutModalOpen] = useState(false);
  const [payoutAmount, setPayoutAmount] = useState("");
  const [payoutError, setPayoutError] = useState("");
  const [payoutSuccess, setPayoutSuccess] = useState("");

  // Payout settings form state
  const [payoutMethod, setPayoutMethod] = useState(user?.payout_method || "bank");
  const [bankName, setBankName] = useState(user?.payout_bank_name || "");
  const [accountNumber, setAccountNumber] = useState(user?.payout_account_number || "");
  const [ifscCode, setIfscCode] = useState(user?.payout_ifsc_code || "");
  const [accountHolder, setAccountHolder] = useState(user?.payout_account_holder_name || "");
  const [upiId, setUpiId] = useState(user?.payout_razorpay_vpa || user?.creator_payout_details?.upi_id || "");
  const [stripeEmail, setStripeEmail] = useState(user?.payout_stripe_email || user?.creator_payout_details?.stripe_email || "");
  const [isSavingBank, setIsSavingBank] = useState(false);
  const [bankSaveMessage, setBankSaveMessage] = useState("");

  // Fetch Creator Earnings & Financial Ledger
  const {
    data: earningsData,
    isLoading: isEarningsLoading,
    refetch: refetchEarnings,
  } = useQuery({
    queryKey: ["creator-earnings", user?.id],
    queryFn: async () => {
      return await api.get("/payouts/earnings", authToken);
    },
    enabled: !!authToken && isExtreme,
    staleTime: 1000 * 30,
  });

  // Fetch Creator's Templates
  const {
    data: myTemplates = [],
    isLoading: isTemplatesLoading,
    refetch: refetchTemplates,
  } = useQuery({
    queryKey: ["creator-templates", user?.id],
    queryFn: async () => {
      const res = await api.get("/templates/my-templates", authToken);
      return Array.isArray(res) ? res : res?.items || [];
    },
    enabled: !!authToken && isExtreme,
    staleTime: 1000 * 30,
  });

  // Fetch Withdrawal Requests
  const {
    data: withdrawals = [],
    isLoading: isWithdrawalsLoading,
    refetch: refetchWithdrawals,
  } = useQuery({
    queryKey: ["creator-withdrawals", user?.id],
    queryFn: async () => {
      const res = await api.get("/payouts/withdrawals", authToken);
      return Array.isArray(res) ? res : [];
    },
    enabled: !!authToken && isExtreme,
    staleTime: 1000 * 30,
  });

  // Resubmit rejected template for review
  const resubmitMutation = useMutation({
    mutationFn: async (templateId) => {
      return await api.post(`/templates/${templateId}/submit-review`, {}, authToken);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["creator-templates"] });
      queryClient.invalidateQueries({ queryKey: ["creator-earnings"] });
    },
  });

  // Submit withdrawal request
  const handleWithdrawalSubmit = async (e) => {
    e.preventDefault();
    setPayoutError("");
    setPayoutSuccess("");
    const amountNum = Number(payoutAmount);
    const available = Number(earningsData?.available_balance || 0);

    if (isNaN(amountNum) || amountNum <= 0) {
      setPayoutError("Please enter a valid withdrawal amount.");
      return;
    }
    if (amountNum > available) {
      setPayoutError(`Amount exceeds your available balance ($${available.toFixed(2)}).`);
      return;
    }

    try {
      await api.post(
        "/payouts/withdrawals",
        {
          amount: amountNum,
          payout_method: payoutMethod,
          upi_id: upiId || undefined,
          stripe_email: stripeEmail || undefined,
          bank_name: bankName || undefined,
          account_number: accountNumber || undefined,
          ifsc_code: ifscCode || undefined,
          account_holder_name: accountHolder || undefined,
        },
        authToken
      );
      setPayoutSuccess("Withdrawal request submitted successfully! Funds will be reviewed and disbursed.");
      setPayoutAmount("");
      refetchEarnings();
      refetchWithdrawals();
      setTimeout(() => {
        setIsPayoutModalOpen(false);
        setPayoutSuccess("");
      }, 2500);
    } catch (err) {
      setPayoutError(err?.response?.data?.detail || err?.message || "Failed to submit withdrawal request.");
    }
  };

  // Ready to retail: AI Studio generated drafts not yet submitted to the marketplace
  const readyToRetail = useMemo(() => {
    return myTemplates.filter((item) => isStudioProjectItem(item) && !item.is_marketplace);
  }, [myTemplates]);

  // Filtered templates list for the My Templates tab
  const filteredTemplates = useMemo(() => {
    return myTemplates.filter((t) => {
      const status = String(t.status || "").toLowerCase();
      if (templateFilter === "published" && status !== "published") return false;
      if (templateFilter === "review" && !["submitted", "under_review"].includes(status)) return false;
      if (templateFilter === "rejected" && status !== "rejected") return false;
      if (templateFilter === "draft" && status !== "draft") return false;

      if (templateSearch.trim()) {
        const q = templateSearch.toLowerCase();
        return (
          t.title?.toLowerCase().includes(q) ||
          t.description?.toLowerCase().includes(q) ||
          t.slug?.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [myTemplates, templateFilter, templateSearch]);

  // ═══════════════════════════════════════════════════════════════════════════
  // CASE 1: USER IS NOT ON EXTREME PLAN -> SHOW PROFESSIONAL UPGRADE SCREEN
  // ═══════════════════════════════════════════════════════════════════════════
  if (!isExtreme) {
    return (
      <div className="cs-wrapper">
        <div className="cs-gate-container">
          <div className="cs-gate-icon-wrap">
            <Crown className="w-10 h-10 text-[#dfb180]" />
          </div>

          <div>
            <span className="cs-tier-badge">Extreme Plan Privilege</span>
            <h2 className="cs-gate-title mt-2">Unlock the Creator Studio</h2>
            <p className="cs-gate-text mt-2">
              Transform your AI-generated websites into an automated revenue stream. Upgrade to the
              <strong> Extreme Plan ($50/mo)</strong> to retail your generated websites on the global marketplace and
              keep <strong>80% creator revenue</strong> from every sale.
            </p>
          </div>

          <div className="cs-gate-pricing">
            <span className="cs-gate-price-big">$50</span>
            <span className="cs-gate-price-sub">/ month (or $500/year)</span>
          </div>

          <div className="cs-gate-features">
            <div className="cs-gate-feat-item">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <strong>Retail AI Websites:</strong> Sell your generated websites with zero coding required.
              </div>
            </div>
            <div className="cs-gate-feat-item">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <strong>80% Revenue Share:</strong> Keep the majority of every purchase directly in your bank account.
              </div>
            </div>
            <div className="cs-gate-feat-item">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <strong>Creator Dashboard:</strong> Real-time sales logs, analytics, customer ledger, and earnings charts.
              </div>
            </div>
            <div className="cs-gate-feat-item">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <strong>Fast Payouts:</strong> Automated 7-day holding clearance with direct bank withdrawals.
              </div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-3 w-full justify-center mt-2">
            <button
              type="button"
              onClick={() => navigate("/pricing")}
              className="cs-btn-primary px-6 py-3 text-sm w-full sm:w-auto justify-center"
            >
              <Zap className="w-4 h-4" />
              <span>Upgrade to Extreme Plan</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <Link
              href="/marketplace"
              className="cs-btn-secondary px-6 py-3 text-sm w-full sm:w-auto justify-center"
            >
              <ExternalLink className="w-4 h-4" />
              <span>Explore Marketplace</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // CASE 2: ACTIVE EXTREME CREATOR -> COMPLETE 8-TAB CREATOR STUDIO
  // ═══════════════════════════════════════════════════════════════════════════

  const grossSales = Number(earningsData?.gross_sales || 0);
  const netEarnings = Number(earningsData?.net_earnings || earningsData?.total_earned || 0);
  const platformFee = Number(earningsData?.platform_commission || 0);
  const availableBalance = Number(earningsData?.available_balance || 0);
  const pendingEarnings = Number(earningsData?.pending_earnings || 0);
  const commissionRate = Number(earningsData?.commission_rate || 20);
  const holdingDays = Number(earningsData?.holding_days || 7);
  const publishedCount = Number(earningsData?.published_templates_count || 0);
  const pendingCount = Number(earningsData?.pending_templates_count || 0);
  const totalViews = Number(earningsData?.total_views || 0);
  const totalPurchases = Number(earningsData?.total_purchases || earningsData?.sales?.length || 0);
  const recentOrders = earningsData?.recent_orders || [];
  const bestTemplates = earningsData?.best_performing_templates || [];

  return (
    <div className="cs-wrapper">
      {/* ── Top Header ──────────────────────────────────────────────────────── */}
      <div className="cs-header">
        <div className="cs-header-left">
          <div className="cs-avatar-wrap">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt={user.full_name} className="cs-avatar-img" />
            ) : (
              <Crown className="w-6 h-6 text-[#dfb180]" />
            )}
          </div>
          <div className="cs-title-wrap">
            <div className="cs-title-row">
              <h2 className="cs-title">{user?.full_name || user?.username || "Extreme Creator"}</h2>
              <span className="cs-tier-badge">
                <Crown className="w-3.5 h-3.5" />
                Verified Extreme Creator
              </span>
            </div>
            <p className="cs-subtitle">
              Manage your retailed website templates, sales ledger, real-time analytics, and payouts.
            </p>
          </div>
        </div>

        <div className="cs-header-actions">
          <Link
            href={user?.creator_store_slug ? `/creator/${user.creator_store_slug}` : "/creator/setup"}
            className="cs-btn-secondary"
            title="View Your Dedicated Storefront on Our Domain"
          >
            <Store className="w-4 h-4 text-[#dfb180]" />
            <span>{user?.creator_store_slug ? "My Storefront" : "Storefront Setup"}</span>
          </Link>
          <button
            type="button"
            onClick={() => setActiveTab("add-template")}
            className="cs-btn-primary"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Retail New Website</span>
          </button>
          <Link href="/marketplace" className="cs-btn-secondary">
            <ExternalLink className="w-4 h-4" />
            <span>View Marketplace</span>
          </Link>
        </div>
      </div>

      {/* ── Navigation Tabs Bar (8 Tabs) ────────────────────────────────────── */}
      <div className="cs-nav-bar">
        <button
          type="button"
          onClick={() => setActiveTab("overview")}
          className={`cs-nav-btn ${activeTab === "overview" ? "active" : ""}`}
        >
          <LayoutDashboard className="w-4 h-4" />
          <span>Overview</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("templates")}
          className={`cs-nav-btn ${activeTab === "templates" ? "active" : ""}`}
        >
          <Folder className="w-4 h-4" />
          <span>My Templates</span>
          {myTemplates.length > 0 && <span className="cs-nav-count">{myTemplates.length}</span>}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("add-template")}
          className={`cs-nav-btn ${activeTab === "add-template" ? "active" : ""}`}
        >
          <PlusCircle className="w-4 h-4" />
          <span>Add New Template</span>
          {readyToRetail.length > 0 && (
            <span className="cs-nav-count ready">
              {readyToRetail.length} ready
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("orders")}
          className={`cs-nav-btn ${activeTab === "orders" ? "active" : ""}`}
        >
          <FileText className="w-4 h-4" />
          <span>Sales & Orders</span>
          {totalPurchases > 0 && <span className="cs-nav-count">{totalPurchases}</span>}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("earnings")}
          className={`cs-nav-btn ${activeTab === "earnings" ? "active" : ""}`}
        >
          <DollarSign className="w-4 h-4" />
          <span>Earnings</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("analytics")}
          className={`cs-nav-btn ${activeTab === "analytics" ? "active" : ""}`}
        >
          <BarChart3 className="w-4 h-4" />
          <span>Analytics</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("payouts")}
          className={`cs-nav-btn ${activeTab === "payouts" ? "active" : ""}`}
        >
          <Wallet className="w-4 h-4" />
          <span>Payouts</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("settings")}
          className={`cs-nav-btn ${activeTab === "settings" ? "active" : ""}`}
        >
          <Settings className="w-4 h-4" />
          <span>Creator Settings</span>
        </button>
      </div>

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 1: OVERVIEW                                                       */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Metrics Grid */}
          <div className="cs-metrics-grid">
            <div className="cs-metric-card gold">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Gross Sales</span>
                <div className="cs-metric-icon-wrap gold">
                  <DollarSign className="w-4 h-4" />
                </div>
              </div>
              <div className="cs-metric-value">${grossSales.toFixed(2)}</div>
              <div className="cs-metric-subtext">
                <span className="cs-metric-pill emerald">Volume</span>
                <span>Total customer checkouts</span>
              </div>
            </div>

            <div className="cs-metric-card emerald">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Net Creator Earnings</span>
                <div className="cs-metric-icon-wrap emerald">
                  <TrendingUp className="w-4 h-4" />
                </div>
              </div>
              <div className="cs-metric-value" style={{ color: "#34d399" }}>${netEarnings.toFixed(2)}</div>
              <div className="cs-metric-subtext">
                <span className="cs-metric-pill emerald">{100 - commissionRate}% share</span>
                <span>Creator take-home</span>
              </div>
            </div>

            <div className="cs-metric-card emerald">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Available Balance</span>
                <div className="cs-metric-icon-wrap emerald">
                  <Wallet className="w-4 h-4" />
                </div>
              </div>
              <div className="cs-metric-value">${availableBalance.toFixed(2)}</div>
              <div className="cs-metric-subtext">
                <span className="cs-metric-pill emerald">Ready</span>
                <span>Withdrawable now</span>
              </div>
            </div>

            <div className="cs-metric-card amber">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Pending Balance</span>
                <div className="cs-metric-icon-wrap amber">
                  <Clock className="w-4 h-4" />
                </div>
              </div>
              <div className="cs-metric-value" style={{ color: "#fbbf24" }}>${pendingEarnings.toFixed(2)}</div>
              <div className="cs-metric-subtext">
                <span className="cs-metric-pill amber">{holdingDays}d hold</span>
                <span>Dispute holding escrow</span>
              </div>
            </div>

            <div className="cs-metric-card indigo">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Published Templates</span>
                <div className="cs-metric-icon-wrap indigo">
                  <Globe className="w-4 h-4" />
                </div>
              </div>
              <div className="cs-metric-value">{publishedCount}</div>
              <div className="cs-metric-subtext">
                <span className="cs-metric-pill blue">Live</span>
                <span>Live in catalog</span>
              </div>
            </div>

            <div className="cs-metric-card purple">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Under Admin Review</span>
                <div className="cs-metric-icon-wrap purple">
                  <Clock className="w-4 h-4" />
                </div>
              </div>
              <div className="cs-metric-value">{pendingCount}</div>
              <div className="cs-metric-subtext">
                <span className="cs-metric-pill purple">Pending</span>
                <span>Fast moderation queue</span>
              </div>
            </div>

            <div className="cs-metric-card cyan">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Total Views</span>
                <div className="cs-metric-icon-wrap cyan">
                  <Eye className="w-4 h-4" />
                </div>
              </div>
              <div className="cs-metric-value">{totalViews}</div>
              <div className="cs-metric-subtext">
                <span className="cs-metric-pill cyan">Impressions</span>
                <span>Verified template views</span>
              </div>
            </div>

            <div className="cs-metric-card rose">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Total Purchases</span>
                <div className="cs-metric-icon-wrap rose">
                  <ShoppingBag className="w-4 h-4" />
                </div>
              </div>
              <div className="cs-metric-value">{totalPurchases}</div>
              <div className="cs-metric-subtext">
                <span className="cs-metric-pill pink">Orders</span>
                <span>Completed orders</span>
              </div>
            </div>
          </div>

          {/* Dedicated Creator Storefront Banner */}
          <div className="cs-storefront-banner">
            <div className="cs-storefront-left">
              <div className="cs-storefront-icon">
                <Store className="w-6 h-6" />
              </div>
              <div>
                <div className="cs-storefront-title-row">
                  <h4 className="cs-storefront-title">
                    Your Dedicated Storefront on Our Domain
                  </h4>
                  <span className="cs-storefront-tag">
                    {user?.creator_brand_name || "Branded"}
                  </span>
                </div>
                <div className="cs-storefront-desc">
                  {user?.creator_store_slug ? (
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                      <span>Live at:</span>
                      <code>/creator/{user.creator_store_slug}</code>
                      <button
                        type="button"
                        onClick={() =>
                          handleCopyStorefront(
                            `${typeof window !== "undefined" ? window.location.origin : ""}/creator/${user.creator_store_slug}`
                          )
                        }
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.25rem",
                          background: "rgba(255, 255, 255, 0.08)",
                          border: "1px solid rgba(255, 255, 255, 0.15)",
                          borderRadius: "0.4rem",
                          padding: "0.15rem 0.5rem",
                          color: "#f1f5f9",
                          fontSize: "0.7rem",
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        {copiedStorefront ? (
                          <>
                            <Check className="w-3 h-3 text-emerald-400" />
                            <span style={{ color: "#34d399" }}>Copied!</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3" />
                            <span>Copy Link</span>
                          </>
                        )}
                      </button>
                      <span style={{ color: "#64748b" }}>•</span>
                      <span>
                        Gateway:{" "}
                        <strong style={{ color: "#e2e8f0", textTransform: "capitalize" }}>
                          {user.payout_method || "Stripe"}
                        </strong>
                      </span>
                      <span style={{ color: "#64748b" }}>•</span>
                      <span>
                        Distribution:{" "}
                        <strong style={{ color: "#e2e8f0", textTransform: "capitalize" }}>
                          {user.storefront_distribution || "Dual (Both)"}
                        </strong>
                      </span>
                    </div>
                  ) : (
                    "Set up your studio name, logo, banner, and payout gateways (Stripe, Razorpay, UPI, Bank) to activate your live storefront URL on our domain."
                  )}
                </div>
              </div>
            </div>
            <div className="cs-storefront-actions">
              {user?.creator_store_slug ? (
                <Link
                  href={`/creator/${user.creator_store_slug}`}
                  className="cs-btn-primary"
                >
                  <Store className="w-3.5 h-3.5" />
                  <span>Visit Storefront</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>
              ) : null}
              <Link
                href="/creator/setup"
                className="cs-btn-secondary"
              >
                <Settings className="w-3.5 h-3.5" />
                <span>{user?.creator_store_slug ? "Edit Setup" : "Setup Storefront"}</span>
              </Link>
            </div>
          </div>

          {/* Quick Retailing Banner if User Has Generated Sites Ready to Retail */}
          {readyToRetail.length > 0 && (
            <div className="cs-retail-banner">
              <div className="cs-retail-left">
                <div className="cs-retail-icon">
                  <Sparkles className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="cs-retail-title">
                    You have {readyToRetail.length} AI-generated website{readyToRetail.length > 1 ? "s" : ""} ready to retail!
                  </h4>
                  <p className="cs-retail-desc">
                    Publish your customized websites directly to the global marketplace and start earning revenue with automated 80% splits.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActiveTab("add-template")}
                className="cs-retail-btn"
              >
                <span>Select &amp; Retail Now</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Two-Column Layout: Recent Orders & Best Performing Templates */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Orders */}
            <div className="cs-card">
              <div className="cs-card-header">
                <div>
                  <h3 className="cs-card-title">Recent Orders</h3>
                  <p className="cs-card-desc">Latest customer purchases of your templates</p>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("orders")}
                  className="text-xs font-semibold text-[#dfb180] hover:underline"
                >
                  View all ({totalPurchases})
                </button>
              </div>

              {recentOrders.length === 0 ? (
                <div className="cs-empty-state">
                  <div className="cs-empty-icon gold">
                    <ShoppingBag className="w-6 h-6" />
                  </div>
                  <h4 className="cs-empty-title">No customer orders yet</h4>
                  <p className="cs-empty-desc">
                    When buyers purchase your templates, transactions, buyer info, and real-time 80% splits will appear here.
                  </p>
                  <div className="cs-empty-action">
                    <Link href="/marketplace" className="cs-btn-secondary text-xs">
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>View Marketplace Catalog</span>
                    </Link>
                  </div>
                </div>
              ) : (
                <div className="cs-table-wrap">
                  <table className="cs-table">
                    <thead>
                      <tr>
                        <th>Order</th>
                        <th>Template</th>
                        <th>Net Earning</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentOrders.map((ord, idx) => (
                        <tr key={idx}>
                          <td>
                            <span className="font-mono text-xs">{ord.order_number}</span>
                          </td>
                          <td className="font-medium max-w-[140px] truncate">{ord.template_title}</td>
                          <td className="font-bold text-emerald-400">${Number(ord.net).toFixed(2)}</td>
                          <td>
                            {ord.is_available ? (
                              <span className="cs-badge cs-badge-success">Available</span>
                            ) : (
                              <span className="cs-badge cs-badge-warning">Holding</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Best Performing Templates */}
            <div className="cs-card">
              <div className="cs-card-header">
                <div>
                  <h3 className="cs-card-title">Top Performing Templates</h3>
                  <p className="cs-card-desc">Ranked by real customer sales volume</p>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("templates")}
                  className="text-xs font-semibold text-[#dfb180] hover:underline"
                >
                  Manage listings
                </button>
              </div>

              {bestTemplates.length === 0 ? (
                <div className="cs-empty-state">
                  <div className="cs-empty-icon gold">
                    <TrendingUp className="w-6 h-6" />
                  </div>
                  <h4 className="cs-empty-title">No performance data yet</h4>
                  <p className="cs-empty-desc">
                    Publish your AI-generated websites to start tracking customer views, conversions, and top-selling templates.
                  </p>
                  <div className="cs-empty-action">
                    <button
                      type="button"
                      onClick={() => setActiveTab("add-template")}
                      className="cs-btn-primary text-xs"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Retail First Website</span>
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {bestTemplates.map((t, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 rounded-xl bg-black/40 border border-white/10 gap-3"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {t.thumbnail_url ? (
                          <img
                            src={t.thumbnail_url}
                            alt={t.title}
                            className="w-10 h-10 rounded-lg object-cover shrink-0 border border-white/10"
                          />
                        ) : (
                          <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center shrink-0 border border-white/10">
                            <Globe className="w-5 h-5 text-muted-foreground" />
                          </div>
                        )}
                        <div className="min-w-0">
                          <h4 className="font-bold text-xs text-foreground truncate">{t.title}</h4>
                          <span className="text-[11px] text-muted-foreground">
                            {t.sales_count} sale{t.sales_count > 1 ? "s" : ""} • ${Number(t.price).toFixed(2)}
                          </span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="font-extrabold text-xs text-emerald-400">
                          +${Number(t.total_gross * 0.8).toFixed(2)}
                        </div>
                        <span className="text-[10px] text-muted-foreground">Creator share</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 2: MY TEMPLATES                                                   */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === "templates" && (
        <div className="cs-card">
          <div className="cs-card-header">
            <div>
              <h3 className="cs-card-title">My Template Listings</h3>
              <p className="cs-card-desc">Review your published, pending review, and draft websites</p>
            </div>

            <button
              type="button"
              onClick={() => setActiveTab("add-template")}
              className="cs-btn-primary"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Retail Website</span>
            </button>
          </div>

          {/* Filters & Search */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
            <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
              {["all", "published", "review", "draft", "rejected"].map((flt) => (
                <button
                  key={flt}
                  type="button"
                  onClick={() => setTemplateFilter(flt)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-colors ${
                    templateFilter === flt
                      ? "bg-[#dfb180]/15 text-[#dfb180] border border-[#dfb180]/30"
                      : "text-muted-foreground hover:bg-secondary/40"
                  }`}
                >
                  {flt === "review" ? "Under Review" : flt}
                </button>
              ))}
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={templateSearch}
                onChange={(e) => setTemplateSearch(e.target.value)}
                placeholder="Search your templates..."
                className="cs-input pl-8 py-1.5 text-xs"
              />
            </div>
          </div>

          {/* Template Grid */}
          {filteredTemplates.length === 0 ? (
            <div className="py-12 text-center text-xs text-muted-foreground">
              No templates found matching your filter.
            </div>
          ) : (
            <div className="cs-template-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
              {filteredTemplates.map((t) => {
                const statusStr = String(t.status || "").toLowerCase();
                const isPublished = statusStr === "published";
                const isUnderReview = ["submitted", "under_review"].includes(statusStr);
                const isRejected = statusStr === "rejected";

                return (
                  <div
                    key={t.id}
                    className="cs-item-card"
                  >
                    <div>
                      {/* Image Preview */}
                      <div className="relative aspect-video rounded-lg overflow-hidden bg-secondary/30 mb-3 border border-border/20">
                        {t.thumbnail_url ? (
                          <img src={t.thumbnail_url} alt={t.title} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                            <Globe className="w-8 h-8 opacity-40" />
                          </div>
                        )}
                        <div className="absolute top-2 right-2">
                          {isPublished && <span className="cs-badge cs-badge-success">Published</span>}
                          {isUnderReview && <span className="cs-badge cs-badge-warning">Under Review</span>}
                          {isRejected && <span className="cs-badge cs-badge-danger">Rejected</span>}
                          {!isPublished && !isUnderReview && !isRejected && (
                            <span className="cs-badge cs-badge-neutral">Draft</span>
                          )}
                        </div>
                      </div>

                      <h4 className="font-bold text-sm text-foreground truncate">{t.title}</h4>
                      <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                        {t.short_description || t.description || "No description provided."}
                      </p>

                      {/* Rejection notice */}
                      {isRejected && t.rejection_reason && (
                        <div className="mt-2.5 p-2.5 rounded-lg bg-red-500/10 border border-red-500/25 text-red-400 text-xs">
                          <strong>Admin Feedback:</strong> {t.rejection_reason}
                        </div>
                      )}
                    </div>

                    <div className="pt-3 border-t border-border/30 flex items-center justify-between gap-2">
                      <div>
                        <div className="text-[10px] text-muted-foreground uppercase font-bold">Price</div>
                        <div className="text-sm font-extrabold text-foreground">
                          ${Number(t.price || 0).toFixed(2)}
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5">
                        {t.preview_url && (
                          <button
                            type="button"
                            onClick={() => onOpenPreview ? onOpenPreview(t) : window.open(t.preview_url, "_blank")}
                            className="p-1.5 rounded-lg bg-secondary hover:bg-secondary/80 text-foreground transition-colors"
                            title="Live Preview"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {isRejected && (
                          <button
                            type="button"
                            onClick={() => resubmitMutation.mutate(t.id)}
                            disabled={resubmitMutation.isPending}
                            className="px-2.5 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-400 text-xs font-bold transition-colors"
                          >
                            Resubmit
                          </button>
                        )}

                        {!t.is_marketplace && (
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedTemplateForRetail(t);
                              setIsRetailModalOpen(true);
                            }}
                            className="cs-btn-primary px-3 py-1.5 text-xs"
                          >
                            <span>Retail</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 3: ADD NEW TEMPLATE (RETAIL GENERATED WEBSITE WIZARD)            */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === "add-template" && (
        <div className="cs-card">
          <div className="cs-card-header">
            <div>
              <h3 className="cs-card-title">Retail an AI-Generated Website</h3>
              <p className="cs-card-desc">
                Select an eligible website created with Site Studio and list it for retail on the global marketplace.
              </p>
            </div>
            <Link href="/studio" className="cs-btn-secondary">
              <Sparkles className="w-4 h-4" />
              <span>Generate New in Studio</span>
            </Link>
          </div>

          {readyToRetail.length === 0 ? (
            <div className="py-12 text-center flex flex-col items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-secondary/40 flex items-center justify-center">
                <Globe className="w-6 h-6 text-muted-foreground" />
              </div>
              <h4 className="font-bold text-sm text-foreground">No un-retailed websites available</h4>
              <p className="text-xs text-muted-foreground max-w-md">
                Generate a custom website in AI Site Studio first. Once your website is generated, it will immediately
                appear here ready to be retailed.
              </p>
              <Link href="/studio" className="cs-btn-primary mt-2">
                <Sparkles className="w-4 h-4" />
                <span>Open AI Site Studio</span>
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Select one of your AI-generated websites below to customize its title, price, category, and submit for
                marketplace review:
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {readyToRetail.map((item) => (
                  <div
                    key={item.id}
                    className="cs-item-card group"
                  >
                    <div>
                      <div className="relative aspect-video rounded-lg overflow-hidden bg-secondary/30 mb-3 border border-border/20">
                        {item.thumbnail_url ? (
                          <img src={item.thumbnail_url} alt={item.title} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                            <Sparkles className="w-8 h-8 opacity-40 text-[#dfb180]" />
                          </div>
                        )}
                        <span className="absolute top-2 left-2 cs-badge cs-badge-info">
                          AI Generated
                        </span>
                      </div>

                      <h4 className="font-bold text-sm text-foreground truncate">{item.title}</h4>
                      <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                        {item.short_description || "Turnkey AI-generated website ready for production deployment."}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTemplateForRetail(item);
                        setIsRetailModalOpen(true);
                      }}
                      className="cs-btn-primary w-full justify-center text-xs py-2 mt-2"
                    >
                      <Tag className="w-3.5 h-3.5" />
                      <span>Configure &amp; Retail</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 4: SALES & ORDERS                                                 */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === "orders" && (
        <div className="cs-card">
          <div className="cs-card-header">
            <div>
              <h3 className="cs-card-title">Sales &amp; Customer Orders</h3>
              <p className="cs-card-desc">Comprehensive order ledger of all buyer purchases for your templates</p>
            </div>
          </div>

          {(!earningsData?.sales || earningsData.sales.length === 0) ? (
            <div className="py-12 text-center text-xs text-muted-foreground">
              No sales recorded yet. Once customers purchase your published templates, every transaction will be logged
              here with buyer information, commission split, and dispute clearance dates.
            </div>
          ) : (
            <div className="cs-table-wrap">
              <table className="cs-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Order #</th>
                    <th>Template</th>
                    <th>Customer</th>
                    <th>License</th>
                    <th>Gross</th>
                    <th>Platform Fee</th>
                    <th>Your Earning</th>
                    <th>Hold Status</th>
                  </tr>
                </thead>
                <tbody>
                  {earningsData.sales.map((sale, idx) => (
                    <tr key={idx}>
                      <td className="text-xs text-muted-foreground whitespace-nowrap">
                        {new Date(sale.date).toLocaleDateString()}
                      </td>
                      <td className="font-mono text-xs font-bold">{sale.order_number}</td>
                      <td className="font-medium max-w-[160px] truncate">{sale.template_title}</td>
                      <td className="text-xs text-muted-foreground">{sale.purchaser_email}</td>
                      <td className="capitalize text-xs font-semibold">{sale.license_type}</td>
                      <td className="font-medium">${Number(sale.gross_amount || sale.price).toFixed(2)}</td>
                      <td className="text-xs text-muted-foreground">
                        -${Number(sale.platform_fee || 0).toFixed(2)}
                      </td>
                      <td className="font-extrabold text-emerald-400">
                        +${Number(sale.net_creator_earning || sale.price * 0.8).toFixed(2)}
                      </td>
                      <td>
                        {sale.is_available ? (
                          <span className="cs-badge cs-badge-success">Available</span>
                        ) : (
                          <span
                            className="cs-badge cs-badge-warning"
                            title={`Held until ${new Date(sale.holding_until).toLocaleDateString()}`}
                          >
                            Hold ({holdingDays}d)
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 5: EARNINGS & DISPUTE HOLDING LEDGER                              */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === "earnings" && (
        <div className="space-y-6">
          <div className="cs-metrics-grid">
            <div className="cs-metric-card">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Gross Revenue</span>
                <DollarSign className="w-4 h-4 text-[#dfb180]" />
              </div>
              <div className="cs-metric-value">${grossSales.toFixed(2)}</div>
              <div className="cs-metric-subtext">Total buyer checkouts</div>
            </div>

            <div className="cs-metric-card">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Platform Fee ({commissionRate}%)</span>
                <PercentIcon className="w-4 h-4 text-muted-foreground" />
              </div>
              <div className="cs-metric-value text-muted-foreground">-${platformFee.toFixed(2)}</div>
              <div className="cs-metric-subtext">Infrastructure &amp; delivery</div>
            </div>

            <div className="cs-metric-card">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Net Creator Earnings</span>
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="cs-metric-value text-emerald-400">${netEarnings.toFixed(2)}</div>
              <div className="cs-metric-subtext">80% creator take-home</div>
            </div>

            <div className="cs-metric-card">
              <div className="cs-metric-top">
                <span className="cs-metric-label">Withdrawn Amount</span>
                <Download className="w-4 h-4 text-blue-400" />
              </div>
              <div className="cs-metric-value">${Number(earningsData?.withdrawn_amount || 0).toFixed(2)}</div>
              <div className="cs-metric-subtext">Disbursed to your bank</div>
            </div>
          </div>

          {/* Holding Period Policy Banner */}
          <div className="p-5 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200 flex items-start gap-3">
            <Clock className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <strong className="font-bold text-amber-300">
                Dispute &amp; Refund Protection Holding Window ({holdingDays} Days):
              </strong>
              <p className="text-muted-foreground leading-relaxed">
                To protect our marketplace against payment disputes and unauthorized card activity, earnings from each
                sale are placed in pending escrow for <strong>{holdingDays} calendar days</strong> after purchase. Once
                the holding window elapses, the net funds automatically become <strong>Available Balance</strong> and can
                be withdrawn immediately to your bank.
              </p>
            </div>
          </div>

          {/* Balance Breakdown Card */}
          <div className="cs-card">
            <h3 className="cs-card-title">Withdrawal Eligibility Summary</h3>
            <div className="space-y-3 pt-2">
              <div className="flex justify-between items-center py-2 border-b border-border/30 text-sm">
                <span className="text-muted-foreground">Cleared &amp; Available for Withdrawal</span>
                <span className="font-bold text-emerald-400 text-base">${availableBalance.toFixed(2)}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-border/30 text-sm">
                <span className="text-muted-foreground">Pending Dispute Window Clearance</span>
                <span className="font-bold text-amber-400">${pendingEarnings.toFixed(2)}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-border/30 text-sm">
                <span className="text-muted-foreground">Pending Withdrawal Requests</span>
                <span className="font-bold text-foreground">
                  ${Number(earningsData?.pending_withdrawal || 0).toFixed(2)}
                </span>
              </div>
            </div>

            <div className="pt-2">
              <button
                type="button"
                onClick={() => {
                  setActiveTab("payouts");
                  setIsPayoutModalOpen(true);
                }}
                disabled={availableBalance <= 0}
                className="cs-btn-primary"
              >
                <Wallet className="w-4 h-4" />
                <span>Request Payout (${availableBalance.toFixed(2)})</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 6: ANALYTICS                                                      */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === "analytics" && (
        <div className="space-y-6">
          <div className="cs-card">
            <div className="cs-card-header">
              <div>
                <h3 className="cs-card-title">Marketplace Performance &amp; Conversion</h3>
                <p className="cs-card-desc">Track visitor engagement and sales conversions</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div className="p-4 rounded-xl bg-card border border-border/40">
                <div className="text-xs text-muted-foreground font-semibold uppercase">Total Views</div>
                <div className="text-2xl font-extrabold text-foreground mt-1">{totalViews}</div>
                <div className="text-xs text-muted-foreground mt-0.5">Across all listings</div>
              </div>

              <div className="p-4 rounded-xl bg-card border border-border/40">
                <div className="text-xs text-muted-foreground font-semibold uppercase">Total Purchases</div>
                <div className="text-2xl font-extrabold text-foreground mt-1">{totalPurchases}</div>
                <div className="text-xs text-muted-foreground mt-0.5">Successful checkouts</div>
              </div>

              <div className="p-4 rounded-xl bg-card border border-border/40">
                <div className="text-xs text-muted-foreground font-semibold uppercase">Conversion Rate</div>
                <div className="text-2xl font-extrabold text-emerald-400 mt-1">
                  {totalViews > 0 ? ((totalPurchases / totalViews) * 100).toFixed(1) : "0.0"}%
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">View-to-purchase ratio</div>
              </div>
            </div>
          </div>

          {/* Sales Chart */}
          <div className="cs-card">
            <h3 className="cs-card-title">Recent Sales Velocity</h3>
            <p className="cs-card-desc">Daily net revenue breakdown</p>

            {(!earningsData?.sales_chart || earningsData.sales_chart.length === 0) ? (
              <div className="py-12 text-center text-xs text-muted-foreground">
                No recent transactions to chart. Sales trends will populate as orders are completed.
              </div>
            ) : (
              <div className="space-y-3 pt-4">
                {earningsData.sales_chart.map((point, idx) => (
                  <div key={idx} className="flex items-center gap-3 text-xs">
                    <span className="w-24 text-muted-foreground font-mono">{point.date}</span>
                    <div className="flex-1 bg-secondary/40 h-4 rounded-full overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-[#c89666] to-[#dfb180] h-full rounded-full transition-all"
                        style={{
                          width: `${Math.min(100, (point.net / (grossSales || 1)) * 100)}%`,
                        }}
                      />
                    </div>
                    <span className="w-16 font-extrabold text-emerald-400 text-right">
                      +${Number(point.net).toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 7: PAYOUTS                                                        */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === "payouts" && (
        <div className="space-y-6">
          <div className="cs-card">
            <div className="cs-card-header">
              <div>
                <h3 className="cs-card-title">Payouts &amp; Withdrawals</h3>
                <p className="cs-card-desc">Disburse your available creator balance directly to your bank account</p>
              </div>

              <button
                type="button"
                onClick={() => setIsPayoutModalOpen(true)}
                disabled={availableBalance <= 0}
                className="cs-btn-primary"
              >
                <Wallet className="w-4 h-4" />
                <span>Request Payout</span>
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                <div className="text-xs text-emerald-400 font-bold uppercase">Available to Withdraw</div>
                <div className="text-3xl font-extrabold text-emerald-400 mt-1">${availableBalance.toFixed(2)}</div>
                <div className="text-xs text-muted-foreground mt-1">Cleared 7-day dispute holding period</div>
              </div>

              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
                <div className="text-xs text-amber-400 font-bold uppercase">Pending Escrow Balance</div>
                <div className="text-3xl font-extrabold text-amber-400 mt-1">${pendingEarnings.toFixed(2)}</div>
                <div className="text-xs text-muted-foreground mt-1">Clears in {holdingDays} days from purchase</div>
              </div>
            </div>
          </div>

          {/* Withdrawal History */}
          <div className="cs-card">
            <h3 className="cs-card-title">Withdrawal History</h3>
            <p className="cs-card-desc">Track past payout requests and download payment receipts</p>

            {withdrawals.length === 0 ? (
              <div className="py-12 text-center text-xs text-muted-foreground">
                No withdrawal requests submitted yet.
              </div>
            ) : (
              <div className="cs-table-wrap">
                <table className="cs-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Amount</th>
                      <th>Bank</th>
                      <th>Account</th>
                      <th>Status</th>
                      <th>Receipt</th>
                    </tr>
                  </thead>
                  <tbody>
                    {withdrawals.map((w) => {
                      const st = String(w.status || "").toLowerCase();
                      return (
                        <tr key={w.id}>
                          <td className="text-xs text-muted-foreground whitespace-nowrap">
                            {new Date(w.created_at).toLocaleDateString()}
                          </td>
                          <td className="font-extrabold text-sm text-foreground">${Number(w.amount).toFixed(2)}</td>
                          <td className="text-xs text-muted-foreground">{w.bank_name || "Bank Transfer"}</td>
                          <td className="text-xs font-mono">••••{String(w.account_number || "").slice(-4)}</td>
                          <td>
                            {st === "paid" && <span className="cs-badge cs-badge-success">Paid</span>}
                            {st === "approved" && <span className="cs-badge cs-badge-info">Approved</span>}
                            {st === "pending" && <span className="cs-badge cs-badge-warning">Pending</span>}
                            {st === "rejected" && <span className="cs-badge cs-badge-danger">Rejected</span>}
                          </td>
                          <td>
                            <a
                              href={`/api/v1/payouts/withdrawals/${w.id}/receipt`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs font-semibold text-[#dfb180] hover:underline flex items-center gap-1"
                            >
                              <Receipt className="w-3.5 h-3.5" />
                              <span>Receipt</span>
                            </a>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 8: CREATOR SETTINGS (MULTI-GATEWAY PAYOUT METHOD SELECTION)       */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === "settings" && (
        <div className="cs-card">
          <div className="cs-card-header">
            <div>
              <h3 className="cs-card-title">Creator Profile &amp; Payout Settings</h3>
              <p className="cs-card-desc">Choose how you receive your 80% creator sales revenue directly</p>
            </div>
            <span className="cs-badge cs-badge-success">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Automated Payouts
            </span>
          </div>

          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setIsSavingBank(true);
              setBankSaveMessage("");
              try {
                await api.patch(
                  "/auth/me",
                  {
                    payout_method: payoutMethod,
                    payout_bank_name: bankName,
                    payout_account_number: accountNumber,
                    payout_ifsc_code: ifscCode,
                    payout_account_holder_name: accountHolder,
                    payout_razorpay_vpa: upiId,
                    payout_upi_id: upiId,
                    payout_stripe_email: stripeEmail,
                  },
                  authToken
                );
                queryClient.invalidateQueries({ queryKey: ["creator-earnings"] });
                queryClient.invalidateQueries({ queryKey: ["user"] });
                setBankSaveMessage("Payout preferences and details saved successfully!");
                setTimeout(() => setBankSaveMessage(""), 3500);
              } catch (err) {
                setBankSaveMessage("Failed to save payout settings: " + (err?.response?.data?.detail || err?.message || "Unknown error"));
              } finally {
                setIsSavingBank(false);
              }
            }}
            className="space-y-6 max-w-2xl"
          >
            {/* 1. Choose Payout Method Selector */}
            <div>
              <label className="cs-label block mb-2">Select Your Preferred Payout Gateway</label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {[
                  { id: "bank", label: "Bank Transfer", icon: Building2, desc: "Direct NEFT / SWIFT", tag: "Wire" },
                  { id: "upi", label: "UPI (India)", icon: Smartphone, desc: "Instant GPay / PhonePe", tag: "Zero Fee" },
                  { id: "stripe", label: "Stripe Connect", icon: CreditCard, desc: "Cards in 135+ Currencies", tag: "Global" },
                  { id: "razorpay", label: "Razorpay Route", icon: Zap, desc: "Domestic Settlement", tag: "Fast" },
                ].map((item) => {
                  const Icon = item.icon;
                  const isSelected = payoutMethod === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setPayoutMethod(item.id)}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between gap-2 ${
                        isSelected
                          ? "border-[#dfb180] bg-[#dfb180]/15 ring-2 ring-[#dfb180]/40 shadow-md shadow-[#dfb180]/10"
                          : "border-white/10 bg-black/40 hover:border-white/20 hover:bg-white/5"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <div
                          className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                            isSelected
                              ? "bg-[#dfb180]/25 text-[#dfb180]"
                              : "bg-white/5 text-muted-foreground"
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                        </div>
                        <span
                          className={`text-[9px] font-extrabold uppercase px-1.5 py-0.5 rounded ${
                            isSelected
                              ? "bg-[#dfb180]/20 text-[#dfb180]"
                              : "bg-white/5 text-muted-foreground"
                          }`}
                        >
                          {item.tag}
                        </span>
                      </div>
                      <div>
                        <strong className={`text-xs block font-bold ${isSelected ? "text-white" : "text-slate-300"}`}>
                          {item.label}
                        </strong>
                        <span className="text-[10px] text-muted-foreground block line-clamp-1">{item.desc}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 2. Dynamic Input Fields Based on Selected Gateway */}
            {payoutMethod === "upi" && (
              <div className="p-4 rounded-xl bg-black/40 border border-[#dfb180]/30 space-y-4">
                <div className="flex items-center gap-2 text-xs text-[#dfb180] font-bold">
                  <Smartphone className="w-4 h-4" />
                  <span>UPI Instant Settlement Configuration</span>
                </div>
                <div className="cs-form-group">
                  <label className="cs-label">UPI ID / Virtual Payment Address (VPA)</label>
                  <input
                    type="text"
                    value={upiId}
                    onChange={(e) => setUpiId(e.target.value)}
                    placeholder="e.g. yourname@okhdfcbank or 9876543210@paytm"
                    className="cs-input font-mono"
                    required
                  />
                  <span className="text-[11px] text-muted-foreground">
                    Earnings will be disbursed directly to your UPI-linked bank account (GPay, PhonePe, Paytm, BHIM, etc.).
                  </span>
                </div>

                <div className="cs-form-group">
                  <label className="cs-label">Account Holder / Registered Name</label>
                  <input
                    type="text"
                    value={accountHolder}
                    onChange={(e) => setAccountHolder(e.target.value)}
                    placeholder="Full name as registered on UPI"
                    className="cs-input"
                  />
                </div>
              </div>
            )}

            {payoutMethod === "stripe" && (
              <div className="p-4 rounded-xl bg-black/40 border border-indigo-500/30 space-y-4">
                <div className="flex items-center gap-2 text-xs text-indigo-400 font-bold">
                  <CreditCard className="w-4 h-4" />
                  <span>Stripe Connect / Direct Card Payouts</span>
                </div>
                <div className="cs-form-group">
                  <label className="cs-label">Stripe Account Email</label>
                  <input
                    type="email"
                    value={stripeEmail}
                    onChange={(e) => setStripeEmail(e.target.value)}
                    placeholder="e.g. payments@yourdomain.com"
                    className="cs-input"
                    required
                  />
                  <span className="text-[11px] text-muted-foreground">
                    Connect your Stripe Express or Custom account to receive automated credit/debit card payouts across 135+ currencies.
                  </span>
                </div>
              </div>
            )}

            {payoutMethod === "razorpay" && (
              <div className="p-4 rounded-xl bg-black/40 border border-blue-500/30 space-y-4">
                <div className="flex items-center gap-2 text-xs text-blue-400 font-bold">
                  <Zap className="w-4 h-4 text-[#dfb180]" />
                  <span>Razorpay Route / Linked Account</span>
                </div>
                <div className="cs-form-group">
                  <label className="cs-label">Razorpay Linked Account / VPA</label>
                  <input
                    type="text"
                    value={upiId}
                    onChange={(e) => setUpiId(e.target.value)}
                    placeholder="acc_XXXXXXXXXXXXXX or upi@razorpay"
                    className="cs-input font-mono"
                    required
                  />
                  <span className="text-[11px] text-muted-foreground">
                    Direct automated splits via Razorpay Route for merchant-to-merchant payouts.
                  </span>
                </div>
              </div>
            )}


            {/* Always allow configuring / backing up Bank Wire Details */}
            <div className={`p-4 rounded-xl bg-black/40 border space-y-4 ${payoutMethod === "bank" ? "border-[#dfb180]/40" : "border-white/10"}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
                  <Building2 className="w-4 h-4 text-[#dfb180]" />
                  <span>Direct Bank Wire Details {payoutMethod !== "bank" && "(Backup Payout Option)"}</span>
                </div>
                {payoutMethod === "bank" && (
                  <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-[#dfb180]/20 text-[#dfb180]">
                    Primary Selected
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="cs-form-group">
                  <label className="cs-label">Bank Name</label>
                  <input
                    type="text"
                    value={bankName}
                    onChange={(e) => setBankName(e.target.value)}
                    placeholder="e.g. Chase Bank, HDFC Bank, Barclays"
                    className="cs-input"
                    required={payoutMethod === "bank"}
                  />
                </div>

                <div className="cs-form-group">
                  <label className="cs-label">Account Number / IBAN</label>
                  <input
                    type="text"
                    value={accountNumber}
                    onChange={(e) => setAccountNumber(e.target.value)}
                    placeholder="Account number or IBAN"
                    className="cs-input font-mono"
                    required={payoutMethod === "bank"}
                  />
                </div>

                <div className="cs-form-group">
                  <label className="cs-label">IFSC / Routing / SWIFT Code</label>
                  <input
                    type="text"
                    value={ifscCode}
                    onChange={(e) => setIfscCode(e.target.value)}
                    placeholder="Branch IFSC, Routing, or SWIFT"
                    className="cs-input font-mono uppercase"
                    required={payoutMethod === "bank"}
                  />
                </div>

                <div className="cs-form-group">
                  <label className="cs-label">Account Holder Legal Name</label>
                  <input
                    type="text"
                    value={accountHolder}
                    onChange={(e) => setAccountHolder(e.target.value)}
                    placeholder="Full name as printed on bank records"
                    className="cs-input"
                    required={payoutMethod === "bank"}
                  />
                </div>
              </div>
            </div>

            {bankSaveMessage && (
              <div
                className={`p-3 rounded-lg text-xs font-semibold flex items-center gap-2 ${
                  bankSaveMessage.includes("success")
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-red-500/10 text-red-400 border border-red-500/20"
                }`}
              >
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{bankSaveMessage}</span>
              </div>
            )}

            <button type="submit" disabled={isSavingBank} className="cs-btn-primary">
              {isSavingBank ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              <span>Save Payout Settings</span>
            </button>
          </form>
        </div>
      )}

      {/* ── Retail Website Modal ────────────────────────────────────────────── */}
      {isRetailModalOpen && selectedTemplateForRetail && (
        <RetailTemplateModal
          isOpen={isRetailModalOpen}
          onClose={() => {
            setIsRetailModalOpen(false);
            setSelectedTemplateForRetail(null);
          }}
          template={selectedTemplateForRetail}
          user={user}
          authToken={authToken}
          onSuccess={() => {
            refetchTemplates();
            refetchEarnings();
          }}
        />
      )}

      {/* ── Request Payout Modal ────────────────────────────────────────────── */}
      {isPayoutModalOpen && (
        <div className="cs-modal-backdrop" onClick={() => setIsPayoutModalOpen(false)}>
          <div className="cs-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between pb-3 border-b border-border/30">
              <div className="flex items-center gap-2">
                <Wallet className="w-5 h-5 text-emerald-400" />
                <h3 className="font-bold text-base text-foreground">Request Creator Payout</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsPayoutModalOpen(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleWithdrawalSubmit} className="space-y-4">
              <div className="p-3 rounded-xl bg-card border border-border/40 text-xs">
                <div className="text-muted-foreground">Available to withdraw:</div>
                <div className="text-xl font-extrabold text-emerald-400">${availableBalance.toFixed(2)} USD</div>
              </div>

              <div className="cs-form-group">
                <label className="cs-label">Withdrawal Amount ($ USD)</label>
                <input
                  type="number"
                  min="10"
                  max={availableBalance}
                  step="0.01"
                  value={payoutAmount}
                  onChange={(e) => setPayoutAmount(e.target.value)}
                  placeholder="Minimum $10.00"
                  className="cs-input"
                  required
                />
              </div>

              {payoutError && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/25 text-red-400 text-xs">
                  {payoutError}
                </div>
              )}

              {payoutSuccess && (
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 text-xs">
                  {payoutSuccess}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsPayoutModalOpen(false)}
                  className="cs-btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={availableBalance <= 0 || !payoutAmount}
                  className="cs-btn-primary"
                >
                  Confirm Withdrawal
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function PercentIcon(props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <line x1="19" x2="5" y1="5" y2="19" />
      <circle cx="6.5" cy="6.5" r="2.5" />
      <circle cx="17.5" cy="17.5" r="2.5" />
    </svg>
  );
}
