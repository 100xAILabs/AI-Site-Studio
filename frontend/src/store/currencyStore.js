/**
 * Currency store for real-time exchange rates & location-based currency conversion.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

const DEFAULT_RATES = {
  USD: 1.0,
  INR: 95.48,
  EUR: 0.92,
  GBP: 0.78,
  CAD: 1.36,
  AUD: 1.52,
  JPY: 154.20,
  AED: 3.67,
  SGD: 1.34,
  BRL: 5.65,
};

export const useCurrencyStore = create(
  persist(
    (set, get) => ({
      rates: DEFAULT_RATES,
      userCurrency: "USD",
      hasFetched: false,

      setUserCurrency: (currency) => set({ userCurrency: (currency || "USD").toUpperCase() }),

      fetchRates: async () => {
        try {
          const res = await fetch(`${API_BASE}/payment/exchange-rates`);
          if (res.ok) {
            const data = await res.json();
            if (data.rates) {
              set({ rates: { ...DEFAULT_RATES, ...data.rates }, hasFetched: true });
            }
          }
        } catch (err) {
          console.warn("Failed to fetch exchange rates, using defaults:", err);
        }
      },

      convertAmount: (amount, fromCurrency = "USD", toCurrency = null) => {
        if (!amount || amount === 0) return 0;
        const targetCurrency = (toCurrency || get().userCurrency || "USD").toUpperCase();
        const srcCurrency = (fromCurrency || "USD").toUpperCase();

        if (srcCurrency === targetCurrency) return amount;

        const currentRates = get().rates || DEFAULT_RATES;
        const srcRate = currentRates[srcCurrency] || 1.0;
        const targetRate = currentRates[targetCurrency] || 1.0;

        // Convert to USD base first, then to target currency
        const amountInUSD = amount / srcRate;
        const converted = amountInUSD * targetRate;
        return Math.round(converted * 100) / 100;
      },
    }),
    {
      name: "aisitestudio_currency",
      partialize: (state) => ({
        userCurrency: state.userCurrency,
      }),
    }
  )
);
