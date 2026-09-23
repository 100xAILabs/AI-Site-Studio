"use client";

import React, { useState, useMemo } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Clock,
  LayoutGrid,
  List,
  Search,
  RefreshCw,
  Eye,
  ExternalLink,
  Trash2,
  Info,
  Sparkles,
  AlertTriangle,
  FileCode,
  Layers,
  ChevronDown,
  X,
  Check,
  Code2,
  Calendar,
  DollarSign,
  ArrowUpDown,
  Download,
  Terminal,
} from "lucide-react";
import Image from "@/components/Image";
import Link from "@/components/Link";
import { cn } from "@/lib/utils";
import "./AdminModerationHub.css";

export default function AdminModerationHub({
  adminTemplates = [],
  isLoading = false,
  onUpdateStatus,
  onDeleteTemplate,
  onBatchUpdateStatus,
  onRefresh,
  formatPrice = (p) => `$${Number(p || 0).toFixed(2)}`,
}) {
  // ── Filters & Search State ───────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all"); // 'all' | 'draft' | 'published' | 'archived'
  const [frameworkFilter, setFrameworkFilter] = useState("all");
  const [sortBy, setSortBy] = useState("newest"); // 'newest' | 'oldest' | 'price-desc' | 'price-asc'
  const [viewMode, setViewMode] = useState("table"); // 'table' | 'cards'
  const [selectedIds, setSelectedIds] = useState([]);

  // ── Modals & Drawers ─────────────────────────────────────────────────────
  const [inspectingTemplate, setInspectingTemplate] = useState(null);
  const [confirmModal, setConfirmModal] = useState({
    isOpen: false,
    type: null, // 'approve' | 'reject' | 'delete' | 'batch-approve' | 'batch-reject' | 'batch-delete'
    target: null,
    loading: false,
  });

  // ── Toast Notification ───────────────────────────────────────────────────
  const [toast, setToast] = useState(null);

  const showToast = (message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 3500);
  };

  // ── Strict Exclusion of Buyer Customized Personal Drafts ──────────────────
  const moderationTemplates = useMemo(() => {
    return (adminTemplates || []).filter(
      (t) =>
        !t.slug?.includes("-custom-") &&
        !t.title?.includes("(Customized)") &&
        !t.title?.startsWith("Customized ")
    );
  }, [adminTemplates]);

  // ── Metrics Calculation ──────────────────────────────────────────────────
  const metrics = useMemo(() => {
    const total = moderationTemplates.length;
    const inReview = moderationTemplates.filter((t) => t.status === "draft").length;
    const published = moderationTemplates.filter((t) => t.status === "published").length;
    const figmaCount = moderationTemplates.filter((t) => t.is_figma || t.title?.includes("(Figma Import)")).length;
    const archived = moderationTemplates.filter((t) => t.status === "archived").length;
    return { total, inReview, published, figmaCount, archived };
  }, [moderationTemplates]);

  // ── Unique Frameworks List ───────────────────────────────────────────────
  const availableFrameworks = useMemo(() => {
    const set = new Set();
    moderationTemplates.forEach((t) => {
      if (t.framework) set.add(t.framework);
    });
    return Array.from(set).sort();
  }, [moderationTemplates]);

  // ── Filtered & Sorted Templates ──────────────────────────────────────────
  const filteredTemplates = useMemo(() => {
    return moderationTemplates
      .filter((t) => {
        // Status & Category Filter
        if (statusFilter === "draft" && t.status !== "draft") return false;
        if (statusFilter === "published" && t.status !== "published") return false;
        if (statusFilter === "archived" && t.status !== "archived") return false;
        if (statusFilter === "figma" && !t.is_figma && !t.title?.includes("(Figma Import)")) return false;

        // Framework Filter
        if (frameworkFilter !== "all" && t.framework?.toLowerCase() !== frameworkFilter.toLowerCase()) {
          return false;
        }

        // Search Query (Multi-attribute comprehensive search)
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase().trim();
          const matchTitle = t.title?.toLowerCase().includes(q);
          const matchDev = t.developer_name?.toLowerCase().includes(q);
          const matchEmail = t.developer_email?.toLowerCase().includes(q);
          const matchSlug = t.slug?.toLowerCase().includes(q);
          const matchCategory = t.category?.toLowerCase().includes(q);
          const matchFramework = t.framework?.toLowerCase().includes(q);
          const matchTags = (t.tags || []).some((tag) => tag.toLowerCase().includes(q));
          if (!matchTitle && !matchDev && !matchEmail && !matchSlug && !matchCategory && !matchFramework && !matchTags) {
            return false;
          }
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === "newest") {
          const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
          const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
          return dateB - dateA;
        }
        if (sortBy === "oldest") {
          const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
          const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
          return dateA - dateB;
        }
        if (sortBy === "price-desc") return (Number(b.price) || 0) - (Number(a.price) || 0);
        if (sortBy === "price-asc") return (Number(a.price) || 0) - (Number(b.price) || 0);
        if (sortBy === "title") return (a.title || "").localeCompare(b.title || "");
        return 0;
      });
  }, [moderationTemplates, statusFilter, frameworkFilter, searchQuery, sortBy]);

  // ── Multi-select Handlers ────────────────────────────────────────────────
  const isAllSelected =
    filteredTemplates.length > 0 &&
    filteredTemplates.every((t) => selectedIds.includes(t.id));

  const handleToggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredTemplates.map((t) => t.id));
    }
  };

  const handleToggleSelectItem = (id, e) => {
    e.stopPropagation();
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // ── Status & Mutation Actions ────────────────────────────────────────────
  const handleApprove = (template, e) => {
    if (e) e.stopPropagation();
    setConfirmModal({
      isOpen: true,
      type: "approve",
      target: template,
      loading: false,
    });
  };

  const handleReject = (template, e) => {
    if (e) e.stopPropagation();
    setConfirmModal({
      isOpen: true,
      type: "reject",
      target: template,
      loading: false,
    });
  };

  const handleDelete = (template, e) => {
    if (e) e.stopPropagation();
    setConfirmModal({
      isOpen: true,
      type: "delete",
      target: template,
      loading: false,
    });
  };

  const handleBatchApprove = () => {
    setConfirmModal({
      isOpen: true,
      type: "batch-approve",
      target: null,
      loading: false,
    });
  };

  const handleBatchReject = () => {
    setConfirmModal({
      isOpen: true,
      type: "batch-reject",
      target: null,
      loading: false,
    });
  };

  const handleBatchDelete = () => {
    setConfirmModal({
      isOpen: true,
      type: "batch-delete",
      target: null,
      loading: false,
    });
  };

  const executeConfirmAction = async () => {
    setConfirmModal((prev) => ({ ...prev, loading: true }));
    try {
      if (confirmModal.type === "approve") {
        await onUpdateStatus(confirmModal.target.id, "published");
        showToast(`"${confirmModal.target.title}" is now published and live!`);
        if (inspectingTemplate?.id === confirmModal.target.id) {
          setInspectingTemplate((prev) => ({ ...prev, status: "published" }));
        }
      } else if (confirmModal.type === "reject") {
        await onUpdateStatus(confirmModal.target.id, "archived");
        showToast(`"${confirmModal.target.title}" archived / rejected.`, "info");
        if (inspectingTemplate?.id === confirmModal.target.id) {
          setInspectingTemplate((prev) => ({ ...prev, status: "archived" }));
        }
      } else if (confirmModal.type === "delete") {
        await onDeleteTemplate(confirmModal.target.id);
        showToast(`"${confirmModal.target.title}" permanently removed.`);
        if (inspectingTemplate?.id === confirmModal.target.id) {
          setInspectingTemplate(null);
        }
        setSelectedIds((prev) => prev.filter((id) => id !== confirmModal.target.id));
      } else if (confirmModal.type === "batch-approve") {
        if (onBatchUpdateStatus) {
          await onBatchUpdateStatus(selectedIds, "published");
        } else {
          await Promise.all(selectedIds.map((id) => onUpdateStatus(id, "published")));
        }
        showToast(`${selectedIds.length} templates approved and published!`);
        setSelectedIds([]);
      } else if (confirmModal.type === "batch-reject") {
        if (onBatchUpdateStatus) {
          await onBatchUpdateStatus(selectedIds, "archived");
        } else {
          await Promise.all(selectedIds.map((id) => onUpdateStatus(id, "archived")));
        }
        showToast(`${selectedIds.length} templates rejected & archived.`, "info");
        setSelectedIds([]);
      } else if (confirmModal.type === "batch-delete") {
        await Promise.all(selectedIds.map((id) => onDeleteTemplate(id)));
        showToast(`${selectedIds.length} templates deleted permanently.`);
        setSelectedIds([]);
      }
      setConfirmModal({ isOpen: false, type: null, target: null, loading: false });
    } catch (err) {
      console.error("Moderation action error:", err);
      showToast(err?.message || "Action failed to complete", "error");
      setConfirmModal((prev) => ({ ...prev, loading: false }));
    }
  };

  // Helper for framework color styling
  const getFrameworkColor = (fw) => {
    switch (fw?.toLowerCase()) {
      case "react":
        return "text-cyan-800 border-cyan-200 bg-cyan-50";
      case "nextjs":
        return "text-slate-800 border-slate-300 bg-slate-100";
      case "vue":
        return "text-emerald-800 border-emerald-200 bg-emerald-50";
      case "tailwind":
        return "text-sky-800 border-sky-200 bg-sky-50";
      case "html":
        return "text-orange-800 border-orange-200 bg-orange-50";
      case "astro":
        return "text-purple-800 border-purple-200 bg-purple-50";
      default:
        return "text-indigo-800 border-indigo-200 bg-indigo-50";
    }
  };

  return (
    <div className="mod-hub-container">
      {/* ── Top Header & Description ──────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shadow-sm">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
                Template Moderation Hub
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                  Admin Control
                </span>
              </h2>
              <p className="text-xs text-muted-foreground">
                Audit creator submissions, review code compliance, and publish templates to the marketplace.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onRefresh}
            className="mod-icon-btn"
            title="Refresh Moderation Catalog"
          >
            <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin text-primary")} />
          </button>
        </div>
      </div>

      {/* ── KPI Metrics Cards ──────────────────────────────────────────────── */}
      <div className="mod-stats-grid">
        {/* Total Catalog */}
        <div
          onClick={() => setStatusFilter("all")}
          className={cn("mod-stat-card", statusFilter === "all" && "is-active")}
        >
          <div className="mod-stat-icon-wrap mod-stat-icon-indigo">
            <LayoutGrid className="w-5 h-5" />
          </div>
          <div className="mod-stat-content">
            <span className="mod-stat-label">Total Catalog</span>
            <div className="mod-stat-val-row">
              <span className="mod-stat-value">{metrics.total}</span>
              <span className="mod-stat-pill bg-indigo-50 text-indigo-700 border border-indigo-200">
                All Items
              </span>
            </div>
          </div>
        </div>

        {/* Pending Review / In Review */}
        <div
          onClick={() => setStatusFilter("draft")}
          className={cn("mod-stat-card", statusFilter === "draft" && "is-active")}
        >
          <div className="mod-stat-icon-wrap mod-stat-icon-amber">
            <Clock className="w-5 h-5" />
          </div>
          <div className="mod-stat-content">
            <span className="mod-stat-label">Pending Review</span>
            <div className="mod-stat-val-row">
              <span className="mod-stat-value text-amber-600">{metrics.inReview}</span>
              {metrics.inReview > 0 ? (
                <span className="mod-stat-pill bg-amber-50 text-amber-700 border border-amber-200 animate-pulse">
                  Needs Action
                </span>
              ) : (
                <span className="mod-stat-pill bg-muted text-muted-foreground">Clear</span>
              )}
            </div>
          </div>
        </div>

        {/* Published & Live */}
        <div
          onClick={() => setStatusFilter("published")}
          className={cn("mod-stat-card", statusFilter === "published" && "is-active")}
        >
          <div className="mod-stat-icon-wrap mod-stat-icon-emerald">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div className="mod-stat-content">
            <span className="mod-stat-label">Live & Published</span>
            <div className="mod-stat-val-row">
              <span className="mod-stat-value text-emerald-600">{metrics.published}</span>
              <span className="mod-stat-pill bg-emerald-50 text-emerald-700 border border-emerald-200">
                Active
              </span>
            </div>
          </div>
        </div>

        {/* Archived / Rejected */}
        <div
          onClick={() => setStatusFilter("archived")}
          className={cn("mod-stat-card", statusFilter === "archived" && "is-active")}
        >
          <div className="mod-stat-icon-wrap mod-stat-icon-rose">
            <XCircle className="w-5 h-5" />
          </div>
          <div className="mod-stat-content">
            <span className="mod-stat-label">Archived / Rejected</span>
            <div className="mod-stat-val-row">
              <span className="mod-stat-value text-rose-600">{metrics.archived}</span>
              <span className="mod-stat-pill bg-rose-50 text-rose-700 border border-rose-200">
                Offline
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Filter & Search Toolbar ────────────────────────────────────────── */}
      <div className="mod-toolbar">
        {/* Status Filter Tabs */}
        <div className="mod-status-tabs">
          <button
            type="button"
            onClick={() => setStatusFilter("all")}
            className={cn("mod-tab-btn", statusFilter === "all" && "is-active")}
          >
            All Submissions
            <span className="mod-tab-badge">{metrics.total}</span>
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("draft")}
            className={cn("mod-tab-btn", statusFilter === "draft" && "is-active")}
          >
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            In Review
            <span className="mod-tab-badge">{metrics.inReview}</span>
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("published")}
            className={cn("mod-tab-btn", statusFilter === "published" && "is-active")}
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Approved &amp; Live
            <span className="mod-tab-badge">{metrics.published}</span>
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("figma")}
            className={cn("mod-tab-btn", statusFilter === "figma" && "is-active")}
          >
            <Sparkles className="w-3.5 h-3.5 text-purple-500" />
            Figma Imports
            <span className="mod-tab-badge">{metrics.figmaCount}</span>
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("archived")}
            className={cn("mod-tab-btn", statusFilter === "archived" && "is-active")}
          >
            <span className="w-2 h-2 rounded-full bg-slate-400" />
            Archived
            <span className="mod-tab-badge">{metrics.archived}</span>
          </button>
        </div>

        {/* Search, Framework & View Controls */}
        <div className="mod-search-and-controls">
          <div className="mod-search-box">
            <Search className="mod-search-icon" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search templates, creator, tech..."
              className="mod-search-input"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="mod-search-clear"
                title="Clear search"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Framework Selector */}
          <select
            value={frameworkFilter}
            onChange={(e) => setFrameworkFilter(e.target.value)}
            className="mod-select-filter"
            title="Filter by framework"
          >
            <option value="all">All Tech Stacks</option>
            {availableFrameworks.map((fw) => (
              <option key={fw} value={fw}>
                {fw.toUpperCase()}
              </option>
            ))}
          </select>

          {/* Sort By Dropdown */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="mod-select-filter"
            title="Sort templates"
          >
            <option value="newest">Newest First</option>
            <option value="oldest">Oldest First</option>
            <option value="price-desc">Price: High to Low</option>
            <option value="price-asc">Price: Low to High</option>
            <option value="title">Title (A-Z)</option>
          </select>

          {/* View Mode Toggle */}
          <div className="flex items-center bg-muted/70 p-0.5 rounded-xl border border-border">
            <button
              type="button"
              onClick={() => setViewMode("table")}
              className={cn("mod-icon-btn !w-8 !h-8 !border-0", viewMode === "table" && "is-active")}
              title="Table density view"
            >
              <List className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setViewMode("cards")}
              className={cn("mod-icon-btn !w-8 !h-8 !border-0", viewMode === "cards" && "is-active")}
              title="Visual cards view"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* ── Batch Actions Floating Bar ──────────────────────────────────────── */}
      {selectedIds.length > 0 && (
        <div className="mod-batch-bar">
          <div className="mod-batch-left">
            <span className="mod-batch-count">
              {selectedIds.length} {selectedIds.length === 1 ? "template" : "templates"} selected
            </span>
            <button
              type="button"
              onClick={() => setSelectedIds([])}
              className="text-xs text-muted-foreground hover:text-foreground underline ml-2"
            >
              Deselect all
            </button>
          </div>

          <div className="mod-batch-actions">
            <button
              type="button"
              onClick={handleBatchApprove}
              className="mod-btn-action mod-btn-approve"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Batch Approve
            </button>
            <button
              type="button"
              onClick={handleBatchReject}
              className="mod-btn-action mod-btn-reject"
            >
              <XCircle className="w-3.5 h-3.5" />
              Batch Archive
            </button>
            <button
              type="button"
              onClick={handleBatchDelete}
              className="mod-btn-action mod-btn-delete"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete Selected
            </button>
          </div>
        </div>
      )}

      {/* ── Main Data View (Table or Cards) ─────────────────────────────────── */}
      <div className="mod-glass-card p-4 sm:p-6 space-y-4">
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <RefreshCw className="w-7 h-7 animate-spin text-primary" />
            <p className="text-xs font-semibold uppercase tracking-wider">
              Loading moderation audit queue...
            </p>
          </div>
        ) : filteredTemplates.length === 0 ? (
          <div className="py-16 flex flex-col items-center justify-center text-center gap-3">
            <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-muted-foreground">
              <ShieldCheck className="w-7 h-7 text-primary/60" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-bold text-foreground">No templates found</h3>
              <p className="text-xs text-muted-foreground max-w-sm">
                {searchQuery || statusFilter !== "all" || frameworkFilter !== "all"
                  ? "Try resetting your search filters or selecting a different status tab."
                  : "All creator templates have been audited. No pending submissions in queue."}
              </p>
            </div>
            {(searchQuery || statusFilter !== "all" || frameworkFilter !== "all") && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setStatusFilter("all");
                  setFrameworkFilter("all");
                }}
                className="mt-2 text-xs font-semibold text-primary hover:underline"
              >
                Clear all active filters
              </button>
            )}
          </div>
        ) : viewMode === "table" ? (
          /* ── Table View ──────────────────────────────────────────────────── */
          <div className="mod-table-wrap">
            <table className="mod-table">
              <thead>
                <tr>
                  <th style={{ width: "40px" }}>
                    <label className="mod-checkbox-label" title="Select all visible">
                      <input
                        type="checkbox"
                        checked={isAllSelected}
                        onChange={handleToggleSelectAll}
                        className="mod-checkbox-input"
                      />
                    </label>
                  </th>
                  <th>Template</th>
                  <th>Developer</th>
                  <th>Tech / Pricing</th>
                  <th>Moderation Status</th>
                  <th style={{ textAlign: "right" }}>Moderation Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredTemplates.map((t) => {
                  const isSelected = selectedIds.includes(t.id);
                  const isDraft = t.status === "draft";
                  const isPublished = t.status === "published";
                  const isArchived = t.status === "archived";

                  return (
                    <tr
                      key={t.id}
                      className={cn(isSelected && "is-selected")}
                      onClick={() => setInspectingTemplate(t)}
                      style={{ cursor: "pointer" }}
                    >
                      {/* Checkbox Column */}
                      <td onClick={(e) => e.stopPropagation()}>
                        <label className="mod-checkbox-label">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={(e) => handleToggleSelectItem(t.id, e)}
                            className="mod-checkbox-input"
                          />
                        </label>
                      </td>

                      {/* Template Column */}
                      <td>
                        <div className="mod-cell-template">
                          <div className="mod-thumb-box">
                            {t.thumbnail_url ? (
                              <Image
                                src={t.thumbnail_url}
                                alt={t.title}
                                className="mod-thumb-img"
                              />
                            ) : (
                              <div className="mod-thumb-fallback">
                                <Code2 className="w-4 h-4" />
                              </div>
                            )}
                          </div>
                          <div className="mod-meta-info">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setInspectingTemplate(t);
                              }}
                              className="mod-title-btn"
                              title={t.title}
                            >
                              {t.title}
                            </button>
                            <div className="mod-tags-row">
                              {Boolean(t.is_figma || t.title?.includes("(Figma Import)")) && (
                                <span className="mod-category-pill !bg-purple-500/10 !text-purple-600 dark:!text-purple-400 !border-purple-500/20 font-bold flex items-center gap-1">
                                  <Sparkles className="w-2.5 h-2.5" /> Figma
                                </span>
                              )}
                              <span className="mod-category-pill">
                                {t.category || "General"}
                              </span>
                              {t.pages_count > 0 && (
                                <span className="mod-category-pill">
                                  {t.pages_count} {t.pages_count === 1 ? "page" : "pages"}
                                </span>
                              )}
                              {t.is_ai_ready && (
                                <span className="mod-ai-pill">
                                  <Sparkles className="w-2.5 h-2.5" /> AI Ready
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Developer Column */}
                      <td>
                        <div className="mod-cell-developer">
                          <div className="mod-avatar">
                            {t.developer_avatar ? (
                              <Image src={t.developer_avatar} alt={t.developer_name} />
                            ) : (
                              <span>{(t.developer_name || "P").slice(0, 2).toUpperCase()}</span>
                            )}
                          </div>
                          <div>
                            <div className="mod-dev-name font-bold text-foreground text-xs">{t.developer_name || "Platform Creator"}</div>
                            {t.developer_email && (
                              <div className="text-[11px] text-muted-foreground truncate max-w-[150px]" title={t.developer_email}>
                                {t.developer_email}
                              </div>
                            )}
                            <div className="mod-dev-role text-[10px] text-muted-foreground mt-0.5">
                              {t.created_at
                                ? new Date(t.created_at).toLocaleDateString(undefined, {
                                    month: "short",
                                    day: "numeric",
                                    year: "numeric",
                                  })
                                : "Uploaded recently"}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Tech & Pricing */}
                      <td>
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-1.5">
                            {t.framework && (
                              <span
                                className={cn(
                                  "mod-framework-badge",
                                  getFrameworkColor(t.framework)
                                )}
                              >
                                {t.framework}
                              </span>
                            )}
                            <span className="text-[10px] text-muted-foreground font-mono">
                              v{t.version || "1.0.0"}
                            </span>
                          </div>
                          <div>
                            {Number(t.price) > 0 ? (
                              <span className="mod-price-tag">{formatPrice(t.price)}</span>
                            ) : (
                              <span className="mod-price-free">FREE</span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Status Column with glowing dot */}
                      <td>
                        {isPublished ? (
                          <span className="mod-status-badge mod-status-approved">
                            <span className="mod-status-dot" />
                            Approved & Live
                          </span>
                        ) : isDraft ? (
                          <span className="mod-status-badge mod-status-in-review">
                            <span className="mod-status-dot" />
                            In Review
                          </span>
                        ) : (
                          <span className="mod-status-badge mod-status-archived">
                            <span className="mod-status-dot" />
                            Archived
                          </span>
                        )}
                      </td>

                      {/* Moderation Actions Column */}
                      <td onClick={(e) => e.stopPropagation()}>
                        <div className="mod-actions-cell">
                          {/* Approve Action */}
                          <button
                            type="button"
                            onClick={(e) => handleApprove(t, e)}
                            disabled={isPublished}
                            className="mod-btn-action mod-btn-approve"
                            title={isPublished ? "Already approved & live" : "Approve and publish to marketplace"}
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            {isPublished ? "Live" : "Approve"}
                          </button>

                          {/* Reject / Archive Action */}
                          <button
                            type="button"
                            onClick={(e) => handleReject(t, e)}
                            disabled={isArchived}
                            className="mod-btn-action mod-btn-reject"
                            title={isArchived ? "Already archived" : "Archive / Reject template"}
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            {isArchived ? "Archived" : "Reject"}
                          </button>

                          {/* Live Preview Button */}
                          <a
                            href={t.preview_url || `/preview?template=${t.id}&mode=live`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="mod-btn-action mod-btn-preview"
                            title="Open live sandboxed preview in new tab"
                          >
                            <ExternalLink className="w-3.5 h-3.5 text-blue-500" />
                            Live Demo
                          </a>

                          {/* Inspect Info Button */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setInspectingTemplate(t);
                            }}
                            className="mod-btn-icon-action mod-btn-info"
                            title="Audit & view template details"
                          >
                            <Info className="w-3.5 h-3.5" />
                          </button>

                          {/* Delete Button (Sleek red glass button) */}
                          <button
                            type="button"
                            onClick={(e) => handleDelete(t, e)}
                            className="mod-btn-icon-action mod-btn-delete"
                            title="Delete template permanently"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          /* ── Cards Grid View ─────────────────────────────────────────────── */
          <div className="mod-cards-grid">
            {filteredTemplates.map((t) => {
              const isSelected = selectedIds.includes(t.id);
              const isDraft = t.status === "draft";
              const isPublished = t.status === "published";
              const isArchived = t.status === "archived";

              return (
                <div
                  key={t.id}
                  className={cn("mod-card-item", isSelected && "is-selected")}
                  onClick={() => setInspectingTemplate(t)}
                  style={{ cursor: "pointer" }}
                >
                  {/* Media Viewport */}
                  <div className="mod-card-media">
                    {t.thumbnail_url ? (
                      <Image src={t.thumbnail_url} alt={t.title} className="mod-card-img" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-muted/20 text-muted-foreground">
                        <Code2 className="w-8 h-8 opacity-40" />
                      </div>
                    )}

                    {/* Checkbox Overlay */}
                    <div className="mod-card-checkbox" onClick={(e) => e.stopPropagation()}>
                      <label className="mod-checkbox-label">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={(e) => handleToggleSelectItem(t.id, e)}
                          className="mod-checkbox-input"
                        />
                      </label>
                    </div>

                    {/* Status Badge Overlay */}
                    <div className="mod-card-status-badge">
                      {isPublished ? (
                        <span className="mod-status-badge mod-status-approved">
                          <span className="mod-status-dot" />
                          Live
                        </span>
                      ) : isDraft ? (
                        <span className="mod-status-badge mod-status-in-review">
                          <span className="mod-status-dot" />
                          Review
                        </span>
                      ) : (
                        <span className="mod-status-badge mod-status-archived">
                          <span className="mod-status-dot" />
                          Archived
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="mod-card-body">
                    <div className="flex items-center justify-between gap-2">
                      <span className="mod-category-pill">{t.category || "General"}</span>
                      {t.framework && (
                        <span
                          className={cn("mod-framework-badge", getFrameworkColor(t.framework))}
                        >
                          {t.framework}
                        </span>
                      )}
                    </div>

                    <div>
                      <h4 className="font-bold text-sm text-foreground line-clamp-1 group-hover:text-primary">
                        {t.title}
                      </h4>
                      <p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5">
                        {t.short_description || `By ${t.developer_name || "Unknown Creator"}`}
                      </p>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-white/5 text-xs">
                      <div className="flex items-center gap-1.5">
                        <div className="mod-avatar !w-5 !h-5 !text-[9px]">
                          {(t.developer_name || "U").slice(0, 1).toUpperCase()}
                        </div>
                        <span className="text-[11px] text-muted-foreground font-medium">
                          {t.developer_name || "Unknown"}
                        </span>
                      </div>
                      <span className="font-bold text-primary">
                        {Number(t.price) > 0 ? formatPrice(t.price) : "FREE"}
                      </span>
                    </div>
                  </div>

                  {/* Card Footer Actions */}
                  <div className="mod-card-footer" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={(e) => handleApprove(t, e)}
                        disabled={isPublished}
                        className="mod-btn-action mod-btn-approve !px-2 !py-1 !text-[11px]"
                        title="Approve & publish"
                      >
                        <CheckCircle2 className="w-3 h-3" />
                        Approve
                      </button>
                      <button
                        type="button"
                        onClick={(e) => handleReject(t, e)}
                        disabled={isArchived}
                        className="mod-btn-action mod-btn-reject !px-2 !py-1 !text-[11px]"
                        title="Reject & archive"
                      >
                        <XCircle className="w-3 h-3" />
                        Reject
                      </button>
                    </div>

                    <div className="flex items-center gap-1">
                      <a
                        href={t.preview_url || `/preview?template=${t.id}&mode=live`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mod-btn-icon-action mod-btn-preview !w-7 !h-7"
                        title="Live Demo Preview"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                      <button
                        type="button"
                        onClick={(e) => handleDelete(t, e)}
                        className="mod-btn-icon-action mod-btn-delete !w-7 !h-7"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Footer info banner */}
        {!isLoading && filteredTemplates.length > 0 && (
          <div className="pt-3 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between text-[11px] text-muted-foreground gap-2">
            <div>
              Showing <span className="font-bold text-foreground">{filteredTemplates.length}</span> of{" "}
              <span className="font-bold text-foreground">{adminTemplates.length}</span> templates in catalog
            </div>
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-400" /> Pending Review
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400" /> Approved & Live
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-slate-400" /> Archived
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ── Inspection / Audit Details Modal ───────────────────────────────── */}
      {inspectingTemplate && (
        <div className="mod-modal-overlay" onClick={() => setInspectingTemplate(null)}>
          <div className="mod-modal-content" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="mod-modal-header">
              <div className="mod-modal-title">
                <ShieldCheck className="w-5 h-5 text-primary" />
                Template Audit Inspector
              </div>
              <button
                type="button"
                onClick={() => setInspectingTemplate(null)}
                className="mod-modal-close"
                title="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="mod-modal-body">
              {/* Media Preview Banner */}
              <div className="relative h-48 sm:h-56 rounded-xl overflow-hidden border border-border bg-muted/30">
                {inspectingTemplate.thumbnail_url ? (
                  <Image
                    src={inspectingTemplate.thumbnail_url}
                    alt={inspectingTemplate.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                    <Code2 className="w-12 h-12 opacity-30" />
                  </div>
                )}
                <div className="absolute top-3 right-3 flex items-center gap-2">
                  <a
                    href={inspectingTemplate.preview_url || `/preview?template=${inspectingTemplate.id}&mode=live`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 rounded-lg bg-black/75 backdrop-blur-md border border-white/20 text-xs font-bold text-white hover:bg-black transition-colors flex items-center gap-1.5 shadow-lg"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    Open Live Canvas
                  </a>
                  <a
                    href={`/marketplace/${inspectingTemplate.slug}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 rounded-lg bg-black/75 backdrop-blur-md border border-white/20 text-xs font-bold text-white hover:bg-black/90 transition-colors flex items-center gap-1.5 shadow-lg"
                  >
                    Marketplace View
                  </a>
                </div>

                <div className="absolute bottom-3 left-3">
                  {inspectingTemplate.status === "published" ? (
                    <span className="mod-status-badge mod-status-approved shadow-md backdrop-blur-md bg-white/95">
                      <span className="mod-status-dot" /> Approved & Live
                    </span>
                  ) : inspectingTemplate.status === "draft" ? (
                    <span className="mod-status-badge mod-status-in-review shadow-md backdrop-blur-md bg-white/95">
                      <span className="mod-status-dot" /> Pending Review
                    </span>
                  ) : (
                    <span className="mod-status-badge mod-status-archived shadow-md backdrop-blur-md bg-white/95">
                      <span className="mod-status-dot" /> Archived / Rejected
                    </span>
                  )}
                </div>
              </div>

              {/* Title & Creator */}
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-foreground">{inspectingTemplate.title}</h3>
                <p className="text-xs text-muted-foreground font-mono">
                  Slug: /{inspectingTemplate.slug} • ID: {inspectingTemplate.id}
                </p>
              </div>

              {/* Specs Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-muted/40 border border-border space-y-1">
                  <div className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider">Category</div>
                  <div className="text-xs font-bold text-foreground">{inspectingTemplate.category || "General"}</div>
                </div>
                <div className="p-3 rounded-xl bg-muted/40 border border-border space-y-1">
                  <div className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider">Framework</div>
                  <div className="text-xs font-bold text-primary uppercase">{inspectingTemplate.framework || "HTML"}</div>
                </div>
                <div className="p-3 rounded-xl bg-muted/40 border border-border space-y-1">
                  <div className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider">Price</div>
                  <div className="text-xs font-bold text-emerald-600">
                    {Number(inspectingTemplate.price) > 0 ? formatPrice(inspectingTemplate.price) : "FREE"}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-muted/40 border border-border space-y-1">
                  <div className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider">Pages Count</div>
                  <div className="text-xs font-bold text-foreground">
                    {inspectingTemplate.pages_count || 1} Pages Included
                  </div>
                </div>
              </div>

              {/* Creator Card */}
              <div className="p-3.5 rounded-xl bg-muted/30 border border-border flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="mod-avatar !w-9 !h-9">
                    {inspectingTemplate.developer_avatar ? (
                      <Image src={inspectingTemplate.developer_avatar} alt={inspectingTemplate.developer_name} />
                    ) : (
                      <span>{(inspectingTemplate.developer_name || "U").slice(0, 2).toUpperCase()}</span>
                    )}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-foreground">
                      {inspectingTemplate.developer_name || "Unknown Creator"}
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      Template Author • Submitted{" "}
                      {inspectingTemplate.created_at
                        ? new Date(inspectingTemplate.created_at).toLocaleDateString()
                        : "recently"}
                    </div>
                  </div>
                </div>
                {inspectingTemplate.is_ai_ready && (
                  <span className="mod-ai-pill !text-xs !py-1 !px-2.5">
                    <Sparkles className="w-3 h-3" /> AI Canvas Ready
                  </span>
                )}
              </div>

              {/* Quality Audit Checklist */}
              <div className="p-4 rounded-xl bg-indigo-50/70 border border-indigo-200/80 space-y-3">
                <div className="text-xs font-bold text-indigo-900 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-primary" />
                  Marketplace Quality Standard Checks
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  <div className="flex items-center gap-2 text-slate-700 font-medium">
                    <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 font-bold" />
                    <span>Clean directory & code structure</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-700 font-medium">
                    <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 font-bold" />
                    <span>Mobile responsive & dark mode</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-700 font-medium">
                    <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 font-bold" />
                    <span>Zero missing pages compliance</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-700 font-medium">
                    <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 font-bold" />
                    <span>Standalone backend API ready</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer Actions */}
            <div className="mod-modal-footer">
              <button
                type="button"
                onClick={() => handleDelete(inspectingTemplate)}
                className="px-3.5 py-2 rounded-xl text-xs font-bold text-rose-700 bg-rose-50 border border-rose-200 hover:bg-rose-100 transition-colors flex items-center gap-1.5 mr-auto cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete Template
              </button>

              {inspectingTemplate.status !== "archived" && (
                <button
                  type="button"
                  onClick={() => handleReject(inspectingTemplate)}
                  className="px-3.5 py-2 rounded-xl text-xs font-bold text-amber-800 bg-amber-50 border border-amber-200 hover:bg-amber-100 transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Archive / Reject
                </button>
              )}

              {inspectingTemplate.status !== "published" && (
                <button
                  type="button"
                  onClick={() => handleApprove(inspectingTemplate)}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/20 transition-all flex items-center gap-1.5 cursor-pointer"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Approve & Publish
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Custom Confirmation Modal ──────────────────────────────────────── */}
      {confirmModal.isOpen && (
        <div
          className="mod-modal-overlay"
          onClick={() =>
            !confirmModal.loading &&
            setConfirmModal({ isOpen: false, type: null, target: null, loading: false })
          }
        >
          <div
            className="mod-modal-content !max-w-md"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mod-modal-header">
              <div className="mod-modal-title text-base">
                {confirmModal.type === "delete" || confirmModal.type === "batch-delete" ? (
                  <AlertTriangle className="w-5 h-5 text-rose-400" />
                ) : confirmModal.type === "approve" || confirmModal.type === "batch-approve" ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                ) : (
                  <XCircle className="w-5 h-5 text-amber-400" />
                )}
                {confirmModal.type === "delete" && "Delete Template"}
                {confirmModal.type === "batch-delete" && "Batch Delete Templates"}
                {confirmModal.type === "approve" && "Publish Template"}
                {confirmModal.type === "batch-approve" && "Batch Approve Templates"}
                {confirmModal.type === "reject" && "Archive / Reject Template"}
                {confirmModal.type === "batch-reject" && "Batch Archive Templates"}
              </div>
              <button
                type="button"
                disabled={confirmModal.loading}
                onClick={() =>
                  setConfirmModal({ isOpen: false, type: null, target: null, loading: false })
                }
                className="mod-modal-close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mod-modal-body text-xs text-muted-foreground leading-relaxed">
              {confirmModal.type === "delete" && (
                <p>
                  Are you sure you want to permanently delete{" "}
                  <strong className="text-foreground font-semibold">
                    "{confirmModal.target?.title}"
                  </strong>
                  ? All files, reviews, and associated records will be permanently removed.
                </p>
              )}
              {confirmModal.type === "batch-delete" && (
                <p>
                  Are you sure you want to permanently delete all{" "}
                  <strong className="text-foreground font-semibold">
                    {selectedIds.length} selected templates
                  </strong>
                  ? This action cannot be undone.
                </p>
              )}
              {confirmModal.type === "approve" && (
                <p>
                  Approve{" "}
                  <strong className="text-foreground font-semibold">
                    "{confirmModal.target?.title}"
                  </strong>{" "}
                  and make it immediately visible and searchable across the marketplace?
                </p>
              )}
              {confirmModal.type === "batch-approve" && (
                <p>
                  Approve and publish all{" "}
                  <strong className="text-foreground font-semibold">
                    {selectedIds.length} selected templates
                  </strong>{" "}
                  to the marketplace catalog?
                </p>
              )}
              {confirmModal.type === "reject" && (
                <p>
                  Move{" "}
                  <strong className="text-foreground font-semibold">
                    "{confirmModal.target?.title}"
                  </strong>{" "}
                  to archived status? It will be hidden from the public marketplace.
                </p>
              )}
              {confirmModal.type === "batch-reject" && (
                <p>
                  Move all{" "}
                  <strong className="text-foreground font-semibold">
                    {selectedIds.length} selected templates
                  </strong>{" "}
                  to archived status?
                </p>
              )}
            </div>

            <div className="mod-modal-footer">
              <button
                type="button"
                disabled={confirmModal.loading}
                onClick={() =>
                  setConfirmModal({ isOpen: false, type: null, target: null, loading: false })
                }
                className="px-4 py-2 rounded-xl border border-border text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={confirmModal.loading}
                onClick={executeConfirmAction}
                className={cn(
                  "px-4 py-1.5 rounded-xl text-xs font-bold text-white transition-all shadow-lg flex items-center gap-1.5",
                  confirmModal.type === "delete" || confirmModal.type === "batch-delete"
                    ? "bg-rose-600 hover:bg-rose-500 shadow-rose-600/30"
                    : confirmModal.type === "approve" || confirmModal.type === "batch-approve"
                    ? "bg-emerald-600 hover:bg-emerald-500 shadow-emerald-600/30"
                    : "bg-amber-600 hover:bg-amber-500 shadow-amber-600/30"
                )}
              >
                {confirmModal.loading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                Confirm Action
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Toast Alert ────────────────────────────────────────────────────── */}
      {toast && (
        <div className="mod-toast">
          {toast.type === "error" ? (
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          )}
          <span>{toast.message}</span>
        </div>
      )}
    </div>
  );
}
