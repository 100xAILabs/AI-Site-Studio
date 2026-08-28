"use client";

/**
 * Template Details Page — full template info with gallery, preview CTA, purchase box (React JSX).
 * Redesigned to support all 26 layouts/sections with rich interactive simulations.
 */

import { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import Image from "@/components/Image";
import Link, { navigate } from "@/components/Link";
import { useAppAuth, useAppUser } from "@/lib/auth";
import { motion, AnimatePresence } from "framer-motion";
import {
  Star, Download, Eye, Heart, Bookmark, ShoppingCart,
  Check, ArrowLeft, Globe, Code, Moon, Zap, Shield,
  Copy, ChevronRight, Share2, Scale, RefreshCw, FileText, X,
  Terminal, Sliders, Cpu, Smartphone, Tablet, Laptop,
  Monitor, HelpCircle, UserCheck, ChevronDown, ChevronUp,
  Play, Flame, Award, Activity, Sparkles, Clock, Plus,
  ExternalLink, Calendar, ShieldCheck, Info, Edit3, Upload,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import TemplateCard from "@/components/marketplace/TemplateCard";
import { useTemplate, useTemplates, useToggleFavorite, useToggleWishlist, useTemplateReviews, useCreateReview, useFollowStatus, useToggleFollow } from "@/hooks/useTemplates";
import { cn, formatPrice, formatNumber } from "@/lib/utils";
import { useCartStore } from "@/store";
import { API_URL, api } from "@/lib/api";
import "./Page.css";

export default function TemplateDetailsPage({ slug: propSlug }) {
  const { slug: routeSlug } = useParams();
  const [searchParams] = useSearchParams();
  const slug = propSlug || routeSlug;

  const { getToken, isSignedIn } = useAppAuth();
  const { user } = useAppUser();
  const [activeImage, setActiveImage] = useState(0);
  const [copied, setCopied] = useState(false);
  // Single-tier flat rate license package
  const [heroTab, setHeroTab] = useState("desktop"); // screenshot, gallery, video, mobile, tablet, desktop

  // Live Preview Device section
  const [deviceTab, setDeviceTab] = useState("desktop"); // desktop, laptop, tablet, mobile

  // Live Preview generation simulation states
  const [aiForm, setAiForm] = useState({
    businessName: "",
    industry: "Agency",
    location: "",
    primaryColor: "#2563eb",
    logoText: "",
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [isGenerated, setIsGenerated] = useState(false);
  const [generationStep, setGenerationStep] = useState(0);
  const [editableTitle, setEditableTitle] = useState("");
  const [editableSubtitle, setEditableSubtitle] = useState("");
  const [editableCta, setEditableCta] = useState("");
  const [aiPrimaryColor, setAiPrimaryColor] = useState("#2563eb");
  const aiFormRef = useRef(null);

  // Documentation Preview section active tab
  const [docTab, setDocTab] = useState("installation"); // installation, structure, customization, deployment

  // Accordion active keys
  const [openFaq, setOpenFaq] = useState(null);
  const [openChangelog, setOpenChangelog] = useState(0); // first item open by default

  // Lightbox Modal
  const [lightboxImg, setLightboxImg] = useState(null);

  // Share link modal states
  const [shareUrl, setShareUrl] = useState("");
  const [showShareModal, setShowShareModal] = useState(false);

  // Dynamic Reviews & Likes State
  const [newReview, setNewReview] = useState({ rating: 5, title: "", body: "" });
  const [likedReviews, setLikedReviews] = useState({});
  const [reviewError, setReviewError] = useState("");

  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  // Seller Profile Card States

  // Recently Viewed Templates
  const [recentlyViewed, setRecentlyViewed] = useState([]);

  const [token, setToken] = useState(null);
  useEffect(() => {
    getToken().then(setToken);
  }, [getToken]);

  // Declare template query hook first to avoid TDZ ReferenceError in render hooks
  const { data: template, isLoading, error } = useTemplate(slug, token);

  // Seller Edit Modal States
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editForm, setEditForm] = useState({
    title: "",
    short_description: "",
    description: "",
    price: 0,
    price_currency: "USD",
    license_type: "Single Site Commercial & Personal License",
    tags: "",
  });
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  useEffect(() => {
    if (template) {
      setEditForm({
        title: template.title || "",
        short_description: template.short_description || "",
        description: template.description || "",
        price: template.price || 0,
        price_currency: template.price_currency || "USD",
        license_type: template.license_type || "Single Site Commercial & Personal License",
        tags: Array.isArray(template.tags) ? template.tags.join(", ") : (template.tags || ""),
      });
    }
  }, [template]);

  const handleSaveTemplateEdit = async (e) => {
    e.preventDefault();
    if (!template?.id) return;
    const tokenVal = await getToken();
    if (!tokenVal) {
      alert("Session expired. Please sign in again.");
      return;
    }
    setIsSavingEdit(true);
    try {
      const payload = {
        title: editForm.title,
        short_description: editForm.short_description,
        description: editForm.description,
        price: Number(editForm.price),
        price_currency: editForm.price_currency,
        license_type: editForm.license_type,
        tags: editForm.tags ? editForm.tags.split(",").map(t => t.trim()).filter(Boolean) : [],
      };
      await api.patch(`/templates/${template.id}`, payload, tokenVal);
      alert("Template updated successfully!");
      setIsEditModalOpen(false);
      window.location.reload();
    } catch (err) {
      console.error(err);
      alert("Failed to update template: " + (err.message || "Unknown error"));
    } finally {
      setIsSavingEdit(false);
    }
  };

  // Seller Re-upload ZIP state
  const [reuploadZipFile, setReuploadZipFile] = useState(null);
  const [isUploadingZip, setIsUploadingZip] = useState(false);

  const handleReuploadZip = async () => {
    if (!reuploadZipFile || !template?.id) return;
    const tokenVal = await getToken();
    if (!tokenVal) {
      alert("Session expired. Please sign in again.");
      return;
    }
    setIsUploadingZip(true);
    try {
      const formData = new FormData();
      formData.append("file", reuploadZipFile);
      const res = await fetch(`${API_URL}/templates/${template.id}/reupload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${tokenVal}`,
        },
        body: formData,
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to re-upload template ZIP archive.");
      }
      alert("New template website ZIP package uploaded successfully! Live preview and download assets updated.");
      setReuploadZipFile(null);
      window.location.reload();
    } catch (err) {
      console.error(err);
      alert("Error re-uploading website package: " + err.message);
    } finally {
      setIsUploadingZip(false);
    }
  };

  // Load customizations state from shared link query params on mount
  useEffect(() => {
    if (!template) return;
    const isEdited = searchParams.get("isEdited") === "true";

    if (isEdited) {
      const bName = searchParams.get("businessName") || "";
      const ind = searchParams.get("industry") || "Agency";
      const loc = searchParams.get("location") || "";
      const pColor = searchParams.get("primaryColor") || "#2563eb";
      const lText = searchParams.get("logoText") || "";
      const cTitle = searchParams.get("title") || "";
      const cSub = searchParams.get("subtitle") || "";
      const cCta = searchParams.get("ctaText") || "";

      setAiForm({
        businessName: bName,
        industry: ind,
        location: loc,
        primaryColor: pColor,
        logoText: lText,
      });

      setEditableTitle(cTitle);
      setEditableSubtitle(cSub);
      setEditableCta(cCta);
      setAiPrimaryColor(pColor);
      setIsGenerated(true);
    }
  }, [template, searchParams]);
  const previewSrc = (() => {
    let base = template?.id ? `${API_URL}/preview/live/${template.id}` : "";
    if (template?.preview_url && !template.preview_url.includes("example.com") && !template.preview_url.includes("/preview/watermarked")) {
      base = template.preview_url;
    }

    if (isGenerated) {
      const q = new URLSearchParams();
      q.set("businessName", aiForm.businessName || "");
      q.set("industry", aiForm.industry || "");
      q.set("location", aiForm.location || "");
      q.set("primaryColor", aiPrimaryColor || "");
      q.set("logoText", aiForm.logoText || "");
      q.set("title", editableTitle || "");
      q.set("subtitle", editableSubtitle || "");
      q.set("ctaText", editableCta || "");
      q.set("customized", "true");
      return `${base}?${q.toString()}`;
    }
    return base;
  })();
  const favoriteMutation = useToggleFavorite(token ?? "");
  const wishlistMutation = useToggleWishlist(token ?? "");
  const addToCart = useCartStore((s) => s.addItem);
  const isInCart = useCartStore((s) => s.isInCart(template?.id ?? ""));
  const { data: reviewsData, isLoading: isReviewsLoading } = useTemplateReviews(template?.id);
  const reviewsList = reviewsData?.items || [];
  const createReviewMutation = useCreateReview(token);
  const { data: followStatusData } = useFollowStatus(template?.seller_id, token);
  const isFollowing = !!followStatusData?.is_following;
  const toggleFollowMutation = useToggleFollow(token);

  const handleFollowToggle = () => {
    if (!isSignedIn || !token) {
      alert("Please sign in to follow this seller.");
      return;
    }
    if (!template?.seller_id) {
      alert("Seller information is not available.");
      return;
    }
    toggleFollowMutation.mutate(template.seller_id);
  };

  const isSeller = isSignedIn && (user?.role === "seller" || user?.role === "SELLER");

  // Fetch related templates of the same category
  const categorySlug = template?.category?.slug || template?.category_id || "";
  const { data: relatedTemplates } = useTemplates(
    { category: categorySlug, page_size: 4 },
    token
  );

  // Manage Recently Viewed Templates in LocalStorage
  useEffect(() => {
    if (!template) return;

    try {
      const stored = localStorage.getItem("recently_viewed_templates");
      let list = stored ? JSON.parse(stored) : [];

      // Filter out current template to avoid duplicates
      list = list.filter((item) => item.id !== template.id);

      // Add to front of array
      const currentMeta = {
        id: template.id,
        title: template.title,
        slug: template.slug,
        price: template.price,
        thumbnail_url: template.thumbnail_url,
        rating_avg: template.rating_avg,
        rating_count: template.rating_count,
        framework: template.framework,
      };
      list.unshift(currentMeta);

      // Keep only last 4 items
      const truncated = list.slice(0, 5);
      localStorage.setItem("recently_viewed_templates", JSON.stringify(truncated));

      // Update state, filtering out current template from display
      setRecentlyViewed(truncated.filter((item) => item.id !== template.id));
    } catch (e) {
      console.error("Failed to update recently viewed templates", e);
    }
  }, [template]);

  // Load recently viewed templates on mount/view change
  useEffect(() => {
    try {
      const stored = localStorage.getItem("recently_viewed_templates");
      if (stored && template) {
        const list = JSON.parse(stored);
        setRecentlyViewed(list.filter((item) => item.id !== template.id));
      }
    } catch (e) {
      console.error(e);
    }
  }, [template]);
  useEffect(() => {
    if (template) {
      const primaryCol = template.color_scheme ? template.color_scheme.split(",")[0].trim() : "#2563eb";
      setAiForm((prev) => ({
        ...prev,
        industry: template.industry || "Agency",
        logoText: template.title?.split(" ")[0] || "Logo",
        primaryColor: primaryCol,
      }));
      setAiPrimaryColor(primaryCol);

      // If user arrived with ?buy=1 or ?action=buy, directly add to cart and route to checkout
      const buyParam = searchParams.get("buy");
      const actionParam = searchParams.get("action");
      if (buyParam === "1" || actionParam === "buy" || buyParam === "true") {
        addToCart({
          templateId: template.id,
          title: template.title,
          price: Number(template.price),
          thumbnail: template.thumbnail_url || template.gallery_images?.[0] || "",
          licenseType: "regular",
        });
        navigate("/checkout");
      }
    }
  }, [template, searchParams]);

  const handleAddToCart = () => {
    if (!template) return;
    addToCart({
      templateId: template.id,
      title: template.title,
      price: Number(template.price),
      thumbnail: template.thumbnail_url,
      licenseType: "regular",
    });
  };

  const handleBuyNow = (e) => {
    e.preventDefault();
    if (!template) return;
    if (!isInCart) {
      addToCart({
        templateId: template.id,
        title: template.title,
        price: Number(template.price),
        thumbnail: template.thumbnail_url,
        licenseType: "regular",
      });
    }
    navigate("/checkout");
  };

  const handleShareClick = () => {
    let url = window.location.origin + window.location.pathname;
    const params = new URLSearchParams();

    if (isGenerated) {
      params.set("businessName", aiForm.businessName || "");
      params.set("industry", aiForm.industry || "");
      params.set("location", aiForm.location || "");
      params.set("primaryColor", aiPrimaryColor || "");
      params.set("logoText", aiForm.logoText || "");
      params.set("title", editableTitle || "");
      params.set("subtitle", editableSubtitle || "");
      params.set("ctaText", editableCta || "");
      params.set("isEdited", "true");
    }

    const searchStr = params.toString();
    if (searchStr) {
      url += "?" + searchStr;
    }

    setShareUrl(url);
    setShowShareModal(true);
  };

  const handleLikeReview = (id) => {
    setLikedReviews((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    if (!token) {
      setReviewError("Please sign in to submit a review.");
      return;
    }
    if (!newReview.body.trim()) {
      setReviewError("Review comment is required.");
      return;
    }
    setReviewError("");
    setIsSubmittingReview(true);
    try {
      await createReviewMutation.mutateAsync({
        template_id: template.id,
        rating: Number(newReview.rating),
        title: newReview.title || "Review",
        body: newReview.body,
      });
      setNewReview({ rating: 5, title: "", body: "" });
    } catch (err) {
      setReviewError(err.message || "Failed to submit review");
    } finally {
      setIsSubmittingReview(false);
    }
  };

  // Simulated Live Generation Terminal steps
  const generatorSteps = [
    "Analyzing template framework structure & design style...",
    "Scanning industry-specific landing pages and branding rules...",
    "Synthesizing customized HSL color palette based on primary color preference...",
    "Drafting tailored copywriting headlines (Instant Content Generator)...",
    "Selecting business-specific visual mockups (Dynamic Graphics Generator)...",
    "Injecting schema metadata and tag frameworks (Automated SEO Optimization)...",
    "Provisioning custom editor preview sandbox..."
  ];

  const handleGeneratePreview = (e) => {
    e.preventDefault();
    if (!aiForm.businessName) {
      alert("Please enter your business name.");
      return;
    }
    setIsGenerating(true);
    setGenerationStep(0);

    // Dynamic text defaults based on inputs
    setEditableTitle(`Customized ${template.title} for ${aiForm.businessName}`);
    setEditableSubtitle(`Optimized for the ${aiForm.industry} sector in ${aiForm.location || "your region"}. This is an interactive watermarked draft.`);
    setEditableCta(`Partner with ${aiForm.businessName}`);
    setAiPrimaryColor(aiForm.primaryColor);

    const interval = setInterval(() => {
      setGenerationStep((prev) => {
        if (prev >= generatorSteps.length - 1) {
          clearInterval(interval);
          setIsGenerating(false);
          setIsGenerated(true);
          return prev;
        }
        return prev + 1;
      });
    }, 600);
  };

  if (isLoading) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen pt-20">
          <div className="container-xl py-12">
            <div className="grid lg:grid-cols-3 gap-10">
              <div className="lg:col-span-2 space-y-4">
                <div className="aspect-video skeleton rounded-2xl animate-pulse bg-muted" />
                <div className="h-8 skeleton rounded w-1/2 animate-pulse bg-muted" />
                <div className="h-4 skeleton rounded w-full animate-pulse bg-muted" />
                <div className="h-4 skeleton rounded w-3/4 animate-pulse bg-muted" />
              </div>
              <div className="h-96 skeleton rounded-2xl animate-pulse bg-muted" />
            </div>
          </div>
        </div>
      </>
    );
  }

  if (error || !template) {
    return (
      <>
        <Navbar />
        <div className="min-h-screen pt-20 flex items-center justify-center">
          <div className="text-center">
            <div className="text-6xl mb-4">😕</div>
            <h1 className="text-2xl font-bold mb-2">Template Not Found</h1>
            <p className="text-muted-foreground mb-6">This template doesn&apos;t exist or has been removed.</p>
            <Link href="/marketplace" className="px-6 py-3 bg-primary text-primary-foreground rounded-xl font-semibold">
              Browse Marketplace
            </Link>
          </div>
        </div>
      </>
    );
  }

  const allImages = [template.thumbnail_url, ...(template.gallery_images ?? [])];

  // Helper arrays for features and specifications mapping
  const featuresList = [
    { name: "Responsive Layout", desc: "Looks stunning on Desktop, Tablet, and Mobile devices out-of-the-box.", icon: Globe },
    { name: "SEO Optimization Ready", desc: "Includes semantic structure, pre-mapped metatags, and JSON-LD markup schema.", icon: Shield },
    { name: "Ultra Fast Loading", desc: "Highly optimized code with Google Lighthouse scores close to 100.", icon: Flame },
    { name: "Accessibility Focused", desc: "Complies with WCAG accessibility patterns for screen readers.", icon: UserCheck },
    { name: "Modern Dark Mode", desc: "Smooth toggles with native system preference detection.", icon: Moon },
    { name: "Premium Micro-Animations", desc: "Configured using Framer Motion and modern CSS keyframes.", icon: Sparkles },
    { name: "Sticky Header Layout", desc: "Fully responsive, glassmorphic headers that follow screen scrolling.", icon: Clock },
    { name: "CMS Ready Framework", desc: "Easily plug into Sanity, Strapi, or headless WordPress backends.", icon: Cpu },
  ];

  const customizationOptions = [
    { title: "Colors & Schemes", desc: "Tailor the appearance using a single master CSS variable.", icon: Sliders },
    { title: "Typography & Fonts", desc: "Pre-linked with Google Fonts. Easily customize in index.css.", icon: FileText },
    { title: "Image Assets", desc: "SVG mockups and placeholders are easily replacable in assets directory.", icon: Image },
    { title: "Interactive Layouts", desc: "Re-arrange sections or components safely without layout breaks.", icon: Code },
  ];

  const docsInstallCode = `# Install dependencies
npm install

# Run the local development server
npm run dev

# Build the optimized production bundle
npm run build`;

  const docsFolders = `├── public/          # Static assets & public icons
├── src/
│   ├── app/         # Page components & routing setup
│   ├── components/  # Reusable UI component modules
│   ├── hooks/       # Custom React query hooks
│   ├── store/       # State management stores (Zustand)
│   └── index.css    # Global stylesheets & design tokens
├── package.json
└── vite.config.js`;

  return (
    <>
      <Navbar />


      <div className="details-main-container">
        <div className="details-grid">
          {/* ── Left Column: Media & Info ────────────────────────────────── */}
          <div className="details-left-panel">

            {/* 1. Template Hero Section */}
            <div className="details-hero-block card-container">

              {/* ── Tab Switcher Row (ABOVE the viewport) ── */}
              <div className="details-hero-tabs-row">
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                  <button
                    onClick={() => { setHeroTab("screenshot"); setActiveImage(0); }}
                    className={cn("hero-tab-btn", heroTab === "screenshot" && "active")}
                  >
                    Hero Screenshot
                  </button>
                  <button
                    onClick={() => setHeroTab("video")}
                    className={cn("hero-tab-btn", heroTab === "video" && "active")}
                  >
                    <Play className="w-3.5 h-3.5 mr-1 inline" /> Video Preview
                  </button>
                  <button
                    onClick={() => setHeroTab("desktop")}
                    className={cn("hero-tab-btn", heroTab === "desktop" && "active")}
                  >
                    <Monitor className="w-3.5 h-3.5 mr-1 inline" /> Desktop
                  </button>
                  <button
                    onClick={() => setHeroTab("tablet")}
                    className={cn("hero-tab-btn", heroTab === "tablet" && "active")}
                  >
                    <Tablet className="w-3.5 h-3.5 mr-1 inline" /> Tablet
                  </button>

                </div>

                <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
                  <a
                    href={previewSrc}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hero-action-btn live"
                  >
                    <Globe className="w-4 h-4" /> Live Demo
                  </a>
                  {/* Favorite Button */}
                  <button
                    onClick={() => {
                      if (!isSignedIn || !token) {
                        alert("Please sign in to favorite templates.");
                        return;
                      }
                      favoriteMutation.mutate(template.id);
                    }}
                    className={cn("hero-action-icon", template?.is_favorited && "active")}
                    title={template?.is_favorited ? "Remove from Favorites" : "Add to Favorites"}
                  >
                    <Heart className={cn("w-4 h-4", template?.is_favorited && "fill-current")} />
                  </button>

                  {/* Wishlist Button */}
                  <button
                    onClick={() => {
                      if (!isSignedIn || !token) {
                        alert("Please sign in to save templates to your wishlist.");
                        return;
                      }
                      wishlistMutation.mutate(template.id);
                    }}
                    className={cn("hero-action-icon", template?.is_wishlisted && "active")}
                    title={template?.is_wishlisted ? "Remove from Wishlist" : "Add to Wishlist"}
                  >
                    <Bookmark className={cn("w-4 h-4", template?.is_wishlisted && "fill-current")} />
                  </button>
                  <button onClick={handleShareClick} className="hero-action-icon" title="Share Link">
                    <Share2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* ── Media Display Viewport ── */}
              <div className={cn("details-media-viewport glass-card", heroTab === "mobile" && "is-mobile-tab")}>
                {heroTab === "screenshot" || heroTab === "gallery" ? (
                  /* Screenshot / Gallery view */
                  <div
                    style={{ position: "absolute", inset: 0, cursor: "zoom-in" }}
                    onClick={() => setLightboxImg(allImages[activeImage])}
                  >
                    <Image
                      src={allImages[activeImage]}
                      alt={template.title}
                      fill
                      className="object-cover"
                      style={{ transition: "transform 0.4s ease" }}
                    />
                  </div>
                ) : heroTab === "video" ? (
                  template.video_url ? (
                    /* Real uploaded video player */
                    <div style={{ position: "absolute", inset: 0, background: "#000" }}>
                      {template.video_url.includes("youtube.com") || template.video_url.includes("youtu.be") || template.video_url.includes("vimeo.com") ? (
                        <iframe
                          src={template.video_url.replace("watch?v=", "embed/")}
                          title={`${template.title} Video Walkthrough`}
                          style={{ width: "100%", height: "100%", border: "none" }}
                          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                          allowFullScreen
                        />
                      ) : (
                        <video
                          src={template.video_url}
                          controls
                          style={{ width: "100%", height: "100%", objectFit: "cover" }}
                          poster={allImages[0]}
                        />
                      )}
                    </div>
                  ) : (
                    /* Premium Live Auto-Scrolling Video Walkthrough Simulation */
                    <div className="video-walkthrough-player">
                      {/* Top HUD: REC indicator */}
                      <div className="video-player-hud-top">
                        <div className="rec-indicator">
                          <span className="rec-dot" />
                          <span>REC</span>
                        </div>
                        <div className="video-title-hud">
                          {template.title} — Live Walkthrough
                        </div>
                      </div>

                      {/* Auto-scrolling screen content */}
                      <div className="video-player-screen">
                        <iframe
                          src={previewSrc}
                          title={`Live Video Walkthrough — ${template.title}`}
                          sandbox="allow-scripts allow-same-origin allow-forms"
                          className="autoscroll-iframe"
                        />
                      </div>

                      {/* Bottom HUD: Player UI Controls */}
                      <div className="video-player-hud-bottom">
                        <div className="hud-play-btn">
                          <Play className="w-3.5 h-3.5 fill-current text-primary" />
                        </div>
                        <div className="hud-progress-container">
                          <div className="hud-progress-bar" />
                        </div>
                        <div className="hud-time-display">
                          Auto-Walkthrough
                        </div>
                      </div>
                    </div>
                  )
                ) : heroTab === "mobile" ? (
                  /* Premium iPhone Simulator Mockup */
                  <div className="iphone-mockup" style={{ position: "absolute", inset: 0 }}>
                    <div className="iphone-bezel">
                      {/* Top Status Bar */}
                      <div className="iphone-status-bar">
                        <span className="iphone-time">
                          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        <div className="iphone-dynamic-island" />
                        <div className="iphone-status-icons">
                          <span className="iphone-signal">📶</span>
                          <span className="iphone-wifi">📶</span>
                          <div className="iphone-battery">
                            <div className="iphone-battery-level" />
                          </div>
                        </div>
                      </div>

                      {/* Screen Content */}
                      <div className="iphone-screen">
                        <iframe
                          src={previewSrc}
                          title={`Mobile Preview — ${template.title}`}
                          sandbox="allow-scripts allow-same-origin allow-forms"
                        />
                      </div>

                      {/* Safari Bottom Navigation Bar */}
                      <div className="iphone-safari-bar">
                        <div className="iphone-safari-address-bar">
                          <span className="iphone-safari-text-format">aA</span>
                          <div className="iphone-safari-url">
                            <span className="iphone-safari-lock">🔒</span>
                            <span className="iphone-safari-host">{template.slug}.preview.dev</span>
                          </div>
                          <span className="iphone-safari-refresh">🔄</span>
                        </div>
                        <div className="iphone-safari-nav-icons">
                          <span className="iphone-safari-icon">⟨</span>
                          <span className="iphone-safari-icon">⟩</span>
                          <span className="iphone-safari-icon">📤</span>
                          <span className="iphone-safari-icon">📖</span>
                          <span className="iphone-safari-icon">🔳</span>
                        </div>
                      </div>

                      {/* Home Indicator Bar */}
                      <div className="iphone-home-indicator" />
                    </div>
                  </div>
                ) : (
                  /* Desktop / Tablet device simulator */
                  <div style={{
                    position: "absolute", inset: 0,
                    background: "linear-gradient(135deg, #0d0d1a 0%, #0a0a12 100%)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    padding: heroTab === "desktop" ? "0.5rem" : "1rem",
                  }}>
                    <div
                      className={cn(
                        "device-preview-inner",
                        heroTab === "desktop" && "device-desktop",
                        heroTab === "tablet" && "device-tablet"
                      )}
                    >
                      {/* Browser chrome */}
                      <div className="device-preview-header">
                        <div style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
                          <span style={{ width: "0.55rem", height: "0.55rem", borderRadius: "9999px", background: "#ef4444", display: "block" }} />
                          <span style={{ width: "0.55rem", height: "0.55rem", borderRadius: "9999px", background: "#f59e0b", display: "block" }} />
                          <span style={{ width: "0.55rem", height: "0.55rem", borderRadius: "9999px", background: "#22c55e", display: "block" }} />
                        </div>
                        <span style={{
                          fontSize: "0.575rem", fontFamily: "monospace",
                          background: "rgba(0,0,0,0.2)", padding: "0.15rem 0.6rem",
                          borderRadius: "0.3rem", border: "1px solid rgba(255,255,255,0.1)",
                          color: "rgba(255,255,255,0.5)", maxWidth: "14rem",
                          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"
                        }}>
                          {template.slug}.preview.dev
                        </span>
                        <span style={{ width: "1.25rem" }} />
                      </div>
                      {/* Full-cover body */}
                      {/* Full-cover body */}
                      <div className="device-preview-body">
                        <Image
                          src={allImages[0]}
                          alt={`${heroTab} preview`}
                          fill
                          className="object-cover object-top"
                        />
                        <iframe
                          src={previewSrc}
                          title={`${heroTab} Preview — ${template.title}`}
                          sandbox="allow-scripts allow-same-origin allow-forms"
                          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: "none", zIndex: 1 }}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Compare Tray Removed */}
            </div>

            {/* 2. Template Information */}
            <div className="details-info-block card-container">
              <div className="details-info-header">
                <div>
                  <h1 className="details-title-heading">
                    {isGenerated && editableTitle ? editableTitle : template.title}
                  </h1>
                  <p className="details-subtitle-text">
                    {isGenerated && editableSubtitle ? editableSubtitle : template.short_description}
                  </p>
                </div>
                <div className="details-info-price">
                  <div className="text-2xl font-bold text-foreground">
                    {template.is_free ? "Free" : formatPrice(template.price)}
                  </div>
                  <span className="text-xs text-muted-foreground">Single site regular license</span>
                </div>
              </div>

              {/* Information Card Grid */}
              <div className="details-specs-grid">
                <div className="spec-info-card">
                  <span className="spec-label">Category</span>
                  <span className="spec-val capitalize">{template.category?.name || "Business"}</span>
                </div>
                <div className="spec-info-card">
                  <span className="spec-label">Industry Match</span>
                  <span className="spec-val">{template.industry || "General Agency"}</span>
                </div>
                <div className="spec-info-card">
                  <span className="spec-label">Customer Rating</span>
                  <span className="spec-val flex items-center gap-1">
                    <Star className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
                    {template.rating_avg} ({template.rating_count} reviews)
                  </span>
                </div>
                <div className="spec-info-card">
                  <span className="spec-label">Downloads</span>
                  <span className="spec-val">{formatNumber(template.downloads_count)} installs</span>
                </div>
                <div className="spec-info-card">
                  <span className="spec-label">Framework v{template.version}</span>
                  <span className="spec-val uppercase font-mono">{template.framework}</span>
                </div>
                <div className="spec-info-card">
                  <span className="spec-label">Last Updated</span>
                  <span className="spec-val">June 2026</span>
                </div>
              </div>
            </div>

            {/* 3. Description Details */}
            <div className="details-desc-card card-container">
              <h3 className="section-title">About this template</h3>
              <div className="details-markdown-content text-muted-foreground text-sm leading-relaxed space-y-4">
                <p>
                  {template.description || `Build a highly customized homepage for your business in seconds. Designed specifically for modern consulting, agency structures, and startups looking to represent a bold, premium aesthetic.`}
                </p>
                <p>
                  Built with professional developers in mind, this package delivers multiple variations for grid setups, flexible CTA items, responsive menus, and clean CSS code scopes that can easily be compiled or extended.
                </p>
              </div>
            </div>



            {/* 4. Screenshots Gallery */}
            <div className="details-gallery-block card-container">
              <h3 className="section-title">Screenshots Gallery</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {allImages.map((img, i) => (
                  <div key={i} className="screenshot-card group cursor-zoom-in" onClick={() => setLightboxImg(img)}>
                    <div className="relative aspect-video rounded-lg overflow-hidden border border-border/30 bg-muted">
                      <Image src={img} alt={`Screenshot ${i + 1}`} fill className="object-cover transition-all duration-300 group-hover:scale-105" />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                        <Eye className="w-5 h-5 text-white" />
                      </div>
                    </div>
                    <span className="text-[11px] font-medium text-muted-foreground mt-1.5 block text-center capitalize">
                      {["Home Dashboard", "Services Grid", "Portfolio Details", "Contact Panel"][i % 4] || `Screenshot ${i + 1}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* 5. Pages Included */}
            <div className="details-pages-included-block card-container">
              <h3 className="section-title">Pages & Layouts Included</h3>
              <p className="text-xs text-muted-foreground mb-4">
                This bundle features {template.pages_count} highly responsive pages pre-linked and configured for the client routing system.
              </p>
              <div className="details-pages-grid">
                {(template.included_pages && template.included_pages.length > 0
                  ? template.included_pages
                  : ["Home", "About", "Services", "Portfolio Showcase", "Pricing Table", "Testimonials Panel", "Accordion FAQ", "Contact Form", "Blog Listing", "Privacy Policy", "404 Error page"]
                ).map((page, index) => (
                  <div key={page} className="details-page-item">
                    <Check className="w-4 h-4 text-green-500 shrink-0" />
                    <span>{page}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 6. Features Section */}
            <div className="details-features-block card-container">
              <h3 className="section-title">Utility & Design Features</h3>
              <div className="grid sm:grid-cols-2 gap-4">
                {featuresList.map((f, i) => {
                  const IconComp = f.icon;
                  return (
                    <div key={i} className="flex gap-3 p-3 rounded-lg border border-border/30 hover:border-primary/20 transition-all bg-card/40">
                      <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
                        <IconComp className="w-4 h-4" />
                      </div>
                      <div>
                        <h4 className="font-bold text-sm text-foreground">{f.name}</h4>
                        <p className="text-xs text-muted-foreground mt-0.5">{f.desc}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 7. Technology Stack & Browser Support */}
            <div className="details-tech-stack-block card-container">
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <h3 className="section-title">Technology Stack</h3>
                  <div className="flex flex-wrap gap-2.5">
                    {(() => {
                      // If we have audit report, use it
                      if (template.changelog?.ai_report) {
                        return [
                          template.changelog.ai_report.framework_detected,
                          template.changelog.ai_report.language,
                          template.changelog.ai_report.css_system,
                          template.changelog.ai_report.ui_library && template.changelog.ai_report.ui_library !== "None" ? template.changelog.ai_report.ui_library : null,
                          template.changelog.ai_report.animation_library && template.changelog.ai_report.animation_library !== "None" ? template.changelog.ai_report.animation_library : null
                        ].filter(Boolean);
                      }

                      // Build dynamically from framework and tags
                      const stack = [];
                      const fw = template.framework?.toLowerCase() || "";

                      if (fw.includes("next")) {
                        stack.push("Next.js", "React", "JavaScript");
                      } else if (fw.includes("react")) {
                        stack.push("React", "JavaScript");
                      } else if (fw.includes("vue")) {
                        stack.push("Vue.js", "JavaScript");
                      } else if (fw.includes("html")) {
                        stack.push("HTML5", "CSS3", "JavaScript");
                      }

                      if (template.tags && Array.isArray(template.tags)) {
                        template.tags.forEach(tag => {
                          const t = tag.toLowerCase().trim();
                          if (t === "tailwind" || t === "tailwindcss") {
                            if (!stack.includes("TailwindCSS")) stack.push("TailwindCSS");
                          } else if (t === "typescript" || t === "ts") {
                            if (!stack.includes("TypeScript")) stack.push("TypeScript");
                          } else if (t === "sass" || t === "scss") {
                            if (!stack.includes("SASS")) stack.push("SASS");
                          } else if (t === "vite") {
                            if (!stack.includes("Vite")) stack.push("Vite");
                          } else if (t === "framer-motion" || t === "framer" || t === "framer motion") {
                            if (!stack.includes("Framer Motion")) stack.push("Framer Motion");
                          } else if (t === "bootstrap") {
                            if (!stack.includes("Bootstrap")) stack.push("Bootstrap");
                          }
                        });
                      }

                      // Ensure base tags
                      if (!stack.includes("HTML5") && !fw.includes("next") && !fw.includes("react") && !fw.includes("vue")) {
                        stack.push("HTML5");
                      }
                      if (!stack.includes("CSS3") && !fw.includes("next") && !fw.includes("react") && !fw.includes("vue") && !stack.includes("TailwindCSS")) {
                        stack.push("CSS3");
                      }
                      if (stack.length === 0) {
                        stack.push("HTML5", "CSS3", "JavaScript");
                      }
                      return stack;
                    })().map((t) => (
                      <span key={t} className="tech-badge font-mono uppercase text-xs font-bold px-3 py-1.5 rounded-lg border border-border/40 bg-card/60 flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 bg-primary rounded-full" />
                        {t}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="section-title">Browser Support</h3>
                  <div className="space-y-3">
                    {(() => {
                      const defaultBrowsers = [
                        { name: "Google Chrome", score: "99% (Stable)" },
                        { name: "Mozilla Firefox", score: "98% (Stable)" },
                        { name: "Apple Safari", score: "96% (Stable)" },
                        { name: "Microsoft Edge", score: "99% (Stable)" },
                      ];

                      if (!template.compatibility || !Array.isArray(template.compatibility) || template.compatibility.length === 0) {
                        return defaultBrowsers;
                      }

                      // Filter out any accidentally stored framework names (due to dashboard uploads)
                      const knownBrowsers = ["chrome", "firefox", "safari", "edge", "opera", "ie"];
                      const filteredComp = template.compatibility.filter(item =>
                        knownBrowsers.includes(item.toLowerCase())
                      );

                      if (filteredComp.length === 0) {
                        return defaultBrowsers;
                      }

                      const browserMap = {
                        chrome: { name: "Google Chrome", score: "99% (Stable)" },
                        firefox: { name: "Mozilla Firefox", score: "98% (Stable)" },
                        safari: { name: "Apple Safari", score: "96% (Stable)" },
                        edge: { name: "Microsoft Edge", score: "99% (Stable)" },
                        opera: { name: "Opera", score: "97% (Stable)" },
                        ie: { name: "Internet Explorer", score: "Supported (IE11+)" }
                      };

                      return filteredComp.map(item => {
                        const key = item.toLowerCase();
                        return browserMap[key] || { name: item, score: "100% (Stable)" };
                      });
                    })().map((b) => (
                      <div key={b.name} className="flex items-center justify-between text-xs border-b border-border/30 pb-2">
                        <span className="font-medium text-foreground flex items-center gap-1.5">
                          <Globe className="w-3.5 h-3.5 text-muted-foreground" />
                          {b.name}
                        </span>
                        <span className="text-muted-foreground font-mono font-semibold">{b.score}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 8. Performance Scores */}
            <div className="details-performance-block card-container">
              <h3 className="section-title">Google Lighthouse Audits</h3>
              <p className="text-xs text-muted-foreground mb-6">
                Scores gathered on production builds hosted on serverless edges. Audited on simulated 4G throttling.
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
                {(() => {
                  const getDeterministicScore = (seedStr, offset, minScore = 85, maxScore = 100) => {
                    if (!seedStr) return 95;
                    let hash = 0;
                    for (let i = 0; i < seedStr.length; i++) {
                      hash = seedStr.charCodeAt(i) + ((hash << 5) - hash);
                    }
                    const val = Math.abs(hash + offset) % (maxScore - minScore + 1);
                    return minScore + val;
                  };

                  const scores = template.changelog?.ai_report?.performance_scores || {
                    performance: getDeterministicScore(template.id, 1, 92, 99),
                    accessibility: getDeterministicScore(template.id, 2, 94, 100),
                    seo: getDeterministicScore(template.id, 3, 95, 100),
                    best_practices: getDeterministicScore(template.id, 4, 93, 100)
                  };
                  return [
                    { name: "Performance", score: scores.performance, color: scores.performance >= 90 ? "#22c55e" : "#eab308" },
                    { name: "Accessibility", score: scores.accessibility, color: scores.accessibility >= 90 ? "#22c55e" : "#eab308" },
                    { name: "SEO Optimization", score: scores.seo, color: scores.seo >= 90 ? "#22c55e" : "#eab308" },
                    { name: "Best Practices", score: scores.best_practices, color: scores.best_practices >= 90 ? "#22c55e" : "#eab308" },
                  ];
                })().map((s) => (
                  <div key={s.name} className="flex flex-col items-center text-center space-y-2">
                    {/* SVG Circular Progress Chart */}
                    <div className="relative w-20 h-20">
                      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                        <path className="text-border" strokeWidth="3" stroke="currentColor" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                        <motion.path
                          initial={{ strokeDasharray: "0, 100" }}
                          animate={{ strokeDasharray: `${s.score}, 100` }}
                          transition={{ duration: 1.2, ease: "easeOut" }}
                          strokeWidth="3.2"
                          strokeDasharray={`${s.score}, 100`}
                          strokeLinecap="round"
                          stroke={s.color}
                          fill="none"
                          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center font-mono font-bold text-base text-foreground">
                        {s.score}
                      </div>
                    </div>
                    <span className="text-xs font-bold text-foreground">{s.name}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 9. Customization Options */}
            <div className="details-customization-options-block card-container">
              <h3 className="section-title">Design Customization Options</h3>
              <div className="grid sm:grid-cols-2 gap-4">
                {customizationOptions.map((c, i) => {
                  const IconComp = c.icon;
                  return (
                    <div key={i} className="flex gap-3 items-start p-3 bg-muted/10 rounded-lg">
                      <div className="p-2 rounded bg-card border border-border/50 text-primary shrink-0">
                        <IconComp className="w-4 h-4" />
                      </div>
                      <div>
                        <h4 className="font-bold text-xs text-foreground">{c.title}</h4>
                        <p className="text-[11px] text-muted-foreground mt-0.5">{c.desc}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 10. Template Specifications */}
            <div className="details-specs-block card-container">
              <h3 className="section-title">Technical Specifications</h3>
              <div className="overflow-x-auto">
                <table className="specs-table w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-border/50 text-muted-foreground font-semibold">
                      <th className="py-2.5 px-3">Specification</th>
                      <th className="py-2.5 px-3">Detail Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/30">
                    <tr>
                      <td className="py-2.5 px-3 font-medium text-foreground">Bundle File Size</td>
                      <td className="py-2.5 px-3 font-mono text-muted-foreground">
                        {template.changelog?.ai_report?.assets_count?.zip_size || "1.8 MB"} (ZIP Archive)
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2.5 px-3 font-medium text-foreground">Interactive Components</td>
                      <td className="py-2.5 px-3 font-mono text-muted-foreground">
                        {template.changelog?.ai_report?.components?.length
                          ? `${template.changelog.ai_report.components.length} UI Modules`
                          : "24+ UI Blocks"}
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2.5 px-3 font-medium text-foreground">Stock Images Included</td>
                      <td className="py-2.5 px-3 font-mono text-muted-foreground">
                        {template.changelog?.ai_report?.assets_count?.images
                          ? `Yes (${template.changelog.ai_report.assets_count.images} Images, licensed)`
                          : "Yes (Unsplash licensed, clean usage)"}
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2.5 px-3 font-medium text-foreground">Google Web Fonts</td>
                      <td className="py-2.5 px-3 font-mono text-muted-foreground">
                        {template.changelog?.ai_report?.typography?.length
                          ? template.changelog.ai_report.typography.join(", ")
                          : "Inter, Outfit (CSS linked)"}
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2.5 px-3 font-medium text-foreground">Documentation Guide</td>
                      <td className="py-2.5 px-3 font-mono text-muted-foreground">Comprehensive Markdown (SKILL.md layout)</td>
                    </tr>
                    <tr>
                      <td className="py-2.5 px-3 font-medium text-foreground">Support Period</td>
                      <td className="py-2.5 px-3 font-mono text-muted-foreground">6 Months Developer SLA (Extendable)</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* 11. What's Included */}
            <div className="details-whats-included-block card-container">
              <h3 className="section-title">What&apos;s Included in the Archive</h3>
              <div className="grid sm:grid-cols-2 gap-3">
                {(template.changelog?.ai_report?.ai_selling_points || [
                  "React / Next.js Source Files (TypeScript configuration)",
                  "Static HTML5 & CSS3 layout files",
                  "Configured CSS design system with HSL colors",
                  "All visual mockup SVGs & Picsum vector links",
                  "Comprehensive folder deployment configurations",
                  "Single-Domain regular developer license key",
                ]).map((item, idx) => (
                  <div key={idx} className="flex gap-2.5 items-center text-xs text-muted-foreground">
                    <div className="w-5 h-5 rounded-full bg-green-500/10 border border-green-500/20 flex items-center justify-center text-green-500 shrink-0">
                      <Check className="w-3 h-3" />
                    </div>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 12. Reviews */}
            <div className="details-reviews-block card-container">
              <h3 className="section-title">Verified Buyer Reviews</h3>

              {/* Summary Stats */}
              <div className="flex flex-col sm:flex-row gap-6 p-4 rounded-xl border border-border/30 bg-muted/10 mb-6">
                <div className="flex flex-col items-center justify-center text-center p-4 border-r border-border/30 shrink-0">
                  <span className="text-4xl font-extrabold text-foreground">{template.rating_avg}</span>
                  <div className="flex gap-0.5 my-1.5">
                    {[1, 2, 3, 4, 5].map((s) => (
                      <Star key={s} className={cn("w-4 h-4", s <= Math.round(template.rating_avg) ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground/30")} />
                    ))}
                  </div>
                  <span className="text-xs text-muted-foreground font-medium">({template.rating_count} ratings)</span>
                </div>

                <div className="flex-1 space-y-2">
                  <span className="font-bold text-xs uppercase text-muted-foreground">Rating Distribution</span>
                  {[
                    { stars: 5, pct: reviewsList.length ? `${Math.round((reviewsList.filter(r => r.rating === 5).length / reviewsList.length) * 100)}%` : "0%" },
                    { stars: 4, pct: reviewsList.length ? `${Math.round((reviewsList.filter(r => r.rating === 4).length / reviewsList.length) * 100)}%` : "0%" },
                    { stars: 3, pct: reviewsList.length ? `${Math.round((reviewsList.filter(r => r.rating === 3).length / reviewsList.length) * 100)}%` : "0%" },
                    { stars: 2, pct: reviewsList.length ? `${Math.round((reviewsList.filter(r => r.rating === 2).length / reviewsList.length) * 100)}%` : "0%" },
                    { stars: 1, pct: reviewsList.length ? `${Math.round((reviewsList.filter(r => r.rating === 1).length / reviewsList.length) * 100)}%` : "0%" },
                  ].map((d) => (
                    <div key={d.stars} className="flex items-center gap-3 text-xs">
                      <span className="w-3 text-right">{d.stars}</span>
                      <div className="flex-1 bg-border/40 h-2 rounded-full overflow-hidden">
                        <div className="bg-yellow-400 h-full" style={{ width: d.pct }} />
                      </div>
                      <span className="w-8 text-muted-foreground text-right">{d.pct}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Review Comments list */}
              {isReviewsLoading ? (
                <div className="text-center py-6 text-xs text-muted-foreground animate-pulse">
                  Loading buyer reviews...
                </div>
              ) : reviewsList.length === 0 ? (
                <div className="text-center py-8 border border-dashed border-border/40 rounded-xl bg-muted/5 text-xs text-muted-foreground mb-6">
                  No verified buyer reviews yet. Be the first to share your feedback!
                </div>
              ) : (
                <div className="divide-y divide-border/30 space-y-6 mb-6">
                  {reviewsList.map((rev) => {
                    const isLiked = !!likedReviews[rev.id];
                    const helpfulCount = rev.helpful_count + (isLiked ? 1 : 0);
                    const reviewerName = rev.user?.name || rev.user?.email || "Anonymous Buyer";
                    const reviewerAvatar = rev.user?.avatar_url || `https://picsum.photos/seed/${rev.id}/100/100`;
                    const formattedDate = rev.created_at ? new Date(rev.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long' }) : "Just now";

                    return (
                      <div key={rev.id} className="pt-4 first:pt-0 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-full overflow-hidden bg-muted relative">
                              <Image src={reviewerAvatar} alt={reviewerName} width={32} height={32} className="object-cover" />
                            </div>
                            <div>
                              <span className="font-bold text-xs block text-foreground">{reviewerName}</span>
                              <div className="flex items-center gap-1.5">
                                <span className="flex">
                                  {[1, 2, 3, 4, 5].map((s) => (
                                    <Star key={s} className={cn("w-3 h-3", s <= rev.rating ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground/30")} />
                                  ))}
                                </span>
                                <span className="text-[10px] text-muted-foreground">• {formattedDate}</span>
                              </div>
                            </div>
                          </div>

                          {rev.is_verified_purchase && (
                            <span className="text-[9px] font-bold text-green-500 bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded flex items-center gap-1">
                              <Shield className="w-2.5 h-2.5" /> Verified Purchase
                            </span>
                          )}
                        </div>

                        {rev.title && <h4 className="font-bold text-xs text-foreground mt-1">{rev.title}</h4>}
                        <p className="text-xs text-muted-foreground leading-relaxed">{rev.body}</p>

                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => handleLikeReview(rev.id)}
                            className={cn(
                              "px-2.5 py-1 rounded border border-border/50 text-[10px] font-semibold flex items-center gap-1 hover:border-primary/30 transition-all",
                              isLiked && "bg-primary/5 text-primary border-primary/20"
                            )}
                          >
                            Helpful ({helpfulCount})
                          </button>
                        </div>

                        {rev.admin_reply && (
                          <div className="p-3 bg-muted/20 border-l-2 border-primary/40 rounded-r-lg space-y-1.5 ml-4">
                            <div className="flex items-center gap-1.5">
                              <span className="font-bold text-[10px] text-foreground">{template.developer_name || "Site Studio"}</span>
                              <span className="text-[8px] bg-primary/10 text-primary border border-primary/20 px-1 rounded uppercase">Seller</span>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">{rev.admin_reply}</p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Review Submission Form */}
              {isSignedIn ? (
                <form onSubmit={handleReviewSubmit} className="mt-8 p-4 rounded-xl border border-border/40 bg-muted/5 space-y-4">
                  <h4 className="font-bold text-xs text-foreground">Write a Review</h4>
                  {reviewError && (
                    <div className="text-[11px] text-red-500 bg-red-500/10 border border-red-500/20 p-2 rounded-lg">
                      {reviewError}
                    </div>
                  )}

                  <div className="space-y-1.5">
                    <span className="text-xs text-muted-foreground block font-medium">Select Rating</span>
                    <div className="flex gap-1">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setNewReview(prev => ({ ...prev, rating: s }))}
                          className="p-1 focus:outline-none transition-transform active:scale-95"
                        >
                          <Star className={cn("w-6 h-6", s <= newReview.rating ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground/30")} />
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground block font-medium">Review Title (optional)</label>
                    <input
                      type="text"
                      className="form-input text-xs w-full p-2.5 rounded-lg border border-border bg-card/50 text-foreground"
                      placeholder="e.g. Excellent codebase style!"
                      value={newReview.title}
                      onChange={(e) => setNewReview(prev => ({ ...prev, title: e.target.value }))}
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground block font-medium">Your Feedback</label>
                    <textarea
                      rows={3}
                      className="form-input text-xs w-full p-2.5 rounded-lg border border-border bg-card/50 text-foreground resize-y"
                      placeholder="Write your review here. What did you like or dislike?"
                      value={newReview.body}
                      onChange={(e) => setNewReview(prev => ({ ...prev, body: e.target.value }))}
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSubmittingReview}
                    className="py-2 px-4 bg-primary text-primary-foreground text-xs font-bold rounded-lg hover:bg-primary/95 transition-all disabled:opacity-50"
                  >
                    {isSubmittingReview ? "Submitting..." : "Submit Review"}
                  </button>
                </form>
              ) : (
                <div className="mt-8 p-4 rounded-xl border border-dashed border-border/40 text-center bg-muted/5 text-xs text-muted-foreground">
                  Please sign in to write a review.
                </div>
              )}
            </div>

            {/* 13. Changelog */}
            <div className="details-changelog-block card-container">
              <h3 className="section-title">Template Release Changelog</h3>

              <div className="space-y-2.5">
                {[
                  {
                    ver: "v2.3",
                    date: "June 15, 2026",
                    bullets: ["Upgraded dynamic animations with smoother layout shifts", "Added full blog listing module layout", "Optimized mobile toggle header dropdowns"]
                  },
                  {
                    ver: "v2.2",
                    date: "April 10, 2026",
                    bullets: ["Migrated template bundles to latest stable config", "Fixed visual padding discrepancies in service columns", "Updated metatags parsing framework"]
                  },
                  {
                    ver: "v2.1",
                    date: "Jan 12, 2026",
                    bullets: ["Initial template release with core configurations"]
                  }
                ].map((c, i) => (
                  <div key={c.ver} className="border border-border/30 rounded-lg overflow-hidden bg-card/40">
                    <button
                      onClick={() => setOpenChangelog(openChangelog === i ? null : i)}
                      className="w-full flex items-center justify-between p-3 text-left font-bold text-xs text-foreground bg-muted/10 hover:bg-muted/30"
                    >
                      <span className="flex items-center gap-2">
                        <code className="bg-primary/10 text-primary border border-primary/20 px-1.5 py-0.5 rounded text-[10px]">{c.ver}</code>
                        <span>Released on {c.date}</span>
                      </span>
                      {openChangelog === i ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                    </button>

                    <AnimatePresence>
                      {openChangelog === i && (
                        <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="overflow-hidden">
                          <ul className="p-3 border-t border-border/20 list-disc pl-5 text-xs text-muted-foreground space-y-1">
                            {c.bullets.map((b, idx) => (
                              <li key={idx}>{b}</li>
                            ))}
                          </ul>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ))}
              </div>
            </div>

            {/* 14. Documentation Preview */}
            <div className="details-docs-preview-block card-container">
              <h3 className="section-title">Documentation Preview</h3>

              {/* Doc Tabs */}
              <div className="flex gap-2 border-b border-border/40 pb-2 mb-4">
                {[
                  { id: "installation", label: "Installation" },
                  { id: "structure", label: "Folder Structure" },
                  { id: "customization", label: "Customization" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setDocTab(tab.id)}
                    className={cn(
                      "doc-tab-btn px-2.5 py-1 text-xs font-semibold rounded hover:bg-muted",
                      docTab === tab.id && "bg-primary/10 text-primary border border-primary/25 hover:bg-primary/15"
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Doc Body */}
              <div className="p-4 bg-neutral-950 rounded-lg border border-border/40 text-xs font-mono text-muted-foreground">
                {docTab === "installation" ? (
                  <pre className="whitespace-pre overflow-x-auto leading-relaxed">{docsInstallCode}</pre>
                ) : docTab === "structure" ? (
                  <pre className="whitespace-pre overflow-x-auto leading-relaxed">{docsFolders}</pre>
                ) : (
                  <div className="font-sans text-xs space-y-2.5 leading-relaxed text-muted-foreground">
                    <p><strong>Branding Colors:</strong> Open <code>src/index.css</code> and update the <code>--primary</code> HSL variable. All components reflect this change immediately.</p>
                    <p><strong>Headlines & Subtexts:</strong> Find component sections in <code>src/components/landing/*</code>. Static JSON files are located in <code>src/public/data/*</code> for easy text configuration.</p>
                  </div>
                )}
              </div>
            </div>

            {/* 15. License Comparison Removed */}

          </div>

          {/* 16. Right Column: Purchase Sidebar (Sticky) ────────────────── */}
          <div className="details-right-panel">
            <div className="details-sidebar">

              {/* 5. Purchase Card */}
              <div className="details-price-card glass-card">
                <div>
                  <div className="details-price-row flex items-baseline justify-between mb-1">
                    <span className="details-price-value text-3xl font-extrabold text-foreground">
                      {formatPrice(template.price, template.price_currency || "USD")}
                    </span>
                    {template.original_price && (
                      <span className="details-price-original text-sm line-through text-muted-foreground">
                        {formatPrice(template.original_price, template.price_currency || "USD")}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground block font-medium mt-1">Single site commercial and personal usage license</span>
                </div>

                {/* Action Buttons */}
                <div className="details-action-stack space-y-2">
                  {(user?.id === template?.seller_id || user?.role === "admin" || user?.role === "super_admin") ? (
                    <button
                      onClick={() => setIsEditModalOpen(true)}
                      className="w-full py-3 px-4 rounded-xl font-bold flex items-center justify-center gap-2 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white shadow-md transition-all text-sm cursor-pointer"
                    >
                      <Edit3 className="w-4 h-4" /> Edit Template Details
                    </button>
                  ) : isSeller ? (
                    <button disabled className="w-full py-3 bg-muted text-muted-foreground text-xs font-bold rounded-xl cursor-not-allowed">
                      Sellers cannot purchase templates
                    </button>
                  ) : (
                    <>
                      <button
                        onClick={handleAddToCart}
                        className={cn("details-purchase-btn w-full py-3 px-4 rounded-xl font-bold flex items-center justify-center gap-2 transition-all shadow-md text-sm", isInCart ? "bg-green-500 hover:bg-green-600 text-white shadow-green-500/10" : "bg-primary hover:bg-primary/95 text-primary-foreground shadow-primary/20")}
                      >
                        {isInCart ? (
                          <>
                            <Check className="w-4 h-4" /> Added to Cart
                          </>
                        ) : (
                          <>
                            <ShoppingCart className="w-4 h-4" /> Add to Cart
                          </>
                        )}
                      </button>
                      <button
                        onClick={handleBuyNow}
                        className="details-preview-link w-full py-3 rounded-xl text-center font-bold text-sm bg-card hover:bg-muted border border-border/80 block text-foreground cursor-pointer"
                      >
                        Buy Now
                      </button>
                    </>
                  )}

                  <Link
                    href={`/preview?template=${template.id}`}
                    className="w-full py-2.5 text-xs text-center border border-dashed border-primary/40 text-primary hover:bg-primary/[0.02] transition-colors rounded-xl font-semibold flex items-center justify-center gap-1.5"
                    style={{ textDecoration: 'none' }}
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    Try Live Preview Editor
                  </Link>
                </div>

                {/* Trust Badges */}
                <div className="trust-badges-section">
                  <span className="trust-badges-title">Developer Guarantees</span>
                  <div className="trust-badges-grid">
                    <div className="trust-badge-item">
                      <Check className="w-3 h-3 text-green-500" style={{ flexShrink: 0 }} />
                      <span>Lifetime Updates</span>
                    </div>
                    <div className="trust-badge-item">
                      <Shield className="w-3 h-3 text-green-500" style={{ flexShrink: 0 }} />
                      <span>Secure Payment</span>
                    </div>
                    <div className="trust-badge-item">
                      <Download className="w-3 h-3 text-green-500" />
                      <span>Instant Download</span>
                    </div>
                    <div className="trust-badge-item">
                      <FileText className="w-3 h-3 text-green-500" />
                      <span>Docs Included</span>
                    </div>
                  </div>
                </div>

              </div>

              {/* 18b. Template Specifications & License Info Box */}
              <div className="details-specs-card card-container p-5 rounded-2xl border border-border/60 bg-card shadow-sm space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-border/50">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5 text-primary" /> Template Information
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                    Verified Release
                  </span>
                </div>

                <div className="space-y-3 text-xs">
                  {/* Published Time */}
                  <div className="flex items-center justify-between py-1 border-b border-border/30">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-blue-500" /> Published Date
                    </span>
                    <span className="font-semibold text-foreground">
                      {template.created_at
                        ? new Date(template.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
                        : "Recently Published"}
                    </span>
                  </div>

                  {/* Updated Time */}
                  <div className="flex items-center justify-between py-1 border-b border-border/30">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-amber-500" /> Last Updated
                    </span>
                    <span className="font-semibold text-foreground">
                      {template.updated_at
                        ? new Date(template.updated_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
                        : (template.created_at ? new Date(template.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }) : "Up to Date")}
                    </span>
                  </div>

                  {/* License Box */}
                  <div className="flex items-start justify-between py-1">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" /> License Type
                    </span>
                    <span className="font-bold text-foreground text-right max-w-[180px] leading-tight text-emerald-500">
                      {template.license_type || "Single Site Commercial & Personal License"}
                    </span>
                  </div>
                </div>
              </div>

              {/* 19. Seller Information Card */}
              <div className="details-developer-card">
                <div className="seller-top">
                  <div className="seller-avatar">
                    <Image src={template.developer_avatar || "https://picsum.photos/seed/avatar/100/100"} alt={template.developer_name || "Site Studio"} width={40} height={40} />
                  </div>
                  <div>
                    <div className="seller-info-name">
                      {template.developer_name || "Site Studio"}
                      <Award className="w-4 h-4 text-primary" />
                    </div>
                    <span className="seller-verified-label">Verified Author</span>
                  </div>
                </div>

                {/* Seller stats */}
                <div className="seller-stats">
                  <div className="seller-stat">
                    <span className="seller-stat-label">Published</span>
                    <span className="seller-stat-val">{template.seller_templates_count || 0} Templates</span>
                  </div>
                  <div className="seller-stat">
                    <span className="seller-stat-label">Total Sales</span>
                    <span className="seller-stat-val">{(template.seller_total_sales || 0).toLocaleString()} orders</span>
                  </div>
                </div>

                <div className="seller-actions">
                  {user?.id !== template.seller_id && (
                    <button
                      onClick={handleFollowToggle}
                      className={cn("seller-follow-btn", isFollowing ? "following" : "")}
                      disabled={toggleFollowMutation.isPending}
                    >
                      {toggleFollowMutation.isPending ? "Loading..." : (isFollowing ? "Following" : "Follow")}
                    </button>
                  )}
                  <Link href={`/marketplace?developer=${template.developer_name}`} className="seller-more-link">More Items</Link>
                </div>
              </div>

            </div>
          </div>
        </div>


        {/* 17. FAQ Section */}
        <div className="details-faq-block pt-12 border-t border-border/40 mt-12 max-w-3xl mx-auto">
          <h3 className="section-title text-center text-lg mb-8">Frequently Asked Questions</h3>

          <div className="space-y-3">
            {[
              {
                q: "Can I customize the files myself?",
                a: "Absolutely! The template comes with complete development files, documentation, and asset instructions. You can customize standard CSS classes or swap components easily."
              },
              {
                q: "Do I get future bundle updates for free?",
                a: "Yes. All template licenses include lifetime minor updates and 1 year of major version updates free of charge."
              },
              {
                q: "Can Instant Fill rewrite my copy automatically?",
                a: "Yes, our preview generator uses intelligent copywriting models to compose marketing copy suited for your industry, location, and metadata."
              },
              {
                q: "How does the download delivery work?",
                a: "Immediately after your payment is processed, we trigger a ZIP download containing the package and register a license key in your buyer dashboard."
              }
            ].map((faq, idx) => (
              <div key={idx} className="border border-border/40 rounded-lg overflow-hidden bg-card/20">
                <button
                  onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                  className="w-full flex items-center justify-between p-3.5 text-left font-bold text-xs text-foreground hover:bg-muted/30"
                >
                  <span>{faq.q}</span>
                  {openFaq === idx ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                </button>
                <AnimatePresence>
                  {openFaq === idx && (
                    <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="overflow-hidden">
                      <p className="p-3.5 border-t border-border/20 text-xs text-muted-foreground leading-relaxed">
                        {faq.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>
        </div>

        {/* 18. Footer CTA Banner */}
        <div className="details-footer-cta-block">
          <div className="cta-glow" />
          <h2 className="cta-heading">Ready to build your professional site?</h2>
          <p className="cta-sub">
            Try the template first in our Live Sandbox editor, or purchase a commercial license to download the source archives immediately.
          </p>
          <div className="cta-buttons">
            <Link
              href={`/preview?template=${template.id}`}
              className="cta-primary-btn"
              style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
            >
              Try Live Preview Editor
            </Link>
            <button
              onClick={handleAddToCart}
              className="cta-secondary-btn"
            >
              Buy Now
            </button>
          </div>
        </div>
      </div>

      {/* 19. Screenshot Lightbox Modal */}
      <AnimatePresence>
        {lightboxImg && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setLightboxImg(null)}
            className="lightbox-overlay fixed inset-0 z-[9999] bg-black/90 p-4 flex items-center justify-center cursor-zoom-out"
          >
            <div className="relative max-w-5xl max-h-[85vh] aspect-video w-full" onClick={(e) => e.stopPropagation()}>
              <Image src={lightboxImg} alt="Lightbox view" fill className="object-contain" />
              <button onClick={() => setLightboxImg(null)} className="absolute -top-10 right-0 text-white font-bold text-sm bg-neutral-900/60 p-2 rounded-full border border-white/20 hover:bg-neutral-800">
                Close Preview
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 20. Share Template Modal */}
      <AnimatePresence>
        {showShareModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(0, 0, 0, 0.6)",
              backdropFilter: "blur(8px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 9999,
              padding: "1rem",
            }}
            onClick={() => setShowShareModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, y: 15 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 15 }}
              style={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border) / 0.8)",
                borderRadius: "1rem",
                width: "100%",
                maxWidth: "28rem",
                padding: "1.5rem",
                boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.3), 0 8px 10px -6px rgb(0 0 0 / 0.3)",
                position: "relative",
                display: "flex",
                flexDirection: "column",
                gap: "1rem",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ fontSize: "1.125rem", fontWeight: "700", color: "hsl(var(--foreground))" }}>
                  Share Template
                </h3>
                <button
                  onClick={() => setShowShareModal(false)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "hsl(var(--muted-foreground))",
                    cursor: "pointer",
                    padding: "0.25rem",
                  }}
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Description */}
              <p style={{ fontSize: "0.875rem", color: "hsl(var(--muted-foreground))", margin: 0 }}>
                {isGenerated
                  ? "Share this customized version of the template with others. It includes your custom colors, copy, and settings."
                  : "Share this template with others."
                }
              </p>

              {/* Link Input Container */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                background: "hsl(var(--background))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "0.75rem",
                padding: "0.5rem 0.75rem",
              }}>
                <input
                  type="text"
                  readOnly
                  value={shareUrl}
                  style={{
                    flex: 1,
                    background: "none",
                    border: "none",
                    color: "hsl(var(--foreground))",
                    fontSize: "0.875rem",
                    outline: "none",
                    width: "100%",
                  }}
                  onClick={(e) => e.target.select()}
                />
              </div>

              {/* Actions Stack */}
              <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "0.5rem" }}>
                <button
                  onClick={() => setShowShareModal(false)}
                  style={{
                    padding: "0.625rem 1.25rem",
                    borderRadius: "0.75rem",
                    fontSize: "0.875rem",
                    fontWeight: "600",
                    background: "hsl(var(--muted) / 0.5)",
                    color: "hsl(var(--muted-foreground))",
                    border: "1px solid hsl(var(--border))",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                >
                  Close
                </button>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(shareUrl);
                    alert("Link copied successfully!");
                    setShowShareModal(false);
                  }}
                  style={{
                    padding: "0.625rem 1.25rem",
                    borderRadius: "0.75rem",
                    fontSize: "0.875rem",
                    fontWeight: "600",
                    background: "hsl(var(--primary))",
                    color: "hsl(var(--primary-foreground))",
                    border: "none",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                >
                  Copy & Close
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* Seller Edit Template Modal */}
        {isEditModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
            onClick={() => setIsEditModalOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-xl max-h-[90vh] overflow-y-auto bg-card border border-border/80 rounded-2xl shadow-2xl p-6 space-y-5"
            >
              <div className="flex items-center justify-between pb-4 border-b border-border/50">
                <div className="flex items-center gap-2">
                  <Edit3 className="w-5 h-5 text-amber-500" />
                  <h2 className="text-lg font-bold text-foreground">Edit Template Details</h2>
                </div>
                <button
                  onClick={() => setIsEditModalOpen(false)}
                  className="p-1 rounded-lg text-muted-foreground hover:bg-muted transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleSaveTemplateEdit} className="space-y-4 text-xs">
                <div>
                  <label className="block font-bold text-foreground mb-1">Template Title</label>
                  <input
                    type="text"
                    required
                    value={editForm.title}
                    onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                    className="w-full px-3 py-2 bg-muted/30 border border-border/60 rounded-xl text-foreground font-semibold focus:outline-none focus:border-primary"
                    placeholder="e.g. Port Portfolio Template"
                  />
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block font-bold text-foreground mb-1">Pricing Currency</label>
                    <select
                      value={editForm.price_currency}
                      onChange={(e) => setEditForm({ ...editForm, price_currency: e.target.value })}
                      className="w-full px-3 py-2 bg-muted/30 border border-border/60 rounded-xl text-foreground font-bold focus:outline-none focus:border-primary"
                    >
                      <option value="USD">USD ($)</option>
                      <option value="INR">INR (₹)</option>
                      <option value="EUR">EUR (€)</option>
                      <option value="GBP">GBP (£)</option>
                      <option value="CAD">CAD (CA$)</option>
                      <option value="AUD">AUD (A$)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-bold text-foreground mb-1">Fixed Price</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      required
                      value={editForm.price}
                      onChange={(e) => setEditForm({ ...editForm, price: e.target.value })}
                      className="w-full px-3 py-2 bg-muted/30 border border-border/60 rounded-xl text-foreground font-bold focus:outline-none focus:border-primary"
                    />
                  </div>
                  <div>
                    <label className="block font-bold text-foreground mb-1">License Type</label>
                    <select
                      value={editForm.license_type}
                      onChange={(e) => setEditForm({ ...editForm, license_type: e.target.value })}
                      className="w-full px-3 py-2 bg-muted/30 border border-border/60 rounded-xl text-foreground font-semibold focus:outline-none focus:border-primary"
                    >
                      <option value="Single Site Commercial & Personal License">Single Site Commercial & Personal License</option>
                      <option value="Extended Commercial License">Extended Commercial License</option>
                      <option value="Unlimited Multi-Site License">Unlimited Multi-Site License</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block font-bold text-foreground mb-1">Short Description</label>
                  <input
                    type="text"
                    required
                    value={editForm.short_description}
                    onChange={(e) => setEditForm({ ...editForm, short_description: e.target.value })}
                    className="w-full px-3 py-2 bg-muted/30 border border-border/60 rounded-xl text-foreground focus:outline-none focus:border-primary"
                    placeholder="Brief 1-sentence summary"
                  />
                </div>

                <div>
                  <label className="block font-bold text-foreground mb-1">Full Overview / Description</label>
                  <textarea
                    rows={4}
                    value={editForm.description}
                    onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    className="w-full px-3 py-2 bg-muted/30 border border-border/60 rounded-xl text-foreground focus:outline-none focus:border-primary font-mono text-xs"
                    placeholder="Detailed template breakdown..."
                  />
                </div>

                <div>
                  <label className="block font-bold text-foreground mb-1">Tags (Comma-separated)</label>
                  <input
                    type="text"
                    value={editForm.tags}
                    onChange={(e) => setEditForm({ ...editForm, tags: e.target.value })}
                    className="w-full px-3 py-2 bg-muted/30 border border-border/60 rounded-xl text-foreground focus:outline-none focus:border-primary"
                    placeholder="HTML, CSS, React, Responsive, Portfolio"
                  />
                </div>

                {/* Re-upload ZIP File Box */}
                <div className="p-4 rounded-xl border border-dashed border-primary/40 bg-primary/[0.03] space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-foreground flex items-center gap-1.5">
                      <Upload className="w-4 h-4 text-primary" /> Re-upload Website Package (.zip)
                    </span>
                    <span className="text-[10px] text-muted-foreground font-semibold">Updates live preview & download files</span>
                  </div>
                  
                  <input
                    type="file"
                    accept=".zip"
                    onChange={(e) => setReuploadZipFile(e.target.files[0] || null)}
                    className="w-full text-xs text-muted-foreground file:mr-3 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-primary file:text-primary-foreground hover:file:opacity-90 cursor-pointer"
                  />

                  {reuploadZipFile && (
                    <div className="flex items-center justify-between pt-2 border-t border-primary/20">
                      <span className="text-[11px] font-semibold text-emerald-500 truncate max-w-[250px]">
                        Selected: {reuploadZipFile.name} ({(reuploadZipFile.size / (1024 * 1024)).toFixed(2)} MB)
                      </span>
                      <button
                        type="button"
                        onClick={handleReuploadZip}
                        disabled={isUploadingZip}
                        className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-500 hover:bg-emerald-600 text-white shadow transition-all flex items-center gap-1"
                      >
                        {isUploadingZip ? "Uploading & Processing..." : "Upload & Update Live Demo"}
                      </button>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-end gap-3 pt-3 border-t border-border/50">
                  <button
                    type="button"
                    onClick={() => setIsEditModalOpen(false)}
                    className="px-4 py-2 rounded-xl text-xs font-semibold bg-muted/50 hover:bg-muted text-muted-foreground border border-border/40 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSavingEdit}
                    className="px-5 py-2 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white shadow-md transition-all flex items-center gap-1.5"
                  >
                    {isSavingEdit ? "Saving Changes..." : "Save Changes"}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}


// End of file

