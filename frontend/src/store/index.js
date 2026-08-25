/**
 * Zustand store for marketplace filter state (React JS version).
 */

import { create } from "zustand";
import { useAuthStore } from "./authStore";

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
        // Reset to page 1 when any filter changes (except page itself)
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

// ── Cart Store ────────────────────────────────────────────────────────────

export const useCartStore = create((set, get) => ({
  items: [],

  addItem: (item) => {
    const userId = useAuthStore.getState().user?.id || "guest";
    const currentItems = get().items;
    if (currentItems.some((i) => i.templateId === item.templateId)) return;
    const newItems = [...currentItems, item];
    localStorage.setItem(`cart_items_${userId}`, JSON.stringify(newItems));
    set({ items: newItems });
  },

  removeItem: (templateId) => {
    const userId = useAuthStore.getState().user?.id || "guest";
    const newItems = get().items.filter((i) => i.templateId !== templateId);
    localStorage.setItem(`cart_items_${userId}`, JSON.stringify(newItems));
    set({ items: newItems });
  },

  clearCart: () => {
    const userId = useAuthStore.getState().user?.id || "guest";
    localStorage.setItem(`cart_items_${userId}`, JSON.stringify([]));
    set({ items: [] });
  },

  total: () => get().items.reduce((sum, item) => sum + item.price, 0),

  isInCart: (templateId) => get().items.some((i) => i.templateId === templateId),
}));

// Subscribe to auth changes to dynamically swap carts on login/logout
if (typeof window !== "undefined") {
  // Set initial items based on current auth state
  const initialUserId = useAuthStore.getState().user?.id || "guest";
  const stored = localStorage.getItem(`cart_items_${initialUserId}`);
  if (stored) {
    useCartStore.setState({ items: JSON.parse(stored) });
  }

  useAuthStore.subscribe((state) => {
    const userId = state.user?.id || "guest";
    
    // Read stored cart for this user
    let storedCart = [];
    try {
      const storedStr = localStorage.getItem(`cart_items_${userId}`);
      storedCart = storedStr ? JSON.parse(storedStr) : [];
    } catch (e) {
      storedCart = [];
    }
    
    if (userId !== "guest") {
      // If we just logged in, merge any items in 'guest' cart
      let guestCart = [];
      try {
        const guestStr = localStorage.getItem("cart_items_guest");
        guestCart = guestStr ? JSON.parse(guestStr) : [];
      } catch (e) {}
      
      if (guestCart.length > 0) {
        const userTemplateIds = new Set(storedCart.map(i => i.templateId));
        const newGuestItems = guestCart.filter(i => !userTemplateIds.has(i.templateId));
        if (newGuestItems.length > 0) {
          storedCart = [...storedCart, ...newGuestItems];
          localStorage.setItem(`cart_items_${userId}`, JSON.stringify(storedCart));
        }
        // Clear guest cart
        localStorage.setItem("cart_items_guest", JSON.stringify([]));
      }
    }
    
    useCartStore.setState({ items: storedCart });
  });
}
