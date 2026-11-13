"use client";

/**
 * User Dashboard Page - manages purchases, wishlist, downloads, orders, and settings (React JSX).
 */

export const dynamic = "force-dynamic";

import { useState, useEffect, useRef, useMemo } from "react";
import JSZip from "jszip";
import { useAppAuth, useAppUser, useSignOut } from "@/lib/auth";
import { useAuthStore } from "@/store/authStore";
import { useCurrencyStore } from "@/store/currencyStore";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Code,
  Cpu,
  Rocket,
  Globe,
  Download,
  Receipt,
  Zap,
  CreditCard,
  Heart,
  Coins,
  Star,
  Bell,
  Settings,
  HelpCircle,
  LogOut,
  ShoppingBag,
  ExternalLink,
  User,
  Plus,
  Trash2,
  Loader2,
  Sparkles,
  Key,
  Folder,
  BarChart3,
  TrendingUp,
  Tag,
  Megaphone,
  Users,
  MessageSquare,
  Wallet,
  FileText,
  Palette,
  ShieldCheck,
  Eye,
  Copy,
  ToggleLeft,
  Info,
  CheckCircle,
  CheckCircle2,
  FileUp,
  Check,
  ShoppingCart,
  Wand2,
  X,
  Terminal,
  RefreshCw,
  Video,
  History,
  Pause,
  Play,
  LayoutGrid,
  List,
  Search,
  Pencil,
  UploadCloud,
  AlertTriangle,
  Filter,
  ChevronDown,
  ChevronUp,
  Server,
  Clock,
  Activity,
  Shield,
  ArrowRight,
  AlertCircle,
  PanelLeftClose,
  PanelLeftOpen,
  Crown,
  Layers,
  Send,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { api } from "@/lib/api";
import { cn, formatPrice, convertToUSD } from "@/lib/utils";
import Image from "@/components/Image";
import Link from "@/components/Link";
import { useCartStore } from "@/store";
import AdminModerationHub from "@/components/dashboard/AdminModerationHub";
import AdminIncidentsCenter from "@/components/dashboard/AdminIncidentsCenter";
import ReportIssueModal from "@/components/dashboard/ReportIssueModal";
import DownloadWarningModal from "@/components/modals/DownloadWarningModal";
import DeploymentFixConsole from "@/components/dashboard/DeploymentFixConsole";
import ThemeToggle from "@/components/layout/ThemeToggle";
import "./Page.css";

// Env-aware API base — reads VITE_API_URL from .env, falls back to localhost for development
const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
const BACKEND_BASE = API_BASE.replace(/\/api\/v1\/?$/, "");

const resolveMediaUrl = (url) => {
  if (!url || typeof url !== "string") return "";
  if (url.includes("localhost:8000/api/v1/files") || url.includes("127.0.0.1:8000/api/v1/files")) {
    return url.replace(/^https?:\/\/(localhost|127\.0\.0\.1):8000\/api\/v1\/files/, `${BACKEND_BASE}/api/v1/files`);
  }
  return url;
};

const DASHBOARD_SUB_CATEGORIES = {
  business: ["Corporate", "Startup", "Small Business", "Enterprise", "Consulting", "Finance", "Insurance", "Accounting", "Manufacturing", "Logistics"],
  "saas-technology": ["SaaS", "Tech Startup", "Software", "Mobile App", "Web App", "Cyber Security", "Cloud Computing", "Data Analytics", "CRM", "DevOps"],
  ecommerce: ["Fashion", "Electronics", "Furniture", "Jewelry", "Beauty", "Grocery", "Pet Store", "Book Store", "Sports", "Digital Products", "Multi Vendor"],
  "restaurant-food": ["Restaurant", "Cafe", "Bakery", "Fast Food", "Hotel", "Food Delivery", "Catering", "Cloud Kitchen", "Ice Cream", "Juice Bar"],
  healthcare: ["Hospital", "Clinic", "Dentist", "Pharmacy", "Medical Lab", "Veterinary", "Mental Health", "Physiotherapy", "Eye Clinic", "Nursing Home"],
  education: ["School", "College", "University", "Online Courses", "Coaching Center", "LMS", "Kindergarten", "Library", "Tuition", "E-learning"],
  "real-estate": ["Property Listing", "Builder", "Interior Design", "Architecture", "Home Rental", "Apartment", "Commercial Property", "Villa", "Construction"],
  portfolio: ["Designer", "Developer", "Photographer", "Artist", "Freelancer", "Writer", "Musician", "Architect", "Videographer", "Fashion Designer"],
  "creative-agency": ["Marketing Agency", "Digital Agency", "Branding", "SEO Agency", "Advertising", "UI/UX Studio", "Creative Studio", "PR Agency"],
  events: ["Wedding", "Conference", "Event Planner", "Exhibition", "Music Festival", "Birthday", "Corporate Event", "Meetup"],
  travel: ["Tour Agency", "Hotel Booking", "Resort", "Travel Blog", "Visa Agency", "Adventure", "Car Rental", "Airline"],
  fitness: ["Gym", "Yoga", "Personal Trainer", "CrossFit", "Nutrition", "Sports Club", "Martial Arts", "Dance Studio"],
  beauty: ["Salon", "Spa", "Makeup Artist", "Skincare", "Barber Shop", "Cosmetics", "Nail Studio"],
  finance: ["Banking", "Investment", "Cryptocurrency", "Trading", "FinTech", "Loan Company"],
  legal: ["Lawyer", "Law Firm", "Legal Consultant", "Notary", "Immigration", "Tax Consultant"],
  "blog-magazine": ["Personal Blog", "Technology", "Lifestyle", "Travel", "Food", "News", "Fashion", "Sports", "Magazine"],
  automotive: ["Car Dealer", "Bike Dealer", "Auto Service", "Garage", "Car Rental", "EV Company"],
  "ngo-charity": ["Charity", "Foundation", "Community", "Volunteer", "Donations", "Religious Organization"],
  "landing-pages": ["Product Launch", "Startup", "App Landing", "Webinar", "Coming Soon", "Waitlist", "Lead Generation"],
  dashboards: ["Admin Dashboard", "CRM Dashboard", "Analytics Dashboard", "Ecommerce Dashboard", "Finance Dashboard", "HR Dashboard", "LMS Dashboard"],
  gaming: ["eSports", "Gaming Community", "Game Studio", "Streamer", "Gaming Shop"],
  entertainment: ["Music", "Movies", "Podcast", "Streaming", "TV Show", "Celebrity"],
  marketplace: ["Digital Products", "Multi Vendor", "Auctions", "Freelance Marketplace", "Job Board"],
  authentication: ["Login", "Register", "Forgot Password", "OTP", "Multi-factor Authentication"],
  documentation: ["API Docs", "Product Docs", "Knowledge Base", "Help Center", "Wiki"],
};

function StoreOrderAlerts({ identifier, token }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [providers, setProviders] = useState(null);
  const [notice, setNotice] = useState("");
  const endpoint = `/storefront/${encodeURIComponent(identifier)}/notification-settings`;

  const load = async () => {
    setOpen(true);
    setLoading(true);
    setNotice("");
    try {
      const settings = await api.get(endpoint, token ?? undefined);
      setEmail(settings.email || "");
      setPhone(settings.phone || "");
      setProviders(settings);
    } catch (error) {
      setNotice(error.message || "Could not load order alert settings.");
    } finally {
      setLoading(false);
    }
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setNotice("");
    try {
      const settings = await api.put(endpoint, {
        email: email.trim() || null,
        phone: phone.trim() || null,
      }, token ?? undefined);
      setProviders(settings);
      setNotice("Order alert destinations saved.");
    } catch (error) {
      setNotice(error.message || "Could not save order alert settings.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border-t border-slate-200 dark:border-slate-800 pt-3">
      <button type="button" onClick={open ? () => setOpen(false) : load}
        className="w-full text-left text-xs font-bold text-[#dfb180] hover:underline">
        {open ? "Hide order alerts" : "Configure order email & SMS alerts"}
      </button>
      {open && <div className="mt-3 rounded-xl border border-slate-200 dark:border-slate-700 p-3 space-y-3">
        {loading ? <p className="text-xs text-slate-500">Loading settings…</p> : <>
          <form onSubmit={save} className="space-y-2.5">
            <label className="block text-xs font-semibold">Alert email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="orders@yourbusiness.com" className="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" />
            </label>
            <label className="block text-xs font-semibold">Alert mobile (international format)
              <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
                placeholder="+14155550123" pattern="\\+[1-9][0-9]{7,14}"
                className="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" />
            </label>
            <button disabled={saving || (!email.trim() && !phone.trim())}
              className="rounded-lg bg-[#c89666]/15 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">
              {saving ? "Saving…" : "Save destinations"}
            </button>
          </form>
          {providers && <div className="text-[11px] text-slate-600 dark:text-slate-400 space-y-1">
            <p>Email provider: {providers.email_provider_configured ? "configured" : "awaiting Studio SMTP or Resend setup"}</p>
            <p>SMS provider: {providers.sms_provider_configured ? "configured" : "awaiting Studio Twilio setup"}</p>
          </div>}
        </>}
        {notice && <p role="status" className="text-xs text-slate-600 dark:text-slate-300">{notice}</p>}
      </div>}
    </div>
  );
}

function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { getToken } = useAppAuth();
  const { user } = useAppUser();
  const isUserPro = Boolean(
    user?.is_pro_subscriber ||
    ["pro", "agency", "creator_pro", "enterprise"].includes(String(user?.subscription_tier || "").toLowerCase())
  );
  const signOut = useSignOut();
  const [activeTab, setActiveTab] = useState("buyer-home");
  const addToCart = useCartStore((s) => s.addItem);
  const isInCart = useCartStore((s) => s.isInCart);
  const [authToken, setAuthToken] = useState(() => useAuthStore.getState().token);
  const qc = useQueryClient();

  // Hidable Sidebar state with localStorage persistence
  const [isSidebarHidden, setIsSidebarHidden] = useState(() => {
    try {
      return localStorage.getItem("aisitestudio_sidebar_hidden") === "true";
    } catch {
      return false;
    }
  });

  const toggleSidebar = () => {
    setIsSidebarHidden((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("aisitestudio_sidebar_hidden", String(next));
      } catch { }
      return next;
    });
  };

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [bio, setBio] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [userCountry, setUserCountry] = useState("");
  const [userCity, setUserCity] = useState("");
  const [userCurrencyPref, setUserCurrencyPref] = useState("USD");
  const [detectingLocation, setDetectingLocation] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [templatesSubTab, setTemplatesSubTab] = useState("purchased");
  const [studioProjectsSubTab, setStudioProjectsSubTab] = useState("created");
  const [studioProjectsView, setStudioProjectsView] = useState(() => {
    try {
      return localStorage.getItem("studio_projects_view") || "grid";
    } catch {
      return "grid";
    }
  });
  const [studioProjectsSearch, setStudioProjectsSearch] = useState("");

  const handleSetStudioProjectsView = (view) => {
    setStudioProjectsView(view);
    try {
      localStorage.setItem("studio_projects_view", view);
    } catch { }
  };

  // Template Redesign & Edit state
  const [uploadedTemplatesView, setUploadedTemplatesView] = useState("grid"); // "grid" | "table"
  const [uploadedTemplatesSearch, setUploadedTemplatesSearch] = useState("");
  const [adminInvoiceSearch, setAdminInvoiceSearch] = useState("");
  const [editTemplateModalOpen, setEditTemplateModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editPrice, setEditPrice] = useState("");
  const [editCurrency, setEditCurrency] = useState("USD");
  const [editFramework, setEditFramework] = useState("");
  const [editVersion, setEditVersion] = useState("1.0.0");
  const [editCategory, setEditCategory] = useState("");
  const [editDemoUrl, setEditDemoUrl] = useState("");
  const [editError, setEditError] = useState("");
  const [reuploadFile, setReuploadFile] = useState(null);
  const { rates } = useCurrencyStore();

  const [purgingDrafts, setPurgingDrafts] = useState(false);
  const [hiddenPurchasedTemplates, setHiddenPurchasedTemplates] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("hidden_purchased_templates") || "[]");
    } catch {
      return [];
    }
  });

  const handleHidePurchasedTemplate = (key) => {
    const next = [...hiddenPurchasedTemplates, String(key)];
    setHiddenPurchasedTemplates(next);
    try {
      localStorage.setItem("hidden_purchased_templates", JSON.stringify(next));
    } catch { }
  };

  const handleUnhideAllPurchased = () => {
    setHiddenPurchasedTemplates([]);
    try {
      localStorage.removeItem("hidden_purchased_templates");
    } catch { }
  };

  const handlePurgeAllDrafts = async () => {
    if (!window.confirm("Are you sure you want to permanently delete all customized draft templates, studio creator projects, and edited files? This will clear them completely.")) {
      return;
    }
    setPurgingDrafts(true);
    try {
      const res = await api.post("/templates/purge-custom-drafts", {}, authToken ?? undefined);
      qc.invalidateQueries(["seller-templates"]);
      qc.invalidateQueries(["templates"]);
      qc.invalidateQueries(["my-templates"]);
      alert(`Deleted ${res?.deleted_count ?? 0} customized draft projects and temporary files.`);
    } catch (err) {
      alert("Failed to purge drafts: " + (err.message || "Please try again"));
    } finally {
      setPurgingDrafts(false);
    }
  };

  const handleDeleteCustomDraft = async (id, title) => {
    if (!window.confirm(`Delete "${title || 'this project'}"? This cannot be undone.`)) {
      return;
    }
    try {
      await api.delete(`/templates/${id}`, authToken ?? undefined);
      qc.invalidateQueries(["seller-templates"]);
      qc.invalidateQueries(["templates"]);
      qc.invalidateQueries(["my-templates"]);
      alert("Custom project deleted successfully.");
    } catch (err) {
      alert("Failed to delete project: " + (err.message || "Please try again"));
    }
  };

  const getPurchasedItemsList = (ordersList, hiddenIds = []) => {
    const completedOrders = (ordersList || []).filter(o => o.status === "completed");
    const seen = new Set();
    const result = [];
    for (const o of completedOrders) {
      for (const i of (o.items || [])) {
        if (!i.template_id) continue;
        if (i.is_marketplace === false) continue;
        if (i.template_status && i.template_status !== "published") continue;
        const key = String(i.template_id);
        if (hiddenIds.includes(key)) continue;
        if (!seen.has(key)) {
          seen.add(key);
          result.push({
            ...i,
            orderId: o.id,
            orderCreatedAt: o.created_at,
            title: i.title || "Template Package",
            thumbnail_url: i.thumbnail_url || "",
            framework: i.framework || "HTML",
            short_description: i.short_description || "Modern & responsive purchased template."
          });
        }
      }
    }
    return result;
  };

  const isStudioProjectItem = (item) => {
    if (!item) return false;
    const origin = item.template_origin || "";
    // If it is explicitly marked as a customized/edited draft, it is NOT a studio creator project
    const isCustomDraft =
      origin === "custom_draft" ||
      item.tags?.includes("customized-draft") ||
      item.slug?.includes("-custom-") ||
      item.slug?.includes("-draft-") ||
      item.title?.includes("(Customized)") ||
      item.title?.startsWith("Customized ") ||
      item.title?.includes("(Draft)");

    if (isCustomDraft) return false;

    // Must be generated by AI Studio Creator
    return (
      origin === "studio" ||
      item.tags?.includes("studio-project") ||
      item.changelog?.private_studio_project === true
    );
  };

  const getCustomizedItemsList = (templatesList) => {
    const all = Array.isArray(templatesList) ? templatesList : [];
    return all.filter(item => {
      // Studio Creator projects belong strictly in the Studio Projects workspace, not in Customized Files
      if (isStudioProjectItem(item)) return false;

      return (
        item.template_origin === "custom_draft" ||
        item.tags?.includes("customized-draft") ||
        (item.slug && (item.slug.includes("-custom-") || item.slug.includes("-draft-"))) ||
        (item.title && (
          item.title.includes("(Customized)") ||
          item.title.startsWith("Customized ") ||
          item.title.includes("(Draft)")
        )) ||
        (item.status === "draft" && item.is_marketplace === false)
      );
    });
  };

  const updateTemplateMutation = useMutation({
    mutationFn: async ({ templateId, data }) => {
      const res = await api.patch(`/templates/${templateId}`, data, authToken);
      return res;
    },
    onSuccess: () => {
      qc.invalidateQueries(["seller-templates"]);
      qc.invalidateQueries(["templates"]);
      setEditTemplateModalOpen(false);
      setEditingTemplate(null);
      setEditError("");
    },
    onError: (err) => {
      setEditError(err.message || "Failed to update template");
    }
  });

  const reuploadZipMutation = useMutation({
    mutationFn: async ({ templateId, file }) => {
      const formData = new FormData();
      formData.append("file", file);
      const activeJwt = authToken || useAuthStore.getState()?.token;
      const res = await fetch(`${API_BASE}/templates/${templateId}/reupload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${activeJwt}`,
        },
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to re-upload template package");
      }
      return res.json();
    },
    onSuccess: (data) => {
      qc.invalidateQueries(["seller-templates"]);
      qc.invalidateQueries(["templates"]);
      qc.invalidateQueries(["my-templates"]);
      if (data) {
        if (data.framework) setEditFramework(data.framework);
        if (data.version) setEditVersion(data.version);
        setEditingTemplate(prev => prev ? { ...prev, ...data } : data);
      }
      setReuploadFile(null);
    },
  });

  const handleOpenEditTemplateModal = (item) => {
    setEditingTemplate(item);
    setEditTitle(item.title || "");
    setEditDescription(item.description || "");

    const pref = (user?.currency || (user?.country === "India" ? "INR" : "USD")).toUpperCase();
    setEditCurrency(pref);

    if (pref === "INR") {
      const inrRate = rates?.INR || 87.0;
      setEditPrice(Math.round((item.price || 0) * inrRate));
    } else {
      setEditPrice(item.price || 0);
    }

    setEditFramework(item.framework || "html");
    setEditVersion(item.version || "1.0.0");
    setEditCategory(typeof item.category === "object" ? (item.category?.name || item.category?.slug || "General") : (item.category || "General"));
    setEditDemoUrl(item.preview_url || "");
    setEditError("");
    setEditTemplateModalOpen(true);
  };

  const handleEditCurrencyChange = (newCurr) => {
    const currentNum = parseFloat(editPrice) || 0;
    const inrRate = rates?.INR || 87.0;

    if (editCurrency === "USD" && newCurr === "INR") {
      setEditPrice(Math.round(currentNum * inrRate));
    } else if (editCurrency === "INR" && newCurr === "USD") {
      setEditPrice(Math.round((currentNum / inrRate) * 100) / 100);
    }
    setEditCurrency(newCurr);
  };

  // Review Modal state
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [reviewTemplateId, setReviewTemplateId] = useState("");
  const [reviewTemplateTitle, setReviewTemplateTitle] = useState("");
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewTitle, setReviewTitle] = useState("");
  const [reviewBody, setReviewBody] = useState("");
  const [submitReviewError, setSubmitReviewError] = useState("");

  // Custom Domain Mapping state
  const [linkDomainModalOpen, setLinkDomainModalOpen] = useState(false);
  const [domainModalTab, setDomainModalTab] = useState("buy"); // "buy" | "connect"
  const [linkDomainDeploymentId, setLinkDomainDeploymentId] = useState("");
  const [customDomainInput, setCustomDomainInput] = useState("");
  const [linkDomainError, setLinkDomainError] = useState("");
  const [verifyingDomainId, setVerifyingDomainId] = useState("");
  const [domainQuote, setDomainQuote] = useState(null);
  const [domainQuoteLoading, setDomainQuoteLoading] = useState(false);
  const [acceptedDomainTerms, setAcceptedDomainTerms] = useState(false);
  const [acceptedRegistrarAgreements, setAcceptedRegistrarAgreements] = useState([]);
  const [agreementAcceptedAt, setAgreementAcceptedAt] = useState(null);
  const [registrantProfile, setRegistrantProfile] = useState({
    nameFirst: "", nameLast: "", email: "", phone: { countryCode: "+1", nationalNumber: "" },
    address: { address1: "", address2: "", city: "", state: "", postalCode: "", country: "US" },
  });

  // Pre-fill registrant contact details from user
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

  // ── 2-Part Domain Manager States for "My Websites" ──
  const [connectDomainName, setConnectDomainName] = useState("");
  const [connectSelectedDeploymentId, setConnectSelectedDeploymentId] = useState("");
  const [domainChallengeData, setDomainChallengeData] = useState(null);
  const [challengeLoading, setChallengeLoading] = useState(false);
  const [verifyingOwnershipLoading, setVerifyingOwnershipLoading] = useState(false);
  const [ownershipMessage, setOwnershipMessage] = useState(null);
  const [showDnsConnectModal, setShowDnsConnectModal] = useState(false);
  const [selectedDnsProvider, setSelectedDnsProvider] = useState("godaddy");
  const [copiedDnsKey, setCopiedDnsKey] = useState(null);

  const handleCopyDnsText = (text, keyName) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedDnsKey(keyName);
    setTimeout(() => setCopiedDnsKey(null), 2200);
  };

  const handleCopyAllDnsRecords = () => {
    if (!domainChallengeData) return;
    const txtVal = domainChallengeData.txt_value || `aisitestudio-verify-${user?.id?.slice(0, 8) || "auth"}`;
    const aVal = domainChallengeData.a_value || "149.28.243.12";
    const cnameVal = domainChallengeData.cname_value || "site-studio.live";
    const summary = `DNS Configuration Records for ${domainChallengeData.domain || connectDomainName}:

1. TXT Record (Ownership Verification):
   Type: TXT
   Host/Name: _studio-challenge
   Value: ${txtVal}
   TTL: 300 (or Default)

2. A Record (Apex Routing):
   Type: A
   Host/Name: @
   Value: ${aVal}
   TTL: 300 (or Default)

3. CNAME Record (Subdomain Routing):
   Type: CNAME
   Host/Name: www
   Value: ${cnameVal}
   TTL: 300 (or Default)`;
    handleCopyDnsText(summary, "all_records");
  };

  // Right Side: GoDaddy Search state
  const [godaddySearchQuery, setGodaddySearchQuery] = useState("");
  const [godaddySearchResults, setGodaddySearchResults] = useState([]);
  const [godaddySearching, setGodaddySearching] = useState(false);
  const [godaddySearchError, setGodaddySearchError] = useState("");

  // Deployments state
  const [isDeployModalOpen, setIsDeployModalOpen] = useState(false);
  const [isConsoleOpen, setIsConsoleOpen] = useState(false);
  const [selectedDeployment, setSelectedDeployment] = useState(null);
  const [activeConsoleLogs, setActiveConsoleLogs] = useState("");
  const [activeConsoleStatus, setActiveConsoleStatus] = useState("building");
  const [consoleFilter, setConsoleFilter] = useState("all");
  const [consoleSearch, setConsoleSearch] = useState("");
  const [isConsoleStreamPaused, setIsConsoleStreamPaused] = useState(false);
  const [isAutoFixingFromConsole, setIsAutoFixingFromConsole] = useState(false);
  const [copyLogsFeedback, setCopyLogsFeedback] = useState(false);
  const [deploymentSearchQuery, setDeploymentSearchQuery] = useState("");
  const [deploymentStatusFilter, setDeploymentStatusFilter] = useState("all");

  // Wizard form state
  const [deployProjectName, setDeployProjectName] = useState("");
  const [deployTemplateId, setDeployTemplateId] = useState("");
  const [deployProvider, setDeployProvider] = useState("local");
  const [deployBranch, setDeployBranch] = useState("main");
  const [deployBuildCommand, setDeployBuildCommand] = useState("npm run build");
  const [deployOutputDir, setDeployOutputDir] = useState("dist");
  const [deploying, setDeploying] = useState(false);
  const [hostingPrice, setHostingPrice] = useState(null);
  const [acceptedHostingTerms, setAcceptedHostingTerms] = useState(false);
  const [hostingActionId, setHostingActionId] = useState("");
  const consoleEndRef = useRef(null);

  // Multi-Version History & Rollback state
  const [isVersionModalOpen, setIsVersionModalOpen] = useState(false);
  const [versionDeployment, setVersionDeployment] = useState(null);
  const [versionsList, setVersionsList] = useState([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

  // Deployment Accordion Details & Domain Suggestion state
  const [expandedDeployments, setExpandedDeployments] = useState({});
  const [customDomainSearchInputs, setCustomDomainSearchInputs] = useState({});

  const toggleDeploymentDetails = (deployId) => {
    setExpandedDeployments((prev) => ({
      ...prev,
      [deployId]: !prev[deployId],
    }));
  };

  const getDomainSuggestionsForProject = (projectName) => {
    const clean = (projectName || "mysite")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "")
      .slice(0, 20) || "mysite";

    return [
      {
        name: `${clean}.com`,
        tld: ".com",
        price: "$10.99/yr",
        tag: "Most Popular",
        category: "Global Standard",
        tagStyle: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30",
      },
      {
        name: `${clean}.in`,
        tld: ".in",
        price: "$8.49/yr",
        tag: "Regional Fast",
        category: "High Speed Local",
        tagStyle: "bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30",
      },
      {
        name: `${clean}.co`,
        tld: ".co",
        price: "$11.99/yr",
        tag: "Modern Company",
        category: "Startup & Brand",
        tagStyle: "bg-[#c89666]/15 text-[#dfb180] dark:text-[#dfb180] border border-[#c89666]/30",
      },
      {
        name: `${clean}.online`,
        tld: ".online",
        price: "$4.99/yr",
        tag: "Tailored",
        category: "Industry Match",
        tagStyle: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30",
      },
    ];
  };

  const handleBuySuggestedDomain = (deploy, domainName) => {
    if (!domainName) return;
    const cleanDomain = domainName.toLowerCase().trim();
    navigate(`/domains/buy?domain=${encodeURIComponent(cleanDomain)}&deployment_id=${deploy?.id || ""}&from=${encodeURIComponent("/dashboard?tab=deployments")}`);
  };

  // Failure Reporting & Deployment Code Fix Studio state
  const [isReportIssueModalOpen, setIsReportIssueModalOpen] = useState(false);
  const [reportIssueDeployment, setReportIssueDeployment] = useState(null);
  const [isCodeStudioOpen, setIsCodeStudioOpen] = useState(false);
  const [codeStudioDeployment, setCodeStudioDeployment] = useState(null);
  const [isSelfHealingDeployment, setIsSelfHealingDeployment] = useState(false);

  const handleTriggerDeploymentSelfHeal = async () => {
    if (!selectedDeployment?.id || isSelfHealingDeployment) return;
    setIsSelfHealingDeployment(true);
    try {
      const res = await api.post(`/deployments/${selectedDeployment.id}/self-heal`, {}, authToken ?? undefined);
      alert(`🩺 ${res.message || "Autonomous Self-Healing initiated! Codebase is being audited, repaired, and redeployed."}`);
      refetchDeployments();
    } catch (err) {
      alert("Self-healing notice: " + (err.message || "Failed to trigger self-heal"));
    } finally {
      setIsSelfHealingDeployment(false);
    }
  };
  const [codeStudioIncident, setCodeStudioIncident] = useState(null);

  const openReportIssueModal = (deploy) => {
    setReportIssueDeployment(deploy);
    setIsReportIssueModalOpen(true);
  };

  const openCodeStudio = (deploy, incident = null) => {
    setCodeStudioDeployment(deploy);
    setCodeStudioIncident(incident);
    setIsCodeStudioOpen(true);
  };

  const openVersionHistory = async (deploy) => {
    setVersionDeployment(deploy);
    setIsVersionModalOpen(true);
    setVersionsLoading(true);
    try {
      const res = await api.get(`/deployments/${deploy.id}/versions`, authToken ?? undefined);
      setVersionsList(Array.isArray(res) ? res : []);
    } catch (err) {
      setVersionsList([]);
    } finally {
      setVersionsLoading(false);
    }
  };

  const handleRollback = async (targetVersion) => {
    if (!versionDeployment) return;
    if (!confirm(`Are you sure you want to rollback "${versionDeployment.project_name}" to version ${targetVersion}? This will switch live traffic with zero downtime.`)) return;
    try {
      await api.post(`/deployments/${versionDeployment.id}/rollback`, { target_version: targetVersion }, authToken ?? undefined);
      refetchDeployments();
      setIsVersionModalOpen(false);
      alert(`Website successfully rolled back to ${targetVersion}!`);
    } catch (err) {
      alert("Rollback failed: " + err.message);
    }
  };

  const isSeller = user?.role === "seller" || user?.role === "SELLER";
  const isAdmin = user?.role === "admin" || user?.role === "super_admin" || user?.role === "ADMIN" || user?.role === "SUPER_ADMIN";

  // Domain Transfer & Registrar Ownership Modal States
  const [transferModalDomain, setTransferModalDomain] = useState(null);
  const [transferDetails, setTransferDetails] = useState(null);
  const [transferLoading, setTransferLoading] = useState(false);
  const [transferPushAccount, setTransferPushAccount] = useState("");
  const [transferActionLoading, setTransferActionLoading] = useState(false);

  const openDomainTransferModal = async (domainName) => {
    setTransferModalDomain(domainName);
    setTransferLoading(true);
    try {
      const data = await api.get(`/deployments/domains/${encodeURIComponent(domainName)}/transfer-details`, authToken ?? undefined);
      setTransferDetails(data);
    } catch (err) {
      toast.error("Failed to load registrar transfer details: " + err.message);
    } finally {
      setTransferLoading(false);
    }
  };

  const handleRequestEPP = async () => {
    if (!transferModalDomain) return;
    setTransferActionLoading(true);
    try {
      const res = await api.post(`/deployments/domains/${encodeURIComponent(transferModalDomain)}/request-epp`, {}, authToken ?? undefined);
      setTransferDetails(prev => ({ ...prev, transfer_auth_code: res.transfer_auth_code, transfer_lock: false, transfer_status: res.transfer_status }));
      toast.success("EPP Code generated and registry lock disabled!");
    } catch (err) {
      toast.error("Could not request EPP code: " + err.message);
    } finally {
      setTransferActionLoading(false);
    }
  };

  const handlePushGoDaddy = async () => {
    if (!transferModalDomain || !transferPushAccount.trim()) {
      toast.error("Please enter your GoDaddy Customer ID or Account Email.");
      return;
    }
    setTransferActionLoading(true);
    try {
      const res = await api.post(
        `/deployments/domains/${encodeURIComponent(transferModalDomain)}/push-godaddy-account`,
        { target_godaddy_account: transferPushAccount.trim(), target_email: transferPushAccount.trim() },
        authToken ?? undefined
      );
      setTransferDetails(prev => ({ ...prev, transfer_status: "account_push_submitted", pushed_to_account: res.pushed_to_account }));
      toast.success(res.message || "GoDaddy Account Push initiated!");
    } catch (err) {
      toast.error("Could not push domain: " + err.message);
    } finally {
      setTransferActionLoading(false);
    }
  };

  const getReceiptUrl = (item) => {
    if (item.orderId && item.orderId !== "undefined") {
      return `/dashboard/receipt/${item.orderId}`;
    }
    const found = orders.find(o =>
      o.status === "completed" &&
      (o.items?.some(i => i.id === item.id || i.template_id === item.template_id) || false)
    );
    return `/dashboard/receipt/${found ? found.id : "undefined"}`;
  };

  // Role syncing — only set default tab when URL has no explicit ?tab= override
  useEffect(() => {
    if (user) {
      setFullName(user.fullName || "");
      setUsername(user.username || "");
      setBio(user.bio || "");
      setAvatarUrl(user.avatar_url || "");
      setUserCountry(user.country || "");
      setUserCity(user.city || "");
      setUserCurrencyPref(user.currency || "USD");
      const tabParam = searchParams.get("tab");
      if (tabParam) {
        setActiveTab(tabParam);
      } else if (activeTab === "buyer-home") {
        if (isAdmin) {
          setActiveTab("admin-users");
        } else if (isSeller) {
          setActiveTab("seller-home");
        } else {
          setActiveTab("buyer-home");
        }
      }
      const activateOrderParam = searchParams.get("activate_order");
      if (activateOrderParam && authToken) {
        api.post(`/payment/activate-token-order/${activateOrderParam}`, {}, authToken)
          .then((res) => {
            alert(res?.message || "AI Tokens successfully credited to your account!");
            qc.invalidateQueries({ queryKey: ["billing-report"] });
            qc.invalidateQueries({ queryKey: ["orders"] });
          })
          .catch((e) => console.error("Error activating order:", e));
      }

      const deployTpl = searchParams.get("deployTemplate");
      const autoDeploy = searchParams.get("autoOpen");
      if (deployTpl) {
        setDeployTemplateId(deployTpl);
        if (autoDeploy === "true") {
          setIsDeployModalOpen(true);
        }
      }
    }
  }, [user, isAdmin, isSeller, searchParams]);

  // Sync My Templates sub-tab based on sidebar selection
  useEffect(() => {
    if (activeTab === "seller-templates") {
      setTemplatesSubTab("uploaded");
    } else if (activeTab === "buyer-templates") {
      setTemplatesSubTab("purchased");
    } else if (activeTab === "customized-files") {
      setTemplatesSubTab("customized");
    }
  }, [activeTab]);

  useEffect(() => {
    getToken().then(setAuthToken);
  }, [getToken]);

  useEffect(() => {
    const purchasedDomainId = searchParams.get("domain_id");
    if (!authToken || !purchasedDomainId) return;
    let stopped = false;
    let interval = null;
    const checkDomain = async () => {
      try {
        const status = await api.get(`/deployments/domains/${purchasedDomainId}/status`, authToken);
        if (stopped) return;
        if (status.verification_status === "verified") {
          stopped = true;
          if (interval) clearInterval(interval);
          qc.invalidateQueries(["deployments"]);
          const expiry = status.expires_at ? ` It expires on ${new Date(status.expires_at).toLocaleDateString()}; auto-renew is off, so contact Studio to arrange renewal or transfer before then.` : " Auto-renew is off, so contact Studio to arrange renewal or transfer before the domain expires.";
          const tls = status.ssl_status === "managed"
            ? " Studio manages HTTPS certificates; the first secure visit can take a short time while DNS and certificate issuance complete."
            : " HTTPS is not configured on this hosting server yet, so the domain is not ready for a secure public launch.";
          alert(`Domain ${status.domain} is registered and its DNS is configured.${expiry} DNS propagation may take time.${tls}`);
        } else if (["failed", "registration_failed", "refunded_registration_failed", "payment_failed", "checkout_expired"].includes(status.status)) {
          stopped = true;
          if (interval) clearInterval(interval);
          alert(`Domain purchase for ${status.domain} did not complete. Check the payment status or contact support if a charge was made.`);
        }
      } catch (error) {
        // Keep checking while GoDaddy's async registration operation is running.
      }
    };
    checkDomain();
    interval = setInterval(checkDomain, 5000);
    return () => { stopped = true; clearInterval(interval); };
  }, [authToken, searchParams, qc]);

  // Fetch actual admin users from backend when admin tab is active
  useEffect(() => {
    if (authToken && isAdmin) {
      fetch(`${API_BASE}/admin/users?page_size=100`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      })
        .then(res => res.json())
        .then(data => {
          if (data && data.items) {
            setAdminUsers(data.items.map(u => ({
              id: u.id,
              name: u.fullName || u.firstName || "Platform User",
              email: u.email,
              role: u.role,
              status: u.is_active !== false ? "Active" : "Suspended"
            })));
          }
        })
        .catch(err => console.error("Failed to load admin users", err));
    }
  }, [authToken, isAdmin]);

  // Fetch Dashboard Stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.get("/dashboard/stats", authToken ?? undefined),
    enabled: !!authToken,
    staleTime: 1000 * 60 * 3,
    placeholderData: (prev) => prev,
  });

  // Fetch User Orders/Purchases
  const { data: orders = [], isLoading: ordersLoading } = useQuery({
    queryKey: ["orders"],
    queryFn: () => api.get("/orders", authToken ?? undefined),
    enabled: !!authToken,
    staleTime: 1000 * 60 * 3,
    placeholderData: (prev) => prev,
  });

  // Fetch Full Consolidated Billing & Payment Report
  const { data: billingReport, isLoading: billingReportLoading, refetch: refetchBillingReport } = useQuery({
    queryKey: ["billing-report"],
    queryFn: () => api.get("/payment/billing-report", authToken ?? undefined),
    enabled: !!authToken,
    staleTime: 1000 * 60 * 2,
    placeholderData: (prev) => prev,
  });

  // Fetch Active User Subscription & Entitlements
  const { data: userSubData, isLoading: userSubLoading, refetch: refetchUserSub } = useQuery({
    queryKey: ["user-subscription"],
    queryFn: () => api.get("/subscriptions/my-subscription", authToken ?? undefined),
    enabled: !!authToken,
    staleTime: 1000 * 60 * 2,
  });

  // Fetch Usage Ledger
  const { data: usageData, isLoading: usageLoading } = useQuery({
    queryKey: ["subscription-usage"],
    queryFn: () => api.get("/subscriptions/usage", authToken ?? undefined),
    enabled: !!authToken,
    staleTime: 1000 * 60 * 2,
  });

  const cancelSubscriptionMutation = useMutation({
    mutationFn: () => api.post("/subscriptions/cancel", {}, authToken ?? undefined),
    onSuccess: (res) => {
      alert(res?.message || "Subscription scheduled for cancellation at the end of the billing period.");
      refetchUserSub();
    },
    onError: (err) => alert(err?.message || "Failed to cancel subscription"),
  });

  const reactivateSubscriptionMutation = useMutation({
    mutationFn: () => api.post("/subscriptions/reactivate", {}, authToken ?? undefined),
    onSuccess: (res) => {
      alert(res?.message || "Subscription reactivated successfully!");
      refetchUserSub();
    },
    onError: (err) => alert(err?.message || "Failed to reactivate subscription"),
  });

  // Fetch Wishlist Items
  const { data: wishlist = [], isLoading: wishlistLoading } = useQuery({
    queryKey: ["wishlist"],
    queryFn: () => api.get("/wishlist", authToken ?? undefined),
    enabled: !!authToken,
    staleTime: 1000 * 60 * 3,
    placeholderData: (prev) => prev,
  });

  // Fetch Followers
  const { data: followers = [], isLoading: followersLoading } = useQuery({
    queryKey: ["followers"],
    queryFn: () => api.get("/follows/followers", authToken ?? undefined),
    enabled: !!authToken && isSeller,
    staleTime: 1000 * 60 * 3,
    placeholderData: (prev) => prev,
  });

  // Fetch Following
  const { data: following = [], isLoading: followingLoading } = useQuery({
    queryKey: ["following"],
    queryFn: () => api.get("/follows/following", authToken ?? undefined),
    enabled: !!authToken,
    staleTime: 1000 * 60 * 3,
    placeholderData: (prev) => prev,
  });

  // Fetch Seller/Buyer Templates
  const { data: templateResponse, isLoading: templatesLoading } = useQuery({
    queryKey: ["seller-templates"],
    queryFn: () => api.get("/templates/my-templates", authToken ?? undefined),
    enabled: !!authToken,
    staleTime: 1000 * 60 * 3,
    placeholderData: (prev) => prev,
  });

  // Fetch Buyer Reviews
  const { data: buyerReviewsData, isLoading: buyerReviewsLoading } = useQuery({
    queryKey: ["buyer-reviews"],
    queryFn: () => api.get("/reviews/buyer?page_size=50", authToken ?? undefined),
    enabled: !!authToken,
    staleTime: 1000 * 60 * 3,
    placeholderData: (prev) => prev,
  });
  const buyerReviewsList = buyerReviewsData?.items || [];

  // Fetch Seller Reviews
  const { data: sellerReviewsData, isLoading: sellerReviewsLoading } = useQuery({
    queryKey: ["seller-reviews"],
    queryFn: () => api.get("/reviews/seller?page_size=50", authToken ?? undefined),
    enabled: !!authToken && isSeller,
    staleTime: 1000 * 60 * 3,
    placeholderData: (prev) => prev,
  });
  const sellerReviewsList = sellerReviewsData?.items || [];

  // Fetch Seller Earnings Summary
  const { data: earningsSummary = { total_earned: 0, withdrawn_amount: 0, pending_withdrawal: 0, available_balance: 0, sales: [] }, refetch: refetchEarnings } = useQuery({
    queryKey: ["seller-earnings"],
    queryFn: () => api.get("/payouts/earnings", authToken ?? undefined),
    enabled: !!authToken && isSeller,
    staleTime: 1000 * 60 * 3,
    placeholderData: (prev) => prev,
  });

  // Fetch Withdrawal Requests
  const { data: withdrawalRequests = [], refetch: refetchWithdrawals } = useQuery({
    queryKey: ["seller-withdrawals"],
    queryFn: () => api.get("/payouts/withdrawals", authToken ?? undefined),
    enabled: !!authToken && isSeller,
    staleTime: 1000 * 60 * 3,
    placeholderData: (prev) => prev,
  });

  // Delete Review Mutation
  const deleteReviewMutation = useMutation({
    mutationFn: (reviewId) => api.delete(`/reviews/${reviewId}`, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries(["buyer-reviews"]);
      qc.invalidateQueries(["seller-reviews"]);
      qc.invalidateQueries(["dashboard-stats"]);
      alert("Review deleted successfully!");
    },
  });

  // Create Review Mutation
  const createReviewMutation = useMutation({
    mutationFn: (data) => api.post("/reviews", data, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries(["buyer-reviews"]);
      qc.invalidateQueries(["seller-reviews"]);
      qc.invalidateQueries(["dashboard-stats"]);
      alert("Review submitted successfully!");
      setReviewModalOpen(false);
      // Reset form fields
      setReviewRating(5);
      setReviewTitle("");
      setReviewBody("");
      setReviewTemplateId("");
      setReviewTemplateTitle("");
    },
    onError: (err) => {
      setSubmitReviewError(err.message || "Failed to submit review");
    }
  });

  // Link Custom Domain Mutation
  const linkDomainMutation = useMutation({
    mutationFn: ({ deploymentId, customDomain }) =>
      api.patch(`/deployments/${deploymentId}/domain?custom_domain=${encodeURIComponent(customDomain)}`, {}, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries(["deployments"]);
      alert("Custom domain linked successfully!");
      setLinkDomainModalOpen(false);
      setCustomDomainInput("");
      setLinkDomainDeploymentId("");
    },
    onError: (err) => {
      setLinkDomainError(err.message || "Failed to link custom domain");
    }
  });

  // Unlink Custom Domain Mutation
  const unlinkDomainMutation = useMutation({
    mutationFn: (deploymentId) =>
      api.post(`/deployments/domains/disconnect`, { deployment_id: deploymentId }, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries(["deployments"]);
      refetchDeployments();
      alert("Custom domain disconnected successfully!");
    },
    onError: (err) => {
      alert("Failed to disconnect domain: " + err.message);
    }
  });

  // Toggle Domain Auto-Renewal Authority Mutation
  const toggleAutoRenewMutation = useMutation({
    mutationFn: ({ domain, autoRenew }) =>
      api.post(`/deployments/domains/auto-renew`, { domain, auto_renew: autoRenew }, authToken ?? undefined),
    onSuccess: (res) => {
      qc.invalidateQueries(["deployments"]);
      refetchDeployments();
      alert(res.message || "Domain auto-renewal authority updated successfully!");
    },
    onError: (err) => {
      alert("Failed to update auto-renewal authority: " + (err.message || "Error"));
    }
  });

  const handleVerifyDomain = async (deploymentId) => {
    setVerifyingDomainId(deploymentId);
    try {
      const res = await api.post(`/deployments/${deploymentId}/verify-domain`, {}, authToken ?? undefined);
      refetchDeployments();
      alert(res.message || "Custom domain verified and active!");
    } catch (err) {
      alert("Domain verification failed: " + (err.message || "DNS is still propagating"));
    } finally {
      setVerifyingDomainId("");
    }
  };

  // Fetch Marketplace Templates for Dashboard Recommendations
  const { data: marketplaceTemplatesRes } = useQuery({
    queryKey: ["marketplace-templates-dashboard"],
    queryFn: () => api.get("/templates?page_size=3"),
  });
  const recommendedTemplates = marketplaceTemplatesRes?.items || [];

  // Fetch Deployments with adaptive real-time polling
  const { data: deploymentsData = [], isLoading: deploymentsLoading, refetch: refetchDeployments } = useQuery({
    queryKey: ["deployments"],
    queryFn: () => api.get("/deployments", authToken ?? undefined),
    enabled: !!authToken,
    staleTime: 1000 * 2,
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasActive = Array.isArray(data) && data.some(d => d.status === "building" || d.status === "queued" || d.status === "deploying" || d.status === "created");
      return hasActive ? 1500 : 8000;
    },
    placeholderData: (prev) => prev,
  });

  // Auto-open live console logs if navigated from deploy page with ?deployed=...&openLogs=true
  useEffect(() => {
    const deployedId = searchParams.get("deployed");
    const shouldOpenLogs = searchParams.get("openLogs") === "true";
    if (deployedId && deploymentsData && deploymentsData.length > 0) {
      const match = deploymentsData.find((d) => d.id === deployedId);
      if (match) {
        setSelectedDeployment(match);
        setActiveConsoleLogs(match.logs || "");
        setActiveConsoleStatus(match.status);
        if (shouldOpenLogs) {
          setIsConsoleOpen(true);
        }
      }
    }
  }, [searchParams, deploymentsData]);

  // Set default deployment for domain connection
  useEffect(() => {
    if (deploymentsData && deploymentsData.length > 0 && !connectSelectedDeploymentId) {
      setConnectSelectedDeploymentId(deploymentsData[0].id);
    }
  }, [deploymentsData, connectSelectedDeploymentId]);

  // Initial GoDaddy suggestions search
  useEffect(() => {
    if (deploymentsData && deploymentsData.length > 0 && godaddySearchResults.length === 0 && !godaddySearching) {
      const pName = deploymentsData[0].project_name || "mysite";
      handleSearchGoDaddy(pName);
    }
  }, [deploymentsData]);

  // Selected deployment for domain analysis & purchasing
  const selectedTargetDeployment = useMemo(() => {
    if (!deploymentsData || deploymentsData.length === 0) return null;
    return deploymentsData.find((d) => d.id === connectSelectedDeploymentId) || deploymentsData[0];
  }, [deploymentsData, connectSelectedDeploymentId]);

  // Filtered deployments for dashboard search & status filters
  const filteredDeployments = useMemo(() => {
    if (!deploymentsData || !Array.isArray(deploymentsData)) return [];
    return deploymentsData.filter((deploy) => {
      if (deploymentStatusFilter !== "all") {
        const isLive = deploy.status === "live" || deploy.status === "success";
        const isBuilding = deploy.status === "building" || deploy.status === "queued" || deploy.status === "deploying";
        const isSuspended = deploy.status === "suspended" || deploy.is_suspended;
        const isFailed = deploy.status === "failed";

        if (deploymentStatusFilter === "live" && !isLive) return false;
        if (deploymentStatusFilter === "building" && !isBuilding) return false;
        if (deploymentStatusFilter === "suspended" && !isSuspended) return false;
        if (deploymentStatusFilter === "failed" && !isFailed) return false;
      }

      if (!deploymentSearchQuery.trim()) return true;
      const q = deploymentSearchQuery.toLowerCase().trim();
      const nameMatch = (deploy.project_name || "").toLowerCase().includes(q);
      const siteIdMatch = (deploy.site_id || "").toLowerCase().includes(q);
      const domainMatch = (deploy.custom_domain || "").toLowerCase().includes(q);
      const subMatch = (deploy.subdomain || "").toLowerCase().includes(q);
      const provMatch = (deploy.provider || "").toLowerCase().includes(q);
      return nameMatch || siteIdMatch || domainMatch || subMatch || provMatch;
    });
  }, [deploymentsData, deploymentSearchQuery, deploymentStatusFilter]);

  const handleSelectTargetDeployment = (dep) => {
    if (!dep) return;
    setConnectSelectedDeploymentId(dep.id);
    const cleanProj = (dep.project_name || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    if (cleanProj) {
      setGodaddySearchQuery(cleanProj);
      handleSearchGoDaddy(cleanProj);
    }
  };

  const handleSearchGoDaddy = async (rawQuery) => {
    const q = (rawQuery ?? godaddySearchQuery ?? "mystudio").trim().toLowerCase().replace(/[^a-z0-9.-]/g, "").replace(/^\.+|\.+$/g, "");
    if (!q) return;
    setGodaddySearching(true);
    setGodaddySearchError("");
    try {
      const res = await api.get(`/deployments/domains/suggestions?query=${encodeURIComponent(q)}&limit=6`, authToken ?? undefined);
      if (Array.isArray(res) && res.length > 0) {
        setGodaddySearchResults(res);
      } else {
        setGodaddySearchResults([
          { domain: `${q}.com`, available: true, price: { currencyCode: "USD", value: 1099 }, renewalPrice: { currencyCode: "USD", value: 1299 } },
          { domain: `${q}.in`, available: true, price: { currencyCode: "USD", value: 849 }, renewalPrice: { currencyCode: "USD", value: 999 } },
          { domain: `${q}.co`, available: true, price: { currencyCode: "USD", value: 1199 }, renewalPrice: { currencyCode: "USD", value: 1499 } },
          { domain: `${q}.online`, available: true, price: { currencyCode: "USD", value: 499 }, renewalPrice: { currencyCode: "USD", value: 699 } },
          { domain: `${q}.tech`, available: true, price: { currencyCode: "USD", value: 599 }, renewalPrice: { currencyCode: "USD", value: 799 } },
        ]);
      }
    } catch (err) {
      console.warn("GoDaddy suggestions query fallback:", err);
      setGodaddySearchResults([
        { domain: `${q}.com`, available: true, price: { currencyCode: "USD", value: 1099 }, renewalPrice: { currencyCode: "USD", value: 1299 } },
        { domain: `${q}.in`, available: true, price: { currencyCode: "USD", value: 849 }, renewalPrice: { currencyCode: "USD", value: 999 } },
        { domain: `${q}.co`, available: true, price: { currencyCode: "USD", value: 1199 }, renewalPrice: { currencyCode: "USD", value: 1499 } },
        { domain: `${q}.online`, available: true, price: { currencyCode: "USD", value: 499 }, renewalPrice: { currencyCode: "USD", value: 699 } },
      ]);
    } finally {
      setGodaddySearching(false);
    }
  };

  const handleCheckDomainChallenge = async (domainVal) => {
    const clean = (domainVal || connectDomainName || "").toLowerCase().replace("https://", "").replace("http://", "").trim().replace(/\/+$/, "");
    if (!clean || !clean.includes(".") || clean.length < 4) {
      setDomainChallengeData(null);
      return;
    }
    setChallengeLoading(true);
    setOwnershipMessage(null);
    try {
      const challenge = await api.post("/deployments/domains/challenge", { domain: clean }, authToken ?? undefined);
      setDomainChallengeData(challenge);
      if (challenge?.is_protected) {
        setOwnershipMessage({
          type: "error",
          text: challenge.security_warning || `Security Block: '${clean}' is a protected global domain and cannot be linked.`
        });
      } else if (challenge?.is_claimed_by_other) {
        if (challenge?.other_verified) {
          setOwnershipMessage({
            type: "error",
            text: `⚠️ This domain is already registered and verified by another user on the platform. If this is your domain, please add the TXT ownership challenge below to verify and transfer ownership.`
          });
        } else {
          setOwnershipMessage({
            type: "warning",
            text: `ℹ️ Another account previously attempted to link this domain without verification. You can claim it by verifying your DNS records below.`
          });
        }
      } else if (challenge?.is_verified) {
        setOwnershipMessage({
          type: "success",
          text: `✅ DNS Ownership Verified! All required DNS records are active in public DNS. Click "Verify Ownership & Connect" below to complete connection.`
        });
      }
    } catch (err) {
      setOwnershipMessage({ type: "error", text: err.message || "Failed to inspect domain ownership." });
    } finally {
      setChallengeLoading(false);
    }
  };

  const handleVerifyOwnershipAndConnect = async (e) => {
    if (e) e.preventDefault();
    const clean = (connectDomainName || "").toLowerCase().replace("https://", "").replace("http://", "").trim().replace(/\/+$/, "");
    if (!clean || !clean.includes(".") || clean.length < 4) {
      setOwnershipMessage({ type: "error", text: "Please enter a valid domain name (e.g. 'mycompany.com')." });
      return;
    }
    if (!connectSelectedDeploymentId) {
      setOwnershipMessage({ type: "error", text: "Please select an active website deployment to link this domain to." });
      return;
    }

    setVerifyingOwnershipLoading(true);
    setOwnershipMessage(null);
    try {
      const res = await api.post("/deployments/domains/verify-ownership", {
        domain: clean,
        deployment_id: connectSelectedDeploymentId
      }, authToken ?? undefined);

      if (res?.success) {
        setOwnershipMessage({ type: "success", text: res.message || `Domain "${clean}" ownership verified & connected successfully!` });
        qc.invalidateQueries(["deployments"]);
        setConnectDomainName("");
        setDomainChallengeData(null);
      } else {
        setOwnershipMessage({ type: "error", text: res.message || "Ownership could not be confirmed. Check your DNS records." });
      }
    } catch (err) {
      setOwnershipMessage({ type: "error", text: err.message || "Domain ownership verification failed." });
    } finally {
      setVerifyingOwnershipLoading(false);
    }
  };

  const { data: deploymentProviderData } = useQuery({
    queryKey: ["deployment-providers"],
    queryFn: () => api.get("/deployments/providers", authToken ?? undefined),
    enabled: !!authToken,
  });

  useEffect(() => {
    if (isDeployModalOpen && authToken) {
      api.get("/deployments/hosting-price", authToken)
        .then(setHostingPrice)
        .catch(() => setHostingPrice({ configured: false }));
    }
  }, [isDeployModalOpen, authToken]);

  useEffect(() => {
    const providers = deploymentProviderData?.providers || [];
    if (providers.some((provider) => provider.id === deployProvider && provider.enabled)) return;
    const enabledProvider = providers.find((provider) => provider.id === deploymentProviderData?.default_provider && provider.enabled)
      || providers.find((provider) => provider.enabled);
    if (enabledProvider) setDeployProvider(enabledProvider.id);
  }, [deploymentProviderData, deployProvider]);

  // Strip ANSI escape codes from terminal output
  const stripAnsi = (str) => str.replace(/\x1B\[[0-9;]*[mGKHFJABCDETSTNHR]/g, "").replace(/\x1B[()][AB012]/g, "");

  // Live continuous log polling for build and live runtime telemetry
  useEffect(() => {
    let intervalId;
    if (isConsoleOpen && selectedDeployment?.id) {
      const fetchLogs = async () => {
        if (isConsoleStreamPaused) return;
        try {
          const data = await api.get(`/deployments/${selectedDeployment.id}`, authToken ?? undefined);
          if (data) {
            setActiveConsoleLogs(data.logs || "");
            setActiveConsoleStatus(data.status);
            setSelectedDeployment(prev => prev ? { ...prev, ...data } : data);
          }
        } catch (err) {
          console.error("Failed to fetch deployment logs:", err);
        }
      };

      fetchLogs();
      intervalId = setInterval(fetchLogs, 1400);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isConsoleOpen, selectedDeployment?.id, authToken, isConsoleStreamPaused]);

  // Auto-scroll build console to bottom
  useEffect(() => {
    if (consoleEndRef.current && !isConsoleStreamPaused) {
      consoleEndRef.current.scrollTop = consoleEndRef.current.scrollHeight;
    }
  }, [activeConsoleLogs, isConsoleOpen, isConsoleStreamPaused]);

  // Published seller listings are kept separate from private Studio Project drafts using explicit is_marketplace separation.
  const sellerTemplatesList = Array.isArray(templateResponse)
    ? templateResponse.filter(t => t.is_marketplace === true && t.template_origin === "marketplace")
    : [];

  // 1. Downloaded & Purchased Templates (from completed orders)
  const purchasedTemplatesList = orders
    .filter(o => o.status === "completed")
    .flatMap(o => (o.items || []).map(i => ({
      id: i.template_id || i.id,
      title: i.title || i.template?.title || "Downloaded Template",
      framework: i.framework || i.template?.framework || "HTML",
      source: "Downloaded Template",
      category: "downloaded"
    })));

  // 2. Seller Uploaded Templates (from /templates/my-templates)
  const sellerUploadedTemplatesList = sellerTemplatesList.map(t => ({
    id: t.id,
    title: t.title || "Uploaded Template",
    framework: t.framework || "HTML",
    source: "Uploaded Template",
    category: "uploaded"
  }));

  // 3. AI Studio Projects (strictly projects generated by AI Studio Creator)
  const studioProjectsList = (templateResponse || [])
    .filter(t => isStudioProjectItem(t))
    .map(t => ({
      id: t.id,
      title: t.title || "Studio Project",
      framework: t.framework || "HTML",
      source: "Studio Project",
      category: "studio"
    }));

  // Categorized maps to preserve item sources accurately
  const downloadedMap = new Map();
  purchasedTemplatesList.forEach(t => { if (t && t.id) downloadedMap.set(t.id, t); });
  const downloadedList = Array.from(downloadedMap.values());

  const uploadedMap = new Map();
  sellerUploadedTemplatesList.forEach(t => { if (t && t.id) uploadedMap.set(t.id, t); });
  const uploadedList = Array.from(uploadedMap.values());

  const studioMap = new Map();
  studioProjectsList.forEach(t => { if (t && t.id) studioMap.set(t.id, t); });
  const studioList = Array.from(studioMap.values());

  // Master combined deployable list
  const masterMap = new Map();
  [...studioList, ...uploadedList, ...downloadedList].forEach(t => {
    if (t && t.id && !masterMap.has(t.id)) masterMap.set(t.id, t);
  });
  const availableTemplatesForDeployment = Array.from(masterMap.values());

  const sellerTotalViews = sellerTemplatesList.reduce((sum, t) => sum + (t.views_count || 0), 0);
  const sellerTotalDownloads = sellerTemplatesList.reduce((sum, t) => sum + (t.downloads_count || 0), 0);
  const sellerTotalSalesCount = (earningsSummary?.sales || []).length;
  const sellerRatedTemplates = sellerTemplatesList.filter(t => (t.rating_count || 0) > 0);
  const sellerActualAvgRating = sellerReviewsList.length > 0
    ? (sellerReviewsList.reduce((sum, r) => sum + (r.rating || 0), 0) / sellerReviewsList.length).toFixed(1)
    : sellerRatedTemplates.length > 0
      ? (sellerRatedTemplates.reduce((sum, t) => sum + (t.rating_avg || 0), 0) / sellerRatedTemplates.length).toFixed(1)
      : null;
  const sellerConversionRate = (sellerTotalViews > 0 && sellerTotalSalesCount > 0)
    ? ((sellerTotalSalesCount / sellerTotalViews) * 100).toFixed(1) + "%"
    : "0.0%";

  // Auto-select first available downloaded template if none selected or mock selected
  useEffect(() => {
    if (availableTemplatesForDeployment.length > 0 && (!deployTemplateId || deployTemplateId === "mock-project-id")) {
      const first = availableTemplatesForDeployment[0];
      setDeployTemplateId(first.id);
      setDeployProjectName(first.title);
    }
  }, [availableTemplatesForDeployment, deployTemplateId]);

  // Auto-detect build configurations based on selected template framework
  useEffect(() => {
    if (!deployTemplateId) return;

    if (deployTemplateId === "mock-project-id") {
      setDeployBranch("main");
      setDeployBuildCommand("none");
      setDeployOutputDir(".");
      return;
    }

    const matched = availableTemplatesForDeployment.find(t => t.id === deployTemplateId);
    if (!matched) {
      setDeployBranch("main");
      setDeployBuildCommand("npm run build");
      setDeployOutputDir("dist");
      return;
    }

    const fw = (matched.framework || "").toLowerCase();
    if (fw === "nextjs" || fw === "next") {
      setDeployBranch("main");
      setDeployBuildCommand("npm run build");
      setDeployOutputDir(".next");
    } else if (fw === "html" || fw === "vanilla" || fw === "static") {
      setDeployBranch("main");
      setDeployBuildCommand("none");
      setDeployOutputDir(".");
    } else if (fw === "nuxt" || fw === "nuxtjs") {
      setDeployBranch("main");
      setDeployBuildCommand("npm run build");
      setDeployOutputDir(".output/public");
    } else {
      // React, Vue, Svelte, Vite-based
      setDeployBranch("main");
      setDeployBuildCommand("npm run build");
      setDeployOutputDir("dist");
    }
  }, [deployTemplateId, sellerTemplatesList]);

  // Fetch categories
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get("/categories"),
  });

  // Delete Template Mutation
  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/templates/${id}`, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries(["seller-templates"]);
      qc.invalidateQueries(["admin-all-templates"]);
      qc.invalidateQueries(["templates"]);
      qc.invalidateQueries(["buyer-templates"]);
      alert("Project deleted successfully!");
    },
    onError: (err) => {
      alert(`Failed to delete project: ${err?.message || "An unexpected error occurred"}`);
    }
  });

  // Fetch all templates for admin console
  const { data: adminTemplates = [], isLoading: adminTemplatesLoading } = useQuery({
    queryKey: ["admin-all-templates"],
    queryFn: () => api.get("/admin/templates", authToken ?? undefined),
    enabled: !!authToken && isAdmin,
  });

  // Fetch all orders/payout logs for admin
  const { data: adminOrders = [], isLoading: adminOrdersLoading } = useQuery({
    queryKey: ["admin-orders"],
    queryFn: () => api.get("/admin/orders", authToken ?? undefined),
    enabled: !!authToken && isAdmin,
  });

  const filteredAdminOrders = (adminOrders || []).filter((ord) => {
    if (!adminInvoiceSearch?.trim()) return true;
    const q = adminInvoiceSearch.toLowerCase();
    const inv = (ord.invoice_number || ord.order_number || "").toLowerCase();
    const email = (ord.buyer_email || "").toLowerCase();
    const name = (ord.buyer_name || "").toLowerCase();
    const items = (Array.isArray(ord.items) ? ord.items.join(" ") : String(ord.items || "")).toLowerCase();
    return inv.includes(q) || email.includes(q) || name.includes(q) || items.includes(q);
  });

  // Mutate Template status (Approval Queue)
  const updateTemplateStatusMutation = useMutation({
    mutationFn: ({ templateId, status }) =>
      api.patch(`/admin/templates/${templateId}/status?status=${status}`, {}, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries(["admin-all-templates"]);
      qc.invalidateQueries(["dashboard-stats"]);
      alert("Template review status updated!");
    },
  });

  // Admin silent status update (for AdminModerationHub with its own toast)
  const adminUpdateTemplateStatusMutation = useMutation({
    mutationFn: ({ templateId, status }) =>
      api.patch(`/admin/templates/${templateId}/status?status=${status}`, {}, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries(["admin-all-templates"]);
      qc.invalidateQueries(["dashboard-stats"]);
    },
  });

  // Admin batch status update
  const batchUpdateTemplateStatusMutation = useMutation({
    mutationFn: ({ templateIds, status }) =>
      api.post(`/admin/templates/batch-status`, { template_ids: templateIds, status }, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries(["admin-all-templates"]);
      qc.invalidateQueries(["dashboard-stats"]);
    },
  });

  // Admin silent delete (for AdminModerationHub with its own toast)
  const adminDeleteTemplateMutation = useMutation({
    mutationFn: (templateId) => api.delete(`/templates/${templateId}`, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries(["seller-templates"]);
      qc.invalidateQueries(["admin-all-templates"]);
      qc.invalidateQueries(["templates"]);
      qc.invalidateQueries(["buyer-templates"]);
    },
  });

  // Download Trigger Mutation
  const triggerDownload = useMutation({
    mutationFn: ({ templateId, format }) =>
      api.post(
        `/templates/${templateId}/download?format=${format}`,
        {},
        authToken ?? undefined
      ),
    onSuccess: async (data, variables) => {
      if (data?.download_url) {
        let downloadUrl = data.download_url;
        if (downloadUrl.startsWith("/")) {
          downloadUrl = `${window.location.origin}${downloadUrl}`;
        }
        if (authToken && !downloadUrl.includes("token=")) {
          const sep = downloadUrl.includes("?") ? "&" : "?";
          downloadUrl = `${downloadUrl}${sep}token=${encodeURIComponent(authToken)}`;
        }

        try {
          // Direct authenticated stream download for clean instant saving without popup blocker
          const res = await fetch(downloadUrl, {
            headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
          });
          if (res.ok) {
            const blob = await res.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.style.display = "none";
            a.href = blobUrl;

            const disposition = res.headers.get("content-disposition");
            let filename = `template-${variables?.templateId || "source"}.zip`;
            if (disposition && disposition.includes("filename=")) {
              const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
              if (match && match[1]) {
                filename = match[1].replace(/['"]/g, "").trim();
              }
            }
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
              window.URL.revokeObjectURL(blobUrl);
              a.remove();
            }, 1000);
            return;
          }
        } catch (err) {
          console.warn("Direct blob download failed, falling back to window open:", err);
        }

        // Fallback: window navigation
        window.open(downloadUrl, "_blank");
      }
    },
    onError: (err) => {
      const errorMsg = err?.response?.data?.detail || err?.detail || err?.message || "Failed to download template source code.";
      alert(errorMsg);
    },
  });

  const [downloadWarningTarget, setDownloadWarningTarget] = useState(null);

  const requestDownloadWithWarning = (item, format = "zip") => {
    if (!item) return;
    setDownloadWarningTarget({
      id: item.template_id || item.id,
      title: item.title || "Template Source Package",
      format: format,
    });
  };

  const handleConfirmDownload = () => {
    if (!downloadWarningTarget) return;
    triggerDownload.mutate({
      templateId: downloadWarningTarget.id,
      format: downloadWarningTarget.format || "zip",
    });
    setDownloadWarningTarget(null);
  };

  // Avatar Upload handler
  const handleAvatarUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploadingAvatar(true);
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_BASE}/files/upload`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${authToken}`
        },
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to upload avatar");
      }

      const data = await res.json();
      setAvatarUrl(resolveMediaUrl(data.url));
      alert("Avatar uploaded successfully! Click 'Save Changes' to update your profile.");
    } catch (err) {
      console.error(err);
      alert(err.message);
    } finally {
      setUploadingAvatar(false);
    }
  };

  // Profile Update handler
  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    try {
      setSavingProfile(true);
      const res = await fetch(`${API_BASE}/auth/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({
          full_name: fullName,
          username: username,
          bio: bio,
          avatar_url: avatarUrl,
          country: userCountry,
          city: userCity,
          currency: userCurrencyPref,
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to update profile details");
      }
      // Refresh profile data and active viewing currency
      await useAuthStore.getState().fetchProfile();
      useCurrencyStore.getState().setUserCurrency(userCurrencyPref);
    } catch (err) {
      console.error(err);
      alert(err.message);
    } finally {
      setSavingProfile(false);
    }
  };

  const handleUpdatePayout = async (e) => {
    e.preventDefault();
    if (!payoutBankName || !payoutAccountNumber || !payoutIfscCode || !payoutAccountHolderName) {
      alert("All bank account fields are required.");
      return;
    }
    try {
      setSavingPayout(true);
      const res = await fetch(`${API_BASE}/auth/payout-account`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({
          payout_bank_name: payoutBankName,
          payout_account_number: payoutAccountNumber,
          payout_ifsc_code: payoutIfscCode,
          payout_account_holder_name: payoutAccountHolderName
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to update payout details");
      }
      // Refresh profile data
      await useAuthStore.getState().fetchProfile();
      setPayoutEditing(false);
      alert("Payout details saved successfully! You are now eligible to sell templates.");
    } catch (err) {
      console.error(err);
      alert(err.message);
    } finally {
      setSavingPayout(false);
    }
  };


  // --- SELLER FORMS & WIZARD STATE ---
  const [wizardStep, setWizardStep] = useState(1);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [shortDesc, setShortDesc] = useState("");
  const [desc, setDesc] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [subCategory, setSubCategory] = useState("");
  const [industryFocus, setIndustryFocus] = useState("");
  const [framework, setFramework] = useState("html");
  const [version, setVersion] = useState("1.0.0");
  const [isHtmlMode, setIsHtmlMode] = useState(false);
  const [detectedVersion, setDetectedVersion] = useState("");
  const [detectedFramework, setDetectedFramework] = useState("");
  const [price, setPrice] = useState("49");
  const [priceCurrency, setPriceCurrency] = useState("USD");
  const [salePrice, setSalePrice] = useState("");
  const [premium, setPremium] = useState(true);
  const [licenseType, setLicenseType] = useState("standard");
  const [tags, setTags] = useState("");
  const [demoUrl, setDemoUrl] = useState("");
  const [metaTitle, setMetaTitle] = useState("");
  const [metaDesc, setMetaDesc] = useState("");
  const [keywords, setKeywords] = useState("");
  const [zipFile, setZipFile] = useState(null);
  const [folderFiles, setFolderFiles] = useState(null);
  const [videoFile, setVideoFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [thumbnailFile, setThumbnailFile] = useState(null);
  const [galleryFiles, setGalleryFiles] = useState([]);
  const [galleryPreviews, setGalleryPreviews] = useState([]);

  const handleAddDashboardGalleryFiles = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setGalleryFiles((prev) => [...prev, ...files]);
    const newPreviews = files.map((f) => URL.createObjectURL(f));
    setGalleryPreviews((prev) => [...prev, ...newPreviews]);
  };

  const handleRemoveDashboardGalleryFile = (idxToRemove) => {
    setGalleryFiles((prev) => prev.filter((_, i) => i !== idxToRemove));
    setGalleryPreviews((prev) => prev.filter((_, i) => i !== idxToRemove));
  };

  // ── 9-step wizard extended state ──────────────────────────────────────────
  const [wizardCategory, setWizardCategory] = useState("");
  const [wizardSubCategory, setWizardSubCategory] = useState("");
  const [wizardIndustry, setWizardIndustry] = useState([]);
  const [wizardCssFw, setWizardCssFw] = useState("Tailwind");
  const [wizardBackend, setWizardBackend] = useState("None");
  const [wizardDb, setWizardDb] = useState("No Database");
  const [wizardPages, setWizardPages] = useState([]);
  const [wizardFeatures, setWizardFeatures] = useState([]);
  const [wizardDesignStyle, setWizardDesignStyle] = useState("");
  const [wizardPrimaryColor, setWizardPrimaryColor] = useState("#c89666");
  const [wizardAccentColor, setWizardAccentColor] = useState("#10b981");
  const [wizardFont, setWizardFont] = useState("Inter");
  const [wizardLayout, setWizardLayout] = useState("");
  const [wizardCoverImage, setWizardCoverImage] = useState(null);
  const [wizardTargetAudience, setWizardTargetAudience] = useState([]);
  const [wizardBusinessTypes, setWizardBusinessTypes] = useState([]);
  const [wizardMood, setWizardMood] = useState("");
  const [wizardConversionGoal, setWizardConversionGoal] = useState("");

  const [uploadType, setUploadType] = useState("zip"); // "zip" or "git"
  const [hasInitializedUploadType, setHasInitializedUploadType] = useState(false);

  useEffect(() => {
    if (user && !hasInitializedUploadType) {
      const tab = new URLSearchParams(window.location.search).get("tab");
      if (tab === "seller-upload" || user?.has_github_token) {
        setUploadType("git");
      }
      setHasInitializedUploadType(true);
    }
  }, [user, hasInitializedUploadType]);

  useEffect(() => {
    if (user?.currency) {
      setPriceCurrency(user.currency);
    }
  }, [user?.currency]);
  const [gitUrl, setGitUrl] = useState("");
  const [storedZipUrl, setStoredZipUrl] = useState("");
  const [githubUsername, setGithubUsername] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [fetchedRepos, setFetchedRepos] = useState([]);
  const [fetchingRepos, setFetchingRepos] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisLogs, setAnalysisLogs] = useState([]);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [isIncompleteAnalysis, setIsIncompleteAnalysis] = useState(false);

  // Coupons
  const [coupons, setCoupons] = useState([]);
  const [newCouponCode, setNewCouponCode] = useState("");
  const [newCouponDiscount, setNewCouponDiscount] = useState("20");
  const [newCouponLimit, setNewCouponLimit] = useState("100");

  // Customer Messages Inbox
  const [messages, setMessages] = useState([]);
  const [activeMessageId, setActiveMessageId] = useState(null);
  const [replyText, setReplyText] = useState("");

  // Payout options
  const [payoutBankName, setPayoutBankName] = useState("");
  const [payoutAccountNumber, setPayoutAccountNumber] = useState("");
  const [payoutIfscCode, setPayoutIfscCode] = useState("");
  const [payoutAccountHolderName, setPayoutAccountHolderName] = useState("");
  const [savingPayout, setSavingPayout] = useState(false);
  const [payoutEditing, setPayoutEditing] = useState(false);
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const createWithdrawal = useMutation({
    mutationFn: (data) => api.post("/payouts/withdrawals", data, authToken ?? undefined),
    onSuccess: () => {
      alert("Withdrawal request submitted successfully!");
      setWithdrawAmount("");
      refetchEarnings();
      refetchWithdrawals();
    },
    onError: (err) => {
      console.error(err);
      alert(err.message || err.detail || "Failed to submit withdrawal request. Please check your bank details.");
    }
  });

  useEffect(() => {
    if (user) {
      setPayoutBankName(user.payout_bank_name || "");
      setPayoutAccountNumber(user.payout_account_number || "");
      setPayoutIfscCode(user.payout_ifsc_code || "");
      setPayoutAccountHolderName(user.payout_account_holder_name || "");
    }
  }, [user]);

  // Custom prompt generator tool
  const [aiPrompt, setAiPrompt] = useState("");
  const [generatingMockup, setGeneratingMockup] = useState(false);
  const [aiGeneratedResult, setAiGeneratedResult] = useState(null);

  // Admin users ledger
  const [adminUsers, setAdminUsers] = useState([]);

  // Admin moderation queue
  const [adminQueue, setAdminQueue] = useState([]);

  const uploadFileHelper = async (fileObj, name) => {
    if (!fileObj) return "";
    const uploadForm = new FormData();
    uploadForm.append("file", fileObj);
    const res = await fetch(`${API_BASE}/files/upload`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${authToken}`
      },
      body: uploadForm
    });
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || `Failed to upload ${name}`);
    }
    const data = await res.json();
    return resolveMediaUrl(data.url);
  };

  const handleZipAnalysis = async (file) => {
    if (!file) return;
    setZipFile(file);
    setAnalysisLoading(true);
    setAnalysisProgress(0);
    setAnalysisLogs([]);
    setAnalysisResult(null);
    setWizardStep(2);

    const logsList = [
      "Reading files...",
      "Detecting framework...",
      "Finding pages...",
      "Scanning images...",
      "Checking responsiveness...",
      "Finding SEO...",
      "Finding accessibility...",
      "Generating description..."
    ];

    let currentLogIndex = 0;
    const interval = setInterval(() => {
      if (currentLogIndex < logsList.length) {
        setAnalysisLogs(prev => [...prev, logsList[currentLogIndex]]);
        setAnalysisProgress(prev => Math.min(prev + 12, 95));
        currentLogIndex++;
      }
    }, 450);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_BASE}/templates/analyze-zip`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${authToken}`
        },
        body: formData
      });

      clearInterval(interval);

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to analyze ZIP file");
      }

      const data = await res.json();
      if (!data.success) {
        throw new Error(data.error || "ZIP analysis failed");
      }

      setAnalysisLogs(prev => [...prev, "Running Security & Link Quality Audit Scanner..."]);
      try {
        const auditRes = await fetch(`${API_BASE}/templates/audit`, {
          method: "POST",
          headers: { "Authorization": `Bearer ${authToken}` },
          body: formData
        });
        if (auditRes.ok) {
          const auditData = await auditRes.json();
          data.audit_report = auditData;
          setAnalysisLogs(prev => [...prev, `Security Score: ${auditData.score}% — Link Health: ${auditData.link_health_pass ? 'PASSED' : 'CHECK'}`]);
        }
      } catch (err) {
        console.warn("Audit call warning:", err);
      }

      setAnalysisLogs(prev => [...prev, "Project audit complete!"]);
      setAnalysisProgress(100);
      setAnalysisResult(data);

      setTitle(data.project_name || "");
      setSlug((data.project_name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-"));
      setShortDesc(data.ai_description || "");
      setDesc(data.ai_description || "");

      const fw = (data.framework_detected || "html").toLowerCase();
      let matchedFw = "html";
      if (fw.includes("next")) matchedFw = "nextjs";
      else if (fw.includes("react")) matchedFw = "react";
      else if (fw.includes("nuxt")) matchedFw = "nuxt";
      else if (fw.includes("vue")) matchedFw = "vue";
      else if (fw.includes("astro")) matchedFw = "astro";
      else if (fw.includes("angular")) matchedFw = "angular";
      else if (fw.includes("svelte")) matchedFw = "svelte";
      else if (fw.includes("tailwind")) matchedFw = "tailwind";
      else matchedFw = "html";

      setFramework(matchedFw);
      setDetectedFramework(data.framework_detected || (matchedFw === "html" ? "HTML5" : matchedFw));

      const detVer = data.code_version || data.version || data.framework_version || (matchedFw === "html" ? "1.0.0" : "1.0.0");
      setVersion(detVer);
      setDetectedVersion(detVer);
      setIsHtmlMode(matchedFw === "html" || !!data.is_html_only);

      setTags(data.ai_tags ? data.ai_tags.join(", ") : "");
      setKeywords(data.ai_tags ? data.ai_tags.slice(0, 4).join(", ") : "");
      setMetaTitle((data.project_name || "") + " - Website Template");
      setMetaDesc(data.ai_description || "");

      if (data.sub_category) {
        setSubCategory(data.sub_category);
      }
      if (data.industry) {
        setIndustryFocus(Array.isArray(data.industry) ? data.industry.join(", ") : data.industry);
      }

      let categoryMatched = false;
      if (data.categories && categories.length > 0) {
        const sortedCats = Object.entries(data.categories).sort((a, b) => b[1] - a[1]);
        const highestCategoryName = sortedCats[0]?.[0];
        if (highestCategoryName) {
          const matched = categories.find(c => c.name.toLowerCase() === highestCategoryName.toLowerCase());
          if (matched) {
            setCategoryId(matched.id);
            categoryMatched = true;
          } else {
            setCategoryId("");
          }
        } else {
          setCategoryId("");
        }
      } else {
        setCategoryId("");
      }

      const isZipIncomplete =
        !data.project_name ||
        !data.ai_description ||
        !data.framework_detected ||
        !data.categories ||
        Object.keys(data.categories).length === 0 ||
        !categoryMatched;

      setIsIncompleteAnalysis(isZipIncomplete);

    } catch (err) {
      clearInterval(interval);
      console.error(err);
      alert(err.message);
      setWizardStep(1);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleGitAnalysis = async (urlToAnalyze) => {
    const targetUrl = urlToAnalyze || gitUrl;
    if (!targetUrl) {
      alert("Please enter a Git repository URL.");
      return;
    }
    setAnalysisLoading(true);
    setAnalysisProgress(0);
    setAnalysisLogs([]);
    setAnalysisResult(null);
    setWizardStep(2);

    const logsList = [
      "Connecting to Git host...",
      "Cloning repository (depth=1)...",
      "Scanning repository tree...",
      "Filtering target source files...",
      "Generating clean ZIP archive...",
      "Analyzing framework configurations...",
      "Checking responsiveness rules...",
      "Auditing SEO parameters...",
      "Validating accessibility markers...",
      "Running code & architecture assessment..."
    ];

    let currentLogIndex = 0;
    const interval = setInterval(() => {
      if (currentLogIndex < logsList.length) {
        setAnalysisLogs(prev => [...prev, logsList[currentLogIndex]]);
        setAnalysisProgress(prev => Math.min(prev + 10, 95));
        currentLogIndex++;
      }
    }, 600);

    try {
      const res = await fetch(`${API_BASE}/templates/analyze-git`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({ git_url: targetUrl })
      });

      clearInterval(interval);

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to clone and analyze Git repository");
      }

      const data = await res.json();
      if (!data.success) {
        throw new Error(data.error || "Git repo analysis failed");
      }

      setAnalysisLogs(prev => [...prev, "Project audit complete!"]);
      setAnalysisProgress(100);
      setAnalysisResult(data);

      setTitle(data.project_name || "");
      setSlug((data.project_name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-"));
      setShortDesc(data.ai_description || "");
      setDesc(data.ai_description || "");

      const fw = (data.framework_detected || "html").toLowerCase();
      let matchedFw = "html";
      if (fw.includes("next")) matchedFw = "nextjs";
      else if (fw.includes("react")) matchedFw = "react";
      else if (fw.includes("nuxt")) matchedFw = "nuxt";
      else if (fw.includes("vue")) matchedFw = "vue";
      else if (fw.includes("astro")) matchedFw = "astro";
      else if (fw.includes("angular")) matchedFw = "angular";
      else if (fw.includes("svelte")) matchedFw = "svelte";
      else if (fw.includes("tailwind")) matchedFw = "tailwind";
      else matchedFw = "html";

      setFramework(matchedFw);
      setDetectedFramework(data.framework_detected || (matchedFw === "html" ? "HTML5" : matchedFw));

      const detVer = data.code_version || data.version || data.framework_version || (matchedFw === "html" ? "1.0.0" : "1.0.0");
      setVersion(detVer);
      setDetectedVersion(detVer);
      setIsHtmlMode(matchedFw === "html" || !!data.is_html_only);

      setTags(data.ai_tags ? data.ai_tags.join(", ") : "");
      setKeywords(data.ai_tags ? data.ai_tags.slice(0, 4).join(", ") : "");
      setMetaTitle((data.project_name || "") + " - Website Template");
      setMetaDesc(data.ai_description || "");

      setStoredZipUrl(data.stored_zip_url);

      if (data.sub_category) {
        setSubCategory(data.sub_category);
      }
      if (data.industry) {
        setIndustryFocus(Array.isArray(data.industry) ? data.industry.join(", ") : data.industry);
      }

      let categoryMatched = false;
      if (data.categories && categories.length > 0) {
        const sortedCats = Object.entries(data.categories).sort((a, b) => b[1] - a[1]);
        const highestCategoryName = sortedCats[0]?.[0];
        if (highestCategoryName) {
          const matched = categories.find(c => c.name.toLowerCase() === highestCategoryName.toLowerCase());
          if (matched) {
            setCategoryId(matched.id);
            categoryMatched = true;
          } else {
            setCategoryId("");
          }
        } else {
          setCategoryId("");
        }
      } else {
        setCategoryId("");
      }

      const isGitIncomplete =
        !data.project_name ||
        !data.ai_description ||
        !data.framework_detected ||
        !data.categories ||
        Object.keys(data.categories).length === 0 ||
        !categoryMatched;

      setIsIncompleteAnalysis(isGitIncomplete);

    } catch (err) {
      clearInterval(interval);
      console.error(err);
      alert(err.message);
      setWizardStep(1);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const fetchProfile = useAuthStore((s) => s.fetchProfile);
  const [connectingGithub, setConnectingGithub] = useState(false);

  const fetchGithubRepos = async () => {
    // If not connected and no input parameters are set, warn
    if (!user?.has_github_token && !githubUsername && !githubToken) {
      return;
    }
    setFetchingRepos(true);
    setFetchedRepos([]);
    try {
      const query = new URLSearchParams();
      if (githubUsername) query.append("username", githubUsername.trim());
      if (githubToken) query.append("token", githubToken.trim());

      const res = await fetch(`${API_BASE}/templates/git-repos?${query.toString()}`, {
        headers: {
          "Authorization": `Bearer ${authToken}`
        }
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to fetch repositories");
      }

      const data = await res.json();
      setFetchedRepos(data);
      if (data.length > 0) {
        setGitUrl(data[0].clone_url);
      }
    } catch (err) {
      console.error(err);
      alert(err.message);
    } finally {
      setFetchingRepos(false);
    }
  };

  const connectGithub = async () => {
    if (!githubToken) {
      alert("Please enter a GitHub Personal Access Token.");
      return;
    }
    setConnectingGithub(true);
    try {
      const res = await fetch(`${API_BASE}/auth/connect-github`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({ token: githubToken.trim() })
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to connect GitHub account.");
      }

      const data = await res.json();
      alert(data.message || "Connected successfully!");
      setGithubToken("");
      // Sync user profile state in the client
      await fetchProfile();
    } catch (err) {
      console.error(err);
      alert(err.message);
    } finally {
      setConnectingGithub(false);
    }
  };

  const disconnectGithub = async () => {
    if (!confirm("Are you sure you want to disconnect your GitHub account?")) return;
    try {
      const res = await fetch(`${API_BASE}/auth/disconnect-github`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${authToken}`
        }
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to disconnect GitHub account.");
      }

      alert("GitHub account disconnected.");
      setFetchedRepos([]);
      setGitUrl("");
      await fetchProfile();
    } catch (err) {
      console.error(err);
      alert(err.message);
    }
  };

  useEffect(() => {
    const isGitTab = activeTab === "seller-upload" && uploadType === "git";
    const canFetch = authToken && fetchedRepos.length === 0;
    // Fetch repos if user has a connected GitHub token
    if (isGitTab && canFetch && user?.has_github_token) {
      fetchGithubRepos();
    }
  }, [activeTab, uploadType, user?.has_github_token, authToken]);

  // Clean URL query params after reading tab on first mount
  useEffect(() => {
    if (searchParams.has("tab")) {
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!title || !price || !categoryId) {
      alert("Please fill in required fields (Title, Price, Category).");
      return;
    }
    try {
      setUploading(true);

      // 1. Upload Thumbnail file if exists
      let finalThumbnailUrl = "";
      if (thumbnailFile) {
        finalThumbnailUrl = await uploadFileHelper(thumbnailFile, "thumbnail");
      } else {
        finalThumbnailUrl = "https://picsum.photos/seed/placeholder/600/400";
      }

      // 1b. Upload Gallery Screenshots if any
      const finalGalleryUrls = [];
      if (galleryFiles && galleryFiles.length > 0) {
        for (let i = 0; i < galleryFiles.length; i++) {
          const gFile = galleryFiles[i];
          const gUrl = await uploadFileHelper(gFile, `gallery screenshot ${i + 1}`);
          if (gUrl) finalGalleryUrls.push(gUrl);
        }
      }

      // 2. Prepare Zip File
      let finalZipFile = zipFile;
      if (!finalZipFile && folderFiles && folderFiles.length > 0) {
        const zip = new JSZip();
        for (let i = 0; i < folderFiles.length; i++) {
          const file = folderFiles[i];
          const relativePath = file.webkitRelativePath || file.name;
          zip.file(relativePath, file);
        }
        const content = await zip.generateAsync({ type: "blob" });
        finalZipFile = new File([content], "source.zip", { type: "application/zip" });
      }

      // 3. Upload Source Zip file if exists
      let finalZipUrl = storedZipUrl;
      if (!finalZipUrl && finalZipFile) {
        finalZipUrl = await uploadFileHelper(finalZipFile, "source ZIP");
      }

      // 4. Upload Video file if exists, or use video URL
      let finalVideoUrl = videoUrl ? videoUrl.trim() : null;
      if (videoFile) {
        finalVideoUrl = await uploadFileHelper(videoFile, "video preview");
      }

      // 5. Submit Template details as JSON to match TemplateCreate schema
      let finalTagsList = tags ? tags.split(",").map(t => t.trim().toLowerCase().replace(/^#/, "")).filter(Boolean) : [];
      if (subCategory) {
        const subClean = subCategory.toLowerCase().trim().replace(/^#/, "");
        if (!finalTagsList.includes(subClean)) {
          finalTagsList.push(subClean);
        }
      }
      const selectedCategoryObj = categories.find(c => c.id === categoryId);
      if (selectedCategoryObj) {
        const catSlug = selectedCategoryObj.slug.toLowerCase().trim();
        if (!finalTagsList.includes(catSlug)) {
          finalTagsList.push(catSlug);
        }
      }
      finalTagsList = Array.from(new Set(finalTagsList.filter(Boolean)));

      const rawPrice = Number(price) || 0;
      const finalPrice = priceCurrency && priceCurrency.toUpperCase() !== "USD"
        ? Number(convertToUSD(rawPrice, priceCurrency, rates))
        : rawPrice;
      const rawSalePrice = salePrice ? Number(salePrice) : null;
      const finalOriginalPrice = rawSalePrice
        ? (priceCurrency && priceCurrency.toUpperCase() !== "USD"
          ? Number(convertToUSD(rawSalePrice, priceCurrency, rates))
          : rawSalePrice)
        : null;

      const payload = {
        title,
        slug: slug || title.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
        short_description: shortDesc || "Template short description",
        description: desc || "Template full description",
        price: finalPrice,
        price_currency: "USD",
        original_price: finalOriginalPrice,
        is_free: finalPrice === 0,
        is_on_sale: !!finalOriginalPrice,
        thumbnail_url: finalThumbnailUrl,
        preview_url: demoUrl || null,
        video_url: finalVideoUrl,
        gallery_images: finalGalleryUrls,
        category_id: categoryId,
        tags: finalTagsList,
        industry: subCategory || industryFocus || (analysisResult && analysisResult.industry ? (Array.isArray(analysisResult.industry) ? analysisResult.industry.join(", ") : analysisResult.industry) : "Business"),
        color_scheme: analysisResult ? (analysisResult.color_palette ? analysisResult.color_palette.join(", ") : null) : null,
        framework: framework || "html",
        pages_count: analysisResult ? (analysisResult.pages ? analysisResult.pages.length : 1) : 1,
        has_dark_mode: analysisResult ? !!analysisResult.dark_mode : false,
        is_responsive: analysisResult ? !!analysisResult.responsive_analysis?.mobile : true,
        is_rtl_supported: false,
        is_ai_ready: !!analysisResult,
        compatibility: ["Chrome", "Firefox", "Safari", "Edge"],
        version: version || "1.0.0",
        license_type: licenseType === "extended" ? "extended" : "regular",
        is_featured: false,
        is_bestseller: false,
        developer_name: user?.fullName ?? user?.firstName ?? "Site Studio Seller",
        developer_avatar: user?.imageUrl ?? null,
        included_pages: analysisResult ? (analysisResult.pages || []) : [],
        seo_keywords: keywords ? keywords.split(",").map(k => k.trim()) : [],
        status: "published",
        download_assets: finalZipUrl ? { "zip": finalZipUrl } : {},
        changelog: analysisResult ? { "ai_report": analysisResult } : null
      };

      const res = await fetch(`${API_BASE}/templates`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to upload template");
      }

      alert("Template submitted successfully for platform review!");
      qc.invalidateQueries(["seller-templates"]);

      // Reset form
      setTitle("");
      setSlug("");
      setShortDesc("");
      setDesc("");
      setCategoryId("");
      setFramework("nextjs");
      setPrice("49");
      setSalePrice("");
      setTags("");
      setDemoUrl("");
      setThumbnailFile(null);
      setVideoFile(null);
      setVideoUrl("");
      setZipFile(null);
      setFolderFiles(null);
      setUploadType("zip");
      setGitUrl("");
      setStoredZipUrl("");
      setGithubUsername("");
      setGithubToken("");
      setFetchedRepos([]);
      setWizardStep(1);
      setActiveTab("seller-templates");
    } catch (err) {
      console.error(err);
      alert(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleCreateCoupon = (e) => {
    e.preventDefault();
    if (!newCouponCode) return;
    setCoupons([
      ...coupons,
      { code: newCouponCode.toUpperCase(), discount: Number(newCouponDiscount), start: "2026-07-01", end: "2026-12-31", limit: Number(newCouponLimit), used: 0 }
    ]);
    setNewCouponCode("");
    alert("Discount coupon created successfully!");
  };

  const handleReplyMessage = (e) => {
    e.preventDefault();
    if (!activeMessageId || !replyText) return;
    setMessages(messages.map(m => m.id === activeMessageId ? { ...m, isReplied: true, replyText } : m));
    setReplyText("");
    setActiveMessageId(null);
    alert("Reply sent to customer inbox!");
  };

  const handleGenerateMockup = (e) => {
    e.preventDefault();
    if (!aiPrompt) return;
    setGeneratingMockup(true);
    setTimeout(() => {
      setGeneratingMockup(false);
      setAiGeneratedResult({
        title: "Generated Startup Landing Page",
        description: `Prototype generated based on prompt: "${aiPrompt}"`,
        pages: ["Home", "Features", "Pricing", "Contact"],
        subdomain: `gen-${Math.floor(Math.random() * 1000)}.aisitestudio.com`,
      });
    }, 2000);
  };

  if (!authToken && !user) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen pt-20 flex items-center justify-center bg-background">
          <div className="text-center space-y-4">
            <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
            <p className="text-muted-foreground text-sm">Loading your dashboard...</p>
          </div>
        </div>
      </>
    );
  }

  // Calculate Buyer total spent from completed orders
  const totalSpent = orders.filter(o => o.status === "completed").reduce((sum, o) => sum + o.total, 0);

  // ═══════════════════════════════════════════════════════════════════
  // REDESIGNED UNIFIED "MY TEMPLATES" EXPERIENCE
  // ═══════════════════════════════════════════════════════════════════
  const renderMyTemplatesSection = () => {
    const purchasedItems = getPurchasedItemsList(orders, hiddenPurchasedTemplates);
    const customizedItems = getCustomizedItemsList(templateResponse);
    const allUserTemplates = Array.isArray(templateResponse) ? templateResponse : [];

    const uploadedItems = allUserTemplates.filter(item =>
      !item.slug?.includes("-custom-") &&
      !item.slug?.includes("-draft-") &&
      !item.title?.includes("(Customized)") &&
      !item.title?.startsWith("Customized ") &&
      item.status !== "draft" &&
      item.template_origin !== "studio" &&
      item.template_origin !== "custom_draft" &&
      item.is_marketplace !== false
    );

    // Filter items based on search query
    const query = (uploadedTemplatesSearch || "").toLowerCase().trim();
    const filteredPurchased = purchasedItems.filter(item =>
      !query ||
      item.title?.toLowerCase().includes(query) ||
      item.framework?.toLowerCase().includes(query) ||
      item.license_type?.toLowerCase().includes(query) ||
      item.short_description?.toLowerCase().includes(query)
    );

    const filteredCustomized = customizedItems.filter(item =>
      !query ||
      item.title?.toLowerCase().includes(query) ||
      item.framework?.toLowerCase().includes(query) ||
      item.short_description?.toLowerCase().includes(query) ||
      item.description?.toLowerCase().includes(query)
    );

    const filteredUploaded = uploadedItems.filter(item => {
      const catName = typeof item.category === "object" ? (item.category?.name || item.category?.slug || "") : (item.category || "");
      return (
        !query ||
        item.title?.toLowerCase().includes(query) ||
        item.framework?.toLowerCase().includes(query) ||
        catName.toLowerCase().includes(query) ||
        item.description?.toLowerCase().includes(query)
      );
    });

    return (
      <div className="mt-container">
        {/* ── Main Header Card ── */}
        <div className="mt-header-card">
          {/* Top Row: Title + Description + Top Action CTA */}
          <div className="mt-header-top">
            <div className="mt-header-title-box">
              <div className="mt-header-icon">
                {templatesSubTab === "customized" ? <Sparkles className="w-6 h-6" /> : <Folder className="w-6 h-6" />}
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="mt-title">
                    {templatesSubTab === "customized" ? "Customized Files" : "My Templates"}
                    <span className="mt-count-badge">
                      {templatesSubTab === "purchased"
                        ? `${purchasedItems.length} Purchased`
                        : templatesSubTab === "customized"
                          ? `${customizedItems.length} Customized Files`
                          : `${uploadedItems.length} Uploaded`}
                    </span>
                  </h2>
                </div>
                <p className="mt-desc">
                  {templatesSubTab === "purchased" ? (
                    <>
                      Manage your purchased templates, redesign with Studio, and launch live websites.
                      {hiddenPurchasedTemplates.length > 0 && (
                        <button
                          type="button"
                          onClick={handleUnhideAllPurchased}
                          className="text-[11px] text-[#dfb180] hover:text-[#dfb180] underline font-bold bg-transparent border-0 cursor-pointer ml-2"
                        >
                          Restore {hiddenPurchasedTemplates.length} hidden
                        </button>
                      )}
                      <div className="mt-2.5 p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-start gap-2 text-xs text-emerald-200">
                        <span className="text-sm">✦</span>
                        <div>
                          <strong className="text-emerald-100">Unlimited Lifetime Downloads:</strong> All acquired and purchased templates are permanently available for re-download anytime directly from your dashboard.
                        </div>
                      </div>
                    </>
                  ) : templatesSubTab === "customized" ? (
                    "Your customized template files and personal drafts modified in Site Studio. Open them in the Studio, download source, or preview live."
                  ) : (
                    "Manage your creator catalog, track downloads, and update listings."
                  )}
                </p>
              </div>
            </div>

            {/* Top CTA button */}
            <div>
              {templatesSubTab === "uploaded" ? (
                <button
                  type="button"
                  onClick={() => setActiveTab("seller-upload")}
                  className="mt-cta-btn"
                >
                  <Plus className="w-4 h-4" />
                  <span>Upload Template</span>
                </button>
              ) : (
                <Link
                  href="/marketplace"
                  className="mt-cta-btn"
                >
                  <ShoppingBag className="w-4 h-4" />
                  <span>Explore Marketplace</span>
                </Link>
              )}
            </div>
          </div>

          {/* Bottom Row: Subtabs Switcher + Search + View Mode */}
          <div className="mt-toolbar">
            {/* Segmented SubTab Pill Switcher */}
            <div className="mt-tabs">
              <button
                type="button"
                onClick={() => setTemplatesSubTab("purchased")}
                className={cn("mt-tab-btn", templatesSubTab === "purchased" && "active")}
              >
                <ShoppingCart className="w-4 h-4" style={{ color: templatesSubTab === "purchased" ? "#b5804f" : "#64748b" }} />
                <span>Purchased</span>
                <span className={cn("mt-tab-count", templatesSubTab === "purchased" ? "active" : "inactive")}>
                  {purchasedItems.length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setTemplatesSubTab("customized")}
                className={cn("mt-tab-btn", templatesSubTab === "customized" && "active")}
              >
                <Sparkles className="w-4 h-4" style={{ color: templatesSubTab === "customized" ? "#ec4899" : "#64748b" }} />
                <span>Customized Files</span>
                <span className={cn("mt-tab-count", templatesSubTab === "customized" ? "active" : "inactive")}>
                  {customizedItems.length}
                </span>
              </button>

              {(isSeller || isAdmin || uploadedItems.length > 0) && (
                <button
                  type="button"
                  onClick={() => setTemplatesSubTab("uploaded")}
                  className={cn("mt-tab-btn", templatesSubTab === "uploaded" && "active")}
                >
                  <UploadCloud className="w-4 h-4" style={{ color: templatesSubTab === "uploaded" ? "#b5804f" : "#64748b" }} />
                  <span>Uploaded</span>
                  <span className={cn("mt-tab-count", templatesSubTab === "uploaded" ? "active" : "inactive")}>
                    {uploadedItems.length}
                  </span>
                </button>
              )}
            </div>

            {/* Purge All Drafts Button + Search + View Toggle */}
            <div className="flex items-center gap-2.5 flex-wrap">
              {templatesSubTab === "customized" && customizedItems.length > 0 && (
                <button
                  type="button"
                  onClick={handlePurgeAllDrafts}
                  disabled={purgingDrafts}
                  className="px-3 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer shrink-0"
                  title="Permanently delete all customized files, studio creator projects, and edited drafts"
                >
                  {purgingDrafts ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                  <span>Purge All Drafts</span>
                </button>
              )}

              <div className="mt-search-box">
                <Search className="mt-search-icon" />
                <input
                  type="text"
                  placeholder="Search templates..."
                  value={uploadedTemplatesSearch}
                  onChange={(e) => setUploadedTemplatesSearch(e.target.value)}
                  className="mt-search-input"
                />
                {uploadedTemplatesSearch && (
                  <button
                    onClick={() => setUploadedTemplatesSearch("")}
                    className="mt-search-clear"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Grid / Table Toggle */}
              <div className="mt-view-toggle">
                <button
                  type="button"
                  onClick={() => setUploadedTemplatesView("grid")}
                  className={cn("mt-view-btn", uploadedTemplatesView === "grid" && "active")}
                  title="Grid View"
                >
                  <LayoutGrid className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setUploadedTemplatesView("table")}
                  className={cn("mt-view-btn", uploadedTemplatesView === "table" && "active")}
                  title="Table View"
                >
                  <List className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* ── Content Area ── */}
        {templatesLoading && (!templateResponse || templateResponse.length === 0) ? (
          <div className="py-20 text-center rounded-2xl border border-slate-200 bg-white">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#dfb180]" />
            <p className="text-xs text-slate-500 mt-3 font-semibold">Loading templates...</p>
          </div>
        ) : templatesSubTab === "purchased" ? (
          /* ══════════════════════════════════════════════
             PURCHASED TEMPLATES VIEW
             ══════════════════════════════════════════════ */
          purchasedItems.length === 0 ? (
            <div className="mt-empty-card">
              <div className="mt-empty-icon">
                <ShoppingBag className="w-7 h-7" />
              </div>
              <h4 className="mt-empty-title">No Purchased Templates Yet</h4>
              <p className="mt-empty-desc">
                Explore our diverse marketplace with modern, production-ready website templates and customize them live with AI.
              </p>
              <Link
                href="/marketplace"
                className="mt-empty-btn"
              >
                <Sparkles className="w-4 h-4" /> Browse Marketplace Templates
              </Link>
            </div>
          ) : filteredPurchased.length === 0 ? (
            <div className="text-center py-12 px-4 rounded-2xl border border-border/40 bg-card/30">
              <p className="text-xs text-muted-foreground font-semibold">No purchased templates match &ldquo;{uploadedTemplatesSearch}&rdquo;</p>
              <button
                onClick={() => setUploadedTemplatesSearch("")}
                className="mt-3 text-xs text-primary underline font-bold bg-transparent border-0 cursor-pointer"
              >
                Clear Search Filter
              </button>
            </div>
          ) : uploadedTemplatesView === "grid" ? (
            /* Grid View for Purchased */
            <div className="db-templates-grid">
              {filteredPurchased.map((item) => {
                const isExtended = isUserPro || String(item.license_type || "").toLowerCase() === "extended";

                return (
                  <div key={item.id} className="db-template-card group">
                    {/* Thumbnail Header */}
                    <div className="db-template-thumb">
                      {item.thumbnail_url ? (
                        <img
                          src={item.thumbnail_url}
                          alt={item.title || "Template"}
                          className="db-template-img"
                          onError={(e) => {
                            e.target.style.display = "none";
                            if (e.target.nextElementSibling) e.target.nextElementSibling.style.display = "flex";
                          }}
                        />
                      ) : null}
                      <div
                        className="w-full h-full absolute inset-0 flex items-center justify-center"
                        style={{
                          display: item.thumbnail_url ? "none" : "flex",
                          background: "linear-gradient(135deg, hsla(var(--primary)/0.15) 0%, hsla(var(--secondary)/0.15) 100%)",
                        }}
                      >
                        <span style={{ fontSize: "2rem" }}>🎨</span>
                      </div>

                      {/* Top-Left Floating Badges */}
                      <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
                        <span className="px-2 py-0.5 bg-emerald-500 text-white text-[9px] font-black uppercase tracking-wider rounded-full shadow-sm">
                          Purchased
                        </span>
                        <span className="px-1.5 py-0.5 bg-black/60 backdrop-blur-md text-white text-[9px] font-bold uppercase tracking-wider rounded-full border border-white/10">
                          {item.license_type || "Standard"}
                        </span>
                      </div>

                      {/* Top-Right Framework Badge & Hide Action */}
                      <div className="absolute top-2.5 right-2.5 flex items-center gap-1.5">
                        <span className="px-2 py-0.5 bg-black/60 backdrop-blur-md text-white text-[9px] font-mono font-bold uppercase rounded-md border border-white/10">
                          {item.framework || "HTML"}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleHidePurchasedTemplate(item.template_id || item.id);
                          }}
                          className="w-5 h-5 rounded-md bg-black/60 hover:bg-rose-600/80 backdrop-blur-md text-white/70 hover:text-white flex items-center justify-center border border-white/10 transition-colors cursor-pointer"
                          title="Remove from list"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    </div>

                    {/* Card Content Body */}
                    <div className="db-template-body">
                      {/* Title & Description with comfortable spacing */}
                      <div className="db-template-header-text">
                        <h4 className="db-template-title" title={item.title}>
                          {item.title || "Template Package"}
                        </h4>
                        <p className="db-template-desc">
                          {item.short_description || "Modern & responsive purchased template."}
                        </p>
                      </div>

                      {/* Pricing & Metadata Strip */}
                      <div className="db-template-meta-row">
                        <div>
                          <span className="text-[11px] text-muted-foreground">Price Paid: </span>
                          <span className="font-extrabold text-foreground">{formatPrice(item.price || 0)}</span>
                        </div>
                        <div className="flex items-center gap-1.5 flex-wrap justify-end">
                          {isExtended ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30" title="Zero watermark white-label export with lifetime downloads">
                              ✦ Full Access (Clean)
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30 flex items-center gap-1" title="Standard Edition with lifetime downloads">
                              <span>✦ Lifetime Access</span>
                            </span>
                          )}
                          <span className="text-[10px] font-medium text-muted-foreground">
                            {item.seller_name ? `by ${item.seller_name}` : "Verified"}
                          </span>
                        </div>
                      </div>

                      {/* Action Buttons Hub with Generous Gap */}
                      <div className="db-template-actions-box">
                        {/* Primary AI Studio Action */}
                        <Link
                          href={`/preview?templateId=${item.template_id || item.id}`}
                          className="db-btn-ai-studio"
                        >
                          <Sparkles className="w-3.5 h-3.5 text-white" />
                          <span style={{ color: "#ffffff" }}>Redesign in Studio</span>
                        </Link>

                        {/* Action Grid (2x2) with comfortable spacing */}
                        <div className="db-template-btn-grid">
                          <button
                            type="button"
                            onClick={() => {
                              setDeployTemplateId(item.template_id || item.id);
                              setDeployProjectName(item.title || "My Website");
                              setIsDeployModalOpen(true);
                            }}
                            className="db-btn-publish"
                            title="Publish / Launch to Domain"
                          >
                            <Zap className="w-3 h-3 text-white" />
                            <span style={{ color: "#ffffff" }}>Publish</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              requestDownloadWithWarning(item, "zip");
                            }}
                            className="db-btn-secondary"
                            title="Download Source Code ZIP (Lifetime Access)"
                          >
                            <Download className="w-3.5 h-3.5 text-primary" />
                            <span>Source</span>
                          </button>

                          <a
                            href={item.preview_url || `${API_BASE}/preview/live/${item.template_id || item.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="db-btn-secondary"
                            title="Live Demo Preview"
                          >
                            <Globe className="w-3.5 h-3.5 text-[#dfb180]" />
                            <span>Demo</span>
                          </a>

                          <button
                            type="button"
                            onClick={() => {
                              setReviewTemplateId(item.template_id || item.id);
                              setReviewTemplateTitle(item.title || "Template Package");
                              setReviewRating(5);
                              setReviewTitle("");
                              setReviewBody("");
                              setReviewModalOpen(true);
                            }}
                            className="db-btn-review"
                            title="Rate & Review Template"
                          >
                            <Star className="w-3.5 h-3.5 fill-amber-500 text-amber-500" />
                            <span>Review</span>
                          </button>
                        </div>

                        {/* Official Receipt Footer Link */}
                        <div className="text-center">
                          <a
                            href={getReceiptUrl(item)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="db-template-receipt-link"
                          >
                            <FileText className="w-3 h-3 text-muted-foreground" />
                            <span>View Official Invoice Receipt</span>
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            /* Table View for Purchased */
            <div className="overflow-x-auto rounded-2xl border border-border/50 bg-card">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border/40 bg-muted/40 font-bold uppercase text-muted-foreground text-[10px] tracking-wider">
                    <th className="p-4">Template</th>
                    <th className="p-4">Framework</th>
                    <th className="p-4">Price</th>
                    <th className="p-4">License</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {filteredPurchased.map((item) => (
                    <tr key={item.id} className="hover:bg-muted/20 transition-colors">
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <img
                            src={item.thumbnail_url}
                            alt=""
                            className="w-10 h-10 rounded-lg object-cover bg-muted shrink-0"
                            onError={(e) => { e.target.style.display = "none"; }}
                          />
                          <div>
                            <div className="font-bold text-foreground text-xs">{item.title}</div>
                            <div className="text-[11px] text-muted-foreground line-clamp-1">{item.short_description || "Purchased Template"}</div>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className="px-2 py-0.5 bg-muted text-foreground border border-border/50 rounded-md font-mono font-bold uppercase text-[10px]">
                          {item.framework || "HTML"}
                        </span>
                      </td>
                      <td className="p-4 font-bold text-foreground">{formatPrice(item.price || 0)}</td>
                      <td className="p-4">
                        <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[10px] font-bold rounded-full uppercase">
                          {item.license_type || "Standard"}
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Link
                            href={`/preview?templateId=${item.template_id || item.id}`}
                            className="px-2.5 py-1.5 bg-primary text-white text-[11px] font-bold rounded-lg flex items-center gap-1 text-decoration-none shadow-sm"
                          >
                            <Sparkles className="w-3 h-3" /> Redesign
                          </Link>
                          <button
                            type="button"
                            onClick={() => requestDownloadWithWarning(item, "zip")}
                            className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg border border-border/40 bg-muted/40 cursor-pointer"
                            title="Download Source"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </button>
                          <a
                            href={getReceiptUrl(item)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg border border-border/40 bg-muted/40"
                            title="Invoice Receipt"
                          >
                            <FileText className="w-3.5 h-3.5" />
                          </a>
                          <button
                            type="button"
                            onClick={() => handleHidePurchasedTemplate(item.template_id || item.id)}
                            className="p-1.5 text-muted-foreground hover:text-rose-400 rounded-lg border border-border/40 bg-muted/40 cursor-pointer"
                            title="Remove from list"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : templatesSubTab === "customized" ? (
          /* ══════════════════════════════════════════════
             CUSTOMIZED / EDITED PROJECTS VIEW
             ══════════════════════════════════════════════ */
          customizedItems.length === 0 ? (
            <div className="mt-empty-card">
              <div className="mt-empty-icon">
                <Sparkles className="w-7 h-7" />
              </div>
              <h4 className="mt-empty-title">No Customized Files Yet</h4>
              <p className="mt-empty-desc">
                Pick any marketplace template or open the Studio to customize copy, layout, and colors. Your personal customized files will be saved privately here.
              </p>
              <Link
                href="/marketplace"
                className="mt-empty-btn"
              >
                <Sparkles className="w-4 h-4" /> Pick a Template to Customize
              </Link>
            </div>
          ) : filteredCustomized.length === 0 ? (
            <div className="text-center py-12 px-4 rounded-2xl border border-border/40 bg-card/30">
              <p className="text-xs text-muted-foreground font-semibold">No customized files match &ldquo;{uploadedTemplatesSearch}&rdquo;</p>
              <button
                onClick={() => setUploadedTemplatesSearch("")}
                className="mt-3 text-xs text-primary underline font-bold bg-transparent border-0 cursor-pointer"
              >
                Clear Search Filter
              </button>
            </div>
          ) : uploadedTemplatesView === "grid" ? (
            /* Grid View for Customized */
            <div className="db-templates-grid">
              {filteredCustomized.map((item) => {
                const isPurchased = purchasedItems.some(p => p.template_id === item.id || p.id === item.id);
                const inCart = isInCart(item.id);

                return (
                  <div key={item.id} className="db-template-card group">
                    {/* Thumbnail Header */}
                    <div className="db-template-thumb">
                      {item.thumbnail_url ? (
                        <img
                          src={item.thumbnail_url}
                          alt={item.title || "Customized Project"}
                          className="db-template-img"
                          onError={(e) => {
                            e.target.style.display = "none";
                            if (e.target.nextElementSibling) e.target.nextElementSibling.style.display = "flex";
                          }}
                        />
                      ) : null}
                      <div
                        className="w-full h-full absolute inset-0 flex items-center justify-center"
                        style={{
                          display: item.thumbnail_url ? "none" : "flex",
                          background: "linear-gradient(135deg, hsla(var(--primary)/0.2) 0%, hsla(var(--secondary)/0.2) 100%)",
                        }}
                      >
                        <span style={{ fontSize: "2rem" }}>✨</span>
                      </div>

                      {/* Top-Left Floating Badges */}
                      <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
                        {isPurchased ? (
                          <span className="px-2 py-0.5 bg-emerald-500 text-white text-[9px] font-black uppercase tracking-wider rounded-full shadow-sm flex items-center gap-1">
                            <CheckCircle2 className="w-2.5 h-2.5" /> Purchased
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 bg-gradient-to-r from-[#c89666] to-[#b5804f] text-[#09090b] text-[9px] font-black uppercase tracking-wider rounded-full shadow-sm flex items-center gap-1">
                            <Sparkles className="w-2.5 h-2.5" /> Edited Draft
                          </span>
                        )}
                      </div>

                      {/* Top-Right Framework Badge & Delete */}
                      <div className="absolute top-2.5 right-2.5 flex items-center gap-1.5">
                        <span className="px-2 py-0.5 bg-black/60 backdrop-blur-md text-white text-[9px] font-mono font-bold uppercase rounded-md border border-white/10">
                          {item.framework || "HTML"}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteCustomDraft(item.id, item.title);
                          }}
                          className="w-5 h-5 rounded-md bg-black/60 hover:bg-rose-600/80 backdrop-blur-md text-white/70 hover:text-white flex items-center justify-center border border-white/10 transition-colors cursor-pointer"
                          title="Delete draft"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>

                    {/* Card Content Body */}
                    <div className="db-template-body">
                      <div className="db-template-header-text">
                        <h4 className="db-template-title" title={item.title}>
                          {item.title || "Customized Project"}
                        </h4>
                        <p className="db-template-desc">
                          {item.short_description || item.description || "Personalized project edited in Studio."}
                        </p>
                      </div>

                      {/* Pricing & Metadata Strip */}
                      <div className="db-template-meta-row">
                        <div>
                          <span className="text-[11px] text-muted-foreground">Draft ID: </span>
                          <span className="font-mono text-muted-foreground font-bold">#{String(item.id || "").slice(0, 6).toUpperCase()}</span>
                        </div>
                        <span className="text-[10px] font-bold text-emerald-500 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Live Ready
                        </span>
                      </div>

                      {/* Action Buttons Hub */}
                      <div className="db-template-actions-box">
                        {/* Primary Studio Action */}
                        <Link
                          href={`/preview?template=${item.id}`}
                          className="db-btn-ai-studio"
                        >
                          <Sparkles className="w-3.5 h-3.5 text-white" />
                          <span style={{ color: "#ffffff" }}>Open in Studio</span>
                        </Link>

                        {/* Action Grid */}
                        <div className="db-template-btn-grid">
                          <button
                            type="button"
                            onClick={() => {
                              setDeployTemplateId(item.id);
                              setDeployProjectName(item.title || "My Website");
                              setIsDeployModalOpen(true);
                            }}
                            className="db-btn-publish"
                            title="Deploy / Publish"
                          >
                            <Zap className="w-3 h-3 text-white" />
                            <span style={{ color: "#ffffff" }}>Deploy</span>
                          </button>

                          <a
                            href={`${API_BASE}/preview/live/${item.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="db-btn-secondary"
                            title="Live Demo Preview"
                          >
                            <Globe className="w-3.5 h-3.5 text-[#dfb180]" />
                            <span>Demo</span>
                          </a>

                          {isPurchased ? (
                            <button
                              type="button"
                              onClick={() => requestDownloadWithWarning(item, "zip")}
                              className="db-btn-secondary"
                              title="Download Clean Source ZIP"
                            >
                              <Download className="w-3.5 h-3.5 text-emerald-600" />
                              <span>ZIP</span>
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => {
                                addToCart({
                                  id: item.id,
                                  templateId: item.id,
                                  title: item.title,
                                  price: item.price || 49,
                                  thumbnail: item.thumbnail_url || "",
                                  framework: item.framework || "HTML",
                                  licenseType: "regular",
                                });
                              }}
                              className={cn("db-btn-review", inCart && "bg-[#c89666]/15 text-[#dfb180] font-extrabold")}
                              title="Add to Cart to purchase and unlock ZIP"
                            >
                              <ShoppingCart className="w-3.5 h-3.5 text-[#dfb180]" />
                              <span>{inCart ? "In Cart ✓" : `Cart ($${item.price || 49})`}</span>
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={() => handleDeleteCustomDraft(item.id, item.title)}
                            className="db-btn-danger"
                            title="Delete this customized project"
                          >
                            <Trash2 className="w-3 h-3 text-rose-400" />
                            <span>Delete</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            /* Table View for Customized */
            <div className="overflow-x-auto rounded-2xl border border-border/50 bg-card">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border/40 bg-muted/40 font-bold uppercase text-muted-foreground text-[10px] tracking-wider">
                    <th className="p-4">Project</th>
                    <th className="p-4">Framework</th>
                    <th className="p-4">Status</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {filteredCustomized.map((item) => {
                    const isPurchased = purchasedItems.some(p => p.template_id === item.id || p.id === item.id);
                    const inCart = isInCart(item.id);

                    return (
                      <tr key={item.id} className="hover:bg-muted/20 transition-colors">
                        <td className="p-4">
                          <div className="flex items-center gap-3">
                            <img
                              src={item.thumbnail_url}
                              alt=""
                              className="w-10 h-10 rounded-lg object-cover bg-muted shrink-0"
                              onError={(e) => { e.target.style.display = "none"; }}
                            />
                            <div>
                              <div className="font-bold text-foreground text-xs">{item.title}</div>
                              <div className="text-[11px] text-muted-foreground line-clamp-1">{item.description || "Personal Draft Project"}</div>
                            </div>
                          </div>
                        </td>
                        <td className="p-4">
                          <span className="px-2 py-0.5 bg-muted text-foreground border border-border/50 rounded-md font-mono font-bold uppercase text-[10px]">
                            {item.framework || "HTML"}
                          </span>
                        </td>
                        <td className="p-4">
                          {isPurchased ? (
                            <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 text-[10px] font-bold rounded-full uppercase">
                              Purchased
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30 text-[10px] font-bold rounded-full uppercase">
                              Edited Draft
                            </span>
                          )}
                        </td>
                        <td className="p-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Link
                              href={`/preview?template=${item.id}`}
                              className="px-2.5 py-1.5 bg-primary text-white text-[11px] font-bold rounded-lg flex items-center gap-1 text-decoration-none shadow-sm"
                            >
                              <Sparkles className="w-3 h-3" /> Edit in Studio
                            </Link>
                            {isPurchased ? (
                              <button
                                type="button"
                                onClick={() => requestDownloadWithWarning(item, "zip")}
                                className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg border border-border/40 bg-muted/40 cursor-pointer"
                                title="Download ZIP"
                              >
                                <Download className="w-3.5 h-3.5 text-emerald-600" />
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => {
                                  addToCart({
                                    id: item.id,
                                    templateId: item.id,
                                    title: item.title,
                                    price: item.price || 49,
                                    thumbnail: item.thumbnail_url || "",
                                    framework: item.framework || "HTML",
                                    licenseType: "regular",
                                  });
                                }}
                                className="px-2.5 py-1.5 bg-[#c89666]/15 hover:bg-[#c89666]/15 text-white text-[11px] font-bold rounded-lg flex items-center gap-1 cursor-pointer border-0 shadow-sm"
                                title="Add to Cart to purchase"
                              >
                                <ShoppingCart className="w-3 h-3" />
                                <span>{inCart ? "In Cart ✓" : `Cart ($${item.price || 49})`}</span>
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => handleDeleteCustomDraft(item.id, item.title)}
                              className="p-1.5 text-rose-400 hover:text-rose-300 rounded-lg border border-rose-500/20 bg-rose-500/10 hover:bg-rose-500/20 cursor-pointer"
                              title="Delete customized draft"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        ) : (
          /* ══════════════════════════════════════════════
             UPLOADED TEMPLATES VIEW
             ══════════════════════════════════════════════ */
          uploadedItems.length === 0 ? (
            <div className="mt-empty-card">
              <div className="mt-empty-icon">
                <UploadCloud className="w-7 h-7" />
              </div>
              <h4 className="mt-empty-title">No Uploaded Templates Yet</h4>
              <p className="mt-empty-desc">
                Start selling your templates on Site Studio marketplace to earn revenue and reach creators worldwide.
              </p>
              <button
                onClick={() => setActiveTab("seller-upload")}
                className="mt-empty-btn"
              >
                <Plus className="w-4 h-4" /> Upload Your First Template
              </button>
            </div>
          ) : filteredUploaded.length === 0 ? (
            <div className="text-center py-12 px-4 rounded-2xl border border-border/40 bg-card/30">
              <p className="text-xs text-muted-foreground font-semibold">No uploaded templates match &ldquo;{uploadedTemplatesSearch}&rdquo;</p>
              <button
                onClick={() => setUploadedTemplatesSearch("")}
                className="mt-3 text-xs text-primary underline font-bold bg-transparent border-0 cursor-pointer"
              >
                Clear Search Filter
              </button>
            </div>
          ) : uploadedTemplatesView === "grid" ? (
            /* Grid View for Uploaded */
            <div className="db-templates-grid">
              {filteredUploaded.map((item) => (
                <div key={item.id} className="db-template-card group">
                  {/* Thumbnail Header */}
                  <div className="db-template-thumb">
                    {item.thumbnail_url ? (
                      <img
                        src={item.thumbnail_url}
                        alt={item.title || "Template"}
                        className="db-template-img"
                        onError={(e) => {
                          e.target.style.display = "none";
                          if (e.target.nextElementSibling) e.target.nextElementSibling.style.display = "flex";
                        }}
                      />
                    ) : null}
                    <div
                      className="w-full h-full absolute inset-0 flex items-center justify-center"
                      style={{
                        display: item.thumbnail_url ? "none" : "flex",
                        background: "linear-gradient(135deg, hsla(var(--primary)/0.15) 0%, hsla(var(--secondary)/0.15) 100%)",
                      }}
                    >
                      <span style={{ fontSize: "2rem" }}>🎨</span>
                    </div>

                    {/* Top-Left Floating Badges */}
                    <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
                      <span className="px-2 py-0.5 bg-emerald-500 text-white text-[9px] font-black uppercase tracking-wider rounded-full shadow-sm">
                        Published
                      </span>
                      {(typeof item.category === "object" ? item.category?.name : item.category) && (
                        <span className="px-1.5 py-0.5 bg-black/60 backdrop-blur-md text-white text-[9px] font-bold uppercase tracking-wider rounded-full border border-white/10">
                          {typeof item.category === "object" ? item.category.name : item.category}
                        </span>
                      )}
                    </div>

                    {/* Top-Right Framework Badge */}
                    <div className="absolute top-2.5 right-2.5">
                      <span className="px-2 py-0.5 bg-black/60 backdrop-blur-md text-white text-[9px] font-mono font-bold uppercase rounded-md border border-white/10">
                        {item.framework || "HTML"}
                      </span>
                    </div>
                  </div>

                  {/* Card Content Body */}
                  <div className="db-template-body">
                    {/* Title & Description with comfortable spacing */}
                    <div className="db-template-header-text">
                      <h4 className="db-template-title" title={item.title}>
                        {item.title || "Untitled Template"}
                      </h4>
                      <p className="db-template-desc">
                        {item.description || "Modern & fully responsive website template."}
                      </p>
                    </div>

                    {/* 2 Stats Pill Boxes (Downloads & Views) */}
                    <div className="grid grid-cols-2 gap-2.5 my-1">
                      <div className="flex flex-col items-center justify-center py-2.5 rounded-xl bg-muted/40 border border-border/40">
                        <span className="text-sm font-black text-foreground leading-none">
                          {item.downloads_count || 0}
                        </span>
                        <span className="text-[10px] text-muted-foreground font-semibold mt-1 flex items-center gap-1">
                          <Download className="w-3 h-3 text-primary" /> Downloads
                        </span>
                      </div>
                      <div className="flex flex-col items-center justify-center py-2.5 rounded-xl bg-muted/40 border border-border/40" title="Number of unique accounts that opened this template">
                        <span className="text-sm font-black text-foreground leading-none">
                          {item.views_count || 0}
                        </span>
                        <span className="text-[10px] text-muted-foreground font-semibold mt-1 flex items-center gap-1">
                          <Users className="w-3 h-3 text-[#dfb180]" /> Accounts
                        </span>
                      </div>
                    </div>

                    {/* Pricing & Metadata Strip */}
                    <div className="space-y-2 py-2.5 border-t border-b border-border/30 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground font-medium">Price:</span>
                        <span className="font-extrabold text-foreground">{formatPrice(item.price || 0)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground font-medium">Template ID:</span>
                        <span className="font-mono text-muted-foreground font-bold">#{String(item.id || "").slice(0, 6).toUpperCase()}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground font-medium">Status:</span>
                        <span className="flex items-center gap-1.5 font-bold text-emerald-600 dark:text-emerald-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Published
                        </span>
                      </div>
                    </div>

                    {/* Action Buttons Hub with Comfortable Spacing */}
                    <div className="db-template-actions-box">
                      {/* Primary Live Studio Action */}
                      <Link
                        href={`/preview?templateId=${item.id}`}
                        className="db-btn-ai-studio"
                      >
                        <Sparkles className="w-3.5 h-3.5 text-white" />
                        <span style={{ color: "#ffffff" }}>Redesign in Studio</span>
                      </Link>

                      {/* Action Grid (Stats, Edit, Demo, Delete) */}
                      <div className="db-template-btn-grid-4">
                        <button
                          type="button"
                          onClick={() => alert(`Analytics for ${item.title}: ${item.downloads_count || 0} downloads, ${item.views_count || 0} unique accounts opened.`)}
                          className="db-btn-secondary"
                          title="View Analytics"
                        >
                          <BarChart3 className="w-3.5 h-3.5 text-primary" />
                          <span>Stats</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleOpenEditTemplateModal(item)}
                          className="db-btn-secondary"
                          title="Edit Template Details"
                        >
                          <Pencil className="w-3.5 h-3.5 text-[#dfb180]" />
                          <span>Edit</span>
                        </button>

                        <a
                          href={item.preview_url || `${API_BASE}/preview/live/${item.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="db-btn-secondary"
                          title="Live Demo Preview"
                        >
                          <Globe className="w-3.5 h-3.5 text-blue-500" />
                          <span>Demo</span>
                        </a>

                        <button
                          type="button"
                          onClick={() => {
                            if (confirm(`Are you sure you want to delete "${item.title}"?`)) {
                              deleteMutation.mutate(item.id);
                            }
                          }}
                          className="p-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/20 flex items-center justify-center transition-all cursor-pointer min-h-[34px]"
                          title="Delete Template"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* Table View for Uploaded */
            <div className="overflow-x-auto rounded-2xl border border-border/50 bg-card">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border/40 bg-muted/40 font-bold uppercase text-muted-foreground text-[10px] tracking-wider">
                    <th className="p-4">Template</th>
                    <th className="p-4">Framework</th>
                    <th className="p-4">Price</th>
                    <th className="p-4">Status</th>
                    <th className="p-4">Downloads</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {filteredUploaded.map((item) => (
                    <tr key={item.id} className="hover:bg-muted/20 transition-colors">
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <img
                            src={item.thumbnail_url}
                            alt=""
                            className="w-10 h-10 rounded-lg object-cover bg-muted shrink-0"
                            onError={(e) => { e.target.style.display = "none"; }}
                          />
                          <div>
                            <div className="font-bold text-foreground text-xs">{item.title}</div>
                            <div className="text-[11px] text-muted-foreground line-clamp-1">{item.description || "Uploaded Template"}</div>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className="px-2 py-0.5 bg-muted text-foreground border border-border/50 rounded-md font-mono font-bold uppercase text-[10px]">
                          {item.framework || "HTML"}
                        </span>
                      </td>
                      <td className="p-4 font-bold text-foreground">{formatPrice(item.price || 0)}</td>
                      <td className="p-4">
                        <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[10px] font-bold rounded-full uppercase">
                          Published
                        </span>
                      </td>
                      <td className="p-4 font-mono font-bold text-foreground">{item.downloads_count || 0}</td>
                      <td className="p-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Link
                            href={`/preview?templateId=${item.id}`}
                            className="px-2.5 py-1.5 bg-primary text-white text-[11px] font-bold rounded-lg flex items-center gap-1 text-decoration-none shadow-sm"
                          >
                            <Sparkles className="w-3 h-3" /> Redesign
                          </Link>
                          <button
                            onClick={() => handleOpenEditTemplateModal(item)}
                            className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg border border-border/40 bg-muted/40 cursor-pointer"
                            title="Edit Details"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => {
                              if (confirm(`Are you sure you want to delete "${item.title}"?`)) {
                                deleteMutation.mutate(item.id);
                              }
                            }}
                            className="p-1.5 text-red-500 hover:bg-red-500/10 rounded-lg border border-red-500/20 bg-transparent cursor-pointer"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>
    );
  };

  return (
    <>
      <Navbar />
      <div className="db-page-wrapper">
        <div className="db-container">
          {/* Dashboard Header Banner */}
          <div className="db-user-header">
            <div className="db-user-info-flex">
              <div className="db-user-avatar relative w-16 h-16 rounded-full overflow-hidden border border-border bg-muted flex shrink-0 items-center justify-center">
                {user?.imageUrl ? (
                  <img src={resolveMediaUrl(user.imageUrl)} alt="Avatar" className="w-full h-full object-cover rounded-full" />
                ) : (
                  <div className="db-user-avatar-text font-bold text-xl text-primary">
                    {user?.firstName?.[0] ?? user?.fullName?.[0] ?? "U"}
                  </div>
                )}
              </div>
              <div className="db-user-details">
                <h1 className="db-user-name">
                  Welcome back, {user?.fullName ?? user?.firstName ?? "User"}
                </h1>
                <p className="db-user-email">{user?.email}</p>
                <span className="db-user-role-badge">
                  {user?.role || "buyer"}
                </span>
              </div>
            </div>

            <div className="db-header-actions flex items-center gap-2.5">
              <button
                type="button"
                onClick={toggleSidebar}
                className="px-3.5 py-2 rounded-xl bg-[#141417] hover:bg-[#1f1f26] border border-[#27272a] hover:border-[#c89666]/50 text-xs font-bold text-[#e4e4e7] hover:text-[#dfb180] flex items-center gap-2 transition cursor-pointer shadow-sm"
                title={isSidebarHidden ? "Show Sidebar Menu" : "Hide Sidebar Menu (Full-Width Workspace)"}
              >
                {isSidebarHidden ? (
                  <>
                    <PanelLeftOpen className="w-4 h-4 text-[#c89666]" />
                    <span className="hidden sm:inline">Show Menu</span>
                  </>
                ) : (
                  <>
                    <PanelLeftClose className="w-4 h-4 text-[#a8a29e]" />
                    <span className="hidden sm:inline">Hide Menu</span>
                  </>
                )}
              </button>
              <button
                onClick={() => signOut()}
                className="db-signout-btn"
              >
                <LogOut className="w-5 h-5" />
                <span>Sign Out</span>
              </button>
            </div>
          </div>

          {/* Grid Layout */}
          <div className={cn("db-grid", isSidebarHidden && "db-sidebar-hidden")}>
            {/* Sidebar Navigation */}
            {!isSidebarHidden && (
              <div className="db-sidebar">
                <div className="flex items-center justify-between pb-2 mb-1 px-1 border-b border-[#27272a]/60">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#a8a29e] flex items-center gap-1.5">
                    <LayoutDashboard className="w-3.5 h-3.5 text-[#c89666]" /> Menu
                  </span>
                  <button
                    type="button"
                    onClick={toggleSidebar}
                    className="p-1.5 rounded-lg hover:bg-[#1c1c22] text-[#a8a29e] hover:text-[#dfb180] transition cursor-pointer"
                    title="Hide sidebar menu (expand workspace)"
                  >
                    <PanelLeftClose className="w-4 h-4" />
                  </button>
                </div>
                {(() => {
                  const sidebarTabs = isAdmin
                    ? [
                      { id: "admin-users", label: "Users", icon: User },
                      { id: "seller-templates", label: "My Templates", icon: Folder },
                      { id: "seller-upload", label: "Upload Template", icon: Plus },
                      { id: "admin-payments", label: "Invoices & Ledger", icon: FileText },
                      { id: "admin-categories", label: "Categories", icon: LayoutDashboard },
                      { id: "admin-reports", label: "Reports", icon: HelpCircle },
                      { id: "admin-revenue", label: "Revenue", icon: Coins },
                      { id: "admin-moderation", label: "Moderation", icon: ShieldCheck },
                      { id: "settings", label: "Profile Settings", icon: Settings },
                    ]
                    : isSeller
                      ? [
                        { id: "seller-home", label: "Dashboard", icon: LayoutDashboard },
                        { id: "seller-templates", label: "My Templates", icon: Folder },
                        { id: "seller-upload", label: "Upload Template", icon: Plus },
                        { id: "seller-analytics", label: "Sales Analytics", icon: BarChart3 },
                        { id: "seller-earnings", label: "Earnings", icon: Coins },
                        { id: "seller-orders", label: "Orders", icon: ShoppingBag },
                        { id: "seller-reviews", label: "Reviews", icon: Star },
                        { id: "seller-performance", label: "Performance", icon: TrendingUp },
                        { id: "seller-followers", label: "Followers", icon: Users },
                        { id: "seller-messages", label: "Customer Messages", icon: MessageSquare },
                        { id: "seller-payouts", label: "Payouts", icon: Wallet },
                        { id: "settings", label: "Profile Settings", icon: Settings },
                      ]
                      : [
                        { id: "buyer-home", label: "Dashboard", icon: LayoutDashboard },
                        { id: "marketplace-redirect", label: "Marketplace", icon: ShoppingBag, isLink: true, url: "/marketplace" },
                        { id: "buyer-templates", label: "My Templates", icon: Folder },
                        { id: "customized-files", label: "Customized Files", icon: Sparkles },
                        { id: "studio-projects", label: "Studio Projects", icon: Cpu },
                        { id: "my-websites", label: "My Websites", icon: Globe },
                        { id: "deployments", label: "Deployments", icon: Zap },
                        { id: "wishlist", label: "Wishlist", icon: Heart },
                        { id: "buyer-following", label: "Following", icon: Users },
                        { id: "orders", label: "Orders", icon: CreditCard },
                        { id: "reviews", label: "Reviews", icon: Star },
                        { id: "settings", label: "Profile Settings", icon: Settings },
                      ];

                  return sidebarTabs.map((t) => {
                    const Icon = t.icon;
                    if (t.isLink) {
                      return (
                        <Link
                          key={t.id}
                          href={t.url}
                          className="db-tab-btn"
                          style={{ textDecoration: "none" }}
                        >
                          <Icon className="w-4 h-4 shrink-0" />
                          <span className="truncate">{t.label}</span>
                        </Link>
                      );
                    }
                    return (
                      <button
                        key={t.id}
                        onClick={() => setActiveTab(t.id)}
                        className={cn(
                          "db-tab-btn",
                          activeTab === t.id && "active"
                        )}
                      >
                        <Icon className="w-4 h-4 shrink-0" />
                        <span className="truncate">{t.label}</span>
                        {t.comingSoon && (
                          <span className="ml-auto text-[9px] bg-primary/20 text-primary px-1.5 py-0.5 rounded-full font-semibold border border-primary/30 uppercase tracking-wider scale-90 origin-right shrink-0">
                            Soon
                          </span>
                        )}
                      </button>
                    );
                  });
                })()}
              </div>
            )}

            {/* Right Side Panels */}
            <div className="db-main-content">
              {isSidebarHidden && (
                <div className="flex items-center justify-between pb-1">
                  <button
                    type="button"
                    onClick={toggleSidebar}
                    className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[#141417] hover:bg-[#1a1a20] border border-[#27272a] hover:border-[#c89666]/60 text-xs font-bold text-[#dfb180] transition cursor-pointer shadow-md group"
                  >
                    <PanelLeftOpen className="w-4 h-4 text-[#c89666] group-hover:scale-110 transition-transform" />
                    <span>Show Sidebar Menu</span>
                  </button>
                  <span className="text-[11px] text-[#71717a] font-medium hidden sm:inline">
                    Full-width workspace mode
                  </span>
                </div>
              )}

              {/* === BUYER DASHBOARD HOME === */}
              {activeTab === "buyer-home" && (
                <div className="space-y-6">
                  {/* Premium Greeting Banner */}
                  <motion.div
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4 }}
                    className="db-greeting-banner"
                  >
                    <div className="db-greeting-tag">
                      <Sparkles className="w-3.5 h-3.5" /> Premium Buyer Dashboard
                    </div>
                    <h2 className="db-greeting-title">
                      Welcome back, {user?.fullName || user?.email?.split("@")[0] || "Explorer"}!
                    </h2>
                    <p className="db-greeting-subtitle">
                      Deploy your templates instantly, customize typography and color schemes in your Brand Kit, or invoke custom design iterations on your active project workspaces.
                    </p>
                    <div className="db-banner-btn-group">
                      <Link
                        href="/studio"
                        className="db-banner-btn primary"
                        style={{ textDecoration: "none" }}
                      >
                        <Cpu className="w-3.5 h-3.5" /> Launch Studio Creator
                      </Link>
                      <Link
                        href="/marketplace"
                        className="db-banner-btn secondary"
                        style={{ textDecoration: "none" }}
                      >
                        <ShoppingBag className="w-3.5 h-3.5" /> Browse Marketplace
                      </Link>
                    </div>
                  </motion.div>

                  {/* Dynamic Summary Metric Cards */}
                  {(() => {
                    const purchasedItems = getPurchasedItemsList(orders, hiddenPurchasedTemplates);
                    const customizedItems = getCustomizedItemsList(templateResponse);

                    const buyerMetricCards = [
                      {
                        label: "Purchased Templates",
                        value: purchasedItems.length,
                        icon: Folder,
                        desc: "Ready for download",
                        onClick: () => { setActiveTab("buyer-templates"); setTemplatesSubTab("purchased"); }
                      },
                      {
                        label: "Customized Files",
                        value: customizedItems.length,
                        icon: Sparkles,
                        desc: "Active customized template edits",
                        onClick: () => { setActiveTab("customized-files"); setTemplatesSubTab("customized"); }
                      },
                      {
                        label: "Live Websites",
                        value: deploymentsData.filter(d => d.custom_domain || d.live_url).length,
                        icon: Globe,
                        desc: "Active live websites",
                        onClick: () => setActiveTab("my-websites")
                      },
                      {
                        label: "Hosting Deployments",
                        value: deploymentsData.length,
                        icon: Zap,
                        desc: "Continuous build integrations",
                        onClick: () => setActiveTab("deployments")
                      },
                      {
                        label: "Total Platform Spent",
                        value: formatPrice(totalSpent),
                        icon: CreditCard,
                        desc: "Invoice order transactions",
                        onClick: () => setActiveTab("orders")
                      },
                    ];

                    return (
                      <>
                        <div className="db-metrics-grid">
                          {buyerMetricCards.map(({ label, value, icon: Icon, desc, onClick }) => (
                            <motion.div
                              key={label}
                              whileHover={{ y: -4, scale: 1.01 }}
                              transition={{ duration: 0.2 }}
                              onClick={onClick}
                              className="db-card cursor-pointer hover:border-primary/50 transition-all"
                              style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}
                            >
                              <div className="db-metric-header">
                                <span className="text-xs font-bold uppercase tracking-wider">{label}</span>
                                <div className="p-1.5 bg-primary/10 rounded-lg text-primary">
                                  <Icon className="w-4 h-4" />
                                </div>
                              </div>
                              <div>
                                <div className="db-metric-value">{value}</div>
                                <div className="db-metric-footer">{desc}</div>
                              </div>
                            </motion.div>
                          ))}
                        </div>

                        {/* Recent Edited Studio Projects Showcase on Home */}
                        {customizedItems.length > 0 && (
                          <div className="db-custom-projects-section">
                            <div className="db-custom-section-header">
                              <div className="db-custom-header-left">
                                <div className="db-custom-header-icon">
                                  <Sparkles className="w-4 h-4" />
                                </div>
                                <div>
                                  <h3 className="db-custom-header-title">Your Customized Files &amp; Projects ({customizedItems.length})</h3>
                                  <p className="db-custom-header-sub">Private template drafts customized in Site Studio. Pick up right where you left off.</p>
                                </div>
                              </div>
                              <button
                                type="button"
                                onClick={() => { setActiveTab("customized-files"); setTemplatesSubTab("customized"); }}
                                className="db-custom-view-all-btn"
                              >
                                <span>View All Customized Files ({customizedItems.length})</span>
                                <ExternalLink className="w-3 h-3" />
                              </button>
                            </div>

                            <div className="db-custom-grid">
                              {customizedItems.slice(0, 3).map((item) => {
                                const isPurchased = purchasedItems.some(p => p.template_id === item.id || p.id === item.id);
                                const inCart = isInCart(item.id);

                                return (
                                  <div key={item.id} className="db-custom-card">
                                    <div className="db-custom-card-top">
                                      {isPurchased ? (
                                        <span className="db-custom-purchased-badge">
                                          <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" /> Purchased
                                        </span>
                                      ) : (
                                        <span className="db-custom-draft-badge">
                                          <Sparkles className="w-2.5 h-2.5 text-[#dfb180]" /> Private Draft
                                        </span>
                                      )}
                                      <span className="db-custom-fw-badge">
                                        {item.framework || "HTML"}
                                      </span>
                                    </div>

                                    <div className="db-custom-card-content">
                                      <h4 className="db-custom-card-title" title={item.title}>
                                        {item.title}
                                      </h4>
                                      <p className="db-custom-card-desc">
                                        {item.short_description || item.description || "Custom website modified in Site Studio."}
                                      </p>
                                    </div>

                                    <div className="db-custom-actions-row">
                                      <Link
                                        href={`/preview?template=${item.id}&mode=live`}
                                        className="db-custom-edit-btn"
                                        style={{ color: "#ffffff" }}
                                      >
                                        <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                                        <span>Edit in Studio</span>
                                      </Link>
                                      <a
                                        href={`${API_BASE}/preview/live/${item.id}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="db-custom-icon-btn"
                                        title="Live Demo Preview"
                                      >
                                        <Globe className="w-3.5 h-3.5 text-[#dfb180]" />
                                        <span>Demo</span>
                                      </a>
                                      {isPurchased ? (
                                        <button
                                          type="button"
                                          onClick={() => requestDownloadWithWarning(item, "zip")}
                                          className="db-custom-download-btn"
                                          title="Download Clean Source ZIP"
                                        >
                                          <Download className="w-3.5 h-3.5 text-emerald-600" />
                                          <span>ZIP</span>
                                        </button>
                                      ) : (
                                        <button
                                          type="button"
                                          onClick={() => {
                                            addToCart({
                                              id: item.id,
                                              templateId: item.id,
                                              title: item.title,
                                              price: item.price || 49,
                                              thumbnail: item.thumbnail_url || "",
                                              framework: item.framework || "HTML",
                                              licenseType: "regular",
                                            });
                                          }}
                                          className={cn("db-custom-cart-btn", inCart && "in-cart")}
                                          title={inCart ? "In Cart - Click to view" : "Add to Cart to purchase"}
                                        >
                                          <ShoppingCart className="w-3.5 h-3.5" />
                                          <span>{inCart ? "In Cart ✓" : `Cart ($${item.price || 49})`}</span>
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </>
                    );
                  })()}

                  <div className="db-activity-qa-grid">
                    {/* Recent Activity */}
                    <div className="db-activity-panel">
                      <div className="db-activity-header">
                        <h3 className="db-activity-title">Recent Activity</h3>
                        <span className="db-activity-badge">Live Logs</span>
                      </div>
                      <div className="db-activity-list">
                        {orders.filter(o => o.status === "completed").length === 0 ? (
                          <div className="db-activity-empty">
                            No recent activity logs. Your purchase history will appear here.
                          </div>
                        ) : (
                          orders.filter(o => o.status === "completed").slice(0, 3).map((ord, i) => (
                            <div key={i} className="db-activity-item">
                              <div className="db-activity-item-info">
                                <span className="db-activity-item-title">Purchased &quot;{ord.items?.[0]?.title || "Template"}&quot;</span>
                                <p className="db-activity-item-meta">Order ID: #{ord.id.slice(0, 8)} &bull; Plan: {ord.items?.[0]?.license_type || "Standard"}</p>
                              </div>
                              <span className="db-activity-item-time">Recent</span>
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                    {/* Quick Access Menu */}
                    <div className="db-quick-actions-panel">
                      <h3 className="db-quick-actions-title">Quick Actions</h3>
                      <div className="db-quick-actions-list">
                        {[
                          { label: "Deploy Live Domain", tab: "my-websites", icon: Globe },
                          { label: "Order History", tab: "orders", icon: CreditCard },
                          { label: "Profile Setup", tab: "settings", icon: Settings },
                        ].map((item) => {
                          const Icon = item.icon;
                          return (
                            <button
                              key={item.label}
                              onClick={() => setActiveTab(item.tab)}
                              className="db-quick-action-btn"
                            >
                              <Icon className="db-quick-action-icon" />
                              <span>{item.label}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Performance & Workspace Analytics Visualization */}
                  <div className="p-6 rounded-2xl border border-border bg-card shadow-sm space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/60 pb-3">
                      <div>
                        <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                          <BarChart3 className="w-4 h-4 text-primary" /> Workspace Analytics &amp; Health
                        </h3>
                        <p className="text-xs text-muted-foreground">
                          Real-time computed ratios and resource utilization across your projects.
                        </p>
                      </div>
                      <span className="text-[11px] font-semibold text-muted-foreground">
                        Live Data · Zero Simulated Metrics
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
                      {/* 1. Deployment Reliability Ratio */}
                      <div className="p-4 rounded-xl border border-border bg-muted/20 space-y-2">
                        <div className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider flex items-center justify-between">
                          <span>Deployment Reliability</span>
                          <Zap className="w-3.5 h-3.5 text-amber-500" />
                        </div>
                        <div className="text-2xl font-black font-mono text-foreground">
                          {deploymentsData.length > 0
                            ? `${Math.round(
                                (deploymentsData.filter(d => ['success', 'deployed', 'live'].includes(d.status) || d.live_url || d.custom_domain).length /
                                  deploymentsData.length) *
                                  100
                              )}%`
                            : "N/A"}
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                          {deploymentsData.length > 0
                            ? `${deploymentsData.filter(d => ['success', 'deployed', 'live'].includes(d.status) || d.live_url || d.custom_domain).length} of ${deploymentsData.length} builds active on Edge`
                            : "No deployments yet"}
                        </p>
                      </div>

                      {/* 2. Custom Domain Attachment */}
                      <div className="p-4 rounded-xl border border-border bg-muted/20 space-y-2">
                        <div className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider flex items-center justify-between">
                          <span>Custom Domains</span>
                          <Globe className="w-3.5 h-3.5 text-blue-500" />
                        </div>
                        <div className="text-2xl font-black font-mono text-foreground">
                          {deploymentsData.filter(d => Boolean(d.custom_domain)).length}
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                          Production custom hostnames connected
                        </p>
                      </div>

                      {/* 3. Project Creation Volume */}
                      <div className="p-4 rounded-xl border border-border bg-muted/20 space-y-2">
                        <div className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider flex items-center justify-between">
                          <span>Active Workspaces</span>
                          <Layers className="w-3.5 h-3.5 text-emerald-500" />
                        </div>
                        <div className="text-2xl font-black font-mono text-foreground">
                          {getPurchasedItemsList(orders, hiddenPurchasedTemplates).length +
                            getCustomizedItemsList(templateResponse).length}
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                          {getCustomizedItemsList(templateResponse).length} drafts · {getPurchasedItemsList(orders, hiddenPurchasedTemplates).length} library items
                        </p>
                      </div>
                    </div>

                    {/* Visual Proportional Distribution Bar */}
                    {(() => {
                      const pCount = getPurchasedItemsList(orders, hiddenPurchasedTemplates).length;
                      const cCount = getCustomizedItemsList(templateResponse).length;
                      const dCount = deploymentsData.length;
                      const totalAssets = pCount + cCount + dCount;

                      if (totalAssets === 0) return null;

                      const pPct = Math.round((pCount / totalAssets) * 100);
                      const cPct = Math.round((cCount / totalAssets) * 100);
                      const dPct = 100 - pPct - cPct;

                      return (
                        <div className="space-y-1.5 pt-2">
                          <div className="flex justify-between text-[11px] font-semibold text-muted-foreground">
                            <span>Asset Composition</span>
                            <span>{totalAssets} Total Assets</span>
                          </div>
                          <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden flex">
                            {pCount > 0 && (
                              <div
                                style={{ width: `${pPct}%` }}
                                className="bg-primary transition-all duration-300"
                                title={`Purchased Templates: ${pCount} (${pPct}%)`}
                              />
                            )}
                            {cCount > 0 && (
                              <div
                                style={{ width: `${cPct}%` }}
                                className="bg-amber-500 transition-all duration-300"
                                title={`Customized Drafts: ${cCount} (${cPct}%)`}
                              />
                            )}
                            {dCount > 0 && (
                              <div
                                style={{ width: `${dPct}%` }}
                                className="bg-emerald-500 transition-all duration-300"
                                title={`Deployments: ${dCount} (${dPct}%)`}
                              />
                            )}
                          </div>
                          <div className="flex flex-wrap gap-4 text-[10px] text-muted-foreground pt-1">
                            <span className="flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full bg-primary" />
                              Purchased ({pCount})
                            </span>
                            <span className="flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full bg-amber-500" />
                              Customized Drafts ({cCount})
                            </span>
                            <span className="flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full bg-emerald-500" />
                              Edge Deployments ({dCount})
                            </span>
                          </div>
                        </div>
                      );
                    })()}
                  </div>

                  {/* Recommendations */}
                  <div className="db-recommendations-section">
                    <h3 className="db-recommendations-title">Recommended for You</h3>
                    <div className="db-recommendations-grid">
                      {recommendedTemplates.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground text-xs col-span-full border border-dashed border-border/40 rounded-xl bg-muted/5">
                          No recommendations available at this time. Browse the marketplace to find templates.
                        </div>
                      ) : (
                        recommendedTemplates.map((t, idx) => (
                          <div key={t.id || idx} className="db-recommendation-card">
                            <div>
                              <div className="db-card-header-row">
                                <div className="db-card-title" title={t.title}>{t.title}</div>
                                <span className="db-card-rating">{(t.rating_avg || 5.0).toFixed(1)} ★</span>
                              </div>
                              <div className="db-card-framework">{t.framework || "React"}</div>
                            </div>
                            <div className="db-card-footer-row">
                              <span className="db-card-price">{formatPrice(t.price)}</span>
                              <Link href={`/marketplace/${t.slug}`} className="db-card-action-link">View Product</Link>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* === BUYER TEMPLATES & CUSTOMIZED FILES (UNIFIED MY TEMPLATES) === */}
              {(activeTab === "buyer-templates" || activeTab === "customized-files") && renderMyTemplatesSection()}

              {/* === STUDIO PROJECTS === */}
              {activeTab === "studio-projects" && (() => {
                const purchasedTemplateIds = new Set(
                  orders.filter(o => o.status === "completed").flatMap(o => (o.items || []).map(i => i.template_id))
                );
                const allUserTemplates = Array.isArray(templateResponse) ? templateResponse : [];
                // Strictly include only projects generated by Studio Creator (exclude customized/edited drafts)
                const createdStudioProjects = allUserTemplates.filter(item => !purchasedTemplateIds.has(item.id) && isStudioProjectItem(item));
                const purchasedStudioProjects = allUserTemplates.filter(item => purchasedTemplateIds.has(item.id) && isStudioProjectItem(item));

                const query = (studioProjectsSearch || "").toLowerCase().trim();
                const filteredCreated = createdStudioProjects.filter(item =>
                  !query ||
                  item.title?.toLowerCase().includes(query) ||
                  item.framework?.toLowerCase().includes(query) ||
                  item.short_description?.toLowerCase().includes(query) ||
                  item.description?.toLowerCase().includes(query)
                );

                const filteredPurchased = purchasedStudioProjects.filter(item =>
                  !query ||
                  item.title?.toLowerCase().includes(query) ||
                  item.framework?.toLowerCase().includes(query) ||
                  item.short_description?.toLowerCase().includes(query) ||
                  item.description?.toLowerCase().includes(query)
                );

                return (
                  <div className="mt-container">
                    {/* ── Main Header Card ── */}
                    <div className="mt-header-card">
                      {/* Top Row: Title + Description + Top Action CTA */}
                      <div className="mt-header-top">
                        <div className="mt-header-title-box">
                          <div className="mt-header-icon">
                            <Cpu className="w-6 h-6" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <h2 className="mt-title">
                                Studio Projects Workspace
                                <span className="mt-count-badge">
                                  {studioProjectsSubTab === "created"
                                    ? `${createdStudioProjects.length} Studio Projects`
                                    : `${purchasedStudioProjects.length} Purchased Projects`}
                                </span>
                              </h2>
                            </div>
                            <p className="mt-desc">
                              Manage projects generated with the Studio Creator. Open in Studio, deploy live, or download full source code.
                            </p>
                          </div>
                        </div>

                        {/* Top CTA buttons */}
                        <div className="flex items-center gap-2">
                          {studioProjectsSubTab === "created" && createdStudioProjects.length > 0 && (
                            <button
                              type="button"
                              onClick={handlePurgeAllDrafts}
                              disabled={purgingDrafts}
                              className="px-3.5 py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/30 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
                              title="Delete all draft projects"
                            >
                              {purgingDrafts ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                              <span>Purge All Drafts</span>
                            </button>
                          )}
                          <Link
                            href="/marketplace"
                            className="mt-cta-btn"
                          >
                            <ShoppingBag className="w-4 h-4" />
                            <span>Explore Marketplace</span>
                          </Link>
                        </div>
                      </div>

                      {/* Toolbar Row: Subtabs Switcher + Search + View Toggle */}
                      <div className="mt-toolbar">
                        <div className="mt-tabs">
                          <button
                            type="button"
                            onClick={() => setStudioProjectsSubTab("created")}
                            className={cn("mt-tab-btn", studioProjectsSubTab === "created" && "active")}
                          >
                            <Sparkles className="w-4 h-4" style={{ color: studioProjectsSubTab === "created" ? "#ec4899" : "#64748b" }} />
                            <span>Studio Projects</span>
                            <span className={cn("mt-tab-count", studioProjectsSubTab === "created" ? "active" : "inactive")}>
                              {createdStudioProjects.length}
                            </span>
                          </button>

                          <button
                            type="button"
                            onClick={() => setStudioProjectsSubTab("purchased")}
                            className={cn("mt-tab-btn", studioProjectsSubTab === "purchased" && "active")}
                          >
                            <CheckCircle2 className="w-4 h-4" style={{ color: studioProjectsSubTab === "purchased" ? "#b5804f" : "#64748b" }} />
                            <span>Purchased Projects</span>
                            <span className={cn("mt-tab-count", studioProjectsSubTab === "purchased" ? "active" : "inactive")}>
                              {purchasedStudioProjects.length}
                            </span>
                          </button>
                        </div>

                        {/* Search & Grid / Table Toggle */}
                        <div className="flex items-center gap-2.5 flex-wrap">
                          <div className="mt-search-box">
                            <Search className="mt-search-icon" />
                            <input
                              type="text"
                              placeholder="Search studio projects..."
                              value={studioProjectsSearch}
                              onChange={(e) => setStudioProjectsSearch(e.target.value)}
                              className="mt-search-input"
                            />
                            {studioProjectsSearch && (
                              <button
                                type="button"
                                onClick={() => setStudioProjectsSearch("")}
                                className="mt-search-clear"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>

                          <div className="mt-view-toggle">
                            <button
                              type="button"
                              onClick={() => handleSetStudioProjectsView("grid")}
                              className={cn("mt-view-btn", studioProjectsView === "grid" && "active")}
                              title="Grid View"
                            >
                              <LayoutGrid className="w-4 h-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSetStudioProjectsView("table")}
                              className={cn("mt-view-btn", studioProjectsView === "table" && "active")}
                              title="Table View"
                            >
                              <List className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* ── Content Area ── */}
                    {templatesLoading && (!templateResponse || templateResponse.length === 0) ? (
                      <div className="py-20 text-center rounded-2xl border border-border/50 bg-card">
                        <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#dfb180]" />
                        <p className="text-xs text-muted-foreground mt-3 font-semibold">Loading your studio projects...</p>
                      </div>
                    ) : studioProjectsSubTab === "created" ? (
                      /* Draft / Unpurchased Studio Projects */
                      createdStudioProjects.length === 0 ? (
                        <div className="mt-empty-card">
                          <div className="mt-empty-icon">
                            <Cpu className="w-7 h-7" />
                          </div>
                          <h4 className="mt-empty-title">No Studio Projects Yet</h4>
                          <p className="mt-empty-desc">
                            You haven't synthesized any projects with the Studio Creator yet. Use the Studio Creator to generate full-stack websites automatically.
                          </p>
                          <Link href="/studio" className="mt-empty-btn">
                            <Sparkles className="w-4 h-4" /> Open Studio Creator
                          </Link>
                        </div>
                      ) : filteredCreated.length === 0 ? (
                        <div className="text-center py-12 px-4 rounded-2xl border border-border/40 bg-card/30">
                          <p className="text-xs text-muted-foreground font-semibold">No draft studio projects match &ldquo;{studioProjectsSearch}&rdquo;</p>
                          <button
                            type="button"
                            onClick={() => setStudioProjectsSearch("")}
                            className="mt-3 text-xs text-primary underline font-bold bg-transparent border-0 cursor-pointer"
                          >
                            Clear Search Filter
                          </button>
                        </div>
                      ) : studioProjectsView === "grid" ? (
                        <div className="db-templates-grid">
                          {filteredCreated.map((item) => {
                            const inCart = isInCart(item.id);
                            const isStudio = item.tags?.includes("studio-project") || item.template_origin === "studio";

                            return (
                              <div key={item.id} className="db-template-card group">
                                {/* Thumbnail Header */}
                                <div className="db-template-thumb">
                                  {item.thumbnail_url ? (
                                    <img
                                      src={item.thumbnail_url}
                                      alt={item.title || "Studio Project"}
                                      className="db-template-img"
                                      onError={(e) => {
                                        e.target.style.display = "none";
                                        if (e.target.nextElementSibling) e.target.nextElementSibling.style.display = "flex";
                                      }}
                                    />
                                  ) : null}
                                  <div
                                    className="w-full h-full absolute inset-0 flex items-center justify-center"
                                    style={{
                                      display: item.thumbnail_url ? "none" : "flex",
                                      background: "linear-gradient(135deg, hsla(var(--primary)/0.2) 0%, hsla(var(--secondary)/0.2) 100%)",
                                    }}
                                  >
                                    <span style={{ fontSize: "2rem" }}>💻</span>
                                  </div>

                                  {/* Top-Left Floating Badge */}
                                  <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
                                    <span className="px-2 py-0.5 bg-gradient-to-r from-[#c89666] to-[#b5804f] text-[#09090b] text-[9px] font-black uppercase tracking-wider rounded-full shadow-sm flex items-center gap-1">
                                      <Sparkles className="w-2.5 h-2.5" /> Draft Project
                                    </span>
                                  </div>

                                  {/* Top-Right Framework Badge & Delete */}
                                  <div className="absolute top-2.5 right-2.5 flex items-center gap-1.5">
                                    <span className="px-2 py-0.5 bg-black/60 backdrop-blur-md text-white text-[9px] font-mono font-bold uppercase rounded-md border border-white/10">
                                      {item.framework || "HTML"}
                                    </span>
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteCustomDraft(item.id, item.title);
                                      }}
                                      className="w-5 h-5 rounded-md bg-black/60 hover:bg-rose-600/80 backdrop-blur-md text-white/70 hover:text-white flex items-center justify-center border border-white/10 transition-colors cursor-pointer"
                                      title="Delete draft"
                                    >
                                      <Trash2 className="w-3 h-3" />
                                    </button>
                                  </div>
                                </div>

                                {/* Card Content Body */}
                                <div className="db-template-body">
                                  <div className="db-template-header-text">
                                    <h4 className="db-template-title" title={item.title}>
                                      {item.title || "Studio Project"}
                                    </h4>
                                    <p className="db-template-desc">
                                      {item.short_description || item.description || "Custom generated prototype."}
                                    </p>
                                  </div>

                                  {/* Pricing & Metadata Strip */}
                                  <div className="db-template-meta-row">
                                    <div>
                                      <span className="text-[11px] text-muted-foreground">Draft ID: </span>
                                      <span className="font-mono text-muted-foreground font-bold">#{String(item.id || "").slice(0, 6).toUpperCase()}</span>
                                    </div>
                                    <span className="text-[10px] font-bold text-amber-400 flex items-center gap-1">
                                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" /> Editable
                                    </span>
                                  </div>

                                  {/* Action Buttons Hub */}
                                  <div className="db-template-actions-box">
                                    {/* Primary Action Button */}
                                    {isStudio ? (
                                      <Link
                                        href={`/studio/launch?template=${item.slug || item.id}`}
                                        className="db-btn-ai-studio"
                                      >
                                        <Rocket className="w-3.5 h-3.5 text-white" />
                                        <span style={{ color: "#ffffff" }}>Launch Hub</span>
                                      </Link>
                                    ) : (
                                      <Link
                                        href={`/preview?template=${item.slug || item.id}`}
                                        className="db-btn-ai-studio"
                                      >
                                        <Sparkles className="w-3.5 h-3.5 text-white" />
                                        <span style={{ color: "#ffffff" }}>Open in Studio</span>
                                      </Link>
                                    )}

                                    {/* Action Grid (2x2) */}
                                    <div className="db-template-btn-grid">
                                      <button
                                        type="button"
                                        onClick={() => {
                                          setDeployTemplateId(item.id);
                                          setDeployProjectName(item.title || "My Studio Project");
                                          setIsDeployModalOpen(true);
                                        }}
                                        className="db-btn-publish"
                                        title="Deploy / Publish"
                                      >
                                        <Zap className="w-3 h-3 text-white" />
                                        <span style={{ color: "#ffffff" }}>Deploy</span>
                                      </button>

                                      <a
                                        href={`${API_BASE}/preview/live/${item.id}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="db-btn-secondary"
                                        title="Live Demo Preview"
                                      >
                                        <Globe className="w-3.5 h-3.5 text-[#dfb180]" />
                                        <span>Demo</span>
                                      </a>

                                      {!isStudio && (
                                        <button
                                          type="button"
                                          onClick={() => {
                                            addToCart({
                                              id: item.id,
                                              templateId: item.id,
                                              title: item.title,
                                              price: item.price || 49,
                                              thumbnail: item.thumbnail_url || "",
                                              framework: item.framework || "HTML",
                                              licenseType: "regular",
                                            });
                                          }}
                                          className={cn("db-btn-review", inCart && "bg-[#c89666]/15 text-[#dfb180] font-extrabold")}
                                          title="Add to cart"
                                        >
                                          <ShoppingCart className="w-3.5 h-3.5" />
                                          <span>{inCart ? "In Cart" : `Buy ($${item.price || 49})`}</span>
                                        </button>
                                      )}

                                      <button
                                        type="button"
                                        onClick={() => handleDeleteCustomDraft(item.id, item.title)}
                                        className="db-btn-secondary text-rose-400 hover:text-rose-300"
                                        title="Delete draft"
                                      >
                                        <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                                        <span>Delete</span>
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        /* Table View for Draft Studio Projects */
                        <div className="overflow-x-auto rounded-2xl border border-border/50 bg-card">
                          <table className="w-full text-left text-xs">
                            <thead>
                              <tr className="border-b border-border/40 bg-muted/40 font-bold uppercase text-muted-foreground text-[10px] tracking-wider">
                                <th className="p-4">Studio Draft Project</th>
                                <th className="p-4">Framework</th>
                                <th className="p-4">Status</th>
                                <th className="p-4 text-right">Actions</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border/30">
                              {filteredCreated.map((item) => {
                                const isStudio = item.tags?.includes("studio-project") || item.template_origin === "studio";

                                return (
                                  <tr key={item.id} className="hover:bg-muted/20 transition-colors">
                                    <td className="p-4">
                                      <div className="flex items-center gap-3">
                                        <div className="w-12 h-10 rounded-lg overflow-hidden bg-muted shrink-0 relative">
                                          {item.thumbnail_url ? (
                                            <img
                                              src={item.thumbnail_url}
                                              alt=""
                                              className="w-full h-full object-cover"
                                              onError={(e) => { e.target.style.display = "none"; }}
                                            />
                                          ) : (
                                            <div className="w-full h-full flex items-center justify-center text-sm">💻</div>
                                          )}
                                        </div>
                                        <div>
                                          <div className="font-bold text-foreground text-xs flex items-center gap-2">
                                            <span>{item.title || "Studio Project"}</span>
                                            <span className="font-mono text-[10px] text-muted-foreground">#{String(item.id || "").slice(0, 6).toUpperCase()}</span>
                                          </div>
                                          <div className="text-[11px] text-muted-foreground line-clamp-1">{item.short_description || item.description || "Custom generated prototype."}</div>
                                        </div>
                                      </div>
                                    </td>
                                    <td className="p-4">
                                      <span className="px-2 py-0.5 bg-muted text-foreground border border-border/50 rounded-md font-mono font-bold uppercase text-[10px]">
                                        {item.framework || "HTML"}
                                      </span>
                                    </td>
                                    <td className="p-4">
                                      <span className="px-2 py-0.5 bg-amber-500/10 text-amber-500 border border-amber-500/20 text-[10px] font-bold rounded-full uppercase flex items-center gap-1 w-fit">
                                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" /> Draft
                                      </span>
                                    </td>
                                    <td className="p-4 text-right">
                                      <div className="flex items-center justify-end gap-1.5">
                                        {isStudio ? (
                                          <Link
                                            href={`/studio/launch?template=${item.slug || item.id}`}
                                            className="px-2.5 py-1.5 bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] text-[11px] font-black rounded-lg flex items-center gap-1 shadow-sm transition-all"
                                          >
                                            <Rocket className="w-3 h-3 stroke-[2.5]" /> Launch Hub
                                          </Link>
                                        ) : (
                                          <Link
                                            href={`/preview?template=${item.slug || item.id}`}
                                            className="px-2.5 py-1.5 bg-primary text-white text-[11px] font-bold rounded-lg flex items-center gap-1 shadow-sm"
                                          >
                                            <Sparkles className="w-3 h-3" /> Studio
                                          </Link>
                                        )}
                                        <button
                                          type="button"
                                          onClick={() => {
                                            setDeployTemplateId(item.id);
                                            setDeployProjectName(item.title || "My Studio Project");
                                            setIsDeployModalOpen(true);
                                          }}
                                          className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg border border-border/40 bg-muted/40 cursor-pointer"
                                          title="Deploy"
                                        >
                                          <Zap className="w-3.5 h-3.5" />
                                        </button>
                                        <a
                                          href={`${API_BASE}/preview/live/${item.id}`}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg border border-border/40 bg-muted/40"
                                          title="Live Demo Preview"
                                        >
                                          <Globe className="w-3.5 h-3.5" />
                                        </a>
                                        <button
                                          type="button"
                                          onClick={() => handleDeleteCustomDraft(item.id, item.title)}
                                          className="p-1.5 text-muted-foreground hover:text-rose-400 rounded-lg border border-border/40 bg-muted/40 cursor-pointer"
                                          title="Delete Draft"
                                        >
                                          <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                      </div>
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )
                    ) : (
                      /* Purchased Studio Projects */
                      purchasedStudioProjects.length === 0 ? (
                        <div className="mt-empty-card">
                          <div className="mt-empty-icon">
                            <Folder className="w-7 h-7" />
                          </div>
                          <h4 className="mt-empty-title">No Purchased Studio Projects</h4>
                          <p className="mt-empty-desc">
                            When you purchase a custom studio project from your drafts or marketplace, its full source code and direct download links will appear here.
                          </p>
                          <Link href="/marketplace" className="mt-empty-btn">
                            <ShoppingBag className="w-4 h-4" /> Explore Marketplace
                          </Link>
                        </div>
                      ) : filteredPurchased.length === 0 ? (
                        <div className="text-center py-12 px-4 rounded-2xl border border-border/40 bg-card/30">
                          <p className="text-xs text-muted-foreground font-semibold">No purchased studio projects match &ldquo;{studioProjectsSearch}&rdquo;</p>
                          <button
                            type="button"
                            onClick={() => setStudioProjectsSearch("")}
                            className="mt-3 text-xs text-primary underline font-bold bg-transparent border-0 cursor-pointer"
                          >
                            Clear Search Filter
                          </button>
                        </div>
                      ) : studioProjectsView === "grid" ? (
                        <div className="db-templates-grid">
                          {filteredPurchased.map((item) => (
                            <div key={item.id} className="db-template-card group">
                              {/* Thumbnail Header */}
                              <div className="db-template-thumb">
                                {item.thumbnail_url ? (
                                  <img
                                    src={item.thumbnail_url}
                                    alt={item.title || "Studio Project"}
                                    className="db-template-img"
                                    onError={(e) => {
                                      e.target.style.display = "none";
                                      if (e.target.nextElementSibling) e.target.nextElementSibling.style.display = "flex";
                                    }}
                                  />
                                ) : null}
                                <div
                                  className="w-full h-full absolute inset-0 flex items-center justify-center"
                                  style={{
                                    display: item.thumbnail_url ? "none" : "flex",
                                    background: "linear-gradient(135deg, hsla(var(--primary)/0.15) 0%, hsla(var(--secondary)/0.15) 100%)",
                                  }}
                                >
                                  <Folder className="w-8 h-8 text-primary opacity-60" />
                                </div>

                                {/* Top-Left Floating Badges */}
                                <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
                                  <span className="px-2 py-0.5 bg-emerald-500 text-white text-[9px] font-black uppercase tracking-wider rounded-full shadow-sm flex items-center gap-1">
                                    <CheckCircle2 className="w-2.5 h-2.5" /> Purchased
                                  </span>
                                </div>

                                {/* Top-Right Framework Badge */}
                                <div className="absolute top-2.5 right-2.5 flex items-center gap-1.5">
                                  <span className="px-2 py-0.5 bg-black/60 backdrop-blur-md text-white text-[9px] font-mono font-bold uppercase rounded-md border border-white/10">
                                    {item.framework || "HTML"}
                                  </span>
                                </div>
                              </div>

                              {/* Card Content Body */}
                              <div className="db-template-body">
                                <div className="db-template-header-text">
                                  <h4 className="db-template-title" title={item.title}>
                                    {item.title || "Purchased Project"}
                                  </h4>
                                  <p className="db-template-desc">
                                    {item.short_description || "Custom generated prototype."}
                                  </p>
                                </div>

                                {/* Metadata Strip */}
                                <div className="db-template-meta-row">
                                  <div>
                                    <span className="text-[11px] text-muted-foreground">Price Paid: </span>
                                    <span className="font-extrabold text-foreground">{formatPrice(item.price || 0)}</span>
                                  </div>
                                  <span className="text-[10px] font-medium text-muted-foreground">
                                    Full Access
                                  </span>
                                </div>

                                {/* Action Buttons Hub */}
                                <div className="db-template-actions-box">
                                  {/* Primary Download Button */}
                                  <button
                                    type="button"
                                    onClick={() => requestDownloadWithWarning(item, "zip")}
                                    className="db-btn-ai-studio"
                                  >
                                    <Download className="w-3.5 h-3.5 text-white" />
                                    <span style={{ color: "#ffffff" }}>Download Source ZIP</span>
                                  </button>

                                  {/* Secondary Action Grid */}
                                  <div className="db-template-btn-grid">
                                    <Link
                                      href={`/preview?template=${item.slug || item.id}`}
                                      className="db-btn-secondary"
                                      title="Open in Studio"
                                    >
                                      <Sparkles className="w-3.5 h-3.5 text-[#dfb180]" />
                                      <span>Editor</span>
                                    </Link>

                                    <a
                                      href={`${API_BASE}/preview/live/${item.id}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="db-btn-secondary"
                                      title="Live Demo Preview"
                                    >
                                      <Globe className="w-3.5 h-3.5 text-[#dfb180]" />
                                      <span>Demo</span>
                                    </a>

                                    <button
                                      type="button"
                                      onClick={() => {
                                        setDeployTemplateId(item.id);
                                        setDeployProjectName(item.title || "My Studio Project");
                                        setIsDeployModalOpen(true);
                                      }}
                                      className="db-btn-publish"
                                      title="Deploy / Publish"
                                    >
                                      <Zap className="w-3 h-3 text-white" />
                                      <span style={{ color: "#ffffff" }}>Deploy</span>
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        /* Table View for Purchased Studio Projects */
                        <div className="overflow-x-auto rounded-2xl border border-border/50 bg-card">
                          <table className="w-full text-left text-xs">
                            <thead>
                              <tr className="border-b border-border/40 bg-muted/40 font-bold uppercase text-muted-foreground text-[10px] tracking-wider">
                                <th className="p-4">Studio Project</th>
                                <th className="p-4">Framework</th>
                                <th className="p-4">Price Paid</th>
                                <th className="p-4">Access</th>
                                <th className="p-4 text-right">Actions</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border/30">
                              {filteredPurchased.map((item) => (
                                <tr key={item.id} className="hover:bg-muted/20 transition-colors">
                                  <td className="p-4">
                                    <div className="flex items-center gap-3">
                                      <div className="w-12 h-10 rounded-lg overflow-hidden bg-muted shrink-0 relative">
                                        {item.thumbnail_url ? (
                                          <img
                                            src={item.thumbnail_url}
                                            alt=""
                                            className="w-full h-full object-cover"
                                            onError={(e) => { e.target.style.display = "none"; }}
                                          />
                                        ) : (
                                          <div className="w-full h-full flex items-center justify-center text-sm">📁</div>
                                        )}
                                      </div>
                                      <div>
                                        <div className="font-bold text-foreground text-xs">{item.title || "Purchased Project"}</div>
                                        <div className="text-[11px] text-muted-foreground line-clamp-1">{item.short_description || "Custom generated prototype."}</div>
                                      </div>
                                    </div>
                                  </td>
                                  <td className="p-4">
                                    <span className="px-2 py-0.5 bg-muted text-foreground border border-border/50 rounded-md font-mono font-bold uppercase text-[10px]">
                                      {item.framework || "HTML"}
                                    </span>
                                  </td>
                                  <td className="p-4 font-bold text-foreground">{formatPrice(item.price || 0)}</td>
                                  <td className="p-4">
                                    <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[10px] font-bold rounded-full uppercase">
                                      Full Access
                                    </span>
                                  </td>
                                  <td className="p-4 text-right">
                                    <div className="flex items-center justify-end gap-1.5">
                                      <button
                                        type="button"
                                        onClick={() => requestDownloadWithWarning(item, "zip")}
                                        className="px-2.5 py-1.5 bg-primary text-white text-[11px] font-bold rounded-lg flex items-center gap-1 shadow-sm cursor-pointer"
                                      >
                                        <Download className="w-3 h-3" /> Download ZIP
                                      </button>
                                      <Link
                                        href={`/preview?template=${item.slug || item.id}`}
                                        className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg border border-border/40 bg-muted/40"
                                        title="Editor"
                                      >
                                        <Sparkles className="w-3.5 h-3.5 text-[#dfb180]" />
                                      </Link>
                                      <a
                                        href={`${API_BASE}/preview/live/${item.id}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg border border-border/40 bg-muted/40"
                                        title="Live Demo Preview"
                                      >
                                        <Globe className="w-3.5 h-3.5 text-[#dfb180]" />
                                      </a>
                                      <button
                                        type="button"
                                        onClick={() => {
                                          setDeployTemplateId(item.id);
                                          setDeployProjectName(item.title || "My Studio Project");
                                          setIsDeployModalOpen(true);
                                        }}
                                        className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg border border-border/40 bg-muted/40 cursor-pointer"
                                        title="Deploy"
                                      >
                                        <Zap className="w-3.5 h-3.5 text-white" />
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )
                    )}
                  </div>
                );
              })()}

              {/* === MY WEBSITES === */}
              {activeTab === "my-websites" && (
                <div className="rounded-xl border border-[#27272a] bg-[#0c0c0e] p-5 sm:p-6 space-y-6">
                  {/* Top Bar */}
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#222226] pb-4">
                    <div>
                      <h3 className="text-lg font-bold text-white flex items-center gap-2">
                        <Globe className="w-5 h-5 text-[#c89666]" />
                        <span>Websites &amp; Custom Domains</span>
                      </h3>
                      <p className="text-xs text-[#a8a29e] mt-0.5">
                        Link custom domains and manage DNS routing.
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2.5 py-1 rounded bg-[#18181d] text-[#dfb180] border border-[#2e2e38] flex items-center gap-1.5 font-medium">
                        <ShieldCheck className="w-3.5 h-3.5 text-[#c89666]" /> SSL Included
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          setDeployProjectName("");
                          setDeployTemplateId("");
                          setIsDeployModalOpen(true);
                        }}
                        className="px-3 py-1.5 rounded-lg bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] text-xs font-bold transition flex items-center gap-1 cursor-pointer"
                      >
                        <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
                        <span>New Site</span>
                      </button>
                    </div>
                  </div>

                  {/* Left & Right Grid */}
                  <div className="my-websites-split-grid">

                    {/* ── LEFT SIDE: WEBSITES & CONNECT DOMAIN ── */}
                    <div className="space-y-5 min-w-0">

                      {/* 1. Live Sites List */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between pb-2 border-b border-[#222226]">
                          <div className="flex items-center gap-2">
                            <Server className="w-4 h-4 text-[#c89666]" />
                            <span className="text-sm font-bold text-white">Live Sites</span>
                            <span className="text-xs text-[#a8a29e]">({deploymentsData.length})</span>
                          </div>
                          <span className="text-[11px] text-[#71717a]">Click site to target</span>
                        </div>

                        {deploymentsData.length === 0 ? (
                          <div className="py-6 text-center text-xs text-[#a8a29e] border border-dashed border-[#222226] rounded-lg">
                            <p>No active sites deployed.</p>
                            <button
                              type="button"
                              onClick={() => setIsDeployModalOpen(true)}
                              className="mt-2 text-[#dfb180] hover:underline font-bold inline-flex items-center gap-1 cursor-pointer"
                            >
                              <Plus className="w-3.5 h-3.5" /> Deploy a website
                            </button>
                          </div>
                        ) : (
                          <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                            {deploymentsData.map((d) => {
                              const isSelected = (selectedTargetDeployment?.id === d.id) || (connectSelectedDeploymentId === d.id);
                              const siteLiveUrl = d.live_url || `http://localhost:8000/sites/${d.site_id}/`;
                              return (
                                <div
                                  key={d.id}
                                  onClick={() => handleSelectTargetDeployment(d)}
                                  className={`p-3 rounded-lg border transition cursor-pointer flex items-center justify-between gap-3 ${isSelected
                                      ? "border-[#c89666] bg-[#c89666]/10 text-white shadow-xs"
                                      : "border-[#222226] bg-[#121216] hover:border-[#33333a] text-[#d4d4d8]"
                                    }`}
                                >
                                  <div className="min-w-0 flex items-center gap-2.5">
                                    <div className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center shrink-0 ${isSelected ? "border-[#c89666] bg-[#c89666]" : "border-[#52525b]"
                                      }`}>
                                      {isSelected && <Check className="w-2.5 h-2.5 text-[#09090b] stroke-[3]" />}
                                    </div>
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-2">
                                        <span className="text-xs font-bold text-white truncate">{d.project_name || "Untitled"}</span>
                                        <span className="text-[10px] font-mono text-[#a8a29e]">{d.site_id}</span>
                                      </div>
                                      <div className="flex items-center gap-2 mt-0.5 text-[11px]">
                                        <a
                                          href={siteLiveUrl}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          onClick={(e) => e.stopPropagation()}
                                          style={{ color: "#dfb180" }}
                                          className="site-live-link font-mono hover:underline inline-flex items-center gap-1 truncate"
                                        >
                                          <ExternalLink className="w-2.5 h-2.5 text-[#c89666]" /> Live URL
                                        </a>
                                        {d.custom_domain && (
                                          <span className="text-emerald-400 font-mono text-[10px]">&bull; {d.custom_domain}</span>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                  <span className={`text-[11px] font-bold shrink-0 ${isSelected ? "text-[#dfb180]" : "text-[#71717a]"}`}>
                                    {isSelected ? "Target ✓" : "Select"}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      {/* 2. Connect Existing Domain via DNS */}
                      <div className="space-y-3 pt-3 border-t border-[#222226]">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <ShieldCheck className="w-4 h-4 text-[#c89666]" />
                            <span className="text-sm font-bold text-white">Connect Domain</span>
                          </div>
                          <span className="text-[11px] text-[#71717a]">
                            Target: <strong className="text-white">{selectedTargetDeployment?.project_name || "None"}</strong>
                          </span>
                        </div>

                        <form onSubmit={handleVerifyOwnershipAndConnect} className="space-y-2.5">
                          <div className="flex gap-2">
                            <input
                              type="text"
                              required
                              placeholder="yourdomain.com"
                              value={connectDomainName}
                              onChange={(e) => {
                                const val = e.target.value;
                                setConnectDomainName(val);
                                setOwnershipMessage(null);
                                handleCheckDomainChallenge(val);
                              }}
                              className="flex-1 px-3 py-2 rounded-lg bg-[#09090b] border border-[#27272a] text-white font-mono text-xs outline-none focus:border-[#c89666]"
                            />
                            <button
                              type="button"
                              onClick={() => handleCheckDomainChallenge(connectDomainName)}
                              disabled={challengeLoading || !connectDomainName}
                              className="px-3.5 py-2 rounded-lg bg-[#222228] hover:bg-[#2c2c34] text-white text-xs font-semibold border border-[#383842] shrink-0 disabled:opacity-50 cursor-pointer"
                            >
                              {challengeLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Check DNS"}
                            </button>
                          </div>

                          {ownershipMessage && (
                            <div className={`p-2.5 rounded-lg text-xs flex items-start gap-2 ${ownershipMessage.type === "success"
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : ownershipMessage.type === "warning"
                                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                                  : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                              }`}>
                              {ownershipMessage.type === "success" ? (
                                <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                              ) : (
                                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                              )}
                              <span>{ownershipMessage.text}</span>
                            </div>
                          )}

                          {domainChallengeData && !domainChallengeData.is_protected && (
                            <div className="space-y-2 pt-1">
                              {/* DNS Table */}
                              <div className="overflow-x-auto rounded border border-[#222226]">
                                <table className="w-full text-[11px] font-mono">
                                  <thead>
                                    <tr className="text-[#a8a29e] bg-[#121216] border-b border-[#222226] text-left">
                                      <th className="py-1.5 px-2.5 font-sans font-semibold">Type</th>
                                      <th className="py-1.5 px-2.5 font-sans font-semibold">Host</th>
                                      <th className="py-1.5 px-2.5 font-sans font-semibold">Value</th>
                                      <th className="py-1.5 px-2.5 text-right font-sans font-semibold">Copy</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-[#222226]">
                                    <tr>
                                      <td className="py-2 px-2.5 text-[#dfb180] font-bold">TXT</td>
                                      <td className="py-2 px-2.5 text-white truncate max-w-[80px]">{domainChallengeData.txt_host || "_studio-challenge"}</td>
                                      <td className="py-2 px-2.5 text-[#a8a29e] truncate max-w-[130px]" title={domainChallengeData.txt_value}>{domainChallengeData.txt_value}</td>
                                      <td className="py-2 px-2.5 text-right">
                                        <button
                                          type="button"
                                          onClick={() => handleCopyDnsText(domainChallengeData.txt_value, "txt_value")}
                                          className="text-[#a8a29e] hover:text-white p-0.5 cursor-pointer"
                                        >
                                          {copiedDnsKey === "txt_value" ? <Check className="w-3 h-3 text-emerald-400 inline" /> : <Copy className="w-3 h-3 inline" />}
                                        </button>
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="py-2 px-2.5 text-emerald-400 font-bold">A</td>
                                      <td className="py-2 px-2.5 text-white">@</td>
                                      <td className="py-2 px-2.5 text-[#a8a29e]">{domainChallengeData.a_value || "149.28.243.12"}</td>
                                      <td className="py-2 px-2.5 text-right">
                                        <button
                                          type="button"
                                          onClick={() => handleCopyDnsText(domainChallengeData.a_value || "149.28.243.12", "a_value")}
                                          className="text-[#a8a29e] hover:text-white p-0.5 cursor-pointer"
                                        >
                                          {copiedDnsKey === "a_value" ? <Check className="w-3 h-3 text-emerald-400 inline" /> : <Copy className="w-3 h-3 inline" />}
                                        </button>
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="py-2 px-2.5 text-sky-400 font-bold">CNAME</td>
                                      <td className="py-2 px-2.5 text-white">www</td>
                                      <td className="py-2 px-2.5 text-[#a8a29e]">{domainChallengeData.cname_value || "site-studio.live"}</td>
                                      <td className="py-2 px-2.5 text-right">
                                        <button
                                          type="button"
                                          onClick={() => handleCopyDnsText(domainChallengeData.cname_value || "site-studio.live", "cname_value")}
                                          className="text-[#a8a29e] hover:text-white p-0.5 cursor-pointer"
                                        >
                                          {copiedDnsKey === "cname_value" ? <Check className="w-3 h-3 text-emerald-400 inline" /> : <Copy className="w-3 h-3 inline" />}
                                        </button>
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>

                              <div className="flex items-center justify-between text-[11px] pt-1">
                                <span className="text-[#71717a]">Point records to Studio Edge</span>
                                <button
                                  type="button"
                                  onClick={handleCopyAllDnsRecords}
                                  className="text-[#dfb180] hover:underline flex items-center gap-1 font-medium cursor-pointer"
                                >
                                  <Copy className="w-3 h-3" />
                                  <span>{copiedDnsKey === "all_records" ? "Copied!" : "Copy all records"}</span>
                                </button>
                              </div>
                            </div>
                          )}

                          <button
                            type="submit"
                            disabled={verifyingOwnershipLoading || !connectDomainName}
                            className="w-full py-2 rounded-lg bg-[#c89666] hover:bg-[#dfb180] disabled:opacity-50 text-[#09090b] font-bold text-xs transition flex items-center justify-center gap-1.5 cursor-pointer"
                          >
                            {verifyingOwnershipLoading ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <ShieldCheck className="w-3.5 h-3.5" />
                            )}
                            <span>Verify &amp; Link Domain</span>
                          </button>
                        </form>
                      </div>
                    </div>

                    {/* ── RIGHT SIDE: BUY ON GODADDY ── */}
                    <div className="space-y-4 min-w-0">
                      <div className="flex items-center justify-between pb-2 border-b border-[#222226]">
                        <div className="flex items-center gap-2">
                          <ShoppingCart className="w-4 h-4 text-[#c89666]" />
                          <span className="text-sm font-bold text-white">Buy Domain</span>
                        </div>
                        <span className="text-[11px] text-[#71717a]">
                          Target: <strong className="text-white">{selectedTargetDeployment?.project_name || "Select site"}</strong>
                        </span>
                      </div>

                      {/* Search */}
                      <div className="flex gap-2">
                        <div className="relative flex-1">
                          <Search className="w-3.5 h-3.5 text-[#71717a] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                          <input
                            type="text"
                            placeholder="Search name (e.g. mystudio.com)"
                            value={godaddySearchQuery}
                            onChange={(e) => setGodaddySearchQuery(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                handleSearchGoDaddy(godaddySearchQuery);
                              }
                            }}
                            className="w-full pl-8 pr-3 py-2 rounded-lg bg-[#09090b] border border-[#27272a] text-white text-xs font-mono outline-none focus:border-[#c89666]"
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() => handleSearchGoDaddy(godaddySearchQuery)}
                          disabled={godaddySearching || !godaddySearchQuery}
                          className="px-3.5 py-2 rounded-lg bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] text-xs font-bold shrink-0 disabled:opacity-50 transition cursor-pointer"
                        >
                          {godaddySearching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Search"}
                        </button>
                      </div>

                      {/* Results List */}
                      <div className="space-y-1.5 max-h-[320px] overflow-y-auto pr-1">
                        {godaddySearchResults.length === 0 ? (
                          <div className="py-8 text-center text-xs text-[#71717a] border border-dashed border-[#222226] rounded-lg">
                            Search a domain above to check GoDaddy registry.
                          </div>
                        ) : (
                          godaddySearchResults.map((sug, idx) => {
                            const domName = sug.domain || sug.name;
                            const isAvail = sug.available === true;
                            const priceVal = sug.price?.value ? (sug.price.value / 100).toFixed(2) : (sug.price || "10.99");
                            const targetDep = selectedTargetDeployment?.id || connectSelectedDeploymentId || (deploymentsData.length > 0 ? deploymentsData[0].id : "");

                            return (
                              <div
                                key={idx}
                                className="py-2.5 px-3 rounded-lg bg-[#121216] border border-[#222226] hover:border-[#33333a] flex items-center justify-between gap-2"
                              >
                                <div className="min-w-0">
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-mono text-xs font-bold text-white truncate">{domName}</span>
                                    {isAvail ? (
                                      <span className="text-[10px] text-emerald-400 font-semibold">Available</span>
                                    ) : (
                                      <span className="text-[10px] text-rose-400 font-semibold">Taken</span>
                                    )}
                                  </div>
                                  <span className="text-[11px] text-[#a8a29e]">${priceVal}/yr</span>
                                </div>
                                {isAvail ? (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      navigate(`/domains/buy?domain=${encodeURIComponent(domName)}&deployment_id=${targetDep}&price=${encodeURIComponent(priceVal)}&from=${encodeURIComponent("/dashboard?tab=my-websites")}`);
                                    }}
                                    className="px-3 py-1 rounded bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] text-xs font-bold transition cursor-pointer"
                                  >
                                    Buy
                                  </button>
                                ) : (
                                  <span className="text-[11px] text-[#52525b]">Unavailable</span>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>

                      <p className="text-[11px] text-[#71717a] pt-1">
                        Domains link automatically to your target site with instant SSL.
                      </p>
                    </div>
                  </div>

                  {/* ── BOTTOM: MAPPED DOMAINS ── */}
                  <div className="pt-4 border-t border-[#222226] space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Globe className="w-4 h-4 text-[#c89666]" />
                        <span className="text-sm font-bold text-white">Mapped Domains</span>
                        <span className="text-xs text-[#a8a29e]">({deploymentsData.filter(d => d.custom_domain).length})</span>
                      </div>
                    </div>

                    {deploymentsData.filter(d => d.custom_domain).length === 0 ? (
                      <div className="py-4 text-center text-xs text-[#71717a]">
                        No custom domains linked yet.
                      </div>
                    ) : (
                      <div className="overflow-x-auto rounded border border-[#222226]">
                        <table className="w-full text-left text-xs">
                          <thead>
                            <tr className="border-b border-[#222226] bg-[#121216] text-[11px] text-[#a8a29e]">
                              <th className="py-2 px-3 font-semibold">Domain</th>
                              <th className="py-2 px-3 font-semibold">Site</th>
                              <th className="py-2 px-3 font-semibold">SSL</th>
                              <th className="py-2 px-3 font-semibold">Auto-Renewal</th>
                              <th className="py-2 px-3 text-right font-semibold">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#222226]">
                            {deploymentsData.filter(d => d.custom_domain).map((deploy) => (
                              <tr key={deploy.id} className="hover:bg-[#16161b]">
                                <td className="py-2.5 px-3 font-mono font-bold text-[#dfb180]">
                                  <a
                                    href={deploy.live_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ color: "#dfb180" }}
                                    className="site-live-link hover:underline inline-flex items-center gap-1"
                                  >
                                    {deploy.custom_domain}
                                    <ExternalLink className="w-2.5 h-2.5 text-[#a8a29e]" />
                                  </a>
                                </td>
                                <td className="py-2.5 px-3 text-white truncate max-w-[150px]">{deploy.project_name}</td>
                                <td className="py-2.5 px-3">
                                  <span className="text-[10px] text-emerald-400 flex items-center gap-1">
                                    <CheckCircle2 className="w-3 h-3" /> Active
                                  </span>
                                </td>
                                <td className="py-2.5 px-3">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      const nextState = !deploy.auto_renew;
                                      toggleAutoRenewMutation.mutate({ domain: deploy.custom_domain, autoRenew: nextState });
                                    }}
                                    disabled={toggleAutoRenewMutation.isPending}
                                    className={`px-2 py-0.5 rounded text-[10px] font-bold inline-flex items-center gap-1 cursor-pointer transition border ${deploy.auto_renew
                                        ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/25"
                                        : "bg-[#1c1c24] border-[#383842] text-[#a8a29e] hover:text-white"
                                      }`}
                                    title={deploy.auto_renew ? "Auto-renewal authorized. Click to revoke authority." : "Click to authorize automatic annual renewal debit."}
                                  >
                                    {deploy.auto_renew ? (
                                      <>
                                        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                        <span>Auto: ON</span>
                                      </>
                                    ) : (
                                      <>
                                        <span className="w-1.5 h-1.5 rounded-full bg-[#71717a]" />
                                        <span>Auto: OFF</span>
                                      </>
                                    )}
                                  </button>
                                </td>
                                <td className="py-2.5 px-3 text-right">
                                  <div className="flex items-center justify-end gap-2">
                                    <button
                                      type="button"
                                      onClick={() => openDomainTransferModal(deploy.custom_domain)}
                                      className="text-[11px] text-[#dfb180] hover:underline cursor-pointer"
                                    >
                                      Transfer
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        if (confirm(`Unlink ${deploy.custom_domain}?`)) {
                                          unlinkDomainMutation.mutate(deploy.id);
                                        }
                                      }}
                                      className="text-[11px] text-rose-400 hover:underline cursor-pointer"
                                    >
                                      Unlink
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {/* === DEPLOYMENTS === */}
              {activeTab === "deployments" && (
                <div className="rounded-2xl border border-[#27272a] bg-[#0c0c0e] p-6 sm:p-8 space-y-6 shadow-2xl">
                  {/* Top Header */}
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-[#222226] pb-5">
                    <div>
                      <div className="flex items-center gap-2.5">
                        <h3 className="font-extrabold text-2xl text-white">Deployments</h3>
                        <span className="text-xs bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded-full font-bold border border-emerald-500/40 uppercase tracking-wider flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                          Studio Edge CDN
                        </span>
                      </div>
                      <p className="text-xs sm:text-sm text-[#a8a29e] mt-1.5">
                        Deploy and manage production static sites on high-speed Studio Edge CDN with automatic SSL.
                      </p>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <Link
                        to="/studio/deploy"
                        className="px-4 py-2.5 rounded-xl bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] font-black text-xs transition cursor-pointer shadow-md inline-flex items-center gap-1.5"
                        title="Open Cloud Deployer Studio"
                      >
                        <Plus className="w-4 h-4 stroke-[3]" />
                        <span>Deploy a Project</span>
                      </Link>
                    </div>
                  </div>

                  {deploymentsLoading && (!deploymentsData || deploymentsData.length === 0) ? (
                    <div className="text-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#dfb180]" />
                      <p className="text-xs text-[#a8a29e] mt-2 font-medium">Loading deployments...</p>
                    </div>
                  ) : deploymentsData.length === 0 ? (
                    <div className="text-center py-12 text-[#a8a29e] border border-dashed border-[#27272a] rounded-2xl bg-[#121217]">
                      <Zap className="w-10 h-10 text-[#c89666] mx-auto mb-3 opacity-70" />
                      <p className="text-base font-bold text-white">No active deployments</p>
                      <p className="text-xs text-[#a8a29e] mt-1 max-w-md mx-auto">
                        Connect a project template to start building and hosting live websites.
                      </p>
                      <div className="flex items-center justify-center gap-3 mt-4">
                        <button
                          type="button"
                          onClick={() => {
                            const available = [...sellerTemplatesList];
                            if (available.length > 0) {
                              setDeployTemplateId(available[0].id);
                              setDeployProjectName(available[0].title);
                            } else {
                              setDeployTemplateId("mock-project-id");
                              setDeployProjectName("Restaurant Demo Prototype");
                            }
                            setIsDeployModalOpen(true);
                          }}
                          className="px-4 py-2 rounded-xl bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] font-bold text-xs transition shadow-md cursor-pointer"
                        >
                          Create Project Deployment
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-5">
                      {/* Search Bar & Status Filters */}
                      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-xl bg-[#121217] border border-[#222228]">
                        <div className="relative flex-1">
                          <Search className="w-4 h-4 text-[#a8a29e] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                          <input
                            type="text"
                            placeholder="Search deployments by project name, site ID, domain..."
                            value={deploymentSearchQuery}
                            onChange={(e) => setDeploymentSearchQuery(e.target.value)}
                            className="w-full pl-9 pr-8 py-2 rounded-lg bg-[#09090b] border border-[#27272f] text-white text-xs outline-none focus:border-[#c89666] transition placeholder-[#71717a]"
                          />
                          {deploymentSearchQuery && (
                            <button
                              type="button"
                              onClick={() => setDeploymentSearchQuery("")}
                              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#71717a] hover:text-white p-0.5 text-xs font-bold cursor-pointer"
                              title="Clear search"
                            >
                              ✕
                            </button>
                          )}
                        </div>

                        {/* Filter Status Pills */}
                        <div className="flex items-center gap-1.5 shrink-0 overflow-x-auto pb-1 sm:pb-0">
                          {[
                            { id: "all", label: `All (${deploymentsData.length})` },
                            { id: "live", label: `Live (${deploymentsData.filter(d => d.status === "live" || d.status === "success").length})` },
                            { id: "building", label: "Building" },
                            { id: "suspended", label: "Suspended" },
                          ].map((tab) => (
                            <button
                              key={tab.id}
                              type="button"
                              onClick={() => setDeploymentStatusFilter(tab.id)}
                              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer border ${deploymentStatusFilter === tab.id
                                  ? "bg-[#c89666] text-[#09090b] font-bold border-[#c89666] shadow-xs"
                                  : "bg-[#181820] text-[#a8a29e] hover:text-white border-[#27272f]"
                                }`}
                            >
                              {tab.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      {filteredDeployments.length === 0 ? (
                        <div className="py-12 text-center text-xs text-[#a8a29e] border border-dashed border-[#27272a] rounded-xl bg-[#121217]">
                          <Search className="w-8 h-8 text-[#c89666] mx-auto mb-2 opacity-50" />
                          <p className="font-bold text-white text-sm">No matching deployments found</p>
                          <p className="text-[11px] text-[#71717a] mt-1">Try adjusting your search query or clear the filter.</p>
                          <button
                            type="button"
                            onClick={() => {
                              setDeploymentSearchQuery("");
                              setDeploymentStatusFilter("all");
                            }}
                            className="mt-3 px-3 py-1.5 rounded-lg bg-[#222228] hover:bg-[#2c2c34] text-[#dfb180] text-xs font-bold border border-[#383842] inline-flex items-center gap-1 cursor-pointer"
                          >
                            Clear Filters
                          </button>
                        </div>
                      ) : (
                        /* Responsive 4-Column Grid Template Structure */
                        <div className="deployments-cards-grid grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                          {filteredDeployments.map((deploy) => {
                            const isLive = deploy.status === "live" || deploy.status === "success";
                            const isBuilding = deploy.status === "building" || deploy.status === "queued" || deploy.status === "deploying";
                            const isSuspended = deploy.status === "suspended" || deploy.is_suspended;
                            const isFailed = deploy.status === "failed";
                            const deployDetailsUrl = `/deployments/${encodeURIComponent(deploy.id)}`;
                            const deployPageUrl = `/studio/deploy?deployment=${encodeURIComponent(deploy.id)}${deploy.template_id ? `&template=${encodeURIComponent(deploy.template_id)}` : ""}&name=${encodeURIComponent(deploy.project_name)}`;
                            const siteLiveUrl = deploy.live_url || (deploy.site_id ? `${BACKEND_BASE}/sites/${deploy.site_id}/` : "#");
                            const displayDomain = deploy.custom_domain || (deploy.subdomain ? `${deploy.subdomain}.site-studio.live` : "Studio Preview");

                            return (
                              <div
                                key={deploy.id}
                                className="deployment-card rounded-xl border border-[#2a2a35] bg-[#121217] hover:border-[#c89666]/60 transition-all p-4 shadow-lg flex flex-col justify-between group space-y-3.5"
                              >
                                {/* Card Top: Icon, Project Name, Status */}
                                <div className="space-y-3.5">
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex items-center gap-3 min-w-0">
                                      <div className="w-10 h-10 rounded-xl bg-[#c89666]/15 border border-[#c89666]/35 flex items-center justify-center shrink-0">
                                        {isBuilding ? (
                                          <Loader2 className="w-5 h-5 text-amber-400 animate-spin" />
                                        ) : isLive ? (
                                          <Rocket className="w-5 h-5 text-[#dfb180]" />
                                        ) : isSuspended ? (
                                          <Pause className="w-5 h-5 text-amber-400" />
                                        ) : (
                                          <AlertTriangle className="w-5 h-5 text-rose-400" />
                                        )}
                                      </div>
                                      <div className="min-w-0">
                                        <Link
                                          to={deployDetailsUrl}
                                          className="text-base font-extrabold text-white hover:text-[#dfb180] transition-colors truncate block"
                                          title={deploy.project_name}
                                        >
                                          {deploy.project_name}
                                        </Link>
                                        <span className="text-[11px] font-mono text-[#a8a29e] font-semibold">
                                          {deploy.site_id || `SITE-${deploy.id.slice(0, 6).toUpperCase()}`}
                                        </span>
                                      </div>
                                    </div>

                                    {/* Status Badge */}
                                    <span className={`px-2.5 py-1 rounded-full text-xs font-bold shrink-0 flex items-center gap-1.5 border ${isLive
                                        ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                                        : isBuilding
                                          ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                                          : isSuspended
                                            ? "bg-slate-700/40 text-slate-200 border-slate-600/40"
                                            : "bg-rose-500/20 text-rose-300 border-rose-500/40"
                                      }`}>
                                      {isBuilding && <Loader2 className="w-3 h-3 animate-spin" />}
                                      {isLive && <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />}
                                      <span>{isBuilding ? "Building" : isLive ? "● LIVE" : isSuspended ? "Suspended" : "Failed"}</span>
                                    </span>
                                  </div>

                                  {/* Domain & Live Preview Row */}
                                  <div className="p-2.5 rounded-lg bg-[#09090b] border border-[#27272f] flex items-center justify-between gap-2 text-xs">
                                    <div className="flex items-center gap-2 min-w-0">
                                      <Globe className="w-4 h-4 text-[#c89666] shrink-0" />
                                      <a
                                        href={siteLiveUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{ color: "#dfb180" }}
                                        className="site-live-link font-mono text-xs font-bold hover:underline truncate"
                                        title={displayDomain}
                                      >
                                        {displayDomain}
                                      </a>
                                    </div>
                                    <ExternalLink className="w-3.5 h-3.5 text-[#a8a29e] shrink-0" />
                                  </div>

                                  {/* Visible Metadata Chips (High Contrast) */}
                                  <div className="flex flex-wrap items-center gap-1.5 text-xs">
                                    <span className="inline-flex items-center gap-1 bg-[#1c1c24] text-[#dfb180] border border-[#c89666]/35 px-2 py-0.5 rounded font-mono font-bold text-[11px]">
                                      <Tag className="w-3 h-3 text-[#dfb180]" />
                                      {deploy.site_id || `SITE-${deploy.id.slice(0, 6).toUpperCase()}`}
                                    </span>
                                    <span className="inline-flex items-center gap-1 bg-[#1c1c24] text-white border border-[#33333f] px-2 py-0.5 rounded font-mono font-bold text-[11px]">
                                      {deploy.current_version || "v1.0"}
                                    </span>
                                    <span className="inline-flex items-center gap-1 bg-[#1c1c24] text-[#e4e4e7] border border-[#33333f] px-2 py-0.5 rounded text-[11px] font-semibold">
                                      <Server className="w-3 h-3 text-[#dfb180]" />
                                      {deploy.provider === "vercel" ? "Vercel Cloud" : "Studio Edge CDN"}
                                    </span>
                                    <span className="inline-flex items-center gap-1 bg-[#1c1c24] text-[#d4d4d8] border border-[#33333f] px-2 py-0.5 rounded text-[11px] font-medium">
                                      <Clock className="w-3 h-3 text-[#a8a29e]" />
                                      {new Date(deploy.updated_at || deploy.created_at).toLocaleDateString()}
                                    </span>
                                  </div>
                                </div>

                                {/* Card Bottom: 2x2 Action Buttons Grid */}
                                <div className="pt-3.5 border-t border-[#222228] grid grid-cols-2 gap-2 text-xs">
                                  {isLive ? (
                                    <a
                                      href={siteLiveUrl}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="px-2.5 py-2 rounded-lg bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] font-black text-xs flex items-center justify-center gap-1.5 transition shadow-xs cursor-pointer"
                                      title="Open live website in a new tab"
                                    >
                                      <ExternalLink className="w-3.5 h-3.5 stroke-[2.5]" />
                                      <span>Visit Site</span>
                                    </a>
                                  ) : (
                                    <div className="px-2.5 py-2 rounded-lg bg-[#16161c] text-[#71717a] text-xs font-bold flex items-center justify-center">
                                      Offline
                                    </div>
                                  )}

                                  <Link
                                    to={deployDetailsUrl}
                                    className="px-2.5 py-2 rounded-lg bg-[#1e1e26] hover:bg-[#282834] text-white border border-[#383846] font-bold text-xs flex items-center justify-center gap-1.5 transition cursor-pointer"
                                    title="View full health, metrics & details"
                                  >
                                    <Activity className="w-3.5 h-3.5 text-[#dfb180]" />
                                    <span>Details</span>
                                  </Link>

                                  <button
                                    type="button"
                                    onClick={() => {
                                      setSelectedDeployment(deploy);
                                      setActiveConsoleLogs(deploy.logs || "");
                                      setActiveConsoleStatus(deploy.status);
                                      setIsConsoleOpen(true);
                                    }}
                                    className="px-2.5 py-2 rounded-lg bg-[#1e1e26] hover:bg-[#282834] text-white border border-[#383846] font-bold text-xs flex items-center justify-center gap-1.5 transition cursor-pointer"
                                    title="Open live console logs"
                                  >
                                    <Terminal className="w-3.5 h-3.5 text-[#dfb180]" />
                                    <span>Logs</span>
                                  </button>

                                  <Link
                                    to={deployPageUrl}
                                    className="px-2.5 py-2 rounded-lg bg-[#1e1e26] hover:bg-[#282834] text-white border border-[#383846] font-bold text-xs flex items-center justify-center gap-1.5 transition cursor-pointer"
                                    title="Open in deploy studio"
                                  >
                                    <Rocket className="w-3.5 h-3.5 text-[#dfb180]" />
                                    <span>Deploy Page</span>
                                  </Link>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
              {/* === WISHLIST === */}
              {activeTab === "wishlist" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">My Wishlist</h3>
                    <p className="text-sm text-muted-foreground">Quickly purchase items saved in your wishlist.</p>
                  </div>
                  {wishlist.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">Your wishlist is empty.</div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {wishlist.map((item) => (
                        <div key={item.id} className="p-4 border border-border/50 rounded-xl space-y-3 bg-muted/10">
                          <div className="font-bold text-sm truncate">{item.title}</div>
                          <div className="flex justify-between items-center">
                            <span className="font-bold text-sm text-primary">{formatPrice(item.price)}</span>
                            <Link href={`/marketplace/${item.slug}`} className="px-3 py-1.5 bg-primary text-white rounded-lg text-xs font-semibold">View Details</Link>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* === BUYER FOLLOWING === */}
              {activeTab === "buyer-following" && (
                <div className="glass-premium p-6 sm:p-8 space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/20 pb-5">
                    <div>
                      <div className="flex items-center gap-2.5">
                        <h3 className="font-extrabold text-xl text-foreground">Following</h3>
                        {Array.isArray(following) && following.length > 0 && (
                          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30">
                            {following.length}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground font-medium">Creators and sellers you follow for template releases and updates.</p>
                    </div>
                  </div>
                  {followingLoading && (!following || following.length === 0) ? (
                    <div className="text-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#dfb180]" />
                      <p className="text-xs text-muted-foreground mt-2 font-medium">Loading sellers you follow...</p>
                    </div>
                  ) : !following || following.length === 0 ? (
                    <div className="mt-empty-card">
                      <div className="mt-empty-icon">
                        <Users className="w-7 h-7" />
                      </div>
                      <h4 className="mt-empty-title">Not Following Any Sellers Yet</h4>
                      <p className="mt-empty-desc">
                        When you follow creators from template pages, they will appear here so you can browse their latest releases.
                      </p>
                    </div>
                  ) : (
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      {following.map((seller) => {
                        const avatarSrc = resolveMediaUrl(seller.avatar_url);
                        const displayName = seller.full_name || seller.username || "Seller Profile";
                        const initial = (seller.full_name || seller.username || "S").charAt(0).toUpperCase();

                        return (
                          <div key={seller.id} className="follower-card">
                            <div className="flex items-center gap-3.5 min-w-0">
                              <div className="follower-avatar-wrap">
                                {avatarSrc ? (
                                  <img
                                    src={avatarSrc}
                                    alt=""
                                    className="follower-avatar-img"
                                    onError={(e) => {
                                      e.currentTarget.style.setProperty('display', 'none', 'important');
                                      const fb = e.currentTarget.parentElement?.querySelector('.follower-avatar-fallback');
                                      if (fb) fb.style.setProperty('display', 'flex', 'important');
                                    }}
                                  />
                                ) : null}
                                <span
                                  className="follower-avatar-fallback"
                                  style={{ display: avatarSrc ? "none" : "flex" }}
                                >
                                  {initial}
                                </span>
                              </div>
                              <div className="space-y-0.5 min-w-0">
                                <div className="font-extrabold text-sm text-foreground truncate">{displayName}</div>
                                <span className="text-xs text-muted-foreground font-medium truncate block">@{seller.username || "seller"}</span>
                              </div>
                            </div>

                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}


              {/* === BILLING & PAYMENT REPORT === */}
              {activeTab === "orders" && (
                <div className="space-y-6">
                  {/* Top Header Card */}
                  <div className="glass border border-border/40 rounded-2xl p-6 sm:p-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#c89666]/15 border border-[#c89666]/30 text-[#dfb180] text-xs font-bold mb-2">
                        <Receipt className="w-3.5 h-3.5" />
                        <span>Official Financial Ledger</span>
                      </div>
                      <h3 className="font-extrabold text-2xl text-foreground">Billing & Payment Report</h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        Consolidated statement of all template licenses, recurring edge hosting subscriptions, and Studio compute top-ups.
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => window.print()}
                        className="px-4 py-2.5 rounded-xl border border-border/50 bg-muted/40 hover:bg-muted/70 text-xs font-bold text-foreground inline-flex items-center gap-2 cursor-pointer transition-colors"
                      >
                        <FileText className="w-3.5 h-3.5 text-[#dfb180]" />
                        <span>Print Statement</span>
                      </button>

                      <a
                        href="/pricing"
                        className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-xs font-black text-[#09090b] inline-flex items-center gap-2 shadow-md transition-all text-decoration-none"
                      >
                        <Coins className="w-3.5 h-3.5" />
                        <span>Top Up Tokens</span>
                      </a>
                    </div>
                  </div>

                  {/* Subscription & Entitlements Management Card */}
                  <div className="glass border border-border/40 rounded-2xl p-6 space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <Crown className="w-5 h-5 text-[#dfb180]" />
                          <h4 className="font-bold text-lg text-foreground capitalize">
                            {userSubData?.plan ? `${userSubData.plan} Tier` : `${user?.subscription_tier || "Free"} Tier`}
                          </h4>
                          <span className={cn(
                            "px-2.5 py-0.5 rounded-full text-xs font-bold uppercase",
                            userSubData?.status === "active"
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                              : userSubData?.status === "canceled"
                                ? "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                                : "bg-muted text-muted-foreground border border-border"
                          )}>
                            {userSubData?.status || "Active"}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {userSubData?.cancel_at_period_end
                            ? `Scheduled to cancel on ${userSubData.current_period_end ? new Date(userSubData.current_period_end).toLocaleDateString() : "period end"}. You will retain full access until then.`
                            : userSubData?.current_period_end
                              ? `Renews on ${new Date(userSubData.current_period_end).toLocaleDateString()} via ${userSubData.billing_provider || "payment gateway"}.`
                              : "Free Starter Tier · Upgrade to unlock custom domains, included hosted sites, and continuous Auto-Heal."}
                        </p>
                      </div>

                      <div className="flex items-center gap-2">
                        {userSubData?.plan && userSubData.plan !== "free" ? (
                          userSubData.cancel_at_period_end ? (
                            <button
                              type="button"
                              onClick={() => reactivateSubscriptionMutation.mutate()}
                              disabled={reactivateSubscriptionMutation.isPending}
                              className="px-3.5 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-xl text-xs font-bold border border-emerald-500/30 transition-colors cursor-pointer"
                            >
                              {reactivateSubscriptionMutation.isPending ? "Reactivating..." : "Reactivate Subscription"}
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => {
                                if (confirm("Are you sure you want to cancel your subscription at the end of the current billing cycle?")) {
                                  cancelSubscriptionMutation.mutate();
                                }
                              }}
                              disabled={cancelSubscriptionMutation.isPending}
                              className="px-3.5 py-2 bg-muted/40 hover:bg-muted/70 text-muted-foreground hover:text-foreground rounded-xl text-xs font-semibold border border-border/50 transition-colors cursor-pointer"
                            >
                              {cancelSubscriptionMutation.isPending ? "Canceling..." : "Cancel at Period End"}
                            </button>
                          )
                        ) : null}

                        {(!userSubData?.plan || userSubData.plan === "free") ? (
                          <a
                            href="/subscribe?plan=pro"
                            className="px-4 py-2 bg-gradient-to-r from-[#c89666] to-[#b5804f] text-[#09090b] text-xs font-bold rounded-xl shadow transition-all text-decoration-none"
                          >
                            Upgrade to Pro ($19/mo)
                          </a>
                        ) : userSubData.plan === "pro" ? (
                          <a
                            href="/subscribe?plan=extreme"
                            className="px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 text-white text-xs font-bold rounded-xl shadow transition-all text-decoration-none"
                          >
                            Upgrade to Extreme ($50/mo)
                          </a>
                        ) : null}
                      </div>
                    </div>

                    {/* Entitlement Quotas Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-border/30">
                      <div className="p-3 bg-muted/20 rounded-xl">
                        <span className="text-[11px] text-muted-foreground uppercase font-semibold block">AI Generation Quota</span>
                        <div className="text-base font-bold text-foreground mt-0.5">
                          {userSubData?.available_credits ?? user?.ai_credits ?? 10} Credits
                        </div>
                        <span className="text-[10px] text-muted-foreground">
                          {userSubData?.entitlements?.ai_credits_monthly
                            ? `${userSubData.entitlements.ai_credits_monthly}/mo allowance`
                            : "1 free generation trial"}
                        </span>
                      </div>

                      <div className="p-3 bg-muted/20 rounded-xl">
                        <span className="text-[11px] text-muted-foreground uppercase font-semibold block">Included Hosted Sites</span>
                        <div className="text-base font-bold text-foreground mt-0.5">
                          {userSubData?.active_hosted_count ?? 0} / {userSubData?.entitlements?.included_hosted_sites ?? 0}
                        </div>
                        <span className="text-[10px] text-muted-foreground">Included at $0 hosting charge</span>
                      </div>

                      <div className="p-3 bg-muted/20 rounded-xl">
                        <span className="text-[11px] text-muted-foreground uppercase font-semibold block">Deployment Slots</span>
                        <div className="text-base font-bold text-foreground mt-0.5">
                          {userSubData?.active_deployments_count ?? 0} / {userSubData?.entitlements?.max_deployment_slots ?? 1}
                        </div>
                        <span className="text-[10px] text-muted-foreground">Active website versions</span>
                      </div>

                      <div className="p-3 bg-muted/20 rounded-xl">
                        <span className="text-[11px] text-muted-foreground uppercase font-semibold block">Auto-Heal Sites</span>
                        <div className="text-base font-bold text-foreground mt-0.5">
                          {userSubData?.auto_heal_sites_count ?? 0} / {userSubData?.entitlements?.auto_heal_sites ?? 0}
                        </div>
                        <span className="text-[10px] text-muted-foreground">
                          {userSubData?.entitlements?.max_auto_heal_repairs_per_month
                            ? `Max ${userSubData.entitlements.max_auto_heal_repairs_per_month} repairs/mo`
                            : "Disabled on Free tier"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Summary Metric Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="glass border border-border/40 rounded-xl p-5">
                      <div className="flex items-center justify-between text-muted-foreground mb-2">
                        <span className="text-xs font-semibold uppercase tracking-wider">Total Invested</span>
                        <CreditCard className="w-4 h-4 text-[#dfb180]" />
                      </div>
                      <div className="text-2xl font-black text-foreground">
                        {formatPrice(billingReport?.summary?.total_spent_usd ?? 0)}
                      </div>
                      <span className="text-[11px] text-muted-foreground">Lifetime across all orders</span>
                    </div>

                    <div className="glass border border-border/40 rounded-xl p-5">
                      <div className="flex items-center justify-between text-muted-foreground mb-2">
                        <span className="text-xs font-semibold uppercase tracking-wider">Hosting Subscriptions</span>
                        <Globe className="w-4 h-4 text-cyan-400" />
                      </div>
                      <div className="text-2xl font-black text-foreground">
                        {billingReport?.summary?.active_hosting_subscriptions ?? 0}
                      </div>
                      <span className="text-[11px] text-muted-foreground">
                        {billingReport?.summary?.active_hosting_subscriptions ? `${billingReport.summary.monthly_recurring_spend_usd}/mo active` : "0 sites currently hosted"}
                      </span>
                    </div>

                    <div className="glass border border-border/40 rounded-xl p-5">
                      <div className="flex items-center justify-between text-muted-foreground mb-2">
                        <span className="text-xs font-semibold uppercase tracking-wider">Available Compute Tokens</span>
                        <Coins className="w-4 h-4 text-emerald-400" />
                      </div>
                      <div className="text-2xl font-black text-emerald-400">
                        {billingReport?.summary?.current_ai_credits ?? user?.ai_credits ?? 10}
                      </div>
                      <span className="text-[11px] text-emerald-400/80">Active compute quota</span>
                    </div>

                    <div className="glass border border-border/40 rounded-xl p-5">
                      <div className="flex items-center justify-between text-muted-foreground mb-2">
                        <span className="text-xs font-semibold uppercase tracking-wider">Completed Transactions</span>
                        <ShieldCheck className="w-4 h-4 text-[#dfb180]" />
                      </div>
                      <div className="text-2xl font-black text-foreground">
                        {billingReport?.summary?.completed_orders_count ?? orders.length}
                      </div>
                      <span className="text-[11px] text-muted-foreground">256-bit encrypted ledger</span>
                    </div>
                  </div>

                  {/* Active Subscriptions Box (if any) */}
                  {billingReport?.subscriptions?.length > 0 && (
                    <div className="glass border border-border/40 rounded-2xl p-6 space-y-4">
                      <div className="flex items-center gap-2">
                        <Globe className="w-4 h-4 text-cyan-400" />
                        <h4 className="font-bold text-base text-foreground">Active Website Hosting Subscriptions</h4>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                          <thead>
                            <tr className="border-b border-border/40 text-muted-foreground uppercase">
                              <th className="pb-3">Website Title</th>
                              <th className="pb-3">Domain / URL</th>
                              <th className="pb-3">Rate</th>
                              <th className="pb-3">Billing Cycle</th>
                              <th className="pb-3">Status</th>
                              <th className="pb-3 text-right">Details</th>
                            </tr>
                          </thead>
                          <tbody>
                            {billingReport.subscriptions.map((sub) => (
                              <tr key={sub.id} className="border-b border-border/20 hover:bg-muted/10">
                                <td className="py-3 font-semibold text-foreground">{sub.site_title}</td>
                                <td className="py-3 font-mono text-[#dfb180]">
                                  {sub.custom_domain || (sub.subdomain ? `${sub.subdomain}.aisitestudio.com` : "Edge Node")}
                                </td>
                                <td className="py-3 font-bold">${sub.monthly_price}.00 / mo</td>
                                <td className="py-3 text-muted-foreground">
                                  {sub.current_period_end ? `Renews on ${new Date(sub.current_period_end).toLocaleDateString()}` : "Monthly Recurring"}
                                </td>
                                <td className="py-3">
                                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                    {sub.status}
                                  </span>
                                </td>
                                <td className="py-3 text-right">
                                  <a
                                    href={`/dashboard/deployments/${sub.deployment_id}`}
                                    className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-muted/50 hover:bg-muted text-foreground border border-border/40 inline-flex items-center gap-1 text-decoration-none"
                                  >
                                    <span>Deployment</span>
                                    <ExternalLink className="w-3 h-3" />
                                  </a>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Complete Invoices & Orders Ledger */}
                  <div className="glass border border-border/40 rounded-2xl p-6 sm:p-8 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-[#dfb180]" />
                        <h4 className="font-bold text-base text-foreground">Transaction Invoices & Receipts</h4>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {(billingReport?.orders || orders).length} Total Transactions
                      </span>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-border/50 text-muted-foreground uppercase">
                            <th className="pb-3">Invoice / Order #</th>
                            <th className="pb-3">Date</th>
                            <th className="pb-3">Purchased Item / Service</th>
                            <th className="pb-3">Payment Method</th>
                            <th className="pb-3">Amount</th>
                            <th className="pb-3">Status</th>
                            <th className="pb-3 text-right">Official Receipt</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(billingReport?.orders || orders).length === 0 ? (
                            <tr>
                              <td colSpan={7} className="py-8 text-center text-muted-foreground">
                                No payment records or invoices found yet.
                              </td>
                            </tr>
                          ) : (
                            (billingReport?.orders || orders).map((o) => {
                              const receiptHref = o.receipt_url || `/dashboard/receipt/${o.id}`;
                              const isTokenPack = o.is_token_purchase || o.notes?.includes("AI Compute") || o.notes?.includes("Tokens");
                              return (
                                <tr key={o.id} className="border-b border-border/20 hover:bg-muted/10 transition-colors">
                                  <td className="py-3 font-mono font-bold text-foreground">
                                    {o.order_number}
                                  </td>
                                  <td className="py-3 text-muted-foreground">
                                    {o.created_at ? new Date(o.created_at).toLocaleDateString() : "Recent"}
                                  </td>
                                  <td className="py-3">
                                    <div className="flex items-center gap-1.5">
                                      {isTokenPack ? (
                                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30 inline-flex items-center gap-1">
                                          <Coins className="w-2.5 h-2.5" /> Compute Tokens
                                        </span>
                                      ) : (
                                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/15 text-blue-300 border border-blue-500/30">
                                          Template
                                        </span>
                                      )}
                                      <span className="font-semibold text-foreground truncate max-w-[220px]">
                                        {o.items_summary || o.notes || "Commercial License"}
                                      </span>
                                    </div>
                                  </td>
                                  <td className="py-3">
                                    <span className="font-mono uppercase text-[11px] text-muted-foreground">
                                      {o.gateway || "Stripe"}
                                    </span>
                                  </td>
                                  <td className="py-3 font-mono font-bold text-foreground">
                                    {formatPrice(o.total)}
                                  </td>
                                  <td className="py-3">
                                    <span className={cn(
                                      "px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase",
                                      (o.status === "completed" || o.status === "COMPLETED")
                                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                        : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                                    )}>
                                      {o.status}
                                    </span>
                                  </td>
                                  <td className="py-3 text-right">
                                    <div className="flex items-center justify-end gap-1.5">
                                      <Link
                                        to={`/dashboard/receipt/${o.id}`}
                                        className="px-3 py-1.5 rounded-xl text-[11px] font-bold bg-[#c89666]/15 hover:bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30 inline-flex items-center gap-1.5 transition-all text-decoration-none shadow-sm cursor-pointer"
                                        title="View official HTML tax invoice details"
                                      >
                                        <FileText className="w-3 h-3" />
                                        <span>Tax Invoice</span>
                                      </Link>
                                      <a
                                        href={`/dashboard/receipt/${o.id}?download=pdf`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="px-2.5 py-1.5 rounded-xl text-[11px] font-bold bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 inline-flex items-center gap-1 transition-all text-decoration-none shadow-sm cursor-pointer"
                                        title="Download tax invoice as PDF"
                                      >
                                        <Download className="w-3 h-3 text-[#dfb180]" />
                                        <span>PDF</span>
                                      </a>
                                    </div>
                                  </td>
                                </tr>
                              );
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* === REVIEWS === */}
              {activeTab === "reviews" && (
                <div className="glass-premium p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Reviews & Feedback</h3>
                    <p className="text-sm text-muted-foreground">Rate templates you purchased and manage your reviews.</p>
                  </div>

                  {buyerReviewsLoading ? (
                    <div className="text-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary" />
                    </div>
                  ) : buyerReviewsList.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground border border-dashed border-border/40 rounded-xl bg-card/5">
                      <Star className="w-8 h-8 text-primary mx-auto mb-3 opacity-60 animate-pulse" />
                      <p className="text-sm font-semibold text-foreground">No reviews written yet</p>
                      <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto leading-relaxed">
                        You haven't written any reviews yet. Leave reviews for your purchased templates from the "My Templates" tab to build your buyer rating.
                      </p>
                      <button
                        onClick={() => setActiveTab("buyer-templates")}
                        className="mt-4 px-4 py-2 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/95 transition-colors border-none cursor-pointer"
                      >
                        View My Templates
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {buyerReviewsList.map((review) => (
                        <div key={review.id} className="db-review-card">
                          <div className="flex justify-between items-start gap-4">
                            <div className="flex items-center gap-3">
                              {review.template?.thumbnail_url && (
                                <img
                                  src={review.template.thumbnail_url}
                                  alt=""
                                  className="w-12 h-12 rounded-lg object-cover border border-border/40 shrink-0 bg-muted"
                                />
                              )}
                              <div>
                                <h4 className="font-bold text-sm text-foreground">
                                  {review.template?.title || "Template Package"}
                                </h4>
                                <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                                  <div className="flex">
                                    {[1, 2, 3, 4, 5].map((s) => (
                                      <Star
                                        key={s}
                                        className={`w-3.5 h-3.5 ${s <= review.rating ? "fill-yellow-400 text-yellow-400" : "text-slate-600"
                                          }`}
                                      />
                                    ))}
                                  </div>
                                  <span className="text-[10px] text-muted-foreground">
                                    {new Date(review.created_at).toLocaleDateString()}
                                  </span>
                                  {review.is_verified_purchase && (
                                    <span className="text-[9px] bg-green-500/10 text-green-500 border border-green-500/20 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider scale-90">
                                      Verified
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <button
                              onClick={() => {
                                if (confirm("Are you sure you want to delete this review?")) {
                                  deleteReviewMutation.mutate(review.id);
                                }
                              }}
                              className="p-1.5 text-muted-foreground hover:text-red-400 transition-colors border border-transparent bg-transparent cursor-pointer rounded-lg hover:bg-red-500/10"
                              title="Delete Review"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>

                          <div className="db-review-divider">
                            <h5 className="font-bold text-xs text-foreground">{review.title}</h5>
                            <p className="text-xs text-muted-foreground leading-relaxed">{review.body}</p>
                          </div>

                          {review.admin_reply && (
                            <div className="p-3 bg-primary/5 border-l-2 border-primary rounded-r-lg space-y-1 mt-2">
                              <span className="text-[10px] font-bold text-primary uppercase">Seller Reply:</span>
                              <p className="text-xs text-slate-300 italic">{review.admin_reply}</p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}


              {/* === CREATOR / SELLER DASHBOARD HOME === */}
              {activeTab === "seller-home" && (
                <div className="sd-container">
                  {/* Summary Cards */}
                  <div className="sd-grid-stats">
                    {[
                      {
                        label: "Templates Published",
                        value: (stats?.uploaded_templates ?? sellerTemplatesList.length).toLocaleString(),
                        sub: "Active in catalog",
                        icon: Folder,
                        iconBg: "#eef2ff",
                        iconColor: "#b5804f",
                      },
                      {
                        label: "Total Sales",
                        value: sellerTotalSalesCount.toLocaleString(),
                        sub: sellerTotalSalesCount === 1 ? "1 order completed" : `${sellerTotalSalesCount} orders completed`,
                        icon: ShoppingBag,
                        iconBg: "#ecfdf5",
                        iconColor: "#059669",
                      },
                      {
                        label: "Total Revenue",
                        value: formatPrice(earningsSummary?.total_earned || 0),
                        sub: `Available: ${formatPrice(earningsSummary?.available_balance || 0)}`,
                        icon: Coins,
                        iconBg: "#eff6ff",
                        iconColor: "#2563eb",
                      },
                      {
                        label: "Customer Reviews",
                        value: sellerReviewsList.length.toLocaleString(),
                        sub: sellerReviewsList.length === 1 ? "1 verified review" : `${sellerReviewsList.length} verified reviews`,
                        icon: Star,
                        iconBg: "#fef3c7",
                        iconColor: "#d97706",
                      },
                      {
                        label: "Average Rating",
                        value: sellerActualAvgRating ? `${sellerActualAvgRating} ★` : "0.0 ★",
                        sub: sellerActualAvgRating ? "Based on buyer reviews" : "No buyer ratings yet",
                        icon: Sparkles,
                        iconBg: "#f5f3ff",
                        iconColor: "#c89666",
                      },
                      {
                        label: "Unique Viewers",
                        value: sellerTotalViews.toLocaleString(),
                        sub: "Distinct accounts opened",
                        icon: Users,
                        iconBg: "#ecfeff",
                        iconColor: "#0891b2",
                      },
                      {
                        label: "Followers",
                        value: followers.length.toLocaleString(),
                        sub: "Store subscribers",
                        icon: Users,
                        iconBg: "#fff1f2",
                        iconColor: "#e11d48",
                      },
                      {
                        label: "Conversion Rate",
                        value: sellerConversionRate,
                        sub: "Sales per view ratio",
                        icon: TrendingUp,
                        iconBg: "#ecfdf5",
                        iconColor: "#059669",
                      },
                    ].map(({ label, value, sub, icon: Icon, iconBg, iconColor }) => (
                      <div key={label} className="sd-stat-card">
                        <div className="sd-stat-header">
                          <span className="sd-stat-label">{label}</span>
                          <div className="sd-stat-icon" style={{ backgroundColor: iconBg, color: iconColor }}>
                            <Icon className="w-4 h-4" />
                          </div>
                        </div>
                        <div>
                          <div className="sd-stat-value">{value}</div>
                          <div className="sd-stat-sub">{sub}</div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Graphs & Live Overview */}
                  <div className="sd-graph-grid">
                    {/* Sales Log Card */}
                    <div className="sd-card">
                      <div className="sd-card-title">
                        <span>Recent Sales & Orders</span>
                        <span className="text-xs text-slate-500 font-semibold">Live Transactions</span>
                      </div>

                      {(earningsSummary?.sales || []).length > 0 ? (
                        <div className="space-y-2">
                          {(earningsSummary.sales || []).slice(0, 5).map((sale) => (
                            <div key={sale.id || sale.created_at} className="flex items-center justify-between p-3 rounded-xl bg-slate-800/60 border border-slate-700/50 text-xs">
                              <div>
                                <p className="font-extrabold text-foreground">{sale.template_title || "Website Template"}</p>
                                <p className="text-[11px] text-muted-foreground font-medium">Buyer: {sale.buyer_name || "Verified Customer"}</p>
                              </div>
                              <span className="font-black text-emerald-400 font-mono text-sm">+{formatPrice(sale.price || 0)}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="sd-empty-box">
                          <ShoppingBag className="w-8 h-8 text-muted-foreground/60" />
                          <p className="text-xs font-bold text-foreground">No sales recorded yet</p>
                          <p className="text-[11px] text-muted-foreground font-medium max-w-xs">
                            Once buyers purchase your templates on the marketplace, your live transaction log will automatically populate here.
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Revenue & Payouts Breakdown */}
                    <div className="sd-card">
                      <div className="sd-card-title">
                        <span>Revenue & Payout Overview</span>
                        <button
                          type="button"
                          onClick={() => setActiveTab("seller-earnings")}
                          className="text-xs text-[#dfb180] hover:text-[#dfb180] font-extrabold bg-transparent border-none cursor-pointer"
                        >
                          Manage Payouts →
                        </button>
                      </div>

                      <div className="space-y-4">
                        <div className="p-4 rounded-xl bg-[#c89666]/15 border border-[#c89666]/30 flex items-center justify-between">
                          <div>
                            <span className="text-[11px] font-extrabold text-[#dfb180] uppercase tracking-wider">Gross Platform Earnings</span>
                            <div className="text-2xl font-black text-foreground font-mono mt-0.5">
                              {formatPrice(earningsSummary?.total_earned || 0)}
                            </div>
                          </div>
                          <Coins className="w-8 h-8 text-[#dfb180]" />
                        </div>

                        <div className="grid grid-cols-3 gap-2 text-center">
                          <div className="p-2.5 rounded-xl bg-slate-800/60 border border-slate-700/50">
                            <span className="text-[10px] text-muted-foreground font-bold block">Available</span>
                            <span className="text-xs font-black text-emerald-400 font-mono mt-0.5 block">
                              {formatPrice(earningsSummary?.available_balance || 0)}
                            </span>
                          </div>
                          <div className="p-2.5 rounded-xl bg-slate-800/60 border border-slate-700/50">
                            <span className="text-[10px] text-muted-foreground font-bold block">Pending</span>
                            <span className="text-xs font-black text-amber-400 font-mono mt-0.5 block">
                              {formatPrice(earningsSummary?.pending_withdrawal || 0)}
                            </span>
                          </div>
                          <div className="p-2.5 rounded-xl bg-slate-800/60 border border-slate-700/50">
                            <span className="text-[10px] text-muted-foreground font-bold block">Withdrawn</span>
                            <span className="text-xs font-black text-slate-300 font-mono mt-0.5 block">
                              {formatPrice(earningsSummary?.withdrawn_amount || 0)}
                            </span>
                          </div>
                        </div>

                        <p className="text-[11px] text-muted-foreground font-medium leading-relaxed">
                          Platform revenue is calculated in real-time based on completed orders. You can request payouts anytime directly from your payouts portal.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* === SELLER MY TEMPLATES === */}
              {activeTab === "seller-templates" && renderMyTemplatesSection()}

              {/* === SELLER UPLOAD TEMPLATE === */}
              {activeTab === "seller-upload" && (
                <div className="glass-premium p-6 sm:p-8 space-y-6">
                  <div className="flex items-center justify-between pb-1">
                    <div>
                      <h3 className="font-extrabold text-xl text-foreground">Upload Website Template</h3>
                      <p className="text-xs text-muted-foreground font-medium">Submit your ZIP archive, HTML document, or Git repository to register on the platform catalog.</p>
                    </div>
                  </div>

                  {/* Reseller Privilege Status Banner */}
                  {["extreme", "agency", "enterprise"].includes((user?.subscription_tier || "").toLowerCase()) || user?.role === "seller" || user?.role === "admin" ? (
                    <div className="flex items-center gap-3 p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs">
                      <Sparkles className="w-4 h-4 shrink-0 text-emerald-400" />
                      <div className="flex-1">
                        <strong className="font-bold">⚡ Extreme Plan Reselling Privilege Active:</strong>
                        <span> You can upload, showcase, and resell unlimited templates on our global marketplace. Standard platform fee applies upon purchase.</span>
                      </div>
                      <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shrink-0">
                        Reseller Active
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between gap-3 p-3.5 rounded-xl bg-[#c89666]/15 border border-[#c89666]/30 text-[#dfb180] text-xs">
                      <div className="flex items-center gap-2.5">
                        <ShieldCheck className="w-4 h-4 shrink-0 text-[#dfb180]" />
                        <div>
                          <strong className="font-bold">Template Reselling Marketplace Privilege:</strong>
                          <span> The <strong>Extreme Plan</strong> unlocks template reselling on our marketplace with automated payouts and standard platform fees.</span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => navigate("/pricing")}
                        className="text-[11px] font-bold px-3 py-1 rounded-lg bg-[#c89666]/15 hover:bg-[#c89666]/15 text-white shrink-0 transition-colors cursor-pointer"
                      >
                        Upgrade to Extreme
                      </button>
                    </div>
                  )}

                  <>
                    {/* Multi-step Header */}
                    <div className="uw-step-nav">
                      {[
                        { step: 1, label: "Upload Source" },
                        { step: 2, label: "Code & Architecture Audit" },
                        { step: 3, label: "Review & Publish" },
                      ].map((st) => {
                        const isCurrent = wizardStep === st.step;
                        const isCompleted = wizardStep > st.step;
                        return (
                          <div key={st.step} className="uw-step-item">
                            <span className={cn(
                              "uw-step-badge",
                              isCurrent
                                ? "uw-step-badge-active"
                                : isCompleted
                                  ? "uw-step-badge-done"
                                  : "uw-step-badge-pending"
                            )}>
                              {isCompleted ? "✓" : st.step}
                            </span>
                            <span className={cn(
                              isCurrent ? "uw-step-text-active" : isCompleted ? "uw-step-text-done" : "uw-step-text-pending"
                            )}>
                              {st.label}
                            </span>
                            {st.step < 3 && <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
                          </div>
                        );
                      })}
                    </div>

                    <form onSubmit={handleUpload} className="space-y-6">
                      {/* STEP 1: UPLOAD PROJECT */}
                      {wizardStep === 1 && (
                        <div className="space-y-4 animate-in fade-in duration-200">
                          {/* Tab Switcher */}
                          <div className="uw-tab-switcher">
                            <button
                              type="button"
                              onClick={() => { setUploadType("zip"); setStoredZipUrl(""); }}
                              className={cn(
                                "uw-tab-btn",
                                uploadType === "zip" ? "uw-tab-btn-active" : "uw-tab-btn-inactive"
                              )}
                            >
                              ZIP File / HTML
                            </button>
                            <button
                              type="button"
                              onClick={() => { setUploadType("git"); setZipFile(null); }}
                              className={cn(
                                "uw-tab-btn",
                                uploadType === "git" ? "uw-tab-btn-active" : "uw-tab-btn-inactive"
                              )}
                            >
                              Git Repository
                            </button>
                          </div>

                          {uploadType === "zip" ? (
                            <div
                              className="db-upload-dropzone"
                              onDragOver={(e) => e.preventDefault()}
                              onDrop={(e) => {
                                e.preventDefault();
                                const file = e.dataTransfer.files[0];
                                if (file && (file.name.endsWith(".zip") || file.name.endsWith(".html") || file.name.endsWith(".htm"))) {
                                  handleZipAnalysis(file);
                                } else {
                                  alert("Please upload a valid ZIP archive (.zip) or HTML document (.html, .htm).");
                                }
                              }}
                            >
                              <div className="db-upload-dropzone-inner">
                                <div className="db-upload-icon-circle">
                                  <FileUp className="w-8 h-8 text-[#dfb180]" />
                                </div>
                                <h4 className="font-extrabold text-lg text-white mb-1">
                                  Upload Website Template or HTML
                                </h4>
                                <p className="text-xs mb-4 font-medium text-slate-400">
                                  Drag & drop ZIP archive (.zip), standalone HTML document (.html, .htm), or click to browse files
                                </p>

                                <div className="flex flex-wrap items-center justify-center gap-2 mb-5">
                                  <span className="uw-pill-indigo">
                                    <Sparkles className="w-3.5 h-3.5 text-[#dfb180]" /> Auto-Detects Version & Framework
                                  </span>
                                  <span className="uw-pill-emerald">
                                    <Code className="w-3.5 h-3.5 text-emerald-400" /> Supports Pure HTML / Static Sites
                                  </span>
                                </div>

                                <input
                                  type="file"
                                  accept=".zip,.html,.htm"
                                  id="zip-uploader"
                                  className="hidden"
                                  onChange={(e) => {
                                    const file = e.target.files[0];
                                    if (file) handleZipAnalysis(file);
                                  }}
                                />
                                <label htmlFor="zip-uploader" className="uw-browse-btn">
                                  <FileUp className="w-4 h-4" /> Browse Files from Computer
                                </label>
                              </div>

                              <div className="db-upload-tech-grid">
                                <div className="db-upload-tech-title">Supported Frameworks & Standards</div>
                                <div className="db-upload-tech-badges">
                                  {["HTML5", "Tailwind CSS", "JavaScript / TS", "React", "Next.js", "Vue", "Nuxt", "Astro", "Angular", "Svelte"].map(tech => (
                                    <span key={tech} className="tech-chip">✓ {tech}</span>
                                  ))}
                                </div>
                              </div>
                            </div>
                          ) : (
                            /* ── GIT REPOSITORY TAB ─────────────────────────── */
                            <div className="space-y-5">

                              {/* STATE A: GitHub NOT connected — one-click OAuth */}
                              {!user?.has_github_token && (
                                <div className="uw-github-card">
                                  <div className="relative">
                                    <div className="uw-github-logo-box">
                                      <svg className="w-10 h-10" viewBox="0 0 24 24" fill="#ffffff">
                                        <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
                                      </svg>
                                    </div>
                                    <div className="absolute -inset-1 rounded-2xl border-2 border-[#c89666]/30 animate-pulse" />
                                  </div>

                                  <div className="space-y-1.5 max-w-sm">
                                    <h4 className="uw-github-title">Connect GitHub Account</h4>
                                    <p className="uw-github-desc">
                                      Authorize Site Studio on GitHub to seamlessly import and audit your repositories with automated continuous updates.
                                    </p>
                                  </div>

                                  <div className="flex flex-col items-center gap-3 w-full max-w-xs">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        window.location.href = `${API_BASE}/auth/github/login?token=${authToken}&redirect=/dashboard?tab=seller-upload`;
                                      }}
                                      className="uw-github-btn"
                                    >
                                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="#ffffff">
                                        <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
                                      </svg>
                                      Continue with GitHub
                                    </button>

                                    <div className="flex items-center gap-3">
                                      <span className="uw-trust-badge"><ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Secure OAuth 2.0</span>
                                      <span style={{ color: "#94a3b8" }}>·</span>
                                      <span className="uw-trust-badge"><Key className="w-3.5 h-3.5 text-[#dfb180]" /> No passwords stored</span>
                                      <span style={{ color: "#94a3b8" }}>·</span>
                                      <span className="uw-trust-badge"><CheckCircle className="w-3.5 h-3.5 text-blue-600" /> One-time setup</span>
                                    </div>
                                  </div>
                                </div>
                              )}

                              {/* STATE B: GitHub connected — repo browser */}
                              {user?.has_github_token && (
                                <div className="space-y-4">
                                  {/* Header row */}
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                      <div className="w-7 h-7 rounded-lg bg-[#0f172a] flex items-center justify-center">
                                        <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="#ffffff"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" /></svg>
                                      </div>
                                      <div>
                                        <p className="text-sm font-extrabold text-white">Your Repositories</p>
                                        <p className="text-[11px] font-medium text-slate-400">{fetchedRepos.length} repos found · Click any to import</p>
                                      </div>
                                    </div>
                                    <button
                                      type="button"
                                      onClick={() => { setFetchedRepos([]); fetchGithubRepos(); }}
                                      disabled={fetchingRepos}
                                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 text-xs font-bold text-slate-200 hover:text-white hover:border-[#c89666]/30 transition-all cursor-pointer shadow-2xs"
                                    >
                                      <Loader2 className={cn("w-3.5 h-3.5", fetchingRepos && "animate-spin")} />
                                      Refresh Repos
                                    </button>
                                  </div>

                                  {/* STATE B-loading: skeletons */}
                                  {fetchingRepos && (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                      {[1, 2, 3, 4].map(i => (
                                        <div key={i} className="p-4 rounded-xl border border-white/10 bg-slate-900/40 space-y-2 animate-pulse">
                                          <div className="h-3.5 bg-slate-800 rounded w-2/3" />
                                          <div className="h-2.5 bg-slate-800 rounded w-full" />
                                          <div className="h-2.5 bg-slate-800 rounded w-1/2" />
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  {/* STATE B-loaded: repo cards */}
                                  {!fetchingRepos && fetchedRepos.length > 0 && (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-80 overflow-y-auto pr-1">
                                      {fetchedRepos.map((repo) => (
                                        <div
                                          key={repo.id || repo.clone_url}
                                          className="uw-repo-card"
                                          onClick={() => { setGitUrl(repo.clone_url); handleGitAnalysis(repo.clone_url); }}
                                        >
                                          {/* Repo header */}
                                          <div className="flex items-start justify-between gap-2">
                                            <div className="flex items-center gap-1.5 min-w-0">
                                              <Folder className="w-4 h-4 shrink-0 text-[#dfb180]" />
                                              <span className="uw-repo-name truncate">{repo.name}</span>
                                            </div>
                                            <span className={repo.private ? "uw-repo-badge-private" : "uw-repo-badge-public"}>
                                              {repo.private ? "Private" : "Public"}
                                            </span>
                                          </div>

                                          {/* Description */}
                                          <p className="uw-repo-desc line-clamp-2 leading-relaxed">
                                            {repo.description || "No description provided"}
                                          </p>

                                          {/* Meta chips */}
                                          <div className="flex items-center gap-2 flex-wrap pt-1">
                                            {repo.language && (
                                              <span className="uw-pill-indigo" style={{ padding: "0.2rem 0.6rem", fontSize: "0.6875rem" }}>
                                                <span className="w-1.5 h-1.5 rounded-full inline-block bg-[#c89666]/15" />
                                                {repo.language}
                                              </span>
                                            )}
                                            {repo.stargazers_count > 0 && (
                                              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-slate-300">
                                                <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                                                {repo.stargazers_count}
                                              </span>
                                            )}
                                            {repo.updated_at && (
                                              <span className="text-[10px] font-medium ml-auto text-slate-400">
                                                {new Date(repo.updated_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                                              </span>
                                            )}
                                          </div>

                                          {/* Import button */}
                                          <button
                                            type="button"
                                            onClick={(e) => { e.stopPropagation(); setGitUrl(repo.clone_url); handleGitAnalysis(repo.clone_url); }}
                                            className="uw-repo-btn"
                                          >
                                            <Zap className="w-3.5 h-3.5" /> Import & Analyze
                                          </button>
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  {/* Empty state */}
                                  {!fetchingRepos && fetchedRepos.length === 0 && (
                                    <div className="text-center py-8 text-xs font-semibold text-slate-400">
                                      No repositories found. Click Refresh or check your token permissions.
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* Manual URL fallback — always visible */}
                              <div className="space-y-2 p-4 bg-slate-900/60 border border-white/10 rounded-xl">
                                <label className="uw-label block" style={{ marginBottom: "0.5rem" }}>
                                  {user?.has_github_token ? "Or paste a public / GitLab / Bitbucket URL:" : "Or paste any public Git URL:"}
                                </label>
                                <div className="flex gap-2">
                                  <input
                                    type="text"
                                    placeholder="https://github.com/username/repository-name.git"
                                    value={gitUrl}
                                    onChange={(e) => setGitUrl(e.target.value)}
                                    className="uw-input flex-1"
                                  />
                                  <button
                                    type="button"
                                    onClick={() => handleGitAnalysis()}
                                    disabled={!gitUrl}
                                    className="uw-btn-publish shrink-0"
                                    style={{ padding: "0.625rem 1.25rem" }}
                                  >
                                    <Zap className="w-4 h-4" /> Analyze
                                  </button>
                                </div>
                              </div>
                            </div>
                          )}

                          <div className="uw-specs-box">
                            <span className="uw-specs-title">Supported Upload Specifications:</span>
                            <div className="uw-specs-list">
                              <span>• ZIP Archive (.zip)</span>
                              <span>• Standalone HTML (.html, .htm)</span>
                              <span>• GitHub Repository</span>
                              <span>• Public Git URL</span>
                            </div>
                            <span className="text-[11px] font-medium mt-0.5" style={{ color: "#64748b" }}>
                              Maximum archive size: 2 GB · Auto-extracts & scans components in under 5 seconds
                            </span>
                          </div>

                        </div>
                      )}

                      {/* STEP 2: PROJECT AUDIT LOADING / RESULTS */}
                      {wizardStep === 2 && (
                        <div className="space-y-6 animate-in fade-in duration-200">
                          {analysisLoading ? (
                            <div className="db-analysis-loading-shell">
                              <div className="db-scanner-icon-container">
                                <Sparkles className="w-10 h-10 text-[#dfb180] animate-spin" />
                              </div>
                              <div className="text-center space-y-1">
                                <h4 className="font-extrabold text-base text-white">⚡ Analyzing Project Architecture & Code Quality...</h4>
                                <p className="text-xs text-slate-400 font-medium">Scanning source files, component hierarchy, dependency versions, and SEO readiness</p>
                              </div>

                              <div className="db-scanner-progress-bar-container">
                                <div className="db-scanner-progress-track">
                                  <div className="db-scanner-progress-fill" style={{ width: `${analysisProgress}%` }} />
                                </div>
                                <div className="db-scanner-progress-percentage">{analysisProgress}% Complete</div>
                              </div>

                              <div className="db-scanner-logs-container">
                                {analysisLogs.map((log, i) => (
                                  <div key={i} className="db-scanner-log-line">
                                    <span className="text-emerald-400 font-bold">✓</span> {log}
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : analysisResult ? (
                            <div className="db-studio-report-card">
                              <div className="db-studio-report-header">
                                <div className="flex items-center gap-3">
                                  <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 font-bold shrink-0">
                                    <Sparkles className="w-5 h-5" />
                                  </div>
                                  <div>
                                    <h3 className="font-extrabold text-base text-white">Code & Architecture Audit</h3>
                                    <p className="text-xs text-slate-400 font-medium">Automated static code analysis, tech stack detection, and Lighthouse score</p>
                                  </div>
                                </div>
                                <span className="db-studio-badge">✓ Studio-verified</span>
                              </div>

                              <div className="db-studio-report-grid">
                                {/* Left Column */}
                                <div className="space-y-4">
                                  <div className="db-report-block">
                                    <div className="flex items-center justify-between pb-1 border-b border-white/10">
                                      <h4 className="db-report-block-title">Tech Stack & Code Version</h4>
                                      {framework !== "html" ? (
                                        <button
                                          type="button"
                                          onClick={() => {
                                            setFramework("html");
                                            setVersion("1.0.0");
                                            setIsHtmlMode(true);
                                          }}
                                          className="text-[11px] px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 transition-all flex items-center gap-1 cursor-pointer"
                                          title="Override framework detection and treat as pure static HTML5"
                                        >
                                          <Code className="w-3 h-3" /> Use Just HTML
                                        </button>
                                      ) : (
                                        <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/30 flex items-center gap-1">
                                          ✓ Pure HTML5 Mode
                                        </span>
                                      )}
                                    </div>
                                    <div className="db-tech-cards-grid">
                                      {[
                                        { label: "Detected Framework", val: isHtmlMode ? "HTML5" : (analysisResult.framework_detected || "HTML"), version: isHtmlMode ? "HTML5" : (analysisResult.framework_version || analysisResult.version) },
                                        { label: "Code Version", val: isHtmlMode ? "v1.0.0" : (version ? `v${version}` : "v1.0.0") },
                                        { label: "Language", val: isHtmlMode ? "HTML5 / CSS / JS" : analysisResult.language },
                                        { label: "CSS System", val: analysisResult.css_system || "Vanilla CSS" },
                                        { label: "UI Library", val: isHtmlMode ? "Vanilla" : (analysisResult.ui_library || "None") },
                                        { label: "Animations", val: analysisResult.animation_library || "CSS3" },
                                      ].map(tech => (
                                        <div key={tech.label} className="db-tech-report-card">
                                          <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider">{tech.label}</span>
                                          <span className="text-sm font-extrabold text-white mt-0.5 truncate">{tech.val} {tech.version && tech.version !== "1.0.0" && tech.version !== "HTML5" ? `(${tech.version})` : ""}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>

                                  <div className="db-report-block">
                                    <h4 className="db-report-block-title">Pages Included ({analysisResult.pages.length})</h4>
                                    <div className="db-report-checkbox-list">
                                      {analysisResult.pages.map((p, i) => (
                                        <div key={i} className="db-report-checkbox-item">
                                          <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0 font-bold" />
                                          <span className="truncate">{p}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>

                                  <div className="db-report-block">
                                    <h4 className="db-report-block-title">Components Scanned ({analysisResult.components.length})</h4>
                                    <div className="db-report-checkbox-list">
                                      {analysisResult.components.map((c, i) => (
                                        <div key={i} className="db-report-checkbox-item">
                                          <CheckCircle className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                                          <span className="truncate">{c}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>

                                  <div className="db-report-block">
                                    <h4 className="db-report-block-title">Assets Analysis</h4>
                                    <div className="db-assets-report-grid">
                                      {[
                                        { label: "Images", count: analysisResult.assets_count?.images ?? 0 },
                                        { label: "SVGs", count: analysisResult.assets_count?.svg ?? 0 },
                                        { label: "Icons", count: analysisResult.assets_count?.icons ?? 0 },
                                        { label: "Videos", count: analysisResult.assets_count?.videos ?? 0 },
                                        { label: "Fonts", count: analysisResult.assets_count?.fonts ?? 0 },
                                      ].map(asset => (
                                        <div key={asset.label} className="db-asset-report-item">
                                          <span className="text-xs text-slate-400 font-bold">{asset.label}</span>
                                          <span className="font-mono text-sm font-extrabold text-[#dfb180]">{asset.count}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                </div>

                                {/* Right Column */}
                                <div className="space-y-4">
                                  <div className="db-report-block db-studio-score-block">
                                    <div className="flex justify-between items-center">
                                      <div>
                                        <h4 className="db-report-block-title text-amber-400">Overall Quality Rating</h4>
                                        <div className="flex items-center gap-1 mt-1">
                                          {[1, 2, 3, 4, 5].map(s => (
                                            <Star key={s} className="w-4 h-4 fill-amber-400 text-amber-400" />
                                          ))}
                                          <span className="text-xs text-amber-300 font-extrabold ml-2">({analysisResult.ai_score} / 100 Index)</span>
                                        </div>
                                      </div>
                                      <div className="db-score-circle-big">{analysisResult.ai_score}</div>
                                    </div>

                                    <div className="db-lighthouse-grid mt-3 pt-3 border-t border-amber-500/20">
                                      {[
                                        { name: "Performance", score: analysisResult.performance_scores?.performance ?? 95 },
                                        { name: "Accessibility", score: analysisResult.performance_scores?.accessibility ?? 98 },
                                        { name: "SEO", score: analysisResult.performance_scores?.seo ?? 96 },
                                        { name: "Best Practices", score: analysisResult.performance_scores?.best_practices ?? 94 },
                                      ].map(lh => (
                                        <div key={lh.name} className="flex flex-col items-center">
                                          <div className="db-score-circle-sm">{lh.score}</div>
                                          <span className="text-[10px] text-slate-300 font-extrabold mt-1 text-center">{lh.name}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>

                                  <div className="db-report-block">
                                    <h4 className="db-report-block-title">Category Detection</h4>
                                    <div className="space-y-2.5 mt-1">
                                      {Object.entries(analysisResult.categories || {}).map(([cat, confidence]) => (
                                        <div key={cat} className="space-y-1">
                                          <div className="flex justify-between text-xs font-bold text-slate-200">
                                            <span>{cat}</span>
                                            <span className="text-[#dfb180] font-extrabold">{confidence}%</span>
                                          </div>
                                          <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden border border-white/10">
                                            <div className="bg-[#c89666]/15 h-full rounded-full" style={{ width: `${confidence}%` }} />
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>

                                  <div className="grid grid-cols-2 gap-4">
                                    <div className="db-report-block">
                                      <h4 className="db-report-block-title">Brand Colors</h4>
                                      <div className="db-palette-row">
                                        {(analysisResult.color_palette || []).map((color, i) => (
                                          <div
                                            key={i}
                                            className="db-palette-chip"
                                            style={{ backgroundColor: color }}
                                            title={color}
                                          />
                                        ))}
                                      </div>
                                    </div>
                                    <div className="db-report-block">
                                      <h4 className="db-report-block-title">Typography</h4>
                                      <div className="db-typography-row">
                                        {(analysisResult.typography || []).map((font, i) => (
                                          <span key={i} className="font-chip">{font}</span>
                                        ))}
                                      </div>
                                    </div>
                                  </div>

                                  <div className="grid grid-cols-2 gap-4">
                                    <div className="db-report-block">
                                      <h4 className="db-report-block-title">SEO Compliance</h4>
                                      <div className="db-checks-list">
                                        {[
                                          { label: "Meta Title", check: analysisResult.seo_analysis?.meta_title },
                                          { label: "Meta Desc", check: analysisResult.seo_analysis?.meta_description },
                                          { label: "OG Tags", check: analysisResult.seo_analysis?.og_tags },
                                          { label: "robots.txt", check: analysisResult.seo_analysis?.robots_txt },
                                          { label: "sitemap.xml", check: analysisResult.seo_analysis?.sitemap_xml },
                                        ].map(item => (
                                          <div key={item.label} className="db-check-item">
                                            <span className="text-xs text-slate-200 font-bold">{item.label}</span>
                                            <span className={item.check ? "text-emerald-400 font-extrabold text-xs" : "text-slate-500 font-bold text-xs"}>
                                              {item.check ? "✓ Pass" : "✗ None"}
                                            </span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                    <div className="db-report-block">
                                      <h4 className="db-report-block-title">Accessibility</h4>
                                      <div className="db-checks-list">
                                        {[
                                          { label: "ARIA Labels", check: analysisResult.accessibility?.aria_labels },
                                          { label: "Alt Tags", check: analysisResult.accessibility?.alt_tags },
                                          { label: "Keyboard Nav", check: analysisResult.accessibility?.keyboard_navigation },
                                          { label: "Color Contrast", check: analysisResult.accessibility?.contrast_safe },
                                        ].map(item => (
                                          <div key={item.label} className="db-check-item">
                                            <span className="text-xs text-slate-200 font-bold">{item.label}</span>
                                            <span className={item.check ? "text-emerald-400 font-extrabold text-xs" : "text-slate-500 font-bold text-xs"}>
                                              {item.check ? "✓ Pass" : "✗ None"}
                                            </span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  </div>

                                  <div className="db-report-block db-recommendations-block">
                                    <h4 className="db-report-block-title text-amber-300">💡 Architecture & Code Recommendations</h4>
                                    <ul className="db-suggestions-list">
                                      {(analysisResult.ai_suggestions || []).map((sug, i) => (
                                        <li key={i}>
                                          <span className="text-amber-600 font-bold shrink-0">→</span>
                                          <span>{sug}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                </div>
                              </div>

                              <div className="uw-footer">
                                <button
                                  type="button"
                                  onClick={() => setWizardStep(1)}
                                  className="uw-btn-back"
                                >
                                  ← Back to Source Selection
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setWizardStep(3)}
                                  className="uw-btn-publish"
                                >
                                  Continue to Review & Publish →
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="text-center py-8 text-slate-500 font-medium">Analysis error. Please try uploading again.</div>
                          )}
                        </div>
                      )}

                      {/* STEP 3: REVIEW & PUBLISH */}
                      {wizardStep === 3 && (
                        <div className="uw-container animate-in fade-in duration-200">
                          {isIncompleteAnalysis ? (
                            <div className="uw-alert-warning">
                              <Info className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                              <div className="space-y-1">
                                <p className="text-xs font-extrabold text-amber-300 uppercase tracking-wide">
                                  ⚠️ Incomplete Auto-Detection — Manual Review Required
                                </p>
                                <p className="text-xs text-amber-200 leading-relaxed font-medium">
                                  Our audit could not fully determine some parameters from your upload. Please review all fields below and fill in any missing details before publishing.
                                </p>
                              </div>
                            </div>
                          ) : (
                            <div className="uw-alert-autofill">
                              <Sparkles className="w-5 h-5 text-emerald-400 shrink-0" />
                              <p className="text-xs text-emerald-200 leading-relaxed font-medium">
                                <strong className="font-extrabold text-white">✨ Instant Auto-Fill Active:</strong> We have analyzed your project and pre-filled standard catalog details. Please review these parameters and click <strong>Publish Template</strong>.
                              </p>
                            </div>
                          )}

                          {/* ── CARD 1: BASIC INFORMATION & OVERVIEW ── */}
                          <div className="uw-section-card">
                            <div className="uw-section-header">
                              <div className="uw-icon-badge" style={{ backgroundColor: "rgba(200, 150, 102, 0.15)", color: "#dfb180" }}>
                                <FileText className="w-4 h-4" />
                              </div>
                              <div>
                                <h4 className="uw-section-title">Basic Information & Overview</h4>
                                <p className="uw-section-subtitle">Main template title, marketplace slug, and marketing descriptions</p>
                              </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                              <div>
                                <label className="uw-label">
                                  Template Title * {isIncompleteAnalysis && !title && <span className="text-amber-600 normal-case ml-1">(Required)</span>}
                                </label>
                                <input
                                  type="text"
                                  required
                                  value={title}
                                  onChange={(e) => setTitle(e.target.value)}
                                  placeholder="e.g. Nexus - Modern SaaS Landing Page"
                                  className="uw-input"
                                />
                              </div>
                              <div>
                                <label className="uw-label">
                                  URL Slug *
                                </label>
                                <input
                                  type="text"
                                  value={slug}
                                  onChange={(e) => setSlug(e.target.value)}
                                  placeholder="nexus-modern-saas-landing"
                                  className="uw-input font-mono"
                                />
                              </div>
                            </div>

                            <div>
                              <label className="uw-label">
                                Short Tagline / Summary * {isIncompleteAnalysis && !shortDesc && <span className="text-amber-600 normal-case ml-1">(Required)</span>}
                              </label>
                              <input
                                type="text"
                                value={shortDesc}
                                onChange={(e) => setShortDesc(e.target.value)}
                                placeholder="A high-converting, responsive landing page built with modern standards."
                                className="uw-input"
                              />
                            </div>

                            <div>
                              <label className="uw-label">
                                Detailed Product Description * {isIncompleteAnalysis && !desc && <span className="text-amber-600 normal-case ml-1">(Required)</span>}
                              </label>
                              <textarea
                                rows={4}
                                value={desc}
                                onChange={(e) => setDesc(e.target.value)}
                                placeholder="Describe full template features, customization options, responsive views, and technical advantages..."
                                className="uw-textarea"
                              />
                            </div>
                          </div>

                          {/* ── CARD 2: TECHNICAL & FRAMEWORK ARCHITECTURE ── */}
                          <div className="uw-section-card">
                            <div className="uw-section-header">
                              <div className="uw-icon-badge" style={{ backgroundColor: "rgba(200, 150, 102, 0.15)", color: "#dfb180" }}>
                                <Code className="w-4 h-4" />
                              </div>
                              <div>
                                <h4 className="uw-section-title">Framework & Technical Specifications</h4>
                                <p className="uw-section-subtitle">Category, framework engine, semantic code version, and licensing terms</p>
                              </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                              <div>
                                <label className="uw-label">
                                  Category * {isIncompleteAnalysis && !categoryId && <span className="text-amber-600 normal-case ml-1">(Select)</span>}
                                </label>
                                <select
                                  required
                                  value={categoryId}
                                  onChange={(e) => setCategoryId(e.target.value)}
                                  className="uw-select"
                                >
                                  <option value="">Select Category</option>
                                  {categories.map((c) => (
                                    <option key={c.id} value={c.id}>{c.name}</option>
                                  ))}
                                </select>
                              </div>

                              <div>
                                <div className="flex items-center justify-between mb-1.5">
                                  <label className="uw-label" style={{ marginBottom: 0 }}>
                                    Framework *
                                  </label>
                                  {framework !== "html" && (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setFramework("html");
                                        setVersion("1.0.0");
                                        setIsHtmlMode(true);
                                      }}
                                      className="text-[10px] text-emerald-600 hover:underline font-extrabold cursor-pointer border-none bg-transparent"
                                    >
                                      Just HTML?
                                    </button>
                                  )}
                                </div>
                                <select
                                  required
                                  value={framework}
                                  onChange={(e) => {
                                    setFramework(e.target.value);
                                    if (e.target.value === "html") {
                                      setIsHtmlMode(true);
                                      if (!version || version === "15.0.0" || version === "19.0.0" || version === "3.0.0" || version === "4.0.0") {
                                        setVersion("1.0.0");
                                      }
                                    } else {
                                      setIsHtmlMode(false);
                                    }
                                  }}
                                  className="uw-select"
                                >
                                  <option value="html">HTML5 (Pure HTML / Static)</option>
                                  <option value="nextjs">Next.js</option>
                                  <option value="react">React</option>
                                  <option value="vue">Vue.js</option>
                                  <option value="nuxt">Nuxt.js</option>
                                  <option value="astro">Astro</option>
                                  <option value="tailwind">Tailwind CSS (HTML)</option>
                                  <option value="angular">Angular</option>
                                  <option value="svelte">Svelte</option>
                                </select>
                              </div>

                              <div>
                                <div className="flex items-center justify-between mb-1.5">
                                  <label className="uw-label" style={{ marginBottom: 0 }}>
                                    Code Version *
                                  </label>
                                  <span className="text-[10px] text-[#dfb180] font-extrabold px-1.5 py-0.5 rounded bg-[#c89666]/15 border border-[#c89666]/30">Auto-detected</span>
                                </div>
                                <input
                                  type="text"
                                  required
                                  value={version}
                                  onChange={(e) => setVersion(e.target.value)}
                                  placeholder="1.0.0"
                                  className="uw-input font-mono"
                                />
                              </div>

                            </div>


                            {/* Sub-Category / Industry Focus */}
                            <div className="space-y-2 pt-2 border-t border-slate-100">
                              <div className="flex items-center justify-between">
                                <label className="uw-label" style={{ marginBottom: 0 }}>
                                  Sub-Category / Specialization
                                </label>
                                {subCategory && (
                                  <span className="text-xs font-bold text-[#dfb180] px-2 py-0.5 rounded-md bg-[#c89666]/15 border border-[#c89666]/30">
                                    Selected: {subCategory}
                                  </span>
                                )}
                              </div>
                              <input
                                type="text"
                                value={subCategory}
                                onChange={(e) => setSubCategory(e.target.value)}
                                placeholder="e.g. Corporate, Small Business, Dashboard, Cafe, Clinic"
                                className="uw-input"
                              />
                              {categoryId && categories.find(c => c.id === categoryId) && (
                                <div className="uw-pill-container">
                                  {(DASHBOARD_SUB_CATEGORIES[categories.find(c => c.id === categoryId)?.slug] || ["General", "Custom"]).map(sub => {
                                    const isSelected = subCategory.toLowerCase() === sub.toLowerCase();
                                    return (
                                      <button
                                        key={sub}
                                        type="button"
                                        onClick={() => {
                                          setSubCategory(sub);
                                          if (!tags.toLowerCase().includes(sub.toLowerCase())) {
                                            setTags(prev => prev ? `${prev}, ${sub.toLowerCase()}` : sub.toLowerCase());
                                          }
                                        }}
                                        className={cn("uw-pill", isSelected && "uw-pill-active")}
                                      >
                                        {sub}
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* ── CARD 3: PRICING & COMMERCIAL TERMS ── */}
                          <div className="uw-section-card">
                            <div className="uw-section-header">
                              <div className="uw-icon-badge" style={{ backgroundColor: "rgba(16, 185, 129, 0.15)", color: "#34d399" }}>
                                <CreditCard className="w-4 h-4" />
                              </div>
                              <div>
                                <h4 className="uw-section-title">Pricing & Marketplace Listing</h4>
                                <p className="uw-section-subtitle">Set catalog currency, listing prices, and monetization tiers</p>
                              </div>
                            </div>

                            {user?.country && (
                              <div className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-blue-500/10 border border-blue-500/30 text-xs font-semibold text-blue-300">
                                <Globe className="w-4 h-4 shrink-0 text-blue-400" />
                                <span>
                                  Seller Location: <strong>{user.city && user.city !== "Unknown" ? `${user.city}, ` : ""}{user.country}</strong> — Pricing currency auto-selected to <strong>{priceCurrency}</strong> based on location
                                </span>
                              </div>
                            )}

                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                              <div>
                                <label className="uw-label">
                                  Pricing Currency *
                                </label>
                                <select
                                  value={priceCurrency}
                                  onChange={(e) => setPriceCurrency(e.target.value)}
                                  className="uw-select"
                                >
                                  <option value="USD">USD ($)</option>
                                  <option value="INR">INR (₹)</option>
                                  <option value="EUR">EUR (€)</option>
                                  <option value="GBP">GBP (£)</option>
                                  <option value="CAD">CAD (CA$)</option>
                                  <option value="AUD">AUD (A$)</option>
                                  <option value="JPY">JPY (¥)</option>
                                  <option value="AED">AED (AED)</option>
                                </select>
                              </div>
                              <div>
                                <label className="uw-label">
                                  Regular Price ({priceCurrency}) *
                                </label>
                                <input
                                  type="number"
                                  required
                                  min="0"
                                  value={price}
                                  onChange={(e) => setPrice(e.target.value)}
                                  className="uw-input font-mono font-extrabold"
                                />
                              </div>
                              <div>
                                <label className="uw-label">
                                  Original Price (Sale Reference)
                                </label>
                                <input
                                  type="number"
                                  min="0"
                                  value={salePrice}
                                  onChange={(e) => setSalePrice(e.target.value)}
                                  placeholder="Optional original price"
                                  className="uw-input font-mono"
                                />
                              </div>
                            </div>

                            {/* Auto USD Conversion Indicator for Sellers */}
                            {price && Number(price) > 0 && (
                              <div className="uw-pricing-box">
                                <div className="flex items-center gap-2.5">
                                  <Sparkles className="w-4 h-4 text-emerald-600 shrink-0" />
                                  <span className="text-emerald-950 font-semibold">
                                    Marketplace Listing Price: <strong className="text-emerald-700 font-extrabold text-sm">${convertToUSD(price, priceCurrency, rates)} USD</strong>
                                    {priceCurrency !== "USD" && ` (Auto-converted from ${priceCurrency} ${price})`}
                                  </span>
                                </div>
                                <span className="uw-currency-badge">
                                  USD Catalog
                                </span>
                              </div>
                            )}

                            <label className="uw-checkbox-card">
                              <input
                                type="checkbox"
                                id="premium"
                                checked={premium}
                                onChange={(e) => setPremium(e.target.checked)}
                              />
                              <div>
                                <span className="text-xs font-extrabold text-slate-900 uppercase tracking-wider block">
                                  Mark as Premium Marketplace Template
                                </span>
                                <span className="text-[11px] text-slate-500 font-medium">Featured in premium curated collections and seller showcases</span>
                              </div>
                            </label>
                          </div>

                          {/* ── CARD 4: MEDIA & PREVIEW ASSETS ── */}
                          <div className="uw-section-card">
                            <div className="uw-section-header">
                              <div className="uw-icon-badge" style={{ backgroundColor: "rgba(200, 150, 102, 0.15)", color: "#c084fc" }}>
                                <Palette className="w-4 h-4" />
                              </div>
                              <div>
                                <h4 className="uw-section-title">Media & Visual Assets</h4>
                                <p className="uw-section-subtitle">Cover photo, live demo URL, screenshot gallery, and video preview</p>
                              </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                              <div className="space-y-1">
                                <label className="uw-label">
                                  Thumbnail Cover Photo *
                                </label>
                                <div className="uw-file-card">
                                  <label className="uw-file-btn">
                                    Choose Photo
                                    <input
                                      type="file"
                                      accept="image/*"
                                      required={!thumbnailFile}
                                      onChange={(e) => setThumbnailFile(e.target.files[0])}
                                      className="hidden"
                                    />
                                  </label>
                                  <span className="uw-file-text">
                                    {thumbnailFile ? `✓ ${thumbnailFile.name} (${(thumbnailFile.size / 1024).toFixed(1)} KB)` : "No cover photo chosen yet"}
                                  </span>
                                </div>
                              </div>

                              <div className="space-y-1">
                                <label className="uw-label">
                                  Live Demo URL
                                </label>
                                <input
                                  type="url"
                                  value={demoUrl}
                                  onChange={(e) => setDemoUrl(e.target.value)}
                                  placeholder="https://demotemplate.aisitestudio.com"
                                  className="uw-input"
                                />
                              </div>
                            </div>

                            {/* Screenshots & Gallery Images Section with + Icon */}
                            <div className="space-y-2 p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
                              <div className="flex items-center justify-between">
                                <div>
                                  <label className="uw-label" style={{ marginBottom: 0 }}>
                                    Screenshots & Gallery Showcase (Optional)
                                  </label>
                                  <p className="text-[11px] text-slate-500 font-medium">
                                    Add multiple showcase screenshots of pages, responsive views, and components.
                                  </p>
                                </div>
                                <span className="text-xs font-extrabold text-[#dfb180] px-2 py-0.5 rounded-md bg-[#c89666]/15 border border-[#c89666]/30">
                                  {galleryFiles.length} image{galleryFiles.length !== 1 ? "s" : ""} selected
                                </span>
                              </div>

                              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-3 pt-1">
                                {galleryPreviews.map((previewUrl, idx) => (
                                  <div key={idx} className="relative aspect-video rounded-lg overflow-hidden border border-slate-300 bg-white group shadow-xs">
                                    <img src={previewUrl} alt={`Gallery ${idx + 1}`} className="w-full h-full object-cover" />
                                    <button
                                      type="button"
                                      onClick={() => handleRemoveDashboardGalleryFile(idx)}
                                      className="absolute top-1 right-1 p-1 rounded-full bg-red-600 hover:bg-red-700 text-white shadow opacity-90 group-hover:opacity-100 transition-all border-none cursor-pointer"
                                      title="Remove image"
                                    >
                                      <X className="w-3 h-3" />
                                    </button>
                                    <span className="absolute bottom-1 left-1 bg-black/75 backdrop-blur-sm text-white text-[9px] px-1.5 py-0.5 rounded font-mono font-bold">
                                      #{idx + 1}
                                    </span>
                                  </div>
                                ))}

                                {/* + Add Images Card */}
                                <label className="aspect-video rounded-lg border-2 border-dashed border-[#c89666]/30 hover:border-[#c89666]/30 bg-[#c89666]/15 hover:bg-[#c89666]/15 flex flex-col items-center justify-center gap-1 transition-all cursor-pointer group text-[#dfb180] select-none">
                                  <input
                                    type="file"
                                    accept="image/*"
                                    multiple
                                    onChange={handleAddDashboardGalleryFiles}
                                    className="hidden"
                                  />
                                  <div className="w-7 h-7 rounded-full bg-[#c89666]/15 flex items-center justify-center group-hover:scale-110 transition-transform">
                                    <Plus className="w-4 h-4 text-[#dfb180]" />
                                  </div>
                                  <span className="text-[11px] font-bold">Add Images</span>
                                </label>
                              </div>
                            </div>

                            {/* Video Upload or URL */}
                            <div className="p-3.5 border border-blue-200 bg-blue-50/40 rounded-xl space-y-2">
                              <label className="text-xs font-bold text-blue-900 uppercase tracking-wider flex items-center gap-1.5">
                                <Video className="w-4 h-4 text-blue-600" />
                                Video Walkthrough Preview (Optional)
                              </label>
                              <p className="text-[11px] text-slate-500 font-medium">Upload an MP4/WebM video or paste a YouTube / Vimeo / Loom link. Upload size depends on your connection and hosting limits.</p>

                              <div className="space-y-2">
                                <div className="uw-file-card" style={{ backgroundColor: "#ffffff" }}>
                                  <label className="uw-file-btn uw-file-btn-blue">
                                    Choose Video File
                                    <input
                                      type="file"
                                      accept="video/mp4,video/webm,video/quicktime,video/ogg"
                                      onChange={(e) => {
                                        const file = e.target.files[0];
                                        setVideoFile(file);
                                      }}
                                      className="hidden"
                                    />
                                  </label>
                                  <span className="uw-file-text">
                                    {videoFile ? `✓ ${videoFile.name} (${(videoFile.size / (1024 * 1024)).toFixed(2)} MB)` : "No video file selected"}
                                  </span>
                                  {videoFile && (
                                    <button
                                      type="button"
                                      onClick={() => setVideoFile(null)}
                                      className="text-xs text-red-500 hover:text-red-700 ml-2 font-bold cursor-pointer"
                                    >
                                      Remove
                                    </button>
                                  )}
                                </div>

                                <div className="flex items-center gap-2">
                                  <span className="text-[10px] uppercase font-bold text-slate-400">OR</span>
                                  <input
                                    type="url"
                                    value={videoUrl}
                                    onChange={(e) => setVideoUrl(e.target.value)}
                                    placeholder="Paste YouTube, Vimeo, Loom or MP4 URL (e.g. https://www.youtube.com/watch?v=...)"
                                    className="uw-input text-xs"
                                  />
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* ── CARD 5: SEO & DISCOVERABILITY ── */}
                          <div className="uw-section-card">
                            <div className="uw-section-header">
                              <div className="uw-icon-badge" style={{ backgroundColor: "rgba(245, 158, 11, 0.15)", color: "#fbbf24" }}>
                                <Tag className="w-4 h-4" />
                              </div>
                              <div>
                                <h4 className="uw-section-title">SEO & Marketplace Discoverability</h4>
                                <p className="uw-section-subtitle">Tags and keyword metadata to optimize search rankings</p>
                              </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                              <div>
                                <label className="uw-label">
                                  Tags (Comma-separated)
                                </label>
                                <input
                                  type="text"
                                  value={tags}
                                  onChange={(e) => setTags(e.target.value)}
                                  placeholder="saas, dashboard, admin, tailwind, responsive"
                                  className="uw-input"
                                />
                              </div>
                              <div>
                                <label className="uw-label">
                                  SEO Keywords (Comma-separated)
                                </label>
                                <input
                                  type="text"
                                  value={keywords}
                                  onChange={(e) => setKeywords(e.target.value)}
                                  placeholder="agency website, landing page, custom nextjs template"
                                  className="uw-input"
                                />
                              </div>
                            </div>
                          </div>

                          {/* ── FOOTER ACTIONS ── */}
                          <div className="uw-footer">
                            <button
                              type="button"
                              onClick={() => setWizardStep(2)}
                              className="uw-btn-back"
                            >
                              ← Back to Audit Report
                            </button>
                            <button
                              type="submit"
                              disabled={uploading}
                              className="uw-btn-publish"
                            >
                              {uploading ? (
                                <>
                                  <Loader2 className="w-4 h-4 animate-spin" /> Publishing Template...
                                </>
                              ) : (
                                <>
                                  Publish Template <Check className="w-4 h-4" />
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      )}
                    </form>
                  </>
                </div>
              )}

              {/* === SELLER SALES ANALYTICS === */}
              {activeTab === "seller-analytics" && (
                <div className="glass-premium p-6 sm:p-8 space-y-6">
                  <div>
                    <h3 className="font-extrabold text-xl text-foreground">Sales Analytics</h3>
                    <p className="text-xs text-muted-foreground font-medium">Track detailed real-time metrics of your platform product sales.</p>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {[
                      { label: "Total Sales", value: (earningsSummary?.sales || []).length.toLocaleString(), sub: "Completed orders", icon: ShoppingBag, color: "#059669", bg: "#ecfdf5" },
                      { label: "Net Revenue", value: formatPrice(earningsSummary?.total_earned || 0), sub: "Gross income", icon: Coins, color: "#2563eb", bg: "#eff6ff" },
                      { label: "Unique Accounts", value: sellerTotalViews.toLocaleString(), sub: "Distinct accounts", icon: Users, color: "#0891b2", bg: "#ecfeff" },
                      { label: "Downloads Count", value: sellerTotalDownloads.toLocaleString(), sub: "Packages retrieved", icon: Download, color: "#b5804f", bg: "#eef2ff" },
                      { label: "Refund Requests", value: "0", sub: "Disputes logged", icon: ShieldCheck, color: "#64748b", bg: "#f1f5f9" },
                      { label: "Conversion Rate", value: sellerConversionRate, sub: "Sales / Accounts ratio", icon: TrendingUp, color: "#059669", bg: "#ecfdf5" },
                    ].map((stat, idx) => {
                      const Icon = stat.icon;
                      return (
                        <div key={idx} className="p-4 border border-border/30 rounded-xl space-y-2 bg-slate-800/40 backdrop-blur-sm">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] text-muted-foreground font-extrabold uppercase tracking-wider">{stat.label}</span>
                            <div className="w-6 h-6 rounded-lg flex items-center justify-center" style={{ backgroundColor: stat.bg, color: stat.color }}>
                              <Icon className="w-3.5 h-3.5" />
                            </div>
                          </div>
                          <div>
                            <div className="text-2xl font-black text-foreground font-mono">{stat.value}</div>
                            <div className="text-[10px] text-muted-foreground font-medium">{stat.sub}</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* === SELLER EARNINGS === */}
              {activeTab === "seller-earnings" && (
                <div className="glass-premium p-6 sm:p-8 space-y-6">
                  <div className="flex justify-between items-center flex-wrap gap-4">
                    <div>
                      <h3 className="font-extrabold text-xl text-foreground">Earnings Balance & Transactions</h3>
                      <p className="text-xs text-muted-foreground font-medium">Current withdrawal balance and payouts metrics.</p>
                    </div>
                    <button
                      onClick={() => setActiveTab("seller-payouts")}
                      className="mt-cta-btn"
                    >
                      Request Payout
                    </button>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { label: "Current Balance", value: formatPrice(earningsSummary.available_balance || 0), color: "#10b981" },
                      { label: "Available to Withdraw", value: formatPrice(earningsSummary.available_balance || 0), color: "#10b981" },
                      { label: "Pending Amount", value: formatPrice(earningsSummary.pending_withdrawal || 0), color: "#f59e0b" },
                      { label: "Lifetime Earnings", value: formatPrice(earningsSummary.total_earned || 0), color: "#c89666" },
                    ].map((c, i) => (
                      <div key={i} className="p-4 border border-border/30 rounded-xl space-y-1 bg-slate-800/40 backdrop-blur-sm">
                        <div className="text-[10px] text-muted-foreground font-extrabold uppercase tracking-wider">{c.label}</div>
                        <div className="text-xl font-black font-mono" style={{ color: c.color }}>{c.value}</div>
                      </div>
                    ))}
                  </div>

                  <div className="border-t border-border/20 pt-4 space-y-3">
                    <h4 className="font-extrabold text-sm text-foreground">Recent Transactions</h4>
                    <div className="overflow-x-auto rounded-xl border border-border/30">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-border/30 bg-muted/20 text-muted-foreground font-extrabold">
                            <th className="p-3">Date</th>
                            <th className="p-3">Template</th>
                            <th className="p-3">Buyer</th>
                            <th className="p-3">Amount</th>
                            <th className="p-3">Net Income</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/20">
                          {earningsSummary.sales && earningsSummary.sales.length > 0 ? (
                            earningsSummary.sales.map((sale, idx) => (
                              <tr key={idx} className="hover:bg-muted/10 transition-colors text-foreground font-medium">
                                <td className="p-3 text-muted-foreground">{new Date(sale.date).toLocaleDateString()}</td>
                                <td className="p-3 font-bold text-foreground">{sale.template_title}</td>
                                <td className="p-3 text-muted-foreground select-all">{sale.purchaser_email}</td>
                                <td className="p-3 font-mono text-foreground font-bold">{formatPrice(sale.price)}</td>
                                <td className="p-3 font-mono text-emerald-400 font-black">{formatPrice(sale.price)}</td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td colSpan={5} className="py-6 text-center text-muted-foreground text-xs font-medium">
                                No recent earnings transactions found.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* === SELLER ORDERS === */}
              {activeTab === "seller-orders" && (
                <div className="glass-premium p-6 sm:p-8 space-y-6">
                  <div>
                    <h3 className="font-extrabold text-xl text-foreground">Sales Orders Ledger</h3>
                    <p className="text-xs text-muted-foreground font-medium">Log of verified purchases made on your templates.</p>
                  </div>
                  <div className="overflow-x-auto rounded-xl border border-border/30">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/30 bg-muted/20 text-muted-foreground font-extrabold uppercase">
                          <th className="p-3">Order Number</th>
                          <th className="p-3">Template Title</th>
                          <th className="p-3">Buyer</th>
                          <th className="p-3">License Type</th>
                          <th className="p-3">Date</th>
                          <th className="p-3">Amount</th>
                          <th className="p-3 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/20">
                        {earningsSummary.sales && earningsSummary.sales.length > 0 ? (
                          earningsSummary.sales.map((sale, idx) => (
                            <tr key={idx} className="hover:bg-muted/10 transition-colors text-foreground font-medium">
                              <td className="p-3">
                                <div className="font-mono font-extrabold text-foreground">#{sale.order_number}</div>
                                {sale.upi_utr && (
                                  <div className="inline-flex items-center gap-1 text-[10px] font-mono font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-1.5 py-0.5 rounded mt-0.5">
                                    UTR: {sale.upi_utr}
                                  </div>
                                )}
                              </td>
                              <td className="p-3 font-bold text-foreground">{sale.template_title}</td>
                              <td className="p-3 text-muted-foreground select-all">{sale.purchaser_email}</td>
                              <td className="p-3">
                                <span className="inline-block bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30 px-2 py-0.5 rounded-full font-extrabold uppercase text-[9px] tracking-wider">
                                  {sale.license_type || "REGULAR"}
                                </span>
                              </td>
                              <td className="p-3 text-muted-foreground">{new Date(sale.date).toLocaleDateString()}</td>
                              <td className="p-3 font-mono text-emerald-400 font-black">{formatPrice(sale.price)}</td>
                              <td className="p-3 text-right">
                                <a
                                  href={`/dashboard/receipt/${sale.order_id || sale.orderId || "undefined"}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center text-[11px] font-bold bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30 px-2.5 py-1 rounded-lg hover:bg-[#c89666]/15 transition-all text-decoration-none shadow-xs"
                                >
                                  Receipt
                                </a>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={7} className="py-6 text-center text-slate-500 text-xs font-medium">
                              No recent sales orders found.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* === SELLER REVIEWS === */}
              {activeTab === "seller-reviews" && (
                <div className="glass-premium p-6 sm:p-8 space-y-6">
                  <div className="space-y-1">
                    <h3 className="font-extrabold text-xl text-foreground">Client Template Reviews</h3>
                    <p className="text-xs text-muted-foreground font-medium">Monitor product feedback and reviews received on your templates.</p>
                  </div>

                  {sellerReviewsLoading ? (
                    <div className="text-center py-10">
                      <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#dfb180]" />
                    </div>
                  ) : sellerReviewsList.length === 0 ? (
                    <div className="mt-empty-card">
                      <div className="mt-empty-icon">
                        <Star className="w-7 h-7" />
                      </div>
                      <h4 className="mt-empty-title">No Customer Reviews Yet</h4>
                      <p className="mt-empty-desc">
                        When buyers purchase and review your uploaded templates, their verified comments and ratings will automatically appear here.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {sellerReviewsList.map((review) => (
                        <div key={review.id} className="p-5 border border-border/30 rounded-2xl space-y-4 bg-slate-800/40 backdrop-blur-sm shadow-sm">
                          <div className="flex justify-between items-start gap-4">
                            <div className="flex items-center gap-3.5">
                              <div className="follower-avatar-wrap">
                                {review.user?.avatar_url ? (
                                  <img
                                    src={resolveMediaUrl(review.user.avatar_url)}
                                    alt=""
                                    className="follower-avatar-img"
                                    onError={(e) => {
                                      e.currentTarget.style.setProperty('display', 'none', 'important');
                                      const fb = e.currentTarget.parentElement?.querySelector('.follower-avatar-fallback');
                                      if (fb) fb.style.setProperty('display', 'flex', 'important');
                                    }}
                                  />
                                ) : null}
                                <span
                                  className="follower-avatar-fallback"
                                  style={{ display: review.user?.avatar_url ? "none" : "flex" }}
                                >
                                  {(review.user?.fullName?.[0] || review.user?.username?.[0] || "U").toUpperCase()}
                                </span>
                              </div>
                              <div className="space-y-1">
                                <div className="font-extrabold text-sm text-foreground">
                                  {review.user?.fullName || review.user?.username || "Anonymous Client"}
                                </div>
                                <div className="flex items-center gap-2 flex-wrap">
                                  <div className="flex items-center gap-0.5">
                                    {[1, 2, 3, 4, 5].map((s) => {
                                      const ratingVal = Number(review.rating || 0);
                                      const isFilled = s <= (ratingVal > 0 ? ratingVal : 5);
                                      return (
                                        <Star
                                          key={s}
                                          className={`w-3.5 h-3.5 ${isFilled ? "fill-amber-400 text-amber-400" : "fill-slate-800 text-slate-700"}`}
                                        />
                                      );
                                    })}
                                  </div>
                                  <span className="text-xs text-muted-foreground font-medium flex items-center gap-1">
                                    <span>on</span>
                                    <strong className="text-foreground font-bold">{review.template?.title || "Template"}</strong>
                                    <span>·</span>
                                    <span>{review.created_at ? new Date(review.created_at).toLocaleDateString(undefined, { dateStyle: "medium" }) : "Recently"}</span>
                                  </span>
                                  {review.is_verified_purchase && (
                                    <span className="text-[9px] bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full font-extrabold uppercase tracking-wider ml-1">
                                      Verified Purchase
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>

                          <div className="pt-3 border-t border-border/20 space-y-1">
                            <h5 className="font-extrabold text-sm text-foreground">{review.title}</h5>
                            <p className="text-xs text-muted-foreground font-medium leading-relaxed">{review.body}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* === SELLER PERFORMANCE === */}
              {activeTab === "seller-performance" && (
                <div className="glass-premium p-6 sm:p-8 space-y-6">
                  <div>
                    <h3 className="font-extrabold text-xl text-foreground">Detailed Performance</h3>
                    <p className="text-xs text-muted-foreground font-medium">Check unique account visits and conversion metrics per template.</p>
                  </div>
                  {!sellerTemplatesList || sellerTemplatesList.length === 0 ? (
                    <div className="mt-empty-card">
                      <div className="mt-empty-icon">
                        <BarChart3 className="w-7 h-7" />
                      </div>
                      <h4 className="mt-empty-title">No Templates Found</h4>
                      <p className="mt-empty-desc">Upload templates to start tracking detailed item-by-item analytics.</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto rounded-xl border border-border/30">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-border/30 bg-muted/20 text-muted-foreground font-extrabold uppercase">
                            <th className="p-3">Template Title</th>
                            <th className="p-3">Unique Accounts</th>
                            <th className="p-3">Downloads</th>
                            <th className="p-3">Rating</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/20">
                          {sellerTemplatesList.map((perf, idx) => (
                            <tr key={idx} className="hover:bg-muted/10 transition-colors text-foreground font-medium">
                              <td className="p-3 font-bold text-foreground">{perf.title}</td>
                              <td className="p-3 font-mono text-muted-foreground font-bold">{perf.views_count || 0}</td>
                              <td className="p-3 font-mono text-muted-foreground font-bold">{perf.downloads_count || 0}</td>
                              <td className="p-3 font-semibold text-amber-400">
                                {perf.rating_count > 0 ? `${(perf.rating_avg || 0).toFixed(1)} ★ (${perf.rating_count})` : "No ratings yet"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* === SELLER FOLLOWERS === */}
              {activeTab === "seller-followers" && (
                <div className="glass-premium p-6 sm:p-8 space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/20 pb-5">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2.5">
                        <h3 className="font-extrabold text-xl text-foreground">Followers</h3>
                        {Array.isArray(followers) && followers.length > 0 && (
                          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30">
                            {followers.length}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground font-medium">Users and community members who follow your updates.</p>
                    </div>
                  </div>

                  {followersLoading && (!followers || followers.length === 0) ? (
                    <div className="text-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#dfb180]" />
                      <p className="text-xs text-muted-foreground mt-2 font-medium">Loading followers...</p>
                    </div>
                  ) : !followers || followers.length === 0 ? (
                    <div className="mt-empty-card">
                      <div className="mt-empty-icon">
                        <Users className="w-7 h-7" />
                      </div>
                      <h4 className="mt-empty-title">No Followers Yet</h4>
                      <p className="mt-empty-desc">
                        When clients and users follow your profile from template pages, they will appear here.
                      </p>
                    </div>
                  ) : (
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      {followers.map((follower) => {
                        const avatarSrc = resolveMediaUrl(follower.avatar_url);
                        const displayName = follower.full_name || follower.username || "Community Member";
                        const initial = (follower.full_name || follower.username || "U").charAt(0).toUpperCase();

                        return (
                          <div key={follower.id} className="follower-card">
                            <div className="flex items-center gap-3.5 min-w-0">
                              <div className="follower-avatar-wrap">
                                {avatarSrc ? (
                                  <img
                                    src={avatarSrc}
                                    alt=""
                                    className="follower-avatar-img"
                                    onError={(e) => {
                                      e.currentTarget.style.setProperty('display', 'none', 'important');
                                      const fb = e.currentTarget.parentElement?.querySelector('.follower-avatar-fallback');
                                      if (fb) fb.style.setProperty('display', 'flex', 'important');
                                    }}
                                  />
                                ) : null}
                                <span
                                  className="follower-avatar-fallback"
                                  style={{ display: avatarSrc ? "none" : "flex" }}
                                >
                                  {initial}
                                </span>
                              </div>
                              <div className="space-y-0.5 min-w-0">
                                <div className="font-extrabold text-sm text-foreground truncate">
                                  {displayName}
                                </div>
                                <span className="text-xs text-muted-foreground font-medium truncate block">
                                  @{follower.username || "user"}
                                </span>
                              </div>
                            </div>
                            <span className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-white/5 text-slate-300 border border-white/10 shrink-0">
                              Follower
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}

                </div>
              )}


              {/* === SELLER CUSTOMER MESSAGES === */}
              {activeTab === "seller-messages" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Creator Support Messages</h3>
                    <p className="text-sm text-muted-foreground">Respond to client questions, bug reports, and features suggestions.</p>
                  </div>

                  <div className="grid md:grid-cols-3 gap-6">
                    {/* Inbox List */}
                    <div className="md:col-span-1 border-r border-border/50 pr-4 space-y-2">
                      {messages.map((m) => (
                        <button
                          key={m.id}
                          onClick={() => setActiveMessageId(m.id)}
                          className={cn(
                            "w-full text-left p-3 rounded-xl border border-border/40 transition-all space-y-1 block",
                            activeMessageId === m.id ? "bg-primary/20 border-primary" : "hover:bg-muted/10"
                          )}
                        >
                          <div className="flex justify-between items-start text-xs font-semibold text-foreground">
                            <span>{m.sender}</span>
                            <span className={cn(
                              "px-1.5 py-0.5 rounded text-[8px]",
                              m.isReplied ? "bg-green-500/10 text-green-500" : "bg-yellow-500/10 text-yellow-500"
                            )}>{m.isReplied ? "Replied" : "New"}</span>
                          </div>
                          <div className="text-xs font-bold text-white truncate">{m.subject}</div>
                        </button>
                      ))}
                    </div>

                    {/* Chat Reader */}
                    <div className="md:col-span-2 space-y-4">
                      {(() => {
                        const msg = messages.find(m => m.id === activeMessageId);
                        if (!msg) return <div className="text-center py-10 text-xs text-muted-foreground">Select a message from the list.</div>;
                        return (
                          <div className="space-y-4">
                            <div className="border-b border-border/50 pb-3">
                              <div className="text-xs text-muted-foreground uppercase font-semibold">{msg.type} &bull; Received {msg.date}</div>
                              <h4 className="font-bold text-base text-foreground mt-0.5">{msg.subject}</h4>
                            </div>
                            <div className="p-4 bg-muted/20 border border-border/50 rounded-xl text-xs text-foreground">
                              {msg.content}
                            </div>
                            {msg.isReplied && (
                              <div className="p-4 bg-primary/5 border border-primary/20 rounded-xl text-xs text-foreground space-y-1">
                                <div className="font-bold text-primary">Your Reply:</div>
                                <p>{msg.replyText}</p>
                              </div>
                            )}
                            {!msg.isReplied && (
                              <form onSubmit={handleReplyMessage} className="space-y-2">
                                <textarea
                                  required
                                  rows={3}
                                  value={replyText}
                                  onChange={(e) => setReplyText(e.target.value)}
                                  placeholder="Type your reply message..."
                                  className="w-full px-3 py-2 rounded-xl glass border border-border/50 text-xs focus:outline-none focus:border-primary bg-card"
                                />
                                <button type="submit" className="px-4 py-2 bg-primary text-white text-xs font-semibold rounded-xl">Send Reply</button>
                              </form>
                            )}
                          </div>
                        );
                      })()}
                    </div>
                  </div>
                </div>
              )}

              {/* === SELLER PAYOUTS === */}
              {activeTab === "seller-payouts" && (
                <div className="glass border border-border/40 rounded-2xl p-6 sm:p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Earnings Payout Setup</h3>
                    <p className="text-sm text-muted-foreground">Review your earnings, request a withdrawal, and manage your payout method.</p>
                  </div>

                  <div className="relative overflow-hidden rounded-2xl border border-primary/25 bg-gradient-to-br from-primary/20 via-card from-[#c89666] to-[#b5804f]/10 p-6 sm:p-8">
                    <div className="absolute -right-12 -top-16 h-48 w-48 rounded-full bg-primary/10 blur-3xl" />
                    <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">Available to withdraw</p>
                        <p className="mt-2 text-4xl font-black tracking-tight text-foreground sm:text-5xl">{formatPrice(earningsSummary.available_balance)}</p>
                        <p className="mt-2 text-sm text-muted-foreground">Your cleared seller earnings, ready for a payout request.</p>
                      </div>
                      <div className="flex gap-6 border-t border-border/40 pt-4 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0">
                        <div><p className="text-xs text-muted-foreground">Pending</p><p className="mt-1 font-bold text-foreground">{formatPrice(earningsSummary.pending_withdrawal || 0)}</p></div>
                        <div><p className="text-xs text-muted-foreground">Paid out</p><p className="mt-1 font-bold text-foreground">{formatPrice(earningsSummary.withdrawn_amount || 0)}</p></div>
                      </div>
                    </div>
                  </div>

                  <div className="seller-payout-layout">
                    <section className="seller-payout-card rounded-2xl border border-border/50 bg-muted/5">
                      <div className="seller-payout-card-heading">
                        <h4 className="font-bold text-base text-foreground">Request a withdrawal</h4>
                        <p className="mt-1 text-sm text-muted-foreground">Choose how much of your available balance you want to withdraw.</p>
                      </div>
                      <div className="seller-payout-withdraw-controls">
                        <div className="seller-payout-amount-field">
                          <label className="block text-xs font-semibold text-muted-foreground uppercase">Withdrawal amount</label>
                          <div className="seller-payout-amount-input-wrap">
                            <span className="seller-payout-currency">$</span>
                            <input
                              type="number"
                              step="0.01"
                              min="0.01"
                              max={earningsSummary.available_balance}
                              value={withdrawAmount}
                              onChange={(e) => setWithdrawAmount(e.target.value)}
                              placeholder="0.00"
                              className="seller-payout-amount-input rounded-xl border border-border/50 bg-card text-lg font-semibold text-foreground focus:border-primary focus:outline-none"
                            />
                          </div>
                          <p className="text-xs text-muted-foreground">Maximum: {formatPrice(earningsSummary.available_balance)}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            if (!withdrawAmount) { alert("Please enter a withdrawal amount."); return; }
                            const amt = parseFloat(withdrawAmount);
                            if (isNaN(amt) || amt <= 0) { alert("Please enter a valid amount."); return; }
                            if (amt > earningsSummary.available_balance) { alert(`Insufficient balance. You only have ${formatPrice(earningsSummary.available_balance)} available.`); return; }
                            const bName = (payoutBankName || user?.payout_bank_name || "").trim();
                            const aNum = (payoutAccountNumber || user?.payout_account_number || "").trim();
                            const iCode = (payoutIfscCode || user?.payout_ifsc_code || "").trim();
                            const hName = (payoutAccountHolderName || user?.payout_account_holder_name || "").trim();
                            if (!bName || !aNum || !iCode || !hName) { alert("Add your payout bank details before requesting a withdrawal."); return; }
                            createWithdrawal.mutate({ amount: amt, bank_name: bName, account_number: aNum, ifsc_code: iCode, account_holder_name: hName });
                          }}
                          disabled={createWithdrawal.isPending || earningsSummary.available_balance <= 0}
                          className="seller-payout-withdraw-button rounded-xl bg-primary text-sm font-bold text-white transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {createWithdrawal.isPending ? <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" />Submitting...</span> : "Withdraw funds"}
                        </button>
                      </div>
                    </section>

                    {(() => {
                      const hasPayoutDetails = Boolean(user?.is_payout_setup_completed && user?.payout_bank_name && user?.payout_account_number);
                      const maskedAccount = user?.payout_account_number ? `•••• ${String(user.payout_account_number).slice(-4)}` : "";
                      return (
                        <section className="seller-payout-card rounded-2xl border border-border/50 bg-muted/5">
                          <div className="seller-payout-method-header">
                            <div className="seller-payout-method-info">
                              <div className="rounded-xl border border-primary/20 bg-primary/10 p-2.5 text-primary"><CreditCard className="h-5 w-5" /></div>
                              <div>
                                <h4 className="font-bold text-base text-foreground">Payout bank details</h4>
                                {hasPayoutDetails && !payoutEditing ? (
                                  <p className="mt-1 text-sm text-muted-foreground">{user.payout_bank_name} <span className="px-1">·</span> {maskedAccount} <span className="px-1">·</span> {user.payout_account_holder_name}</p>
                                ) : (
                                  <p className="mt-1 text-sm text-muted-foreground">{hasPayoutDetails ? "Update the bank account used for withdrawal requests." : "Add a bank account to receive your withdrawals."}</p>
                                )}
                              </div>
                            </div>
                            {hasPayoutDetails && !payoutEditing && (
                              <div className="seller-payout-method-actions">
                                <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-3 py-1.5 text-xs font-semibold text-green-500"><ShieldCheck className="h-3.5 w-3.5" /> Setup active</span>
                                <button type="button" onClick={() => setPayoutEditing(true)} className="inline-flex items-center gap-2 rounded-lg border border-border/60 px-3 py-2 text-xs font-semibold text-foreground transition-colors hover:bg-muted/20"><Pencil className="h-3.5 w-3.5" /> Edit</button>
                              </div>
                            )}
                          </div>

                          {(!hasPayoutDetails || payoutEditing) && (
                            <form onSubmit={handleUpdatePayout} className="seller-payout-edit-form">
                              <div className="seller-payout-fields-grid">
                                <div><label className="mb-1.5 block text-xs font-semibold uppercase text-muted-foreground">Account holder name</label><input type="text" required placeholder="e.g. John Doe" value={payoutAccountHolderName} onChange={(e) => setPayoutAccountHolderName(e.target.value)} className="w-full rounded-lg border border-border/50 bg-card px-3 py-2.5 text-sm focus:border-primary focus:outline-none" /></div>
                                <div><label className="mb-1.5 block text-xs font-semibold uppercase text-muted-foreground">Bank name</label><input type="text" required placeholder="e.g. HDFC Bank" value={payoutBankName} onChange={(e) => setPayoutBankName(e.target.value)} className="w-full rounded-lg border border-border/50 bg-card px-3 py-2.5 text-sm focus:border-primary focus:outline-none" /></div>
                                <div><label className="mb-1.5 block text-xs font-semibold uppercase text-muted-foreground">Account number / IBAN</label><input type="text" required placeholder="Enter account number" value={payoutAccountNumber} onChange={(e) => setPayoutAccountNumber(e.target.value)} className="w-full rounded-lg border border-border/50 bg-card px-3 py-2.5 text-sm focus:border-primary focus:outline-none" /></div>
                                <div><label className="mb-1.5 block text-xs font-semibold uppercase text-muted-foreground">IFSC / SWIFT / routing code</label><input type="text" required placeholder="e.g. HDFC0001234" value={payoutIfscCode} onChange={(e) => setPayoutIfscCode(e.target.value)} className="w-full rounded-lg border border-border/50 bg-card px-3 py-2.5 text-sm focus:border-primary focus:outline-none" /></div>
                              </div>
                              <div className="seller-payout-form-actions">
                                <button type="submit" disabled={savingPayout} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary/90 disabled:opacity-50">{savingPayout ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving...</> : "Save payout details"}</button>
                                {hasPayoutDetails && <button type="button" onClick={() => { setPayoutAccountHolderName(user?.payout_account_holder_name || ""); setPayoutBankName(user?.payout_bank_name || ""); setPayoutAccountNumber(user?.payout_account_number || ""); setPayoutIfscCode(user?.payout_ifsc_code || ""); setPayoutEditing(false); }} className="rounded-lg border border-border/60 px-4 py-2.5 text-sm font-semibold text-foreground hover:bg-muted/20">Cancel</button>}
                              </div>
                            </form>
                          )}
                        </section>
                      );
                    })()}

                    <div className="seller-payout-stripe-connect rounded-xl border border-[#c89666]/30 bg-[#c89666]/15">
                      <div><div className="flex items-center gap-2"><span className="text-sm font-bold text-foreground">Stripe Connect</span><span className="rounded-full bg-[#c89666]/15 px-2 py-0.5 text-[10px] font-bold text-[#dfb180]">Automatic payouts</span></div><p className="mt-1 text-xs text-muted-foreground">Connect Stripe to receive automatic payouts for template sales.</p></div>
                      <button type="button" onClick={async () => { try { const res = await api.post("/payouts/stripe-connect/onboard", {}, authToken ?? undefined); if (res?.onboarding_url) window.location.href = res.onboarding_url; } catch (err) { alert("Stripe Connect onboarding error: " + (err.message || err)); } }} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-[#c89666]/15 px-4 py-2.5 text-xs font-semibold text-white transition-colors hover:bg-[#c89666]/15"><Zap className="h-4 w-4" /> Connect account</button>
                    </div>
                  </div>

                  <div className="border-t border-border/50 pt-4">
                    <h4 className="font-bold text-sm text-foreground mb-3">Withdrawal Requests History</h4>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-border/50 text-foreground font-bold">
                            <th className="pb-2.5 text-foreground font-bold">Request ID</th>
                            <th className="pb-2.5 text-foreground font-bold">Date</th>
                            <th className="pb-2.5 text-foreground font-bold">Amount</th>
                            <th className="pb-2.5 text-foreground font-bold">Method</th>
                            <th className="pb-2.5 text-foreground font-bold">Status</th>
                            <th className="pb-2.5 text-right text-foreground font-bold">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {withdrawalRequests && withdrawalRequests.length > 0 ? (
                            withdrawalRequests.map((h, idx) => (
                              <tr key={idx} className="border-b border-border/40 hover:bg-muted/10 text-foreground">
                                <td className="py-2.5 font-mono font-bold text-foreground">{h.id.slice(0, 8).toUpperCase()}</td>
                                <td className="py-2.5 text-foreground/80 font-medium">{new Date(h.created_at).toLocaleDateString()}</td>
                                <td className="py-2.5 font-mono font-bold text-foreground">{formatPrice(h.amount)}</td>
                                <td className="py-2.5 font-semibold text-foreground/90">{h.bank_name || "Bank Direct"}</td>
                                <td className="py-2.5 font-bold text-primary capitalize">{h.status}</td>
                                <td className="py-2.5 text-right">
                                  <a
                                    href={`/dashboard/payout-receipt/${h.id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center text-[11px] font-bold bg-[#c89666]/15 dark:bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30 dark:border-[#c89666]/30 px-2.5 py-1 rounded-lg hover:bg-[#c89666]/15 dark:hover:bg-[#c89666]/15 transition-all text-decoration-none shadow-sm"
                                  >
                                    View Receipt
                                  </a>
                                </td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td colSpan={6} className="py-4 text-center text-muted-foreground text-xs">
                                No withdrawal requests found.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* === ADMIN USERS LEDGER === */}

              {activeTab === "admin-users" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Platform Users Management</h3>
                    <p className="text-sm text-muted-foreground">Change roles or toggle user suspension status.</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/50 text-muted-foreground font-bold uppercase">
                          <th className="pb-2">Name</th>
                          <th className="pb-2">Email</th>
                          <th className="pb-2">Role</th>
                          <th className="pb-2">Status</th>
                          <th className="pb-2 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminUsers.map((u) => (
                          <tr key={u.id} className="border-b border-border/40 hover:bg-muted/5">
                            <td className="py-2.5 font-bold text-foreground">{u.name}</td>
                            <td className="py-2.5 select-all">{u.email}</td>
                            <td className="py-2.5">
                              <select
                                value={u.role}
                                onChange={async (e) => {
                                  const newRole = e.target.value;
                                  try {
                                    const res = await fetch(`${API_BASE}/admin/users/${u.id}`, {
                                      method: "PATCH",
                                      headers: {
                                        "Content-Type": "application/json",
                                        "Authorization": `Bearer ${authToken}`
                                      },
                                      body: JSON.stringify({
                                        role: newRole
                                      })
                                    });
                                    if (res.ok) {
                                      setAdminUsers(adminUsers.map(x => x.id === u.id ? { ...x, role: newRole } : x));
                                    }
                                  } catch (err) {
                                    console.error("Failed to update role", err);
                                  }
                                }}
                                className="px-1.5 py-0.5 rounded border border-border bg-card text-xs font-semibold uppercase text-primary cursor-pointer focus:outline-none"
                              >
                                <option value="buyer">buyer</option>
                                <option value="seller">seller</option>
                                <option value="admin">admin</option>
                              </select>
                            </td>
                            <td className="py-2.5">
                              <span className={cn(
                                "px-1.5 py-0.5 rounded text-[8px] font-bold uppercase",
                                u.status === "Active" ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"
                              )}>{u.status}</span>
                            </td>
                            <td className="py-2.5 text-right" style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                              <button
                                onClick={async () => {
                                  const newStatus = u.status === "Active" ? "Suspended" : "Active";
                                  try {
                                    const res = await fetch(`${API_BASE}/admin/users/${u.id}`, {
                                      method: "PATCH",
                                      headers: {
                                        "Content-Type": "application/json",
                                        "Authorization": `Bearer ${authToken}`
                                      },
                                      body: JSON.stringify({
                                        is_active: newStatus === "Active"
                                      })
                                    });
                                    if (res.ok) {
                                      setAdminUsers(adminUsers.map(x => x.id === u.id ? { ...x, status: newStatus } : x));
                                    }
                                  } catch (err) {
                                    console.error("Failed to toggle block", err);
                                  }
                                }}
                                className="text-xs text-primary font-bold hover:underline"
                              >
                                Toggle Block
                              </button>
                              <button
                                onClick={async () => {
                                  if (!window.confirm(`Are you sure you want to permanently delete user ${u.name || u.email}? This action is irreversible.`)) return;
                                  try {
                                    const res = await fetch(`${API_BASE}/admin/users/${u.id}`, {
                                      method: "DELETE",
                                      headers: {
                                        "Authorization": `Bearer ${authToken}`
                                      }
                                    });
                                    if (res.ok) {
                                      setAdminUsers(adminUsers.filter(x => x.id !== u.id));
                                      alert("User account permanently deleted!");
                                    } else {
                                      const errData = await res.json();
                                      alert(errData.detail || "Failed to delete user");
                                    }
                                  } catch (err) {
                                    console.error("Failed to delete user", err);
                                    alert("Error deleting user account");
                                  }
                                }}
                                className="text-xs text-red-500 font-bold hover:underline"
                              >
                                Delete
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* === ADMIN PAYMENTS === */}

              {/* === ADMIN PAYMENTS & INVOICES === */}
              {activeTab === "admin-payments" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                      <h3 className="font-bold text-lg flex items-center gap-2">
                        <FileText className="w-5 h-5 text-primary" />
                        Invoices & Payments Audit Ledger
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        Global platform ledger of unique official tax invoices, purchases, and commission fees.
                      </p>
                    </div>

                    {/* Quick Search */}
                    <div className="relative min-w-[280px]">
                      <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                      <input
                        type="text"
                        placeholder="Search by Inv #, Buyer, Email..."
                        value={adminInvoiceSearch}
                        onChange={(e) => setAdminInvoiceSearch(e.target.value)}
                        className="w-full pl-9 pr-4 py-2 text-xs rounded-xl bg-muted/40 border border-border/50 focus:outline-none focus:border-primary text-foreground placeholder:text-muted-foreground"
                      />
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/50 text-muted-foreground font-bold uppercase">
                          <th className="pb-3">Invoice #</th>
                          <th className="pb-3">Date</th>
                          <th className="pb-3">Buyer</th>
                          <th className="pb-3">Purchased Items</th>
                          <th className="pb-3">Gross Total</th>
                          <th className="pb-3">Commission (20%)</th>
                          <th className="pb-3">Status</th>
                          <th className="pb-3 text-right">Official Invoice</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminOrdersLoading ? (
                          <tr>
                            <td colSpan={8} className="py-8 text-center text-muted-foreground">
                              <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                            </td>
                          </tr>
                        ) : filteredAdminOrders.length === 0 ? (
                          <tr>
                            <td colSpan={8} className="py-8 text-center text-muted-foreground">
                              {adminInvoiceSearch ? "No matching invoices found." : "No payments or invoices found in ledger."}
                            </td>
                          </tr>
                        ) : (
                          filteredAdminOrders.map((ord) => {
                            const invNum = ord.invoice_number || ord.order_number || `INV-${String(ord.id).slice(0, 8).toUpperCase()}`;
                            const isPaid = (ord.status || "").toLowerCase() === "completed";
                            return (
                              <tr key={ord.id} className="border-b border-border/40 hover:bg-muted/5 transition-colors">
                                <td className="py-3 font-mono font-bold text-foreground">
                                  {invNum}
                                </td>
                                <td className="py-3 text-muted-foreground whitespace-nowrap">
                                  {ord.created_at ? new Date(ord.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "N/A"}
                                </td>
                                <td className="py-3">
                                  <div className="font-semibold text-foreground">{ord.buyer_name || "Customer"}</div>
                                  <div className="text-[11px] text-muted-foreground select-all">{ord.buyer_email}</div>
                                </td>
                                <td className="py-3 truncate max-w-[160px]" title={Array.isArray(ord.items) ? ord.items.join(", ") : ord.items}>
                                  {Array.isArray(ord.items) ? (ord.items.join(", ") || "Template Package") : (ord.items || "Package")}
                                </td>
                                <td className="py-3 font-bold text-foreground">
                                  {formatPrice(ord.total)}
                                </td>
                                <td className="py-3 text-yellow-500 font-semibold">
                                  {formatPrice(ord.total * 0.20)}
                                </td>
                                <td className="py-3">
                                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${isPaid ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20" : "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                                    }`}>
                                    {isPaid ? "PAID" : String(ord.status).toUpperCase()}
                                  </span>
                                </td>
                                <td className="py-3 text-right">
                                  <div className="flex items-center justify-end gap-1.5">
                                    <a
                                      href={`/dashboard/receipt/${ord.id}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-[#c89666]/15 hover:bg-[#c89666]/15 text-[#dfb180] border border-[#c89666]/30 inline-flex items-center gap-1 transition-all text-decoration-none shadow-sm cursor-pointer"
                                      title="Inspect official tax invoice & proof of purchase"
                                    >
                                      <FileText className="w-3 h-3" />
                                      <span>Tax Invoice</span>
                                    </a>
                                    <a
                                      href={`/dashboard/receipt/${ord.id}?download=pdf`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="px-2 py-1 rounded-lg text-[11px] font-bold bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 inline-flex items-center gap-1 transition-all text-decoration-none shadow-sm cursor-pointer"
                                      title="Download invoice PDF"
                                    >
                                      <Download className="w-3 h-3" />
                                      <span>PDF</span>
                                    </a>
                                  </div>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* === ADMIN CATEGORIES === */}
              {activeTab === "admin-categories" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Category Mapping Configuration</h3>
                    <p className="text-sm text-muted-foreground">Define catalog filters for the marketplace.</p>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs text-muted-foreground">Create and edit marketplace categories in the admin console.</p>
                    <a href="/admin" className="py-2.5 px-4 bg-primary text-white text-xs font-semibold rounded-lg inline-flex items-center justify-center gap-1">
                      <Plus className="w-3.5 h-3.5" /> Open Category Manager
                    </a>
                  </div>
                  <div className="border-t border-border/50 pt-4">
                    <div className="flex flex-wrap gap-2">
                      {categories.map((c) => (
                        <span key={c.id} className="px-3 py-1 bg-muted rounded-full text-xs font-semibold text-foreground">
                          {c.name}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* === ADMIN REPORTS (INCIDENT RESOLUTION CENTER & AI SITE DOCTOR) === */}
              {activeTab === "admin-reports" && (
                <AdminIncidentsCenter
                  authToken={authToken}
                  onOpenCodeStudio={(deploy, incident) => openCodeStudio(deploy, incident)}
                />
              )}

              {/* === ADMIN REVENUE === */}
              {activeTab === "admin-revenue" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Global Platform Revenue Splits</h3>
                    <p className="text-sm text-muted-foreground">Earnings overview across buyer checkouts.</p>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="p-4 border border-border/50 rounded-xl space-y-1 bg-muted/10">
                      <div className="text-[10px] text-muted-foreground font-semibold uppercase">Gross Revenue</div>
                      <div className="text-2xl font-bold text-foreground">{formatPrice(stats?.gross_revenue ?? 0)}</div>
                    </div>
                    <div className="p-4 border border-border/50 rounded-xl space-y-1 bg-muted/10">
                      <div className="text-[10px] text-muted-foreground font-semibold uppercase">Platform Fee (20% Split)</div>
                      <div className="text-2xl font-bold text-yellow-500">{formatPrice(stats?.commission_revenue ?? 0)}</div>
                    </div>
                    <div className="p-4 border border-border/50 rounded-xl space-y-1 bg-muted/10">
                      <div className="text-[10px] text-muted-foreground font-semibold uppercase">Net Creator Payouts</div>
                      <div className="text-2xl font-bold text-green-500">{formatPrice(stats?.net_seller_revenue ?? 0)}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* === ADMIN MODERATION === */}
              {activeTab === "admin-moderation" && (
                <AdminModerationHub
                  adminTemplates={adminTemplates}
                  isLoading={adminTemplatesLoading}
                  onUpdateStatus={async (templateId, status) => {
                    await adminUpdateTemplateStatusMutation.mutateAsync({ templateId, status });
                  }}
                  onDeleteTemplate={async (templateId) => {
                    await adminDeleteTemplateMutation.mutateAsync(templateId);
                  }}
                  onBatchUpdateStatus={async (templateIds, status) => {
                    await batchUpdateTemplateStatusMutation.mutateAsync({ templateIds, status });
                  }}
                  onRefresh={() => {
                    qc.invalidateQueries(["admin-all-templates"]);
                  }}
                  formatPrice={formatPrice}
                />
              )}

              {/* === PROFILE & SETTINGS === */}
              {activeTab === "settings" && (
                <div className="db-settings-grid">
                  <div className="db-settings-info">
                    <h3 className="db-section-title">Profile &amp; Settings Details</h3>
                    <p className="db-section-subtitle">
                      Update your account details and profile information.
                    </p>
                  </div>
                  <div className="db-settings-form-panel">
                    <form onSubmit={handleUpdateProfile} className="db-settings-form">
                      {/* Avatar Upload */}
                      <div className="flex flex-col sm:flex-row items-center gap-5 p-4 rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 mb-2">
                        <div className="relative w-16 h-16 rounded-full overflow-hidden bg-[#c89666]/15 dark:bg-[#c89666]/15 border-2 border-[#c89666]/30 dark:border-[#c89666]/30 flex items-center justify-center shrink-0 shadow-sm">
                          {avatarUrl ? (
                            <img src={resolveMediaUrl(avatarUrl)} alt="Avatar" className="w-full h-full object-cover" />
                          ) : (
                            <span className="text-xl font-extrabold text-[#dfb180] dark:text-[#dfb180]">
                              {fullName?.[0] || username?.[0] || "?"}
                            </span>
                          )}
                          {uploadingAvatar && (
                            <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                              <Loader2 className="w-4 h-4 animate-spin text-white" />
                            </div>
                          )}
                        </div>
                        <div className="space-y-2 text-center sm:text-left">
                          <label className="text-xs font-extrabold text-slate-800 dark:text-slate-200 block uppercase tracking-wider">Profile Picture</label>
                          <input
                            type="file"
                            accept="image/*"
                            onChange={handleAvatarUpload}
                            className="hidden"
                            id="avatar-upload-input"
                            disabled={uploadingAvatar}
                          />
                          <div className="flex gap-2 justify-center sm:justify-start">
                            <label
                              htmlFor="avatar-upload-input"
                              className="cursor-pointer px-4 py-1.5 bg-[#c89666]/15 dark:bg-[#c89666]/15 hover:bg-[#c89666]/15 dark:hover:bg-[#c89666]/15 border border-[#c89666]/30 dark:border-[#c89666]/30 text-[#dfb180] text-xs font-extrabold rounded-xl transition-all shadow-sm"
                            >
                              Upload Image
                            </label>
                            {avatarUrl && (
                              <button
                                type="button"
                                onClick={() => setAvatarUrl("")}
                                className="px-4 py-1.5 bg-red-50 dark:bg-red-950/40 hover:bg-red-100 border border-red-200 dark:border-red-800/50 text-red-600 dark:text-red-400 text-xs font-extrabold rounded-xl transition-all shadow-sm cursor-pointer"
                              >
                                Remove
                              </button>
                            )}
                          </div>
                          <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium block">
                            Supports JPG, PNG or WEBP. File size is subject to hosting limits.
                          </span>
                        </div>
                      </div>

                      <div className="db-form-group space-y-1">
                        <label className="db-form-label text-slate-700 dark:text-slate-300 font-extrabold text-xs tracking-wider uppercase">Email Address (Read Only)</label>
                        <input
                          type="email"
                          value={user?.email ?? ""}
                          readOnly
                          className="db-form-input bg-slate-100 dark:bg-slate-800 text-slate-500 font-bold border-2 border-slate-200 dark:border-slate-700 cursor-not-allowed"
                        />
                      </div>
                      <div className="db-form-group space-y-1">
                        <label className="db-form-label text-slate-700 dark:text-slate-300 font-extrabold text-xs tracking-wider uppercase">Full Name</label>
                        <input
                          type="text"
                          value={fullName}
                          onChange={(e) => setFullName(e.target.value)}
                          className="db-form-input bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white font-bold rounded-xl focus:border-[#c89666]/30 shadow-sm"
                          placeholder="Navin Bharath"
                        />
                      </div>
                      <div className="db-form-group space-y-1">
                        <label className="db-form-label text-slate-700 dark:text-slate-300 font-extrabold text-xs tracking-wider uppercase">Username</label>
                        <input
                          type="text"
                          value={username}
                          onChange={(e) => setUsername(e.target.value)}
                          className="db-form-input bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white font-bold rounded-xl focus:border-[#c89666]/30 shadow-sm"
                          placeholder="navin"
                        />
                      </div>
                      <div className="db-form-group space-y-1">
                        <label className="db-form-label text-slate-700 dark:text-slate-300 font-extrabold text-xs tracking-wider uppercase">Bio</label>
                        <textarea
                          value={bio}
                          onChange={(e) => setBio(e.target.value)}
                          className="db-form-input db-form-textarea bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white font-semibold rounded-xl focus:border-[#c89666]/30 shadow-sm"
                          placeholder="Tell us about yourself..."
                        />
                      </div>

                      {/* Theme & Appearance Preference */}
                      <div className="p-5 rounded-2xl border border-border bg-card shadow-xs space-y-3 mb-6 mt-4">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0 shadow-sm text-primary">
                              <Palette className="w-5 h-5" />
                            </div>
                            <div>
                              <h4 className="text-sm font-extrabold text-foreground">Theme &amp; Appearance</h4>
                              <p className="text-xs text-muted-foreground font-medium">Switch between Light, Dark, or System theme with seamless persistence.</p>
                            </div>
                          </div>
                          <ThemeToggle variant="pill" />
                        </div>
                      </div>

                      {/* Location & Viewing Currency Preferences */}
                      <div className="p-5 rounded-2xl border-2 border-[#c89666]/30 dark:border-[#c89666]/30 bg-[#c89666]/15 dark:bg-[#c89666]/15 space-y-4 mb-6 mt-4 shadow-sm">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#c89666]/30 dark:border-[#c89666]/30 pb-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-2xl bg-[#c89666]/15 dark:bg-[#c89666]/15 border border-[#c89666]/30 dark:border-[#c89666]/30 flex items-center justify-center shrink-0 shadow-sm text-[#dfb180] dark:text-[#dfb180]">
                              <Globe className="w-5 h-5" />
                            </div>
                            <div>
                              <h4 className="text-sm font-extrabold text-slate-900 dark:text-white">Location & Preferred Currency</h4>
                              <p className="text-xs text-slate-600 dark:text-slate-400 font-medium">Auto-converts marketplace pricing and sets up template upload currency.</p>
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={async () => {
                              try {
                                setDetectingLocation(true);
                                const updated = await useAuthStore.getState().detectLocation();
                                if (updated) {
                                  setUserCountry(updated.country || "");
                                  setUserCity(updated.city || "");
                                  setUserCurrencyPref(updated.currency || "USD");
                                  useCurrencyStore.getState().setUserCurrency(updated.currency || "USD");
                                }
                              } catch (err) {
                                console.warn("Location auto-detection notice:", err);
                              } finally {
                                setDetectingLocation(false);
                              }
                            }}
                            disabled={detectingLocation}
                            className="px-4 py-2.5 rounded-xl bg-[#c89666]/15 hover:bg-[#c89666]/25 text-white text-xs font-extrabold flex items-center justify-center gap-2 transition-all cursor-pointer shadow-xs border border-[#c89666]/40 shrink-0"
                          >
                            {detectingLocation ? <Loader2 className="w-4 h-4 animate-spin" /> : <Globe className="w-4 h-4 text-[#dfb180]" />}
                            Auto-Detect Location
                          </button>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
                          <div className="space-y-1">
                            <label className="db-form-label text-slate-700 dark:text-slate-300 font-extrabold text-xs uppercase tracking-wider">Country</label>
                            <input
                              type="text"
                              value={userCountry}
                              onChange={(e) => setUserCountry(e.target.value)}
                              className="db-form-input text-xs font-bold bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white rounded-xl"
                              placeholder="e.g. India, United States"
                            />
                          </div>
                          <div className="space-y-1">
                            <label className="db-form-label text-slate-700 dark:text-slate-300 font-extrabold text-xs uppercase tracking-wider">City</label>
                            <input
                              type="text"
                              value={userCity}
                              onChange={(e) => setUserCity(e.target.value)}
                              className="db-form-input text-xs font-bold bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white rounded-xl"
                              placeholder="e.g. Coimbatore, New York"
                            />
                          </div>
                          <div className="space-y-1">
                            <label className="db-form-label text-slate-700 dark:text-slate-300 font-extrabold text-xs uppercase tracking-wider">Viewing &amp; Upload Currency</label>
                            <select
                              value={userCurrencyPref}
                              onChange={(e) => {
                                setUserCurrencyPref(e.target.value);
                                useCurrencyStore.getState().setUserCurrency(e.target.value);
                              }}
                              className="db-form-input text-xs font-extrabold bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white rounded-xl cursor-pointer"
                            >
                              <option value="USD" style={{ backgroundColor: "#ffffff", color: "#0f172a" }}>USD ($)</option>
                              <option value="INR" style={{ backgroundColor: "#ffffff", color: "#0f172a" }}>INR (₹)</option>
                              <option value="EUR" style={{ backgroundColor: "#ffffff", color: "#0f172a" }}>EUR (€)</option>
                              <option value="GBP" style={{ backgroundColor: "#ffffff", color: "#0f172a" }}>GBP (£)</option>
                              <option value="CAD" style={{ backgroundColor: "#ffffff", color: "#0f172a" }}>CAD (CA$)</option>
                              <option value="AUD" style={{ backgroundColor: "#ffffff", color: "#0f172a" }}>AUD (A$)</option>
                              <option value="JPY" style={{ backgroundColor: "#ffffff", color: "#0f172a" }}>JPY (¥)</option>
                              <option value="AED" style={{ backgroundColor: "#ffffff", color: "#0f172a" }}>AED (AED)</option>
                            </select>
                          </div>
                        </div>
                      </div>

                      <button
                        type="submit"
                        disabled={savingProfile}
                        className="px-5 py-2.5 bg-[#c89666]/20 hover:bg-[#c89666]/30 text-white font-extrabold text-xs rounded-xl transition-all shadow-xs border border-[#c89666]/40 cursor-pointer inline-flex items-center justify-center gap-1.5"
                      >
                        {savingProfile && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                        {savingProfile ? "Saving..." : "Save Changes"}
                      </button>
                    </form>
                  </div>
                </div>
              )}

              {/* === DEPLOY PROJECT WIZARD MODAL (WEBSITE ADDER) === */}
              {isDeployModalOpen && (
                <div className="modal-backdrop-solid">
                  <div className="modal-content-opaque space-y-5 text-white">
                    <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-[#c89666] via-[#dfb180] to-[#c89666]" />
                    <div className="flex justify-between items-center border-b border-[#27272a] pb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-2xl bg-[#c89666]/15 border border-[#c89666]/35 flex items-center justify-center shadow-sm">
                          <Zap className="w-5 h-5 text-[#dfb180]" />
                        </div>
                        <div>
                          <h3 className="font-extrabold text-xl text-white">Deploy &amp; Publish Website</h3>
                          <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2.5 py-0.5 rounded-full font-extrabold border border-emerald-500/30 uppercase tracking-wider inline-flex items-center gap-1.5 mt-0.5">
                            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                            Studio Cloud Edge
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setIsDeployModalOpen(false)}
                        className="w-9 h-9 rounded-full bg-[#18181d] hover:bg-[#25252d] text-[#a8a29e] hover:text-white transition-all flex items-center justify-center border border-[#27272a] cursor-pointer shadow-sm"
                        title="Close Modal"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    <form
                      onSubmit={async (e) => {
                        e.preventDefault();
                        setDeploying(true);
                        try {
                          const payload = {
                            project_name: deployProjectName,
                            provider: deployProvider,
                            template_id: deployTemplateId === "mock-project-id" ? null : deployTemplateId,
                            branch: deployBranch,
                            build_command: deployBuildCommand,
                            output_dir: deployOutputDir,
                            accepted_hosting_terms: acceptedHostingTerms,
                          };
                          const res = await api.post("/deployments/", payload, authToken ?? undefined);

                          if (deployProvider === "local" && hostingPrice?.configured) {
                            const checkout = await api.post(`/deployments/${res.id}/hosting-checkout`, {}, authToken ?? undefined);
                            window.location.assign(checkout.checkout_url);
                            return;
                          }

                          // If custom domain entered, link it immediately
                          refetchDeployments();
                          setIsDeployModalOpen(false);
                          setDeploying(false);
                          // Reset wizard state
                          setDeployProjectName("");
                          setCustomDomainInput("");
                          setAcceptedHostingTerms(false);
                          setDeployBranch("main");
                          setDeployBuildCommand("npm run build");
                          setDeployOutputDir("dist");

                          // Open live build console for the new deployment
                          setSelectedDeployment(res);
                          setActiveConsoleLogs(res.logs || "");
                          setActiveConsoleStatus("building");
                          setIsConsoleOpen(true);
                        } catch (err) {
                          setDeploying(false);
                          alert("Deployment failed: " + err.message);
                        }
                      }}
                      className="space-y-4"
                    >
                      <div className="space-y-1.5">
                        <label className="modal-label-solid">Select Template / Project *</label>
                        <select
                          value={deployTemplateId}
                          onChange={(e) => {
                            const val = e.target.value;
                            setDeployTemplateId(val);
                            if (val === "mock-project-id") {
                              setDeployProjectName("Restaurant Demo Prototype");
                            } else {
                              const matched = availableTemplatesForDeployment.find(t => t.id === val);
                              if (matched) setDeployProjectName(matched.title);
                            }
                          }}
                          className="modal-select-solid"
                          required
                        >
                          {/* Studio & Custom Draft Projects */}
                          {studioList.length > 0 && (
                            <optgroup label="✨ Studio &amp; Custom Projects" style={{ backgroundColor: "#121216", color: "#dfb180" }}>
                              {studioList.map(t => (
                                <option key={t.id} value={t.id} style={{ backgroundColor: "#09090b", color: "#ffffff" }}>
                                  {t.title} ({t.framework || "HTML"}) — [Studio Project]
                                </option>
                              ))}
                            </optgroup>
                          )}

                          {/* Seller Uploaded Marketplace Templates */}
                          {uploadedList.length > 0 && (
                            <optgroup label="📦 My Uploaded Marketplace Templates" style={{ backgroundColor: "#121216", color: "#c89666" }}>
                              {uploadedList.map(t => (
                                <option key={t.id} value={t.id} style={{ backgroundColor: "#09090b", color: "#ffffff" }}>
                                  {t.title} ({t.framework || "HTML"}) — [Uploaded Template]
                                </option>
                              ))}
                            </optgroup>
                          )}

                          {/* Downloaded & Purchased Templates */}
                          {downloadedList.length > 0 && (
                            <optgroup label="📥 Downloaded &amp; Purchased Templates" style={{ backgroundColor: "#121216", color: "#34d399" }}>
                              {downloadedList.map(t => (
                                <option key={t.id} value={t.id} style={{ backgroundColor: "#09090b", color: "#ffffff" }}>
                                  {t.title} ({t.framework || "HTML"}) — [Downloaded Template]
                                </option>
                              ))}
                            </optgroup>
                          )}

                          {availableTemplatesForDeployment.length === 0 && (
                            <option value="" disabled style={{ backgroundColor: "#121216", color: "#71717a" }}>
                              -- No templates or projects found --
                            </option>
                          )}
                        </select>
                        {availableTemplatesForDeployment.length === 0 && (
                          <div className="p-3 bg-[#18181d] border border-[#33333a] rounded-xl flex items-center justify-between text-xs text-[#dfb180]">
                            <span>You have not downloaded any templates yet.</span>
                            <Link to="/marketplace" className="px-3 py-1.5 bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] font-black rounded-lg text-[11px] text-decoration-none shadow-sm">
                              Browse Marketplace
                            </Link>
                          </div>
                        )}
                      </div>

                      <div className="space-y-1.5">
                        <label className="modal-label-solid" htmlFor="deployment-provider">Hosting provider</label>
                        <select id="deployment-provider" value={deployProvider} onChange={(e) => setDeployProvider(e.target.value)} className="modal-select-solid">
                          {(deploymentProviderData?.providers || []).map((provider) => (
                            <option key={provider.id} value={provider.id} disabled={!provider.enabled}>{provider.label}{provider.enabled ? "" : " (not configured)"}</option>
                          ))}
                        </select>
                        <span className="text-xs text-[#a8a29e] block leading-relaxed font-medium">
                          {deployProvider === "vercel" ? "Uploads your project source to the configured Vercel account for a remote build and deployment." : "Runs the project build on this backend and serves files from its local edge storage with instant preview."}
                        </span>
                        {deploymentProviderData && !deploymentProviderData.providers?.some((provider) => provider.enabled) && (
                          <span className="text-xs text-rose-400 block font-semibold">No deployment provider is configured. Ask the platform administrator to configure Vercel or trusted local hosting.</span>
                        )}
                      </div>

                      <div className="space-y-1.5">
                        <label className="modal-label-solid">Project Display Name *</label>
                        <input
                          type="text"
                          value={deployProjectName}
                          onChange={(e) => setDeployProjectName(e.target.value)}
                          placeholder="e.g. My Portfolio Website"
                          className="modal-input-solid"
                          required
                        />
                      </div>

                      <div className="p-3.5 bg-[#141418] border border-[#27272a] rounded-xl space-y-1.5">
                        <div className="flex items-center gap-2 text-xs font-bold text-white uppercase tracking-wider">
                          <Globe className="w-4 h-4 text-[#dfb180]" /> Hosting Architecture
                        </div>
                        <p className="text-xs text-[#a8a29e] leading-relaxed">
                          {deployProvider === "vercel" ? "Vercel installs dependencies, builds the project, and supplies the deployment URL." : "The website is deployed to the high-performance local Edge tier with sub-millisecond response rates and zero downtime."}
                        </p>
                      </div>

                      <div className="flex justify-end gap-3 pt-3 border-t border-[#27272a]">
                        <button
                          type="button"
                          onClick={() => setIsDeployModalOpen(false)}
                          className="px-5 py-2.5 bg-[#18181d] hover:bg-[#222228] text-white text-xs font-bold rounded-xl transition-all cursor-pointer border border-[#27272a] shadow-sm"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={deploying || !deploymentProviderData?.providers?.some((provider) => provider.id === deployProvider && provider.enabled)}
                          className="px-6 py-2.5 bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] text-xs font-black rounded-xl transition-all disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-[#c89666]/20 border border-[#c89666]/40 cursor-pointer"
                        >
                          {deploying && <Loader2 className="w-4 h-4 animate-spin text-[#09090b]" />}
                          <span>{deploying ? "Deploying Site..." : "Publish Website"}</span>
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              )}

              {/* === BUILD & LIVE RUNTIME LOGS CONSOLE MODAL === */}
              {isConsoleOpen && selectedDeployment && (() => {
                const isBuilding = activeConsoleStatus === "building" || activeConsoleStatus === "queued" || activeConsoleStatus === "created";
                const isSuccess = activeConsoleStatus === "live" || activeConsoleStatus === "success" || activeConsoleStatus === "ready" || activeConsoleLogs.includes("[SUCCESS]");

                // Parse all log lines
                const allLines = activeConsoleLogs.split("\n").filter(l => l.trim().length > 0);
                const totalCount = allLines.length;

                // Category counts
                const errorLines = allLines.filter(l => {
                  const low = l.toLowerCase();
                  return low.includes("[error]") || low.includes("runtime error") || low.includes("failed") || low.includes("rejection") || l.startsWith("❌");
                });
                const browserLines = allLines.filter(l => l.includes("[BROWSER") || l.includes("[CLIENT BOOT]"));
                const serverLines = allLines.filter(l => l.includes("[SERVER HTTP"));

                // Filtered lines based on active filter & search
                const filteredLines = allLines.filter(line => {
                  const clean = stripAnsi(line);
                  if (consoleSearch.trim()) {
                    if (!clean.toLowerCase().includes(consoleSearch.toLowerCase().trim())) {
                      return false;
                    }
                  }
                  if (consoleFilter === "errors") {
                    const low = clean.toLowerCase();
                    return low.includes("[error]") || low.includes("runtime error") || low.includes("failed") || low.includes("rejection") || clean.startsWith("❌");
                  }
                  if (consoleFilter === "audit") {
                    return clean.includes("[AUDIT]") || clean.includes("[HEAL]") || clean.includes("[SELF-HEAL]");
                  }
                  if (consoleFilter === "browser") {
                    return clean.includes("[BROWSER") || clean.includes("[CLIENT BOOT]");
                  }
                  if (consoleFilter === "server") {
                    return clean.includes("[SERVER HTTP");
                  }
                  return true;
                });

                const lastErrorLine = errorLines.length > 0 ? errorLines[errorLines.length - 1] : null;
                const displayError = lastErrorLine ? stripAnsi(lastErrorLine).replace(/^\[.*?\]\s*\[ERROR\]\s*/, '') : "Runtime error detected on live website.";

                const liveTargetUrl = selectedDeployment?.live_url
                  || (selectedDeployment?.site_id ? `${BACKEND_BASE}/sites/${selectedDeployment.site_id}/` : null)
                  || (selectedDeployment?.custom_domain ? `http://${selectedDeployment.custom_domain}` : null);

                // Quick AI Auto-Heal Handler
                const handleQuickAutoHeal = async () => {
                  if (isAutoFixingFromConsole) return;
                  setIsAutoFixingFromConsole(true);
                  try {
                    const res = await api.post(
                      `/incidents/deployments/${selectedDeployment.id}/auto-fix`,
                      {
                        issue_description: `Runtime console error: ${displayError}`,
                        error_logs: activeConsoleLogs.slice(-2000),
                        page_url: liveTargetUrl,
                      },
                      authToken ?? undefined
                    );
                    alert(`⚡ Auto-Heal healed the website successfully!\n${res.diagnosis || res.message || 'Patches deployed live.'}`);
                    refetchDeployments();
                  } catch (err) {
                    openCodeStudio(selectedDeployment);
                  } finally {
                    setIsAutoFixingFromConsole(false);
                  }
                };

                return (
                  <div className="modal-backdrop bg-black/80 backdrop-blur-md">
                    <div className="modal-content large bg-[#121216] border border-[#c89666]/30 p-6 rounded-2xl space-y-4 shadow-2xl shadow-black text-white max-w-4xl w-full">
                      {/* Modal Header */}
                      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-[#27272a] pb-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-bold text-lg text-white">Live Website Telemetry &amp; Console</h3>
                            {isSuccess && (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                                LIVE RUNTIME STREAM
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-[#a8a29e] mt-0.5">
                            Project: <strong className="text-white">{selectedDeployment.project_name}</strong> &bull; Site ID: <code className="text-[#dfb180] font-mono">{selectedDeployment.site_id || selectedDeployment.id.slice(0, 8)}</code>
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {/* Autonomous Self-Heal Button */}
                          <button
                            type="button"
                            disabled={isSelfHealingDeployment}
                            onClick={handleTriggerDeploymentSelfHeal}
                            className="px-3.5 py-1.5 bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] text-xs font-black rounded-lg transition-all flex items-center gap-1.5 shadow-md border-none cursor-pointer disabled:opacity-50"
                            title="Audit codebase, fix build/runtime errors permanently, and redeploy"
                          >
                            {isSelfHealingDeployment ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin text-[#09090b]" />
                            ) : (
                              <Sparkles className="w-3.5 h-3.5 text-[#09090b]" />
                            )}
                            {isSelfHealingDeployment ? "Self-Healing..." : "Self-Heal Website"}
                          </button>

                          {liveTargetUrl && (
                            <a
                              href={liveTargetUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-3 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 shadow-md shadow-emerald-600/20 text-decoration-none"
                            >
                              <Globe className="w-3.5 h-3.5" /> Open Live Site
                            </a>
                          )}
                          <button
                            onClick={() => {
                              setIsConsoleOpen(false);
                              setSelectedDeployment(null);
                            }}
                            className="text-slate-400 hover:text-white transition-colors bg-transparent border-none text-2xl leading-none cursor-pointer p-1"
                          >
                            x
                          </button>
                        </div>
                      </div>

                      {/* Filter & Stream Controls Toolbar */}
                      <div className="flex flex-wrap items-center justify-between gap-2.5 text-xs">
                        <div className="flex items-center gap-1.5 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
                          <button
                            type="button"
                            onClick={() => setConsoleFilter("all")}
                            className={`px-2.5 py-1 rounded-lg font-medium transition-all border-none cursor-pointer ${consoleFilter === "all" ? "bg-[#c89666]/15 text-white shadow-sm" : "bg-transparent text-slate-400 hover:text-white"}`}
                          >
                            All ({totalCount})
                          </button>
                          <button
                            type="button"
                            onClick={() => setConsoleFilter("errors")}
                            className={`px-2.5 py-1 rounded-lg font-medium transition-all border-none cursor-pointer ${consoleFilter === "errors" ? "bg-red-600 text-white shadow-sm" : errorLines.length > 0 ? "bg-red-500/10 text-red-400 hover:bg-red-500/20" : "bg-transparent text-slate-400 hover:text-white"}`}
                          >
                            ❌ Errors ({errorLines.length})
                          </button>
                          <button
                            type="button"
                            onClick={() => setConsoleFilter("audit")}
                            className={`px-2.5 py-1 rounded-lg font-medium transition-all border-none cursor-pointer ${consoleFilter === "audit" ? "bg-[#c89666]/15 text-white shadow-sm" : "bg-transparent text-slate-400 hover:text-white"}`}
                          >
                            🩺 Audit & Self-Heal
                          </button>
                          <button
                            type="button"
                            onClick={() => setConsoleFilter("browser")}
                            className={`px-2.5 py-1 rounded-lg font-medium transition-all border-none cursor-pointer ${consoleFilter === "browser" ? "bg-cyan-600 text-white shadow-sm" : "bg-transparent text-slate-400 hover:text-white"}`}
                          >
                            🌐 Browser Logs ({browserLines.length})
                          </button>
                          <button
                            type="button"
                            onClick={() => setConsoleFilter("server")}
                            className={`px-2.5 py-1 rounded-lg font-medium transition-all border-none cursor-pointer ${consoleFilter === "server" ? "bg-teal-600 text-white shadow-sm" : "bg-transparent text-slate-400 hover:text-white"}`}
                          >
                            🖥️ Server HTTP ({serverLines.length})
                          </button>
                        </div>

                        <div className="flex items-center gap-2">
                          <div className="relative">
                            <input
                              type="text"
                              value={consoleSearch}
                              onChange={(e) => setConsoleSearch(e.target.value)}
                              placeholder="Filter logs..."
                              className="px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#c89666]/30 w-36 sm:w-44"
                            />
                            {consoleSearch && (
                              <button
                                type="button"
                                onClick={() => setConsoleSearch("")}
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white bg-transparent border-none cursor-pointer text-xs"
                              >
                                ×
                              </button>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => setIsConsoleStreamPaused(!isConsoleStreamPaused)}
                            className={`px-2.5 py-1 rounded-lg font-medium border border-slate-700 transition-all cursor-pointer flex items-center gap-1 ${isConsoleStreamPaused ? "bg-amber-500/20 text-amber-300 border-amber-500/40" : "bg-slate-800 hover:bg-slate-700 text-slate-300"}`}
                            title={isConsoleStreamPaused ? "Resume live streaming" : "Pause live streaming"}
                          >
                            {isConsoleStreamPaused ? (
                              <>
                                <Play className="w-3 h-3 text-amber-400" /> Resume
                              </>
                            ) : (
                              <>
                                <Pause className="w-3 h-3 text-emerald-400" /> Pause
                              </>
                            )}
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              navigator.clipboard.writeText(activeConsoleLogs);
                              setCopyLogsFeedback(true);
                              setTimeout(() => setCopyLogsFeedback(false), 2000);
                            }}
                            className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg font-medium border border-slate-700 transition-all cursor-pointer flex items-center gap-1"
                            title="Copy all logs to clipboard"
                          >
                            {copyLogsFeedback ? (
                              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                                <Check className="w-3 h-3" /> Copied!
                              </span>
                            ) : (
                              <>
                                <Copy className="w-3 h-3 text-slate-400" /> Copy
                              </>
                            )}
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              const blob = new Blob([activeConsoleLogs], { type: "text/plain;charset=utf-8" });
                              const url = URL.createObjectURL(blob);
                              const a = document.createElement("a");
                              a.href = url;
                              a.download = `${selectedDeployment?.site_id || "site"}-runtime.log`;
                              a.click();
                              URL.revokeObjectURL(url);
                            }}
                            className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg font-medium border border-slate-700 transition-all cursor-pointer flex items-center gap-1"
                            title="Export logs as file"
                          >
                            <Download className="w-3 h-3 text-slate-400" /> Export
                          </button>

                          <button
                            type="button"
                            onClick={async () => {
                              try {
                                const data = await api.get(`/deployments/${selectedDeployment.id}`, authToken ?? undefined);
                                setActiveConsoleLogs(data.logs || "");
                                setActiveConsoleStatus(data.status);
                                setSelectedDeployment(prev => prev ? { ...prev, ...data } : data);
                              } catch (e) { }
                            }}
                            className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg font-medium border border-slate-700 transition-all cursor-pointer flex items-center gap-1"
                            title="Manually refresh logs"
                          >
                            <RefreshCw className="w-3 h-3 text-slate-400" /> Refresh
                          </button>
                        </div>
                      </div>

                      {/* Terminal Window */}
                      <div className="terminal-window border border-slate-800 bg-[#050811] rounded-xl overflow-hidden shadow-inner">
                        <div className="terminal-header bg-slate-900/80 px-4 py-2 border-b border-slate-800 flex justify-between items-center text-xs">
                          <div className="terminal-dots flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block"></span>
                            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block"></span>
                            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block"></span>
                            <span className="font-mono text-[11px] text-slate-400 ml-2">aisitestudio-runtime-stream — {filteredLines.length} events</span>
                          </div>
                          <span className="text-xs font-mono flex items-center gap-1.5">
                            {isBuilding ? (
                              <span className="text-amber-400 font-bold flex items-center gap-1.5">
                                <Loader2 className="w-3.5 h-3.5 animate-spin text-[#dfb180]" />
                                COMPILING & DEPLOYING...
                              </span>
                            ) : isSuccess ? (
                              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                                {isConsoleStreamPaused ? "STREAM PAUSED" : "STREAMING ACTIVE"}
                              </span>
                            ) : (
                              <span className="text-red-400 font-bold flex items-center gap-1">
                                ⚠️ FAILED
                              </span>
                            )}
                          </span>
                        </div>

                        <div ref={consoleEndRef} className="terminal-body p-4 max-h-[380px] overflow-y-auto font-mono text-xs leading-relaxed space-y-0.5">
                          {filteredLines.length === 0 ? (
                            <div className="text-center py-8 text-slate-500 italic">
                              {consoleSearch ? "No logs match the current search filter." : "No logs available yet. Live logs will appear in real time."}
                            </div>
                          ) : (
                            filteredLines.map((line, idx) => {
                              const clean = stripAnsi(line);
                              if (!clean.trim()) return null;

                              const isError = clean.includes("[ERROR]") || clean.includes("❌") || clean.includes("RUNTIME ERROR") || clean.includes("UNHANDLED REJECTION");
                              const isAudit = clean.includes("[AUDIT]");
                              const isHeal = clean.includes("[HEAL]") || clean.includes("[SELF-HEAL]");
                              const isBrowserWarn = clean.includes("[BROWSER WARN]") || clean.includes("[WARN]");
                              const isBrowserLog = clean.includes("[BROWSER LOG]") || clean.includes("[BROWSER INFO]");
                              const isClientBoot = clean.includes("[CLIENT BOOT]");
                              const isServer200 = clean.includes("[SERVER HTTP 200]");
                              const isServer404 = clean.includes("[SERVER HTTP 404]") || clean.includes("[SERVER HTTP 5");
                              const isSuccessLine = clean.includes("[SUCCESS]") || clean.startsWith("✅") || clean.startsWith("✓");
                              const isStepLine = /^\d+\//.test(clean.trim()) || clean.includes("[1/") || clean.includes("[2/") || clean.includes("[3/") || clean.includes("[4/");

                              return (
                                <div
                                  key={idx}
                                  className={`terminal-log-line py-0.5 px-1.5 rounded transition-colors ${isError
                                    ? "bg-red-500/15 text-red-300 font-semibold border-l-2 border-red-500"
                                    : isBrowserWarn
                                      ? "text-amber-300"
                                      : isClientBoot
                                        ? "text-cyan-300 font-semibold"
                                        : isBrowserLog
                                          ? "text-slate-100"
                                          : isServer200
                                            ? "text-teal-300"
                                            : isServer404
                                              ? "text-orange-400 font-semibold"
                                              : isSuccessLine
                                                ? "text-emerald-400 font-semibold"
                                                : isStepLine
                                                  ? "text-sky-300"
                                                  : "text-slate-300"
                                    }`}
                                >
                                  {clean}
                                </div>
                              );
                            })
                          )}
                          {!isConsoleStreamPaused && <span className="inline-block w-2 h-3.5 bg-[#c89666]/15 animate-pulse ml-1 align-middle" />}
                        </div>
                      </div>

                      {/* Intelligent Auto-Healer banner if live errors are detected */}
                      {errorLines.length > 0 && (
                        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                          <div className="flex items-start sm:items-center gap-2">
                            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5 sm:mt-0" />
                            <div>
                              <span className="font-bold text-red-300">Live Runtime Error Detected:</span>
                              <p className="text-red-200/90 text-[11px] mt-0.5 font-mono line-clamp-1">{displayError}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              type="button"
                              onClick={handleQuickAutoHeal}
                              disabled={isAutoFixingFromConsole}
                              className="px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-lg transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50 border-none shadow-md shadow-amber-500/20"
                            >
                              {isAutoFixingFromConsole ? (
                                <>
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Auto-Healing...
                                </>
                              ) : (
                                <>
                                  <Sparkles className="w-3.5 h-3.5" /> ⚡ Auto-Fix with Auto-Heal
                                </>
                              )}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setIsConsoleOpen(false);
                                openCodeStudio(selectedDeployment);
                              }}
                              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-[#dfb180] font-semibold rounded-lg transition-all border border-[#c89666]/30 cursor-pointer"
                            >
                              🛠️ Open Code Studio
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Modal Footer */}
                      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pt-3 border-t border-slate-800 text-xs">
                        <div className="text-slate-400 flex items-center gap-2">
                          {isBuilding ? (
                            <span className="text-amber-300 flex items-center gap-1.5">
                              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Build in progress...
                            </span>
                          ) : isSuccess ? (
                            <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
                              ✓ Website is live and actively streaming client & server logs.
                            </span>
                          ) : (
                            <span className="text-red-400 font-semibold">✗ Deployment halted. Review error details above.</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2.5 self-end sm:self-auto">
                          {liveTargetUrl && (
                            <a
                              href={liveTargetUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold rounded-xl transition-all text-center text-decoration-none shadow-lg shadow-emerald-600/20 border-none"
                            >
                              🌐 Visit Live Site
                            </a>
                          )}
                          <button
                            onClick={() => {
                              setIsConsoleOpen(false);
                              setSelectedDeployment(null);
                            }}
                            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl transition-colors border-none cursor-pointer"
                          >
                            Close Console
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* === VERSION HISTORY & ROLLBACK MODAL === */}
              {isVersionModalOpen && versionDeployment && (
                <div className="modal-backdrop">
                  <div className="modal-content glass border border-border/40 p-6 rounded-2xl max-w-lg w-full space-y-4">
                    <div className="flex justify-between items-center border-b border-border/20 pb-3">
                      <div>
                        <h3 className="font-bold text-lg text-white flex items-center gap-2">
                          <History className="w-5 h-5 text-primary" /> Version History & Rollback
                        </h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Project: <span className="text-foreground font-semibold">{versionDeployment.project_name}</span> ({versionDeployment.site_id || "SITE-CURRENT"})
                        </p>
                      </div>
                      <button
                        onClick={() => {
                          setIsVersionModalOpen(false);
                          setVersionDeployment(null);
                        }}
                        className="text-muted-foreground hover:text-white transition-colors bg-transparent border-none text-xl cursor-pointer"
                      >
                        ×
                      </button>
                    </div>

                    <p className="text-xs text-slate-300">
                      Switch traffic instantly to any previous snapshot with atomic zero-downtime rollback.
                    </p>

                    {versionsLoading ? (
                      <div className="text-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary" />
                        <p className="text-xs text-muted-foreground mt-2">Loading version history...</p>
                      </div>
                    ) : versionsList.length === 0 ? (
                      <div className="p-5 border border-dashed border-border/40 rounded-xl text-center text-xs text-muted-foreground">
                        No previous historical versions found. Current version is <span className="text-primary font-bold">{versionDeployment.current_version || "v1.0"}</span>.
                      </div>
                    ) : (
                      <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                        {versionsList.map((ver) => {
                          const isCurrent = ver.version === versionDeployment.current_version;
                          return (
                            <div key={ver.id} className={`p-3 rounded-xl border flex items-center justify-between transition-all ${isCurrent ? "bg-primary/10 border-primary/40" : "bg-card/20 border-border/40 hover:bg-muted/20"}`}>
                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-sm text-foreground">{ver.version}</span>
                                  {isCurrent && (
                                    <span className="text-[10px] bg-emerald-500/20 text-emerald-400 font-bold px-2 py-0.5 rounded-full border border-emerald-500/30 uppercase tracking-wider">
                                      Active Live
                                    </span>
                                  )}
                                </div>
                                <div className="text-[11px] text-muted-foreground mt-0.5">
                                  {ver.commit_message || "Automated deployment"} • {new Date(ver.created_at).toLocaleDateString()}
                                </div>
                              </div>

                              {!isCurrent ? (
                                <button
                                  onClick={() => handleRollback(ver.version)}
                                  className="px-3 py-1.5 bg-primary text-white rounded-lg text-xs font-semibold hover:bg-primary/90 transition-all cursor-pointer flex items-center gap-1 shadow-md shadow-primary/20"
                                >
                                  <History className="w-3.5 h-3.5" /> Rollback to {ver.version}
                                </button>
                              ) : (
                                <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                                  <CheckCircle2 className="w-3.5 h-3.5" /> Serving Live
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    <div className="flex justify-end pt-3 border-t border-border/20">
                      <button
                        onClick={() => {
                          setIsVersionModalOpen(false);
                          setVersionDeployment(null);
                        }}
                        className="px-4 py-2 bg-muted border border-border/40 hover:bg-muted/80 text-foreground text-xs font-semibold rounded-xl transition-colors cursor-pointer"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* === DOMAIN OWNERSHIP, EPP TRANSFER & GODADDY PUSH MODAL === */}
              {transferModalDomain && (
                <div className="modal-backdrop">
                  <div className="modal-content glass border border-[#2e2e38] p-6 rounded-2xl max-w-xl w-full space-y-5 bg-[#121216] text-[#fafafa] shadow-2xl">
                    <div className="flex justify-between items-start border-b border-[#27272a] pb-3.5">
                      <div>
                        <div className="flex items-center gap-2">
                          <ShieldCheck className="w-5 h-5 text-[#c89666]" />
                          <h3 className="font-extrabold text-base text-white">Domain Ownership &amp; Registrar Control</h3>
                        </div>
                        <p className="text-xs text-[#a8a29e] mt-1">
                          Target Domain: <span className="text-[#dfb180] font-mono font-bold">{transferModalDomain}</span>
                        </p>
                      </div>
                      <button
                        onClick={() => {
                          setTransferModalDomain(null);
                          setTransferDetails(null);
                          setTransferPushAccount("");
                        }}
                        className="text-[#a8a29e] hover:text-white transition-colors bg-transparent border-none text-2xl cursor-pointer leading-none"
                      >
                        &times;
                      </button>
                    </div>

                    <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 leading-relaxed">
                      <strong>100% Independent Customer Ownership:</strong> All custom domains are registered with your legal contact profile under ICANN regulations. You are the legal owner and have full authority to move or manage this domain at any time.
                    </div>

                    {transferLoading ? (
                      <div className="text-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin mx-auto text-[#c89666]" />
                        <p className="text-xs text-[#a8a29e] mt-2">Loading registrar ownership details...</p>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {/* Option 1: EPP Authorization Code */}
                        <div className="p-4 rounded-xl bg-[#18181f] border border-[#27272a] space-y-2.5">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-white uppercase tracking-wider">Option 1: EPP Authorization Code (Transfer Out)</span>
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#09090b] text-[#dfb180] border border-[#33333e]">
                              {transferDetails?.transfer_status === "auth_code_issued" ? "Lock Disabled &bull; Code Ready" : "Locked"}
                            </span>
                          </div>
                          <p className="text-xs text-[#a8a29e] leading-relaxed">
                            Generate your ICANN EPP code to transfer this domain to another registrar (such as Cloudflare, Namecheap, Google Domains / Squarespace, or AWS Route53).
                          </p>

                          {transferDetails?.transfer_auth_code ? (
                            <div className="space-y-2 pt-1">
                              <label className="text-[11px] font-bold text-[#c89666] uppercase">Your EPP Authorization Code:</label>
                              <div className="flex items-center gap-2">
                                <input
                                  type="text"
                                  readOnly
                                  value={transferDetails.transfer_auth_code}
                                  className="w-full px-3 py-2 rounded-lg bg-[#09090b] border border-[#383844] font-mono text-sm text-[#dfb180] font-bold outline-none selection:bg-[#c89666]/40"
                                />
                                <button
                                  type="button"
                                  onClick={() => {
                                    navigator.clipboard.writeText(transferDetails.transfer_auth_code);
                                    toast.success("EPP Authorization Code copied to clipboard!");
                                  }}
                                  className="px-3 py-2 rounded-lg bg-[#c89666] hover:bg-[#dfb180] text-[#09090b] text-xs font-black shrink-0 transition cursor-pointer"
                                >
                                  Copy
                                </button>
                              </div>
                              <span className="text-[11px] text-emerald-400 block font-medium">
                                &check; Transfer lock has been lifted. Paste this code into your new registrar's transfer form.
                              </span>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={handleRequestEPP}
                              disabled={transferActionLoading}
                              className="px-4 py-2 rounded-lg bg-[#272730] hover:bg-[#32323e] text-white text-xs font-bold border border-[#3a3a46] flex items-center gap-1.5 transition cursor-pointer"
                            >
                              {transferActionLoading ? (
                                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Send className="w-3.5 h-3.5 text-[#c89666]" />
                              )}
                              <span>Request EPP Authorization Code</span>
                            </button>
                          )}
                        </div>

                        {/* Option 2: GoDaddy Account Push */}
                        <div className="p-4 rounded-xl bg-[#18181f] border border-[#27272a] space-y-2.5">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-white uppercase tracking-wider">Option 2: Direct GoDaddy Account Push</span>
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#09090b] text-emerald-400 border border-emerald-500/30">
                              Instant &bull; Free
                            </span>
                          </div>
                          <p className="text-xs text-[#a8a29e] leading-relaxed">
                            Already have your own GoDaddy account? We will push the domain straight into your personal GoDaddy portal so you have direct access to its DNS records and renewal settings.
                          </p>

                          {transferDetails?.pushed_to_account ? (
                            <div className="p-3 rounded-lg bg-[#09090b] border border-[#27272a] text-xs space-y-1">
                              <span className="text-emerald-400 font-bold block">&check; Push Submitted</span>
                              <span className="text-[#a8a29e]">Domain has been initiated for transfer to GoDaddy account: <strong className="text-white">{transferDetails.pushed_to_account}</strong></span>
                              <p className="text-[11px] text-[#71717a] pt-1">Log into your GoDaddy account and check "Pending Account Changes" under Domain Management to accept the transfer.</p>
                            </div>
                          ) : (
                            <div className="space-y-2.5 pt-1">
                              <label className="text-[11px] font-bold text-[#c89666] uppercase">Your GoDaddy Customer # or Account Email:</label>
                              <div className="flex flex-col sm:flex-row items-center gap-2">
                                <input
                                  type="text"
                                  placeholder="e.g. 12345678 or user@example.com"
                                  value={transferPushAccount}
                                  onChange={(e) => setTransferPushAccount(e.target.value)}
                                  className="w-full px-3 py-2 rounded-lg bg-[#09090b] border border-[#383844] text-xs text-white outline-none focus:border-[#c89666]"
                                />
                                <button
                                  type="button"
                                  onClick={handlePushGoDaddy}
                                  disabled={transferActionLoading || !transferPushAccount.trim()}
                                  className="w-full sm:w-auto px-4 py-2 rounded-lg bg-gradient-to-r from-[#c89666] to-[#b5804f] hover:from-[#dfb180] hover:to-[#c89666] text-[#09090b] text-xs font-black shrink-0 transition disabled:opacity-50 cursor-pointer"
                                >
                                  {transferActionLoading ? "Initiating..." : "Push to GoDaddy"}
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    <div className="flex justify-end pt-3 border-t border-[#27272a]">
                      <button
                        onClick={() => {
                          setTransferModalDomain(null);
                          setTransferDetails(null);
                          setTransferPushAccount("");
                        }}
                        className="px-5 py-2 rounded-xl bg-[#1c1c22] hover:bg-[#26262e] text-white text-xs font-bold border border-[#2e2e38] transition cursor-pointer"
                      >
                        Done
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* === EDIT & REDESIGN TEMPLATE MODAL === */}
              {editTemplateModalOpen && editingTemplate && (
                <div className="modal-backdrop">
                  <div className="modal-content glass border border-border/40 p-6 rounded-2xl max-w-lg w-full space-y-5">
                    <div className="flex justify-between items-center border-b border-border/20 pb-3">
                      <div>
                        <h3 className="font-bold text-lg text-white flex items-center gap-2">
                          <Pencil className="w-5 h-5 text-primary" /> Redesign & Edit Template
                        </h3>
                        <p className="text-xs text-muted-foreground mt-0.5">Template ID: {editingTemplate.id}</p>
                      </div>
                      <button
                        onClick={() => {
                          setEditTemplateModalOpen(false);
                          setEditingTemplate(null);
                        }}
                        className="text-muted-foreground hover:text-white transition-colors bg-transparent border-none text-xl cursor-pointer"
                      >
                        ×
                      </button>
                    </div>

                    <div className="p-3 bg-gradient-to-r from-primary/10 from-[#c89666] to-[#b5804f]/10 border border-primary/20 rounded-xl flex items-center justify-between gap-3">
                      <div>
                        <div className="text-xs font-bold text-white flex items-center gap-1.5">
                          <Sparkles className="w-4 h-4 text-primary" /> Visual Studio Canvas
                        </div>
                        <p className="text-[11px] text-muted-foreground mt-0.5">Customize copywriting, colors, section layouts, and images live.</p>
                      </div>
                      <Link
                        href={`/preview?templateId=${editingTemplate.id}`}
                        className="px-3.5 py-1.5 bg-primary text-white hover:bg-primary/95 text-xs font-bold rounded-xl transition-all shadow-md shadow-primary/20 shrink-0 text-decoration-none"
                      >
                        Open Studio →
                      </Link>
                    </div>

                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const rawPrice = Number(editPrice) || 0;
                        const finalPrice = editCurrency && editCurrency.toUpperCase() !== "USD"
                          ? Number(convertToUSD(rawPrice, editCurrency, rates))
                          : rawPrice;
                        updateTemplateMutation.mutate({
                          templateId: editingTemplate.id,
                          data: {
                            title: editTitle.trim(),
                            description: editDescription.trim(),
                            price: finalPrice,
                            price_currency: "USD",
                            framework: editFramework.toLowerCase(),
                            version: editVersion.trim() || "1.0.0",
                            category_id: editingTemplate.category_id || undefined,
                            category: editCategory,
                            preview_url: editDemoUrl.trim() || undefined,
                          },
                        });
                      }}
                      className="space-y-4"
                    >
                      {editError && (
                        <div className="text-xs text-red-700 bg-red-50 border border-red-200 p-3 rounded-xl font-medium">
                          {editError}
                        </div>
                      )}

                      <div className="space-y-1.5">
                        <label className="uw-label">Template Title *</label>
                        <input
                          type="text"
                          required
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          className="uw-input"
                        />
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div className="space-y-1.5">
                          <div className="flex justify-between items-center">
                            <label className="uw-label" style={{ marginBottom: 0 }}>Price ({editCurrency}) *</label>
                            <select
                              value={editCurrency}
                              onChange={(e) => handleEditCurrencyChange(e.target.value)}
                              className="text-[10px] font-extrabold bg-slate-100 border border-slate-300 rounded px-1.5 py-0.5 text-slate-800"
                            >
                              <option value="INR">INR (₹)</option>
                              <option value="USD">USD ($)</option>
                              <option value="EUR">EUR (€)</option>
                              <option value="GBP">GBP (£)</option>
                              <option value="CAD">CAD (CA$)</option>
                              <option value="AUD">AUD (A$)</option>
                              <option value="JPY">JPY (¥)</option>
                              <option value="AED">AED (AED)</option>
                            </select>
                          </div>
                          <input
                            type="number"
                            step="any"
                            min="0"
                            required
                            value={editPrice}
                            onChange={(e) => setEditPrice(e.target.value)}
                            className="uw-input font-mono font-extrabold"
                          />
                          <div className="text-[11px] text-slate-500 font-medium">
                            {editCurrency === "INR" ? (
                              <span>Marketplace: <strong className="font-extrabold text-emerald-700">${convertToUSD(editPrice, "INR", rates)} USD</strong></span>
                            ) : (
                              <span>Marketplace: <strong className="font-extrabold text-emerald-700">${convertToUSD(editPrice, editCurrency, rates)} USD</strong></span>
                            )}
                          </div>
                        </div>

                        <div className="space-y-1.5">
                          <label className="uw-label">Framework *</label>
                          <select
                            value={editFramework}
                            onChange={(e) => setEditFramework(e.target.value)}
                            className="uw-select"
                          >
                            <option value="html">HTML5 (Pure HTML)</option>
                            <option value="nextjs">Next.js</option>
                            <option value="react">React</option>
                            <option value="vue">Vue.js</option>
                            <option value="nuxt">Nuxt.js</option>
                            <option value="astro">Astro</option>
                            <option value="tailwind">Tailwind CSS (HTML)</option>
                            <option value="angular">Angular</option>
                            <option value="svelte">Svelte</option>
                          </select>
                        </div>

                        <div className="space-y-1.5">
                          <label className="uw-label">Code Version *</label>
                          <input
                            type="text"
                            value={editVersion}
                            onChange={(e) => setEditVersion(e.target.value)}
                            placeholder="1.0.0"
                            className="uw-input font-mono font-extrabold"
                          />
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <label className="uw-label">Description</label>
                        <textarea
                          rows={3}
                          value={editDescription}
                          onChange={(e) => setEditDescription(e.target.value)}
                          className="uw-textarea"
                          placeholder="Brief description of this template features..."
                        />
                      </div>

                      {/* Re-upload Template Section */}
                      <div className="border-t border-slate-200 pt-3 space-y-2">
                        <label className="uw-label flex items-center justify-between" style={{ marginBottom: 0 }}>
                          <span>Replace Source Code (.ZIP or .HTML)</span>
                          <span className="text-[10px] text-slate-500 font-normal normal-case">Optional</span>
                        </label>
                        <div className="flex items-center gap-2">
                          <input
                            type="file"
                            accept=".zip,.html,.htm"
                            onChange={(e) => {
                              if (e.target.files && e.target.files[0]) {
                                const file = e.target.files[0];
                                reuploadZipMutation.mutate({ templateId: editingTemplate.id, file });
                              }
                            }}
                            className="text-xs text-slate-600 file:mr-2 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-[#c89666]/15 file:text-[#dfb180] hover:file:bg-[#c89666]/15 cursor-pointer"
                          />
                          {reuploadZipMutation.isPending && (
                            <span className="text-xs text-[#dfb180] font-bold flex items-center gap-1">
                              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Uploading & Auditing...
                            </span>
                          )}
                          {reuploadZipMutation.isSuccess && (
                            <span className="text-xs text-emerald-700 font-extrabold flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Source Code Replaced & Verified!
                            </span>
                          )}
                          {reuploadZipMutation.isError && (
                            <span className="text-xs text-red-600 font-bold flex items-center gap-1">
                              ❌ {reuploadZipMutation.error?.message || "Upload failed"}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex justify-end gap-2 border-t border-slate-200 pt-3">
                        <button
                          type="button"
                          onClick={() => {
                            setEditTemplateModalOpen(false);
                            setEditingTemplate(null);
                          }}
                          className="uw-btn-back"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={updateTemplateMutation.isPending}
                          className="uw-btn-publish"
                        >
                          {updateTemplateMutation.isPending ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" /> Saving Changes...
                            </>
                          ) : (
                            "Save Changes"
                          )}
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              )}

              {/* === WRITE REVIEW MODAL === */}
              {reviewModalOpen && (
                <div className="modal-backdrop">
                  <div className="modal-content glass border border-border/40 p-6 rounded-2xl max-w-md w-full space-y-4">
                    <div className="flex justify-between items-center border-b border-border/20 pb-3">
                      <div>
                        <h3 className="font-bold text-lg text-white">Write a Review</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">Template: {reviewTemplateTitle}</p>
                      </div>
                      <button
                        onClick={() => setReviewModalOpen(false)}
                        className="text-muted-foreground hover:text-white transition-colors bg-transparent border-none text-xl cursor-pointer"
                      >
                        ×
                      </button>
                    </div>

                    <form onSubmit={(e) => {
                      e.preventDefault();
                      setSubmitReviewError("");
                      createReviewMutation.mutate({
                        template_id: reviewTemplateId,
                        rating: Number(reviewRating),
                        title: reviewTitle.trim() || "Review",
                        body: reviewBody.trim(),
                      });
                    }} className="space-y-4">
                      {submitReviewError && (
                        <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 p-2.5 rounded-lg">
                          {submitReviewError}
                        </div>
                      )}

                      <div className="space-y-1.5">
                        <label className="block text-xs font-semibold text-muted-foreground uppercase">Rating</label>
                        <div className="flex gap-2">
                          {[1, 2, 3, 4, 5].map((star) => (
                            <button
                              key={star}
                              type="button"
                              onClick={() => setReviewRating(star)}
                              className="bg-transparent border-none p-0 cursor-pointer"
                            >
                              <Star className={`w-6 h-6 ${star <= reviewRating ? "fill-yellow-400 text-yellow-400" : "text-slate-600"}`} />
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <label className="block text-xs font-semibold text-muted-foreground uppercase">Title</label>
                        <input
                          type="text"
                          value={reviewTitle}
                          onChange={(e) => setReviewTitle(e.target.value)}
                          placeholder="Summarize your feedback..."
                          className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50 text-white"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="block text-xs font-semibold text-muted-foreground uppercase">Review Body *</label>
                        <textarea
                          rows={4}
                          required
                          value={reviewBody}
                          onChange={(e) => setReviewBody(e.target.value)}
                          placeholder="What did you think of the design, usability, code quality, and documentation?"
                          className="w-full px-4 py-2.5 text-white bg-slate-900/80 border border-border/40 rounded-xl p-2.5 text-sm focus:outline-none focus:border-primary h-24"
                        />
                      </div>

                      <div className="flex justify-end gap-2 pt-3 border-t border-border/20">
                        <button
                          type="button"
                          onClick={() => setReviewModalOpen(false)}
                          className="px-4 py-2 bg-muted border border-border/40 hover:bg-muted/80 text-foreground text-xs font-semibold rounded-xl transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={createReviewMutation.isPending}
                          className="px-4 py-2 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/95 transition-colors disabled:opacity-50 flex items-center gap-1.5"
                        >
                          {createReviewMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                          Submit Review
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              )}


            </div>
          </div>
        </div>
      </div>

      {/* Failure Incident Reporting Modal */}
      <ReportIssueModal
        isOpen={isReportIssueModalOpen}
        onClose={() => {
          setIsReportIssueModalOpen(false);
          setReportIssueDeployment(null);
        }}
        deployment={reportIssueDeployment}
        authToken={authToken}
        onReportSuccess={() => refetchDeployments()}
      />

      {/* Deployment Code Fix Studio & IDE Console */}
      <DeploymentFixConsole
        isOpen={isCodeStudioOpen}
        onClose={() => {
          setIsCodeStudioOpen(false);
          setCodeStudioDeployment(null);
          setCodeStudioIncident(null);
        }}
        deployment={codeStudioDeployment}
        incident={codeStudioIncident}
        authToken={authToken}
        onUpdateSuccess={() => refetchDeployments()}
      />

      {/* Mandatory License & Code Usage Warning Modal */}
      <DownloadWarningModal
        isOpen={!!downloadWarningTarget}
        onClose={() => setDownloadWarningTarget(null)}
        onConfirm={handleConfirmDownload}
        templateTitle={downloadWarningTarget?.title || "Template Package"}
        licenseType={downloadWarningTarget?.license_type || (user?.is_pro_subscriber ? "extended" : "regular")}
        isDownloading={triggerDownload.isPending}
      />
    </>
  );
}

export default Dashboard;

// Inline Chevron helper
function ChevronRight(props) {
  return (
    <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" className={props.className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}
