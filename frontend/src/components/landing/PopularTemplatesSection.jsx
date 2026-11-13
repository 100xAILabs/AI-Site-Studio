"use client";

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Link from "@/components/Link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Heart,
  ShoppingCart,
  Briefcase,
  Bot,
  Palette,
  Eye,
  Sparkles,
  Flame,
} from "lucide-react";
import { toast } from "sonner";
import { useTemplates, useFeaturedTemplates } from "@/hooks/useTemplates";
import { POPULAR_TEMPLATES_CATALOG } from "@/data/popularTemplatesData";
import "./PopularTemplatesSection.css";

// Fallback icon map based on slug or category
const ICON_MAP = {
  saaskit: Bot,
  shopvibe: ShoppingCart,
  artboard: Palette,
  "nexus-pro": Briefcase,
  technology: Bot,
  ecommerce: ShoppingCart,
  portfolio: Palette,
  business: Briefcase,
};

function getTemplateIcon(item) {
  if (ICON_MAP[item.slug]) return ICON_MAP[item.slug];
  if (ICON_MAP[item.id]) return ICON_MAP[item.id];
  if (item.category?.slug && ICON_MAP[item.category.slug]) return ICON_MAP[item.category.slug];
  return Sparkles;
}

export default function PopularTemplatesSection() {
  const navigate = useNavigate();
  const [favorites, setFavorites] = useState({});

  // Query top high-selling templates from backend API (sorted by best_sellers)
  const { data: topSellingData } = useTemplates({ sort_by: "best_sellers", limit: 4 });
  const { data: featuredData } = useFeaturedTemplates(4);

  const apiList = topSellingData?.items || (Array.isArray(featuredData) && featuredData.length > 0 ? featuredData : null);

  const templatesList = Array.isArray(apiList) && apiList.length > 0
    ? apiList.slice(0, 4)
    : POPULAR_TEMPLATES_CATALOG.slice(0, 4);

  const toggleFavorite = (e, id, title) => {
    e.preventDefault();
    e.stopPropagation();
    setFavorites((prev) => {
      const isFav = !prev[id];
      if (isFav) {
        toast.success(`Saved "${title}" to favorites!`);
      } else {
        toast.info(`Removed "${title}" from favorites.`);
      }
      return { ...prev, [id]: isFav };
    });
  };

  return (
    <section className="popular-templates-section">
      <div className="container-xl popular-templates-container">
        {/* Section Layout Grid: Left Copy & Right 4 Cards */}
        <div className="popular-templates-grid">
          {/* Left Column: Eyebrow, Title, Description, Browse Button */}
          <div className="popular-left-col">
            <motion.div
              initial={{ opacity: 0, x: -14 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4 }}
              className="popular-eyebrow"
            >
              <span className="eyebrow-dash">—</span>
              <span>Top High-Selling Templates</span>
            </motion.div>

            <motion.h2
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: 0.08 }}
              className="popular-headline"
            >
              <div className="popular-head-white">Stunning Designs.</div>
              <div className="popular-head-gradient">Top Selling Templates.</div>
            </motion.h2>

            <motion.p
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: 0.16 }}
              className="popular-description"
            >
              Discover our top-selling, highest-rated templates — battle-tested by
              thousands of developers, creators, and businesses worldwide.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: 0.24 }}
              className="popular-cta-wrapper"
            >
              <Link href="/marketplace?sort_by=best_sellers" className="popular-browse-btn">
                <span>Browse Best Sellers</span>
                <ArrowRight className="w-4 h-4 ml-1 popular-browse-arrow" />
              </Link>
            </motion.div>
          </div>

          {/* Right Column: 4 Template Cards Grid */}
          <div className="popular-cards-grid">
            {templatesList.map((item, idx) => {
              const Icon = getTemplateIcon(item);
              const templateSlug = item.slug || item.id;
              const isFav = !!favorites[item.id || templateSlug];
              const displayTitle = item.displayName || item.title || "Featured Template";
              const previewImgSrc = item.thumbnail_url || `/landing/template_${item.category_id || "business"}.png`;
              const badgeText = item.bestseller_badge || (idx === 0 ? "#1 Top Seller" : "Top Seller");
              const salesText = item.sales_label || `${item.download_count || "2k+"} Sold`;

              return (
                <motion.div
                  key={templateSlug}
                  initial={{ opacity: 0, y: 18 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.45, delay: idx * 0.06 }}
                  className="popular-template-card"
                >
                  {/* Direct interactive card navigating to template details page */}
                  <div
                    className="popular-card-link cursor-pointer"
                    onClick={() => navigate(`/marketplace/${templateSlug}`)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        navigate(`/marketplace/${templateSlug}`);
                      }
                    }}
                    title={`Open ${displayTitle} template`}
                  >
                    {/* Visual Preview */}
                    <div className="popular-card-preview">
                      {/* Top High-Selling Badge */}
                      <div className="popular-bestseller-badge">
                        <Flame className="w-3 h-3 text-amber-400 fill-amber-400" />
                        <span>{badgeText}</span>
                        <span className="bestseller-dot">•</span>
                        <span className="bestseller-sales-text">{salesText}</span>
                      </div>

                      <img
                        src={previewImgSrc}
                        alt={displayTitle}
                        className="popular-card-image"
                        loading="lazy"
                        onError={(e) => {
                          e.target.onerror = null;
                          e.target.src = "/landing/Hero.png";
                        }}
                      />

                      {/* On-Hover Quick Live Preview Action Overlay */}
                      <div className="popular-preview-overlay">
                        <button
                          type="button"
                          className="popular-overlay-preview-btn"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            navigate(`/preview?template=${templateSlug}`);
                          }}
                          title="Open in Live Canvas Editor"
                        >
                          <Eye className="w-3.5 h-3.5 mr-1.5" />
                          <span>Live Preview</span>
                        </button>
                      </div>
                    </div>

                    {/* Bottom Info Bar with Title, Price and Favorite */}
                    <div className="popular-card-bottom-bar">
                      <div className="popular-card-category-tag">
                        <Icon className="w-3.5 h-3.5 text-[#dfb180]" />
                        <span>{displayTitle}</span>
                      </div>

                      {item.price !== undefined && (
                        <div className="popular-card-price-tag">
                          ${item.price}
                        </div>
                      )}

                      <button
                        type="button"
                        onClick={(e) => toggleFavorite(e, item.id || templateSlug, displayTitle)}
                        className={`popular-heart-btn ${isFav ? "active" : ""}`}
                        aria-label={`Favorite ${displayTitle}`}
                        title={isFav ? "Favorited" : "Save to favorites"}
                      >
                        <Heart
                          className={`w-3.5 h-3.5 ${isFav ? "fill-rose-500 text-rose-500" : "text-slate-400"}`}
                        />
                      </button>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
