/**
 * Zustand store for marketplace filter state and cart state.
 */

import { create } from "zustand";
import { useAuthStore } from "./authStore";
import { calculateTax, detectBrowserCountry, COUNTRY_TAX_RATES } from "@/lib/tax";
import { POPULAR_TEMPLATES_CATALOG, getFallbackTemplate } from "@/data/popularTemplatesData";

const defaultFilters = {
  sort: "newest",
  page: 1,
  page_size: 20,
};

export const useFilterStore = create((set, get) => ({
  filters: defaultFilters,

  setFilter: (key, value) =>
    set((state) => ({
      filters: {
        ...state.filters,
        [key]: value,
        ...(key !== "page" ? { page: 1 } : {}),
      },
    })),

  setFilters: (filters) =>
    set((state) => ({ filters: { ...state.filters, ...filters } })),

  resetFilters: () => set({ filters: defaultFilters }),

  isFilterActive: () => {
    const { filters } = get();
    const active = Object.entries(filters).some(([k, v]) => {
      if (k === "sort" && v === "newest") return false;
      if (k === "page" && v === 1) return false;
      if (k === "page_size" && v === 20) return false;
      return v !== undefined && v !== null && v !== "";
    });
    return active;
  },
}));

// ── Price Lookup & Sanitization Helper ─────────────────────────────────────
const lookupTemplateDetails = (item) => {
  const tId = item?.templateId || item?.id || item?.template_id;
  const match = getFallbackTemplate(tId) || POPULAR_TEMPLATES_CATALOG.find(
    (t) => t.id === tId || t.slug === tId
  );
  
  const rawPrice = Number(item?.price);
  const resolvedPrice = !isNaN(rawPrice) && rawPrice > 0 
    ? rawPrice 
    : (match && Number(match.price) > 0 ? Number(match.price) : 49);

  return {
    templateId: tId,
    id: tId,
    title: item?.title || match?.displayName || match?.title || "Exclusive Website Template",
    subtitle: item?.subtitle || item?.short_description || match?.sub_category || match?.industry || "Professional Responsive Website Template",
    price: resolvedPrice,
    price_currency: item?.price_currency || match?.price_currency || "USD",
    quantity: Math.max(1, Number(item?.quantity) || 1),
    thumbnail: item?.thumbnail || item?.thumbnail_url || match?.thumbnail_url || "/landing/template_saas.png",
    thumbnail_url: item?.thumbnail_url || item?.thumbnail || match?.thumbnail_url || "/landing/template_saas.png",
    framework: item?.framework || match?.framework || "HTML5 / CSS / JS",
    licenseType: item?.licenseType || "Lifetime Access",
  };
};

const sanitizeCartItems = (list) => {
  if (!Array.isArray(list)) return [];
  return list.map(lookupTemplateDetails);
};

// ── Cart Store ────────────────────────────────────────────────────────────

