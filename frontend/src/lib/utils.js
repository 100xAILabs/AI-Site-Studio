/**
 * Utility for merging Tailwind classes with proper override behavior.
 * Uses clsx for conditional classes and tailwind-merge for deduplication.
 */

import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/**
 * Format a price number as currency string.
 */
export function formatPrice(price, currency = "USD", locale = "en-US") {
  if (price === 0) return "Free";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price);
}

/**
 * Format a number with K/M abbreviation.
 */
export function formatNumber(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

/**
 * Calculate discount percentage.
 */
export function discountPercent(original, current) {
  return Math.round(((original - current) / original) * 100);
}

/**
 * Truncate text to a max length with ellipsis.
 */
export function truncate(text, maxLength) {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trimEnd() + "…";
}

/**
 * Generate a slug from a string.
 */
export function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/**
 * Debounce a function.
 */
export function debounce(fn, delay) {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Stagger delay for animation sequences.
 */
export function staggerDelay(index, base = 0.05) {
  return index * base;
}
