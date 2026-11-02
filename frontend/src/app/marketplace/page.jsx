"use client";

/**
 * Marketplace Page — split layout: sidebar filters + template grid + toolbar (React JSX).
 */

export const dynamic = "force-dynamic";

import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { navigate } from "@/components/Link";
const useRouter = () => ({
  push: (to) => navigate(to),
  replace: (to) => navigate(to),
});
const useSearchParams = () => new URLSearchParams(window.location.search);
import { useAppAuth } from "@/lib/auth";
import {
  LayoutGrid, LayoutList, Search, X, Sparkles, SlidersHorizontal, Filter,
  TrendingUp, ArrowRight, CornerDownLeft, Eye, Zap, Layers,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import Navbar from "@/components/layout/Navbar";
import SidebarFilters from "@/components/marketplace/SidebarFilters";
import TemplateGrid from "@/components/marketplace/TemplateGrid";
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
      <strong key={i} style={{ color: "#f26445" }}>
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
  const [view, setView] = useState("grid");
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
  const [token, setToken] = useState(() => useAuthStore.getState().token);
  useEffect(() => {
    getToken().then(setToken);
  }, [getToken]);

  const { data, isLoading } = useTemplates(filters, token);
  const favoriteMutation = useToggleFavorite(token ?? "");
  const wishlistMutation = useToggleWishlist(token ?? "");

  // Pre-fetch/cache full catalog in background to enable instantaneous client search (< 1ms)
  const { data: fullCatalogData } = useTemplates({ page_size: 100 }, token);
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
    if (filters.semantic) {
      return data?.items ?? [];
    }
    const raw = (searchInput || "").trim().toLowerCase();
    if (raw && raw !== (filters.q || "").trim().toLowerCase()) {
      const terms = raw.split(/\s+/).filter(Boolean);
      return masterCatalog.filter((item) => {
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
    }
    return data?.items ?? [];
  }, [data?.items, masterCatalog, searchInput, filters.q, filters.semantic]);

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
  const total = isLocallyFiltering ? displayedTemplates.length : (data?.total ?? 0);
  const totalPages = data?.total_pages ?? 1;

  return (
    <>
      <Navbar />
      <div className="marketplace-page marketplace-redesign">
        <div className="marketplace-container">
          <section className="market-hero">
            <div className="market-hero-topline"><span><i /> THE WEBSITE TEMPLATE LIBRARY</span><span>DESIGNED TO GET YOU STARTED</span></div>
            <div className="market-hero-main">
              <div>
                <h1>Good ideas deserve<br /><em>a better starting point.</em></h1>
                <p>Thoughtful, ready-to-customize websites for the things you want to make next.</p>
              </div>
              <button type="button" onClick={() => navigate("/studio")} className="market-hero-studio"><Sparkles size={17} /><span>Studio Creator</span><b aria-hidden="true">↗</b></button>
            </div>
          </section>
          <div className="marketplace-layout">

            {/* ── Sidebar ─────────────────────────────────────────── */}
            <div className="marketplace-sidebar">
              <div className="sticky-sidebar">
                <SidebarFilters categories={categories} />
              </div>
            </div>

            {/* ── Main content ────────────────────────────────────── */}
            <div className="marketplace-main">

              {/* ── Toolbar ──────────────────────────────────────── */}
              <div className="marketplace-toolbar">

                {/* Row 1 — Search bar + Amazon-Style Autocomplete Dropdown + Semantic toggle */}
                <div className="toolbar-row">
                  <div
                    ref={searchWrapperRef}
                    className={cn("marketplace-search-wrapper", filters.semantic && "ai-active")}
                  >
                    <div className="marketplace-search">
                      <Search className="marketplace-search-icon" />
                      <input
                        type="text"
                        placeholder={
                          filters.semantic
                            ? "Describe your dream website (e.g., 'sleek dark dashboard for SaaS')..."
                            : "Search templates (instant matches like Amazon)..."
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
                                <TrendingUp className="w-3.5 h-3.5" style={{ color: "#f26445" }} />
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
                                    const priceText =
                                      item.is_free || item.price === 0
                                        ? "FREE"
                                        : `$${item.price}`;
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
                                          <span
                                            className={cn(
                                              "amazon-match-price",
                                              (item.is_free || item.price === 0) && "is-free"
                                            )}
                                          >
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
                                <p style={{ margin: 0, fontSize: "0.82rem", color: "#77766f" }}>
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

                  <div className="toolbar-spacer" />

                  <div className="view-toggle">
                    {(["grid", "list"]).map((v) => (
                      <button
                        key={v}
                        onClick={() => setView(v)}
                        className={cn("view-btn", view === v && "active")}
                        title={v === "grid" ? "Grid view" : "List view"}
                      >
                        {v === "grid"
                          ? <LayoutGrid className="view-toggle-icon" />
                          : <LayoutList className="view-toggle-icon" />}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* ── Quick Categories Horizontal Scroll Pill Bar ── */}
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

              {/* ── Result count ──────────────────────────────────── */}
              <div className="result-count-bar flex justify-between items-center flex-wrap gap-2" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                <p className="result-count-text">
                  {isLoading && displayedTemplates.length === 0 ? "Loading…" : `${total.toLocaleString()} templates found`}
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

              {/* ── Template grid ─────────────────────────────────── */}
              <TemplateGrid
                templates={displayedTemplates}
                isLoading={isLoading && displayedTemplates.length === 0}
                view={view}
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
    </>
  );
}

export default Marketplace;
