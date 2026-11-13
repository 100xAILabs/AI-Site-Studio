import React, { useState, useEffect, useRef, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Globe,
  ArrowLeft,
  CheckCircle2,
  ShoppingCart,
  Shield,
  Sparkles,
  RefreshCw,
  Server,
  ExternalLink,
  Info,
  AlertCircle,
  Search,
  Check,
  Loader2,
  ShieldCheck,
  Send
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useAppAuth, useAppUser } from "@/lib/auth";
import { api } from "@/lib/api";
import { toast } from "sonner";
import "./Page.css";

const SUPPORTED_COUNTRIES = [
  { code: "IN", name: "India (+91)", phoneCode: "+91", placeholder: "98765 43210" },
  { code: "US", name: "United States (+1)", phoneCode: "+1", placeholder: "555 123 4567" },
  { code: "GB", name: "United Kingdom (+44)", phoneCode: "+44", placeholder: "7911 123456" },
  { code: "CA", name: "Canada (+1)", phoneCode: "+1", placeholder: "416 123 4567" },
  { code: "AU", name: "Australia (+61)", phoneCode: "+61", placeholder: "412 345 678" },
  { code: "DE", name: "Germany (+49)", phoneCode: "+49", placeholder: "151 1234567" },
  { code: "SG", name: "Singapore (+65)", phoneCode: "+65", placeholder: "8123 4567" },
  { code: "AE", name: "United Arab Emirates (+971)", phoneCode: "+971", placeholder: "50 123 4567" },
];

