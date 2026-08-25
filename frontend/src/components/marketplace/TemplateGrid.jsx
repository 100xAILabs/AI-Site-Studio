"use client";

/**
 * TemplateGrid — virtualized grid of TemplateCards with skeleton loading states (React JSX).
 */

import { motion } from "framer-motion";
import TemplateCard from "./TemplateCard";
import { cn } from "@/lib/utils";
import "./TemplateGrid.css";

function TemplateCardSkeleton() {
  return (
    <div className="template-card">
      <div className="card-thumbnail-container skeleton" />
      <div className="skeleton-body">
        <div className="skeleton-line title skeleton" />
        <div className="skeleton-line desc-1 skeleton" />
        <div className="skeleton-line desc-2 skeleton" />
        <div className="skeleton-row">
          <div className="skeleton-pill left skeleton" />
          <div className="skeleton-pill right skeleton" />
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid-empty-state"
    >
      <div className="empty-emoji">🔍</div>
      <h3 className="empty-title">No templates found</h3>
      <p className="empty-subtitle">
        Try adjusting your filters or search query to find what you&apos;re looking for.
      </p>
    </motion.div>
  );
}

export default function TemplateGrid({
  templates,
  isLoading,
  view = "grid",
  onFavorite,
  onWishlist,
}) {
  if (isLoading) {
    return (
      <div className={cn("marketplace-grid", view === "list" && "list-view")}>
        {Array.from({ length: 9 }).map((_, i) => (
          <TemplateCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (!templates || !templates.length) {
    return (
      <div className="marketplace-grid list-view">
        <EmptyState />
      </div>
    );
  }

  return (
    <div className={cn("marketplace-grid", view === "list" && "list-view")}>
      {templates.map((template, i) => (
        <TemplateCard
          key={template.id}
          template={template}
          index={i}
          onFavorite={onFavorite}
          onWishlist={onWishlist}
        />
      ))}
    </div>
  );
}
