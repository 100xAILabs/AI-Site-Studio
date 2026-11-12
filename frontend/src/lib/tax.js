/**
 * Country-specific digital goods tax configuration & calculation utilities.
 * Supports VAT, GST, and Sales Tax across major global markets.
 */

export const COUNTRY_TAX_RATES = {
  IN: {
    code: "IN",
    name: "India",
    rate: 0.18,
    label: "GST (18%)",
    taxName: "Goods and Services Tax",
    flag: "🇮🇳",
    currency: "INR",
  },
  US: {
    code: "US",
    name: "United States",
    rate: 0.08,
    label: "Sales Tax (8%)",
    taxName: "Estimated State Sales Tax",
    flag: "🇺🇸",
    currency: "USD",
  },
  GB: {
    code: "GB",
    name: "United Kingdom",
    rate: 0.20,
    label: "VAT (20%)",
    taxName: "Value Added Tax",
    flag: "🇬🇧",
    currency: "GBP",
  },
  DE: {
    code: "DE",
    name: "Germany",
    rate: 0.19,
    label: "EU VAT (19%)",
    taxName: "Value Added Tax",
    flag: "🇩🇪",
    currency: "EUR",
  },
  FR: {
    code: "FR",
    name: "France",
    rate: 0.20,
    label: "EU VAT (20%)",
    taxName: "Value Added Tax",
    flag: "🇫🇷",
    currency: "EUR",
  },
  ES: {
    code: "ES",
    name: "Spain",
    rate: 0.21,
    label: "EU VAT (21%)",
    taxName: "Value Added Tax",
    flag: "🇪🇸",
    currency: "EUR",
  },
  IT: {
    code: "IT",
    name: "Italy",
    rate: 0.22,
    label: "EU VAT (22%)",
    taxName: "Value Added Tax",
    flag: "🇮🇹",
    currency: "EUR",
  },
  NL: {
    code: "NL",
    name: "Netherlands",
    rate: 0.21,
    label: "EU VAT (21%)",
    taxName: "Value Added Tax",
    flag: "🇳🇱",
    currency: "EUR",
  },
  CA: {
    code: "CA",
    name: "Canada",
    rate: 0.13,
    label: "HST/GST (13%)",
    taxName: "Harmonized Sales Tax",
    flag: "🇨🇦",
    currency: "CAD",
  },
  AU: {
    code: "AU",
    name: "Australia",
    rate: 0.10,
    label: "GST (10%)",
    taxName: "Goods and Services Tax",
    flag: "🇦🇺",
    currency: "AUD",
  },
  SG: {
    code: "SG",
    name: "Singapore",
    rate: 0.09,
    label: "GST (9%)",
    taxName: "Goods and Services Tax",
    flag: "🇸🇬",
    currency: "SGD",
  },
  JP: {
    code: "JP",
    name: "Japan",
    rate: 0.10,
    label: "JCT (10%)",
    taxName: "Japanese Consumption Tax",
    flag: "🇯🇵",
    currency: "JPY",
  },
  AE: {
    code: "AE",
    name: "United Arab Emirates",
    rate: 0.05,
    label: "VAT (5%)",
    taxName: "Value Added Tax",
    flag: "🇦🇪",
    currency: "AED",
  },
  BR: {
    code: "BR",
    name: "Brazil",
    rate: 0.10,
    label: "Digital Tax (10%)",
    taxName: "Digital Service Tax",
    flag: "🇧🇷",
    currency: "BRL",
  },
  OTHER: {
    code: "OTHER",
    name: "Other Countries",
    rate: 0.10,
    label: "Digital Goods Tax (10%)",
    taxName: "Standard Digital Tax",
    flag: "🌐",
    currency: "USD",
  },
};

/**
 * Calculate tax amount and total for a subtotal and country code.
 * Pricing is strictly all-inclusive (zero extra tax charged).
 */
export function calculateTax(subtotal, countryCode = "US") {
  const code = (countryCode || "US").toUpperCase();
  const taxInfo = COUNTRY_TAX_RATES[code] || COUNTRY_TAX_RATES.OTHER;
  const numSubtotal = Math.max(0, Number(subtotal) || 0);

  return {
    subtotal: numSubtotal,
    rate: 0,
    ratePercent: 0,
    taxAmount: 0,
    totalAmount: numSubtotal,
    label: "Tax Included",
    taxName: "All-Inclusive Pricing",
    countryName: taxInfo.name,
    flag: taxInfo.flag,
    code: taxInfo.code,
  };
}

/**
 * Best-effort detection of user's country from browser timezone or language locale.
 * Defaults reliably to India (IN) for Indian regional timezones (+05:30 / Calcutta / Kolkata).
 */
export function detectBrowserCountry() {
  if (typeof window === "undefined") return "IN";
  try {
    const tz = (Intl?.DateTimeFormat()?.resolvedOptions()?.timeZone || "").toLowerCase();
    if (
      tz.includes("calcutta") ||
      tz.includes("kolkata") ||
      tz.includes("india") ||
      tz.includes("delhi") ||
      tz.includes("mumbai")
    ) {
      return "IN";
    }
    if (tz.includes("london")) return "GB";
    if (tz.includes("berlin")) return "DE";
    if (tz.includes("paris")) return "FR";
    if (tz.includes("madrid")) return "ES";
    if (tz.includes("rome")) return "IT";
    if (tz.includes("amsterdam")) return "NL";
    if (tz.includes("toronto") || tz.includes("vancouver") || tz.includes("montreal")) return "CA";
    if (tz.includes("sydney") || tz.includes("melbourne") || tz.includes("brisbane")) return "AU";
    if (tz.includes("singapore")) return "SG";
    if (tz.includes("tokyo")) return "JP";
    if (tz.includes("dubai")) return "AE";
    if (tz.includes("sao_paulo")) return "BR";
    if (tz.includes("new_york") || tz.includes("chicago") || tz.includes("los_angeles") || tz.includes("america")) return "US";

    const lang = (navigator.language || (navigator.languages && navigator.languages[0]) || "").toUpperCase();
    if (lang.includes("-IN") || lang.includes("_IN")) return "IN";
    if (lang.includes("-GB") || lang.includes("_GB")) return "GB";
    if (lang.includes("-US") || lang.includes("_US")) return "US";
    if (lang.includes("-CA") || lang.includes("_CA")) return "CA";
    if (lang.includes("-AU") || lang.includes("_AU")) return "AU";
    if (lang.includes("-DE") || lang.includes("_DE")) return "DE";
    if (lang.includes("-FR") || lang.includes("_FR")) return "FR";
    if (lang.includes("-SG") || lang.includes("_SG")) return "SG";
  } catch (e) {}

  return "IN";
}