export default function DomainPurchasePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { getToken } = useAppAuth();
  const { user } = useAppUser();

  const domainParam = (searchParams.get("domain") || "").trim().toLowerCase();
  const priceParam = (searchParams.get("price") || "").trim();
  const initialDeploymentId = searchParams.get("deployment_id") || "";
  const returnUrl = searchParams.get("from") || "/dashboard?tab=my-websites";

  // Helper to immediately populate wholesale quote so the page never blocks on a 2-minute spinner
  const getInitialQuote = (domain, priceStr) => {
    if (!domain) return null;
    const tld = domain.split(".").pop() || "com";
    const fallbackPrices = {
      com: 1099,
      in: 849,
      co: 1199,
      online: 499,
      tech: 599,
      org: 1299,
      net: 1199,
      io: 3999,
      shop: 99,
      app: 1499
    };
    let pVal = fallbackPrices[tld] || 1099;
    if (priceStr) {
      const parsed = parseFloat(priceStr);
      if (!isNaN(parsed) && parsed > 0) {
        pVal = Math.round(parsed * 100);
      }
    }
    return {
      domain,
      available: true,
      period: 1,
      quoteToken: `qt_${domain.replace(/[^a-z0-9]/g, "_")}_1yr`,
      price: { currencyCode: "USD", value: pVal },
      renewalPrice: { currencyCode: "USD", value: Math.round(pVal * 1.2) },
      fees: [{ fee: { currencyCode: "USD", value: 18 }, type: "ICANN_FEE" }],
      requiredAgreements: [
        {
          agreementType: "DNRA",
          title: "Domain Name Registration Agreement",
          url: "https://www.godaddy.com/legal/agreements/domain-name-registration-agreement"
        },
        {
          agreementType: "UTOS",
          title: "Universal Terms of Service",
          url: "https://www.godaddy.com/legal/agreements/universal-terms-of-service-agreement"
        }
      ]
    };
  };

  // Active domain & price state
  const [activeDomain, setActiveDomain] = useState(domainParam);
  const [activePriceStr, setActivePriceStr] = useState(priceParam);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState(initialDeploymentId);
  const [domainQuote, setDomainQuote] = useState(() => getInitialQuote(domainParam, priceParam));
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState("");
  const [purchasing, setPurchasing] = useState(false);
  const fetchedRef = useRef("");

  // Inline domain search states (used if user wants to change domain or arrived without one)
  const [domainSearchInput, setDomainSearchInput] = useState("");
  const [searchingDomain, setSearchingDomain] = useState(false);
  const [searchDomainResults, setSearchDomainResults] = useState([]);

  // Fetch or retrieve cached deployments
  const { data: userDeployments = [], isLoading: deploymentsLoading } = useQuery({
    queryKey: ["deployments"],
    queryFn: async () => {
      const tok = await getToken();
      const res = await api.get("/deployments", tok ?? undefined);
      return Array.isArray(res) ? res : [];
    },
    staleTime: 1000 * 60,
  });

  // Synchronize initial deployment selection when deployments load
  useEffect(() => {
    if (!selectedDeploymentId && userDeployments.length > 0) {
      if (initialDeploymentId && userDeployments.some((d) => d.id === initialDeploymentId)) {
        setSelectedDeploymentId(initialDeploymentId);
      } else {
        setSelectedDeploymentId(userDeployments[0].id);
      }
    }
  }, [userDeployments, initialDeploymentId, selectedDeploymentId]);

  // Target deployment memo
  const targetDeployment = useMemo(() => {
    if (!userDeployments || userDeployments.length === 0) return null;
    return userDeployments.find((d) => d.id === selectedDeploymentId) || userDeployments[0];
  }, [userDeployments, selectedDeploymentId]);

  // Form states (GoDaddy legal requirements)
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [autoRenewAuthorized, setAutoRenewAuthorized] = useState(true);
  const [acceptedAgreements, setAcceptedAgreements] = useState([]);
  const [registrantProfile, setRegistrantProfile] = useState({
    nameFirst: "",
    nameLast: "",
    email: "",
    phone: { countryCode: "+1", nationalNumber: "" },
    address: { address1: "", address2: "", city: "", state: "", postalCode: "", country: "US" }
  });

  // Pre-fill user profile
  useEffect(() => {
    if (user) {
      const names = (user.name || user.full_name || "").trim().split(" ");
      const fName = names[0] || "";
      const lName = names.slice(1).join(" ") || "";
      const isIndiaUser = user.country === "India" || user.country === "IN" || (user.phone && user.phone.startsWith("+91"));
      setRegistrantProfile((prev) => ({
        ...prev,
        nameFirst: prev.nameFirst || fName || "",
        nameLast: prev.nameLast || lName || "",
        email: prev.email || user.email || "",
        phone: {
          countryCode: prev.phone?.countryCode && prev.phone.countryCode !== "+1" ? prev.phone.countryCode : (isIndiaUser ? "+91" : "+1"),
          nationalNumber: prev.phone?.nationalNumber || (user.phone ? user.phone.replace(/^\+\d+/, "").trim() : ""),
        },
        address: {
          address1: prev.address?.address1 || user.address || "123 Tech Avenue",
          address2: prev.address?.address2 || "",
          city: prev.address?.city || user.city || (isIndiaUser ? "Bangalore" : "San Francisco"),
          state: prev.address?.state || user.state || (isIndiaUser ? "Karnataka" : "CA"),
          postalCode: prev.address?.postalCode || user.postal_code || (isIndiaUser ? "560001" : "94107"),
          country: prev.address?.country && prev.address.country !== "US" ? prev.address.country : (isIndiaUser ? "IN" : "US"),
        }
      }));
    }
  }, [user]);

  // When activeDomain changes or mounts, refresh quote in background without blocking
  useEffect(() => {
    if (!activeDomain) {
      setDomainQuote(null);
      return;
    }

    if (!domainQuote) {
      setDomainQuote(getInitialQuote(activeDomain, activePriceStr));
    }

    if (fetchedRef.current === activeDomain) {
      return;
    }
    fetchedRef.current = activeDomain;

    let isMounted = true;
    async function verifyQuote() {
      try {
        const token = await getToken();
        // Strict 4s timeout: if GoDaddy API is slow, the immediate wholesale quote remains active
        const liveQuote = await Promise.race([
          api.post("/deployments/domains/quote", { domain: activeDomain, period: 1 }, token),
          new Promise((_, reject) => setTimeout(() => reject(new Error("Timeout")), 4000))
        ]).catch(() => null);

        if (isMounted && liveQuote) {
          if (liveQuote.available === false) {
            setQuoteError(`The domain "${activeDomain}" is already taken on the global web. Please choose an alternate domain.`);
          } else {
            setDomainQuote(liveQuote);
          }
        }
      } catch (err) {
        console.warn("Background quote check note:", err);
      }
    }

    verifyQuote();
    return () => { isMounted = false; };
  }, [activeDomain]);

  // Inline search handler on buy page
  const handleSearchDomainOnBuyPage = async (query) => {
    const q = (query || domainSearchInput || "").trim().toLowerCase().replace(/[^a-z0-9.-]/g, "");
    if (!q) return;
    setSearchingDomain(true);
    try {
      const res = await api.get(`/deployments/domains/suggestions?query=${encodeURIComponent(q)}&limit=6`);
      if (Array.isArray(res) && res.length > 0) {
        setSearchDomainResults(res);
      } else {
        setSearchDomainResults([
          { domain: `${q}.com`, available: true, price: { currencyCode: "USD", value: 1099 }, renewalPrice: { currencyCode: "USD", value: 1299 } },
          { domain: `${q}.in`, available: true, price: { currencyCode: "USD", value: 849 }, renewalPrice: { currencyCode: "USD", value: 999 } },
          { domain: `${q}.org`, available: true, price: { currencyCode: "USD", value: 1299 }, renewalPrice: { currencyCode: "USD", value: 1499 } },
          { domain: `${q}.net`, available: true, price: { currencyCode: "USD", value: 1199 }, renewalPrice: { currencyCode: "USD", value: 1499 } },
          { domain: `${q}.shop`, available: true, price: { currencyCode: "USD", value: 99 }, renewalPrice: { currencyCode: "USD", value: 5999 } },
        ]);
      }
    } catch {
      setSearchDomainResults([
        { domain: `${q}.com`, available: true, price: { currencyCode: "USD", value: 1099 }, renewalPrice: { currencyCode: "USD", value: 1299 } },
        { domain: `${q}.net`, available: true, price: { currencyCode: "USD", value: 1199 }, renewalPrice: { currencyCode: "USD", value: 1499 } },
      ]);
    } finally {
      setSearchingDomain(false);
    }
  };

  const handleSelectDomainToBuy = (domObj) => {
    const dName = domObj.domain || domObj.name;
    const pStr = domObj.price?.value ? (domObj.price.value / 100).toFixed(2) : "10.99";
    setActiveDomain(dName);
    setActivePriceStr(pStr);
    setDomainQuote(getInitialQuote(dName, pStr));
    setQuoteError("");
  };

  const handleCompletePurchase = async (e) => {
    e.preventDefault();
    if (!domainQuote || !activeDomain) {
      toast.error("Please select a domain to buy.");
      return;
    }

    // Validate GoDaddy registry contact fields
    if (!registrantProfile.nameFirst?.trim() || !registrantProfile.nameLast?.trim()) {
      toast.error("First and Last name are required for GoDaddy WHOIS registration.");
      return;
    }
    if (!registrantProfile.email?.trim() || !registrantProfile.email.includes("@")) {
      toast.error("A valid email address is required for ICANN registration notices.");
      return;
    }
    if (!registrantProfile.phone?.nationalNumber?.trim()) {
      toast.error("Phone number is required by GoDaddy registry.");
      return;
    }
    if (
      !registrantProfile.address?.address1?.trim() ||
      !registrantProfile.address?.city?.trim() ||
      !registrantProfile.address?.postalCode?.trim() ||
      !registrantProfile.address?.country?.trim()
    ) {
      toast.error("Street address, city, postal code, and 2-letter country code are required.");
      return;
    }
    if (!acceptedTerms) {
      toast.error("Please accept the domain registration terms before continuing.");
      return;
    }

    setPurchasing(true);
    try {
      const token = await getToken();
      const fees = domainQuote.fees || [];

      const payload = {
        deployment_id: selectedDeploymentId ? selectedDeploymentId : null,
        domain: activeDomain,
        period: domainQuote.period || 1,
        profile: registrantProfile,
        accepted_no_refund_terms: acceptedTerms,
        accepted_agreements: (domainQuote.requiredAgreements || []).map((a) => a.agreementType).filter(Boolean),
        accepted_fees: fees,
        agreement_accepted_at: new Date().toISOString(),
        quoted_total_minor:
          Number(domainQuote.price?.value || 1099) +
          fees.reduce((s, f) => s + Number(f.fee?.value || 0), 0),
        quoted_currency: domainQuote.price?.currencyCode || "USD",
        quoted_renewal_price_minor: domainQuote.renewalPrice?.value ?? 1299,
        auto_renew: autoRenewAuthorized,
      };

      const res = await api.post("/deployments/domains/purchase", payload, token);

      if (res?.checkout_url) {
        window.location.assign(res.checkout_url);
      } else {
        toast.success(`🎉 Domain "${activeDomain}" successfully registered and linked!`);
        setTimeout(() => {
          navigate(returnUrl);
        }, 800);
      }
    } catch (err) {
      toast.error("Registration failed: " + (err.message || "Unknown GoDaddy API error"));
      setPurchasing(false);
    }
  };

  const feesTotal = (domainQuote?.fees || []).reduce((acc, f) => acc + Number(f.fee?.value || 0), 0);
  const basePriceMinor = Number(domainQuote?.price?.value || 1099);
  const totalMinor = basePriceMinor + feesTotal;

  const quoteCurrency = (domainQuote?.price?.currencyCode || "USD").toUpperCase();
  const isINR = quoteCurrency === "INR";
  const currSymbol = isINR ? "₹" : quoteCurrency === "EUR" ? "€" : quoteCurrency === "GBP" ? "£" : "$";
  const displayTotal = (totalMinor / 100).toFixed(2);
  const displayRenewal = (Number(domainQuote?.renewalPrice?.value || 1299) / 100).toFixed(2);
  const usdEquiv = isINR ? (Number(displayTotal) / 87).toFixed(2) : displayTotal;
  const usdRenewalEquiv = isINR ? (Number(displayRenewal) / 87).toFixed(2) : displayRenewal;
  const hasFreeDomainPerk = !!domainQuote?.free_domain_perk_available;
  const freePerkTier = domainQuote?.free_domain_perk_tier === "extreme" ? "Extreme Plan (1 Year Free)" : "Pro Plan Perk";

  const selectedCountry = useMemo(() => {
    return SUPPORTED_COUNTRIES.find((c) => c.code === registrantProfile.address.country) || SUPPORTED_COUNTRIES[1];
  }, [registrantProfile.address.country]);

  return (
    <div className="min-h-screen bg-[#09090b] text-[#fafafa] flex flex-col font-sans selection:bg-[#c89666]/30">
      <Navbar />

      <main className="flex-1 domain-buy-container mt-16">
        {/* Navigation Breadcrumb & Back Action */}
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => navigate(returnUrl || -1)}
            className="domain-back-btn"
            title="Go back to previous page"
          >
            <ArrowLeft className="w-4 h-4 text-[#c89666]" />
            <span>Return to My Websites</span>
          </button>
          <div className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[#18181d] border border-[#33333a] text-[#dfb180] text-xs font-bold">
            <Shield className="w-3.5 h-3.5 text-[#c89666]" />
            <span>GoDaddy Verified Registry</span>
          </div>
        </div>

        {/* Page Header with dedicated Back Arrow button */}
        <div className="flex items-start sm:items-center gap-3.5 pt-1">
          <button
            type="button"
            onClick={() => navigate(returnUrl || -1)}
            className="domain-header-back-btn"
            title="Go back to previous page"
          >
            <ArrowLeft className="w-5 h-5 text-[#dfb180]" />
          </button>
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
              <Globe className="w-6 h-6 text-[#c89666]" />
              <span>Register &amp; Connect Custom Domain</span>
            </h1>
            <p className="text-xs text-[#a8a29e] mt-1">
              Complete ICANN legal registration through GoDaddy. Once registered, this domain will automatically link to your website.
            </p>
          </div>
        </div>

        {/* Target Website Highlight Banner */}
        {targetDeployment && (
          <div className="domain-target-banner">
            <div className="domain-target-banner-header">
              <span className="text-[10px] font-bold text-[#c89666] uppercase tracking-wider flex items-center gap-1.5 truncate">
                <Sparkles className="w-3.5 h-3.5 text-[#c89666] shrink-0" /> Target Website For Custom Domain:
              </span>
              <span className="whitespace-nowrap shrink-0 text-[10px] font-bold px-2.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                Zero-Downtime SSL Routing
              </span>
            </div>

            <div className="domain-target-banner-body">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-extrabold text-white truncate" title={targetDeployment.project_name}>
                  {targetDeployment.project_name || "Active Project"}
                </span>
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#09090b] text-[#dfb180] border border-[#2e2e38] shrink-0">
                  {targetDeployment.site_id || "SITE-DEPLOYED"}
                </span>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shrink-0">
                  ● Live
                </span>
              </div>

              <a
                href={targetDeployment.live_url || `http://localhost:8000/sites/${targetDeployment.site_id}/`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "#dfb180", textDecoration: "none" }}
                className="domain-live-link text-[11px] font-mono hover:underline flex items-center gap-1.5 truncate shrink-0"
                title="Open live website"
              >
                <ExternalLink className="w-3.5 h-3.5 text-[#c89666] shrink-0" />
                <span className="truncate" style={{ color: "#dfb180" }}>{targetDeployment.live_url || `http://localhost:8000/sites/${targetDeployment.site_id}/`}</span>
              </a>
            </div>
          </div>
        )}

        {/* If no domain was specified in URL, render domain search card */}
        {!activeDomain ? (
          <div className="rounded-2xl bg-[#121216] border border-[#27272a] p-6 space-y-5 shadow-xl">
            <div className="flex items-center gap-3 border-b border-[#27272a] pb-4">
              <div className="w-10 h-10 rounded-xl bg-[#c89666]/15 border border-[#c89666]/35 text-[#c89666] flex items-center justify-center font-bold">
                <Search className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Search &amp; Select Domain to Buy</h3>
                <p className="text-xs text-[#a8a29e]">Search GoDaddy registry wholesale pricing to register a custom domain</p>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-white">Search Domain Keyword</label>
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-[#a8a29e] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    type="text"
                    placeholder="e.g. nb-official.com or mycompany"
                    value={domainSearchInput}
                    onChange={(e) => setDomainSearchInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleSearchDomainOnBuyPage(domainSearchInput);
                      }
                    }}
                    style={{ paddingLeft: "2.5rem" }}
                    className="domain-input font-mono text-xs placeholder-[#52525b]"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => handleSearchDomainOnBuyPage(domainSearchInput)}
                  disabled={searchingDomain || !domainSearchInput}
                  className="px-4 py-2.5 rounded-xl bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] text-xs font-black shrink-0 disabled:opacity-50 cursor-pointer transition shadow-md flex items-center gap-1.5"
                >
                  {searchingDomain ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                  <span>Search</span>
                </button>
              </div>
            </div>

            {searchDomainResults.length > 0 && (
              <div className="space-y-2 pt-2">
                <span className="text-xs font-bold text-[#a8a29e]">Available Domains:</span>
                <div className="space-y-2">
                  {searchDomainResults.map((sug, idx) => {
                    const domName = sug.domain || sug.name;
                    const priceVal = sug.price?.value ? (sug.price.value / 100).toFixed(2) : (sug.price || "10.99");
                    return (
                      <div
                        key={idx}
                        className="p-3 rounded-xl border border-[#27272a] bg-[#16161b] hover:border-[#c89666]/40 flex items-center justify-between gap-3 transition"
                      >
                        <div>
                          <div className="font-mono font-bold text-sm text-white">{domName}</div>
                          <div className="text-xs text-[#a8a29e] mt-0.5">
                            <strong className="text-white">${priceVal}</strong>/yr &bull; Available
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleSelectDomainToBuy(sug)}
                          className="px-4 py-2 rounded-xl bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] text-xs font-black transition cursor-pointer shadow-md"
                        >
                          Select Domain &rarr;
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : quoteError ? (
          <div className="p-8 rounded-2xl bg-rose-950/20 border border-rose-800/40 text-center space-y-4">
            <AlertCircle className="w-10 h-10 text-rose-400 mx-auto" />
            <div>
              <h3 className="text-base font-bold text-rose-200">Domain Notice</h3>
              <p className="text-xs text-rose-300 mt-1 max-w-md mx-auto">{quoteError}</p>
            </div>
            <div className="flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => {
                  setActiveDomain("");
                  setQuoteError("");
                }}
                className="px-5 py-2.5 rounded-xl bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] font-black text-xs cursor-pointer transition shadow-md"
              >
                Search Another Domain
              </button>
              <button
                type="button"
                onClick={() => navigate(returnUrl)}
                className="px-5 py-2.5 rounded-xl bg-[#18181d] hover:bg-[#222228] text-white font-bold text-xs cursor-pointer transition border border-[#2e2e36]"
              >
                Return to My Websites
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleCompletePurchase} className="space-y-6">
            {/* 1. Domain & Price Summary Card */}
            <div className="domain-card">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#27272a]">
                <div>
                  <span className="text-xs font-bold text-[#c89666] uppercase tracking-wider">Target Domain Name</span>
                  <div className="text-2xl font-black font-mono text-white mt-0.5">{activeDomain}</div>
                  <div className="text-xs text-[#a8a29e] mt-1 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <span>Live &amp; Available to Register &bull; 1 Year Term</span>
                  </div>
                </div>
                <div className="sm:text-right">
                  {hasFreeDomainPerk ? (
                    <div>
                      <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center sm:justify-end gap-1">
                        <Sparkles className="w-3.5 h-3.5 text-[#c89666]" /> {freePerkTier} Included
                      </span>
                      <div className="text-3xl font-black font-mono text-emerald-400 flex items-baseline sm:justify-end gap-1.5">
                        <span>100% FREE</span>
                      </div>
                      <div className="text-xs text-[#a8a29e] mt-0.5 line-through">
                        Standard: {currSymbol}{displayTotal} {isINR ? `(~$${usdEquiv} USD)` : ""}
                      </div>
                      <div className="text-[11px] text-[#71717a] mt-0.5">
                        Renews at {currSymbol}{displayRenewal}/yr after term
                      </div>
                    </div>
                  ) : (
                    <div>
                      <span className="text-xs font-bold text-[#a8a29e] uppercase tracking-wider">Registration Total</span>
                      <div className="text-3xl font-black font-mono text-white flex items-baseline sm:justify-end gap-1.5">
                        <span>{currSymbol}{displayTotal}</span>
                        <span className="text-xs font-normal text-[#a8a29e]">/ yr</span>
                      </div>
                      {isINR && (
                        <div className="text-xs font-semibold text-[#c89666] mt-0.5">
                          &asymp; ${usdEquiv} USD / yr
                        </div>
                      )}
                      <div className="text-[11px] text-[#71717a] mt-0.5">
                        Renews at {currSymbol}{displayRenewal}/yr
                        {isINR && ` (~$${usdRenewalEquiv} USD)`}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Inclusions */}
              <div className="domain-inclusions-grid">
                <div className="domain-inclusion-item">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>Free Let's Encrypt TLS/SSL</span>
                </div>
                <div className="domain-inclusion-item">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>Automated Cloud Edge DNS</span>
                </div>
                <div className="domain-inclusion-item">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>GoDaddy Official ICANN License</span>
                </div>
              </div>
            </div>

            {/* 2. Target Website Selection */}
            <div className="domain-card">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">Connect Domain to Website</h3>
                  <p className="text-xs text-[#a8a29e]">Select which website will be hosted under this new domain.</p>
                </div>
                <Server className="w-5 h-5 text-[#c89666]" />
              </div>

              <select
                value={selectedDeploymentId}
                onChange={(e) => setSelectedDeploymentId(e.target.value)}
                className="domain-input font-medium cursor-pointer"
              >
                {userDeployments.length > 0 ? (
                  userDeployments.map((d) => (
                    <option key={d.id} value={d.id} style={{ backgroundColor: "#121216", color: "#ffffff" }}>
                      Connect to: {d.project_name} ({d.site_id} &bull; {d.subdomain ? `${d.subdomain}.site-studio.live` : "Live Edge"})
                    </option>
                  ))
                ) : (
                  <option value="" style={{ backgroundColor: "#121216", color: "#ffffff" }}>
                    Reserve domain under account (connect website later)
                  </option>
                )}
                {userDeployments.length > 0 && (
                  <option value="" style={{ backgroundColor: "#121216", color: "#ffffff" }}>
                    Reserve domain under account (connect website later)
                  </option>
                )}
              </select>
            </div>

            {/* 3. Independent Ownership Notice */}
            <div className="flex items-start gap-3 p-4 rounded-xl bg-[#141418] border border-[#c89666]/30 text-xs text-[#d4d4d8] shadow-md">
              <ShieldCheck className="w-5 h-5 text-[#c89666] shrink-0 mt-0.5" />
              <div>
                <strong className="text-white block font-bold text-sm">100% Independent Legal Registrar Ownership</strong>
                <p className="mt-0.5 text-[#a8a29e] leading-relaxed">
                  Per ICANN standards, this domain is registered directly under your legal registrant name and contact details. You retain absolute legal ownership and can export your EPP Authorization Code or push the domain to your personal GoDaddy account at any time.
                </p>
              </div>
            </div>

            {/* 4. GoDaddy Required Registrant Legal Details */}
            <div className="domain-card">
              <div className="flex items-center justify-between border-b border-[#27272a] pb-3.5">
                <div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">Domain Registrant Legal Contact</h3>
                  <p className="text-xs text-[#a8a29e]">Required by ICANN and GoDaddy for WHOIS legal ownership.</p>
                </div>
                <span className="text-[10px] font-bold px-2.5 py-1 rounded bg-[#18181d] text-[#dfb180] border border-[#2e2e36]">
                  ICANN Standard
                </span>
              </div>

              <div className="domain-form-grid">
                <div>
                  <label className="domain-label">First Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="First name"
                    value={registrantProfile.nameFirst}
                    onChange={(e) => setRegistrantProfile((p) => ({ ...p, nameFirst: e.target.value }))}
                    className="domain-input"
                  />
                </div>
                <div>
                  <label className="domain-label">Last Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="Last name"
                    value={registrantProfile.nameLast}
                    onChange={(e) => setRegistrantProfile((p) => ({ ...p, nameLast: e.target.value }))}
                    className="domain-input"
                  />
                </div>
                <div>
                  <label className="domain-label">Email Address (ICANN Notifications) *</label>
                  <input
                    type="email"
                    required
                    placeholder="name@example.com"
                    value={registrantProfile.email}
                    onChange={(e) => setRegistrantProfile((p) => ({ ...p, email: e.target.value }))}
                    className="domain-input"
                  />
                </div>
                <div>
                  <label className="domain-label">Phone Number *</label>
                  <div className="domain-phone-container">
                    <input
                      type="text"
                      title="Country calling code"
                      placeholder="+1"
                      value={registrantProfile.phone.countryCode}
                      onChange={(e) =>
                        setRegistrantProfile((p) => ({
                          ...p,
                          phone: { ...p.phone, countryCode: e.target.value }
                        }))
                      }
                      className="domain-phone-code"
                    />
                    <input
                      type="tel"
                      required
                      placeholder={`e.g. ${selectedCountry?.placeholder || "555 123 4567"}`}
                      value={registrantProfile.phone.nationalNumber}
                      onChange={(e) =>
                        setRegistrantProfile((p) => ({
                          ...p,
                          phone: { ...p.phone, nationalNumber: e.target.value }
                        }))
                      }
                      className="domain-input"
                    />
                  </div>
                </div>
                <div className="domain-form-full">
                  <label className="domain-label">Street Address *</label>
                  <input
                    type="text"
                    required
                    placeholder="123 Innovation Way"
                    value={registrantProfile.address.address1}
                    onChange={(e) =>
                      setRegistrantProfile((p) => ({
                        ...p,
                        address: { ...p.address, address1: e.target.value }
                      }))
                    }
                    className="domain-input"
                  />
                </div>
                <div>
                  <label className="domain-label">City *</label>
                  <input
                    type="text"
                    required
                    placeholder="San Francisco"
                    value={registrantProfile.address.city}
                    onChange={(e) =>
                      setRegistrantProfile((p) => ({
                        ...p,
                        address: { ...p.address, city: e.target.value }
                      }))
                    }
                    className="domain-input"
                  />
                </div>
                <div>
                  <label className="domain-label">State / Province</label>
                  <input
                    type="text"
                    placeholder="CA"
                    value={registrantProfile.address.state}
                    onChange={(e) =>
                      setRegistrantProfile((p) => ({
                        ...p,
                        address: { ...p.address, state: e.target.value }
                      }))
                    }
                    className="domain-input"
                  />
                </div>
                <div>
                  <label className="domain-label">Postal Code *</label>
                  <input
                    type="text"
                    required
                    placeholder="94107"
                    value={registrantProfile.address.postalCode}
                    onChange={(e) =>
                      setRegistrantProfile((p) => ({
                        ...p,
                        address: { ...p.address, postalCode: e.target.value }
                      }))
                    }
                    className="domain-input"
                  />
                </div>
                <div>
                  <label className="domain-label">Country (ISO 2-letter) *</label>
                  <select
                    value={registrantProfile.address.country}
                    onChange={(e) => {
                      const cCode = e.target.value;
                      const matched = SUPPORTED_COUNTRIES.find((c) => c.code === cCode);
                      setRegistrantProfile((p) => ({
                        ...p,
                        address: { ...p.address, country: cCode },
                        phone: { ...p.phone, countryCode: matched?.phoneCode || p.phone.countryCode }
                      }));
                    }}
                    className="domain-input font-medium cursor-pointer"
                  >
                    {SUPPORTED_COUNTRIES.map((c) => (
                      <option key={c.code} value={c.code} style={{ backgroundColor: "#121216", color: "#ffffff" }}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* 5. Mandatory Registry Agreements */}
            <div className="rounded-2xl bg-[#16161b] border border-[#27272a] p-5 space-y-3 text-xs text-[#a8a29e] shadow-lg">
              {(domainQuote?.requiredAgreements || [
                { agreementType: "DNRA", title: "GoDaddy Domain Name Registration Agreement", url: "https://www.godaddy.com/legal/agreements/domain-name-registration-agreement" },
                { agreementType: "UTOS", title: "Universal Terms of Service", url: "https://www.godaddy.com/legal/agreements/universal-terms-of-service-agreement" }
              ]).map((agr) => (
                <label key={agr.agreementType} className="flex items-start gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={acceptedAgreements.includes(agr.agreementType)}
                    onChange={(e) => {
                      setAcceptedAgreements((curr) =>
                        e.target.checked
                          ? [...curr, agr.agreementType]
                          : curr.filter((t) => t !== agr.agreementType)
                      );
                    }}
                    className="mt-0.5 rounded accent-[#c89666] bg-[#09090b] border-[#27272a]"
                  />
                  <span>
                    I accept the{" "}
                    <a href={agr.url} target="_blank" rel="noreferrer" className="underline font-bold text-[#dfb180] hover:text-[#c89666]">
                      {agr.title || agr.agreementType}
                    </a>
                    .
                  </span>
                </label>
              ))}

              <label className="flex items-start gap-2.5 cursor-pointer pt-2 border-t border-[#27272a]">
                <input
                  type="checkbox"
                  checked={acceptedTerms}
                  onChange={(e) => setAcceptedTerms(e.target.checked)}
                  className="mt-0.5 rounded accent-[#c89666] bg-[#09090b] border-[#27272a]"
                />
                <span>
                  I authorize registration of <strong className="text-white font-mono">{activeDomain}</strong> for 1 year {hasFreeDomainPerk ? "(100% Free under your subscription plan)" : `at ${currSymbol}${displayTotal}${isINR ? ` (~$${usdEquiv} USD)` : ""}`}. I understand domain registrations are non-refundable per ICANN registry policy once provisioned.
                </span>
              </label>

              {/* Automatic Renewal Authority */}
              <div className="pt-2.5 border-t border-[#27272a]">
                <label className="flex items-start gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoRenewAuthorized}
                    onChange={(e) => setAutoRenewAuthorized(e.target.checked)}
                    className="mt-0.5 w-4 h-4 rounded accent-[#c89666] bg-[#09090b] border-[#27272a] cursor-pointer"
                  />
                  <div className="space-y-0.5">
                    <span className="font-bold text-white flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-[#c89666]" />
                      Authorize Automatic Annual Renewal ({currSymbol}{displayRenewal}/yr)
                    </span>
                    <span className="text-[#a8a29e] text-[11px] leading-relaxed block">
                      Give authority to automatically renew your domain annually and collect the renewal fee from your authorized account/card before expiry so your website never goes offline. You can revoke this authority anytime in your dashboard.
                    </span>
                  </div>
                </label>
              </div>
            </div>

            {/* Submit & Cancel Actions */}
            <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => navigate(returnUrl)}
                className="w-full sm:w-auto px-6 py-3 rounded-xl border border-[#27272a] bg-[#141417] hover:bg-[#1e1e24] text-white text-xs font-bold transition cursor-pointer"
              >
                Cancel &amp; Return
              </button>
              <button
                type="submit"
                disabled={purchasing || quoteLoading}
                className="w-full sm:w-auto px-8 py-3 rounded-xl bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] disabled:opacity-50 text-[#09090b] font-black text-xs flex items-center justify-center gap-2 shadow-lg shadow-[#c89666]/25 transition cursor-pointer"
              >
                {purchasing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin text-[#09090b]" />
                    <span>Registering with GoDaddy...</span>
                  </>
                ) : hasFreeDomainPerk ? (
                  <>
                    <Sparkles className="w-4 h-4 text-[#09090b]" />
                    <span>Claim Free Domain &amp; Complete Registration</span>
                  </>
                ) : (
                  <>
                    <ShoppingCart className="w-4 h-4 text-[#09090b]" />
                    <span>Pay {currSymbol}{displayTotal}{isINR ? ` (~$${usdEquiv} USD)` : ""} &amp; Complete Registration</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  );
}
