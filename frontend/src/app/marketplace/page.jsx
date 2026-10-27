"use client";

/**
 * Marketplace Page — split layout: sidebar filters + template grid + toolbar (React JSX).
 */

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { navigate } from "@/components/Link";
const useRouter = () => ({
  push: (to) => navigate(to),
  replace: (to) => navigate(to),
});
const useSearchParams = () => new URLSearchParams(window.location.search);
import { useAppAuth } from "@/lib/auth";
import {
  LayoutGrid, LayoutList, Search, X, Sparkles, SlidersHorizontal, Filter,
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

  // Debounced search
  const debouncedSearch = debounce((value) => {
    setFilter("q", value || undefined);
    setFilter("semantic", undefined); // Typing normally resets semantic search
  }, 350);

  const handleSearch = (value) => {
    setSearchInput(value);
    debouncedSearch(value);
  };

  const triggerNormalSearch = (value) => {
    debouncedSearch.cancel();
    setFilter("q", value || undefined);
    setFilter("semantic", undefined);
  };

  const triggerAISearch = () => {
    debouncedSearch.cancel();
    if (searchInput) {
      setFilter("q", searchInput);
      setFilter("semantic", true);
    }
  };

  const total = data?.total ?? 0;
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

                {/* Row 1 — Search bar + Semantic toggle */}
                <div className="toolbar-row">
                  <div className={cn("marketplace-search-wrapper", filters.semantic && "ai-active")}>
                    <div className="marketplace-search">
                      <Search className="marketplace-search-icon" />
                      <input
                        type="text"
                        placeholder={
                          filters.semantic
                            ? "Describe your dream website (e.g., 'sleek dark dashboard for SaaS')..."
                            : "Search templates..."
                        }
                        value={searchInput}
                        onChange={(e) => handleSearch(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            triggerNormalSearch(searchInput);
                          }
                        }}
                        className="marketplace-search-input"
                      />
                      {searchInput && (
                        <button
                          type="button"
                          onClick={() => {
                            handleSearch("");
                            triggerNormalSearch("");
                          }}
                          className="search-clear-btn"
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
                  {isLoading ? "Loading…" : `${total.toLocaleString()} templates found`}
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
                templates={data?.items ?? []}
                isLoading={isLoading}
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
