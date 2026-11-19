"use client";

/**
 * Marketplace Page — split layout: sidebar filters + template grid + toolbar (React JSX).
 */

export const dynamic = "force-dynamic";

import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import Link, { navigate } from "@/components/Link";
const useRouter = () => ({
  push: (to) => navigate(to),
  replace: (to) => navigate(to),
});
const useSearchParams = () => new URLSearchParams(window.location.search);
import { useAppAuth, useAppUser } from "@/lib/auth";
import {
  Search, X, Sparkles, SlidersHorizontal, Filter,
  TrendingUp, ArrowRight, CornerDownLeft, Eye, Zap, Layers,
  UploadCloud, MessageCircle, ShoppingBag, Download, Star,
  CheckCircle2, Copy, ExternalLink, ShieldCheck, Loader2,
  Play, Check, Globe, Tag, AlertCircle,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import Navbar from "@/components/layout/Navbar";
import SidebarFilters from "@/components/marketplace/SidebarFilters";
import TemplateGrid from "@/components/marketplace/TemplateGrid";
import SecretsEnvManager from "@/components/deploy/SecretsEnvManager";
import { useTemplates, useToggleFavorite, useToggleWishlist } from "@/hooks/useTemplates";
import { useFilterStore } from "@/store";
import { useAuthStore } from "@/store/authStore";
import { cn, debounce } from "@/lib/utils";
import { api } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import "./Page.css";

const SORT_OPTIONS = [
  { value: "newest", label: "Newest" },
  { value: "best_sellers", label: "Best Sellers" },
  { value: "best_rated", label: "Best Rated" },
  { value: "trending", label: "Trending" },
  { value: "lowest_price", label: "Lowest Price" },
  { value: "highest_price", label: "Highest Price" },
  { value: "most_downloaded", label: "Most Downloaded" },
];

const QUICK_CATEGORIES = [
  { label: "All Templates", value: "" },
  { label: "Business", value: "business" },
  { label: "SaaS & Tech", value: "saas-technology" },
  { label: "Ecommerce", value: "ecommerce" },
  { label: "Landing Pages", value: "landing-pages" },
  { label: "Dashboards", value: "dashboards" },
  { label: "Portfolio", value: "portfolio" },
  { label: "Agency", value: "creative-agency" },
  { label: "Restaurant", value: "restaurant-food" },
  { label: "Healthcare", value: "healthcare" },
  { label: "Education", value: "education" },
  { label: "Real Estate", value: "real-estate" },
  { label: "Events", value: "events" },
  { label: "Travel", value: "travel" },
  { label: "Fitness", value: "fitness" },
  { label: "Beauty", value: "beauty" },
  { label: "Legal", value: "legal" },
  { label: "NGO & Charity", value: "ngo-charity" },
  { label: "Automotive", value: "automotive" },
  { label: "Blog & Magazine", value: "blog-magazine" },
  { label: "Gaming", value: "gaming" },
  { label: "Finance", value: "finance" },
  { label: "Entertainment", value: "entertainment" },
  { label: "Documentation", value: "documentation" },
  { label: "Authentication", value: "authentication" },
  { label: "Marketplace", value: "marketplace" },
];

const TRENDING_SEARCHES = [
  "Crime Portfolio",
  "Creative Agency",
  "Hotel & Resort",
  "SaaS Dashboard",
  "React & Tailwind",
  "Modern Portfolio",
];

function highlightSearchMatch(text, query) {
  if (!query || !text) return text;
  const escaped = query.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  if (!escaped) return text;
  const regex = new RegExp(`(${escaped})`, "gi");
  const parts = text.split(regex);
  return parts.map((part, i) =>
    part.toLowerCase() === query.trim().toLowerCase() ? (
      <strong key={i} className="text-[#dfb180] font-bold underline decoration-[#dfb180]/50">
        {part}
      </strong>
    ) : (
      part
    )
  );
}

function Marketplace() {
  const { getToken } = useAppAuth();
  const { filters, setFilter, setFilters, resetFilters } = useFilterStore();
  const [searchInput, setSearchInput] = useState(filters.q ?? "");
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  const activeFilterCount = [
    filters.category,
    filters.sub_category,
    filters.technology,
    filters.min_price !== undefined || filters.max_price !== undefined,
    filters.is_on_sale,
    filters.sales,
    filters.rating,
    filters.compatibility,
    filters.language,
    filters.date_added,
    filters.developer,
  ].filter(Boolean).length;
  const searchParams = useSearchParams();

  // Sync URL params → store on mount
  useEffect(() => {
    const params = {};
    searchParams.forEach((v, k) => { params[k] = v; });
    if (Object.keys(params).length > 0) {
      setFilters({
        category: params.category,
        sub_category: params.sub_category,
        technology: params.technology,
        q: params.q,
        sort: params.sort ?? "newest",
        page: params.page ? Number(params.page) : 1,
        min_price: params.min_price ? Number(params.min_price) : undefined,
        max_price: params.max_price ? Number(params.max_price) : undefined,
        is_on_sale: params.is_on_sale !== undefined ? (params.is_on_sale === "true" || params.is_on_sale === true) : undefined,
        sales: params.sales,
        rating: params.rating ? Number(params.rating) : undefined,
        compatibility: params.compatibility,
        language: params.language,
        date_added: params.date_added,
        developer: params.developer,
      });
      if (params.q) {
        setSearchInput(params.q);
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep browser URL updated with active filters
  useEffect(() => {
    const urlParams = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        if (k === "sort" && v === "newest") return;
        if (k === "page" && v === 1) return;
        if (k === "page_size") return;
        urlParams.set(k, String(v));
      }
    });
    const queryString = urlParams.toString();
    const newUrl = queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname;
    window.history.replaceState({}, "", newUrl);
  }, [filters]);

  // Fetch categories dynamically (long-lived cache)
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get("/categories"),
    staleTime: 1000 * 60 * 60, // 1 hour fresh
    gcTime: 1000 * 60 * 60 * 24, // 24 hours in memory
    placeholderData: (prev) => prev,
  });

  // Auth token for mutations — initialized synchronously from store
  const { user, isSignedIn } = useAppUser();
  const roleStr = String(user?.role || "").toLowerCase().trim();
  const isAdmin = isSignedIn && (roleStr === "admin" || roleStr === "super_admin");
  const isExtreme = isSignedIn && (
    Boolean(user?.can_retail_templates) ||
    Boolean(user?.is_extreme_subscriber) ||
    ["extreme", "agency", "enterprise"].includes(String(user?.subscription_tier || "").toLowerCase().trim()) ||
    isAdmin
  );

  const [token, setToken] = useState(() => useAuthStore.getState().token);
  useEffect(() => {
    getToken().then(setToken);
  }, [getToken]);

  const effectiveFilters = useMemo(() => {
    return filters;
  }, [filters]);

  const { data, isLoading } = useTemplates(effectiveFilters, token);
  const favoriteMutation = useToggleFavorite(token ?? "");
  const wishlistMutation = useToggleWishlist(token ?? "");

  // ── Active View Mode: "all" vs "purchased" ──────────────────────────────
  const viewParam = searchParams.get("view");
  const [activeViewMode, setActiveViewMode] = useState(viewParam === "purchased" ? "purchased" : "all");

  useEffect(() => {
    if (viewParam === "purchased") {
      setActiveViewMode("purchased");
    }
  }, [viewParam]);

  // User completed orders
  const { data: userOrders = [], isLoading: ordersLoading } = useQuery({
    queryKey: ["user-orders", token],
    queryFn: async () => {
      if (!token) return [];
      try {
        const res = await api.get("/orders");
        return res?.items || res || [];
      } catch {
        return [];
      }
    },
    enabled: !!token,
  });

  // User deployments (for live status & idempotent redeployment)
  const { data: userDeployments = [], refetch: refetchDeployments } = useQuery({
    queryKey: ["user-deployments", token],
    queryFn: async () => {
      if (!token) return [];
      try {
        const res = await api.get("/deployments");
        return Array.isArray(res) ? res : res?.items || [];
      } catch {
        return [];
      }
    },
    enabled: !!token,
  });

  // Deploy Modal State
  const [deployModalOpen, setDeployModalOpen] = useState(false);
  const [selectedDeployItem, setSelectedDeployItem] = useState(null);
  const [deployProjectName, setDeployProjectName] = useState("");
  const [deployProvider, setDeployProvider] = useState("cloudflare");
  const [deployEnvVars, setDeployEnvVars] = useState({});
  const [isDeployEnvValid, setIsDeployEnvValid] = useState(true);
  const [isDeploying, setIsDeploying] = useState(false);
  const [deploySuccess, setDeploySuccess] = useState(null);
  const [deployError, setDeployError] = useState(null);

  const handleOpenDeployModal = (item) => {
    setSelectedDeployItem(item);
    setDeployProjectName(item.deployment?.project_name || (item.slug || "my-site").toLowerCase().replace(/[^a-z0-9-]/g, "-"));
    setDeployProvider(item.deployment?.provider || "cloudflare");
    setDeployEnvVars(item.deployment?.env_vars || {});
    setIsDeployEnvValid(true);
    setDeploySuccess(null);
    setDeployError(null);
    setDeployModalOpen(true);
  };

  const handleDeploySubmit = async (e) => {
    e.preventDefault();
    if (!selectedDeployItem) return;
    if (!isDeployEnvValid) {
      setDeployError("Please provide all required environment credentials before deploying.");
      return;
    }
    setIsDeploying(true);
    setDeployError(null);
    try {
      const payload = {
        template_id: selectedDeployItem.template_id,
        project_name: deployProjectName.trim(),
        provider: deployProvider,
        env_vars: deployEnvVars,
      };
      const res = await api.post("/deployments", payload);
      setDeploySuccess(res);
      await refetchDeployments();
    } catch (err) {
      setDeployError(err.message || "Failed to initiate deployment. Please try again.");
    } finally {
      setIsDeploying(false);
    }
  };

  // Review Modal State
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [selectedReviewItem, setSelectedReviewItem] = useState(null);
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewTitle, setReviewTitle] = useState("");
  const [reviewBody, setReviewBody] = useState("");
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState(false);
  const [reviewError, setReviewError] = useState(null);

  const handleOpenReviewModal = (item) => {
    setSelectedReviewItem(item);
    setReviewRating(5);
    setReviewTitle("");
    setReviewBody("");
    setReviewSuccess(false);
    setReviewError(null);
    setReviewModalOpen(true);
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    if (!selectedReviewItem) return;
    setIsSubmittingReview(true);
    setReviewError(null);
    try {
      const payload = {
        template_id: selectedReviewItem.template_id,
        rating: reviewRating,
        title: reviewTitle.trim() || undefined,
        body: reviewBody.trim() || undefined,
      };
      await api.post("/reviews", payload);
      setReviewSuccess(true);
    } catch (err) {
      setReviewError(err.message || "Failed to submit review. You may have already reviewed this template.");
    } finally {
      setIsSubmittingReview(false);
    }
  };

  // Clean Source ZIP Download
  const [downloadingId, setDownloadingId] = useState(null);
  const handleDownloadSource = async (item) => {
    const tId = item.template_id || item.template?.id;
    if (!tId) return;
    setDownloadingId(tId);
    try {
      const res = await api.post(`/templates/${tId}/download?format=zip&license=commercial`, {});
      if (res?.download_url) {
        const link = document.createElement("a");
        link.href = res.download_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.download = "";
        document.body.appendChild(link);
        link.click();
        link.remove();
      } else {
        alert("The clean source package is preparing, please try again in a few seconds.");
      }
    } catch (err) {
      alert(err.message || "Failed to download clean source code.");
    } finally {
      setDownloadingId(null);
    }
  };

  // Pre-fetch/cache full catalog in background to enable instantaneous client search (< 1ms)
  const fullCatalogFilters = useMemo(() => ({ page_size: 100 }), []);
  const { data: fullCatalogData } = useTemplates(fullCatalogFilters, token);

  const masterCatalog = useMemo(() => {
    return fullCatalogData?.items?.length ? fullCatalogData.items : (data?.items ?? []);
  }, [fullCatalogData?.items, data?.items]);

  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  const searchWrapperRef = useRef(null);

  // Close suggestions dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (searchWrapperRef.current && !searchWrapperRef.current.contains(event.target)) {
        setIsSearchFocused(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Instant Amazon-style suggestions matching searchInput (< 1ms)
  const matchingSuggestions = useMemo(() => {
    const raw = (searchInput || "").trim().toLowerCase();
    if (!raw) return [];
    const terms = raw.split(/\s+/).filter(Boolean);
    return masterCatalog
      .filter((t) => {
        const title = (t.title || "").toLowerCase();
        const desc = (t.short_description || "").toLowerCase();
        const tags = (t.tags || []).map((x) => String(x).toLowerCase());
        const dev = (t.developer_name || "").toLowerCase();
        const fw = (t.framework || "").toLowerCase();
        const ind = (t.industry || "").toLowerCase();
        return terms.every(
          (term) =>
            title.includes(term) ||
            desc.includes(term) ||
            tags.some((tag) => tag.includes(term)) ||
            dev.includes(term) ||
            fw.includes(term) ||
            ind.includes(term)
        );
      })
      .slice(0, 5);
  }, [searchInput, masterCatalog]);

  // Instant Displayed Templates: filters instantaneously on every keystroke without waiting
  const displayedTemplates = useMemo(() => {
    let list = [];
    if (filters.semantic) {
      list = data?.items ?? [];
    } else {
      const raw = (searchInput || "").trim().toLowerCase();
      if (raw && raw !== (filters.q || "").trim().toLowerCase()) {
        const terms = raw.split(/\s+/).filter(Boolean);
        list = masterCatalog.filter((item) => {
          const title = (item.title || "").toLowerCase();
          const desc = (item.short_description || "").toLowerCase();
          const tags = (item.tags || []).map((t) => String(t).toLowerCase());
          const dev = (item.developer_name || "").toLowerCase();
          const fw = (item.framework || "").toLowerCase();
          const ind = (item.industry || "").toLowerCase();
          return terms.every(
            (term) =>
              title.includes(term) ||
              desc.includes(term) ||
              tags.some((tag) => tag.includes(term)) ||
              dev.includes(term) ||
              fw.includes(term) ||
              ind.includes(term)
          );
        });
      } else {
        list = data?.items ?? [];
      }
    }
    return list;
  }, [data?.items, masterCatalog, searchInput, filters.q, filters.semantic]);

  // Memoized purchased templates list enriched with catalog metadata & active deployments
  const purchasedTemplatesList = useMemo(() => {
    if (!Array.isArray(userOrders)) return [];
    const list = [];
    const seenIds = new Set();
    userOrders.forEach((order) => {
      const status = (order.payment_status || order.status || "").toLowerCase();
      if (status === "completed" || status === "paid" || status === "succeeded") {
        (order.items || []).forEach((item) => {
          const tId = item.template_id || item.template?.id;
          if (tId && !seenIds.has(tId)) {
            seenIds.add(tId);
            const dep = (userDeployments || []).find((d) => d.template_id === tId);
            const catItem = (masterCatalog || []).find((t) => String(t.id) === String(tId));
            list.push({
              ...item,
              template_id: tId,
              title: item.template_title || item.template?.title || catItem?.title || "Purchased Template",
              slug: item.template?.slug || catItem?.slug || "",
              framework: item.template?.framework || catItem?.framework || item.framework || "html",
              thumbnail_url: item.template?.thumbnail_url || catItem?.thumbnail_url || item.thumbnail_url || "",
              short_description: item.template?.short_description || catItem?.short_description || "",
              category_id: catItem?.category_id || catItem?.category?.id || item.template?.category_id || item.category_id,
              category_slug: catItem?.category?.slug || catItem?.category_slug || "",
              tags: catItem?.tags || item.template?.tags || [],
              orderId: order.id,
              orderNo: order.order_number,
              orderDate: order.created_at,
              price: item.price || order.total_amount,
              uniquePurchaseNo: item.unique_purchase_no || `PUR-${String(item.id || tId).slice(0, 8).toUpperCase()}`,
              deployment: dep || null,
            });
          }
        });
      }
    });
    return list;
  }, [userOrders, userDeployments, masterCatalog]);

  // Displayed purchased templates: filtered by search input, category, framework, and sort options
  const displayedPurchasedTemplates = useMemo(() => {
    let list = purchasedTemplatesList;

    // Search filter
    const rawSearch = (searchInput || "").trim().toLowerCase();
    if (rawSearch) {
      list = list.filter((item) => {
        const title = (item.title || "").toLowerCase();
        const desc = (item.short_description || "").toLowerCase();
        const purchaseNo = (item.uniquePurchaseNo || "").toLowerCase();
        const orderNo = (item.orderNo || "").toLowerCase();
        const fw = (item.framework || "").toLowerCase();
        const tags = Array.isArray(item.tags) ? item.tags.join(" ").toLowerCase() : "";
        return (
          title.includes(rawSearch) ||
          desc.includes(rawSearch) ||
          purchaseNo.includes(rawSearch) ||
          orderNo.includes(rawSearch) ||
          fw.includes(rawSearch) ||
          tags.includes(rawSearch)
        );
      });
    }

    // Category filter (from sidebar or quick category pills)
    if (filters.category) {
      const activeCat = String(filters.category).toLowerCase().trim();
      list = list.filter((item) => {
        const itemCatId = String(item.category_id || "").toLowerCase();
        const itemCatSlug = String(item.category_slug || "").toLowerCase();
        const itemTags = (item.tags || []).map((t) => String(t).toLowerCase());
        const itemTitle = (item.title || "").toLowerCase();
        return (
          itemCatId === activeCat ||
          itemCatSlug === activeCat ||
          itemTags.includes(activeCat) ||
          itemTitle.includes(activeCat) ||
          (categories || []).some(
            (c) =>
              (String(c.id).toLowerCase() === activeCat || String(c.slug).toLowerCase() === activeCat) &&
              (String(c.id).toLowerCase() === itemCatId || String(c.slug).toLowerCase() === itemCatSlug)
          )
        );
      });
    }

    // Framework filter
    if (filters.framework) {
      const activeFw = String(filters.framework).toLowerCase().trim();
      list = list.filter((item) => String(item.framework || "").toLowerCase() === activeFw);
    }

    // Sort
    if (filters.sort === "newest") {
      list = [...list].sort((a, b) => new Date(b.orderDate || 0) - new Date(a.orderDate || 0));
    } else if (filters.sort === "price_asc") {
      list = [...list].sort((a, b) => Number(a.price || 0) - Number(b.price || 0));
    } else if (filters.sort === "price_desc") {
      list = [...list].sort((a, b) => Number(b.price || 0) - Number(a.price || 0));
    }

    return list;
  }, [purchasedTemplatesList, searchInput, filters.category, filters.framework, filters.sort, categories]);

  // Fast 150ms memoized debounce to sync filters store and URL without stutter
  const debouncedSearch = useMemo(
    () =>
      debounce((value) => {
        setFilter("q", value || undefined);
        setFilter("semantic", undefined);
      }, 150),
    [setFilter]
  );

  const handleSearchChange = (value) => {
    setSearchInput(value);
    setIsSearchFocused(true);
    setSelectedSuggestionIndex(-1);
    debouncedSearch(value);
  };

  const applySearchQuery = (val) => {
    debouncedSearch.cancel();
    setSearchInput(val);
    setFilter("q", val || undefined);
    setFilter("semantic", undefined);
    setIsSearchFocused(false);
    setSelectedSuggestionIndex(-1);
  };

  const handleClearSearch = () => {
    debouncedSearch.cancel();
    setSearchInput("");
    setFilter("q", undefined);
    setFilter("semantic", undefined);
    setIsSearchFocused(false);
    setSelectedSuggestionIndex(-1);
  };

  const triggerAISearch = () => {
    debouncedSearch.cancel();
    setIsSearchFocused(false);
    if (searchInput) {
      setFilter("q", searchInput);
      setFilter("semantic", true);
    }
  };

  // Keyboard navigation for Amazon-style autocomplete dropdown
  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      setIsSearchFocused(false);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setIsSearchFocused(true);
      const maxIndex = matchingSuggestions.length;
      setSelectedSuggestionIndex((prev) => Math.min(prev + 1, maxIndex));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedSuggestionIndex((prev) => Math.max(prev - 1, -1));
      return;
    }
    if (e.key === "Enter") {
      if (selectedSuggestionIndex === 0 && searchInput.trim()) {
        applySearchQuery(searchInput);
      } else if (selectedSuggestionIndex > 0 && matchingSuggestions[selectedSuggestionIndex - 1]) {
        const item = matchingSuggestions[selectedSuggestionIndex - 1];
        navigate(`/preview?template=${item.id}`);
      } else {
        applySearchQuery(searchInput);
      }
    }
  };

  const isLocallyFiltering = !filters.semantic && searchInput.trim() && searchInput.trim() !== (filters.q || "").trim();
  const total = activeViewMode === "purchased"
    ? displayedPurchasedTemplates.length
    : (isLocallyFiltering ? displayedTemplates.length : (data?.total ?? 0));
  const totalPages = data?.total_pages ?? 1;

  return (
    <>
      <Navbar />
      <div className="marketplace-page marketplace-redesign">
        <div className="marketplace-container">
          <header className="marketplace-hero-header">
            <div className="marketplace-hero-badge">
              <Sparkles className="w-3.5 h-3.5 text-[#dfb180]" />
              <span>Curated Template Marketplace</span>
              <span className="marketplace-badge-dot" />
              <span className="text-emerald-400 font-semibold">100% Production Ready</span>
            </div>
            <div className="marketplace-hero-row">
              <div className="marketplace-hero-text">
                <h1 className="marketplace-hero-title">
                  Production-Ready <span className="marketplace-title-gradient">Website Templates</span>
                </h1>
                <p className="marketplace-hero-sub">
                  Modern, multi-page templates with instant live previews, responsive reflow, and Smart Fill personalization.
                </p>
              </div>
              {isExtreme ? (
                <Link
                  to="/dashboard?tab=creator-studio"
                  className="marketplace-studio-cta"
                  title="Open Extreme Creator Studio to retail your AI-generated websites"
                >
                  <Sparkles className="w-4 h-4 text-[#dfb180]" />
                  <span>Extreme Creator Studio</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              ) : (
                <Link
                  to="/studio"
                  className="marketplace-create-callout"
                  aria-label="Want to create your own website? Click to open Studio Creator"
                >
                  <span className="marketplace-create-icon"><MessageCircle className="w-5 h-5" /></span>
                  <span className="marketplace-create-copy">
                    <strong>Want to create your own?</strong>
                    <span>Click here to open Studio Creator <ArrowRight className="w-3.5 h-3.5" /></span>
                  </span>
                </Link>
              )}
            </div>
          </header>
          <div className="marketplace-layout">

            {/* ── Sidebar ── Always visible with all filters ── */}
            <div className="marketplace-sidebar">
              <div className="sticky-sidebar">
                <SidebarFilters categories={categories} />
              </div>
            </div>

            {/* ── Main content ────────────────────────────────────── */}
            <div className="marketplace-main">

              {/* ── Toolbar ──────────────────────────────────────── */}
              <div className={cn("marketplace-toolbar", isSearchFocused && "search-focused")}>

                {/* Row 1 — Search bar + Amazon-Style Autocomplete Dropdown + Semantic toggle */}
                <div className="toolbar-row">
                  <div
                    ref={searchWrapperRef}
                    className={cn(
                      "marketplace-search-wrapper",
                      filters.semantic && "ai-active",
                      isSearchFocused && "dropdown-open"
                    )}
                  >
                    <div className="marketplace-search">
                      <Search className="marketplace-search-icon" />
                      <input
                        type="text"
                        placeholder={
                          filters.semantic
                            ? "Describe your dream website (e.g., 'sleek dark dashboard for SaaS')..."
                            : "Search templates ..........."
                        }
                        value={searchInput}
                        onFocus={() => setIsSearchFocused(true)}
                        onChange={(e) => handleSearchChange(e.target.value)}
                        onKeyDown={handleKeyDown}
                        className="marketplace-search-input"
                        autoComplete="off"
                        spellCheck="false"
                      />
                      {searchInput && (
                        <button
                          type="button"
                          onClick={handleClearSearch}
                          className="search-clear-btn"
                          aria-label="Clear search"
                        >
                          <X className="search-clear-icon" />
                        </button>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={triggerAISearch}
                      className={cn("ai-toggle-btn", filters.semantic && "active")}
                      title="Run Semantic Search on this query"
                    >
                      <Sparkles className={cn("ai-toggle-icon", filters.semantic && "glow-animation")} />
                      <span>Semantic Search</span>
                    </button>

                    {/* ── Amazon-Style Instant Search & Autocomplete Dropdown ── */}
                    {isSearchFocused && (
                      <div className="amazon-search-dropdown">
                        {/* State A: Input is empty -> Trending Searches & Popular Categories */}
                        {!searchInput.trim() ? (
                          <>
                            <div className="amazon-dropdown-section">
                              <div className="amazon-dropdown-section-title">
                                <TrendingUp className="w-3.5 h-3.5 text-[#dfb180]" />
                                <span>Trending Searches</span>
                              </div>
                              <div className="amazon-trending-pills">
                                {TRENDING_SEARCHES.map((query) => (
                                  <button
                                    key={query}
                                    type="button"
                                    onClick={() => applySearchQuery(query)}
                                    className="amazon-trending-pill"
                                  >
                                    <Search className="pill-icon" />
                                    <span>{query}</span>
                                  </button>
                                ))}
                              </div>
                            </div>

                            <div className="amazon-dropdown-section">
                              <div className="amazon-dropdown-section-title">
                                <Layers className="w-3.5 h-3.5 text-primary" />
                                <span>Popular Categories</span>
                              </div>
                              <div className="amazon-category-grid">
                                {QUICK_CATEGORIES.slice(1, 7).map((cat) => (
                                  <div
                                    key={cat.value}
                                    className="amazon-category-item"
                                    onClick={() => {
                                      setFilter("category", cat.value);
                                      setFilter("sub_category", undefined);
                                      setIsSearchFocused(false);
                                    }}
                                  >
                                    <span>{cat.label}</span>
                                    <ArrowRight className="w-3 h-3 text-muted-foreground" />
                                  </div>
                                ))}
                              </div>
                            </div>
                          </>
                        ) : (
                          /* State B: User is typing -> Instant Template Matches & Query Scope */
                          <>
                            <div
                              className={cn(
                                "amazon-quick-search-row",
                                selectedSuggestionIndex === 0 && "is-selected"
                              )}
                              onClick={() => applySearchQuery(searchInput)}
                            >
                              <div className="amazon-quick-search-left">
                                <Search className="w-4 h-4 text-muted-foreground" />
                                <span>
                                  Search for <strong>&ldquo;{searchInput}&rdquo;</strong> in all templates
                                </span>
                              </div>
                              <span className="amazon-key-hint">
                                <CornerDownLeft className="w-3 h-3" /> Enter
                              </span>
                            </div>

                            {matchingSuggestions.length > 0 ? (
                              <div className="amazon-dropdown-section">
                                <div className="amazon-dropdown-section-title">
                                  <Zap className="w-3.5 h-3.5" style={{ color: "#eab308" }} />
                                  <span>Instant Template Matches ({matchingSuggestions.length})</span>
                                </div>
                                <div className="amazon-matches-list">
                                  {matchingSuggestions.map((item, idx) => {
                                    const isSelected = selectedSuggestionIndex === idx + 1;
                                    const effectivePrice = Number(item.price) > 0 ? Number(item.price) : 49;
                                    const priceText = `$${effectivePrice}`;
                                    return (
                                      <div
                                        key={item.id}
                                        className={cn("amazon-match-item", isSelected && "is-selected")}
                                        onClick={() => navigate(`/preview?template=${item.id}`)}
                                      >
                                        <img
                                          src={item.thumbnail_url || "/placeholder-card.png"}
                                          alt={item.title}
                                          className="amazon-match-thumb"
                                          onError={(e) => {
                                            e.target.style.display = "none";
                                          }}
                                        />
                                        <div className="amazon-match-details">
                                          <div className="amazon-match-title-row">
                                            <span className="amazon-match-title">
                                              {highlightSearchMatch(item.title, searchInput)}
                                            </span>
                                            {item.framework && (
                                              <span className="amazon-match-badge">
                                                {item.framework}
                                              </span>
                                            )}
                                          </div>
                                          <span className="amazon-match-subtitle">
                                            {item.short_description || item.industry || "Website Template"}
                                          </span>
                                        </div>
                                        <div className="amazon-match-right">
                                          <span className="amazon-match-price">
                                            {priceText}
                                          </span>
                                          <button
                                            type="button"
                                            className="amazon-match-view-btn"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              navigate(`/preview?template=${item.id}`);
                                            }}
                                          >
                                            <Eye className="w-3 h-3" />
                                            <span>Preview</span>
                                          </button>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            ) : (
                              <div className="amazon-dropdown-section" style={{ padding: "1rem", textAlign: "center" }}>
                                <p style={{ margin: 0, fontSize: "0.82rem", color: "hsl(var(--muted-foreground))" }}>
                                  No instant card matches for <strong>&ldquo;{searchInput}&rdquo;</strong>. Press Enter to search catalog.
                                </p>
                              </div>
                            )}

                            <div className="amazon-dropdown-footer">
                              <span>Instant search-as-you-type (<strong style={{ color: "#16a34a" }}>&lt; 1ms</strong>)</span>
                              <span>Use ↑↓ arrows • Enter to select • Esc to close</span>
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                {/* Row 2 — Mobile & Tablet Action Row */}
                <div className="marketplace-mobile-actions-bar">
                  <button
                    type="button"
                    onClick={() => setMobileFilterOpen(true)}
                    className={cn("marketplace-mobile-filter-btn", activeFilterCount > 0 && "has-filters")}
                    aria-label="Open filter drawer"
                  >
                    <SlidersHorizontal className="w-3.5 h-3.5" />
                    <span>Filters</span>
                    {activeFilterCount > 0 && (
                      <span className="mobile-filter-count-badge">{activeFilterCount}</span>
                    )}
                  </button>
                </div>

                {/* Row 3 — Sort tabs and view toggle */}
                <div className="toolbar-row toolbar-row-controls">
                  <div className="marketplace-view-switch">
                    <button
                      type="button"
                      onClick={() => {
                        setActiveViewMode("all");
                        const u = new URL(window.location.href);
                        u.searchParams.delete("view");
                        window.history.replaceState(null, '', u.toString());
                      }}
                      className={cn("marketplace-switch-tab", activeViewMode === "all" && "active")}
                    >
                      <Layers className="w-3.5 h-3.5" />
                      <span>All Templates</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (!isSignedIn) {
                          navigate("/login?redirect=/marketplace?view=purchased");
                          return;
                        }
                        setActiveViewMode("purchased");
                        const u = new URL(window.location.href);
                        u.searchParams.set("view", "purchased");
                        window.history.replaceState(null, '', u.toString());
                      }}
                      className={cn("marketplace-switch-tab", activeViewMode === "purchased" && "active")}
                    >
                      <ShoppingBag className="w-3.5 h-3.5" />
                      <span>Purchased Templates</span>
                      {purchasedTemplatesList.length > 0 && (
                        <span className="purchased-pill-badge">{purchasedTemplatesList.length}</span>
                      )}
                    </button>
                  </div>

                  <div className="marketplace-sort-bar">
                    {SORT_OPTIONS.slice(0, 4).map((o) => (
                      <button
                        key={o.value}
                        onClick={() => setFilter("sort", o.value)}
                        className={cn("sort-btn", (filters.sort || "newest") === o.value && "active")}
                      >
                        {o.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* ── Quick Categories Horizontal Scroll Pill Bar (Available for both All & Purchased) ── */}
              <div className="marketplace-quick-categories">
                {QUICK_CATEGORIES.map((cat) => {
                  const isSelected = (!filters.category && !cat.value) || filters.category === cat.value;
                  return (
                    <button
                      key={cat.value || "all"}
                      type="button"
                      onClick={() => {
                        setFilter("category", cat.value || undefined);
                        setFilter("sub_category", undefined);
                      }}
                      className={cn("quick-category-pill", isSelected && "active")}
                    >
                      {cat.label}
                    </button>
                  );
                })}
              </div>

              {/* ── Result count (Available for both All & Purchased) ── */}
              <div className="result-count-bar flex justify-between items-center flex-wrap gap-2" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                <p className="result-count-text">
                  {activeViewMode === "purchased"
                    ? `${displayedPurchasedTemplates.length} purchased template${displayedPurchasedTemplates.length === 1 ? "" : "s"} found`
                    : (isLoading && displayedTemplates.length === 0 ? "Loading…" : `${total.toLocaleString()} templates found`)}
                </p>
                {filters.developer && (
                  <div className="flex items-center gap-1.5 bg-primary/20 text-primary border border-primary/30 px-3 py-1 rounded-full text-xs font-semibold" style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                    <span>Developer: {filters.developer}</span>
                    <button
                      type="button"
                      onClick={() => setFilter("developer", undefined)}
                      className="hover:text-white transition-colors ml-1 focus:outline-none bg-transparent border-none p-0 cursor-pointer text-primary flex items-center"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>

              {activeViewMode === "all" ? (
                <>
                  {/* ── Template grid ─────────────────────────────────── */}
                  <TemplateGrid
                    templates={displayedTemplates}
                    isLoading={isLoading && displayedTemplates.length === 0}
                    view="grid"
                    onFavorite={(id) => token && favoriteMutation.mutate(id)}
                    onWishlist={(id) => token && wishlistMutation.mutate(id)}
                  />

                  {/* ── Pagination ────────────────────────────────────── */}
                  {!isLoading && totalPages > 1 && (
                    <div className="pagination-container">
                      <button
                        onClick={() => setFilter("page", Math.max(1, (filters.page ?? 1) - 1))}
                        disabled={(filters.page ?? 1) <= 1}
                        className="page-nav-btn"
                      >
                        Previous
                      </button>

                      <div className="pagination-desktop-numbers">
                        {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                          const page = i + 1;
                          return (
                            <button
                              key={page}
                              onClick={() => setFilter("page", page)}
                              className={cn("page-num-btn", (filters.page ?? 1) === page && "active")}
                            >
                              {page}
                            </button>
                          );
                        })}
                      </div>

                      <span className="pagination-mobile-indicator">
                        Page {filters.page ?? 1} of {totalPages}
                      </span>

                      <button
                        onClick={() => setFilter("page", Math.min(totalPages, (filters.page ?? 1) + 1))}
                        disabled={(filters.page ?? 1) >= totalPages}
                        className="page-nav-btn"
                      >
                        Next
                      </button>
                    </div>
                  )}
                </>
              ) : (
                /* ── Purchased Templates — same grid layout as All Templates ── */
                <>
                  {/* Slim info banner (no separate page, stays inside main content column) */}
                  <div className="purchased-header-banner">
                    <div className="purchased-header-text">
                      <h2 className="purchased-title">
                        <ShoppingBag className="w-5 h-5 text-[#dfb180]" />
                        <span>Your Purchased Templates</span>
                        <span className="purchased-count-pill">{purchasedTemplatesList.length}</span>
                      </h2>
                      <p className="purchased-subtitle">
                        Access full source code, deploy or redeploy to live domains, rate &amp; review, and edit inside the Studio Preview Editor. Every purchase has a permanent tracking ID for stable idempotent redeployments.
                      </p>
                    </div>
                  </div>

                  {ordersLoading ? (
                    <div className="p-12 text-center text-muted-foreground flex items-center justify-center gap-2">
                      <Loader2 className="w-5 h-5 animate-spin text-primary" />
                      <span>Loading your purchased templates…</span>
                    </div>
                  ) : displayedPurchasedTemplates.length === 0 ? (
                    <div className="purchased-empty-state">
                      <div className="purchased-empty-icon">
                        <ShoppingBag className="w-8 h-8 text-muted-foreground" />
                      </div>
                      <h3 className="purchased-empty-title">
                        {purchasedTemplatesList.length === 0
                          ? "No Purchased Templates Yet"
                          : "No Purchased Templates Match Your Filters"}
                      </h3>
                      <p className="purchased-empty-desc">
                        {purchasedTemplatesList.length === 0
                          ? "Templates you purchase will appear here in this dedicated hub with 1-click cloud deployment, full studio customization, unwatermarked clean source code download, and verified customer reviews."
                          : "Try clearing your search query or category filters to view all your purchased templates."}
                      </p>
                      {purchasedTemplatesList.length === 0 ? (
                        <button
                          type="button"
                          onClick={() => {
                            setActiveViewMode("all");
                            const u = new URL(window.location.href);
                            u.searchParams.delete("view");
                            window.history.replaceState(null, '', u.toString());
                          }}
                          className="purchased-empty-action"
                        >
                          Browse Marketplace Templates
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setSearchInput("");
                            setFilter("category", undefined);
                            setFilter("sub_category", undefined);
                          }}
                          className="purchased-empty-action"
                        >
                          Clear Filters
                        </button>
                      )}
                    </div>
                  ) : (
                    /* Use the same marketplace-grid class so columns match All Templates exactly */
                    <div className="marketplace-grid">
                      {displayedPurchasedTemplates.map((item) => (
                        <div key={item.id || item.uniquePurchaseNo} className="purchased-card purchased-card--grid-mode">
                          <div className="purchased-card-media">
                            {item.thumbnail_url ? (
                              <img
                                src={item.thumbnail_url}
                                alt={item.title}
                                className="purchased-card-img"
                              />
                            ) : (
                              <div className="purchased-card-img-placeholder">
                                <Layers className="w-8 h-8 text-muted-foreground" />
                              </div>
                            )}
                            <div className="purchased-media-badges">
                              <span className="purchased-badge framework">{item.framework?.toUpperCase() || "HTML"}</span>
                              <span className="purchased-badge license">
                                <ShieldCheck className="w-3 h-3" />
                                <span>Commercial</span>
                              </span>
                            </div>
                            <div className="purchased-tracking-pill" title="Unique Purchase Tracking Number">
                              <Tag className="w-3 h-3 text-[#dfb180]" />
                              <span>{item.uniquePurchaseNo}</span>
                            </div>
                          </div>

                          <div className="purchased-card-body">
                            <div className="purchased-card-title-row">
                              <h3 className="purchased-card-title" title={item.title}>
                                {item.title}
                              </h3>
                            </div>

                            <div className="purchased-meta-row">
                              <span className="purchased-meta-item">
                                Order #{String(item.orderNo || item.orderId || "").slice(0, 8)}
                              </span>
                              <span className="purchased-meta-dot">•</span>
                              <span className="purchased-meta-item">
                                {item.orderDate ? new Date(item.orderDate).toLocaleDateString() : "Active License"}
                              </span>
                            </div>

                            <div className="purchased-deploy-status">
                              {item.deployment ? (
                                <div className="purchased-status-pill live">
                                  <span className="purchased-live-dot" />
                                  <div className="purchased-status-info">
                                    <span className="purchased-status-label">
                                      Live on {item.deployment.provider || "Cloud"} ({item.deployment.current_version || item.deployment.version || "v1.0"})
                                    </span>
                                    {(item.deployment.live_url || item.deployment.site_url) && (
                                      <a
                                        href={item.deployment.live_url || item.deployment.site_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="purchased-site-link"
                                        title={item.deployment.live_url || item.deployment.site_url}
                                      >
                                        <span>{(item.deployment.live_url || item.deployment.site_url).replace(/^https?:\/\//, '')}</span>
                                        <ExternalLink className="w-3 h-3 inline ml-1 shrink-0" />
                                      </a>
                                    )}
                                  </div>
                                </div>
                              ) : (
                                <div className="purchased-status-pill idle">
                                  <span className="purchased-idle-dot" />
                                  <span>Ready to Deploy • Local / Vercel / Cloudflare</span>
                                </div>
                              )}
                            </div>

                            <div className="purchased-card-actions">
                              {/* 1. Deploy / Redeploy */}
                              <button
                                type="button"
                                onClick={() => handleOpenDeployModal(item)}
                                className="purchased-action-btn deploy"
                                title={item.deployment ? "Redeploy with new details to the same URL" : "Deploy live"}
                              >
                                <Globe className="w-3.5 h-3.5" />
                                <span>{item.deployment ? "Redeploy" : "Deploy"}</span>
                              </button>

                              {/* 2. Edit in Preview Editor */}
                              <Link
                                href={`/preview?template=${item.template_id || item.template?.id}`}
                                className="purchased-action-btn edit"
                                title="Open full studio preview editor"
                                style={{ textDecoration: 'none' }}
                              >
                                <Play className="w-3.5 h-3.5" />
                                <span>Edit</span>
                              </Link>

                              {/* 3. Review */}
                              <button
                                type="button"
                                onClick={() => handleOpenReviewModal(item)}
                                className="purchased-action-btn review"
                                title="Rate and review this template"
                              >
                                <Star className="w-3.5 h-3.5" />
                                <span>Review</span>
                              </button>

                              {/* 4. Download Source */}
                              <button
                                type="button"
                                onClick={() => handleDownloadSource(item)}
                                disabled={downloadingId === (item.template_id || item.template?.id)}
                                className="purchased-action-btn source"
                                title="Download clean unwatermarked ZIP source code"
                              >
                                {downloadingId === (item.template_id || item.template?.id) ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                  <Download className="w-3.5 h-3.5" />
                                )}
                                <span>Source</span>
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Mobile Filter Slide-Over Drawer ── */}
      <AnimatePresence>
        {mobileFilterOpen && (
          <div className="mobile-filter-backdrop" onClick={() => setMobileFilterOpen(false)}>
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 250 }}
              className="mobile-filter-drawer"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="mobile-filter-header">
                <div className="flex items-center gap-2" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <SlidersHorizontal className="w-4 h-4 text-primary" />
                  <h3 className="font-bold text-sm text-foreground m-0" style={{ margin: 0, fontSize: "0.9375rem" }}>Filters & Categories</h3>
                  {activeFilterCount > 0 && (
                    <span className="mobile-filter-count-badge">{activeFilterCount}</span>
                  )}
                </div>
                <div className="flex items-center gap-2" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  {activeFilterCount > 0 && (
                    <button
                      type="button"
                      onClick={() => resetFilters()}
                      className="text-xs font-semibold text-muted-foreground hover:text-red-500 transition-colors cursor-pointer bg-transparent border-none"
                    >
                      Reset All
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setMobileFilterOpen(false)}
                    className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 cursor-pointer border-none bg-transparent"
                    aria-label="Close filters"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              <div className="mobile-filter-body">
                <SidebarFilters categories={categories} />
              </div>

              <div className="mobile-filter-footer">
                <button
                  type="button"
                  onClick={() => setMobileFilterOpen(false)}
                  className="mobile-filter-apply-btn"
                >
                  Show {total.toLocaleString()} Templates
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
      {/* ── Deploy / Redeploy Modal ── */}
      {deployModalOpen && selectedDeployItem && (
        <div className="purchased-modal-backdrop" onClick={() => !isDeploying && setDeployModalOpen(false)}>
          <div className="purchased-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="purchased-modal-header">
              <div className="flex items-center gap-2">
                <Globe className="w-5 h-5 text-[#dfb180]" />
                <h3 className="purchased-modal-title">
                  {selectedDeployItem.deployment ? "Redeploy & Update Live Website" : "Deploy Purchased Template"}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => !isDeploying && setDeployModalOpen(false)}
                className="purchased-modal-close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {deploySuccess ? (
              <div className="p-4 space-y-4">
                <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-200 text-xs">
                  <div className="font-bold flex items-center gap-2 text-emerald-300 text-sm mb-1">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Deployment Successfully Dispatched!</span>
                  </div>
                  <p className="text-[11px] text-emerald-100/80 mb-2">
                    Your site is building and will update at your permanent canonical site URL.
                  </p>
                  {(deploySuccess.live_url || deploySuccess.site_url) && (
                    <div className="p-2 rounded bg-black/40 border border-emerald-500/20 font-mono text-xs text-emerald-300 break-all">
                      <a href={deploySuccess.live_url || deploySuccess.site_url} target="_blank" rel="noopener noreferrer" className="hover:underline flex items-center gap-1">
                        <span>{deploySuccess.live_url || deploySuccess.site_url}</span>
                        <ExternalLink className="w-3 h-3 shrink-0" />
                      </a>
                    </div>
                  )}
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setDeployModalOpen(false);
                      setDeploySuccess(null);
                    }}
                    className="px-4 py-2 rounded-xl bg-[#c89666] text-black font-semibold text-xs cursor-pointer"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleDeploySubmit} className="p-4 space-y-4 text-xs">
                {deployError && (
                  <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-[11px] flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{deployError}</span>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="font-semibold text-muted-foreground">Template</label>
                  <div className="p-2.5 rounded-lg bg-muted/40 border border-border/60 flex items-center justify-between">
                    <span className="font-bold text-foreground">{selectedDeployItem.title}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-black/40 font-mono text-[#dfb180]">
                      {selectedDeployItem.uniquePurchaseNo}
                    </span>
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-muted-foreground">Project Name</label>
                  <input
                    type="text"
                    required
                    value={deployProjectName}
                    onChange={(e) => setDeployProjectName(e.target.value)}
                    placeholder="my-portfolio-site"
                    className="w-full px-3 py-2 rounded-lg bg-background border border-border/80 focus:border-primary focus:outline-none text-foreground font-mono text-xs"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    All redeployments use your permanent purchase ID ({selectedDeployItem.uniquePurchaseNo}) to update this instance idempotently.
                  </p>
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-muted-foreground">Cloud Provider</label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { id: "local", label: "Managed VPS" },
                      { id: "vercel", label: "Vercel" },
                      { id: "cloudflare", label: "Cloudflare" },
                    ].map((prov) => (
                      <button
                        key={prov.id}
                        type="button"
                        onClick={() => setDeployProvider(prov.id)}
                        className={cn(
                          "py-2 px-3 rounded-lg border font-medium text-center transition-all cursor-pointer text-xs",
                          deployProvider === prov.id
                            ? "bg-primary/20 border-primary text-primary font-bold"
                            : "bg-muted/20 border-border/50 text-muted-foreground hover:border-border"
                        )}
                      >
                        {prov.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Phase 4: Pre-Deployment Secrets & Environment Variables Manager */}
                <SecretsEnvManager
                  templateId={selectedDeployItem.template_id}
                  stackKey={selectedDeployItem.framework}
                  initialEnv={deployEnvVars}
                  onChange={(updatedEnv, isValid) => {
                    setDeployEnvVars(updatedEnv);
                    setIsDeployEnvValid(isValid);
                  }}
                />

                <div className="flex justify-end gap-2 pt-2 border-t border-border/60">
                  <button
                    type="button"
                    onClick={() => setDeployModalOpen(false)}
                    disabled={isDeploying}
                    className="px-4 py-2 rounded-xl bg-muted text-muted-foreground hover:bg-muted/80 text-xs font-semibold cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isDeploying}
                    className="px-4 py-2 rounded-xl bg-[#c89666] text-black hover:bg-[#dfb180] text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer"
                  >
                    {isDeploying ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Deploying...</span>
                      </>
                    ) : (
                      <>
                        <Globe className="w-3.5 h-3.5" />
                        <span>{selectedDeployItem.deployment ? "Update Deployment" : "Deploy Live"}</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ── Review Rating Modal ── */}
      {reviewModalOpen && selectedReviewItem && (
        <div className="purchased-modal-backdrop" onClick={() => !isSubmittingReview && setReviewModalOpen(false)}>
          <div className="purchased-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="purchased-modal-header">
              <div className="flex items-center gap-2">
                <Star className="w-5 h-5 text-amber-400 fill-amber-400" />
                <h3 className="purchased-modal-title">Rate & Review Template</h3>
              </div>
              <button
                type="button"
                onClick={() => !isSubmittingReview && setReviewModalOpen(false)}
                className="purchased-modal-close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {reviewSuccess ? (
              <div className="p-4 space-y-4 text-center">
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-200 text-xs space-y-2">
                  <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                  <div className="font-bold text-emerald-300 text-sm">Review Submitted!</div>
                  <p className="text-[11px] text-emerald-100/80">
                    Thank you! Your verified purchaser review has been recorded.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setReviewModalOpen(false);
                    setReviewSuccess(false);
                  }}
                  className="px-4 py-2 rounded-xl bg-[#c89666] text-black font-semibold text-xs cursor-pointer"
                >
                  Close
                </button>
              </div>
            ) : (
              <form onSubmit={handleReviewSubmit} className="p-4 space-y-4 text-xs">
                {reviewError && (
                  <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-[11px] flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{reviewError}</span>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="font-semibold text-muted-foreground">Template</label>
                  <div className="p-2.5 rounded-lg bg-muted/40 border border-border/60 font-bold text-foreground">
                    {selectedReviewItem.title}
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-muted-foreground">Rating</label>
                  <div className="flex items-center gap-1.5 py-1">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        key={star}
                        type="button"
                        onClick={() => setReviewRating(star)}
                        className="p-1 hover:scale-110 transition-transform cursor-pointer bg-transparent border-none"
                      >
                        <Star
                          className={cn(
                            "w-6 h-6",
                            star <= reviewRating
                              ? "text-amber-400 fill-amber-400"
                              : "text-muted-foreground/30"
                          )}
                        />
                      </button>
                    ))}
                    <span className="ml-2 font-bold text-sm text-foreground">{reviewRating} / 5</span>
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-muted-foreground">Review Title (Optional)</label>
                  <input
                    type="text"
                    value={reviewTitle}
                    onChange={(e) => setReviewTitle(e.target.value)}
                    placeholder="Great clean code, super easy to customize!"
                    className="w-full px-3 py-2 rounded-lg bg-background border border-border/80 focus:border-primary focus:outline-none text-foreground text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-muted-foreground">Feedback & Comments</label>
                  <textarea
                    rows={4}
                    required
                    value={reviewBody}
                    onChange={(e) => setReviewBody(e.target.value)}
                    placeholder="Share your experience with the design, responsive layout, responsiveness..."
                    className="w-full px-3 py-2 rounded-lg bg-background border border-border/80 focus:border-primary focus:outline-none text-foreground text-xs resize-none"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-border/60">
                  <button
                    type="button"
                    onClick={() => setReviewModalOpen(false)}
                    disabled={isSubmittingReview}
                    className="px-4 py-2 rounded-xl bg-muted text-muted-foreground hover:bg-muted/80 text-xs font-semibold cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmittingReview}
                    className="px-4 py-2 rounded-xl bg-[#c89666] text-black hover:bg-[#dfb180] text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer"
                  >
                    {isSubmittingReview ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Submitting...</span>
                      </>
                    ) : (
                      <span>Submit Review</span>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default Marketplace;
