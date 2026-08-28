"use client";

/**
 * Admin Control Panel Page - manages templates, categories, users list, and system metrics (React JSX).
 */

export const dynamic = "force-dynamic";

import { useState, useEffect } from "react";
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
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { api } from "@/lib/api";
import { cn, formatPrice } from "@/lib/utils";
import "./Page.css";

function AdminPanel() {
  const { getToken } = useAppAuth();
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
    queryFn: () => api.get("/payouts/withdrawals", authToken ?? undefined),
    enabled: !!authToken,
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
    mutationFn: ({ withdrawalId, status }) => api.patch(`/payouts/withdrawals/${withdrawalId}/status`, { status }, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-withdrawals"] });
    },
  });


  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [categoryForm, setCategoryForm] = useState({
    name: "",
    slug: "",
    description: "",
    icon: "Briefcase",
    color: "#6366f1",
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
        color: "#6366f1",
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
              <button
                onClick={() => alert("Scaffolding new template form...")}
                className="px-4 py-2 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/90 flex items-center gap-1.5 transition-colors"
              >
                <Plus className="w-4 h-4" /> Add Template
              </button>
            </div>
          </div>

          {/* Admin Tab Controls */}
          <div className="admin-tab-group">
            {[
              { id: "metrics", label: "Metrics & Logs", icon: TrendingUp },
              { id: "moderation", label: "Moderation & Payouts", icon: Layers },
              { id: "templates", label: "Templates", icon: FileCode },
              { id: "categories", label: "Categories", icon: Layers },
              { id: "users", label: "Users", icon: Users },
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
                    { label: "Gross Sales (USD)", value: `$${platformAnalytics?.gross_sales_usd || stats?.gross_revenue || 0}`, icon: TrendingUp },
                    { label: "Platform Fee Revenue (20%)", value: `$${platformAnalytics?.platform_fee_revenue_usd || stats?.commission_revenue || 0}`, icon: Coins },
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
                      { name: "File Storage Used", status: `${healthData?.components?.storage_used_mb || 0} MB`, color: "text-indigo-400" },
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

            {/* MODERATION & PAYOUTS */}
            {activeTab === "moderation" && (
              <div className="space-y-6">
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
                                  w.status === "completed" ? "bg-green-500/10 text-green-400" : "bg-amber-500/10 text-amber-400"
                                )}>
                                  {w.status}
                                </span>
                              </td>
                              <td className="admin-td text-right" style={{ textAlign: "right" }}>
                                {w.status === "pending" && (
                                  <button
                                    onClick={() => updateWithdrawalStatusMutation.mutate({ withdrawalId: w.id, status: "completed" })}
                                    className="px-3 py-1 bg-green-600 text-white rounded-lg text-xs font-semibold hover:bg-green-500 transition-colors"
                                  >
                                    Approve Payout
                                  </button>
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

            {/* USERS */}
            {activeTab === "users" && (
              <div className="admin-table-container">
                <div className="p-6">
                  <h3 className="font-bold text-base">Platform User Directory</h3>
                  <p className="text-sm text-muted-foreground">Monitor client credentials, role hierarchies.</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="admin-table">
                    <thead>
                      <tr className="admin-tr">
                        <th className="admin-th">User</th>
                        <th className="admin-th">Email</th>
                        <th className="admin-th">Role</th>
                        <th className="admin-th">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50 text-sm">
                      {usersLoading ? (
                        <tr>
                          <td colSpan={4} className="p-8 text-center text-muted-foreground">
                            <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                          </td>
                        </tr>
                      ) : usersResponse?.items?.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="p-8 text-center text-muted-foreground">
                            No users registered yet.
                          </td>
                        </tr>
                      ) : (
                        usersResponse?.items?.map((user) => (
                          <tr key={user.id} className="admin-tr">
                            <td className="admin-td font-semibold">{user.username ?? "Anonymous"}</td>
                            <td className="admin-td font-mono text-xs">{user.email}</td>
                            <td className="admin-td">
                              <span className="px-2 py-0.5 rounded bg-muted font-bold text-xs uppercase text-primary">
                                {user.role}
                              </span>
                            </td>
                            <td className="admin-td">
                              <span className={cn(
                                "px-2 py-0.5 rounded-full text-xs font-semibold inline-block",
                                user.is_active ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"
                              )}>
                                {user.is_active ? "Active" : "Deactivated"}
                              </span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
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
                      value={categoryForm.color || "#6366f1"}
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
    </>
  );
}

export default AdminPanel;
