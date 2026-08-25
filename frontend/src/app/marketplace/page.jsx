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
  LayoutGrid, LayoutList, Search, X, Sparkles,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import SidebarFilters from "@/components/marketplace/SidebarFilters";
import TemplateGrid from "@/components/marketplace/TemplateGrid";
import { useTemplates, useToggleFavorite, useToggleWishlist } from "@/hooks/useTemplates";
import { useFilterStore } from "@/store";
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

function Marketplace() {
  const { getToken } = useAppAuth();
  const { filters, setFilter, setFilters, resetFilters } = useFilterStore();
  const [view, setView] = useState("grid");
  const [searchInput, setSearchInput] = useState(filters.q ?? "");
  const searchParams = useSearchParams();

  // Sync URL params → store on mount
  useEffect(() => {
    const params = {};
    searchParams.forEach((v, k) => { params[k] = v; });
    if (Object.keys(params).length > 0) {
      setFilters({
        category: params.category,
        sub_category: params.sub_category,
        q: params.q,
        sort: params.sort ?? "newest",
        page: params.page ? Number(params.page) : 1,
        min_price: params.min_price ? Number(params.min_price) : undefined,
        max_price: params.max_price ? Number(params.max_price) : undefined,
        sales: params.sales,
        compatibility: params.compatibility,
        language: params.language,
        date_added: params.date_added,
        developer: params.developer,
      });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch categories dynamically
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get("/categories"),
    staleTime: 1000 * 30,
  });

  // Auth token for mutations
  const [token, setToken] = useState(null);
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
      <div className="marketplace-page">
        <div className="marketplace-container">
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

                {/* Row 2 — Sort tabs + spacer + view toggle */}
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

                  <button
                    onClick={() => navigate("/marketplace/generate")}
                    className="marketplace-ai-generate-btn"
                    style={{ marginRight: "0.75rem" }}
                    title="Generate a custom template in the studio"
                  >
                    <Sparkles className="ai-generate-icon animate-pulse" />
                    <span>Studio Creator</span>
                  </button>

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
    </>
  );
}

export default Marketplace;
