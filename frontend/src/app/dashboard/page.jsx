"use client";

/**
 * User Dashboard Page - manages purchases, wishlist, downloads, orders, and settings (React JSX).
 */

export const dynamic = "force-dynamic";

import { useState, useEffect, useRef } from "react";
import JSZip from "jszip";
import { useAppAuth, useAppUser, useSignOut } from "@/lib/auth";
import { useAuthStore } from "@/store/authStore";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Code,
  Cpu,
  Globe,
  Download,
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
  FileUp,
  Check,
  ShoppingCart,
  Wand2,
  Terminal,
  RefreshCw,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { api } from "@/lib/api";
import { useSearchParams } from "react-router";
import { cn, formatPrice } from "@/lib/utils";
import Image from "@/components/Image";
import Link from "@/components/Link";
import { useCartStore } from "@/store";
import "./Page.css";

function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { getToken } = useAppAuth();
  const { user } = useAppUser();
  const signOut = useSignOut();
  const [activeTab, setActiveTab] = useState("buyer-home");
  const addToCart = useCartStore((s) => s.addItem);
  const isInCart = useCartStore((s) => s.isInCart);
  const [authToken, setAuthToken] = useState(null);
  const qc = useQueryClient();

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [bio, setBio] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [templatesSubTab, setTemplatesSubTab] = useState("purchased");

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
  const [linkDomainDeploymentId, setLinkDomainDeploymentId] = useState("");
  const [customDomainInput, setCustomDomainInput] = useState("");
  const [linkDomainError, setLinkDomainError] = useState("");

  // Deployments state
  const [isDeployModalOpen, setIsDeployModalOpen] = useState(false);
  const [isConsoleOpen, setIsConsoleOpen] = useState(false);
  const [selectedDeployment, setSelectedDeployment] = useState(null);
  const [activeConsoleLogs, setActiveConsoleLogs] = useState("");
  const [activeConsoleStatus, setActiveConsoleStatus] = useState("building");

  // Wizard form state
  const [deployProjectName, setDeployProjectName] = useState("");
  const [deployTemplateId, setDeployTemplateId] = useState("");
  const [deployProvider, setDeployProvider] = useState("vercel");
  const [deployBranch, setDeployBranch] = useState("main");
  const [deployBuildCommand, setDeployBuildCommand] = useState("npm run build");
  const [deployOutputDir, setDeployOutputDir] = useState("dist");
  const [deploying, setDeploying] = useState(false);
  const consoleEndRef = useRef(null);

  const isSeller = user?.role === "seller" || user?.role === "SELLER";
  const isAdmin = user?.role === "admin" || user?.role === "super_admin" || user?.role === "ADMIN" || user?.role === "SUPER_ADMIN";

  // Role syncing — only set default tab when URL has no explicit ?tab= override
  useEffect(() => {
    if (user) {
      setFullName(user.fullName || "");
      setUsername(user.username || "");
      setBio(user.bio || "");
      setAvatarUrl(user.avatar_url || "");
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
    }
  }, [user, isAdmin, isSeller, searchParams]);

  // Sync My Templates sub-tab based on sidebar selection
  useEffect(() => {
    if (activeTab === "seller-templates") {
      setTemplatesSubTab("uploaded");
    } else if (activeTab === "buyer-templates") {
      setTemplatesSubTab("purchased");
    }
  }, [activeTab]);

  useEffect(() => {
    getToken().then(setAuthToken);
  }, [getToken]);

  // Fetch actual admin users from backend when admin tab is active
  useEffect(() => {
    if (authToken && isAdmin) {
      fetch("http://localhost:8000/api/v1/admin/users?page_size=100", {
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
  });

  // Fetch User Orders/Purchases
  const { data: orders = [], isLoading: ordersLoading } = useQuery({
    queryKey: ["orders"],
    queryFn: () => api.get("/orders", authToken ?? undefined),
    enabled: !!authToken,
  });

  // Fetch Wishlist Items
  const { data: wishlist = [], isLoading: wishlistLoading } = useQuery({
    queryKey: ["wishlist"],
    queryFn: () => api.get("/wishlist", authToken ?? undefined),
    enabled: !!authToken,
  });

  // Fetch Followers
  const { data: followers = [], isLoading: followersLoading } = useQuery({
    queryKey: ["followers"],
    queryFn: () => api.get("/follows/followers", authToken ?? undefined),
    enabled: !!authToken && isSeller,
  });

  // Fetch Following
  const { data: following = [], isLoading: followingLoading } = useQuery({
    queryKey: ["following"],
    queryFn: () => api.get("/follows/following", authToken ?? undefined),
    enabled: !!authToken,
  });

  // Fetch Seller/Buyer Templates
  const { data: templateResponse, isLoading: templatesLoading } = useQuery({
    queryKey: ["seller-templates"],
    queryFn: () => api.get("/templates/my-templates", authToken ?? undefined),
    enabled: !!authToken,
  });

  // Fetch Buyer Reviews
  const { data: buyerReviewsData, isLoading: buyerReviewsLoading } = useQuery({
    queryKey: ["buyer-reviews"],
    queryFn: () => api.get("/reviews/buyer?page_size=50", authToken ?? undefined),
    enabled: !!authToken,
  });
  const buyerReviewsList = buyerReviewsData?.items || [];

  // Fetch Seller Reviews
  const { data: sellerReviewsData, isLoading: sellerReviewsLoading } = useQuery({
    queryKey: ["seller-reviews"],
    queryFn: () => api.get("/reviews/seller?page_size=50", authToken ?? undefined),
    enabled: !!authToken && isSeller,
  });
  const sellerReviewsList = sellerReviewsData?.items || [];

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
      api.patch(`/deployments/${deploymentId}/domain`, {}, authToken ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries(["deployments"]);
      alert("Custom domain unlinked successfully!");
    },
    onError: (err) => {
      alert("Failed to unlink domain: " + err.message);
    }
  });

  // Fetch Marketplace Templates for Dashboard Recommendations
  const { data: marketplaceTemplatesRes } = useQuery({
    queryKey: ["marketplace-templates-dashboard"],
    queryFn: () => api.get("/templates?page_size=3"),
  });
  const recommendedTemplates = marketplaceTemplatesRes?.items || [];

  // Fetch Deployments
  const { data: deploymentsData = [], isLoading: deploymentsLoading, refetch: refetchDeployments } = useQuery({
    queryKey: ["deployments"],
    queryFn: () => api.get("/deployments/", authToken ?? undefined),
    enabled: !!authToken && activeTab === "deployments",
  });

  // Strip ANSI escape codes from terminal output
  const stripAnsi = (str) => str.replace(/\x1B\[[0-9;]*[mGKHFJABCDETSTNHR]/g, "").replace(/\x1B[()][AB012]/g, "");

  // Poll logs for active building deployments
  useEffect(() => {
    let intervalId;
    if (isConsoleOpen && selectedDeployment) {
      const fetchLogs = async () => {
        try {
          const data = await api.get(`/deployments/${selectedDeployment.id}`, authToken ?? undefined);
          setActiveConsoleLogs(data.logs || "");
          setActiveConsoleStatus(data.status);
          if (data.status !== "building") {
            clearInterval(intervalId);
            // Update selectedDeployment with fresh data (including live_url)
            setSelectedDeployment(data);
            refetchDeployments();
          }
        } catch (err) {
          console.error("Failed to fetch logs:", err);
        }
      };

      fetchLogs();
      intervalId = setInterval(fetchLogs, 1500);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isConsoleOpen, selectedDeployment?.id, authToken, refetchDeployments]);

  // Auto-scroll build console to bottom
  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollTop = consoleEndRef.current.scrollHeight;
    }
  }, [activeConsoleLogs, isConsoleOpen]);

  // Calculated stats for seller
  const sellerTemplatesList = Array.isArray(templateResponse) ? templateResponse : [];
  const sellerTotalViews = sellerTemplatesList.reduce((sum, t) => sum + (t.views_count || 0), 0);
  const sellerTotalDownloads = sellerTemplatesList.reduce((sum, t) => sum + (t.downloads_count || 0), 0);
  const sellerRatedTemplates = sellerTemplatesList.filter(t => (t.rating_count || 0) > 0);
  const sellerAverageRating = sellerRatedTemplates.length > 0 
    ? (sellerRatedTemplates.reduce((sum, t) => sum + (t.rating_avg || 0), 0) / sellerRatedTemplates.length).toFixed(1)
    : "0.0";
  const sellerConversionRate = sellerTotalViews > 0 
    ? ((sellerTotalDownloads / sellerTotalViews) * 100).toFixed(1) + "%" 
    : "0.0%";

  // Auto-detect build configurations based on selected template framework
  useEffect(() => {
    if (!deployTemplateId) return;
    
    if (deployTemplateId === "mock-project-id") {
      setDeployBranch("main");
      setDeployBuildCommand("none");
      setDeployOutputDir(".");
      return;
    }

    const matched = sellerTemplatesList.find(t => t.id === deployTemplateId);
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
      alert("Template deleted successfully!");
    },
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

  // Download Trigger Mutation
  const triggerDownload = useMutation({
    mutationFn: ({ templateId, format }) =>
      api.post(
        `/templates/${templateId}/download?format=${format}`,
        {},
        authToken ?? undefined
      ),
    onSuccess: (data) => {
      if (data?.download_url) {
        window.open(data.download_url, "_blank");
      }
    },
  });

  // Avatar Upload handler
  const handleAvatarUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      alert("File size exceeds 2MB limit.");
      return;
    }

    try {
      setUploadingAvatar(true);
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("http://localhost:8000/api/v1/files/upload", {
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
      setAvatarUrl(data.url);
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
      const res = await fetch("http://localhost:8000/api/v1/auth/me", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({
          full_name: fullName,
          username: username,
          bio: bio,
          avatar_url: avatarUrl
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to update profile details");
      }
      // Refresh profile data
      await useAuthStore.getState().fetchProfile();
      alert("Profile updated successfully!");
    } catch (err) {
      console.error(err);
      alert(err.message);
    } finally {
      setSavingProfile(false);
    }
  };

  // --- SELLER FORMS & WIZARD STATE ---
  const [wizardStep, setWizardStep] = useState(1);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [shortDesc, setShortDesc] = useState("");
  const [desc, setDesc] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [framework, setFramework] = useState("nextjs");
  const [price, setPrice] = useState("49");
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
  const [thumbnailFile, setThumbnailFile] = useState(null);

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
  const [wizardPrimaryColor, setWizardPrimaryColor] = useState("#6366f1");
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
  const [payoutMethod, setPayoutMethod] = useState("paypal");
  const [payoutDetails, setPayoutDetails] = useState("seller@aisitestudio.com");
  const [payoutHistory, setPayoutHistory] = useState([]);

  // AI custom prompt generator tool
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
    const res = await fetch("http://localhost:8000/api/v1/files/upload", {
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
    return data.url;
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

      const res = await fetch("http://localhost:8000/api/v1/templates/analyze-zip", {
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

      setAnalysisLogs(prev => [...prev, "AI analysis complete!"]);
      setAnalysisProgress(100);
      setAnalysisResult(data);

      setTitle(data.project_name || "");
      setSlug((data.project_name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-"));
      setShortDesc(data.ai_description || "");
      setDesc(data.ai_description || "");
      
      const fw = (data.framework_detected || "html").toLowerCase();
      if (fw.includes("next")) setFramework("nextjs");
      else if (fw.includes("react")) setFramework("react");
      else if (fw.includes("vue") || fw.includes("nuxt")) setFramework("vue");
      else setFramework("html");

      setTags(data.ai_tags ? data.ai_tags.join(", ") : "");
      setKeywords(data.ai_tags ? data.ai_tags.slice(0, 4).join(", ") : "");
      setMetaTitle((data.project_name || "") + " - Website Template");
      setMetaDesc(data.ai_description || "");

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
      "Running AI model assessment..."
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
      const res = await fetch("http://localhost:8000/api/v1/templates/analyze-git", {
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

      setAnalysisLogs(prev => [...prev, "AI analysis complete!"]);
      setAnalysisProgress(100);
      setAnalysisResult(data);

      setTitle(data.project_name || "");
      setSlug((data.project_name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-"));
      setShortDesc(data.ai_description || "");
      setDesc(data.ai_description || "");
      
      const fw = (data.framework_detected || "html").toLowerCase();
      if (fw.includes("next")) setFramework("nextjs");
      else if (fw.includes("react")) setFramework("react");
      else if (fw.includes("vue") || fw.includes("nuxt")) setFramework("vue");
      else setFramework("html");

      setTags(data.ai_tags ? data.ai_tags.join(", ") : "");
      setKeywords(data.ai_tags ? data.ai_tags.slice(0, 4).join(", ") : "");
      setMetaTitle((data.project_name || "") + " - Website Template");
      setMetaDesc(data.ai_description || "");

      setStoredZipUrl(data.stored_zip_url);

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

      const res = await fetch(`http://localhost:8000/api/v1/templates/git-repos?${query.toString()}`, {
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
      const res = await fetch("http://localhost:8000/api/v1/auth/connect-github", {
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
      const res = await fetch("http://localhost:8000/api/v1/auth/disconnect-github", {
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

      // 4. Upload Video file if exists (seller with GitHub connected)
      let finalVideoUrl = null;
      if (videoFile) {
        finalVideoUrl = await uploadFileHelper(videoFile, "video preview");
      }

      // 5. Submit Template details as JSON to match TemplateCreate schema
      const payload = {
        title,
        slug: slug || title.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
        short_description: shortDesc || "Template short description",
        description: desc || "Template full description",
        price: Number(price),
        original_price: salePrice ? Number(salePrice) : null,
        is_free: Number(price) === 0,
        is_on_sale: !!salePrice,
        thumbnail_url: finalThumbnailUrl,
        preview_url: demoUrl || null,
        video_url: finalVideoUrl,
        gallery_images: [],
        category_id: categoryId,
        tags: tags ? tags.split(",").map(t => t.trim()) : [],
        industry: analysisResult ? (analysisResult.industry ? analysisResult.industry.join(", ") : null) : null,
        color_scheme: analysisResult ? (analysisResult.color_palette ? analysisResult.color_palette.join(", ") : null) : null,
        framework: framework,
        pages_count: analysisResult ? (analysisResult.pages ? analysisResult.pages.length : 1) : 1,
        has_dark_mode: analysisResult ? !!analysisResult.dark_mode : false,
        is_responsive: analysisResult ? !!analysisResult.responsive_analysis?.mobile : true,
        is_rtl_supported: false,
        is_ai_ready: !!analysisResult,
        compatibility: ["Chrome", "Firefox", "Safari", "Edge"],
        version: "1.0.0",
        license_type: licenseType === "extended" ? "extended" : "regular",
        is_featured: false,
        is_bestseller: false,
        developer_name: user?.fullName ?? user?.firstName ?? "Site Studio Creator",
        developer_avatar: user?.imageUrl ?? null,
        included_pages: analysisResult ? (analysisResult.pages || []) : [],
        seo_keywords: keywords ? keywords.split(",").map(k => k.trim()) : [],
        status: "published",
        download_assets: finalZipUrl ? { "zip": finalZipUrl } : {},
        changelog: analysisResult ? { "ai_report": analysisResult } : null
      };

      const res = await fetch("http://localhost:8000/api/v1/templates", {
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

  if (!authToken || statsLoading) {
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

  return (
    <>
      <Navbar />
      <div className="db-page-wrapper">
        <div className="db-container">
          {/* Dashboard Header Banner */}
          <div className="db-user-header">
            <div className="db-user-info-flex">
              <div className="db-user-avatar">
                {user?.imageUrl ? (
                  <Image src={user.imageUrl} alt="Avatar" fill className="object-cover" />
                ) : (
                  <div className="db-user-avatar-text">
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

            <div className="db-header-actions">
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
          <div className="db-grid">
            {/* Sidebar Navigation */}
            <div className="db-sidebar">
              {(() => {
                const sidebarTabs = isAdmin
                  ? [
                    { id: "admin-users", label: "Users", icon: User },
                    { id: "admin-templates", label: "Templates Queue", icon: Code },
                    { id: "seller-templates", label: "My Templates", icon: Folder },
                    { id: "seller-upload", label: "Upload Template", icon: Plus },
                    { id: "admin-payments", label: "Payments Ledger", icon: CreditCard },
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
                      { id: "seller-marketing", label: "Marketing", icon: Megaphone },
                      { id: "seller-followers", label: "Followers", icon: Users },
                      { id: "seller-messages", label: "Customer Messages", icon: MessageSquare },
                      { id: "seller-payouts", label: "Payouts", icon: Wallet },
                      { id: "seller-licenses", label: "Licenses", icon: FileText },
                      { id: "settings", label: "Profile Settings", icon: Settings },
                    ]
                    : [
                      { id: "buyer-home", label: "Dashboard", icon: LayoutDashboard },
                      { id: "marketplace-redirect", label: "Marketplace", icon: ShoppingBag, isLink: true, url: "/marketplace" },
                      { id: "buyer-templates", label: "My Templates", icon: Folder },
                      { id: "ai-projects", label: "AI Projects", icon: Cpu },
                      { id: "my-websites", label: "My Websites", icon: Globe },
                      { id: "deployments", label: "Deployments", icon: Zap, comingSoon: true },
                      { id: "wishlist", label: "Wishlist", icon: Heart },
                      { id: "buyer-following", label: "Following Sellers", icon: Users },
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

            {/* Right Side Panels */}
            <div className="db-main-content">

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
                      Deploy your templates instantly, customize typography and color schemes in your Brand Kit, or invoke custom AI iterations on your active project workspaces.
                    </p>
                    <div className="db-banner-btn-group">
                      <button
                        onClick={() => setActiveTab("ai-projects")}
                        className="db-banner-btn primary"
                      >
                        <Cpu className="w-3.5 h-3.5" /> Launch AI Workspace
                      </button>
                      <Link
                        href="/marketplace"
                        className="db-banner-btn secondary"
                        style={{ textDecoration: "none" }}
                      >
                        <ShoppingBag className="w-3.5 h-3.5" /> Browse Marketplace
                      </Link>
                    </div>
                  </motion.div>

                  {/* Summary Metric Cards */}
                  <div className="db-metrics-grid">
                    {[
                      { label: "Purchased Templates", value: stats?.purchases ?? orders.length, icon: Folder, desc: "Ready for download" },
                      { label: "AI website projects", value: 0, icon: Cpu, desc: "Active AI workspaces" },
                      { label: "Live Websites", value: 0, icon: Globe, desc: "Configured custom domains" },
                      { label: "Hosting Deployments", value: 0, icon: Zap, desc: "Continuous build integrations" },
                      { label: "Total Platform Spent", value: formatPrice(totalSpent), icon: CreditCard, desc: "Invoice order transactions" },
                    ].map(({ label, value, icon: Icon, desc }) => (
                      <motion.div
                        key={label}
                        whileHover={{ y: -4, scale: 1.01 }}
                        transition={{ duration: 0.2 }}
                        className="db-card"
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

              {/* === BUYER TEMPLATES (UNIFIED MY TEMPLATES) === */}
              {activeTab === "buyer-templates" && (
                <div className="glass-premium p-8 space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/20 pb-4">
                    <div>
                      <h3 className="font-bold text-lg">My Templates</h3>
                      <p className="text-sm text-muted-foreground">Manage, view, and customize your templates.</p>
                    </div>
                    {/* Segmented Control */}
                    {(isSeller || isAdmin) && (
                      <div className="flex gap-1.5 p-1 bg-muted/40 border border-border/20 rounded-xl self-start">
                        <button
                          type="button"
                          onClick={() => setTemplatesSubTab("purchased")}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                            templatesSubTab === "purchased"
                              ? "bg-primary text-white shadow-lg shadow-primary/20"
                              : "text-muted-foreground hover:text-white"
                          }`}
                        >
                          Purchased
                        </button>
                        <button
                          type="button"
                          onClick={() => setTemplatesSubTab("uploaded")}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                            templatesSubTab === "uploaded"
                              ? "bg-primary text-white shadow-lg shadow-primary/20"
                              : "text-muted-foreground hover:text-white"
                          }`}
                        >
                          Uploaded
                        </button>
                      </div>
                    )}
                  </div>

                  {templatesSubTab === "purchased" ? (
                    <>
                      {orders.filter(o => o.status === "completed").flatMap(o => o.items).length === 0 ? (
                        <div className="text-center py-12 text-muted-foreground border border-dashed border-border/40 rounded-xl bg-card/5">
                          <Folder className="w-8 h-8 text-primary mx-auto mb-3 opacity-60" />
                          <p className="text-sm font-semibold text-foreground">No purchased templates</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            Browse the marketplace and purchase templates to see them here.
                          </p>
                          <Link
                            href="/marketplace"
                            className="mt-4 btn-primary"
                          >
                            Explore Marketplace
                          </Link>
                        </div>
                      ) : (
                        <div className="grid sm:grid-cols-2 gap-4">
                          {orders.filter(o => o.status === "completed").flatMap(o => o.items).map((item) => (
                            <div key={item.id} className="glass-premium p-4 flex gap-4 hover:border-primary/25">
                              {item.thumbnail_url && (
                                <div className="relative w-16 h-16 rounded-lg overflow-hidden border border-border/40 flex-shrink-0">
                                  <Image
                                    src={item.thumbnail_url}
                                    alt={item.title}
                                    fill
                                    className="object-cover"
                                  />
                                </div>
                              )}
                              <div className="flex-1 min-w-0 flex flex-col justify-between">
                                <div>
                                  <div className="font-bold text-sm truncate text-foreground/90">
                                    {item.title || "Template Package"}
                                  </div>
                                  <div className="flex items-center justify-between mt-1 flex-wrap gap-2">
                                    <span className="text-[10px] text-muted-foreground bg-primary/5 border border-primary/10 px-1.5 py-0.5 rounded-full inline-block font-semibold uppercase tracking-wider">
                                      {item.license_type} License
                                    </span>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setReviewTemplateId(item.template_id);
                                        setReviewTemplateTitle(item.title || "Template Package");
                                        setReviewRating(5);
                                        setReviewTitle("");
                                        setReviewBody("");
                                        setReviewModalOpen(true);
                                      }}
                                      className="text-[11px] text-primary hover:text-primary/80 transition-colors flex items-center gap-1 font-semibold border-none bg-transparent cursor-pointer p-0"
                                    >
                                      <Star className="w-3 h-3 fill-primary" /> Leave Review
                                    </button>
                                  </div>
                                </div>
                                <div className="flex gap-2 mt-2">
                                  <button
                                    onClick={() => triggerDownload.mutate({ templateId: item.template_id, format: "zip" })}
                                    className="flex-1 btn-secondary"
                                  >
                                    <Download className="w-3.5 h-3.5" /> Source Code
                                  </button>
                                  <a
                                    href={item.preview_url || `http://localhost:8000/api/v1/preview/live/${item.template_id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex-1 btn-primary"
                                  >
                                    <Globe className="w-3.5 h-3.5" /> Live Demo
                                  </a>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="space-y-4">
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead>
                            <tr className="border-y border-border/50 bg-muted/30 text-xs font-semibold uppercase text-muted-foreground">
                              <th className="p-4">Thumbnail</th>
                              <th className="p-4">Title</th>
                              <th className="p-4">Category</th>
                              <th className="p-4">Price</th>
                              <th className="p-4">Status</th>
                              <th className="p-4">Downloads</th>
                              <th className="p-4 text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border/50">
                            {templatesLoading ? (
                              <tr>
                                <td colSpan={7} className="p-8 text-center text-muted-foreground">
                                  <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                                </td>
                              </tr>
                            ) : !templateResponse || templateResponse.length === 0 ? (
                              <tr>
                                <td colSpan={7} className="p-8 text-center text-muted-foreground">
                                  No templates uploaded yet. <button onClick={() => setActiveTab("seller-upload")} className="text-primary underline ml-1">Upload your first template →</button>
                                </td>
                              </tr>
                            ) : (
                              (Array.isArray(templateResponse) ? templateResponse : []).map((item) => (
                                <tr key={item.id} className="hover:bg-muted/10">
                                  <td className="p-4">
                                    <img src={item.thumbnail_url} alt="" className="w-8 h-8 rounded-lg object-cover bg-muted" />
                                  </td>
                                  <td className="p-4 font-semibold text-foreground">{item.title}</td>
                                  <td className="p-4 font-mono text-xs uppercase">{item.framework}</td>
                                  <td className="p-4">{formatPrice(item.price)}</td>
                                  <td className="p-4">
                                    <span className="px-2 py-0.5 bg-green-500/10 text-green-500 text-[10px] rounded-full font-semibold">Published</span>
                                  </td>
                                  <td className="p-4 font-mono text-xs">{item.downloads_count}</td>
                                  <td className="p-4 text-right">
                                    <div className="flex items-center justify-end gap-1.5">
                                      <button onClick={() => alert("Analytics view for " + item.title)} className="p-1.5 text-muted-foreground hover:text-primary transition-colors" title="Analytics"><BarChart3 className="w-4 h-4" /></button>
                                      <button
                                        onClick={() => {
                                          if (confirm("Are you sure you want to delete this template?")) {
                                            deleteMutation.mutate(item.id);
                                          }
                                        }}
                                        className="p-1.5 text-muted-foreground hover:text-red-400 transition-colors"
                                        title="Delete Template"
                                      >
                                        <Trash2 className="w-4 h-4" />
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* === AI PROJECTS === */}
              {activeTab === "ai-projects" && (
                <div className="glass-premium p-8 space-y-6">
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="font-bold text-lg text-foreground">AI Generated Website Projects</h3>
                      <p className="text-sm text-muted-foreground">Manage your active AI generated prototypes and template sandboxes.</p>
                    </div>
                  </div>

                  {templatesLoading ? (
                    <div className="text-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" />
                      <p className="text-xs text-muted-foreground mt-2">Loading your AI projects...</p>
                    </div>
                  ) : !templateResponse || templateResponse.length === 0 ? (
                    <div className="grid md:grid-cols-2 gap-6">
                      <div className="text-center py-12 text-muted-foreground border border-dashed border-border/40 rounded-xl bg-muted/5 flex flex-col justify-center items-center">
                        <Cpu className="w-8 h-8 text-primary mx-auto mb-3 opacity-60" />
                        <p className="text-sm font-semibold text-foreground">No AI Generated Projects</p>
                        <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                          You haven't generated any AI prototype workspaces yet. Explore templates in the marketplace to start customizing them with AI.
                        </p>
                      </div>

                      <div className="glass p-6 rounded-xl border border-primary/30 bg-primary/5 flex flex-col justify-between">
                        <div>
                          <h4 className="font-bold text-lg text-foreground mb-2">Create New Project.</h4>
                          <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
                            Choose a responsive template designed for food services, then customize it using our AI editor to match your branding. For your site generation, try this prompt: <br/><br/>
                            <span className="italic text-primary/90 block border-l-2 border-primary/50 pl-3">
                              'Create a professional, modern cafeteria website featuring a digital menu, a daily specials section, an online ordering integration, and a clean, high-contrast aesthetic that highlights food photography.'
                            </span>
                            <br/>
                            Our AI will then generate the structure and layout for you.
                          </p>
                        </div>
                        <Link
                          to="/marketplace/generate"
                          state={{ prompt: "Create a professional, modern cafeteria website featuring a digital menu, a daily specials section, an online ordering integration, and a clean, high-contrast aesthetic that highlights food photography." }}
                          className="px-4 py-2 bg-primary text-white text-sm font-semibold rounded-lg text-center hover:bg-primary/90 transition-colors"
                          style={{ textDecoration: 'none' }}
                        >
                          Try this Prompt Now
                        </Link>
                      </div>
                    </div>
                  ) : (
                    <div className="grid sm:grid-cols-2 gap-6">
                      {templateResponse.map((item) => (
                        <div key={item.id} className="glass p-5 rounded-xl border border-border/40 flex flex-col justify-between hover:border-primary/45 transition-all bg-card/10">
                          <div>
                            <div className="relative w-full rounded-lg overflow-hidden border border-border/40 mb-4 bg-muted/20 flex-shrink-0" style={{ height: '180px' }}>
                              {item.thumbnail_url ? (
                                <img src={item.thumbnail_url} alt="" className="object-cover w-full h-full absolute inset-0" />
                              ) : (
                                <Cpu className="w-8 h-8 text-muted-foreground opacity-50" />
                              )}
                              <span className="absolute top-2 right-2 px-2 py-0.5 bg-background/80 backdrop-blur text-[10px] rounded-full text-primary font-semibold border border-primary/10 uppercase">
                                {item.framework || "HTML"}
                              </span>
                            </div>
                            <h4 className="font-bold text-sm text-foreground mb-1.5" style={{ height: '40px', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: '1.4' }} title={item.title}>
                              {item.title}
                            </h4>
                            <p className="text-[11px] text-muted-foreground mb-4" style={{ height: '32px', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: '1.4' }}>
                              {item.short_description || "AI generated workspace template project."}
                            </p>
                          </div>
                          <div className="space-y-2">
                            <div className="flex gap-2">
                              <Link
                                to={`/preview?template=${item.id}`}
                                className="btn-primary flex-1"
                                style={{ textDecoration: "none" }}
                              >
                                <Wand2 className="w-3.5 h-3.5" /> AI Editor
                              </Link>
                              <a
                                href={`http://localhost:8000/api/v1/preview/live/${item.id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn-secondary flex-1"
                                style={{ textDecoration: "none" }}
                              >
                                <ExternalLink className="w-3.5 h-3.5" /> Live Demo
                              </a>
                            </div>
                            <button
                              onClick={() => {
                                if (confirm("Are you sure you want to delete this AI project?")) {
                                  deleteMutation.mutate(item.id);
                                }
                              }}
                              className="btn-danger w-full"
                            >
                              <Trash2 className="w-3.5 h-3.5" /> Delete Project
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* === MY WEBSITES === */}
              {activeTab === "my-websites" && (
                <div className="glass-premium p-8 space-y-6">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-border/20 pb-4">
                    <div>
                      <h3 className="font-bold text-lg text-foreground">Live Websites & Domains</h3>
                      <p className="text-sm text-muted-foreground">Directly publish your template deployments to your own custom domain.</p>
                    </div>
                    <button
                      onClick={() => {
                        setLinkDomainError("");
                        setCustomDomainInput("");
                        // Set default selected deployment if available
                        const readyDeploys = deploymentsData.filter(d => d.status === "success");
                        if (readyDeploys.length > 0) {
                          setLinkDomainDeploymentId(readyDeploys[0].id);
                        } else {
                          setLinkDomainDeploymentId("");
                        }
                        setLinkDomainModalOpen(true);
                      }}
                      className="btn-primary border-none"
                    >
                      <Plus className="w-4 h-4" /> Link Custom Domain
                    </button>
                  </div>

                  {deploymentsLoading ? (
                    <div className="text-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" />
                      <p className="text-xs text-muted-foreground mt-2">Loading mapped websites...</p>
                    </div>
                  ) : deploymentsData.filter(d => d.custom_domain).length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground border border-dashed border-border/40 rounded-xl bg-card/5">
                      <Globe className="w-8 h-8 text-primary mx-auto mb-3 opacity-60 animate-pulse" />
                      <p className="text-sm font-semibold text-foreground">No custom domains mapped yet</p>
                      <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto leading-relaxed">
                        Publish your website directly under your custom brand. Enter your domain, point your DNS records to our server, and we will handle the deployment SSL certificates and hosting routing.
                      </p>
                      <button
                        onClick={() => {
                          setLinkDomainError("");
                          setCustomDomainInput("");
                          const readyDeploys = deploymentsData.filter(d => d.status === "success");
                          if (readyDeploys.length > 0) {
                            setLinkDomainDeploymentId(readyDeploys[0].id);
                          } else {
                            setLinkDomainDeploymentId("");
                          }
                          setLinkDomainModalOpen(true);
                        }}
                        className="mt-4 px-3.5 py-1.5 bg-muted border border-border/40 hover:bg-muted/80 text-foreground text-xs font-semibold rounded-lg transition-all cursor-pointer"
                      >
                        Link a Custom Domain Now
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead>
                            <tr className="border-b border-border/50 text-xs font-semibold text-muted-foreground uppercase">
                              <th className="pb-3">Custom Domain</th>
                              <th className="pb-3">Target Project</th>
                              <th className="pb-3">Provider</th>
                              <th className="pb-3">Status</th>
                              <th className="pb-3 text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {deploymentsData.filter(d => d.custom_domain).map((deploy) => (
                              <tr key={deploy.id} className="border-b border-border/40 hover:bg-muted/5 transition-colors">
                                <td className="py-4">
                                  <a
                                    href={deploy.live_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="font-bold text-sm text-primary hover:underline flex items-center gap-1.5 text-decoration-none"
                                  >
                                    <Globe className="w-3.5 h-3.5" />
                                    {deploy.custom_domain}
                                    <ExternalLink className="w-3 h-3 text-muted-foreground" />
                                  </a>
                                </td>
                                <td className="py-4">
                                  <div className="font-semibold text-foreground">{deploy.project_name}</div>
                                  <div className="text-[10px] text-muted-foreground">ID: {deploy.id.slice(0, 8)}...</div>
                                </td>
                                <td className="py-4">
                                  <span className="text-xs capitalize font-medium text-slate-300">
                                    {deploy.provider === "vercel" ? "▲ Vercel" : deploy.provider === "netlify" ? "⧉ Netlify" : "🕮 Pages"}
                                  </span>
                                </td>
                                <td className="py-4">
                                  <span className={`status-badge ${deploy.status} inline-flex items-center gap-1`}>
                                    {deploy.status === "building" && <Loader2 className="w-2.5 h-2.5 animate-spin" />}
                                    {deploy.status === "success" && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />}
                                    {deploy.status === "failed" && <span className="w-1.5 h-1.5 rounded-full bg-red-500" />}
                                    {deploy.status === "building" ? "Building" : deploy.status === "success" ? "Active" : "Failed"}
                                  </span>
                                </td>
                                <td className="py-4 text-right">
                                  <button
                                    onClick={() => {
                                      if (confirm(`Are you sure you want to unlink the custom domain "${deploy.custom_domain}" from this website?`)) {
                                        unlinkDomainMutation.mutate(deploy.id);
                                      }
                                    }}
                                    disabled={unlinkDomainMutation.isPending}
                                    className="btn-danger"
                                  >
                                    Unlink Domain
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* DNS Records Guide */}
                      <div className="p-5 border border-primary/20 bg-primary/5 rounded-xl space-y-3">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                          <Info className="w-4 h-4" /> DNS Configuration Guide
                        </h4>
                        <p className="text-xs text-slate-300 leading-relaxed">
                          To complete linking your custom domains, log into your domain registrar dashboard (e.g. GoDaddy, Namecheap) and create the following DNS records:
                        </p>
                        <div className="grid sm:grid-cols-2 gap-4 text-xs">
                          <div className="p-3 bg-slate-900/60 rounded-lg border border-border/40">
                            <span className="font-bold text-foreground block mb-1">A Record (for root domain, e.g. mybrand.com)</span>
                            <div className="space-y-1 font-mono text-[11px] text-slate-300">
                              <div>Host: <span className="text-primary">@</span></div>
                              <div>Value / Points to: <span className="text-primary">76.76.21.21</span></div>
                              <div>TTL: <span className="text-muted-foreground">Automatic / 3600</span></div>
                            </div>
                          </div>
                          <div className="p-3 bg-slate-900/60 rounded-lg border border-border/40">
                            <span className="font-bold text-foreground block mb-1">CNAME Record (for www subdomain, e.g. www.mybrand.com)</span>
                            <div className="space-y-1 font-mono text-[11px] text-slate-300">
                              <div>Host: <span className="text-primary">www</span></div>
                              <div>Value / Points to: <span className="text-primary">publish.aisitestudio.com</span></div>
                              <div>TTL: <span className="text-muted-foreground">Automatic / 3600</span></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}


              {/* === DEPLOYMENTS === */}
              {activeTab === "deployments" && (
                <div className="glass-premium p-8 space-y-6">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-lg text-foreground">Continuous Deployments</h3>
                        <span className="text-[10px] bg-primary/20 text-primary px-2 py-0.5 rounded-full font-semibold border border-primary/30 uppercase tracking-wider">
                          Coming Soon
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground">Publish your websites and AI templates to Vercel, Netlify, or GitHub Pages.</p>
                    </div>
                    <button
                      onClick={() => {
                        const available = [...sellerTemplatesList];
                        if (available.length > 0) {
                          setDeployTemplateId(available[0].id);
                          setDeployProjectName(available[0].title);
                        } else {
                          setDeployTemplateId("mock-project-id");
                          setDeployProjectName("AI Restaurant Prototype");
                        }
                        setIsDeployModalOpen(true);
                      }}
                      className="btn-primary"
                    >
                      <Plus className="w-4 h-4" /> Deploy a Project
                    </button>
                  </div>

                  {deploymentsLoading ? (
                    <div className="text-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" />
                      <p className="text-xs text-muted-foreground mt-2">Loading deployments...</p>
                    </div>
                  ) : deploymentsData.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground border border-dashed border-border/40 rounded-xl bg-card/5">
                      <Zap className="w-8 h-8 text-primary mx-auto mb-3 opacity-60" />
                      <p className="text-sm font-semibold text-foreground">No active deployments</p>
                      <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                        Connect a project template or an AI generated sandbox to start building and hosting.
                      </p>
                      <button
                        onClick={() => {
                          const available = [...sellerTemplatesList];
                          if (available.length > 0) {
                            setDeployTemplateId(available[0].id);
                            setDeployProjectName(available[0].title);
                          } else {
                            setDeployTemplateId("mock-project-id");
                            setDeployProjectName("AI Restaurant Prototype");
                          }
                          setIsDeployModalOpen(true);
                        }}
                        className="mt-4 btn-secondary"
                      >
                        Create First Deployment
                      </button>
                    </div>
                  ) : (
                    <div className="deployments-grid">
                      {deploymentsData.map((deploy) => (
                        <div key={deploy.id} className="deploy-card glass border border-border/40 rounded-xl p-5 flex flex-col justify-between space-y-4 bg-card/10">
                          <div className="space-y-2">
                            <div className="flex justify-between items-start">
                              <h4 className="font-bold text-foreground text-base truncate max-w-[180px]" title={deploy.project_name}>
                                {deploy.project_name}
                              </h4>
                              <span className={`status-badge ${deploy.status}`}>
                                {deploy.status === "building" && <Loader2 className="w-3 h-3 animate-spin" />}
                                {deploy.status === "success" && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />}
                                {deploy.status === "failed" && <span className="w-1.5 h-1.5 rounded-full bg-red-500" />}
                                {deploy.status === "building" ? "Building" : deploy.status === "success" ? "Ready" : "Failed"}
                              </span>
                            </div>
                            
                            <div className="text-xs space-y-1.5 text-slate-300">
                              <div className="flex items-center gap-1.5">
                                <span className="text-muted-foreground">Provider:</span>
                                <span className="font-medium capitalize text-foreground flex items-center gap-1">
                                  {deploy.provider === "vercel" && "▲ Vercel"}
                                  {deploy.provider === "netlify" && "⧉ Netlify"}
                                  {deploy.provider === "github_pages" && "🕮 GitHub Pages"}
                                </span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <span className="text-muted-foreground">Branch:</span>
                                <span className="font-mono bg-muted/40 px-1 py-0.5 rounded text-[10px] text-primary">{deploy.branch}</span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <span className="text-muted-foreground">Subdomain:</span>
                                <span className="text-foreground truncate font-mono max-w-[200px]" title={deploy.subdomain}>
                                  {deploy.subdomain}
                                </span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <span className="text-muted-foreground">Created:</span>
                                <span>{new Date(deploy.created_at).toLocaleDateString()} {new Date(deploy.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                              </div>
                            </div>
                          </div>

                          <div className="pt-2 border-t border-border/20 flex flex-col gap-2">
                            <div className="flex gap-2">
                              {deploy.status === "success" && deploy.live_url && (
                                <a
                                  href={deploy.live_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex-1 py-1.5 bg-primary text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1 hover:bg-primary/90 transition-colors text-center text-decoration-none"
                                >
                                  <ExternalLink className="w-3.5 h-3.5" /> Visit Site
                                </a>
                              )}
                              <button
                                onClick={() => {
                                  setSelectedDeployment(deploy);
                                  setActiveConsoleLogs(deploy.logs || "");
                                  setActiveConsoleStatus(deploy.status);
                                  setIsConsoleOpen(true);
                                }}
                                className="flex-1 py-1.5 bg-muted border border-border/40 hover:bg-muted/80 text-foreground rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition-colors"
                              >
                                <Terminal className="w-3.5 h-3.5" /> {deploy.status === "building" ? "View Build" : "View Logs"}
                              </button>
                            </div>
                            
                            <div className="flex gap-2">
                              {deploy.status !== "building" && (
                                <button
                                  onClick={async () => {
                                    if (confirm("Trigger a new deploy for this project?")) {
                                      try {
                                        const res = await api.post(`/deployments/${deploy.id}/redeploy`, {}, authToken ?? undefined);
                                        refetchDeployments();
                                        setSelectedDeployment(res);
                                        setActiveConsoleLogs(res.logs || "");
                                        setActiveConsoleStatus("building");
                                        setIsConsoleOpen(true);
                                      } catch (err) {
                                        alert("Failed to redeploy: " + err.message);
                                      }
                                    }
                                  }}
                                  className="flex-1 py-1.5 bg-background border border-border/40 hover:bg-muted/30 text-slate-300 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition-colors"
                                >
                                  <RefreshCw className="w-3.5 h-3.5" /> Redeploy
                                </button>
                              )}
                              <button
                                onClick={async () => {
                                  if (confirm("Are you sure you want to remove this deployment?")) {
                                    try {
                                      await api.delete(`/deployments/${deploy.id}`, authToken ?? undefined);
                                      refetchDeployments();
                                    } catch (err) {
                                      alert("Failed to delete: " + err.message);
                                    }
                                  }
                                }}
                                className="py-1.5 px-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-xs font-semibold flex items-center justify-center transition-colors border border-red-500/10"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
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
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Following Sellers</h3>
                    <p className="text-sm text-muted-foreground">Manage and view updates from the sellers you follow.</p>
                  </div>
                  {followingLoading ? (
                    <div className="text-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary" />
                    </div>
                  ) : !following || following.length === 0 ? (
                    <div className="p-8 text-center text-muted-foreground text-sm border border-border/40 rounded-xl">
                      You are not following any sellers yet.
                    </div>
                  ) : (
                    <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
                      {following.map((seller) => (
                        <div key={seller.id} className="p-4 rounded-xl border border-border/40 bg-card/10 flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3">
                            <img src={seller.avatar_url || "https://picsum.photos/seed/avatar/100/100"} alt="" className="w-10 h-10 rounded-full object-cover bg-muted" />
                            <div>
                              <div className="font-bold text-sm text-foreground">{seller.full_name || seller.username}</div>
                              <span className="text-[10px] text-muted-foreground">@{seller.username || "seller"}</span>
                            </div>
                          </div>
                          <Link href={`/marketplace?developer=${seller.full_name || seller.username}`} className="px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary text-xs font-semibold rounded-lg text-decoration-none">
                            View Items
                          </Link>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* === ORDERS === */}
              {activeTab === "orders" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Billing & Order Invoices</h3>
                    <p className="text-sm text-muted-foreground">Download transaction receipts and details.</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-border/50 text-xs font-semibold text-muted-foreground uppercase">
                          <th className="pb-3">Order ID</th>
                          <th className="pb-3">Date</th>
                          <th className="pb-3">Total Amount</th>
                          <th className="pb-3">Payment Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {orders.length === 0 ? (
                          <tr>
                            <td colSpan={4} className="py-6 text-center text-muted-foreground">No transaction history.</td>
                          </tr>
                        ) : (
                          orders.map((o) => (
                            <tr key={o.id} className="border-b border-border/40 hover:bg-muted/10">
                              <td className="py-3 font-mono text-xs text-foreground">{o.order_number}</td>
                              <td className="py-3">{new Date(o.created_at).toLocaleDateString()}</td>
                              <td className="py-3 font-semibold">{formatPrice(o.total)}</td>
                              <td className="py-3">
                                <span className={cn(
                                  "px-2 py-0.5 rounded-full text-[10px] font-semibold",
                                  o.status === "completed" ? "bg-green-500/10 text-green-500" : "bg-yellow-500/10 text-yellow-500"
                                )}>
                                  {o.status.toUpperCase()}
                                </span>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
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
                                        className={`w-3.5 h-3.5 ${
                                          s <= review.rating ? "fill-yellow-400 text-yellow-400" : "text-slate-600"
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
                <div className="space-y-6">
                  {/* Summary Cards */}
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                      { label: "Templates Published", value: stats?.uploaded_templates ?? sellerTemplatesList.length, icon: Folder },
                      { label: "Total Sales", value: 0, icon: ShoppingBag },
                      { label: "Monthly Revenue", value: "$0.00", icon: Coins },
                      { label: "Pending Reviews", value: 0, icon: Star },
                      { label: "Average Rating", value: `${sellerAverageRating} ★`, icon: Sparkles },
                      { label: "Profile Views", value: sellerTotalViews.toString(), icon: Eye },
                      { label: "Followers", value: followers.length.toString(), icon: Users },
                      { label: "Conversion Rate", value: sellerConversionRate, icon: TrendingUp },
                    ].map(({ label, value, icon: Icon }) => (
                      <div key={label} className="glass p-5 rounded-2xl border border-border/40 space-y-2">
                        <div className="flex items-center justify-between text-muted-foreground">
                          <span className="text-[10px] font-bold uppercase tracking-wider">{label}</span>
                          <Icon className="w-4 h-4 text-primary" />
                        </div>
                        <div className="text-2xl font-bold">{value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Graphs */}
                  <div className="grid md:grid-cols-2 gap-6">
                    {/* Sales Graph */}
                    <div className="glass border border-border/40 rounded-2xl p-6 space-y-4">
                      <h4 className="font-bold text-sm text-foreground">Sales Graph</h4>
                      <div className="flex items-center justify-center h-32 border border-dashed border-border/40 rounded-xl">
                        <span className="text-xs text-muted-foreground">No sales recorded. Once buyers purchase your templates, progress logs will plot here.</span>
                      </div>
                    </div>

                    {/* Revenue Metrics */}
                    <div className="glass border border-border/40 rounded-2xl p-6 space-y-4">
                      <div className="flex justify-between items-center border-b border-border/50 pb-2">
                        <h4 className="font-bold text-sm text-foreground">Revenue Metrics</h4>
                      </div>
                      <div className="space-y-3">
                        <div className="text-3xl font-extrabold text-white">$0.00</div>
                        <p className="text-xs text-muted-foreground">Cumulative seller platform revenue generated during the selected period.</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* === SELLER MY TEMPLATES === */}
              {/* === SELLER MY TEMPLATES (UNIFIED MY TEMPLATES) === */}
              {activeTab === "seller-templates" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/20 pb-4">
                    <div>
                      <h3 className="font-bold text-lg">My Templates</h3>
                      <p className="text-sm text-muted-foreground">Manage, view, and customize your templates.</p>
                    </div>
                    {/* Segmented Control */}
                    <div className="flex gap-1.5 p-1 bg-muted/40 border border-border/20 rounded-xl self-start">
                      <button
                        type="button"
                        onClick={() => setTemplatesSubTab("purchased")}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                          templatesSubTab === "purchased"
                            ? "bg-primary text-white shadow-lg shadow-primary/20"
                            : "text-muted-foreground hover:text-white"
                        }`}
                      >
                        Purchased ({orders.filter(o => o.status === "completed").flatMap(o => o.items).length})
                      </button>
                      <button
                        type="button"
                        onClick={() => setTemplatesSubTab("uploaded")}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                          templatesSubTab === "uploaded"
                            ? "bg-primary text-white shadow-lg shadow-primary/20"
                            : "text-muted-foreground hover:text-white"
                        }`}
                      >
                        Uploaded ({templateResponse?.length || 0})
                      </button>
                    </div>
                  </div>

                  {templatesSubTab === "purchased" ? (
                    <>
                      {orders.filter(o => o.status === "completed").flatMap(o => o.items).length === 0 ? (
                        <div className="text-center py-12 text-muted-foreground border border-dashed border-border/40 rounded-xl bg-card/5">
                          <Folder className="w-8 h-8 text-primary mx-auto mb-3 opacity-60" />
                          <p className="text-sm font-semibold text-white">No purchased templates</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            Browse the marketplace and purchase templates to see them here.
                          </p>
                          <Link
                            href="/marketplace"
                            className="mt-4 inline-block px-4 py-2 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/95 transition-colors text-decoration-none"
                          >
                            Explore Marketplace
                          </Link>
                        </div>
                      ) : (
                        <div className="grid sm:grid-cols-2 gap-4">
                          {orders.filter(o => o.status === "completed").flatMap(o => o.items).map((item) => (
                            <div key={item.id} className="p-4 border border-border/40 rounded-xl flex gap-4 bg-muted/5 hover:bg-muted/10 transition-colors">
                              {item.thumbnail_url && (
                                <div className="relative w-16 h-16 rounded-lg overflow-hidden border border-border/40 flex-shrink-0">
                                  <Image
                                    src={item.thumbnail_url}
                                    alt={item.title}
                                    fill
                                    className="object-cover"
                                  />
                                </div>
                              )}
                              <div className="flex-1 min-w-0 flex flex-col justify-between">
                                <div>
                                  <div className="font-bold text-sm truncate text-foreground/90">
                                    {item.title || "Template Package"}
                                  </div>
                                  <div className="flex items-center justify-between mt-1 flex-wrap gap-2">
                                    <span className="text-[10px] text-muted-foreground bg-primary/5 border border-primary/10 px-1.5 py-0.5 rounded-full inline-block font-semibold uppercase tracking-wider">
                                      {item.license_type} License
                                    </span>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setReviewTemplateId(item.template_id);
                                        setReviewTemplateTitle(item.title || "Template Package");
                                        setReviewRating(5);
                                        setReviewTitle("");
                                        setReviewBody("");
                                        setReviewModalOpen(true);
                                      }}
                                      className="text-[11px] text-primary hover:text-primary/80 transition-colors flex items-center gap-1 font-semibold border-none bg-transparent cursor-pointer p-0"
                                    >
                                      <Star className="w-3 h-3 fill-primary" /> Leave Review
                                    </button>
                                  </div>
                                </div>
                                <div className="flex gap-2 mt-2">
                                  <button
                                    onClick={() => triggerDownload.mutate({ templateId: item.template_id, format: "zip" })}
                                    className="flex-1 py-1.5 bg-primary/10 text-primary hover:bg-primary/20 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition-colors"
                                  >
                                    <Download className="w-3.5 h-3.5" /> Source Code
                                  </button>
                                  <a
                                    href={item.preview_url || `http://localhost:8000/api/v1/preview/live/${item.template_id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex-1 py-1.5 bg-primary text-white hover:bg-primary/95 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition-colors text-center text-decoration-none"
                                  >
                                    <Globe className="w-3.5 h-3.5" /> Live Demo
                                  </a>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="space-y-4">
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead>
                            <tr className="border-y border-border/50 bg-muted/30 text-xs font-semibold uppercase text-muted-foreground">
                              <th className="p-4">Thumbnail</th>
                              <th className="p-4">Title</th>
                              <th className="p-4">Category</th>
                              <th className="p-4">Price</th>
                              <th className="p-4">Status</th>
                              <th className="p-4">Downloads</th>
                              <th className="p-4 text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border/50">
                            {templatesLoading ? (
                              <tr>
                                <td colSpan={7} className="p-8 text-center text-muted-foreground">
                                  <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                                </td>
                              </tr>
                            ) : !templateResponse || templateResponse.length === 0 ? (
                              <tr>
                                <td colSpan={7} className="p-8 text-center text-muted-foreground">
                                  No templates uploaded yet. <button onClick={() => setActiveTab("seller-upload")} className="text-primary underline ml-1">Upload your first template →</button>
                                </td>
                              </tr>
                            ) : (
                              (Array.isArray(templateResponse) ? templateResponse : []).map((item) => (
                                <tr key={item.id} className="hover:bg-muted/10">
                                  <td className="p-4">
                                    <img src={item.thumbnail_url} alt="" className="w-8 h-8 rounded-lg object-cover bg-muted" />
                                  </td>
                                  <td className="p-4 font-semibold text-foreground">{item.title}</td>
                                  <td className="p-4 font-mono text-xs uppercase">{item.framework}</td>
                                  <td className="p-4">{formatPrice(item.price)}</td>
                                  <td className="p-4">
                                    <span className="px-2 py-0.5 bg-green-500/10 text-green-500 text-[10px] rounded-full font-semibold">Published</span>
                                  </td>
                                  <td className="p-4 font-mono text-xs">{item.downloads_count}</td>
                                  <td className="p-4 text-right">
                                    <div className="flex items-center justify-end gap-1.5">
                                      <button onClick={() => alert("Analytics view for " + item.title)} className="p-1.5 text-muted-foreground hover:text-primary transition-colors" title="Analytics"><BarChart3 className="w-4 h-4" /></button>
                                      <button
                                        onClick={() => {
                                          if (confirm("Are you sure you want to delete this template?")) {
                                            deleteMutation.mutate(item.id);
                                          }
                                        }}
                                        className="p-1.5 text-muted-foreground hover:text-red-400 transition-colors"
                                        title="Delete Template"
                                      >
                                        <Trash2 className="w-4 h-4" />
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* === SELLER UPLOAD TEMPLATE === */}
              {activeTab === "seller-upload" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Upload Website Template</h3>
                    <p className="text-sm text-muted-foreground">Submit your ZIP template or Git repo to register on the platform catalog.</p>
                  </div>

                  {/* Multi-step Header */}
                  <div className="flex items-center gap-2 border-b border-border/50 pb-4 overflow-x-auto scrollbar-none">
                    {[
                      { step: 1, label: "Upload Source" },
                      { step: 2, label: "AI Analysis Audit" },
                      { step: 3, label: "Review & Publish" },
                    ].map((st) => (
                      <div key={st.step} className="flex items-center gap-2 shrink-0">
                        <span className={cn(
                          "w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold",
                          wizardStep === st.step ? "bg-primary text-white" : "bg-muted text-muted-foreground"
                        )}>{st.step}</span>
                        <span className={cn("text-xs font-medium", wizardStep === st.step ? "text-primary" : "text-muted-foreground")}>{st.label}</span>
                        {st.step < 3 && <ChevronRight className="w-3.5 h-3.5 text-slate-600" />}
                      </div>
                    ))}
                  </div>

                  <form onSubmit={handleUpload} className="space-y-6">
                    {/* STEP 1: UPLOAD PROJECT */}
                    {wizardStep === 1 && (
                      <div className="space-y-4 animate-in fade-in duration-200">
                        {/* Tab Switcher */}
                        <div className="flex items-center gap-2 bg-muted/20 p-1 rounded-xl border border-border/45 max-w-xs">
                          <button
                            type="button"
                            onClick={() => { setUploadType("zip"); setStoredZipUrl(""); }}
                            className={cn(
                              "flex-1 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all",
                              uploadType === "zip" ? "bg-primary text-white shadow-sm" : "text-muted-foreground hover:text-foreground"
                            )}
                          >
                            ZIP File
                          </button>
                          <button
                            type="button"
                            onClick={() => { setUploadType("git"); setZipFile(null); }}
                            className={cn(
                              "flex-1 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all",
                              uploadType === "git" ? "bg-primary text-white shadow-sm" : "text-muted-foreground hover:text-foreground"
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
                              if (file && file.name.endsWith(".zip")) {
                                handleZipAnalysis(file);
                              } else {
                                alert("Please upload a valid ZIP archive.");
                              }
                            }}
                          >
                            <div className="db-upload-dropzone-inner">
                              <FileUp className="w-12 h-12 text-primary animate-pulse mb-4 mx-auto" />
                              <h4 className="font-bold text-base text-foreground mb-1">Upload Website Template</h4>
                              <p className="text-xs text-muted-foreground mb-4">Drag & Drop ZIP File or click to browse</p>
                              <input 
                                type="file" 
                                accept=".zip" 
                                id="zip-uploader"
                                className="hidden" 
                                onChange={(e) => {
                                  const file = e.target.files[0];
                                  if (file) handleZipAnalysis(file);
                                }}
                              />
                              <label htmlFor="zip-uploader" className="px-4 py-2 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/95 transition-all cursor-pointer inline-block">
                                Browse Files
                              </label>
                            </div>
                            
                            <div className="db-upload-tech-grid">
                              <div className="db-upload-tech-title">Supported Frameworks & Layouts</div>
                              <div className="db-upload-tech-badges">
                                {["HTML", "CSS", "JavaScript", "React", "Next.js", "Vue", "Angular", "Astro"].map(tech => (
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
                              <div className="db-upload-dropzone p-10 flex flex-col items-center gap-6">
                                <div className="relative">
                                  <div className="w-20 h-20 rounded-3xl bg-[#24292e] flex items-center justify-center shadow-2xl shadow-black/30">
                                    <svg className="w-11 h-11 text-white" viewBox="0 0 24 24" fill="currentColor">
                                      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
                                    </svg>
                                  </div>
                                  {/* animated ring */}
                                  <div className="absolute -inset-1 rounded-3xl border-2 border-primary/20 animate-pulse" />
                                </div>

                                <div className="text-center space-y-2 max-w-xs">
                                  <h4 className="font-bold text-lg text-foreground">Connect GitHub</h4>
                                  <p className="text-xs text-muted-foreground leading-relaxed">
                                    Authorise AI Site Studio on GitHub and we'll automatically load all your repositories. No keys, no copy-pasting.
                                  </p>
                                </div>

                                <div className="flex flex-col items-center gap-3 w-full max-w-xs">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      // Pass current JWT so the backend links GitHub to this account, not creates a new user
                                      const API_BASE = "http://localhost:8000/api/v1";
                                      window.location.href = `${API_BASE}/auth/github/login?token=${authToken}&redirect=/dashboard?tab=seller-upload`;
                                    }}
                                    className="w-full py-3 bg-[#24292e] hover:bg-[#1a1e23] text-white text-sm font-bold rounded-xl transition-all flex items-center justify-center gap-2.5 shadow-lg shadow-black/20 hover:shadow-black/30 hover:-translate-y-0.5"
                                  >
                                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                                      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
                                    </svg>
                                    Continue with GitHub
                                  </button>

                                  <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                                    <span className="flex items-center gap-1"><ShieldCheck className="w-3 h-3 text-green-500" /> Secure OAuth 2.0</span>
                                    <span>·</span>
                                    <span className="flex items-center gap-1"><Key className="w-3 h-3 text-primary" /> No passwords stored</span>
                                    <span>·</span>
                                    <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-blue-400" /> One-time setup</span>
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
                                    <div className="w-7 h-7 rounded-lg bg-[#24292e] flex items-center justify-center">
                                      <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
                                    </div>
                                    <div>
                                      <p className="text-sm font-bold text-foreground">Your Repositories</p>
                                      <p className="text-[10px] text-muted-foreground">{fetchedRepos.length} repos found · Click any to import</p>
                                    </div>
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => { setFetchedRepos([]); fetchGithubRepos(); }}
                                    disabled={fetchingRepos}
                                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-muted-foreground hover:text-foreground hover:border-primary transition-all"
                                  >
                                    <Loader2 className={cn("w-3 h-3", fetchingRepos && "animate-spin")} />
                                    Refresh
                                  </button>
                                </div>

                                {/* STATE B-loading: skeletons */}
                                {fetchingRepos && (
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    {[1, 2, 3, 4].map(i => (
                                      <div key={i} className="p-4 rounded-xl border border-border/50 bg-muted/10 space-y-2 animate-pulse">
                                        <div className="h-3.5 bg-muted/40 rounded w-2/3" />
                                        <div className="h-2.5 bg-muted/30 rounded w-full" />
                                        <div className="h-2.5 bg-muted/20 rounded w-1/2" />
                                        <div className="flex gap-2 pt-1">
                                          <div className="h-5 w-14 bg-muted/30 rounded-full" />
                                          <div className="h-5 w-10 bg-muted/20 rounded-full" />
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* STATE B-loaded: repo cards */}
                                {!fetchingRepos && fetchedRepos.length > 0 && (
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-80 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-border">
                                    {fetchedRepos.map((repo) => (
                                      <div
                                        key={repo.id || repo.clone_url}
                                        className={cn(
                                          "group p-4 rounded-xl border bg-card/50 hover:border-primary hover:bg-primary/5 transition-all cursor-pointer space-y-2",
                                          gitUrl === repo.clone_url ? "border-primary bg-primary/5" : "border-border/50"
                                        )}
                                        onClick={() => setGitUrl(repo.clone_url)}
                                      >
                                        {/* Repo header */}
                                        <div className="flex items-start justify-between gap-2">
                                          <div className="flex items-center gap-1.5 min-w-0">
                                            <Folder className="w-3.5 h-3.5 text-primary shrink-0" />
                                            <span className="text-sm font-bold text-foreground truncate">{repo.name}</span>
                                          </div>
                                          <span className={cn(
                                            "text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-full shrink-0",
                                            repo.private ? "bg-amber-500/10 text-amber-500" : "bg-green-500/10 text-green-500"
                                          )}>
                                            {repo.private ? "Private" : "Public"}
                                          </span>
                                        </div>

                                        {/* Description */}
                                        <p className="text-[10px] text-muted-foreground line-clamp-2 leading-relaxed">
                                          {repo.description || "No description provided"}
                                        </p>

                                        {/* Meta chips */}
                                        <div className="flex items-center gap-2 flex-wrap">
                                          {repo.language && (
                                            <span className="inline-flex items-center gap-1 text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-primary/10 text-primary">
                                              <span className="w-1.5 h-1.5 rounded-full bg-primary inline-block" />
                                              {repo.language}
                                            </span>
                                          )}
                                          {repo.stargazers_count > 0 && (
                                            <span className="inline-flex items-center gap-0.5 text-[9px] font-semibold text-muted-foreground">
                                              <Star className="w-2.5 h-2.5 fill-yellow-400 text-yellow-400" />
                                              {repo.stargazers_count}
                                            </span>
                                          )}
                                          {repo.updated_at && (
                                            <span className="text-[9px] text-muted-foreground/60 ml-auto">
                                              {new Date(repo.updated_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                                            </span>
                                          )}
                                        </div>

                                        {/* Import button */}
                                        <button
                                          type="button"
                                          onClick={(e) => { e.stopPropagation(); setGitUrl(repo.clone_url); handleGitAnalysis(repo.clone_url); }}
                                          className="w-full mt-1 py-1.5 bg-primary text-white text-[10px] font-bold rounded-lg hover:bg-primary/90 transition-all flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100"
                                        >
                                          <Zap className="w-3 h-3" /> Import & Analyze
                                        </button>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* Empty state */}
                                {!fetchingRepos && fetchedRepos.length === 0 && (
                                  <div className="text-center py-8 text-muted-foreground text-xs">
                                    No repositories found. Click Refresh or check your token permissions.
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Manual URL fallback — always visible */}
                            <div className="space-y-2">
                              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                                {user?.has_github_token ? "Or paste a public / GitLab / Bitbucket URL:" : "Or paste any public Git URL:"}
                              </p>
                              <div className="flex gap-2">
                                <input
                                  type="text"
                                  placeholder="https://github.com/username/repository-name.git"
                                  value={gitUrl}
                                  onChange={(e) => setGitUrl(e.target.value)}
                                  className="flex-1 px-4 py-2.5 rounded-xl border border-border bg-background/50 text-sm focus:outline-none focus:ring-2 focus:ring-primary text-foreground"
                                />
                                <button
                                  type="button"
                                  onClick={() => handleGitAnalysis()}
                                  disabled={!gitUrl}
                                  className="px-4 py-2.5 bg-primary text-white text-xs font-bold rounded-xl hover:bg-primary/95 transition-all flex items-center gap-1.5 disabled:opacity-40 shrink-0"
                                >
                                  <Zap className="w-3.5 h-3.5" /> Analyze
                                </button>
                              </div>
                            </div>
                          </div>
                        )}

                        <div className="flex flex-col space-y-2 p-4 bg-muted/10 border border-border/50 rounded-xl">
                          <span className="text-xs text-muted-foreground font-semibold uppercase">Supported uploads:</span>
                          <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                            <span>• ZIP Archive</span>
                            <span>• GitHub Repository</span>
                            <span>• Git URL</span>
                            <span>• Local Folder</span>
                          </div>
                          <span className="text-[10px] text-muted-foreground/60 mt-1">Maximum upload size: 2 GB</span>
                        </div>

                      </div>
                    )}

                    {/* STEP 2: AI ANALYSIS LOADING / RESULTS */}
                    {wizardStep === 2 && (
                      <div className="space-y-6 animate-in fade-in duration-200">
                        {analysisLoading ? (
                          <div className="db-analysis-loading-shell">
                            <div className="db-scanner-icon-container">
                              <Sparkles className="w-12 h-12 text-yellow-500 animate-spin" />
                            </div>
                            <h4 className="font-bold text-base text-foreground text-center">🤖 AI is analyzing your project...</h4>
                            
                            <div className="db-scanner-progress-bar-container">
                              <div className="db-scanner-progress-bar-ascii">
                                {"█".repeat(Math.round(analysisProgress / 5.5)) + "░".repeat(18 - Math.round(analysisProgress / 5.5))}
                              </div>
                              <div className="db-scanner-progress-percentage">{analysisProgress}%</div>
                            </div>

                            <div className="db-scanner-logs-container">
                              {analysisLogs.map((log, i) => (
                                <div key={i} className="db-scanner-log-line">
                                  <span className="text-green-500 mr-2">✓</span> {log}
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : analysisResult ? (
                          <div className="db-ai-report-card">
                            <div className="db-ai-report-header">
                              <div className="flex items-center gap-2">
                                <Sparkles className="w-5 h-5 text-yellow-500" />
                                <h3 className="font-bold text-base text-foreground">AI Project Analysis Audit</h3>
                              </div>
                              <span className="db-ai-badge">Gemini-verified</span>
                            </div>

                            <div className="db-ai-report-grid">
                              {/* Left Column */}
                              <div className="space-y-5">
                                <div className="db-report-block">
                                  <h4 className="db-report-block-title">Tech Stack Detection</h4>
                                  <div className="db-tech-cards-grid">
                                    {[
                                      { label: "Framework", val: analysisResult.framework_detected, version: analysisResult.version },
                                      { label: "Language", val: analysisResult.language },
                                      { label: "CSS", val: analysisResult.css_system },
                                      { label: "UI Library", val: analysisResult.ui_library },
                                      { label: "Animations", val: analysisResult.animation_library },
                                    ].map(tech => (
                                      <div key={tech.label} className="db-tech-report-card">
                                        <span className="text-[10px] text-muted-foreground font-semibold uppercase">{tech.label}</span>
                                        <span className="text-sm font-bold text-foreground mt-0.5">{tech.val} {tech.version ? `v${tech.version}` : ""}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>

                                <div className="db-report-block">
                                  <h4 className="db-report-block-title">Pages Included ({analysisResult.pages.length})</h4>
                                  <div className="db-report-checkbox-list">
                                    {analysisResult.pages.map((p, i) => (
                                      <div key={i} className="db-report-checkbox-item">
                                        <Check className="w-3.5 h-3.5 text-green-500 shrink-0" />
                                        <span>{p}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>

                                <div className="db-report-block">
                                  <h4 className="db-report-block-title">Components Scanned ({analysisResult.components.length})</h4>
                                  <div className="db-report-checkbox-list">
                                    {analysisResult.components.map((c, i) => (
                                      <div key={i} className="db-report-checkbox-item">
                                        <CheckCircle className="w-3.5 h-3.5 text-primary shrink-0" />
                                        <span>{c}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>

                                <div className="db-report-block">
                                  <h4 className="db-report-block-title">Assets Analysis</h4>
                                  <div className="db-assets-report-grid">
                                    {[
                                      { label: "Images", count: analysisResult.assets_count.images },
                                      { label: "SVGs", count: analysisResult.assets_count.svg },
                                      { label: "Icons", count: analysisResult.assets_count.icons },
                                      { label: "Videos", count: analysisResult.assets_count.videos },
                                      { label: "Fonts", count: analysisResult.assets_count.fonts },
                                    ].map(asset => (
                                      <div key={asset.label} className="db-asset-report-item">
                                        <span className="text-xs text-muted-foreground">{asset.label}</span>
                                        <span className="font-mono text-xs font-bold">{asset.count}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>

                              {/* Right Column */}
                              <div className="space-y-5">
                                <div className="db-report-block db-ai-score-block">
                                  <div className="flex justify-between items-center">
                                    <div>
                                      <h4 className="db-report-block-title">Overall Quality Rating</h4>
                                      <div className="flex items-center gap-1 mt-1">
                                        {[1, 2, 3, 4, 5].map(s => (
                                          <Star key={s} className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
                                        ))}
                                        <span className="text-xs text-muted-foreground font-semibold ml-2">({analysisResult.ai_score} / 100)</span>
                                      </div>
                                    </div>
                                    <div className="db-score-circle-big">{analysisResult.ai_score}</div>
                                  </div>

                                  <div className="db-lighthouse-grid mt-4 pt-4 border-t border-border/40">
                                    {[
                                      { name: "Performance", score: analysisResult.performance_scores.performance },
                                      { name: "Accessibility", score: analysisResult.performance_scores.accessibility },
                                      { name: "SEO", score: analysisResult.performance_scores.seo },
                                      { name: "Best Practices", score: analysisResult.performance_scores.best_practices },
                                    ].map(lh => (
                                      <div key={lh.name} className="flex flex-col items-center">
                                        <div className="db-score-circle-sm">{lh.score}</div>
                                        <span className="text-[10px] text-muted-foreground font-bold mt-1">{lh.name}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>

                                <div className="db-report-block">
                                  <h4 className="db-report-block-title">Category Detection</h4>
                                  <div className="space-y-2 mt-2">
                                    {Object.entries(analysisResult.categories).map(([cat, confidence]) => (
                                      <div key={cat} className="space-y-1">
                                        <div className="flex justify-between text-xs font-semibold">
                                          <span>{cat}</span>
                                          <span className="text-muted-foreground">{confidence}%</span>
                                        </div>
                                        <div className="w-full bg-muted/40 h-2 rounded-full overflow-hidden border border-border/10">
                                          <div className="bg-primary h-full rounded-full" style={{ width: `${confidence}%` }} />
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                  <div className="db-report-block">
                                    <h4 className="db-report-block-title">Brand Colors</h4>
                                    <div className="db-palette-row">
                                      {analysisResult.color_palette.map((color, i) => (
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
                                      {analysisResult.typography.map((font, i) => (
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
                                        { label: "Meta Title", check: analysisResult.seo_analysis.meta_title },
                                        { label: "Meta Desc", check: analysisResult.seo_analysis.meta_description },
                                        { label: "OG Tags", check: analysisResult.seo_analysis.og_tags },
                                        { label: "robots.txt", check: analysisResult.seo_analysis.robots_txt },
                                        { label: "sitemap.xml", check: analysisResult.seo_analysis.sitemap_xml },
                                      ].map(item => (
                                        <div key={item.label} className="db-check-item">
                                          <span className={item.check ? "text-green-500 font-bold" : "text-muted-foreground/30 font-bold"}>
                                            {item.check ? "✓" : "✗"}
                                          </span>
                                          <span className="text-xs text-muted-foreground ml-1.5">{item.label}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                  <div className="db-report-block">
                                    <h4 className="db-report-block-title">Accessibility</h4>
                                    <div className="db-checks-list">
                                      {[
                                        { label: "ARIA Labels", check: analysisResult.accessibility.aria_labels },
                                        { label: "Alt Tags", check: analysisResult.accessibility.alt_tags },
                                        { label: "Keyboard Nav", check: analysisResult.accessibility.keyboard_navigation },
                                        { label: "Color Contrast", check: analysisResult.accessibility.contrast_safe },
                                      ].map(item => (
                                        <div key={item.label} className="db-check-item">
                                          <span className={item.check ? "text-green-500 font-bold" : "text-muted-foreground/30 font-bold"}>
                                            {item.check ? "✓" : "✗"}
                                          </span>
                                          <span className="text-xs text-muted-foreground ml-1.5">{item.label}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                </div>

                                <div className="db-report-block">
                                  <h4 className="db-report-block-title text-yellow-500">AI Recommendations</h4>
                                  <ul className="db-suggestions-list">
                                    {analysisResult.ai_suggestions.map((sug, i) => (
                                      <li key={i} className="text-xs text-muted-foreground">{sug}</li>
                                    ))}
                                  </ul>
                                </div>
                              </div>
                            </div>
                            
                            <div className="flex justify-between items-center pt-4 border-t border-border/40">
                              <button 
                                type="button" 
                                onClick={() => setWizardStep(1)}
                                className="px-4 py-2 border border-border hover:border-slate-500 rounded-xl text-xs font-semibold transition-all"
                              >
                                Back to Source Selection
                              </button>
                              <button 
                                type="button" 
                                onClick={() => setWizardStep(3)}
                                className="px-5 py-2.5 bg-primary text-white rounded-xl text-xs font-semibold hover:bg-primary/95 transition-all"
                              >
                                Continue to Review
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="text-center py-8 text-muted-foreground">Analysis error. Please try uploading again.</div>
                        )}
                      </div>
                    )}

                    {/* STEP 3: REVIEW & PUBLISH */}
                    {wizardStep === 3 && (
                      <div className="space-y-6 animate-in fade-in duration-200">
                        {isIncompleteAnalysis ? (
                          <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-start gap-3">
                            <Info className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                            <div className="space-y-1">
                              <p className="text-xs font-bold text-amber-400">
                                ⚠️ Incomplete AI Detection - Action Required
                              </p>
                              <p className="text-[11px] text-slate-300 leading-relaxed">
                                Our AI code audit could not fully determine all metadata (e.g. category mapping, title, framework, or descriptions) from your upload. Please review all fields below and manually answer these questions to ensure buyers can search and find your template accurately.
                              </p>
                            </div>
                          </div>
                        ) : (
                          <div className="p-4 bg-primary/5 border border-primary/20 rounded-xl flex items-center gap-3">
                            <Sparkles className="w-5 h-5 text-primary shrink-0" />
                            <p className="text-xs text-muted-foreground leading-relaxed">
                              <strong>AI Auto-Fill Active:</strong> We have analyzed your project and pre-filled standard catalog details. Please review these parameters and click <strong>Publish Template</strong>.
                            </p>
                          </div>
                        )}

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">
                              Template Title * {isIncompleteAnalysis && !title && <span className="text-amber-500 font-bold normal-case ml-1">(AI could not detect - input manually)</span>}
                            </label>
                            <input
                              type="text"
                              required
                              value={title}
                              onChange={(e) => setTitle(e.target.value)}
                              placeholder="My Awesome SaaS Landing Page"
                              className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Slug</label>
                            <input
                              type="text"
                              value={slug}
                              onChange={(e) => setSlug(e.target.value)}
                              placeholder="my-awesome-saas-landing"
                              className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">
                              Category * {isIncompleteAnalysis && !categoryId && <span className="text-amber-500 font-bold normal-case ml-1">(AI could not detect - select manually)</span>}
                            </label>
                            <select
                              required
                              value={categoryId}
                              onChange={(e) => setCategoryId(e.target.value)}
                              className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                            >
                              <option value="" style={{ backgroundColor: "hsl(var(--card))", color: "hsl(var(--foreground))" }}>Select Category</option>
                              {categories.map((c) => (
                                <option key={c.id} value={c.id} style={{ backgroundColor: "hsl(var(--card))", color: "hsl(var(--foreground))" }}>{c.name}</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">
                              Framework * {isIncompleteAnalysis && !framework && <span className="text-amber-500 font-bold normal-case ml-1">(AI could not detect - select manually)</span>}
                            </label>
                            <select
                              required
                              value={framework}
                              onChange={(e) => setFramework(e.target.value)}
                              className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                            >
                              <option value="nextjs" style={{ backgroundColor: "hsl(var(--card))", color: "hsl(var(--foreground))" }}>Next.js</option>
                              <option value="react" style={{ backgroundColor: "hsl(var(--card))", color: "hsl(var(--foreground))" }}>React</option>
                              <option value="vue" style={{ backgroundColor: "hsl(var(--card))", color: "hsl(var(--foreground))" }}>Vue</option>
                              <option value="html" style={{ backgroundColor: "hsl(var(--card))", color: "hsl(var(--foreground))" }}>HTML</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">License Type</label>
                            <select
                              value={licenseType}
                              onChange={(e) => setLicenseType(e.target.value)}
                              className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                            >
                              <option value="standard" style={{ backgroundColor: "hsl(var(--card))", color: "hsl(var(--foreground))" }}>Standard License</option>
                              <option value="commercial" style={{ backgroundColor: "hsl(var(--card))", color: "hsl(var(--foreground))" }}>Commercial License</option>
                              <option value="extended" style={{ backgroundColor: "hsl(var(--card))", color: "hsl(var(--foreground))" }}>Extended License</option>
                            </select>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Regular Price ($) *</label>
                            <input
                              type="number"
                              required
                              min="0"
                              value={price}
                              onChange={(e) => setPrice(e.target.value)}
                              className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Original Price ($) (For Sale visual)</label>
                            <input
                              type="number"
                              min="0"
                              value={salePrice}
                              onChange={(e) => setSalePrice(e.target.value)}
                              placeholder="Optional sale reference price"
                              className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Thumbnail Cover Photo *</label>
                            <input
                              type="file"
                              accept="image/*"
                              required={!thumbnailFile}
                              onChange={(e) => setThumbnailFile(e.target.files[0])}
                              className="w-full text-xs text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Live Demo URL</label>
                            <input
                              type="url"
                              value={demoUrl}
                              onChange={(e) => setDemoUrl(e.target.value)}
                              placeholder="https://demotemplate.aisitestudio.com"
                              className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                            />
                          </div>
                        </div>

                        {/* Video Upload — only for sellers with GitHub connected */}
                        {user?.has_github_token && (
                          <div className="p-4 border border-primary/20 bg-primary/5 rounded-xl space-y-2">
                            <label className="block text-xs font-semibold text-primary uppercase mb-1 flex items-center gap-1.5">
                              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
                              Video Preview (GitHub Connected)
                            </label>
                            <p className="text-[10px] text-muted-foreground">Upload a walkthrough video of your template. Buyers will see this on the product page.</p>
                            <input
                              type="file"
                              accept="video/*"
                              onChange={(e) => setVideoFile(e.target.files[0])}
                              className="w-full text-xs text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
                            />
                            {videoFile && (
                              <p className="text-[10px] text-green-500 font-semibold">✓ {videoFile.name} selected</p>
                            )}
                          </div>
                        )}

                        <div>
                          <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">
                            Short Description * {isIncompleteAnalysis && !shortDesc && <span className="text-amber-500 font-bold normal-case ml-1">(AI could not detect - fill in manually)</span>}
                          </label>
                          <input
                            type="text"
                            value={shortDesc}
                            onChange={(e) => setShortDesc(e.target.value)}
                            placeholder="A beautiful responsive landing page built with TailwindCSS."
                            className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">
                            Description * {isIncompleteAnalysis && !desc && <span className="text-amber-500 font-bold normal-case ml-1">(AI could not detect - fill in manually)</span>}
                          </label>
                          <textarea
                            rows={4}
                            value={desc}
                            onChange={(e) => setDesc(e.target.value)}
                            placeholder="Describe full product features and customizability..."
                            className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50 h-28"
                          />
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Tags (Comma-separated)</label>
                            <input
                              type="text"
                              value={tags}
                              onChange={(e) => setTags(e.target.value)}
                              placeholder="saas, dashboard, admin, tailwind"
                              className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">SEO Keywords (Comma-separated)</label>
                            <input
                              type="text"
                              value={keywords}
                              onChange={(e) => setKeywords(e.target.value)}
                              placeholder="agency website, landing page, custom nextjs"
                              className="w-full px-4 py-2.5 rounded-xl glass border border-border/50 text-sm focus:outline-none focus:border-primary bg-card/50"
                            />
                          </div>
                        </div>

                        <div className="flex items-center gap-3 pt-2">
                          <input
                            type="checkbox"
                            id="premium"
                            checked={premium}
                            onChange={(e) => setPremium(e.target.checked)}
                            className="w-4 h-4 accent-primary"
                          />
                          <label htmlFor="premium" className="text-xs font-semibold text-foreground uppercase select-none">Premium Template</label>
                        </div>

                        {/* Review step publish button */}
                        <div className="flex justify-between items-center pt-4 border-t border-border/50">
                          <button
                            type="button"
                            onClick={() => setWizardStep(2)}
                            className="px-4 py-2 border border-border hover:border-slate-500 rounded-xl text-xs font-semibold transition-all"
                          >
                            Back to AI Report
                          </button>
                          <button
                            type="submit"
                            disabled={uploading}
                            className="px-5 py-2.5 bg-primary text-white rounded-xl text-xs font-semibold hover:bg-primary/95 transition-all flex items-center gap-1"
                          >
                            {uploading ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Publishing...
                              </>
                            ) : "Publish Template"}
                          </button>
                        </div>
                      </div>
                    )}
                  </form>
                </div>
              )}

              {/* === SELLER SALES ANALYTICS === */}
              {activeTab === "seller-analytics" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Sales Analytics</h3>
                    <p className="text-sm text-muted-foreground">Track detailed metrics of your platform product sales.</p>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {[
                      { label: "Total Sales", value: 0 },
                      { label: "Net Revenue", value: "$0.00" },
                      { label: "Platform Views", value: sellerTotalViews },
                      { label: "Downloads Count", value: sellerTotalDownloads },
                      { label: "Refund Requests", value: 0 },
                      { label: "Conversion Rate", value: sellerConversionRate },
                    ].map((stat, idx) => (
                      <div key={idx} className="p-4 border border-border/50 rounded-xl space-y-1 bg-muted/10">
                        <div className="text-[10px] text-muted-foreground font-semibold uppercase">{stat.label}</div>
                        <div className="text-2xl font-bold text-foreground">{stat.value}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* === SELLER EARNINGS === */}
              {activeTab === "seller-earnings" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="font-bold text-lg">Earnings Balance & Transactions</h3>
                      <p className="text-sm text-muted-foreground">Current withdrawal balance and payouts metrics.</p>
                    </div>
                    <button onClick={() => setActiveTab("seller-payouts")} className="px-3.5 py-2 bg-primary text-white rounded-xl text-xs font-semibold">Request Payout</button>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { label: "Current Balance", value: "$0.00" },
                      { label: "Available to Withdraw", value: "$0.00" },
                      { label: "Pending amount", value: "$0.00" },
                      { label: "Lifetime Earnings", value: "$0.00" },
                    ].map((c, i) => (
                      <div key={i} className="p-4 border border-border/50 rounded-xl space-y-1 bg-muted/10">
                        <div className="text-[10px] text-muted-foreground font-bold uppercase">{c.label}</div>
                        <div className="text-xl font-bold text-foreground">{c.value}</div>
                      </div>
                    ))}
                  </div>

                  <div className="border-t border-border/50 pt-4 space-y-3">
                    <h4 className="font-bold text-sm text-foreground">Recent Transactions</h4>
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/50 text-muted-foreground font-bold">
                          <th className="pb-2">Date</th>
                          <th className="pb-2">Template</th>
                          <th className="pb-2">Buyer</th>
                          <th className="pb-2">Amount</th>
                          <th className="pb-2">Net Income</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td colSpan={5} className="py-4 text-center text-muted-foreground text-xs">
                            No recent earnings transactions found.
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* === SELLER ORDERS === */}
              {activeTab === "seller-orders" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Sales Orders Ledger</h3>
                    <p className="text-sm text-muted-foreground">Log of purchases made on your products.</p>
                  </div>
                  <div className="p-8 text-center text-muted-foreground text-sm border border-border/40 rounded-xl">
                    All completed sales are processed and shown in your earnings transactions history.
                  </div>
                </div>
              )}

              {/* === SELLER REVIEWS === */}
              {activeTab === "seller-reviews" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Client Template Reviews</h3>
                    <p className="text-sm text-muted-foreground">Monitor product feedback and reviews received on your templates.</p>
                  </div>

                  {sellerReviewsLoading ? (
                    <div className="text-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary" />
                    </div>
                  ) : sellerReviewsList.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground border border-dashed border-border/40 rounded-xl bg-card/5">
                      <Star className="w-8 h-8 text-primary mx-auto mb-3 opacity-60 animate-pulse" />
                      <p className="text-sm font-semibold text-white">No customer reviews yet</p>
                      <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                        When buyers purchase and review your uploaded templates, their comments and ratings will automatically appear here.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {sellerReviewsList.map((review) => (
                        <div key={review.id} className="p-5 border border-border/45 rounded-xl space-y-3 bg-muted/5 hover:bg-muted/10 transition-all duration-200">
                          <div className="flex justify-between items-start gap-4">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-full bg-slate-700 overflow-hidden flex items-center justify-center border border-border/40 shrink-0">
                                {review.user?.avatar_url ? (
                                  <img
                                    src={review.user.avatar_url}
                                    alt=""
                                    className="w-full h-full object-cover"
                                  />
                                ) : (
                                  <span className="font-bold text-xs text-slate-300">
                                    {review.user?.fullName?.[0] ?? review.user?.username?.[0] ?? "U"}
                                  </span>
                                )}
                              </div>
                              <div>
                                <div className="font-bold text-xs text-white">
                                  {review.user?.fullName || review.user?.username || "Anonymous Client"}
                                </div>
                                <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                                  <div className="flex">
                                    {[1, 2, 3, 4, 5].map((s) => (
                                      <Star
                                        key={s}
                                        className={`w-3.5 h-3.5 ${
                                          s <= review.rating ? "fill-yellow-400 text-yellow-400" : "text-slate-600"
                                        }`}
                                      />
                                    ))}
                                  </div>
                                  <span className="text-[10px] text-muted-foreground">
                                    on <strong className="text-slate-300">{review.template?.title || "Template"}</strong> &bull; {new Date(review.created_at).toLocaleDateString()}
                                  </span>
                                  {review.is_verified_purchase && (
                                    <span className="text-[9px] bg-green-500/10 text-green-500 border border-green-500/20 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider scale-90">
                                      Verified Purchase
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>

                          <div className="pt-2 border-t border-border/10 space-y-1">
                            <h5 className="font-bold text-xs text-slate-200">{review.title}</h5>
                            <p className="text-xs text-muted-foreground leading-relaxed">{review.body}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* === SELLER PERFORMANCE === */}
              {activeTab === "seller-performance" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Detailed Click Performance</h3>
                    <p className="text-sm text-muted-foreground">Check click conversion and wishlists performance per item.</p>
                  </div>
                  {!sellerTemplatesList || sellerTemplatesList.length === 0 ? (
                    <div className="p-8 text-center text-muted-foreground text-sm border border-border/40 rounded-xl">
                      No templates found. Upload templates to see performance metrics.
                    </div>
                  ) : (
                    <div className="border border-border/50 rounded-xl divide-y divide-border/50">
                      {sellerTemplatesList.map((perf, idx) => (
                        <div key={idx} className="p-4 grid grid-cols-2 md:grid-cols-5 gap-2 items-center text-xs">
                          <div className="font-bold text-sm text-foreground md:col-span-2">{perf.title}</div>
                          <div>Views: {perf.views_count || 0}</div>
                          <div>Downloads: {perf.downloads_count || 0}</div>
                          <div>Likes: {perf.likes_count || 0}</div>
                          <div>Rating: {perf.rating_avg || 0} ★ ({perf.rating_count || 0} reviews)</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}



              {/* === SELLER MARKETING === */}
              {activeTab === "seller-marketing" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Marketing & Referrals</h3>
                    <p className="text-sm text-muted-foreground">Generate referral campaigns link codes.</p>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Referral Campaign Code Generator</label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          readOnly
                          value={`https://aisitestudio.com/ref?seller=${user?.id || "mock"}`}
                          className="flex-1 px-3 py-2.5 rounded-xl glass border border-border/50 text-xs font-mono select-all bg-card/50"
                        />
                        <button onClick={() => alert("Copied to clipboard!")} className="px-4 py-2 bg-primary text-white text-xs font-semibold rounded-xl flex items-center gap-1">
                          <Copy className="w-3.5 h-3.5" /> Copy Link
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* === SELLER FOLLOWERS === */}
              {activeTab === "seller-followers" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Sellers Followers</h3>
                    <p className="text-sm text-muted-foreground">Track profiles and users who follow your updates.</p>
                  </div>
                  {followersLoading ? (
                    <div className="text-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-primary" />
                    </div>
                  ) : !followers || followers.length === 0 ? (
                    <div className="p-8 text-center text-muted-foreground text-sm border border-border/40 rounded-xl">
                      No followers yet.
                    </div>
                  ) : (
                    <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
                      {followers.map((follower) => (
                        <div key={follower.id} className="p-4 rounded-xl border border-border/40 bg-card/10 flex items-center gap-3">
                          <img src={follower.avatar_url || "https://picsum.photos/seed/avatar/100/100"} alt="" className="w-10 h-10 rounded-full object-cover bg-muted" />
                          <div>
                            <div className="font-bold text-sm text-white">{follower.full_name || follower.username}</div>
                            <span className="text-[10px] text-muted-foreground">@{follower.username || "user"}</span>
                          </div>
                        </div>
                      ))}
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
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Earnings Payout Setup</h3>
                    <p className="text-sm text-muted-foreground">Select payout options and manage withdrawal history.</p>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-6">
                    <div className="space-y-4">
                      <div>
                        <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Payout Method</label>
                        <select
                          value={payoutMethod}
                          onChange={(e) => setPayoutMethod(e.target.value)}
                          className="w-full px-3 py-2 rounded-lg glass border border-border/50 text-xs focus:outline-none bg-card"
                        >
                          <option value="paypal">PayPal</option>
                          <option value="stripe">Stripe</option>
                          <option value="bank">Direct Bank Transfer</option>
                          <option value="upi">UPI ID</option>
                          <option value="wise">Wise Transfer</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-muted-foreground uppercase mb-1">Account details ID</label>
                        <input
                          type="text"
                          value={payoutDetails}
                          onChange={(e) => setPayoutDetails(e.target.value)}
                          className="w-full px-3 py-2 rounded-lg glass border border-border/50 text-xs focus:outline-none bg-card"
                        />
                      </div>
                      <button onClick={() => alert("Payout information saved!")} className="px-4 py-2 bg-primary text-white rounded-lg text-xs font-semibold">Save Payout Details</button>
                    </div>

                    <div className="p-6 border border-border/50 rounded-xl space-y-3 bg-muted/5 flex flex-col justify-between">
                      <div>
                        <h4 className="font-bold text-sm text-foreground">Withdrawal Request</h4>
                        <p className="text-xs text-muted-foreground mt-1">Available balance for instant withdrawal: $0.00</p>
                      </div>
                      <button disabled className="py-2.5 bg-primary/50 text-white font-bold text-xs rounded-xl cursor-not-allowed">Withdraw Now ($0.00)</button>
                    </div>
                  </div>

                  <div className="border-t border-border/50 pt-4">
                    <h4 className="font-bold text-sm text-foreground mb-3">Withdrawal Requests History</h4>
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/50 text-muted-foreground font-bold">
                          <th className="pb-2">Request ID</th>
                          <th className="pb-2">Date</th>
                          <th className="pb-2">Amount</th>
                          <th className="pb-2">Method</th>
                          <th className="pb-2 text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {payoutHistory.map((h, idx) => (
                          <tr key={idx} className="border-b border-border/40 hover:bg-muted/5">
                            <td className="py-2.5 font-mono text-foreground">{h.id}</td>
                            <td className="py-2.5">{h.date}</td>
                            <td className="py-2.5">${h.amount.toFixed(2)}</td>
                            <td className="py-2.5">{h.method}</td>
                            <td className="py-2.5 text-right font-semibold text-primary">{h.status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* === SELLER LICENSES === */}
              {activeTab === "seller-licenses" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Issued Licenses</h3>
                    <p className="text-sm text-muted-foreground">Track software license tokens generated for purchases.</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/50 text-muted-foreground font-bold">
                          <th className="pb-2">License Token</th>
                          <th className="pb-2">License Type</th>
                          <th className="pb-2">Created Date</th>
                          <th className="pb-2 text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td colSpan={4} className="py-4 text-center text-muted-foreground text-xs">
                            No issued software licenses found.
                          </td>
                        </tr>
                      </tbody>
                    </table>
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
                                    const res = await fetch(`http://localhost:8000/api/v1/admin/users/${u.id}`, {
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
                                    const res = await fetch(`http://localhost:8000/api/v1/admin/users/${u.id}`, {
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
                                    const res = await fetch(`http://localhost:8000/api/v1/admin/users/${u.id}`, {
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

              {/* === ADMIN TEMPLATES REVIEW QUEUE === */}
              {activeTab === "admin-templates" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Templates Moderation Queue</h3>
                    <p className="text-sm text-muted-foreground">Approve or reject creator template submissions.</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/50 text-muted-foreground font-bold uppercase">
                          <th className="pb-2">Template Title</th>
                          <th className="pb-2">Developer</th>
                          <th className="pb-2">Price</th>
                          <th className="pb-2">Framework</th>
                          <th className="pb-2 text-right">Moderation Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminTemplatesLoading ? (
                          <tr>
                            <td colSpan={5} className="py-8 text-center text-muted-foreground">
                              <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                            </td>
                          </tr>
                        ) : adminTemplates.filter(t => t.status === "draft").length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-8 text-center text-muted-foreground">No templates pending review.</td>
                          </tr>
                        ) : (
                          adminTemplates.filter(t => t.status === "draft").map((t) => (
                            <tr key={t.id} className="border-b border-border/40 hover:bg-muted/5">
                              <td className="py-2.5 font-bold text-foreground">{t.title}</td>
                              <td className="py-2.5">{t.developer_name}</td>
                              <td className="py-2.5 font-semibold text-primary">{formatPrice(t.price)}</td>
                              <td className="py-2.5 font-mono text-[10px] uppercase">{t.framework}</td>
                              <td className="py-2.5 text-right space-x-2">
                                <button
                                  onClick={() => {
                                    if (window.confirm(`Approve and publish "${t.title}"?`)) {
                                      updateTemplateStatusMutation.mutate({ templateId: t.id, status: "published" });
                                    }
                                  }}
                                  className="px-2.5 py-1 bg-green-500/10 text-green-500 rounded hover:bg-green-500/20 text-[10px] font-bold transition-all"
                                >
                                  Approve
                                </button>
                                <button
                                  onClick={() => {
                                    if (window.confirm(`Reject and archive "${t.title}"?`)) {
                                      updateTemplateStatusMutation.mutate({ templateId: t.id, status: "archived" });
                                    }
                                  }}
                                  className="px-2.5 py-1 bg-yellow-500/10 text-yellow-500 rounded hover:bg-yellow-500/20 text-[10px] font-bold transition-all"
                                >
                                  Reject
                                </button>
                                <button
                                  onClick={() => {
                                    if (window.confirm(`Are you sure you want to permanently delete template "${t.title}"?`)) {
                                      deleteMutation.mutate(t.id);
                                    }
                                  }}
                                  className="px-2.5 py-1 bg-red-500/10 text-red-500 rounded hover:bg-red-500/20 text-[10px] font-bold transition-all"
                                >
                                  Delete
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* === ADMIN PAYMENTS === */}
              {activeTab === "admin-payments" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Payments Audit Ledger</h3>
                    <p className="text-sm text-muted-foreground">Global record of platform checkouts and transaction fee commissions.</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/50 text-muted-foreground font-bold uppercase">
                          <th className="pb-2">Order ID</th>
                          <th className="pb-2">Buyer</th>
                          <th className="pb-2">Templates</th>
                          <th className="pb-2">Gross Price</th>
                          <th className="pb-2">Commission (20%)</th>
                          <th className="pb-2 text-right">Net Creator Payout</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminOrdersLoading ? (
                          <tr>
                            <td colSpan={6} className="py-8 text-center text-muted-foreground">
                              <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                            </td>
                          </tr>
                        ) : adminOrders.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="py-8 text-center text-muted-foreground">No payments found in ledger.</td>
                          </tr>
                        ) : (
                          adminOrders.map((ord) => (
                            <tr key={ord.id} className="border-b border-border/40 hover:bg-muted/5">
                              <td className="py-2.5 font-mono text-foreground">{ord.order_number}</td>
                              <td className="py-2.5 select-all">{ord.buyer_email}</td>
                              <td className="py-2.5 truncate max-w-[150px]" title={ord.items.join(", ")}>{ord.items.join(", ") || "Package"}</td>
                              <td className="py-2.5 font-bold">{formatPrice(ord.total)}</td>
                              <td className="py-2.5 text-yellow-500 font-bold">{formatPrice(ord.total * 0.20)}</td>
                              <td className="py-2.5 text-right font-bold text-green-500">{formatPrice(ord.total * 0.80)}</td>
                            </tr>
                          ))
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
                  <div className="grid sm:grid-cols-3 gap-4 items-end">
                    <input
                      type="text"
                      placeholder="New Category Name (e.g. E-Commerce)"
                      className="sm:col-span-2 px-3 py-2 rounded-lg glass border border-border/50 text-xs focus:outline-none bg-card"
                    />
                    <button onClick={() => alert("Category added successfully!")} className="py-2.5 bg-primary text-white text-xs font-semibold rounded-lg flex items-center justify-center gap-1">
                      <Plus className="w-3.5 h-3.5" /> Add Category
                    </button>
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

              {/* === ADMIN REPORTS === */}
              {activeTab === "admin-reports" && (
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Platform Abuse Reports</h3>
                    <p className="text-sm text-muted-foreground">Monitor copyright claims or reviews reports.</p>
                  </div>
                  <div className="p-8 text-center text-muted-foreground text-sm border border-border/40 rounded-xl">
                    No active platform abuse reports found.
                  </div>
                </div>
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
                <div className="glass border border-border/40 rounded-2xl p-8 space-y-6">
                  <div>
                    <h3 className="font-bold text-lg">Moderation Logs</h3>
                    <p className="text-sm text-muted-foreground">Audit lists of live templates and moderation review statuses.</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-border/50 text-muted-foreground font-bold uppercase">
                          <th className="pb-2">Template</th>
                          <th className="pb-2">Developer</th>
                          <th className="pb-2">Status</th>
                          <th className="pb-2">Moderation Status</th>
                          <th className="pb-2 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminTemplatesLoading ? (
                          <tr>
                            <td colSpan={5} className="py-8 text-center text-muted-foreground">
                              <Loader2 className="w-5 h-5 animate-spin mx-auto text-primary" />
                            </td>
                          </tr>
                        ) : adminTemplates.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-8 text-center text-muted-foreground">No templates logged in database.</td>
                          </tr>
                        ) : (
                          adminTemplates.map((t) => (
                            <tr key={t.id} className="border-b border-border/40 hover:bg-muted/5">
                              <td className="py-2.5 font-bold text-foreground">{t.title}</td>
                              <td className="py-2.5">{t.developer_name}</td>
                              <td className="py-2.5 font-mono text-[10px] uppercase">{t.status}</td>
                              <td className="py-2.5 font-semibold">
                                <span className={cn(
                                  "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                                  t.status === "published" ? "bg-green-500/10 text-green-500" : "bg-yellow-500/10 text-yellow-500"
                                )}>
                                  {t.status === "published" ? "Approved" : "In Review"}
                                </span>
                              </td>
                              <td className="py-2.5 text-right">
                                <button
                                  onClick={() => {
                                    if (window.confirm(`Are you sure you want to permanently delete template "${t.title}"?`)) {
                                      deleteMutation.mutate(t.id);
                                    }
                                  }}
                                  className="p-1 text-red-500 hover:text-red-400 transition-colors"
                                  title="Delete Template"
                                >
                                  <Trash2 className="w-4 h-4 inline" />
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
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
                      {/* Avatar Upload Container */}
                      <div className="flex flex-col items-center sm:flex-row gap-4 p-4 rounded-xl border border-border/40 bg-card/20 mb-3">
                        <div className="relative w-16 h-16 rounded-full overflow-hidden border border-border/40 bg-slate-900 flex items-center justify-center shrink-0">
                          {avatarUrl ? (
                            <img src={avatarUrl} alt="Avatar Preview" className="w-full h-full object-cover" />
                          ) : (
                            <span className="text-xl font-bold text-slate-400">
                              {fullName?.[0] || username?.[0] || "?"}
                            </span>
                          )}
                          {uploadingAvatar && (
                            <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                              <Loader2 className="w-4 h-4 animate-spin text-primary" />
                            </div>
                          )}
                        </div>
                        <div className="space-y-2 text-center sm:text-left">
                          <label className="text-xs font-semibold text-slate-200 block">Profile Picture</label>
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
                              className="cursor-pointer px-3 py-1 bg-primary/20 border border-primary/30 text-primary text-xs font-semibold rounded-lg hover:bg-primary/30 transition-all"
                            >
                              Upload Image
                            </label>
                            {avatarUrl && (
                              <button
                                type="button"
                                onClick={() => setAvatarUrl("")}
                                className="px-3 py-1 bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-semibold rounded-lg hover:bg-red-500/20 transition-all"
                              >
                                Remove
                              </button>
                            )}
                          </div>
                          <span className="text-[10px] text-muted-foreground block">
                            Support JPG, PNG or WEBP. Max 2MB.
                          </span>
                        </div>
                      </div>

                      <div className="db-form-group">
                        <label className="db-form-label">Email Address (Read Only)</label>
                        <input
                          type="email"
                          value={user?.email ?? ""}
                          readOnly
                          className="db-form-input db-input-readonly"
                        />
                      </div>
                      <div className="db-form-group">
                        <label className="db-form-label">Full Name</label>
                        <input
                          type="text"
                          value={fullName}
                          onChange={(e) => setFullName(e.target.value)}
                          className="db-form-input"
                          placeholder="Navin Bharath"
                        />
                      </div>
                      <div className="db-form-group">
                        <label className="db-form-label">Username</label>
                        <input
                          type="text"
                          value={username}
                          onChange={(e) => setUsername(e.target.value)}
                          className="db-form-input"
                          placeholder="navin"
                        />
                      </div>
                      <div className="db-form-group">
                        <label className="db-form-label">Bio</label>
                        <textarea
                          value={bio}
                          onChange={(e) => setBio(e.target.value)}
                          className="db-form-input db-form-textarea"
                          placeholder="Tell us about yourself..."
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={savingProfile}
                        className="db-save-btn"
                      >
                        {savingProfile ? "Saving..." : "Save Changes"}
                      </button>
                    </form>
                  </div>
                </div>
              )}

              {/* === DEPLOY PROJECT WIZARD MODAL === */}
              {isDeployModalOpen && (
                <div className="modal-backdrop">
                  <div className="modal-content glass border border-border/40 p-6 rounded-2xl space-y-4">
                    <div className="flex justify-between items-center border-b border-border/20 pb-3">
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-lg text-white">Deploy a New Project</h3>
                        <span className="text-[9px] bg-primary/20 text-primary px-1.5 py-0.5 rounded-full font-semibold border border-primary/30 uppercase tracking-wider">
                          Coming Soon
                        </span>
                      </div>
                      <button
                        onClick={() => setIsDeployModalOpen(false)}
                        className="text-muted-foreground hover:text-white transition-colors bg-transparent border-none text-xl cursor-pointer"
                      >
                        ×
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
                          };
                          const res = await api.post("/deployments/", payload, authToken ?? undefined);
                          refetchDeployments();
                          setIsDeployModalOpen(false);
                          setDeploying(false);
                          // Reset wizard state
                          setDeployProjectName("");
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
                      <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-300 block">Select AI Project / Template</label>
                        <select
                          value={deployTemplateId}
                          onChange={(e) => {
                            const val = e.target.value;
                            setDeployTemplateId(val);
                            if (val === "mock-project-id") {
                              setDeployProjectName("AI Restaurant Prototype");
                            } else {
                              const matched = sellerTemplatesList.find(t => t.id === val);
                              if (matched) setDeployProjectName(matched.title);
                            }
                          }}
                          className="w-full bg-slate-900/80 border border-border/40 rounded-xl p-2.5 text-sm text-white focus:outline-none focus:border-primary"
                          required
                        >
                          {sellerTemplatesList.length > 0 ? (
                            sellerTemplatesList.map(t => (
                              <option key={t.id} value={t.id}>{t.title} ({t.framework || "HTML"})</option>
                            ))
                          ) : (
                            <option value="mock-project-id">AI Restaurant Prototype (HTML)</option>
                          )}
                        </select>
                      </div>

                      <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-300 block">Project Display Name</label>
                        <input
                          type="text"
                          value={deployProjectName}
                          onChange={(e) => setDeployProjectName(e.target.value)}
                          placeholder="My Portfolio Site"
                          className="w-full bg-slate-900/80 border border-border/40 rounded-xl p-2.5 text-sm text-white focus:outline-none focus:border-primary"
                          required
                        />
                      </div>

                      <div className="space-y-2">
                        <label className="text-xs font-semibold text-slate-300 block">Hosting Provider</label>
                        <div className="provider-select-grid">
                          <div
                            onClick={() => setDeployProvider("vercel")}
                            className={`provider-card ${deployProvider === "vercel" ? "selected" : ""}`}
                          >
                            <div className="text-sm font-bold text-white mb-1">▲ Vercel</div>
                            <div className="text-[10px] text-muted-foreground">Serverless Hosting</div>
                          </div>
                          <div
                            onClick={() => setDeployProvider("netlify")}
                            className={`provider-card ${deployProvider === "netlify" ? "selected" : ""}`}
                          >
                            <div className="text-sm font-bold text-white mb-1">⧉ Netlify</div>
                            <div className="text-[10px] text-muted-foreground">Static Builds</div>
                          </div>
                          <div
                            onClick={() => setDeployProvider("github_pages")}
                            className={`provider-card ${deployProvider === "github_pages" ? "selected" : ""}`}
                          >
                            <div className="text-sm font-bold text-white mb-1">🕮 GitHub Pages</div>
                            <div className="text-[10px] text-muted-foreground">Git Repository</div>
                          </div>
                        </div>
                      </div>

                      <div className="p-4 bg-primary/5 border border-primary/20 rounded-xl space-y-3">
                        <div className="flex items-center gap-1.5 text-xs text-primary font-bold uppercase tracking-wider">
                          <Sparkles className="w-3.5 h-3.5 text-primary" /> AI Auto-Detected Build Settings
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-xs text-slate-300">
                          <div className="space-y-0.5">
                            <span className="text-[10px] text-muted-foreground uppercase block font-semibold">Branch</span>
                            <span className="font-mono bg-slate-900/60 border border-border/20 px-1.5 py-0.5 rounded text-[10px] text-white block truncate">
                              {deployBranch}
                            </span>
                          </div>
                          <div className="space-y-0.5">
                            <span className="text-[10px] text-muted-foreground uppercase block font-semibold">Build Cmd</span>
                            <span className="font-mono bg-slate-900/60 border border-border/20 px-1.5 py-0.5 rounded text-[10px] text-white block truncate" title={deployBuildCommand}>
                              {deployBuildCommand}
                            </span>
                          </div>
                          <div className="space-y-0.5">
                            <span className="text-[10px] text-muted-foreground uppercase block font-semibold">Output Dir</span>
                            <span className="font-mono bg-slate-900/60 border border-border/20 px-1.5 py-0.5 rounded text-[10px] text-white block truncate" title={deployOutputDir}>
                              {deployOutputDir}
                            </span>
                          </div>
                        </div>
                        <div className="text-[10px] text-muted-foreground leading-normal">
                          Settings are automatically determined based on the template's framework and files scan.
                        </div>
                      </div>

                      <div className="p-3 bg-primary/5 border border-primary/20 rounded-xl flex items-start gap-2">
                        <Info className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                        <div className="text-[11px] text-slate-300 leading-normal">
                          <strong className="text-white block mb-0.5">Coming Soon (Preview Mode)</strong>
                          The deployment simulation process is fully active to test the flow, but live production hosting integrations are coming soon.
                        </div>
                      </div>

                      <div className="flex justify-end gap-2.5 pt-3 border-t border-border/20">
                        <button
                          type="button"
                          onClick={() => setIsDeployModalOpen(false)}
                          className="px-4 py-2 border border-border/40 text-foreground text-xs font-semibold rounded-xl hover:bg-muted/10 transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={deploying}
                          className="px-4 py-2 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/95 transition-colors disabled:opacity-50 flex items-center gap-1"
                        >
                          {deploying ? (
                            <>
                              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Deploying...
                            </>
                          ) : (
                            "Start Deploy"
                          )}
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              )}

              {/* === BUILD LOGS CONSOLE MODAL === */}
              {isConsoleOpen && selectedDeployment && (
                <div className="modal-backdrop">
                  <div className="modal-content large glass border border-border/40 p-6 rounded-2xl space-y-4">
                    <div className="flex justify-between items-center border-b border-border/20 pb-3">
                      <div>
                        <h3 className="font-bold text-lg text-white">Build & Deploy Console</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">Project: {selectedDeployment.project_name}</p>
                      </div>
                      <button
                        onClick={() => {
                          setIsConsoleOpen(false);
                          setSelectedDeployment(null);
                        }}
                        className="text-muted-foreground hover:text-white transition-colors bg-transparent border-none text-xl cursor-pointer"
                      >
                        ×
                      </button>
                    </div>

                    <div className="terminal-window">
                      <div className="terminal-header">
                        <div className="terminal-dots">
                          <span className="terminal-dot" style={{ backgroundColor: '#ef4444' }}></span>
                          <span className="terminal-dot" style={{ backgroundColor: '#eab308' }}></span>
                          <span className="terminal-dot" style={{ backgroundColor: '#22c55e' }}></span>
                        </div>
                        <span className="text-xs text-slate-400 font-mono flex items-center gap-1.5">
                          {activeConsoleStatus === "building" ? (
                            <>
                              <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                              BUILDING...
                            </>
                          ) : activeConsoleStatus === "success" ? (
                            "READY"
                          ) : (
                            "FAILED"
                          )}
                        </span>
                      </div>

                      <div ref={consoleEndRef} className="terminal-body">
                        {activeConsoleLogs.split("\n").map((line, idx) => {
                          const clean = stripAnsi(line);
                          if (!clean.trim()) return null;
                          const isSuccess = clean.startsWith("✅") || clean.includes("successfully") || clean.startsWith("✓");
                          const isError = clean.startsWith("❌") || clean.toLowerCase().includes("error") || clean.toLowerCase().includes("failed");
                          const isStep = /^\d+\//.test(clean.trim()) || clean.includes("[1/") || clean.includes("[2/") || clean.includes("[3/") || clean.includes("[4/");
                          return (
                            <div key={idx} className={`terminal-log-line ${isSuccess ? "text-emerald-400" : isError ? "text-red-400" : isStep ? "text-sky-400 font-semibold" : ""}`}>
                              {clean}
                            </div>
                          );
                        })}
                        {activeConsoleStatus === "building" && <span className="terminal-cursor" />}
                      </div>
                    </div>

                    <div className="flex justify-between items-center pt-3 border-t border-border/20">
                      <div className="text-xs text-muted-foreground">
                        {activeConsoleStatus === "building" ? (
                          "Please wait, compilation in progress..."
                        ) : activeConsoleStatus === "success" ? (
                          <span className="text-emerald-400 font-semibold flex items-center gap-1">
                            ✓ Build succeeded. Live URL available.
                          </span>
                        ) : (
                          <span className="text-red-400 font-semibold">✗ Build failed. Review config.</span>
                        )}
                      </div>
                      <div className="flex gap-2">
                        {activeConsoleStatus === "success" && selectedDeployment?.live_url && (
                          <a
                            href={selectedDeployment.live_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-4 py-2 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/95 transition-colors text-center text-decoration-none"
                          >
                            🌐 Visit Live Site
                          </a>
                        )}
                        <button
                          onClick={() => {
                            setIsConsoleOpen(false);
                            setSelectedDeployment(null);
                          }}
                          className="px-4 py-2 bg-muted border border-border/40 hover:bg-muted/80 text-foreground text-xs font-semibold rounded-xl transition-colors"
                        >
                          Close Console
                        </button>
                      </div>
                    </div>
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

              {/* === LINK CUSTOM DOMAIN MODAL === */}
              {linkDomainModalOpen && (
                <div className="modal-backdrop">
                  <div className="modal-content glass border border-border/40 p-6 rounded-2xl max-w-md w-full space-y-4">
                    <div className="flex justify-between items-center border-b border-border/20 pb-3">
                      <div>
                        <h3 className="font-bold text-lg text-white">Link Custom Domain</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">Publish your live deployment directly to your own domain.</p>
                      </div>
                      <button
                        onClick={() => setLinkDomainModalOpen(false)}
                        className="text-muted-foreground hover:text-white transition-colors bg-transparent border-none text-xl cursor-pointer"
                      >
                        ×
                      </button>
                    </div>

                    <form onSubmit={(e) => {
                      e.preventDefault();
                      setLinkDomainError("");
                      if (!linkDomainDeploymentId) {
                        setLinkDomainError("Please select a deployment project.");
                        return;
                      }
                      if (!customDomainInput.trim()) {
                        setLinkDomainError("Please input your custom domain name.");
                        return;
                      }
                      linkDomainMutation.mutate({
                        deploymentId: linkDomainDeploymentId,
                        customDomain: customDomainInput.trim()
                      });
                    }} className="space-y-4">
                      {linkDomainError && (
                        <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 p-2.5 rounded-lg">
                          {linkDomainError}
                        </div>
                      )}

                      <div className="space-y-2">
                        <label className="block text-xs font-semibold text-muted-foreground uppercase">Select Active Deployment *</label>
                        <select
                          required
                          value={linkDomainDeploymentId}
                          onChange={(e) => setLinkDomainDeploymentId(e.target.value)}
                          className="w-full px-4 py-2.5 rounded-xl border border-border/45 text-sm focus:outline-none focus:border-primary bg-slate-950/90 text-white cursor-pointer"
                        >
                          <option value="" style={{ backgroundColor: "#0b0f19", color: "#ffffff" }}>Select a deployment project</option>
                          {deploymentsData.filter(d => d.status === "success").map((d) => (
                            <option key={d.id} value={d.id} style={{ backgroundColor: "#0b0f19", color: "#ffffff" }}>
                              {d.project_name} ({d.provider === "vercel" ? "Vercel" : d.provider === "netlify" ? "Netlify" : "GitHub Pages"})
                            </option>
                          ))}
                        </select>
                        {deploymentsData.filter(d => d.status === "success").length === 0 && (
                          <span className="text-[10px] text-amber-400 block mt-2 leading-relaxed bg-amber-500/10 border border-amber-500/25 p-2 rounded-lg">
                            ⚠️ You must have at least one successful template deployment to map a custom domain.
                          </span>
                        )}
                      </div>

                      <div className="space-y-2">
                        <label className="block text-xs font-semibold text-muted-foreground uppercase">Custom Domain Name *</label>
                        <input
                          type="text"
                          required
                          value={customDomainInput}
                          onChange={(e) => setCustomDomainInput(e.target.value)}
                          placeholder="e.g. www.mybrand.com"
                          className="w-full px-4 py-2.5 rounded-xl border border-border/45 text-sm focus:outline-none focus:border-primary bg-slate-950/90 text-white"
                        />
                        <span className="text-[10px] text-muted-foreground block mt-1">
                          Input the full domain name (including www or custom subdomains).
                        </span>
                      </div>

                      <div className="flex justify-end gap-2 pt-3 border-t border-border/20">
                        <button
                          type="button"
                          onClick={() => setLinkDomainModalOpen(false)}
                          className="px-4 py-2 bg-muted border border-border/40 hover:bg-muted/80 text-foreground text-xs font-semibold rounded-xl transition-colors cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={linkDomainMutation.isPending || deploymentsData.filter(d => d.status === "success").length === 0}
                          className="px-4 py-2 bg-primary text-white text-xs font-semibold rounded-xl hover:bg-primary/95 transition-colors disabled:opacity-50 flex items-center gap-1.5 border-none cursor-pointer"
                        >
                          {linkDomainMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                          Connect Domain
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
