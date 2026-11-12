"use client";

/**
 * Admin Control Panel Page - manages templates, categories, users list, and system metrics (React JSX).
 */

export const dynamic = "force-dynamic";

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./Page.css";
import { useAppAuth } from "@/lib/auth";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldAlert,
  Users,
  Layers,
  FileCode,
  TrendingUp,
  Plus,
  Trash2,
  Edit3,
  Loader2,
  Check,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  X,
  CreditCard,
  Coins,
  Zap,
  Download,
  ExternalLink,
  Eye,
  RefreshCw,
  AlertTriangle,
  Search,
  Filter,
  Clock,
  ArrowUpRight,
  ShieldCheck,
  Activity,
  CheckCircle2,
  XCircle,
  Lock,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { api } from "@/lib/api";
import { cn, formatPrice } from "@/lib/utils";
import "./Page.css";

function AdminPanel() {
  const { getToken } = useAppAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("metrics");
  const [authToken, setAuthToken] = useState(null);
  const qc = useQueryClient();

  useEffect(() => {
    getToken().then(setAuthToken);
  }, [getToken]);

  // Fetch admin stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => api.get("/admin/stats", authToken ?? undefined),
    enabled: !!authToken,
  });

  // Fetch all templates
  const { data: templateResponse, isLoading: templatesLoading } = useQuery({
    queryKey: ["admin-templates"],
    queryFn: () => api.get("/templates?page_size=100", authToken ?? undefined),
    enabled: !!authToken,
  });

  // Fetch all categories
  const { data: categories = [], isLoading: categoriesLoading } = useQuery({
    queryKey: ["admin-categories"],
    queryFn: () => api.get("/categories", authToken ?? undefined),
    enabled: !!authToken,
  });

  // Fetch users paginated
  const { data: usersResponse, isLoading: usersLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api.get("/admin/users", authToken ?? undefined),
    enabled: !!authToken,
  });

  // Fetch real-time infrastructure health overview
  const { data: healthData } = useQuery({
    queryKey: ["admin-health-overview"],
    queryFn: () => api.get("/admin/health-overview", authToken ?? undefined),
    enabled: !!authToken,
    refetchInterval: 10000,
  });

  // Fetch real-time platform operational analytics
  const { data: platformAnalytics } = useQuery({
    queryKey: ["admin-analytics"],
    queryFn: () => api.get("/admin/analytics", authToken ?? undefined),
    enabled: !!authToken,
    refetchInterval: 15000,
  });

  // Fetch seller withdrawal requests for moderation
  const { data: sellerWithdrawals = [] } = useQuery({
    queryKey: ["admin-withdrawals"],
    queryFn: () => api.get("/payouts/admin/withdrawals", authToken ?? undefined),
    enabled: !!authToken,
  });

  const { data: pendingUpiPayments = [] } = useQuery({
    queryKey: ["admin-pending-upi"],
    queryFn: () => api.get("/admin/payments/pending-upi", authToken ?? undefined),
    enabled: !!authToken,
  });

  const reviewUpiPaymentMutation = useMutation({
    mutationFn: ({ paymentId, decision }) => api.patch(`/admin/payments/${paymentId}/upi-review`, { decision }, authToken ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-pending-upi"] }),
  });

  // Fetch customer reviews for moderation
  const { data: adminReviewsData } = useQuery({
    queryKey: ["admin-reviews"],
    queryFn: () => api.get("/reviews/admin?page_size=50", authToken ?? undefined),
    enabled: !!authToken,
  });

  // Approve / Reject Review Mutation
  const toggleReviewApprovalMutation = useMutation({
    mutationFn: ({ reviewId, isApproved }) => api.patch(`/reviews/${reviewId}/approve?is_approved=${isApproved}`, {}, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-reviews"] });
    },
  });

  // Update Withdrawal Request Status Mutation
  const updateWithdrawalStatusMutation = useMutation({
    mutationFn: ({ withdrawalId, status }) => api.patch(`/payouts/admin/withdrawals/${withdrawalId}`, { status }, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-withdrawals"] });
    },
  });

  // Payments & Revenue State & Queries (Razorpay Monitoring)
  const [paymentSearch, setPaymentSearch] = useState("");
  const [paymentStatusFilter, setPaymentStatusFilter] = useState("all");
  const [paymentTypeFilter, setPaymentTypeFilter] = useState("all");

  const { data: paymentsData, isLoading: paymentsLoading, refetch: refetchPayments } = useQuery({
    queryKey: ["admin-payments"],
    queryFn: () => api.get("/admin/payments", authToken ?? undefined),
    enabled: !!authToken,
    refetchInterval: 10000,
  });

  // Users Usage State & Queries (Platform Activity Monitoring)
  const [userSearch, setUserSearch] = useState("");
  const [userTierFilter, setUserTierFilter] = useState("all");
  const [selectedUserForActivity, setSelectedUserForActivity] = useState(null);
  const [activityTab, setActivityTab] = useState("orders");

  const { data: usersUsage = [], isLoading: usersUsageLoading, refetch: refetchUsersUsage } = useQuery({
    queryKey: ["admin-users-usage"],
    queryFn: () => api.get("/admin/users/usage", authToken ?? undefined),
    enabled: !!authToken,
    refetchInterval: 15000,
  });

  const { data: userActivity, isLoading: userActivityLoading } = useQuery({
    queryKey: ["admin-user-activity", selectedUserForActivity?.id],
    queryFn: () => api.get(`/admin/users/${selectedUserForActivity.id}/usage-details`, authToken ?? undefined),
    enabled: !!authToken && !!selectedUserForActivity?.id,
  });


  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [categoryForm, setCategoryForm] = useState({
    name: "",
    slug: "",
    description: "",
    icon: "Briefcase",
    color: "#c89666",
  });
  const [categoryError, setCategoryError] = useState("");

  const handleCategoryNameChange = (val) => {
    const autoSlug = val
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    setCategoryForm((prev) => ({
      ...prev,
      name: val,
      slug: autoSlug,
    }));
  };

  // Create Category Mutation
  const createCategoryMutation = useMutation({
    mutationFn: (data) => api.post("/categories", data, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-categories"] });
      qc.invalidateQueries({ queryKey: ["categories"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
      setIsCategoryModalOpen(false);
      setCategoryForm({
        name: "",
        slug: "",
        description: "",
        icon: "Briefcase",
        color: "#c89666",
      });
      setCategoryError("");
    },
    onError: (err) => {
      setCategoryError(err.message || "Failed to create category");
    },
  });

  // Delete Template Mutation
  const deleteTemplateMutation = useMutation({
    mutationFn: (templateId) => api.delete(`/templates/${templateId}`, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-templates"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
    },
  });

  // Delete Category Mutation
  const deleteCategoryMutation = useMutation({
    mutationFn: (categoryId) => api.delete(`/categories/${categoryId}`, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-categories"] });
      qc.invalidateQueries({ queryKey: ["categories"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
    },
  });

  const paymentsList = paymentsData?.payments || [];
  const filteredPayments = paymentsList.filter((p) => {
    const q = paymentSearch.toLowerCase().trim();
    const matchesSearch =
      !q ||
      p.order_number?.toLowerCase().includes(q) ||
      p.buyer_email?.toLowerCase().includes(q) ||
      p.buyer_name?.toLowerCase().includes(q) ||
      p.gateway_payment_id?.toLowerCase().includes(q) ||
      p.gateway_order_id?.toLowerCase().includes(q) ||
      p.items_summary?.toLowerCase().includes(q);

    const matchesStatus =
      paymentStatusFilter === "all" ||
      p.status?.toLowerCase() === paymentStatusFilter.toLowerCase();

    const matchesType =
      paymentTypeFilter === "all" ||
      (paymentTypeFilter === "subscription" && p.payment_type?.toLowerCase().includes("subscription")) ||
      (paymentTypeFilter === "marketplace" && p.payment_type?.toLowerCase().includes("marketplace")) ||
      (paymentTypeFilter === "ai_tokens" && p.payment_type?.toLowerCase().includes("token"));

    return matchesSearch && matchesStatus && matchesType;
  });

  const filteredUsers = (usersUsage || []).filter((u) => {
    const q = userSearch.toLowerCase().trim();
    const matchesSearch =
      !q ||
      u.email?.toLowerCase().includes(q) ||
      u.name?.toLowerCase().includes(q) ||
      u.role?.toLowerCase().includes(q);

    const matchesTier =
      userTierFilter === "all" ||
      u.subscription_tier?.toLowerCase() === userTierFilter.toLowerCase();

    return matchesSearch && matchesTier;
  });

  if (!authToken) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen pt-20 flex items-center justify-center bg-background">
          <div className="text-center space-y-4">
            <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
            <p className="text-muted-foreground text-sm">Authenticating admin session...</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div className="min-h-screen pt-20 bg-background text-foreground">
        <div className="container-xl py-10 space-y-8">
          {/* Admin Header */}
          <div className="admin-header-row">
            <div>
              <div className="flex items-center gap-2 text-primary font-semibold text-sm mb-1">
                <ShieldAlert className="w-4 h-4" /> System Administrator
              </div>
              <h1 className="admin-title">Admin Console</h1>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setIsCategoryModalOpen(true)}
                className="px-4 py-2 bg-primary/10 text-primary hover:bg-primary/20 text-xs font-semibold rounded-xl flex items-center gap-1.5 transition-colors border border-primary/20"
              >
                <Plus className="w-4 h-4" /> Add Category
              </button>
            </div>
          </div>

          {/* Admin Tab Controls */}
          <div className="admin-tab-group">
            {[
              { id: "metrics", label: "Metrics & Logs", icon: TrendingUp },
              { id: "payments", label: "Payments & Revenue", icon: CreditCard },
              { id: "users", label: "Users & Usage", icon: Users },
              { id: "moderation", label: "Moderation & Payouts", icon: Layers },
              { id: "templates", label: "Templates", icon: FileCode },
              { id: "categories", label: "Categories", icon: Layers },
            ].map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "admin-tab-btn",
                    activeTab === tab.id && "active"
                  )}
                >
                  <Icon className="w-4.5 h-4.5" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Tab Pages */}
          <div className="pt-2">
            {/* METRICS */}
            {activeTab === "metrics" && (
              <div className="space-y-6">
                <div className="admin-metrics-grid">
                  {[
                    { label: "Gross Order Totals (currencies mixed)", value: platformAnalytics?.gross_sales_usd ?? stats?.gross_revenue ?? 0, icon: TrendingUp },
                    { label: "Completed Orders", value: platformAnalytics?.completed_orders ?? stats?.total_orders ?? 0, icon: Coins },
                    { label: "Active Live Deployments", value: platformAnalytics?.active_live_deployments ?? 0, icon: Zap },
                    { label: "Sellers / Creators", value: platformAnalytics?.sellers_count ?? 0, icon: Users },
                    { label: "Buyers / Customers", value: platformAnalytics?.buyers_count ?? 0, icon: Users },
                    { label: "Published Templates", value: stats?.total_templates ?? 0, icon: FileCode },
                  ].map((metric) => {
                    const Icon = metric.icon;
                    return (
                      <div key={metric.label} className="admin-metric-card">
                        <div className="admin-metric-header">
                          <span>{metric.label}</span>
                          <Icon className="w-4.5 h-4.5 text-primary" />
                        </div>
                        <div className="admin-metric-value">{metric.value}</div>
                      </div>
                    );
                  })}
                </div>
                <div className="glass border border-border/40 rounded-2xl p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h3 className="font-bold text-base mb-1">Platform Infrastructure Health</h3>
                      <p className="text-sm text-muted-foreground">Real-time core services cluster & storage monitor.</p>
                    </div>
                    <span className={cn(
                      "px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider",
                      healthData?.status === "HEALTHY" ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                    )}>
                      {healthData?.status || "HEALTHY"}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    {[
                      { name: "PostgreSQL Database", status: healthData?.components?.postgresql || "ONLINE", color: "text-green-500" },
                      { name: "Redis Cache & Queue", status: healthData?.components?.redis || "ONLINE", color: "text-green-500" },
                      { name: "Qdrant Vector Engine", status: healthData?.components?.qdrant_vector_db || "ONLINE", color: "text-green-500" },
                      { name: "File Storage Used", status: `${healthData?.components?.storage_used_mb || 0} MB`, color: "text-[#dfb180]" },
                    ].map((svc) => (
                      <div key={svc.name} className="p-4 bg-muted/30 border border-border/50 rounded-xl space-y-1">
                        <div className="text-xs text-muted-foreground font-medium">{svc.name}</div>
                        <div className={cn("text-sm font-bold flex items-center gap-1", svc.color)}>
                          <Check className="w-3.5 h-3.5" /> {svc.status}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* PAYMENTS & REVENUE (RAZORPAY MONITOR) */}
            {activeTab === "payments" && (
              <div className="space-y-6">
                {/* Payment Metric Highlights */}
                <div className="admin-metrics-grid">
                  <div className="admin-metric-card">
                    <div className="admin-metric-header">
                      <span>Total USD Revenue</span>
                      <TrendingUp className="w-4.5 h-4.5 text-emerald-400" />
                    </div>
                    <div className="admin-metric-value text-emerald-400">
                      ${paymentsData?.summary?.total_revenue_usd?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || "0.00"}
                    </div>
                    <span className="text-xs text-muted-foreground">Across subscriptions & templates</span>
                  </div>

                  <div className="admin-metric-card">
                    <div className="admin-metric-header">
                      <span>Razorpay Settled (INR)</span>
                      <Coins className="w-4.5 h-4.5 text-primary" />
                    </div>
                    <div className="admin-metric-value text-primary">
                      ₹{paymentsData?.summary?.total_revenue_inr?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || "0.00"}
                    </div>
                    <span className="text-xs text-muted-foreground">Total captured in INR paise</span>
                  </div>

                  <div className="admin-metric-card">
                    <div className="admin-metric-header">
                      <span>Transactions Breakdown</span>
                      <CreditCard className="w-4.5 h-4.5 text-[#dfb180]" />
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="admin-metric-value text-foreground">
                        {paymentsData?.summary?.captured_count || 0}
                      </span>
                      <span className="text-xs text-emerald-400 font-semibold">Captured</span>
                      <span className="text-xs text-muted-foreground">/ {paymentsData?.summary?.total_transactions || 0} Total</span>
                    </div>
                    <div className="flex gap-3 text-xs text-muted-foreground pt-1">
                      <span>Sub: <strong>{paymentsData?.summary?.subscription_count || 0}</strong></span>
                      <span>Templates: <strong>{paymentsData?.summary?.marketplace_count || 0}</strong></span>
                      {(paymentsData?.summary?.failed_count || 0) > 0 && (
                        <span className="text-rose-400">Failed: <strong>{paymentsData?.summary?.failed_count}</strong></span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Payments Table Card */}
                <div className="admin-table-container">
                  <div className="p-6 border-b border-border/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <h3 className="font-bold text-base flex items-center gap-2">
                        <CreditCard className="w-5 h-5 text-primary" /> Razorpay Payment Transactions
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        Live transaction monitor tracking orders, webhook captures, and customer settlement data.
                      </p>
                    </div>
                    <button
                      onClick={() => refetchPayments()}
                      className="px-3.5 py-1.5 bg-muted/50 hover:bg-muted text-xs font-semibold rounded-xl flex items-center gap-1.5 border border-border/60 transition-colors self-start sm:self-auto cursor-pointer"
                    >
                      <RefreshCw className={cn("w-3.5 h-3.5", paymentsLoading && "animate-spin")} /> Refresh Feed
                    </button>
                  </div>

                  {/* Filter & Search Bar */}
                  <div className="admin-filter-bar">
                    <div className="admin-search-input">
                      <Search className="w-4 h-4 text-muted-foreground" />
                      <input
                        type="text"
                        placeholder="Search order #, email, pay_... or order_..."
                        value={paymentSearch}
                        onChange={(e) => setPaymentSearch(e.target.value)}
                      />
                      {paymentSearch && (
                        <button onClick={() => setPaymentSearch("")} className="text-muted-foreground hover:text-foreground">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-muted-foreground mr-1">Status:</span>
                      {["all", "captured", "pending", "failed"].map((st) => (
                        <button
                          key={st}
                          onClick={() => setPaymentStatusFilter(st)}
                          className={cn("admin-pill-btn", paymentStatusFilter === st && "active")}
                        >
                          {st.charAt(0).toUpperCase() + st.slice(1)}
                        </button>
                      ))}

                      <span className="text-xs font-semibold text-muted-foreground ml-3 mr-1">Type:</span>
                      {[
                        { id: "all", label: "All" },
                        { id: "subscription", label: "Subscriptions" },
                        { id: "marketplace", label: "Templates" },
                        { id: "ai_tokens", label: "AI Tokens" },
                      ].map((t) => (
                        <button
                          key={t.id}
                          onClick={() => setPaymentTypeFilter(t.id)}
                          className={cn("admin-pill-btn", paymentTypeFilter === t.id && "active")}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Transactions Table */}
                  <div className="overflow-x-auto">
                    <table className="admin-table">
                      <thead>
                        <tr className="admin-tr">
                          <th className="admin-th">Order #</th>
                          <th className="admin-th">Buyer</th>
                          <th className="admin-th">Payment Type</th>
                          <th className="admin-th">Razorpay References</th>
                          <th className="admin-th">USD / INR</th>
                          <th className="admin-th">Status</th>
                          <th className="admin-th">Date</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/50 text-sm">
                        {paymentsLoading ? (
                          <tr>
                            <td colSpan={7} className="p-8 text-center text-muted-foreground">
                              <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                              <span className="block mt-2 text-xs">Loading transaction logs...</span>
                            </td>
                          </tr>
                        ) : filteredPayments.length === 0 ? (
                          <tr>
                            <td colSpan={7} className="p-8 text-center text-muted-foreground">
                              No payment transactions match the active search or filter.
                            </td>
                          </tr>
                        ) : (
                          filteredPayments.map((p) => {
                            const isCaptured = p.status?.toLowerCase() === "captured" || p.status?.toLowerCase() === "completed";
                            const isPending = p.status?.toLowerCase() === "pending";
                            return (
                              <tr key={p.id} className="admin-tr">
                                <td className="admin-td font-mono font-semibold text-xs">
                                  <div className="text-foreground">{p.order_number || "—"}</div>
                                  <div className="text-[11px] text-muted-foreground truncate max-w-[140px]" title={p.items_summary}>
                                    {p.items_summary}
                                  </div>
                                </td>
                                <td className="admin-td">
                                  <div className="font-semibold text-foreground">{p.buyer_name || "Customer"}</div>
                                  <div className="font-mono text-xs text-muted-foreground">{p.buyer_email}</div>
                                </td>
                                <td className="admin-td">
                                  <span className={cn(
                                    "px-2.5 py-0.5 rounded-full text-xs font-semibold inline-block",
                                    p.payment_type?.toLowerCase().includes("subscription")
                                      ? "bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30"
                                      : p.payment_type?.toLowerCase().includes("token")
                                        ? "bg-blue-500/15 text-blue-400 border border-blue-500/30"
                                        : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                                  )}>
                                    {p.payment_type}
                                  </span>
                                </td>
                                <td className="admin-td font-mono text-xs space-y-0.5">
                                  <div className="text-foreground font-semibold flex items-center gap-1">
                                    <span className="text-[10px] text-muted-foreground uppercase">Pay:</span>
                                    <span>{p.gateway_payment_id || "Awaiting Gateway"}</span>
                                  </div>
                                  {p.gateway_order_id && (
                                    <div className="text-muted-foreground text-[11px] flex items-center gap-1">
                                      <span className="text-[10px] uppercase">Order:</span>
                                      <span>{p.gateway_order_id}</span>
                                    </div>
                                  )}
                                </td>
                                <td className="admin-td">
                                  <div className="font-bold text-foreground">
                                    ${p.amount_usd ? p.amount_usd.toFixed(2) : "0.00"}
                                  </div>
                                  <div className="text-xs text-muted-foreground font-medium">
                                    ₹{p.amount_inr ? p.amount_inr.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "0.00"}
                                  </div>
                                </td>
                                <td className="admin-td">
                                  <span className={cn(
                                    isCaptured
                                      ? "admin-badge-success"
                                      : isPending
                                        ? "admin-badge-pending"
                                        : "admin-badge-failed"
                                  )}>
                                    {isCaptured ? <CheckCircle2 className="w-3 h-3" /> : isPending ? <Clock className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                                    {p.status}
                                  </span>
                                </td>
                                <td className="admin-td text-xs text-muted-foreground whitespace-nowrap">
                                  {p.created_at ? new Date(p.created_at).toLocaleString() : "—"}
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* MODERATION & PAYOUTS */}
            {activeTab === "moderation" && (
              <div className="space-y-6">
                <div className="glass border border-border/40 rounded-2xl p-6">
                  <h3 className="font-bold text-base mb-2">UPI References Awaiting Review</h3>
                  <p className="text-sm text-muted-foreground mb-4">Match each reference and amount against the merchant bank account before approving.</p>
                  {pendingUpiPayments.length === 0 ? (
                    <div className="text-center py-6 text-sm text-muted-foreground">No UPI references awaiting review.</div>
                  ) : (
                    <div className="overflow-x-auto"><table className="admin-table">
                      <thead><tr className="admin-tr"><th className="admin-th">Order</th><th className="admin-th">Buyer</th><th className="admin-th">UTR</th><th className="admin-th">Amount</th><th className="admin-th text-right">Actions</th></tr></thead>
                      <tbody className="divide-y divide-border/50 text-sm">{pendingUpiPayments.map((payment) => (
                        <tr key={payment.id} className="admin-tr">
                          <td className="admin-td">{payment.order_number || payment.order_id}</td>
                          <td className="admin-td">{payment.buyer_email || "—"}</td>
                          <td className="admin-td font-mono">{payment.utr}</td>
                          <td className="admin-td">{payment.currency} {payment.amount}</td>
                          <td className="admin-td text-right space-x-2">
                            <button disabled={reviewUpiPaymentMutation.isPending} onClick={() => reviewUpiPaymentMutation.mutate({ paymentId: payment.id, decision: "approve" })} className="px-3 py-1 bg-green-600 text-white rounded-lg text-xs font-semibold disabled:opacity-50">Approve</button>
                            <button disabled={reviewUpiPaymentMutation.isPending} onClick={() => reviewUpiPaymentMutation.mutate({ paymentId: payment.id, decision: "reject" })} className="px-3 py-1 bg-red-600 text-white rounded-lg text-xs font-semibold disabled:opacity-50">Reject</button>
                          </td>
                        </tr>
                      ))}</tbody>
                    </table></div>
                  )}
                </div>
                <div className="glass border border-border/40 rounded-2xl p-6">
                  <h3 className="font-bold text-base mb-2">Pending Seller Withdrawal Requests</h3>
                  <p className="text-sm text-muted-foreground mb-4">Review and approve manual payout requests from creators.</p>
                  {sellerWithdrawals.length === 0 ? (
                    <div className="text-center py-6 text-sm text-muted-foreground">No pending withdrawal requests.</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="admin-table">
                        <thead>
                          <tr className="admin-tr">
                            <th className="admin-th">Amount</th>
                            <th className="admin-th">Bank Name</th>
                            <th className="admin-th">Account Number</th>
                            <th className="admin-th">Status</th>
                            <th className="admin-th text-right" style={{ textAlign: "right" }}>Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/50 text-sm">
                          {sellerWithdrawals.map((w) => (
                            <tr key={w.id} className="admin-tr">
                              <td className="admin-td font-bold">${w.amount}</td>
                              <td className="admin-td">{w.bank_name || "N/A"}</td>
                              <td className="admin-td">{w.account_number || "N/A"}</td>
                              <td className="admin-td">
                                <span className={cn(
                                  "px-2.5 py-0.5 rounded-full text-xs font-semibold",
                                  ["approved", "paid"].includes(w.status) ? "bg-green-500/10 text-green-400" : w.status === "rejected" ? "bg-red-500/10 text-red-400" : "bg-amber-500/10 text-amber-400"
                                )}>
                                  {w.status}
                                </span>
                              </td>
                              <td className="admin-td text-right" style={{ textAlign: "right" }}>
                                {w.status === "pending" && (
                                  <>
                                  <button
                                    onClick={() => updateWithdrawalStatusMutation.mutate({ withdrawalId: w.id, status: "approved" })}
                                    className="px-3 py-1 bg-green-600 text-white rounded-lg text-xs font-semibold hover:bg-green-500 transition-colors"
                                  >
                                    Approve Request
                                  </button>
                                  <button
                                    onClick={() => updateWithdrawalStatusMutation.mutate({ withdrawalId: w.id, status: "rejected" })}
                                    className="px-3 py-1 bg-red-600 text-white rounded-lg text-xs font-semibold hover:bg-red-500 transition-colors"
                                  >
                                    Reject
                                  </button>
                                  </>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}


            {/* TEMPLATES */}
            {activeTab === "templates" && (
              <div className="admin-table-container">
                <div className="p-6">
                  <h3 className="font-bold text-base">Templates Catalog</h3>
                  <p className="text-sm text-muted-foreground">Manage templates listing details, stats and attributes.</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="admin-table">
                    <thead>
                      <tr className="admin-tr">
                        <th className="admin-th">Template Title</th>
                        <th className="admin-th">Framework</th>
                        <th className="admin-th">Price</th>
                        <th className="admin-th">Downloads</th>
                        <th className="admin-th text-right" style={{ textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50 text-sm">
                      {templatesLoading ? (
                        <tr>
                          <td colSpan={5} className="p-8 text-center text-muted-foreground">
                            <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                          </td>
                        </tr>
                      ) : templateResponse?.items?.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="p-8 text-center text-muted-foreground">
                            No templates found in database.
                          </td>
                        </tr>
                      ) : (
                        templateResponse?.items?.map((item) => (
                          <tr key={item.id} className="admin-tr">
                            <td className="admin-td font-semibold">{item.title}</td>
                            <td className="admin-td font-mono text-xs uppercase">{item.framework ?? "HTML"}</td>
                            <td className="admin-td">{formatPrice(item.price)}</td>
                            <td className="admin-td">{item.downloads_count}</td>
                            <td className="admin-td text-right">
                              <div className="flex justify-end gap-2">
                                <button className="p-1.5 hover:text-primary transition-colors">
                                  <Edit3 className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => {
                                    if (window.confirm(`Delete "${item.title}"? This cannot be undone.`)) {
                                      deleteTemplateMutation.mutate(item.id);
                                    }
                                  }}
                                  disabled={deleteTemplateMutation.isPending}
                                  className="p-1.5 hover:text-destructive transition-colors disabled:opacity-40"
                                  title="Delete template"
                                >
                                  {deleteTemplateMutation.isPending ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                  ) : (
                                    <Trash2 className="w-4 h-4" />
                                  )}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* CATEGORIES */}
            {activeTab === "categories" && (
              <div className="admin-table-container">
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-base">Hierarchy Categories</h3>
                    <p className="text-sm text-muted-foreground">Marketplace vertical category setup control.</p>
                  </div>
                  <button
                    onClick={() => setIsCategoryModalOpen(true)}
                    className="px-3.5 py-1.5 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/90 flex items-center gap-1.5 transition-colors"
                  >
                    <Plus className="w-4 h-4" /> Create Category
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="admin-table">
                    <thead>
                      <tr className="admin-tr">
                        <th className="admin-th">Category Name</th>
                        <th className="admin-th">Slug</th>
                        <th className="admin-th">Icon Reference</th>
                        <th className="admin-th">Templates Count</th>
                        <th className="admin-th text-right" style={{ textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50 text-sm">
                      {categoriesLoading ? (
                        <tr>
                          <td colSpan={5} className="p-8 text-center text-muted-foreground">
                            <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                          </td>
                        </tr>
                      ) : categories.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="p-8 text-center text-muted-foreground">
                            No categories set up.
                          </td>
                        </tr>
                      ) : (
                        categories.map((cat) => (
                          <tr key={cat.id} className="admin-tr">
                            <td className="admin-td font-semibold">{cat.name}</td>
                            <td className="admin-td font-mono text-xs">{cat.slug}</td>
                            <td className="admin-td">{cat.icon ?? "None"}</td>
                            <td className="admin-td font-bold">{cat.template_count ?? 0}</td>
                            <td className="admin-td text-right">
                              <div className="flex justify-end gap-2">
                                <button
                                  onClick={() => deleteCategoryMutation.mutate(cat.id)}
                                  className="p-1.5 hover:text-destructive transition-colors"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* USERS & USAGE MONITOR */}
            {activeTab === "users" && (
              <div className="space-y-6">
                <div className="admin-table-container">
                  <div className="p-6 border-b border-border/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <h3 className="font-bold text-base flex items-center gap-2">
                        <Users className="w-5 h-5 text-primary" /> Platform User & Usage Directory
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        Monitor user subscription tiers, AI token balances, clean vs watermarked downloads, deployments, and security telemetry.
                      </p>
                    </div>
                    <button
                      onClick={() => refetchUsersUsage()}
                      className="px-3.5 py-1.5 bg-muted/50 hover:bg-muted text-xs font-semibold rounded-xl flex items-center gap-1.5 border border-border/60 transition-colors self-start sm:self-auto cursor-pointer"
                    >
                      <RefreshCw className={cn("w-3.5 h-3.5", usersUsageLoading && "animate-spin")} /> Refresh Users
                    </button>
                  </div>

                  {/* Filter & Search Bar */}
                  <div className="admin-filter-bar">
                    <div className="admin-search-input">
                      <Search className="w-4 h-4 text-muted-foreground" />
                      <input
                        type="text"
                        placeholder="Search by name, email, or role..."
                        value={userSearch}
                        onChange={(e) => setUserSearch(e.target.value)}
                      />
                      {userSearch && (
                        <button onClick={() => setUserSearch("")} className="text-muted-foreground hover:text-foreground">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-muted-foreground mr-1">Subscription Tier:</span>
                      {["all", "free", "pro", "extreme"].map((tier) => (
                        <button
                          key={tier}
                          onClick={() => setUserTierFilter(tier)}
                          className={cn("admin-pill-btn", userTierFilter === tier && "active")}
                        >
                          {tier.charAt(0).toUpperCase() + tier.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="admin-table">
                      <thead>
                        <tr className="admin-tr">
                          <th className="admin-th">User Details</th>
                          <th className="admin-th">Subscription Tier</th>
                          <th className="admin-th">AI Credits</th>
                          <th className="admin-th">Orders & Spend</th>
                          <th className="admin-th">Downloads (Clean / WM)</th>
                          <th className="admin-th">Active Sites</th>
                          <th className="admin-th">Tamper Alerts</th>
                          <th className="admin-th text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/50 text-sm">
                        {usersUsageLoading ? (
                          <tr>
                            <td colSpan={8} className="p-8 text-center text-muted-foreground">
                              <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                              <span className="block mt-2 text-xs">Loading user usage telemetry...</span>
                            </td>
                          </tr>
                        ) : filteredUsers.length === 0 ? (
                          <tr>
                            <td colSpan={8} className="p-8 text-center text-muted-foreground">
                              No users match the active search or filter.
                            </td>
                          </tr>
                        ) : (
                          filteredUsers.map((u) => {
                            const tier = (u.subscription_tier || "free").toLowerCase();
                            return (
                              <tr key={u.id} className="admin-tr">
                                <td className="admin-td">
                                  <div className="font-semibold text-foreground flex items-center gap-2">
                                    <span>{u.name || "Anonymous"}</span>
                                    <span className="px-1.5 py-0.2 rounded bg-muted text-[10px] font-mono uppercase text-muted-foreground">
                                      {u.role}
                                    </span>
                                  </div>
                                  <div className="font-mono text-xs text-muted-foreground">{u.email}</div>
                                </td>
                                <td className="admin-td">
                                  <span className={cn(
                                    "admin-tier-pill",
                                    tier === "extreme"
                                      ? "admin-tier-extreme"
                                      : tier === "pro"
                                        ? "admin-tier-pro"
                                        : "admin-tier-free"
                                  )}>
                                    {tier === "extreme" ? <Sparkles className="w-3 h-3" /> : tier === "pro" ? <Zap className="w-3 h-3" /> : null}
                                    {tier}
                                  </span>
                                </td>
                                <td className="admin-td font-semibold">
                                  {tier === "extreme" ? (
                                    <span className="text-amber-400 font-bold flex items-center gap-1 text-xs">
                                      <Sparkles className="w-3 h-3" /> Unlimited
                                    </span>
                                  ) : (
                                    <span className="text-foreground text-xs">{u.ai_credits ?? 10} tokens</span>
                                  )}
                                </td>
                                <td className="admin-td">
                                  <div className="font-semibold text-foreground text-xs">
                                    {u.total_orders} {u.total_orders === 1 ? "order" : "orders"}
                                  </div>
                                  <div className="text-xs text-emerald-400 font-medium">
                                    ${u.total_spent_usd ? u.total_spent_usd.toFixed(2) : "0.00"}
                                  </div>
                                </td>
                                <td className="admin-td text-xs">
                                  <div className="font-semibold text-foreground">
                                    {u.total_downloads} total
                                  </div>
                                  <div className="text-[11px] text-muted-foreground">
                                    <span className="text-emerald-400 font-semibold">{u.clean_downloads} clean</span> • <span>{u.watermarked_downloads} wm</span>
                                  </div>
                                </td>
                                <td className="admin-td">
                                  <span className="font-semibold text-foreground text-xs">
                                    {u.deployments_count} {u.deployments_count === 1 ? "site" : "sites"}
                                  </span>
                                </td>
                                <td className="admin-td">
                                  {u.tamper_alerts_count > 0 ? (
                                    <span className="admin-badge-failed">
                                      <AlertTriangle className="w-3 h-3" /> {u.tamper_alerts_count} Flagged
                                    </span>
                                  ) : (
                                    <span className="text-emerald-400 text-xs font-semibold flex items-center gap-1">
                                      <ShieldCheck className="w-3.5 h-3.5" /> Clean
                                    </span>
                                  )}
                                </td>
                                <td className="admin-td text-right">
                                  <button
                                    onClick={() => {
                                      setSelectedUserForActivity(u);
                                      setActivityTab("orders");
                                    }}
                                    className="px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary rounded-xl text-xs font-semibold transition-colors flex items-center gap-1 ml-auto cursor-pointer"
                                  >
                                    <Activity className="w-3.5 h-3.5" /> Activity
                                  </button>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* CREATE CATEGORY MODAL */}
      {isCategoryModalOpen && (
        <div className="admin-modal-overlay" onClick={() => setIsCategoryModalOpen(false)}>
          <div className="admin-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-border/50 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-lg text-foreground">Create New Category</h3>
                <p className="text-xs text-muted-foreground">Add a new category to marketplace verticals.</p>
              </div>
              <button
                onClick={() => setIsCategoryModalOpen(false)}
                className="p-1 hover:text-foreground text-muted-foreground rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!categoryForm.name.trim() || !categoryForm.slug.trim()) {
                  setCategoryError("Category Name and Slug are required.");
                  return;
                }
                setCategoryError("");
                createCategoryMutation.mutate(categoryForm);
              }}
              className="p-6 space-y-4 text-sm"
            >
              {categoryError && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-xl text-xs font-semibold">
                  {categoryError}
                </div>
              )}

              <div className="space-y-1.5">
                <label className="font-semibold text-xs text-foreground">Category Name *</label>
                <input
                  type="text"
                  placeholder="e.g. Artificial Intelligence"
                  value={categoryForm.name}
                  onChange={(e) => handleCategoryNameChange(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-muted/40 border border-border/60 rounded-xl text-foreground text-sm focus:outline-none focus:border-primary transition-colors"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-xs text-foreground">Slug (URL Segment) *</label>
                <input
                  type="text"
                  placeholder="e.g. artificial-intelligence"
                  value={categoryForm.slug}
                  onChange={(e) =>
                    setCategoryForm((prev) => ({ ...prev, slug: e.target.value.toLowerCase().replace(/\s+/g, "-") }))
                  }
                  className="w-full px-3.5 py-2.5 bg-muted/40 border border-border/60 rounded-xl font-mono text-xs text-foreground focus:outline-none focus:border-primary transition-colors"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-xs text-foreground">Description</label>
                <textarea
                  rows={2}
                  placeholder="Brief overview of this category..."
                  value={categoryForm.description}
                  onChange={(e) => setCategoryForm((prev) => ({ ...prev, description: e.target.value }))}
                  className="w-full px-3.5 py-2 bg-muted/40 border border-border/60 rounded-xl text-foreground text-sm focus:outline-none focus:border-primary transition-colors resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="font-semibold text-xs text-foreground">Icon Reference</label>
                  <input
                    type="text"
                    placeholder="e.g. Sparkles"
                    value={categoryForm.icon}
                    onChange={(e) => setCategoryForm((prev) => ({ ...prev, icon: e.target.value }))}
                    className="w-full px-3.5 py-2 bg-muted/40 border border-border/60 rounded-xl text-foreground text-sm focus:outline-none focus:border-primary transition-colors"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="font-semibold text-xs text-foreground">Color Hex</label>
                  <div className="flex gap-2">
                    <input
                      type="color"
                      value={categoryForm.color || "#c89666"}
                      onChange={(e) => setCategoryForm((prev) => ({ ...prev, color: e.target.value }))}
                      className="w-10 h-10 rounded-lg cursor-pointer bg-transparent border-0"
                    />
                    <input
                      type="text"
                      value={categoryForm.color}
                      onChange={(e) => setCategoryForm((prev) => ({ ...prev, color: e.target.value }))}
                      className="w-full px-3 py-2 bg-muted/40 border border-border/60 rounded-xl font-mono text-xs text-foreground focus:outline-none focus:border-primary transition-colors"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4 flex items-center justify-end gap-3 border-t border-border/40">
                <button
                  type="button"
                  onClick={() => setIsCategoryModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createCategoryMutation.isPending}
                  className="px-5 py-2.5 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/90 flex items-center gap-2 transition-colors disabled:opacity-50"
                >
                  {createCategoryMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  Create Category
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* USER ACTIVITY & USAGE DRILLDOWN MODAL */}
      {selectedUserForActivity && (
        <div className="admin-modal-overlay" onClick={() => setSelectedUserForActivity(null)}>
          <div className="admin-modal-card admin-modal-card-lg" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-border/50 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-lg text-foreground">
                    {selectedUserForActivity.name || "User Activity"}
                  </h3>
                  <span className={cn(
                    "admin-tier-pill",
                    (selectedUserForActivity.subscription_tier || "free").toLowerCase() === "extreme"
                      ? "admin-tier-extreme"
                      : (selectedUserForActivity.subscription_tier || "free").toLowerCase() === "pro"
                        ? "admin-tier-pro"
                        : "admin-tier-free"
                  )}>
                    {selectedUserForActivity.subscription_tier || "Free"}
                  </span>
                </div>
                <p className="text-xs font-mono text-muted-foreground mt-0.5">
                  {selectedUserForActivity.email} • Registered {selectedUserForActivity.created_at ? new Date(selectedUserForActivity.created_at).toLocaleDateString() : "—"}
                </p>
              </div>
              <button
                onClick={() => setSelectedUserForActivity(null)}
                className="p-1.5 hover:text-foreground text-muted-foreground rounded-lg transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Sub-Tabs inside Modal */}
            <div className="flex border-b border-border/40 px-6 gap-4 bg-muted/20">
              {[
                { id: "orders", label: `Orders (${userActivity?.orders?.length || 0})`, icon: CreditCard },
                { id: "downloads", label: `Downloads (${userActivity?.downloads?.length || 0})`, icon: Download },
                { id: "deployments", label: `Deployments (${userActivity?.deployments?.length || 0})`, icon: Zap },
                { id: "alerts", label: `Security Alerts (${userActivity?.tamper_alerts?.length || 0})`, icon: ShieldAlert },
              ].map((subTab) => {
                const Icon = subTab.icon;
                return (
                  <button
                    key={subTab.id}
                    onClick={() => setActivityTab(subTab.id)}
                    className={cn(
                      "py-3 px-1 text-xs font-semibold border-b-2 flex items-center gap-1.5 transition-colors cursor-pointer",
                      activityTab === subTab.id
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {subTab.label}
                  </button>
                );
              })}
            </div>

            <div className="p-6 overflow-y-auto max-h-[60vh] space-y-4">
              {userActivityLoading ? (
                <div className="py-12 text-center text-muted-foreground">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary" />
                  <span className="block mt-2 text-xs">Loading activity details...</span>
                </div>
              ) : (
                <>
                  {/* ORDERS TAB */}
                  {activityTab === "orders" && (
                    <div className="space-y-3">
                      {userActivity?.orders?.length === 0 ? (
                        <div className="text-center py-8 text-sm text-muted-foreground">
                          No orders placed by this user yet.
                        </div>
                      ) : (
                        userActivity?.orders?.map((ord) => (
                          <div key={ord.id} className="p-3.5 bg-muted/30 border border-border/50 rounded-xl flex items-center justify-between text-xs">
                            <div>
                              <div className="font-semibold text-foreground flex items-center gap-2">
                                <span className="font-mono">{ord.order_number}</span>
                                <span className={cn(
                                  "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                                  ord.status?.toLowerCase() === "completed" ? "bg-green-500/10 text-green-400" : "bg-amber-500/10 text-amber-400"
                                )}>
                                  {ord.status}
                                </span>
                              </div>
                              <div className="text-muted-foreground mt-0.5">
                                {ord.items?.join(", ") || ord.notes || "Template Package"}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="font-bold text-foreground text-sm">${ord.total?.toFixed(2)}</div>
                              <div className="text-muted-foreground text-[11px]">
                                {ord.created_at ? new Date(ord.created_at).toLocaleDateString() : "—"}
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {/* DOWNLOADS TAB */}
                  {activityTab === "downloads" && (
                    <div className="space-y-3">
                      {userActivity?.downloads?.length === 0 ? (
                        <div className="text-center py-8 text-sm text-muted-foreground">
                          No template downloads recorded for this user.
                        </div>
                      ) : (
                        userActivity?.downloads?.map((dl) => (
                          <div key={dl.id} className="p-3.5 bg-muted/30 border border-border/50 rounded-xl flex items-center justify-between text-xs">
                            <div>
                              <div className="font-semibold text-foreground flex items-center gap-2">
                                <span>{dl.template_title}</span>
                                <span className={cn(
                                  "px-2 py-0.2 rounded text-[10px] font-bold uppercase",
                                  dl.is_clean ? "bg-emerald-500/15 text-emerald-400" : "bg-muted text-muted-foreground"
                                )}>
                                  {dl.is_clean ? "Clean (White-Label)" : "Watermarked Standard"}
                                </span>
                              </div>
                              {dl.watermark_text && (
                                <div className="text-muted-foreground text-[11px] mt-0.5">
                                  Watermark text: "{dl.watermark_text}"
                                </div>
                              )}
                            </div>
                            <div className="text-muted-foreground text-[11px] whitespace-nowrap">
                              {dl.created_at ? new Date(dl.created_at).toLocaleString() : "—"}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {/* DEPLOYMENTS TAB */}
                  {activityTab === "deployments" && (
                    <div className="space-y-3">
                      {userActivity?.deployments?.length === 0 ? (
                        <div className="text-center py-8 text-sm text-muted-foreground">
                          No websites currently deployed by this user.
                        </div>
                      ) : (
                        userActivity?.deployments?.map((dep) => (
                          <div key={dep.id} className="p-3.5 bg-muted/30 border border-border/50 rounded-xl flex items-center justify-between text-xs">
                            <div>
                              <div className="font-semibold text-foreground flex items-center gap-2">
                                <span>{dep.project_name || dep.site_id}</span>
                                <span className={cn(
                                  "px-2 py-0.2 rounded text-[10px] font-bold uppercase",
                                  dep.status === "live" ? "bg-green-500/10 text-green-400" : "bg-amber-500/10 text-amber-400"
                                )}>
                                  {dep.status}
                                </span>
                              </div>
                              <div className="font-mono text-muted-foreground text-[11px] mt-0.5">
                                Subdomain: {dep.subdomain || "default"}
                              </div>
                            </div>
                            <div>
                              {dep.live_url && (
                                <a
                                  href={dep.live_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-primary hover:underline flex items-center gap-1 font-semibold"
                                >
                                  Visit Site <ExternalLink className="w-3 h-3" />
                                </a>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {/* SECURITY / TAMPER TAB */}
                  {activityTab === "alerts" && (
                    <div className="space-y-3">
                      {userActivity?.tamper_alerts?.length === 0 ? (
                        <div className="text-center py-8 text-emerald-400 text-sm flex flex-col items-center gap-2">
                          <ShieldCheck className="w-8 h-8" />
                          <span>No tamper incidents or attribution removal attempts detected.</span>
                        </div>
                      ) : (
                        userActivity?.tamper_alerts?.map((al) => (
                          <div key={al.id} className="p-3.5 bg-red-500/10 border border-red-500/20 rounded-xl text-xs space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-rose-400 flex items-center gap-1.5">
                                <AlertTriangle className="w-4 h-4" /> {al.event_type || "Tamper Event"}
                              </span>
                              <span className="text-[11px] text-muted-foreground">
                                {al.created_at ? new Date(al.created_at).toLocaleString() : "—"}
                              </span>
                            </div>
                            <div className="text-foreground">
                              Template: <strong className="font-mono">{al.template_slug}</strong>
                            </div>
                            <div className="text-muted-foreground text-[11px]">
                              Details: {al.details || "Watermark suppression or DOM removal detected"}
                            </div>
                            {al.ip_address && (
                              <div className="font-mono text-[10px] text-muted-foreground">
                                Origin IP: {al.ip_address}
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="p-4 border-t border-border/40 flex justify-end">
              <button
                onClick={() => setSelectedUserForActivity(null)}
                className="px-4 py-2 bg-muted hover:bg-muted/80 text-foreground text-xs font-semibold rounded-xl transition-colors cursor-pointer"
              >
                Close Activity View
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default AdminPanel;
