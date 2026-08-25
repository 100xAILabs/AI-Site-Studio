"use client";

/**
 * TemplateCard — premium card for marketplace grid (React JSX).
 */

import { useState } from "react";
import Image from "@/components/Image";
import Link from "@/components/Link";
import { motion } from "framer-motion";
import {
  Heart,
  Bookmark,
  Eye,
  ShoppingCart,
  Star,
  Download,
  Zap,
  Moon,
  Check,
} from "lucide-react";
import { cn, formatPrice, formatNumber, discountPercent } from "@/lib/utils";
import { useCartStore } from "@/store";
import { useAppUser } from "@/lib/auth";
import "./TemplateCard.css";

const StarRating = ({ rating, count }) => (
  <div className="star-rating-wrapper">
    <div className="star-rating-stars">
      {[1, 2, 3, 4, 5].map((s) => (
        <Star
          key={s}
          className={cn(
            "star-rating-star",
            s <= Math.round(rating) && "active"
          )}
        />
      ))}
    </div>
    <span className="text-xs text-muted-foreground">({formatNumber(count)})</span>
  </div>
);

export default function TemplateCard({
  template,
  onFavorite,
  onWishlist,
  index = 0,
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [imgError, setImgError] = useState(false);
  const { isSignedIn, user } = useAppUser();
  const addToCart = useCartStore((s) => s.addItem);
  const isInCart = useCartStore((s) => s.isInCart(template.id));

  const isSeller = isSignedIn && (user?.role === "seller" || user?.role === "SELLER");

  const handleAddToCart = (e) => {
    e.preventDefault();
    e.stopPropagation();
    addToCart({
      templateId: template.id,
      title: template.title,
      price: template.price,
      thumbnail: template.thumbnail_url,
      licenseType: "regular",
    });
  };

  const discount = template.original_price
    ? discountPercent(template.original_price, template.price)
    : 0;

    const templateSlug = template.slug || template.id;

    return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05, ease: "easeOut" }}
      className="group card-outer-wrapper"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <Link href={`/marketplace/${templateSlug}`} className="card-main-link">
        <div className="template-card card-hover">
          {/* Thumbnail / Video Preview */}
          <div className="card-thumbnail-container">
            {!imgError ? (
              <Image
                src={template.thumbnail_url}
                alt={template.title}
                fill
                className="card-thumbnail-img"
                onError={() => setImgError(true)}
                sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
              />
            ) : (
              <div className="card-thumbnail-fallback">
                <span className="fallback-emoji">🎨</span>
              </div>
            )}

            {/* Overlay on hover */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: isHovered ? 1 : 0 }}
              transition={{ duration: 0.2 }}
              className="card-hover-overlay"
            >
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  window.location.href = `/marketplace/${templateSlug}`;
                }}
                className="overlay-btn-preview"
              >
                <Eye className="overlay-icon" />
                Preview
              </button>
              {!isSeller && (
                <button
                  onClick={handleAddToCart}
                  className={cn(
                    "overlay-btn-cart",
                    isInCart ? "in-cart" : "add-to-cart"
                  )}
                >
                  {isInCart ? (
                    <><Check className="overlay-icon" /> Added</>
                  ) : (
                    <><ShoppingCart className="overlay-icon" /> Add to Cart</>
                  )}
                </button>
              )}
            </motion.div>

            {/* Badges */}
            <div className="card-badge-list">
              {template.is_bestseller && (
                <span className="card-badge-item bestseller">
                  Bestseller
                </span>
              )}
              {template.is_new && (
                <span className="card-badge-item new">
                  New
                </span>
              )}
              {template.is_on_sale && discount > 0 && (
                <span className="card-badge-item onsale">
                  -{discount}%
                </span>
              )}
              {template.is_featured && (
                <span className="card-badge-item featured">
                  Featured
                </span>
              )}
            </div>

            {/* Action buttons */}
            <div className="card-action-list">
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onFavorite?.(template.id);
                }}
                className={cn(
                  "card-action-btn",
                  template.is_favorited && "favorited"
                )}
                aria-label={template.is_favorited ? "Unfavorite" : "Favorite"}
              >
                <Heart
                  className="card-action-icon"
                />
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onWishlist?.(template.id);
                }}
                className={cn(
                  "card-action-btn",
                  template.is_wishlisted && "wishlisted"
                )}
                aria-label={template.is_wishlisted ? "Remove from wishlist" : "Add to wishlist"}
              >
                <Bookmark
                  className="card-action-icon"
                />
              </motion.button>
            </div>
          </div>

          {/* Card Body */}
          <div className="card-body">
            {/* Title & Meta */}
            <div>
              <div className="card-title-row">
                <h3 className="card-title">
                  {template.title}
                </h3>
                <div className="card-title-badges">
                  {template.has_dark_mode && (
                    <span title="Dark mode">
                      <Moon className="card-meta-icon" />
                    </span>
                  )}
                  {template.is_ai_ready && (
                    <span title="Live Customizable">
                      <Zap className="card-meta-icon ai-ready" />
                    </span>
                  )}
                </div>
              </div>
              <p className="card-desc">
                {template.short_description}
              </p>
            </div>

            {/* Rating */}
            <StarRating rating={template.rating_avg} count={template.rating_count} />

            {/* Stats */}
            <div className="card-meta-row">
              <span className="card-meta-download-span">
                <Download className="card-meta-icon" />
                {formatNumber(template.downloads_count)}
              </span>
              {template.framework && (
                <span className="framework-tag">
                  {template.framework}
                </span>
              )}
              <span>{template.pages_count} pages</span>
            </div>

            {/* Price Row */}
            <div className="card-price-row">
              <div className="price-val-container">
                <span className="price-val">
                  {template.is_free ? "Free" : formatPrice(template.price)}
                </span>
                {template.original_price && template.original_price > template.price && (
                  <span className="original-price-val">
                    {formatPrice(template.original_price)}
                  </span>
                )}
              </div>
              <span className="text-xs text-muted-foreground">
                {template.developer_name || "Site Studio"}
              </span>
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
