/**
 * Utility for merging Tailwind classes with proper override behavior.
 * Uses clsx for conditional classes and tailwind-merge for deduplication.
 */

import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

import { useCurrencyStore } from "@/store/currencyStore";

/**
 * Apply psychological charm pricing ending in 99 (e.g. 2327 -> 2399, 4678 -> 4699, 42 -> 49).
 */
export function apply99CharmPricing(amount) {
  if (amount === 0 || !amount) return 0;
  const val = Number(amount);
  if (isNaN(val) || val <= 0) return amount;

  if (val >= 100) {
    return Math.floor(val / 100) * 100 + 99;
  } else if (val >= 10) {
    return Math.floor(val / 10) * 10 + 9;
  }
  return val;
}

export const CURRENCY_RATES_TO_USD = {
  USD: 1.0,
  INR: 87.0,
  EUR: 0.92,
  GBP: 0.79,
  CAD: 1.36,
  AUD: 1.52,
  JPY: 152.0,
  AED: 3.67,
};

/**
 * Convert an amount from a seller's local currency to USD.
 */
export function convertToUSD(amount, fromCurrency = "USD", rates = null) {
  if (!amount || isNaN(Number(amount))) return 0;
  const num = Number(amount);
  const src = (fromCurrency || "USD").toUpperCase();
  if (src === "USD") return num;

  const activeRates = rates || CURRENCY_RATES_TO_USD;
  const rate = activeRates[src] || CURRENCY_RATES_TO_USD[src] || 1.0;
  const inUsd = num / rate;
  return Math.round(inUsd * 100) / 100;
}

/**
 * Format a price number as USD currency string by default.
 * Marketplace browsing, cart, and orders strictly use USD ($).
 */
export function formatPrice(price, currency = "USD", locale = "en-US") {
  if (price === 0 || price === "0") return "Free";
  const numPrice = Number(price) || 0;
  const targetCurrency = (currency || "USD").toUpperCase();

  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: targetCurrency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(numPrice);
  } catch (e) {
    return `$${numPrice.toFixed(0)}`;
  }
}

/**
 * Format price in USD ($) for marketplace and cart.
 */
export function formatConvertedPrice(
  price,
  fromCurrency = "USD",
  targetCurrency = "USD",
  rates = null
) {
  if (price === 0 || price === "0") return "Free";
  const numPrice = Number(price) || 0;
  return formatPrice(numPrice, "USD");
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
