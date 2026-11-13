import { useState, useEffect } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import {
  Rocket,
  Globe,
  ArrowLeft,
  CheckCircle2,
  Copy,
  Check,
  RefreshCw,
  Sparkles,
  ArrowRight,
  Zap,
  ShoppingCart,
  X,
  AlertTriangle,
  ShoppingBag,
  Palette,
  Cpu,
  Lock,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useAppAuth, useAppUser } from "@/lib/auth";
import { api } from "@/lib/api";
import { useStudioBuildStore } from "@/store/studioBuildStore";
import { toast } from "sonner";
import "./Deploy.css";

export default function StudioDeployPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { getToken } = useAppAuth();
  const { user } = useAppUser();
  const buildStore = useStudioBuildStore();

  const queryName = searchParams.get("name") || "";
  const initialTemplateId = searchParams.get("template") || localStorage.getItem("last_studio_template_id") || "";

  // Template selector lists & categories
  const [userTemplates, setUserTemplates] = useState([]);
  const [purchasedTemplates, setPurchasedTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [selectedTemplateCategory, setSelectedTemplateCategory] = useState("all"); // "all" | "purchased" | "studio" | "edited"
  const [selectedTemplateId, setSelectedTemplateId] = useState(initialTemplateId || "");
  const [template, setTemplate] = useState(null);

  // Configured user custom domains from our website
  const [configuredDomains, setConfiguredDomains] = useState([]);
  const [domainsLoading, setDomainsLoading] = useState(true);
  const [domainMode, setDomainMode] = useState("subdomain"); // "subdomain" | "configured"
  const [selectedConfiguredDomain, setSelectedConfiguredDomain] = useState("");

  // Form & deployment options (Fixed to our own Studio Edge CDN deployment)
  const provider = "local";
  const [projectName, setProjectName] = useState(
    (queryName || "").toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
  );
  const [deploying, setDeploying] = useState(false);

  // Subdomain live availability check state
  const [subdomainStatus, setSubdomainStatus] = useState({
    checking: false,
    available: true,
    checkedName: "",
    suggestions: [],
    fullSubdomain: "",
  });

  // In-Website Domain Purchasing modal state (GoDaddy)
  const [isDomainBuyModalOpen, setIsDomainBuyModalOpen] = useState(false);
  const [selectedDomainToBuy, setSelectedDomainToBuy] = useState("");
  const [domainQuote, setDomainQuote] = useState(null);
  const [domainQuoteLoading, setDomainQuoteLoading] = useState(false);
  const [domainBuyError, setDomainBuyError] = useState("");
  const [customSearchDomain, setCustomSearchDomain] = useState("");
  const [acceptedDomainTerms, setAcceptedDomainTerms] = useState(false);
  const [acceptedRegistrarAgreements, setAcceptedRegistrarAgreements] = useState([]);
  const [agreementAcceptedAt, setAgreementAcceptedAt] = useState(null);
  const [registrantProfile, setRegistrantProfile] = useState({
    nameFirst: "",
    nameLast: "",
    email: "",
    phone: { countryCode: "+1", nationalNumber: "" },
    address: { address1: "", address2: "", city: "", state: "", postalCode: "", country: "US" },
  });

  // Pre-fill registrant contact profile from current logged-in user
  useEffect(() => {
    if (user) {
      const names = (user.name || user.full_name || "").trim().split(" ");
      const fName = names[0] || "";
      const lName = names.slice(1).join(" ") || "";
      setRegistrantProfile((prev) => ({
        ...prev,
        nameFirst: prev.nameFirst || fName || "",
        nameLast: prev.nameLast || lName || "",
        email: prev.email || user.email || "",
      }));
    }
  }, [user]);

  // Fetch all user's deployable templates & configured custom domains
  useEffect(() => {
    let isMounted = true;
    async function loadAllDeployableSources() {
      setTemplatesLoading(true);
      setDomainsLoading(true);
      try {
        const token = await getToken();
        const [templatesRes, ordersRes, domainsRes, deploysRes] = await Promise.all([
          api.get("/templates/my-templates", token).catch(() => []),
          api.get("/orders", token).catch(() => []),
          api.get("/deployments/domains/my-domains", token).catch(() => []),
          api.get("/deployments", token).catch(() => []),
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

          // Parse all configured domains from account
          const myDomains = [];
          const seenDomainNames = new Set();
          if (Array.isArray(domainsRes)) {
            domainsRes.forEach((d) => {
              if (d.domain && !d.domain.endsWith(".site-studio.live") && !seenDomainNames.has(d.domain)) {
                seenDomainNames.add(d.domain);
                myDomains.push(d);
              }
            });
          }
          if (Array.isArray(deploysRes)) {
            deploysRes.forEach((dep) => {
              if (dep.custom_domain && !seenDomainNames.has(dep.custom_domain)) {
                seenDomainNames.add(dep.custom_domain);
                myDomains.push({
                  id: dep.id,
                  domain: dep.custom_domain,
                  domain_type: "custom",
                  verification_status: "verified",
                  ssl_status: "active",
                });
              }
            });
          }
          setConfiguredDomains(myDomains);
          if (myDomains.length > 0 && !selectedConfiguredDomain) {
            setSelectedConfiguredDomain(myDomains[0].domain);
          }

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
        if (isMounted) {
          setTemplatesLoading(false);
          setDomainsLoading(false);
        }
      }
    }
    loadAllDeployableSources();
    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken, initialTemplateId]);

  // Construct Categorized Deployable Templates with Pre-Edited & Post-Edited Pairing
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
      title: buildStore.projectTitle || buildStore.plan?.title || "Site Studio Project",
      short_description: buildStore.plan?.summary || "Generated in Site Studio",
      framework: buildStore.plan?.stack?.frontend === "react" ? "react" : "html",
      pages_count: buildStore.plan?.pages?.length || 1,
      originCategory: "studio",
    });
  }

  const allRawTemplates = [
    ...Array.from(purchasedMap.values()),
    ...studioItems,
    ...userTemplates.map((t) => ({ ...t, originCategory: t.originCategory || "user" })),
  ];

  // Group by base template key to generate clean 1: Pre-Edited (Original) and 2: Post-Edited (Customized)
  const getBaseTemplateKey = (item) => {
    if (item.slug && item.slug.includes("-custom-")) {
      return item.slug.split("-custom-")[0].toLowerCase().trim();
    }
    const t = (item.title || "").toLowerCase().trim();
    const cleaned = t
      .replace(/^customized\s+/i, "")
      .replace(/\s*\(customized\)/i, "")
      .replace(/\s*\(draft\)/i, "")
      .replace(/\s*draft$/i, "")
      .trim();
    return cleaned || item.id;
  };

  const isTemplateEdited = (item) => {
    if (item.originCategory === "edited") return true;
    if (item.template_origin === "custom_draft") return true;
    if (item.slug && item.slug.includes("-custom-")) return true;
    const t = (item.title || "").toLowerCase();
    return t.includes("(customized)") || t.startsWith("customized ") || t.includes("(draft)");
  };

  // Grouping & Deduplication
  const groupedByKey = new Map();
  allRawTemplates.forEach((item) => {
    const key = getBaseTemplateKey(item);
    if (!groupedByKey.has(key)) {
      groupedByKey.set(key, []);
    }
    groupedByKey.get(key).push(item);
  });

  const pairedDeployableTemplates = [];

  groupedByKey.forEach((items) => {
    const uneditedCandidates = items.filter((i) => !isTemplateEdited(i));
    const editedCandidates = items.filter((i) => isTemplateEdited(i));

    const rawName = items[0]?.title || "Website Project";
    const cleanBaseName = rawName
      .replace(/^customized\s+/i, "")
      .replace(/\s*\(customized\)/i, "")
      .replace(/\s*\(draft\)/i, "")
      .replace(/\s*draft$/i, "")
      .trim() || rawName;

    // 1. Pre-Edited Version (Original / Base Template)
    if (uneditedCandidates.length > 0) {
      const original = uneditedCandidates[0];
      pairedDeployableTemplates.push({
        ...original,
        versionStep: 1,
        versionLabel: "1. Pre-Edited",
        versionSubtitle: "Original Template",
        displayTitle: cleanBaseName,
        isCustomized: false,
        originCategory: original.originCategory === "studio" ? "studio" : "purchased",
      });
    }

    // 2. Post-Edited Version (Customized - deduplicates intermediate drafts so at most 1 post-edited version exists!)
    if (editedCandidates.length > 0) {
      const latestEdited = editedCandidates.reduce((best, curr) => {
        const bestDate = new Date(best.updated_at || best.created_at || 0).getTime();
        const currDate = new Date(curr.updated_at || curr.created_at || 0).getTime();
        return currDate >= bestDate ? curr : best;
      }, editedCandidates[0]);

      pairedDeployableTemplates.push({
        ...latestEdited,
        versionStep: 2,
        versionLabel: "2. Post-Edited",
        versionSubtitle: "Customized Version",
        displayTitle: `${cleanBaseName} (Customized)`,
        isCustomized: true,
        originCategory: "edited",
      });
    }
  });

  // Filter based on selected tab
  const filteredDeployableTemplates = pairedDeployableTemplates.filter((item) => {
    if (selectedTemplateCategory === "purchased") return item.originCategory === "purchased";
    if (selectedTemplateCategory === "studio") return item.originCategory === "studio";
    if (selectedTemplateCategory === "edited") return item.originCategory === "edited" || item.isCustomized;
    return true;
  });

  // Handle template card selection
  const handleSelectTemplate = (tpl) => {
    setSelectedTemplateId(tpl.id);
    setTemplate(tpl);
    const clean = (tpl.displayTitle || tpl.title || "my-website")
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
    displayTitle: queryName || buildStore.projectTitle || buildStore.plan?.title || "My Studio Website",
    short_description: buildStore.plan?.summary || "Custom AI-generated website project.",
    framework: buildStore.plan?.stack?.frontend === "react" ? "react" : "html",
    pages_count: buildStore.plan?.pages?.length || 1,
  };

  const displayTitle = effectiveTemplate?.displayTitle || effectiveTemplate?.title || queryName || "My Studio Website";
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
      } catch {
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

    if (domainMode === "configured" && !selectedConfiguredDomain) {
      toast.error("Please select a configured domain from your account, or switch to the free staging subdomain.");
      return;
    }

    setDeploying(true);

    try {
      const token = await getToken();
      const payload = {
        project_name: projectName.trim(),
        provider: provider,
        template_id: targetIdentifier && targetIdentifier !== "studio-project" ? targetIdentifier : null,
        build_command: defaultBuildCommand,
        output_dir: defaultOutputDir,
        accepted_hosting_terms: true,
        custom_domain: domainMode === "configured" && selectedConfiguredDomain ? selectedConfiguredDomain : null,
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
      toast.error("Deployment failed: " + (err.message || "Unknown error"));
    }
  };

  const getDomainSuggestions = (name) => {
    const clean = (name || "mysite").toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 20) || "mysite";
    return [
      { name: `${clean}.com`, tld: ".com", price: "$10.99/yr", tag: "Most Popular", desc: "Global Standard" },
      { name: `${clean}.in`, tld: ".in", price: "$8.49/yr", tag: "Regional Fast", desc: "High Speed Local" },
      { name: `${clean}.co`, tld: ".co", price: "$11.99/yr", tag: "Startup Brand", desc: "Modern & Clean" },
      { name: `${clean}.online`, tld: ".online", price: "$4.99/yr", tag: "Best Value", desc: "Digital Identity" },
    ];
  };

  const handleOpenBuyDomain = async (domainName) => {
    if (!domainName) return;
    const cleanDomain = domainName.toLowerCase().trim();
    setSelectedDomainToBuy(cleanDomain);
    setDomainBuyError("");
    setDomainQuote(null);
    setAcceptedDomainTerms(false);
    setAcceptedRegistrarAgreements([]);
    setIsDomainBuyModalOpen(true);
    setDomainQuoteLoading(true);

    try {
      const token = await getToken();
      const quote = await api.post(
        "/deployments/domains/quote",
        {
          domain: cleanDomain,
          period: 1,
        },
        token
      );
      if (quote?.quoteToken) {
        setDomainQuote(quote);
      } else {
        throw new Error("Local fallback required");
      }
    } catch {
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
        requiredAgreements: [
          { agreementType: "DNRA", title: "Domain Name Registration Agreement", url: "https://www.godaddy.com/legal/agreements/domain-name-registration-agreement" },
          { agreementType: "UTOS", title: "Universal Terms of Service", url: "https://www.godaddy.com/legal/agreements/universal-terms-of-service-agreement" }
        ],
      });
      setDomainBuyError("");
    } finally {
      setDomainQuoteLoading(false);
    }
  };

  const handleConfirmDomainCheckout = async () => {
    if (!domainQuote) return;
    setDomainBuyError("");

    // Validate GoDaddy registry contact fields
    if (!registrantProfile.nameFirst?.trim() || !registrantProfile.nameLast?.trim()) {
      setDomainBuyError("First and Last name are required for GoDaddy registry.");
      return;
    }
    if (!registrantProfile.email?.trim() || !registrantProfile.email.includes("@")) {
      setDomainBuyError("A valid email address is required for ICANN domain registration.");
      return;
    }
    if (!registrantProfile.phone?.nationalNumber?.trim()) {
      setDomainBuyError("A valid contact phone number is required by GoDaddy registry.");
      return;
    }
    if (
      !registrantProfile.address?.address1?.trim() ||
      !registrantProfile.address?.city?.trim() ||
      !registrantProfile.address?.postalCode?.trim() ||
      !registrantProfile.address?.country?.trim()
    ) {
      setDomainBuyError("Street address, city, postal code, and 2-letter country code are required.");
      return;
    }
    if (!acceptedDomainTerms) {
      setDomainBuyError("Please accept the domain registration terms before continuing.");
      return;
    }

    try {
      setDomainQuoteLoading(true);
      const token = await getToken();
      const fees = domainQuote.fees || [];
      const res = await api.post(
        "/deployments/domains/purchase",
        {
          deployment_id: "active-deploy",
          domain: selectedDomainToBuy,
          period: domainQuote.period || 1,
          profile: registrantProfile,
          accepted_no_refund_terms: acceptedDomainTerms,
          accepted_agreements: (domainQuote.requiredAgreements || []).map((a) => a.agreementType).filter(Boolean),
          accepted_fees: fees,
          agreement_accepted_at: agreementAcceptedAt || new Date().toISOString(),
          quoted_total_minor:
            Number(domainQuote.price?.value || 1099) +
            fees.reduce((s, f) => s + Number(f.fee?.value || 0), 0),
          quoted_currency: domainQuote.price?.currencyCode || "USD",
          quoted_renewal_price_minor: domainQuote.renewalPrice?.value ?? 1299,
        },
        token
      );

      if (res?.checkout_url) {
        window.location.assign(res.checkout_url);
      } else {
        toast.success(`Domain "${selectedDomainToBuy}" successfully registered and configured!`);
        setConfiguredDomains((prev) => [
          { domain: selectedDomainToBuy, verification_status: "verified", domain_type: "custom" },
          ...prev,
        ]);
        setSelectedConfiguredDomain(selectedDomainToBuy);
        setDomainMode("configured");
        setIsDomainBuyModalOpen(false);
      }
    } catch (err) {
      setDomainBuyError(err.message || "Failed to process domain purchase with GoDaddy.");
    } finally {
      setDomainQuoteLoading(false);
    }
  };

  const purchasedCount = pairedDeployableTemplates.filter((t) => t.originCategory === "purchased").length;
  const studioCount = pairedDeployableTemplates.filter((t) => t.originCategory === "studio").length;
  const customizedCount = pairedDeployableTemplates.filter((t) => t.isCustomized || t.originCategory === "edited").length;

  return (
    <div className="studio-deploy-page">
      <Navbar />

      <main>
        {/* Breadcrumb Navigation & Back to Dashboard */}
        <div className="deploy-top-bar">
          <div className="flex items-center gap-2 text-xs text-zinc-400 font-medium">
            <Link to="/studio" className="deploy-crumb-link">
              <ArrowLeft className="h-3.5 w-3.5" /> Studio Creator
            </Link>
            <span className="text-zinc-600">/</span>
            <span className="font-semibold text-zinc-200 truncate max-w-[220px]">
              {displayTitle}
            </span>
            <span className="text-zinc-600">/</span>
            <span className="text-[#dfb180] font-bold">Deploy to Cloud</span>
          </div>

          <Link to="/dashboard?tab=deployments" className="deploy-back-btn">
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to Dashboard</span>
          </Link>
        </div>

        {/* Hero Banner */}
        <div className="deploy-hero-banner">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="deploy-pill-badge">
                <Rocket className="h-3.5 w-3.5" />
                <span>Instant Cloud Deployment</span>
              </div>
              <h1 className="deploy-hero-title">
                Deploy Website to Cloud
              </h1>
              <p className="deploy-hero-subtitle">
                Choose between original templates (Pre-Edited) and your personalized projects (Post-Edited). Launch to high-speed Edge servers with free automatic SSL.
              </p>
            </div>

            <div className="shrink-0">
              <span className="deploy-tech-pill">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>{isReact ? "React + FastAPI Full-Stack" : "HTML5 + Modern CSS"}</span>
              </span>
            </div>
          </div>
        </div>

        {/* Main Deployment Form */}
        <form onSubmit={handleStartDeploy} className="space-y-6">

          {/* ── STEP 1: SELECT PROJECT (PRE-EDITED VS POST-EDITED DEDUPLICATED) ── */}
          <div className="deploy-step-section">
            <div className="deploy-step-header">
              <div className="deploy-step-title">
                <span className="deploy-step-badge">1</span>
                <span>Select Project to Deploy</span>
              </div>
              <span className="deploy-step-count">
                {pairedDeployableTemplates.length} projects available (Pre &amp; Post-Edited)
              </span>
            </div>

            {/* Category Filter Tabs */}
            <div className="deploy-filter-tabs">
              <button
                type="button"
                onClick={() => setSelectedTemplateCategory("all")}
                className={`deploy-filter-btn ${selectedTemplateCategory === "all" ? "active" : ""}`}
              >
                All ({pairedDeployableTemplates.length})
              </button>
              <button
                type="button"
                onClick={() => setSelectedTemplateCategory("purchased")}
                className={`deploy-filter-btn ${selectedTemplateCategory === "purchased" ? "active" : ""}`}
              >
                <ShoppingBag className="w-3.5 h-3.5 text-emerald-500" />
                Purchased ({purchasedCount})
              </button>
              <button
                type="button"
                onClick={() => setSelectedTemplateCategory("studio")}
                className={`deploy-filter-btn ${selectedTemplateCategory === "studio" ? "active" : ""}`}
              >
                <Cpu className="w-3.5 h-3.5 text-[#dfb180]" />
                Automated Studio ({studioCount})
              </button>
              <button
                type="button"
                onClick={() => setSelectedTemplateCategory("edited")}
                className={`deploy-filter-btn ${selectedTemplateCategory === "edited" ? "active" : ""}`}
              >
                <Palette className="w-3.5 h-3.5 text-amber-500" />
                Customized ({customizedCount})
              </button>
            </div>

            {/* Projects Grid (2-Column Responsive, Word-Break & No Text Overflow) */}
            {templatesLoading ? (
              <div className="p-10 text-center rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface-secondary))] flex items-center justify-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
                <RefreshCw className="h-4 w-4 animate-spin text-[#dfb180]" />
                <span>Loading your projects...</span>
              </div>
            ) : filteredDeployableTemplates.length === 0 ? (
              <div className="p-8 text-center rounded-xl border border-dashed border-[hsl(var(--border))] bg-[hsl(var(--surface-secondary))] text-[hsl(var(--muted-foreground))] text-xs">
                No projects found in this category. Select another tab or generate one in Studio.
              </div>
            ) : (
              <div className="deploy-projects-grid">
                {filteredDeployableTemplates.map((tpl) => {
                  const isSelected = selectedTemplateId === tpl.id;
                  return (
                    <div
                      key={tpl.id}
                      onClick={() => handleSelectTemplate(tpl)}
                      className={`deploy-project-card ${isSelected ? "selected" : ""}`}
                    >
                      <div className="flex items-start gap-3">
                        <div className="deploy-project-thumb">
                          {tpl.thumbnail_url ? (
                            <img src={tpl.thumbnail_url} alt="" className="w-full h-full object-cover" />
                          ) : tpl.originCategory === "purchased" ? (
                            <ShoppingBag className="w-5 h-5 text-emerald-500" />
                          ) : tpl.isCustomized ? (
                            <Palette className="w-5 h-5 text-amber-500" />
                          ) : (
                            <Cpu className="w-5 h-5 text-[#dfb180]" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          {/* Version Badge (1. Pre-Edited vs 2. Post-Edited) + Origin Chip */}
                          <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                            <span className={tpl.isCustomized ? "deploy-version-badge-post" : "deploy-version-badge-pre"}>
                              {tpl.versionLabel}
                            </span>
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                              tpl.originCategory === "purchased"
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25"
                                : tpl.isCustomized
                                ? "bg-amber-500/10 text-amber-600 dark:text-amber-300 border border-amber-500/25"
                                : "bg-[#c89666]/15 text-[#b5804f] dark:text-[#dfb180] border border-[#c89666]/30"
                            }`}>
                              {tpl.originCategory === "purchased" ? "Purchased" : tpl.isCustomized ? "Customized" : "Automated Studio"}
                            </span>
                            <span className="text-[10px] text-[hsl(var(--muted-foreground))] font-mono uppercase font-semibold">{tpl.framework || "html"}</span>
                          </div>

                          {/* High-Contrast Title with 2-line wrap and break-word */}
                          <h4 className="deploy-project-title" title={tpl.displayTitle || tpl.title}>
                            {tpl.displayTitle || tpl.title}
                          </h4>
                        </div>
                      </div>

                      <div className="deploy-project-footer">
                        <span className={isSelected ? "text-[#b5804f] dark:text-[#dfb180] font-bold" : "text-[hsl(var(--muted-foreground))]"}>
                          {isSelected ? "Selected for Deploy" : "Click to select"}
                        </span>
                        <div className={`deploy-select-indicator ${isSelected ? "selected" : ""}`}>
                          {isSelected && <Check className="w-3 h-3 text-[#171717] stroke-[3]" />}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ── STEP 2: SUBDOMAIN & CONFIGURED DOMAINS (NO ARBITRARY NEW DOMAIN ENTRY) ── */}
          <div className="deploy-step-section">
            <div className="deploy-step-header">
              <div className="deploy-step-title">
                <span className="deploy-step-badge">2</span>
                <span>Project Subdomain &amp; Live Address</span>
              </div>
              <span className="text-xs text-zinc-400 font-medium">Studio Edge Deployment</span>
            </div>

            {/* Mode Selector Tabs: Free Subdomain vs Configured Domains from Website */}
            <div className="grid sm:grid-cols-2 gap-3 mb-4">
              <div
                onClick={() => setDomainMode("subdomain")}
                className={`deploy-domain-choice-card ${domainMode === "subdomain" ? "selected" : ""}`}
              >
                <div className="flex items-center gap-2.5">
                  <Zap className="w-4 h-4 text-[#dfb180]" />
                  <div>
                    <div className="deploy-domain-choice-title">Free Staging Subdomain</div>
                    <div className="deploy-domain-choice-sub">*.site-studio.live (Included)</div>
                  </div>
                </div>
                <div className={`deploy-select-indicator ${domainMode === "subdomain" ? "selected" : ""}`}>
                  {domainMode === "subdomain" && <Check className="w-3 h-3 text-[#171717] stroke-[3]" />}
                </div>
              </div>

              <div
                onClick={() => setDomainMode("configured")}
                className={`deploy-domain-choice-card ${domainMode === "configured" ? "selected" : ""}`}
              >
                <div className="flex items-center gap-2.5">
                  <Globe className="w-4 h-4 text-emerald-500" />
                  <div>
                    <div className="deploy-domain-choice-title">Configured Custom Domain</div>
                    <div className="deploy-domain-choice-sub">
                      {configuredDomains.length > 0 ? `${configuredDomains.length} domains available` : "From my account"}
                    </div>
                  </div>
                </div>
                <div className={`deploy-select-indicator ${domainMode === "configured" ? "selected" : ""}`}>
                  {domainMode === "configured" && <Check className="w-3 h-3 text-[#171717] stroke-[3]" />}
                </div>
              </div>
            </div>

            {/* When Subdomain Mode is Active */}
            {domainMode === "subdomain" && (
              <div>
                <label className="deploy-form-label">
                  Subdomain Prefix *
                </label>
                <div className="deploy-domain-input-box">
                  <span className="text-xs text-[hsl(var(--muted-foreground))] font-mono select-none mr-1.5 font-bold">https://</span>
                  <input
                    type="text"
                    required
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""))}
                    placeholder="my-portfolio"
                    className="deploy-domain-input"
                  />
                  <span className="deploy-domain-suffix">.site-studio.live</span>
                </div>

                <div className="mt-2 flex items-center justify-between">
                  <p className="deploy-form-hint">
                    Only lowercase letters, numbers, and hyphens.
                  </p>
                  {subdomainStatus.checking && (
                    <div className="flex items-center gap-1.5 text-xs text-[#b5804f] dark:text-[#dfb180] font-semibold">
                      <RefreshCw className="h-3 w-3 animate-spin" />
                      <span>Checking live availability...</span>
                    </div>
                  )}
                </div>

                {!subdomainStatus.checking && projectName && (
                  subdomainStatus.available ? (
                    <div className="mt-3 flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
                      <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                      <span>
                        <strong>https://{projectName}.site-studio.live</strong> is available and ready!
                      </span>
                    </div>
                  ) : (
                    <div className="mt-3 space-y-2 p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/25 text-xs">
                      <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-bold">
                        <AlertTriangle className="h-4 w-4 shrink-0" />
                        <span>"{projectName}" is already taken. Try one of these available names:</span>
                      </div>
                      <div className="flex flex-wrap gap-2 pt-1">
                        {subdomainStatus.suggestions.map((sug, i) => (
                          <button
                            key={i}
                            type="button"
                            onClick={() => setProjectName(sug)}
                            className="px-3 py-1 rounded-lg bg-[hsl(var(--surface-secondary))] hover:bg-[hsl(var(--muted))] border border-[hsl(var(--border))] hover:border-[#c89666] text-[#b5804f] dark:text-[#dfb180] text-xs font-bold transition flex items-center gap-1.5 cursor-pointer"
                          >
                            <Sparkles className="h-3 w-3 text-[#dfb180]" />
                            <span>{sug}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )
                )}
              </div>
            )}

            {/* When Configured Custom Domain Mode is Active (NO FREEFORM ENTRY) */}
            {domainMode === "configured" && (
              <div className="space-y-3">
                <label className="deploy-form-label">
                  Select Configured Domain from Your Account *
                </label>

                {domainsLoading ? (
                  <div className="p-6 text-center rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface-secondary))] flex items-center justify-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
                    <RefreshCw className="h-4 w-4 animate-spin text-[#dfb180]" />
                    <span>Loading your configured domains...</span>
                  </div>
                ) : configuredDomains.length === 0 ? (
                  <div className="p-5 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--surface-secondary))] text-xs space-y-3">
                    <div className="flex items-start gap-2.5">
                      <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                      <div>
                        <p className="font-bold text-[hsl(var(--foreground))]">No custom domains configured yet in your account.</p>
                        <p className="text-[hsl(var(--muted-foreground))] mt-1 leading-relaxed">
                          To connect a custom domain, configure or buy it in your Dashboard first. You cannot enter an unconfigured domain directly here.
                        </p>
                      </div>
                    </div>
                    <Link
                      to="/dashboard?tab=deployments"
                      className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-[hsl(var(--card))] hover:bg-[hsl(var(--muted))] border border-[hsl(var(--border))] text-[#b5804f] dark:text-[#dfb180] font-bold text-xs transition"
                    >
                      <span>Manage &amp; Configure Domains in Dashboard</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {configuredDomains.map((cd) => {
                      const isChosen = selectedConfiguredDomain === cd.domain;
                      return (
                        <div
                          key={cd.domain}
                          onClick={() => setSelectedConfiguredDomain(cd.domain)}
                          className={`deploy-domain-choice-card ${isChosen ? "selected" : ""}`}
                        >
                          <div className="flex items-center gap-3">
                            <div className="deploy-project-thumb">
                              <Globe className="w-4 h-4 text-emerald-500" />
                            </div>
                            <div>
                              <div className="font-mono font-bold text-sm text-[hsl(var(--foreground))]">
                                {cd.domain}
                              </div>
                              <div className="flex items-center gap-2 mt-0.5 text-[10px]">
                                <span className="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25 font-bold">
                                  Configured on Website
                                </span>
                                <span className="text-[hsl(var(--muted-foreground))] font-medium">DNS Ready</span>
                              </div>
                            </div>
                          </div>

                          <div className={`deploy-select-indicator ${isChosen ? "selected" : ""}`}>
                            {isChosen && <Check className="w-3 h-3 text-[#171717] stroke-[3]" />}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── STEP 3: REVIEW & LAUNCH ── */}
          <div className="deploy-step-section">
            <div className="deploy-step-header">
              <div className="deploy-step-title">
                <span className="deploy-step-badge">3</span>
                <span>Review &amp; Launch</span>
              </div>
              <span className="text-xs text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Ready for Live Launch
              </span>
            </div>

            {/* Review Strip */}
            <div className="deploy-summary-strip space-y-2.5 text-xs">
              <div className="deploy-summary-row">
                <span className="deploy-summary-label">Selected Project:</span>
                <span className="deploy-summary-value truncate max-w-[280px]">{displayTitle}</span>
              </div>
              <div className="deploy-summary-row">
                <span className="deploy-summary-label">Live Address:</span>
                <span className="font-mono font-bold text-[#b5804f] dark:text-[#dfb180]">
                  {domainMode === "configured" && selectedConfiguredDomain
                    ? `https://${selectedConfiguredDomain}`
                    : `https://${projectName || "my-website"}.site-studio.live`}
                </span>
              </div>
              {domainMode === "configured" && selectedConfiguredDomain && (
                <div className="deploy-summary-row">
                  <span className="deploy-summary-label">Edge Routing:</span>
                  <span className="font-mono deploy-summary-value">
                    https://{projectName || "my-website"}.site-studio.live
                  </span>
                </div>
              )}
              <div className="deploy-summary-row">
                <span className="deploy-summary-label">Hosting Platform:</span>
                <span className="deploy-summary-value">
                  Studio Edge CDN (Built-in)
                </span>
              </div>
              <div className="deploy-summary-row">
                <span className="deploy-summary-label">SSL Security:</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
                  <Lock className="w-3.5 h-3.5" /> Free Auto-Provisioned TLS 1.3
                </span>
              </div>
            </div>

            {/* Deploy Action Button */}
            <div className="mt-5">
              <button
                type="submit"
                disabled={deploying}
                className="deploy-launch-btn"
              >
                {deploying ? (
                  <>
                    <RefreshCw className="h-5 w-5 animate-spin" />
                    <span>Building &amp; Launching to Edge...</span>
                  </>
                ) : (
                  <>
                    <Rocket className="h-5 w-5" />
                    <span>🚀 Deploy Website Live</span>
                  </>
                )}
              </button>
            </div>

            {/* Security & Guarantees */}
            <div className="deploy-guarantees-grid">
              <div className="deploy-guarantee-item">
                <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                <span>Automatic Free SSL &amp; HTTPS</span>
              </div>
              <div className="deploy-guarantee-item">
                <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                <span>Instant Global Edge Routing</span>
              </div>
              <div className="deploy-guarantee-item">
                <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                <span>Real-Time Logs &amp; Health</span>
              </div>
            </div>
          </div>
        </form>

        {/* ── BRAND CUSTOM DOMAINS (GODADDY INTEGRATION - CONFIGURE NEW DOMAIN ON PLATFORM) ── */}
        <div className="deploy-step-section mt-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <div className="deploy-pill-badge">
                <Sparkles className="h-3.5 w-3.5" />
                <span>Configure New Brand Domains</span>
              </div>
              <h3 className="text-base sm:text-lg font-bold text-[hsl(var(--foreground))]">
                Need a Custom Domain? Configure via GoDaddy
              </h3>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                Purchased domains are automatically registered with ICANN and added to your configured domains list.
              </p>
            </div>
          </div>

          {/* 4 Smart Domain Cards in a Row */}
          <div className="deploy-domain-grid mb-5">
            {getDomainSuggestions(projectName).map((sug, idx) => (
              <div key={idx} className="deploy-domain-card">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#c89666]/15 text-[#b5804f] dark:text-[#dfb180] border border-[#c89666]/30">
                      {sug.tag}
                    </span>
                    <span className="text-[10px] text-[hsl(var(--muted-foreground))] font-medium">
                      {sug.desc}
                    </span>
                  </div>
                  <h4 className="font-mono font-bold text-sm text-[hsl(var(--foreground))] mt-2 truncate" title={sug.name}>
                    {sug.name}
                  </h4>
                  <div className="text-xs font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                    {sug.price}
                  </div>
                </div>

                <div className="flex gap-2 pt-2 border-t border-[hsl(var(--border))]">
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard?.writeText(sug.name);
                      toast.success(`Copied "${sug.name}" to clipboard`);
                    }}
                    className="p-2 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--surface-secondary))] hover:bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition cursor-pointer"
                    title="Copy domain name"
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleOpenBuyDomain(sug.name)}
                    className="flex-1 py-2 px-3 rounded-lg bg-[#c89666] hover:bg-[#dfb180] text-[#171717] text-xs font-bold flex items-center justify-center gap-1.5 transition cursor-pointer"
                  >
                    <ShoppingCart className="h-3.5 w-3.5" />
                    <span>Buy Domain</span>
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Custom Search Box */}
          <div className="pt-4 border-t border-[hsl(var(--border))] flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
            <span className="text-[hsl(var(--muted-foreground))] font-medium">Looking for another domain to register?</span>
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <input
                type="text"
                placeholder="e.g. mybrandname.com"
                value={customSearchDomain}
                onChange={(e) => setCustomSearchDomain(e.target.value.toLowerCase().trim())}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && customSearchDomain) {
                    e.preventDefault();
                    handleOpenBuyDomain(customSearchDomain);
                  }
                }}
                className="px-3.5 py-2 text-xs rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] text-[hsl(var(--foreground))] font-mono outline-none focus:border-[#c89666] w-full sm:w-64"
              />
              <button
                type="button"
                disabled={!customSearchDomain}
                onClick={() => handleOpenBuyDomain(customSearchDomain)}
                className="px-4 py-2 rounded-xl bg-[#c89666] hover:bg-[#dfb180] text-[#171717] font-bold text-xs disabled:opacity-50 transition cursor-pointer shrink-0"
              >
                Check &amp; Buy
              </button>
            </div>
          </div>
        </div>

        {/* ── GODADDY DOMAIN PURCHASE MODAL ── */}
        {isDomainBuyModalOpen && (
          <div className="deploy-modal-backdrop" onClick={() => setIsDomainBuyModalOpen(false)}>
            <div className="deploy-modal-dialog-dark space-y-4" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between border-b border-[hsl(var(--border))] pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-[#c89666]/15 text-[#b5804f] dark:text-[#dfb180] flex items-center justify-center font-bold">
                    <Globe className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-[hsl(var(--foreground))]">Register Custom Domain (GoDaddy)</h3>
                    <p className="text-[11px] text-[hsl(var(--muted-foreground))]">Official ICANN Registration &amp; Automatic DNS Setup</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsDomainBuyModalOpen(false)}
                  className="w-7 h-7 rounded-lg bg-[hsl(var(--surface-secondary))] hover:bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] flex items-center justify-center transition cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-4 text-xs">
                {/* Domain & Live Quote Banner */}
                <div className="p-3.5 rounded-xl border border-[#c89666]/30 bg-[#c89666]/10 flex items-center justify-between">
                  <div>
                    <div className="font-mono font-bold text-sm text-[hsl(var(--foreground))]">{selectedDomainToBuy}</div>
                    <div className="text-[11px] text-[hsl(var(--muted-foreground))] mt-0.5 font-medium">1-Year Registration &bull; Instant DNS Integration</div>
                  </div>
                  <div className="text-right">
                    {domainQuoteLoading ? (
                      <RefreshCw className="h-4 w-4 animate-spin text-[#dfb180]" />
                    ) : domainQuote ? (
                      <div>
                        <div className="text-emerald-600 dark:text-emerald-400 font-bold text-base font-mono">
                          {domainQuote.price?.currencyCode || "$"}{((Number(domainQuote.price?.value || 1099) + (domainQuote.fees || []).reduce((s, f) => s + Number(f.fee?.value || 0), 0)) / 100).toFixed(2)}
                        </div>
                        <div className="text-[10px] text-[hsl(var(--muted-foreground))]">
                          Renews at {domainQuote.renewalPrice?.currencyCode || "$"}{(Number(domainQuote.renewalPrice?.value || 1299) / 100).toFixed(2)}/yr
                        </div>
                      </div>
                    ) : (
                      <span className="text-[hsl(var(--foreground))] font-mono font-bold">$10.99</span>
                    )}
                  </div>
                </div>

                {domainBuyError && (
                  <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/25 text-red-600 dark:text-red-400 text-xs font-semibold">
                    {domainBuyError}
                  </div>
                )}

                {/* Registrant Legal Details */}
                <div className="space-y-3 border border-[hsl(var(--border))] rounded-xl p-3 bg-[hsl(var(--surface-secondary))]">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[hsl(var(--foreground))] uppercase tracking-wider">
                      Registrant Contact Details
                    </span>
                    <span className="text-[10px] text-[hsl(var(--muted-foreground))] font-medium">Required by ICANN / GoDaddy</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    <div>
                      <label className="block text-[11px] font-semibold text-[hsl(var(--foreground))] mb-1">First Name *</label>
                      <input
                        type="text"
                        required
                        placeholder="First name"
                        value={registrantProfile.nameFirst}
                        onChange={(e) => setRegistrantProfile((p) => ({ ...p, nameFirst: e.target.value }))}
                        className="deploy-modal-input"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-[hsl(var(--foreground))] mb-1">Last Name *</label>
                      <input
                        type="text"
                        required
                        placeholder="Last name"
                        value={registrantProfile.nameLast}
                        onChange={(e) => setRegistrantProfile((p) => ({ ...p, nameLast: e.target.value }))}
                        className="deploy-modal-input"
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-[11px] font-semibold text-[hsl(var(--foreground))] mb-1">Email Address *</label>
                      <input
                        type="email"
                        required
                        placeholder="registrant@example.com"
                        value={registrantProfile.email}
                        onChange={(e) => setRegistrantProfile((p) => ({ ...p, email: e.target.value }))}
                        className="deploy-modal-input"
                      />
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-[hsl(var(--foreground))] mb-1">Country Dial Code *</label>
                      <input
                        type="text"
                        required
                        placeholder="+1 or +91"
                        value={registrantProfile.phone.countryCode}
                        onChange={(e) => setRegistrantProfile((p) => ({ ...p, phone: { ...p.phone, countryCode: e.target.value } }))}
                        className="deploy-modal-input"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-[hsl(var(--foreground))] mb-1">Phone Number *</label>
                      <input
                        type="tel"
                        required
                        placeholder="e.g. 9876543210"
                        value={registrantProfile.phone.nationalNumber}
                        onChange={(e) => setRegistrantProfile((p) => ({ ...p, phone: { ...p.phone, nationalNumber: e.target.value } }))}
                        className="deploy-modal-input"
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-[11px] font-semibold text-[hsl(var(--foreground))] mb-1">Street Address *</label>
                      <input
                        type="text"
                        required
                        placeholder="Street address line 1"
                        value={registrantProfile.address.address1}
                        onChange={(e) => setRegistrantProfile((p) => ({ ...p, address: { ...p.address, address1: e.target.value } }))}
                        className="deploy-modal-input"
                      />
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-[hsl(var(--foreground))] mb-1">City *</label>
                      <input
                        type="text"
                        required
                        placeholder="City"
                        value={registrantProfile.address.city}
                        onChange={(e) => setRegistrantProfile((p) => ({ ...p, address: { ...p.address, city: e.target.value } }))}
                        className="deploy-modal-input"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-[hsl(var(--foreground))] mb-1">Postal Code *</label>
                      <input
                        type="text"
                        required
                        placeholder="PIN / Postal Code"
                        value={registrantProfile.address.postalCode}
                        onChange={(e) => setRegistrantProfile((p) => ({ ...p, address: { ...p.address, postalCode: e.target.value } }))}
                        className="deploy-modal-input"
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-[11px] font-semibold text-[hsl(var(--foreground))] mb-1">Country Code (2-letter) *</label>
                      <input
                        type="text"
                        required
                        maxLength={2}
                        placeholder="US, IN, GB, CA"
                        value={registrantProfile.address.country}
                        onChange={(e) => setRegistrantProfile((p) => ({ ...p, address: { ...p.address, country: e.target.value.toUpperCase() } }))}
                        className="deploy-modal-input font-mono uppercase"
                      />
                    </div>
                  </div>
                </div>

                {/* Legal Agreements Checkboxes */}
                <div className="space-y-2 p-3 bg-[hsl(var(--surface-secondary))] border border-[hsl(var(--border))] rounded-xl text-[11px] text-[hsl(var(--foreground))]">
                  <label className="flex items-start gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={acceptedDomainTerms}
                      onChange={(e) => {
                        setAgreementAcceptedAt(new Date().toISOString());
                        setAcceptedDomainTerms(e.target.checked);
                      }}
                      className="mt-0.5 rounded text-[#c89666] focus:ring-0"
                    />
                    <span>
                      I authorize registration of <strong>{selectedDomainToBuy}</strong> for 1 year at the quoted price. I accept the ICANN and GoDaddy registration agreements.
                    </span>
                  </label>
                </div>

                {/* Modal Buttons */}
                <div className="flex items-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsDomainBuyModalOpen(false)}
                    className="flex-1 py-2.5 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] hover:bg-[hsl(var(--muted))] text-[hsl(var(--foreground))] font-bold text-xs transition cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={domainQuoteLoading}
                    onClick={handleConfirmDomainCheckout}
                    className="flex-1 py-2.5 rounded-xl bg-[#c89666] hover:bg-[#dfb180] disabled:opacity-50 text-black font-bold text-xs flex items-center justify-center gap-2 shadow-md transition cursor-pointer"
                  >
                    {domainQuoteLoading ? (
                      <RefreshCw className="h-4 w-4 animate-spin text-black" />
                    ) : (
                      <ShoppingCart className="h-4 w-4" />
                    )}
                    <span>Pay &amp; Register via GoDaddy</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
