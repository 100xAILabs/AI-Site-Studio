/**
 * TanStack Query hooks for all template-related API calls (React JS version).
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { POPULAR_TEMPLATES_CATALOG, getFallbackTemplate } from "@/data/popularTemplatesData";

// ── Query Keys ────────────────────────────────────────────────────────────

export const templateKeys = {
  all: ["templates"],
  lists: () => [...templateKeys.all, "list"],
  list: (filters) => [...templateKeys.lists(), filters],
  details: () => [...templateKeys.all, "detail"],
  detail: (slug) => [...templateKeys.details(), slug],
  featured: () => [...templateKeys.all, "featured"],
};

// ── Hooks ─────────────────────────────────────────────────────────────────

/**
 * Paginated marketplace template list with filters.
 */
export function useTemplates(filters, token) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      params.set(k, String(v));
    }
  });

  return useQuery({
    queryKey: templateKeys.list(filters),
    queryFn: () =>
      api.get(`/templates?${params.toString()}`, token),
    placeholderData: (prev) => prev,
    staleTime: 1000 * 60 * 15, // 15 minutes fresh
    gcTime: 1000 * 60 * 60, // 1 hour in memory
  });
}

/**
 * Single template detail by slug (with instant cache pre-seeding).
 */
export function useTemplate(slug, token) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: templateKeys.detail(slug),
    queryFn: async () => {
      try {
        const res = await api.get(`/templates/${slug}`, token);
        if (res && res.id) return res;
      } catch (err) {
        const fallback = getFallbackTemplate(slug);
        if (fallback) return fallback;
        throw err;
      }
      const fallback = getFallbackTemplate(slug);
      if (fallback) return fallback;
      return null;
    },
    staleTime: 1000 * 60 * 15, // 15 mins fresh
    gcTime: 1000 * 60 * 60,
    placeholderData: (prev) => prev,
    initialData: () => {
      if (!slug) return undefined;
      const lists = qc.getQueriesData({ queryKey: templateKeys.lists() });
      for (const [, listData] of lists) {
        if (listData?.items) {
          const match = listData.items.find((item) => item.slug === slug || item.id === slug);
          if (match) return match;
        }
      }
      return getFallbackTemplate(slug) || undefined;
    },
    enabled: !!slug,
  });
}

/**
 * Featured templates for landing page.
 */
export function useFeaturedTemplates(limit = 8) {
  return useQuery({
    queryKey: [...templateKeys.featured(), limit],
    queryFn: async () => {
      try {
        const res = await api.get(`/templates/featured?limit=${limit}`);
        if (Array.isArray(res) && res.length > 0) return res;
      } catch {
        // Fallback to real catalog
      }
      return POPULAR_TEMPLATES_CATALOG.slice(0, limit);
    },
    staleTime: 1000 * 60 * 10,
    initialData: () => POPULAR_TEMPLATES_CATALOG.slice(0, limit),
  });
}

/**
 * Search templates (keyword or semantic).
 */
export function useSearch(query, semantic = false, token) {
  return useQuery({
    queryKey: ["search", query, semantic],
    queryFn: () =>
      api.get(
        `/search?q=${encodeURIComponent(query)}&semantic=${semantic}`,
        token,
      ),
    enabled: query.length > 0,
    staleTime: 1000 * 30,
  });
}

export function useToggleFavorite(token) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (templateId) =>
      api.post(`/favorites/${templateId}`, {}, token),
    onMutate: async (templateId) => {
      await qc.cancelQueries({ queryKey: templateKeys.all });
      const previousTemplates = qc.getQueryData(templateKeys.all);

      // Optimistically update lists
      qc.setQueriesData({ queryKey: ["templates", "list"] }, (old) => {
        if (!old || !old.items) return old;
        return {
          ...old,
          items: old.items.map((t) =>
            t.id === templateId ? { ...t, is_favorited: !t.is_favorited } : t
          ),
        };
      });

      // Optimistically update details
      qc.setQueriesData({ queryKey: ["templates", "detail"] }, (old) => {
        if (!old) return old;
        if (old.id === templateId) {
          return { ...old, is_favorited: !old.is_favorited };
        }
        return old;
      });

      return { previousTemplates };
    },
    onError: (err, templateId, context) => {
      if (context?.previousTemplates) {
        qc.setQueryData(templateKeys.all, context.previousTemplates);
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["favorites"] });
    },
  });
}

/**
 * Toggle wishlist mutation.
 */
export function useToggleWishlist(token) {
  const qc = useQueryClient();
  return useMutation({
    pointer: "toggleWishlist",
    mutationFn: (templateId) =>
      api.post(`/wishlist/${templateId}`, {}, token),
    onMutate: async (templateId) => {
      await qc.cancelQueries({ queryKey: templateKeys.all });
      const previousTemplates = qc.getQueryData(templateKeys.all);

      // Optimistically update lists
      qc.setQueriesData({ queryKey: ["templates", "list"] }, (old) => {
        if (!old || !old.items) return old;
        return {
          ...old,
          items: old.items.map((t) =>
            t.id === templateId ? { ...t, is_wishlisted: !t.is_wishlisted } : t
          ),
        };
      });

      // Optimistically update details
      qc.setQueriesData({ queryKey: ["templates", "detail"] }, (old) => {
        if (!old) return old;
        if (old.id === templateId) {
          return { ...old, is_wishlisted: !old.is_wishlisted };
        }
        return old;
      });

      return { previousTemplates };
    },
    onError: (err, templateId, context) => {
      if (context?.previousTemplates) {
        qc.setQueryData(templateKeys.all, context.previousTemplates);
      }
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["wishlist"] });
    },
  });
}

/**
 * Fetch reviews for a template dynamically.
 */
export function useTemplateReviews(templateId, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["reviews", templateId, page, pageSize],
    queryFn: () =>
      api.get(`/reviews/template/${templateId}?page=${page}&page_size=${pageSize}`),
    enabled: !!templateId,
  });
}

/**
 * Submit a review for a template.
 */
export function useCreateReview(token) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => api.post("/reviews", data, token),
    onSuccess: (review) => {
      qc.invalidateQueries({ queryKey: ["reviews", review.template_id] });
      qc.invalidateQueries({ queryKey: templateKeys.all });
    },
  });
}

/**
 * Fetch follow status of current user for a seller.
 */
export function useFollowStatus(sellerId, token) {
  return useQuery({
    queryKey: ["follow-status", sellerId],
    queryFn: () => api.get(`/follows/status/${sellerId}`, token),
    enabled: !!sellerId && !!token,
  });
}

/**
 * Toggle follow status for a seller.
 */
export function useToggleFollow(token) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sellerId) => api.post(`/follows/toggle/${sellerId}`, {}, token),
    onSuccess: (data, sellerId) => {
      qc.invalidateQueries({ queryKey: ["follow-status", sellerId] });
      qc.invalidateQueries({ queryKey: ["seller-followers"] });
      qc.invalidateQueries({ queryKey: ["followers"] });
      qc.invalidateQueries({ queryKey: ["following"] });
    },
  });
}


