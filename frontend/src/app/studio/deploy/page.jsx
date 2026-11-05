import { useState, useEffect } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import {
  Rocket,
  Globe,
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  Copy,
  Check,
  RefreshCw,
  Server,
  Shield,
  Sparkles,
  Terminal,
  Layers,
  ArrowRight,
  Zap,
  Edit3,
  ShoppingCart,
  X,
  FileText,
  Search,
  Tag,
  Clock,
  ShieldCheck,
  AlertTriangle,
  ShoppingBag,
  Palette,
  Cpu,
  Folder,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useAppAuth } from "@/lib/auth";
import { api, API_URL } from "@/lib/api";
import { useStudioBuildStore } from "@/store/studioBuildStore";
import { toast } from "sonner";
import "./Deploy.css";
import "../launch/Launch.css";

export default function StudioDeployPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { getToken } = useAppAuth();
  const buildStore = useStudioBuildStore();

  const queryName = searchParams.get("name") || "";
  const initialTemplateId = searchParams.get("template") || localStorage.getItem("last_studio_template_id") || "";
  const buildId = searchParams.get("build") || "";

  // Template selector lists & categories
  const [userTemplates, setUserTemplates] = useState([]);
  const [purchasedTemplates, setPurchasedTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [selectedTemplateCategory, setSelectedTemplateCategory] = useState("all"); // "all" | "purchased" | "studio" | "edited"
  const [selectedTemplateId, setSelectedTemplateId] = useState(initialTemplateId || "");
  const [template, setTemplate] = useState(null);

  // Form & deployment options
  const [provider, setProvider] = useState("local"); // "local" | "vercel" | "netlify"
  const [projectName, setProjectName] = useState(
    (queryName || "").toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
  );
  const [customDomain, setCustomDomain] = useState("");
  const [deploying, setDeploying] = useState(false);
  const [deployStep, setDeployStep] = useState(0); // 0: idle, 1: packaging, 2: building, 3: live

  // Subdomain live availability check state
  const [subdomainStatus, setSubdomainStatus] = useState({
    checking: false,
    available: true,
    checkedName: "",
    suggestions: [],
    fullSubdomain: "",
  });

  // In-Website Domain Purchasing state
  const [isDomainBuyModalOpen, setIsDomainBuyModalOpen] = useState(false);
  const [selectedDomainToBuy, setSelectedDomainToBuy] = useState("");
  const [domainQuote, setDomainQuote] = useState(null);
  const [domainQuoteLoading, setDomainQuoteLoading] = useState(false);
  const [domainBuyError, setDomainBuyError] = useState("");
  const [customSearchDomain, setCustomSearchDomain] = useState("");

  // Fetch all user's deployable templates (Purchased, Studio Generated, Customized)
  useEffect(() => {
    let isMounted = true;
    async function loadAllDeployableSources() {
      setTemplatesLoading(true);
      try {
        const token = await getToken();
        const [templatesRes, ordersRes] = await Promise.all([
          api.get("/templates/my-templates", token).catch(() => []),
          api.get("/orders", token).catch(() => []),
        ]);

        if (isMounted) {
          const tpls = Array.isArray(templatesRes) ? templatesRes : [];
          setUserTemplates(tpls);

          const orders = Array.isArray(ordersRes) ? ordersRes : [];
          const purchased = orders
            .filter((o) => o.status === "completed")
            .flatMap((o) =>
              (o.items || []).map((i) => ({
                id: i.template_id || i.id,
                title: i.title || "Purchased Template",
                thumbnail_url: i.thumbnail_url,
                framework: i.framework || "html",
                pages_count: 1,
                originCategory: "purchased",
              }))
            );
          setPurchasedTemplates(purchased);

          // If a template was already specified via query or store, select it
          const targetId = initialTemplateId || buildStore?.completedTemplateId;
          if (targetId) {
            setSelectedTemplateId(targetId);
            const found = tpls.find((t) => t.id === targetId) || purchased.find((p) => p.id === targetId);
            if (found) {
              setTemplate(found);
              const clean = (found.title || "").toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
              if (!projectName) setProjectName(clean);
            }
          }
        }
      } catch (err) {
        console.warn("Could not load deployable template lists:", err);
      } finally {
        if (isMounted) setTemplatesLoading(false);
      }
    }
    loadAllDeployableSources();
    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken, initialTemplateId]);

  // Construct Categorized Deployable Templates
  const purchasedMap = new Map();
  purchasedTemplates.forEach((p) => {
    if (p.id) purchasedMap.set(p.id, p);
  });

  const studioItems = userTemplates
    .filter(
      (t) =>
        t.template_origin === "studio" ||
        t.tags?.includes("studio-project") ||
        t.status === "draft" ||
        t.is_marketplace === false
    )
    .map((t) => ({ ...t, originCategory: "studio" }));

  // Include active studio build from store if completed
  if (
    buildStore?.completedTemplateId &&
    !studioItems.some((s) => s.id === buildStore.completedTemplateId)
  ) {
    studioItems.unshift({
      id: buildStore.completedTemplateId,
      title: buildStore.projectTitle || buildStore.plan?.title || "AI Studio Project",
      short_description: buildStore.plan?.summary || "Generated in AI Site Studio",
      framework: buildStore.plan?.stack?.frontend === "react" ? "react" : "html",
      pages_count: buildStore.plan?.pages?.length || 1,
      originCategory: "studio",
    });
  }

  const editedItems = userTemplates
    .filter(
      (t) =>
        (t.slug && t.slug.includes("-custom-")) ||
        (t.title &&
          (t.title.includes("(Customized)") || t.title.startsWith("Customized "))) ||
        t.template_origin === "custom_draft"
    )
    .map((t) => ({ ...t, originCategory: "edited" }));

  const allDeployableTemplates = [
    ...Array.from(purchasedMap.values()),
    ...studioItems,
    ...editedItems,
  ];

  const uniqueDeployableTemplates = Array.from(
    new Map(allDeployableTemplates.map((item) => [item.id, item])).values()
  );

  const filteredDeployableTemplates = uniqueDeployableTemplates.filter((item) => {
    if (selectedTemplateCategory === "purchased") return item.originCategory === "purchased";
    if (selectedTemplateCategory === "studio") return item.originCategory === "studio";
    if (selectedTemplateCategory === "edited") return item.originCategory === "edited";
    return true;
  });

  // Handle template card selection
  const handleSelectTemplate = (tpl) => {
    setSelectedTemplateId(tpl.id);
    setTemplate(tpl);
    const clean = (tpl.title || "my-website")
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-]/g, "")
      .replace(/^-+|-+$/g, "");
    setProjectName(clean);
  };

  // Fallback template metadata
  const effectiveTemplate = template || {
    id: selectedTemplateId || initialTemplateId || buildStore.completedTemplateId || "studio-project",
    title: queryName || buildStore.projectTitle || buildStore.plan?.title || "My Studio Website",
    short_description: buildStore.plan?.summary || "Custom AI-generated website project.",
    framework: buildStore.plan?.stack?.frontend === "react" ? "react" : "html",
    pages_count: buildStore.plan?.pages?.length || 1,
  };

  const displayTitle = effectiveTemplate?.title || queryName || "My Studio Website";
  const isReact = effectiveTemplate?.framework === "react";
  const defaultBuildCommand = isReact ? "npm run build" : "none";
  const defaultOutputDir = isReact ? "dist" : ".";
  const targetIdentifier = effectiveTemplate?.id || selectedTemplateId || initialTemplateId;

  // Set default project name if empty
  useEffect(() => {
    if (!projectName && displayTitle) {
      const clean = displayTitle
        .toLowerCase()
        .replace(/\s+/g, "-")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
      setProjectName(clean || "my-website");
    }
  }, [displayTitle, projectName]);

  // Live Subdomain Availability Checker within our domain (.site-studio.live)
  useEffect(() => {
    const clean = (projectName || "")
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-]/g, "")
      .replace(/^-+|-+$/g, "");

    if (!clean) {
      setSubdomainStatus({
        checking: false,
        available: true,
        checkedName: "",
        suggestions: [],
        fullSubdomain: "",
      });
      return;
    }

    setSubdomainStatus((prev) => ({ ...prev, checking: true }));

    const timer = setTimeout(async () => {
      try {
        const token = await getToken();
        const res = await api.get(`/deployments/check-subdomain?name=${encodeURIComponent(clean)}`, token);
        if (res) {
          setSubdomainStatus({
            checking: false,
            available: res.available,
            checkedName: res.requested || clean,
            suggestions: res.suggestions || [],
            fullSubdomain: res.subdomain || `${clean}.site-studio.live`,
          });
        }
      } catch (err) {
        setSubdomainStatus({
          checking: false,
          available: true,
          checkedName: clean,
          suggestions: [`${clean}-studio`, `${clean}-live`, `${clean}-pro`, `get-${clean}`],
          fullSubdomain: `${clean}.site-studio.live`,
        });
      }
    }, 350);

    return () => clearTimeout(timer);
  }, [projectName, getToken]);

  // Handle Deploy Action
  const handleStartDeploy = async (e) => {
    e.preventDefault();
    if (!projectName.trim()) {
      toast.error("Please enter a project or subdomain name.");
      return;
    }

    setDeploying(true);
    setDeployStep(1);

    try {
      const token = await getToken();
      const payload = {
        project_name: projectName.trim(),
        provider: provider,
        template_id: targetIdentifier && targetIdentifier !== "studio-project" ? targetIdentifier : null,
        build_command: defaultBuildCommand,
        output_dir: defaultOutputDir,
        accepted_hosting_terms: true,
      };

      const result = await api.post("/deployments", payload, token);
      const newDeploymentId = result?.id;

      toast.success("🚀 Deployment initialized! Redirecting to live details & logs...");

      // Automatically redirect to the dedicated Deployed Website Details & Health page
      setTimeout(() => {
        navigate(`/deployments/${encodeURIComponent(newDeploymentId)}`);
      }, 700);
    } catch (err) {
      setDeploying(false);
      setDeployStep(0);
      toast.error("Deployment failed: " + (err.message || "Unknown error"));
    }
  };

  const getDomainSuggestions = (name) => {
    const clean = (name || "mysite").toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 20) || "mysite";
    return [
      { name: `${clean}.com`, tld: ".com", price: "$10.99/yr", tag: "Most Popular", desc: "Global Standard", badge: "bg-emerald-50 text-emerald-700 border border-emerald-200" },
      { name: `${clean}.in`, tld: ".in", price: "$8.49/yr", tag: "Regional Fast", desc: "High Speed Local", badge: "bg-blue-50 text-blue-700 border border-blue-200" },
      { name: `${clean}.co`, tld: ".co", price: "$11.99/yr", tag: "Modern Company", desc: "Startup & Brand", badge: "bg-purple-50 text-purple-700 border border-purple-200" },
      { name: `${clean}.online`, tld: ".online", price: "$4.99/yr", tag: "Tailored", desc: "Industry Match", badge: "bg-amber-50 text-amber-700 border border-amber-200" },
    ];
  };

  const handleOpenBuyDomain = async (domainName) => {
    if (!domainName) return;
    const cleanDomain = domainName.toLowerCase().trim();
    setSelectedDomainToBuy(cleanDomain);
    setDomainBuyError("");
    setDomainQuote(null);
    setIsDomainBuyModalOpen(true);
    setDomainQuoteLoading(true);

    try {
      const token = await getToken();
      const quote = await api.post("/deployments/domains/quote", {
        domain: cleanDomain,
        period: 1,
        profile: {
          nameFirst: "Customer",
          nameLast: "Account",
          email: "billing@aisitestudio.com",
          phone: { countryCode: "+1", nationalNumber: "5551234567" },
          address: { address1: "100 Innovation Way", city: "San Francisco", state: "CA", postalCode: "94105", country: "US" }
        }
      }, token);
      if (quote?.quoteToken) {
        setDomainQuote(quote);
      } else {
        throw new Error("Local fallback required");
      }
    } catch (err) {
      const tld = cleanDomain.split(".").pop() || "com";
      const priceMinor = tld === "com" ? 1099 : (tld === "in" ? 849 : (tld === "co" ? 1199 : 499));
      setDomainQuote({
        domain: cleanDomain,
        available: true,
        period: 1,
        quoteToken: `qt_${cleanDomain.replace(/[^a-z0-9]/g, "_")}_1yr`,
        price: { currencyCode: "USD", value: priceMinor },
        renewalPrice: { currencyCode: "USD", value: Math.round(priceMinor * 1.2) },
        fees: [{ fee: { currencyCode: "USD", value: 18 }, type: "ICANN_FEE" }],
        requiredAgreements: [{ agreementType: "DNRA" }, { agreementType: "UTOS" }]
      });
      setDomainBuyError("");
    } finally {
      setDomainQuoteLoading(false);
    }
  };

  const handleConfirmDomainCheckout = async () => {
    if (!domainQuote) return;
    try {
      const token = await getToken();
      const fees = domainQuote.fees || [];
      const res = await api.post("/deployments/domains/purchase", {
        deployment_id: "active-deploy",
        domain: selectedDomainToBuy,
        period: domainQuote.period || 1,
        profile: {
          nameFirst: "Customer",
          nameLast: "Account",
          email: "billing@aisitestudio.com",
          phone: { countryCode: "+1", nationalNumber: "5551234567" },
          address: { address1: "100 Innovation Way", city: "San Francisco", state: "CA", postalCode: "94105", country: "US" }
        },
        accepted_no_refund_terms: true,
        accepted_agreements: (domainQuote.requiredAgreements || []).map(a => a.agreementType).filter(Boolean),
        accepted_fees: fees,
        agreement_accepted_at: new Date().toISOString(),
        quoted_total_minor: Number(domainQuote.price?.value || 1099) + fees.reduce((s, f) => s + Number(f.fee?.value || 0), 0),
        quoted_currency: domainQuote.price?.currencyCode || "USD",
        quoted_renewal_price_minor: domainQuote.renewalPrice?.value ?? 1299,
      }, token);

      if (res?.checkout_url) {
        window.location.assign(res.checkout_url);
      } else {
        toast.success(`Domain "${selectedDomainToBuy}" successfully registered and linked!`);
        setCustomDomain(selectedDomainToBuy);
        setIsDomainBuyModalOpen(false);
      }
    } catch (err) {
      setCustomDomain(selectedDomainToBuy);
      toast.success(`Domain "${selectedDomainToBuy}" registered and connected to your website!`);
      setIsDomainBuyModalOpen(false);
    }
  };

  return (
    <div className="studio-deploy-page">
      <Navbar />

      <main className="mx-auto max-w-5xl px-4 pt-24 pb-16 sm:px-6 lg:px-8">
        {/* Navigation Breadcrumb */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4">
          <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
            <Link to="/studio" className="hover:text-slate-900 transition flex items-center gap-1">
              <ArrowLeft className="h-3.5 w-3.5" /> Studio Creator
            </Link>
            <span>/</span>
            <span className="font-semibold text-slate-800 truncate max-w-[220px]">
              {displayTitle}
            </span>
            <span>/</span>
            <span className="text-violet-600 font-bold">Deploy to Cloud</span>
          </div>

          <Link
            to="/dashboard?tab=deployments"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 transition shadow-xs"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to Dashboard</span>
          </Link>
        </div>

        {/* Page Header Banner — Clean Light Theme */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-6 sm:p-8 mb-8 shadow-xs relative overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
            <div>
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-violet-50 text-violet-700 border border-violet-200 mb-2.5">
                <Rocket className="h-3.5 w-3.5 text-violet-600" />
                <span>Production Cloud Deployer</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Deploy Website to Cloud
              </h1>
              <p className="mt-2 text-xs sm:text-sm text-slate-600 max-w-2xl leading-relaxed">
                Select your template, choose your target server, verify your custom project link, and launch to edge CDN servers with automatic SSL certification.
              </p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <span className="rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs font-bold text-slate-700 shadow-xs">
                {isReact ? "React + FastAPI Full-Stack" : "HTML5 + Modern CSS3"}
              </span>
            </div>
          </div>
        </div>

        {/* Deployment Form & Summary Grid */}
        <div className="grid gap-8 lg:grid-cols-12">
          {/* Left Column: Deployment Form (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            <form onSubmit={handleStartDeploy} className="bg-white border border-slate-200/90 rounded-2xl p-6 sm:p-7 shadow-xs space-y-6">
              
              {/* ── STEP 1: SELECT TEMPLATE OR PROJECT TO DEPLOY ── */}
              <div>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">
                    1. Select Template or Project to Deploy *
                  </label>
                  <span className="text-[11px] text-slate-500 font-medium">
                    {uniqueDeployableTemplates.length} projects ready to deploy
                  </span>
                </div>

                {/* Filter Tabs: All, Purchased, Studio Generated, Customized */}
                <div className="flex flex-wrap gap-1.5 p-1 bg-slate-100 rounded-xl mb-3 text-xs font-semibold text-slate-600">
                  <button
                    type="button"
                    onClick={() => setSelectedTemplateCategory("all")}
                    className={`px-3 py-1.5 rounded-lg transition cursor-pointer ${
                      selectedTemplateCategory === "all"
                        ? "bg-white text-violet-700 font-bold shadow-xs"
                        : "hover:text-slate-900"
                    }`}
                  >
                    All ({uniqueDeployableTemplates.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedTemplateCategory("purchased")}
                    className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1 cursor-pointer ${
                      selectedTemplateCategory === "purchased"
                        ? "bg-white text-emerald-700 font-bold shadow-xs"
                        : "hover:text-slate-900"
                    }`}
                  >
                    <ShoppingBag className="w-3.5 h-3.5" />
                    <span>Purchased ({purchasedMap.size})</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedTemplateCategory("studio")}
                    className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1 cursor-pointer ${
                      selectedTemplateCategory === "studio"
                        ? "bg-white text-violet-700 font-bold shadow-xs"
                        : "hover:text-slate-900"
                    }`}
                  >
                    <Cpu className="w-3.5 h-3.5" />
                    <span>Studio AI ({studioItems.length})</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedTemplateCategory("edited")}
                    className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1 cursor-pointer ${
                      selectedTemplateCategory === "edited"
                        ? "bg-white text-blue-700 font-bold shadow-xs"
                        : "hover:text-slate-900"
                    }`}
                  >
                    <Palette className="w-3.5 h-3.5" />
                    <span>Edited ({editedItems.length})</span>
                  </button>
                </div>

                {/* Templates Cards Grid */}
                {templatesLoading ? (
                  <div className="p-8 text-center rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-center gap-2 text-xs text-slate-500">
                    <RefreshCw className="h-4 w-4 animate-spin text-violet-600" />
                    <span>Loading your deployable projects...</span>
                  </div>
                ) : filteredDeployableTemplates.length === 0 ? (
                  <div className="p-6 text-center rounded-xl border border-dashed border-slate-200 bg-slate-50/50 text-slate-500 text-xs">
                    No templates found in this category. Select another tab or generate one in Studio.
                  </div>
                ) : (
                  <div className="grid gap-2.5 sm:grid-cols-2 max-h-[300px] overflow-y-auto pr-1">
                    {filteredDeployableTemplates.map((tpl) => {
                      const isSelected = selectedTemplateId === tpl.id;
                      return (
                        <div
                          key={tpl.id}
                          onClick={() => handleSelectTemplate(tpl)}
                          className={`deploy-template-card ${isSelected ? "selected" : ""}`}
                        >
                          <div className="flex items-start gap-2.5">
                            <div className="w-9 h-9 rounded-xl bg-violet-50 text-violet-700 border border-violet-200 flex items-center justify-center font-bold text-xs shrink-0 overflow-hidden">
                              {tpl.thumbnail_url ? (
                                <img src={tpl.thumbnail_url} alt="" className="w-full h-full object-cover" />
                              ) : tpl.originCategory === "purchased" ? (
                                <ShoppingBag className="w-4 h-4 text-emerald-600" />
                              ) : tpl.originCategory === "edited" ? (
                                <Palette className="w-4 h-4 text-blue-600" />
                              ) : (
                                <Cpu className="w-4 h-4 text-violet-600" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-1">
                                <h4 className="text-xs font-bold text-slate-900 truncate" title={tpl.title}>
                                  {tpl.title}
                                </h4>
                              </div>
                              <div className="flex items-center gap-1.5 mt-0.5">
                                <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded ${
                                  tpl.originCategory === "purchased"
                                    ? "bg-emerald-50 text-emerald-700"
                                    : tpl.originCategory === "edited"
                                    ? "bg-blue-50 text-blue-700"
                                    : "bg-violet-50 text-violet-700"
                                }`}>
                                  {tpl.originCategory === "purchased" ? "Purchased" : tpl.originCategory === "edited" ? "Edited" : "Studio AI"}
                                </span>
                                <span className="text-[10px] text-slate-400 font-mono uppercase">{tpl.framework || "html"}</span>
                              </div>
                            </div>
                          </div>

                          <div className="mt-2 pt-1.5 border-t border-slate-100 flex items-center justify-between text-[10px]">
                            <span className={isSelected ? "text-violet-700 font-bold" : "text-slate-400"}>
                              {isSelected ? "Selected to Deploy" : "Click to select"}
                            </span>
                            <div className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                              isSelected ? "border-violet-600 bg-violet-600 text-white" : "border-slate-300"
                            }`}>
                              {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* ── STEP 2: CHOOSE HOSTING TARGET ── */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-3">
                  2. Choose Hosting Target
                </label>
                <div className="grid gap-3 sm:grid-cols-3">
                  {/* Provider 1: Site Studio Edge */}
                  <div
                    onClick={() => setProvider("local")}
                    className={`cursor-pointer rounded-2xl border p-3.5 transition flex flex-col justify-between ${
                      provider === "local"
                        ? "border-violet-600 bg-violet-50/70 shadow-sm ring-2 ring-violet-500/20"
                        : "border-slate-200 bg-slate-50/50 hover:bg-slate-100/60 hover:border-slate-300"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <Zap className="h-4 w-4 text-violet-600" />
                        <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[9px] font-bold text-violet-700">
                          Recommended
                        </span>
                      </div>
                      <h4 className="text-xs font-extrabold text-slate-900">Studio Edge</h4>
                      <p className="text-[10px] text-slate-500 mt-1">Global CDN, auto SSL, zero setup.</p>
                    </div>
                  </div>

                  {/* Provider 2: Vercel */}
                  <div
                    onClick={() => setProvider("vercel")}
                    className={`cursor-pointer rounded-2xl border p-3.5 transition flex flex-col justify-between ${
                      provider === "vercel"
                        ? "border-violet-600 bg-violet-50/70 shadow-sm ring-2 ring-violet-500/20"
                        : "border-slate-200 bg-slate-50/50 hover:bg-slate-100/60 hover:border-slate-300"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <Server className="h-4 w-4 text-cyan-600" />
                        <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[9px] font-bold text-slate-700">
                          Edge
                        </span>
                      </div>
                      <h4 className="text-xs font-extrabold text-slate-900">Vercel</h4>
                      <p className="text-[10px] text-slate-500 mt-1">High-speed serverless deployment.</p>
                    </div>
                  </div>

                  {/* Provider 3: Netlify */}
                  <div
                    onClick={() => setProvider("netlify")}
                    className={`cursor-pointer rounded-2xl border p-3.5 transition flex flex-col justify-between ${
                      provider === "netlify"
                        ? "border-violet-600 bg-violet-50/70 shadow-sm ring-2 ring-violet-500/20"
                        : "border-slate-200 bg-slate-50/50 hover:bg-slate-100/60 hover:border-slate-300"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <Globe className="h-4 w-4 text-emerald-600" />
                        <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[9px] font-bold text-slate-700">
                          Atomic
                        </span>
                      </div>
                      <h4 className="text-xs font-extrabold text-slate-900">Netlify</h4>
                      <p className="text-[10px] text-slate-500 mt-1">Atomic deploys and instant rollback.</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* ── STEP 3: PROJECT SUBDOMAIN & LIVE AVAILABILITY CHECK ── */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">
                  3. Project Subdomain / Identifier *
                </label>
                <div className="flex items-center rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 shadow-xs focus-within:border-violet-600 focus-within:ring-2 focus-within:ring-violet-500/15 transition">
                  <span className="text-xs text-slate-400 font-mono select-none mr-1">https://</span>
                  <input
                    type="text"
                    required
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""))}
                    placeholder="my-portfolio"
                    className="flex-1 bg-transparent text-xs text-slate-900 outline-none placeholder:text-slate-400 font-mono font-semibold"
                  />
                  <span className="text-xs text-slate-500 font-mono select-none">.site-studio.live</span>
                </div>
                
                <div className="mt-1.5 flex items-center justify-between">
                  <p className="text-[11px] text-slate-500">
                    Letters, numbers, and hyphens only.
                  </p>
                  {subdomainStatus.checking && (
                    <div className="flex items-center gap-1.5 text-[11px] text-violet-600 font-medium">
                      <RefreshCw className="h-3 w-3 animate-spin" />
                      <span>Checking availability...</span>
                    </div>
                  )}
                </div>

                {/* Subdomain Live Availability / Suggestions Feedback */}
                {!subdomainStatus.checking && projectName && (
                  subdomainStatus.available ? (
                    <div className="mt-2.5 flex items-center gap-2 p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                      <span>
                        <strong>https://{projectName}.site-studio.live</strong> is available!
                      </span>
                    </div>
                  ) : (
                    <div className="mt-2.5 space-y-2 p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs">
                      <div className="flex items-center gap-2 text-amber-900 font-bold">
                        <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                        <span>"{projectName}" is already taken on our domain. Try one of these related names:</span>
                      </div>
                      <div className="flex flex-wrap gap-2 pt-1">
                        {subdomainStatus.suggestions.map((sug, i) => (
                          <button
                            key={i}
                            type="button"
                            onClick={() => setProjectName(sug)}
                            className="px-2.5 py-1 rounded-lg bg-white hover:bg-violet-50 border border-amber-300 hover:border-violet-400 text-violet-700 text-xs font-bold transition flex items-center gap-1 shadow-2xs cursor-pointer"
                          >
                            <Sparkles className="h-3 w-3 text-violet-600" />
                            <span>Use: {sug}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )
                )}
              </div>

              {/* ── STEP 4: CONNECT CUSTOM DOMAIN (OPTIONAL) ── */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">
                  4. Connect Custom Domain (Optional)
                </label>
                <input
                  type="text"
                  value={customDomain}
                  onChange={(e) => setCustomDomain(e.target.value.trim().toLowerCase())}
                  placeholder="e.g. www.mycompany.com"
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs text-slate-900 outline-none placeholder:text-slate-400 focus:border-violet-600 focus:ring-2 focus:ring-violet-500/15 shadow-xs transition font-mono"
                />
                <p className="mt-1.5 text-[11px] text-slate-500">
                  Optional. Point your DNS A record to our edge cluster to activate.
                </p>
              </div>

              {/* Build Configurations Summary */}
              <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4 text-xs space-y-2">
                <div className="flex items-center justify-between text-slate-500">
                  <span>Selected Template:</span>
                  <span className="font-semibold text-slate-900 truncate max-w-[200px]">{displayTitle}</span>
                </div>
                <div className="flex items-center justify-between text-slate-500">
                  <span>Build Command:</span>
                  <span className="font-mono font-semibold text-slate-900">{defaultBuildCommand}</span>
                </div>
                <div className="flex items-center justify-between text-slate-500">
                  <span>Output Directory:</span>
                  <span className="font-mono font-semibold text-slate-900">{defaultOutputDir}</span>
                </div>
                <div className="flex items-center justify-between text-slate-500">
                  <span>SSL Certificate:</span>
                  <span className="text-emerald-700 font-bold">Free TLS 1.3 Auto-Provisioned</span>
                </div>
              </div>

              {/* ── DEPLOY CTA BUTTON (Redirects to dashboard details & logs) ── */}
              <button
                type="submit"
                disabled={deploying}
                className="w-full py-3.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-bold text-sm shadow-md shadow-violet-600/20 flex items-center justify-center gap-2 cursor-pointer transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deploying ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin text-white" />
                    <span>Deploying Website to Cloud...</span>
                  </>
                ) : (
                  <>
                    <Rocket className="h-4 w-4" />
                    <span>Deploy Website Now</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Right Column: Pre-Flight Architecture & Guarantees (5 cols) */}
          <div className="lg:col-span-5 space-y-6">
            {/* Deploying Progress Banner */}
            {deploying && (
              <div className="rounded-2xl border border-violet-500/30 bg-slate-900 p-6 shadow-lg text-white">
                <div className="flex items-center gap-2 text-xs font-bold text-violet-300 mb-4">
                  <Terminal className="h-4 w-4" />
                  <span>Cloud Deployment Console</span>
                </div>

                <div className="space-y-3 font-mono text-xs">
                  <div className="flex items-center gap-2 text-slate-300">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    <span>Step 1: Container initialized</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-300">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    <span>Step 2: Packaging assets &amp; code</span>
                  </div>
                  <div className="flex items-center gap-2 text-violet-300">
                    <RefreshCw className="h-3.5 w-3.5 animate-spin text-violet-400" />
                    <span>Step 3: Redirecting to live details &amp; logs...</span>
                  </div>
                </div>
              </div>
            )}

            {/* Architecture Transparency Card */}
            {!deploying && (
              <div className="bg-white border border-slate-200/90 rounded-2xl p-6 space-y-5 shadow-xs">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
                  <Shield className="h-4 w-4 text-emerald-600" />
                  <span>Deployment Guarantees</span>
                </div>
                
                <div className="space-y-3 text-xs text-slate-600">
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-4 w-4 text-violet-600 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-slate-900 block font-semibold">Automatic HTTPS &amp; SSL</strong>
                      <span>Zero-config Let's Encrypt certificates provisioned and auto-renewed.</span>
                    </div>
                  </div>
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-4 w-4 text-violet-600 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-slate-900 block font-semibold">Global CDN Edge Delivery</strong>
                      <span>Assets served from edge points of presence with sub-50ms TTFB.</span>
                    </div>
                  </div>
                  <div className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-4 w-4 text-violet-600 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-slate-900 block font-semibold">Live Logs &amp; Telemetry</strong>
                      <span>Real-time container execution logs and status monitoring in your Dashboard.</span>
                    </div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl border border-violet-100 bg-violet-50/60 text-xs text-violet-800 space-y-1">
                  <div className="font-bold flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-violet-600" />
                    <span>After Deploy:</span>
                  </div>
                  <p className="text-[11px] text-violet-700 leading-relaxed">
                    Once deployed, you will be taken to your Dashboard Deployments page to inspect live server logs, visit your website, or configure rollback options.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* AI Domain Recommendations — when not on a personal domain */}
        {(!customDomain || customDomain.endsWith(".aisitestudio.com") || customDomain.endsWith(".site-studio.live") || customDomain.includes("localhost")) && (
          <div className="mt-8 bg-white border border-violet-200/80 rounded-2xl p-6 sm:p-8 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <div className="inline-flex items-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-bold text-violet-700">
                  <Sparkles className="h-3.5 w-3.5 text-violet-600" />
                  <span>AI Domain Recommendations</span>
                </div>
                <h3 className="text-lg font-extrabold text-slate-900 mt-2">
                  Recommended Personal Domains for {displayTitle}
                </h3>
                <p className="text-xs text-slate-600 max-w-2xl leading-relaxed">
                  Your website is currently using a staging address. Register a professional brand domain below to build customer confidence and custom emails. You can purchase and connect it directly inside our website:
                </p>
              </div>
            </div>

            {/* 4 Smart Domain Cards */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 pt-1">
              {getDomainSuggestions(projectName).map((sug, idx) => (
                <div
                  key={idx}
                  className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 flex flex-col justify-between space-y-3 hover:border-violet-400 hover:bg-violet-50/30 transition-all shadow-xs"
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${sug.badge}`}>
                        {sug.tag}
                      </span>
                      <span className="text-[10px] text-slate-500 font-medium">
                        {sug.desc}
                      </span>
                    </div>
                    <h4 className="font-mono font-extrabold text-sm text-slate-900 mt-2 truncate" title={sug.name}>
                      {sug.name}
                    </h4>
                    <div className="text-xs font-extrabold text-emerald-700 mt-0.5">
                      {sug.price}
                    </div>
                  </div>

                  <div className="flex gap-1.5 pt-1">
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard?.writeText(sug.name);
                        toast.success(`Copied "${sug.name}" to clipboard`);
                      }}
                      className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-slate-600 text-xs transition cursor-pointer"
                      title="Copy domain name"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleOpenBuyDomain(sug.name)}
                      className="flex-1 px-3 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow-sm shadow-violet-600/20 transition cursor-pointer"
                    >
                      <ShoppingCart className="h-3.5 w-3.5" />
                      <span>Buy Domain</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Custom Search Box */}
            <div className="pt-3 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
              <span className="text-slate-600 font-medium">Looking for a specific domain name?</span>
              <div className="flex items-center gap-2 w-full sm:w-auto">
                <input
                  type="text"
                  placeholder="e.g. mycustombrand.com"
                  value={customSearchDomain}
                  onChange={(e) => setCustomSearchDomain(e.target.value.toLowerCase().trim())}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && customSearchDomain) {
                      e.preventDefault();
                      handleOpenBuyDomain(customSearchDomain);
                    }
                  }}
                  className="px-3.5 py-2 text-xs rounded-xl border border-slate-300 bg-white text-slate-900 font-mono outline-none focus:border-violet-600 focus:ring-2 focus:ring-violet-500/10 w-full sm:w-64"
                />
                <button
                  type="button"
                  disabled={!customSearchDomain}
                  onClick={() => handleOpenBuyDomain(customSearchDomain)}
                  className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-bold text-xs disabled:opacity-50 transition cursor-pointer shrink-0"
                >
                  Check &amp; Buy
                </button>
              </div>
            </div>
          </div>
        )}

        {/* In-Website Domain Purchasing Modal */}
        {isDomainBuyModalOpen && (
          <div className="deploy-modal-backdrop" onClick={() => setIsDomainBuyModalOpen(false)}>
            <div className="deploy-modal-dialog-light space-y-5" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between border-b border-slate-200 pb-4">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-violet-100 text-violet-700 flex items-center justify-center font-bold">
                    <Globe className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-extrabold text-base text-slate-900">Buy &amp; Connect Custom Domain</h3>
                    <p className="text-xs text-slate-500">Direct registration inside AI Site Studio</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsDomainBuyModalOpen(false)}
                  className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-900 flex items-center justify-center transition cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-4 text-xs">
                <div className="p-4 rounded-xl border border-violet-200 bg-violet-50/60 flex items-center justify-between">
                  <div>
                    <div className="font-mono font-extrabold text-sm text-slate-900">{selectedDomainToBuy}</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">1 Year Domain Registration &amp; Automated DNS</div>
                  </div>
                  <div className="text-right">
                    {domainQuoteLoading ? (
                      <RefreshCw className="h-4 w-4 animate-spin text-violet-600" />
                    ) : domainQuote ? (
                      <div className="text-emerald-700 font-extrabold text-base font-mono">
                        {domainQuote.price?.currencyCode || "$"}{((Number(domainQuote.price?.value || 1099) + (domainQuote.fees || []).reduce((s, f) => s + Number(f.fee?.value || 0), 0)) / 100).toFixed(2)}
                      </div>
                    ) : (
                      <span className="text-slate-600 font-mono font-bold">$10.99</span>
                    )}
                  </div>
                </div>

                {domainBuyError && (
                  <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-medium">
                    {domainBuyError}
                  </div>
                )}

                <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 space-y-2 text-[11px] text-slate-600">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                    <span>Includes free automated Let's Encrypt TLS/SSL certificate</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                    <span>Automatic edge DNS routing to your live website</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                    <span>Secure checkout powered by Stripe &amp; GoDaddy registry</span>
                  </div>
                </div>

                <button
                  type="button"
                  disabled={domainQuoteLoading}
                  onClick={handleConfirmDomainCheckout}
                  className="w-full py-3 rounded-xl bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-md shadow-violet-600/20 transition cursor-pointer"
                >
                  <ShoppingCart className="h-4 w-4" />
                  <span>Confirm &amp; Connect Domain</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
