import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppUser } from "@/lib/auth";

/**
 * Custom hook to identify templates already purchased and owned by the current user.
 * Returns:
 * - isPurchased(templateIdOrSlug): boolean check
 * - purchasedSet: Set of template IDs and slugs owned by user
 * - userOrders: list of completed orders
 */
export function usePurchasedTemplateIds() {
  const { isSignedIn, token } = useAppUser();

  const { data: userOrders = [], isLoading } = useQuery({
    queryKey: ["user-orders-all", token],
    queryFn: async () => {
      if (!token) return [];
      try {
        const res = await api.get("/orders", token);
        return Array.isArray(res) ? res : res?.items || res?.orders || [];
      } catch {
        return [];
      }
    },
    enabled: Boolean(isSignedIn && token),
    staleTime: 1000 * 60 * 2, // 2 minutes fresh
  });

  const purchasedSet = useMemo(() => {
    const ids = new Set();
    if (!Array.isArray(userOrders) || !userOrders.length) return ids;

    userOrders.forEach((order) => {
      const status = (order.payment_status || order.status || "").toLowerCase();
      if (status === "completed" || status === "paid" || status === "succeeded") {
        (order.items || []).forEach((item) => {
          const tId = item.template_id || item.template?.id;
          if (tId) {
            ids.add(String(tId).toLowerCase());
          }
          if (item.template?.slug) {
            ids.add(String(item.template.slug).toLowerCase());
          }
        });
      }
    });

    return ids;
  }, [userOrders]);

  const isPurchased = (templateIdOrSlug) => {
    if (!templateIdOrSlug) return false;
    return purchasedSet.has(String(templateIdOrSlug).toLowerCase());
  };

  return {
    isPurchased,
    purchasedSet,
    userOrders,
    isLoading,
  };
}