export const useCartStore = create((set, get) => ({
  items: [],
  countryCode:
    typeof window !== "undefined"
      ? localStorage.getItem("aisitestudio_country") || detectBrowserCountry()
      : "IN",
  
  couponCode: "",
  couponDiscount: 0, // fraction, e.g. 0.20 for 20%
  couponError: "",
  couponSuccess: "",

  setCountryCode: (code) => {
    const clean = (code || "IN").toUpperCase();
    if (typeof window !== "undefined") {
      localStorage.setItem("aisitestudio_country", clean);
    }
    set({ countryCode: clean });
  },

  addItem: (rawItem) => {
    const userId = useAuthStore.getState().user?.id || "guest";
    const currentItems = get().items;
    const item = lookupTemplateDetails(rawItem);
    
    // If item already in cart, increment quantity
    if (currentItems.some((i) => i.templateId === item.templateId)) {
      const updated = currentItems.map((i) =>
        i.templateId === item.templateId ? { ...i, quantity: (i.quantity || 1) + 1 } : i
      );
      if (typeof window !== "undefined") {
        localStorage.setItem(`cart_items_${userId}`, JSON.stringify(updated));
      }
      set({ items: updated });
      return;
    }

    const newItems = [...currentItems, item];
    if (typeof window !== "undefined") {
      localStorage.setItem(`cart_items_${userId}`, JSON.stringify(newItems));
    }
    set({ items: newItems });
  },

  updateQuantity: (templateId, delta) => {
    const userId = useAuthStore.getState().user?.id || "guest";
    const currentItems = get().items;
    const newItems = currentItems
      .map((i) => {
        if (i.templateId === templateId || i.id === templateId) {
          const newQty = (i.quantity || 1) + delta;
          return newQty > 0 ? { ...i, quantity: newQty } : null;
        }
        return i;
      })
      .filter(Boolean);

    if (typeof window !== "undefined") {
      localStorage.setItem(`cart_items_${userId}`, JSON.stringify(newItems));
    }
    set({ items: newItems });
  },

  removeItem: (templateId) => {
    const userId = useAuthStore.getState().user?.id || "guest";
    const newItems = get().items.filter(
      (i) => i.templateId !== templateId && i.id !== templateId
    );
    if (typeof window !== "undefined") {
      localStorage.setItem(`cart_items_${userId}`, JSON.stringify(newItems));
    }
    set({ items: newItems });
  },

  clearCart: () => {
    const userId = useAuthStore.getState().user?.id || "guest";
    if (typeof window !== "undefined") {
      localStorage.setItem(`cart_items_${userId}`, JSON.stringify([]));
    }
    set({ items: [], couponCode: "", couponDiscount: 0, couponSuccess: "", couponError: "" });
  },

  applyCoupon: (code) => {
    const clean = String(code || "").trim().toUpperCase();
    if (!clean) {
      set({ couponError: "Please enter a valid coupon code.", couponSuccess: "" });
      return false;
    }

    const coupons = {
      WELCOME20: 0.20,
      STUDIO20: 0.20,
      SAVE10: 0.10,
      STUDIO10: 0.10,
      VIP30: 0.30,
      SPECIAL: 0.15,
      FREESHIP: 0.05,
    };

    if (coupons[clean]) {
      const discount = coupons[clean];
      set({
        couponCode: clean,
        couponDiscount: discount,
        couponSuccess: `Coupon "${clean}" applied! (${Math.round(discount * 100)}% off)`,
        couponError: "",
      });
      return true;
    } else {
      set({
        couponError: `Invalid code "${clean}". Try WELCOME20 or STUDIO10.`,
        couponSuccess: "",
      });
      return false;
    }
  },

  removeCoupon: () => {
    set({ couponCode: "", couponDiscount: 0, couponSuccess: "", couponError: "" });
  },

  // Raw items subtotal before coupon
  grossSubtotal: () =>
    get().items.reduce(
      (sum, item) => sum + (Number(item.price) || 0) * (item.quantity || 1),
      0
    ),

  // Discount amount in USD
  discountAmount: () => {
    const gross = get().grossSubtotal();
    const discountRate = get().couponDiscount || 0;
    return Math.round(gross * discountRate * 100) / 100;
  },

  // Net subtotal after coupon discount
  subtotal: () => {
    const gross = get().grossSubtotal();
    const discount = get().discountAmount();
    return Math.max(0, Math.round((gross - discount) * 100) / 100);
  },

  getTaxDetails: () => {
    const sub = get().subtotal();
    return calculateTax(sub, get().countryCode);
  },

  total: () => {
    const { totalAmount } = get().getTaxDetails();
    return totalAmount;
  },

  isInCart: (templateId) =>
    get().items.some((i) => i.templateId === templateId || i.id === templateId),
}));

// Subscribe to auth changes to dynamically swap carts on login/logout
if (typeof window !== "undefined") {
  const initialUserId = useAuthStore.getState().user?.id || "guest";
  const stored = localStorage.getItem(`cart_items_${initialUserId}`);
  if (stored) {
    try {
      useCartStore.setState({ items: sanitizeCartItems(JSON.parse(stored)) });
    } catch (e) {}
  }

  useAuthStore.subscribe((state) => {
    const userId = state.user?.id || "guest";

    let storedCart = [];
    try {
      const storedStr = localStorage.getItem(`cart_items_${userId}`);
      storedCart = storedStr ? JSON.parse(storedStr) : [];
    } catch (e) {
      storedCart = [];
    }

    if (userId !== "guest") {
      let guestCart = [];
      try {
        const guestStr = localStorage.getItem("cart_items_guest");
        guestCart = guestStr ? JSON.parse(guestStr) : [];
      } catch (e) {}

      if (guestCart.length > 0) {
        const userTemplateIds = new Set(storedCart.map((i) => i.templateId || i.id));
        const newGuestItems = guestCart.filter(
          (i) => !userTemplateIds.has(i.templateId || i.id)
        );
        if (newGuestItems.length > 0) {
          storedCart = [...storedCart, ...newGuestItems];
          localStorage.setItem(`cart_items_${userId}`, JSON.stringify(storedCart));
        }
        localStorage.setItem("cart_items_guest", JSON.stringify([]));
      }
    }

    useCartStore.setState({ items: sanitizeCartItems(storedCart) });
  });
}
