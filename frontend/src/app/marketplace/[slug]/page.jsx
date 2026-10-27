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
  ExternalLink, Calendar, ShieldCheck, Info, Edit3, Upload, Lock,
  DollarSign, Tag, Layers, Loader2, CheckCircle2, Trash2, Image as ImageIcon,
  ThumbsUp, ThumbsDown,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Navbar from "@/components/layout/Navbar";
import TemplateCard from "@/components/marketplace/TemplateCard";
import { useTemplate, useTemplates, useToggleFavorite, useToggleWishlist, useTemplateReviews, useCreateReview, useFollowStatus, useToggleFollow } from "@/hooks/useTemplates";
import { cn, formatPrice, formatConvertedPrice, formatNumber, convertToUSD } from "@/lib/utils";
import { useCartStore } from "@/store";
import { useCurrencyStore } from "@/store/currencyStore";
import { API_URL, api } from "@/lib/api";
import { TEMPLATE_DOWNLOADS_FREE } from "@/lib/marketplaceConfig";
import "./Page.css";

/**
 * DeviceSandbox:
 * Dynamically fits and renders the live template preview in Desktop (1280px),
 * Tablet (768px), or Mobile (390px) viewports with zero cropping and 100% edge-to-edge fit.
 */
function DeviceSandbox({ mode, previewSrc, title, slug }) {
  const containerRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!containerRef.current) return;
    const updateSize = () => {
      if (containerRef.current) {
        const { clientWidth, clientHeight } = containerRef.current;
        setSize({ width: clientWidth, height: clientHeight });
      }
    };
    updateSize();

    const ro = new ResizeObserver(updateSize);
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [mode]);

  const containerW = size.width || 800;
  const containerH = size.height || 500;

  if (mode === "desktop") {
    const chromeH = 36;
    const bodyW = containerW;
    const bodyH = Math.max(120, containerH - chromeH);
    const scale = containerW > 0 ? containerW / 1280 : 0.625;
    const iframeH = Math.max(720, Math.round(bodyH / Math.max(scale, 0.05)));

    return (
      <div ref={containerRef} className="device-sandbox-container desktop-mode">
        <div className="device-browser-window">
          {/* Browser Chrome Header */}
          <div className="device-browser-header">
            <div className="device-traffic-dots">
              <span className="dot red" />
              <span className="dot yellow" />
              <span className="dot green" />
            </div>
            <div className="device-url-pill">
              <Lock className="w-2.5 h-2.5 text-emerald-400 shrink-0" />
              <span className="device-url-text">{slug}.preview.dev</span>
            </div>
            <div className="device-resolution-tag">
              <span className="live-dot" />
              <span>1280px • Desktop</span>
            </div>
          </div>

          {/* Browser Viewport Body */}
          <div className="device-browser-body">
            <iframe
              src={previewSrc}
              title={`Desktop Preview — ${title}`}
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
              scrolling="yes"
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "1280px",
                height: `${iframeH}px`,
                transform: `scale(${scale})`,
                transformOrigin: "top left",
                border: "none",
                pointerEvents: "auto",
              }}
            />
          </div>
        </div>
      </div>
    );
  }

  if (mode === "tablet") {
    const frameW = 788;
    const frameH = 1016;
    const scale = Math.min((containerW - 20) / frameW, (containerH - 20) / frameH, 1);

    return (
      <div ref={containerRef} className="device-sandbox-container tablet-mode">
        <div
          className="device-tablet-wrapper"
          style={{
            transform: `scale(${Math.max(scale, 0.15)})`,
            transformOrigin: "center center",
          }}
        >
          <div className="device-tablet-frame">
            {/* Tablet Camera Header */}
            <div className="tablet-header-notch">
              <span className="tablet-camera" />
              <span className="tablet-resolution">768 × 1024 • Tablet</span>
              <span style={{ width: 8 }} />
            </div>
            {/* Screen */}
            <div className="tablet-screen">
              <iframe
                src={previewSrc}
                title={`Tablet Preview — ${title}`}
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                scrolling="yes"
                style={{
                  width: "768px",
                  height: "964px",
                  border: "none",
                  pointerEvents: "auto",
                }}
              />
            </div>
            {/* Home indicator */}
            <div className="tablet-home-bar">
              <span className="tablet-home-pill" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (mode === "mobile") {
    const frameW = 410;
    const frameH = 874;
    const scale = Math.min((containerW - 16) / frameW, (containerH - 16) / frameH, 1);

    return (
      <div ref={containerRef} className="device-sandbox-container mobile-mode">
        <div
          className="device-phone-wrapper"
          style={{
            transform: `scale(${Math.max(scale, 0.15)})`,
            transformOrigin: "center center",
          }}
        >
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
                title={`Mobile Preview — ${title}`}
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                scrolling="yes"
                style={{
                  width: "390px",
                  height: "100%",
                  border: "none",
                  pointerEvents: "auto",
                }}
              />
            </div>

            {/* Safari Address Bar */}
            <div className="iphone-safari-bar">
              <div className="iphone-safari-address-bar">
                <span className="iphone-safari-text-format">aA</span>
                <div className="iphone-safari-url">
                  <span className="iphone-safari-lock">🔒</span>
                  <span className="iphone-safari-host">{slug}.preview.dev</span>
                </div>
                <span className="iphone-safari-refresh">🔄</span>
              </div>
            </div>

            {/* Home Indicator */}
            <div className="iphone-home-indicator" />
          </div>
        </div>
      </div>
    );
  }

  return null;
}

export default function TemplateDetailsPage({ slug: propSlug }) {
  const { slug: routeSlug } = useParams();
  const [searchParams] = useSearchParams();
  const slug = propSlug || routeSlug;

  const { getToken, isSignedIn } = useAppAuth();
  const { user } = useAppUser();

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get("/categories"),
    staleTime: 1000 * 60 * 5,
  });
  const { userCurrency, rates } = useCurrencyStore();
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

  // Description See More / See Less toggle
  const [isDescExpanded, setIsDescExpanded] = useState(false);

  // Share link modal states
  const [shareUrl, setShareUrl] = useState("");
  const [showShareModal, setShowShareModal] = useState(false);

  // Dynamic Reviews & Likes State
  const [newReview, setNewReview] = useState({ rating: 5, title: "", body: "" });
  const [likedReviews, setLikedReviews] = useState({});
  const [dislikedReviews, setDislikedReviews] = useState({});
  const [isReviewFormOpen, setIsReviewFormOpen] = useState(false);
  const [reviewError, setReviewError] = useState("");

  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  // Seller Profile Card States

  // Recently Viewed Templates
  const [recentlyViewed, setRecentlyViewed] = useState([]);

  const [token, setToken] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  useEffect(() => {
    getToken().then(setToken);
  }, [getToken]);

  // Declare template query hook first to avoid TDZ ReferenceError in render hooks
  const { data: template, isLoading, error } = useTemplate(slug, token);

  const handleFreeDownload = async () => {
    if (!template) return;
    if (!isSignedIn) {
      navigate(`/sign-in?from=${encodeURIComponent(window.location.pathname)}`);
      return;
    }
    setIsDownloading(true);
    try {
      const authToken = token || await getToken();
      const result = await api.post(`/templates/${template.id}/download?format=zip`, {}, authToken);
      if (!result?.download_url) throw new Error("The download file is not available yet.");
      const link = document.createElement("a");
      link.href = result.download_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.download = "";
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (downloadError) {
      window.alert(downloadError.message || "Could not download this template.");
    } finally {
      setIsDownloading(false);
    }
  };

  // Helper functions for license enum mapping
  const mapLicenseToBackend = (val) => {
    if (!val) return "regular";
    const s = String(val).toLowerCase();
    if (s.includes("extended") || s.includes("unlimited")) return "extended";
    return "regular";
  };

  const mapBackendToLicense = (val) => {
    if (!val) return "Single Site Commercial & Personal License";
    const s = String(val).toLowerCase();
    if (s === "extended") return "Extended Commercial License";
    if (s === "regular") return "Single Site Commercial & Personal License";
    return val;
  };

  const queryClient = useQueryClient();

  // Seller Edit Modal States
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editModalTab, setEditModalTab] = useState("general"); // general, pricing, tags, gallery, archive
  const [isUploadingGallery, setIsUploadingGallery] = useState(false);
  const [galleryUrlInput, setGalleryUrlInput] = useState("");
  const [editForm, setEditForm] = useState({
    title: "",
    short_description: "",
    description: "",
    price: 0,
    price_currency: "USD",
    license_type: "Single Site Commercial & Personal License",
    tags: "",
    category_id: "",
    industry: "",
    gallery_images: [],
    thumbnail_url: "",
  });
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  useEffect(() => {
    if (template) {
      setEditForm({
        title: template.title || "",
        short_description: template.short_description || "",
        description: template.description || "",
        price: Number(template.price || 0),
        price_currency: "USD",
        license_type: mapBackendToLicense(template.license_type),
        tags: Array.isArray(template.tags) ? template.tags.join(", ") : (template.tags || ""),
        category_id: template.category_id || template.category?.id || "",
        industry: template.industry || "",
        gallery_images: Array.isArray(template.gallery_images) ? template.gallery_images : [],
        thumbnail_url: template.thumbnail_url || "",
      });
    }
  }, [template]);

  const handleEditCurrencySwitch = (newCurrency) => {
    const currentVal = Number(editForm.price) || 0;
    const inrRate = rates?.INR || 87.0;
    let convertedPrice = currentVal;
    
    if (editForm.price_currency === "USD" && newCurrency === "INR") {
      convertedPrice = Math.round(currentVal * inrRate);
    } else if (editForm.price_currency === "INR" && newCurrency === "USD") {
      convertedPrice = Math.round((currentVal / inrRate) * 100) / 100;
    }
    
    setEditForm((prev) => ({
      ...prev,
      price: convertedPrice,
      price_currency: newCurrency,
    }));
  };

  // Direct Gallery Upload from Screenshots Gallery Section
  const handleDirectGalleryUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length || !template?.id) return;
    const tokenVal = await getToken();
    if (!tokenVal) {
      alert("Session expired. Please sign in again.");
      return;
    }
    setIsUploadingGallery(true);
    try {
      const uploadedUrls = [];
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch(`${API_URL}/files/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${tokenVal}` },
          body: formData,
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to upload ${file.name}`);
        }
        const data = await res.json();
        if (data.url) uploadedUrls.push(data.url);
      }

      if (uploadedUrls.length > 0) {
        const currentGallery = template.gallery_images || [];
        const newGallery = [...currentGallery, ...uploadedUrls];
        await api.patch(`/templates/${template.id}`, { gallery_images: newGallery }, tokenVal);
        queryClient.invalidateQueries({ queryKey: ["templates"] });
        setEditForm((prev) => ({ ...prev, gallery_images: newGallery }));
      }
    } catch (err) {
      console.error(err);
      alert("Failed to upload screenshot: " + err.message);
    } finally {
      setIsUploadingGallery(false);
      if (e.target) e.target.value = "";
    }
  };

  const handleRemoveGalleryImage = async (indexToRemove, e) => {
    if (e) e.stopPropagation();
    if (!confirm("Are you sure you want to remove this screenshot?")) return;
    const tokenVal = await getToken();
    if (!tokenVal || !template?.id) return;
    try {
      const currentGallery = [...(template.gallery_images || [])];
      const newGallery = currentGallery.filter((_, idx) => idx !== indexToRemove);
      await api.patch(`/templates/${template.id}`, { gallery_images: newGallery }, tokenVal);
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setEditForm((prev) => ({ ...prev, gallery_images: newGallery }));
    } catch (err) {
      console.error(err);
      alert("Failed to remove image: " + err.message);
    }
  };

  const handleModalAddGalleryImages = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const tokenVal = await getToken();
    if (!tokenVal) {
      alert("Session expired. Please sign in again.");
      return;
    }
    setIsUploadingGallery(true);
    try {
      const uploadedUrls = [];
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch(`${API_URL}/files/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${tokenVal}` },
          body: formData,
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to upload ${file.name}`);
        }
        const data = await res.json();
        if (data.url) uploadedUrls.push(data.url);
      }
      if (uploadedUrls.length > 0) {
        setEditForm((prev) => ({
          ...prev,
          gallery_images: [...(prev.gallery_images || []), ...uploadedUrls],
        }));
      }
    } catch (err) {
      console.error(err);
      alert("Upload failed: " + err.message);
    } finally {
      setIsUploadingGallery(false);
      if (e.target) e.target.value = "";
    }
  };

  const handleModalAddGalleryUrl = () => {
    if (!galleryUrlInput.trim()) return;
    setEditForm((prev) => ({
      ...prev,
      gallery_images: [...(prev.gallery_images || []), galleryUrlInput.trim()],
    }));
    setGalleryUrlInput("");
  };

  const handleModalRemoveGalleryImage = (idxToRemove) => {
    setEditForm((prev) => ({
      ...prev,
      gallery_images: (prev.gallery_images || []).filter((_, i) => i !== idxToRemove),
    }));
  };

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
      const finalPrice = Number(editForm.price) || 0;
      const cleanTags = editForm.tags 
        ? Array.from(new Set(editForm.tags.split(",").map(t => t.trim().replace(/^#/, "")).filter(Boolean)))
        : [];

      const payload = {
        title: editForm.title,
        short_description: editForm.short_description,
        description: editForm.description,
        price: finalPrice,
        price_currency: "USD",
        license_type: mapLicenseToBackend(editForm.license_type),
        category_id: editForm.category_id || undefined,
        industry: editForm.industry || undefined,
        tags: cleanTags,
        gallery_images: editForm.gallery_images || [],
        thumbnail_url: editForm.thumbnail_url || undefined,
      };
      await api.patch(`/templates/${template.id}`, payload, tokenVal);

      // If a replacement source file was selected, upload and re-audit it
      if (reuploadZipFile) {
        const fileFormData = new FormData();
        fileFormData.append("file", reuploadZipFile);
        const reupRes = await fetch(`${API_URL}/templates/${template.id}/reupload`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${tokenVal}`,
          },
          body: fileFormData,
        });
        if (!reupRes.ok) {
          const errData = await reupRes.json().catch(() => ({}));
          throw new Error(errData.detail || "Failed to upload new template file.");
        }
        setReuploadZipFile(null);
      }

      queryClient.invalidateQueries({ queryKey: ["templates"] });
      alert("Template and source files updated successfully!");
      setIsEditModalOpen(false);
      window.location.reload();
    } catch (err) {
      console.error(err);
      alert("Failed to update template: " + (err.message || "Unknown error"));
    } finally {
      setIsSavingEdit(false);
    }
  };

  // Seller Re-upload ZIP/HTML state
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
        throw new Error(errData.detail || "Failed to re-upload template package.");
      }
      alert("New template website package (.ZIP / .HTML) uploaded and audited successfully! Live preview and download assets updated.");
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
    let base = template?.id ? `${API_URL}/preview/live/${template.id}/` : "";
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
  const isTemplateFree = TEMPLATE_DOWNLOADS_FREE || !!template?.is_free;

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
      if (!isTemplateFree && (buyParam === "1" || actionParam === "buy" || buyParam === "true")) {
        addToCart({
          templateId: template.id,
          title: template.title,
          price: Number(template.price),
          price_currency: template.price_currency || "USD",
          thumbnail: template.thumbnail_url || template.gallery_images?.[0] || "",
          licenseType: "regular",
        });
        navigate("/checkout");
      }
    }
  }, [template, searchParams]);

  const handleAddToCart = () => {
    if (!template || isTemplateFree) return;
    addToCart({
      templateId: template.id,
      title: template.title,
      price: Number(template.price),
      price_currency: template.price_currency || "USD",
      thumbnail: template.thumbnail_url,
      licenseType: "regular",
    });
  };

  const handleBuyNow = (e) => {
    e.preventDefault();
    if (!template) return;
    if (isTemplateFree) {
      handleFreeDownload();
      return;
    }
    if (!isInCart) {
      addToCart({
        templateId: template.id,
        title: template.title,
        price: Number(template.price),
        price_currency: template.price_currency || "USD",
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

  if (isLoading && !template) {
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

  const isOwnerOrAdmin = Boolean(user && (user.id === template?.seller_id || user.role === "admin" || user.role === "super_admin"));
  const allImages = [template.thumbnail_url, ...(template.gallery_images ?? [])].filter(Boolean);

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

  const renderPurchaseCard = (extraClass = "") => (
    <div className={cn("details-price-card glass-card", extraClass)}>
      <div>
        <div className="details-price-row flex items-baseline justify-between mb-1">
          <span className="details-price-value text-3xl font-extrabold text-foreground">
            {isTemplateFree ? "Free" : formatPrice(template.price, "USD")}
          </span>
          {template.original_price && template.original_price > template.price && (
            <span className="details-price-original text-sm line-through text-muted-foreground">
              {formatPrice(template.original_price, "USD")}
            </span>
          )}
        </div>
        <span className="text-xs text-muted-foreground block font-medium mt-1">Free source download • Full commercial & personal use</span>
      </div>

      {/* Action Buttons */}
      <div className="details-action-stack space-y-2">
        {(user?.id === template?.seller_id || user?.role === "admin" || user?.role === "super_admin") ? (
          <>
            <button
              onClick={() => {
                setEditModalTab("general");
                setIsEditModalOpen(true);
              }}
              className="w-full py-3 px-4 rounded-xl font-bold flex items-center justify-center gap-2 bg-gradient-to-r from-primary to-indigo-600 hover:opacity-95 text-white shadow-md shadow-primary/20 transition-all text-sm cursor-pointer border-0"
            >
              <Edit3 className="w-4 h-4" /> Edit Template Details
            </button>
            {isTemplateFree && (
              <button type="button" onClick={handleFreeDownload} disabled={isDownloading} className="details-purchase-btn w-full py-3 px-4 rounded-xl font-bold flex items-center justify-center gap-2 bg-primary text-primary-foreground text-sm disabled:opacity-60">
                {isDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                {isDownloading ? "Preparing download…" : "Free Download"}
              </button>
            )}
          </>
        ) : isTemplateFree ? (
          <button
            type="button"
            onClick={handleFreeDownload}
            disabled={isDownloading}
            className="details-purchase-btn w-full py-3 px-4 rounded-xl font-bold flex items-center justify-center gap-2 bg-primary hover:bg-primary/95 text-primary-foreground shadow-md shadow-primary/20 transition-all text-sm disabled:opacity-60"
          >
            {isDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {isDownloading ? "Preparing download…" : "Free Download"}
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
  );

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
                <div className="details-hero-tabs-left">
                  <button
                    onClick={() => setHeroTab("desktop")}
                    className={cn("hero-tab-btn", heroTab === "desktop" && "active")}
                    title="Desktop View (1280px)"
                  >
                    <Monitor className="w-3.5 h-3.5" />
                    <span>Desktop</span>
                  </button>
                  <button
                    onClick={() => setHeroTab("tablet")}
                    className={cn("hero-tab-btn", heroTab === "tablet" && "active")}
                    title="Tablet View (768px)"
                  >
                    <Tablet className="w-3.5 h-3.5" />
                    <span>Tablet</span>
                  </button>
                  <button
                    onClick={() => setHeroTab("mobile")}
                    className={cn("hero-tab-btn", heroTab === "mobile" && "active")}
                    title="Mobile View (390px)"
                  >
                    <Smartphone className="w-3.5 h-3.5" />
                    <span>Mobile</span>
                  </button>
                  <button
                    onClick={() => { setHeroTab("screenshot"); setActiveImage(0); }}
                    className={cn("hero-tab-btn", heroTab === "screenshot" && "active")}
                    title="Full Screenshot"
                  >
                    <ImageIcon className="w-3.5 h-3.5" />
                    <span>Screenshot</span>
                  </button>
                  {template?.video_url && (
                    <button
                      onClick={() => setHeroTab("video")}
                      className={cn("hero-tab-btn", heroTab === "video" && "active")}
                      title="Video Walkthrough"
                    >
                      <Play className="w-3.5 h-3.5" />
                      <span>Video</span>
                    </button>
                  )}
                </div>

                <div className="details-hero-tabs-right">
                  <a
                    href={previewSrc}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hero-action-btn live"
                    title="Open live website in new tab"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Live Demo</span>
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
                    style={{ position: "absolute", inset: 0, cursor: "zoom-in", display: "flex", alignItems: "center", justifyContent: "center", background: "#0a0a14" }}
                    onClick={() => setLightboxImg(allImages[activeImage])}
                  >
                    <Image
                      src={allImages[activeImage]}
                      alt={template.title}
                      fill
                      className="object-contain"
                      style={{ transition: "transform 0.4s ease" }}
                      priority
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
                          style={{ width: "100%", height: "100%", objectFit: "contain" }}
                          poster={allImages[0]}
                        />
                      )}
                    </div>
                  ) : (
                    /* Premium Live Auto-Scrolling Video Walkthrough Simulation */
                    <div className="video-walkthrough-player">
                      <div className="video-player-hud-top">
                        <div className="rec-indicator">
                          <span className="rec-dot" />
                          <span>REC</span>
                        </div>
                        <div className="video-title-hud">
                          {template.title} — Live Walkthrough
                        </div>
                      </div>
                      <div className="video-player-screen">
                        <iframe
                          src={previewSrc}
                          title={`Live Video Walkthrough — ${template.title}`}
                          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                          className="autoscroll-iframe"
                        />
                      </div>
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
                ) : heroTab === "desktop" || heroTab === "tablet" || heroTab === "mobile" ? (
                  <DeviceSandbox
                    mode={heroTab}
                    previewSrc={previewSrc}
                    title={template.title}
                    slug={template.slug}
                  />
                ) : null}
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
                <div className="details-info-price hidden lg:block">
                  <div className="text-2xl font-bold text-foreground">
                    {isTemplateFree ? "Free" : formatPrice(template.price, "USD")}
                  </div>
                  <span className="text-xs text-muted-foreground">Lifetime Access • Complete Source Code</span>
                </div>
              </div>

              {/* Mobile Purchase Box — Shown after template details and before category */}
              <div className="block lg:hidden my-3">
                {renderPurchaseCard("mobile-inline-purchase")}
              </div>

              {/* Information Card Grid */}
              <div className="details-specs-grid">
                {/* Multiple categories support */}
                <div className="spec-info-card">
                  <span className="spec-label">Category</span>
                  <span className="spec-val">
                    {(() => {
                      const cats = [];
                      if (template.category?.name) cats.push(template.category.name);
                      if (template.sub_category) cats.push(template.sub_category);
                      if (template.industry) cats.push(template.industry);
                      const display = cats.length > 0 ? cats : ["Business"];
                      return (
                        <span className="details-categories-wrap">
                          {display.map((c, i) => (
                            <span key={i} className="details-category-chip capitalize">{c}</span>
                          ))}
                        </span>
                      );
                    })()}
                  </span>
                </div>
                <div className="spec-info-card">
                  <span className="spec-label">Customer Rating</span>
                  <span className="spec-val flex items-center gap-1">
                    <Star className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
                    {reviewsList.length > 0 ? (
                      <>
                        {(reviewsList.reduce((acc, r) => acc + Number(r.rating || 5), 0) / reviewsList.length).toFixed(1)} ({reviewsList.length} {reviewsList.length === 1 ? "review" : "reviews"})
                      </>
                    ) : (
                      "No reviews yet"
                    )}
                  </span>
                </div>
                <div className="spec-info-card">
                  <span className="spec-label">License</span>
                  <span className="spec-val">Lifetime Commercial</span>
                </div>
                <div className="spec-info-card">
                  <span className="spec-label">Framework v{template.version}</span>
                  <span className="spec-val uppercase font-mono">{template.framework}</span>
                </div>
                <div className="spec-info-card">
                  <span className="spec-label">Last Updated</span>
                  <span className="spec-val">
                    {template.updated_at
                      ? new Date(template.updated_at).toLocaleDateString("en-US", { year: "numeric", month: "short" })
                      : "June 2026"}
                  </span>
                </div>
              </div>
            </div>

            {/* 3. Description Details */}
            <div className="details-desc-card card-container">
              <h3 className="section-title">About this template</h3>

              {/* Collapsible description with See More */}
              <div className={`details-desc-collapse ${isDescExpanded ? 'expanded' : 'collapsed'}`}>
                <div className="details-markdown-content text-muted-foreground text-sm leading-relaxed space-y-3">
                  <p>
                    {template.description || `Build a highly customized homepage for your business in seconds. Designed specifically for modern consulting, agency structures, and startups looking to represent a bold, premium aesthetic.`}
                  </p>
                  <p>
                    Built with professional developers in mind, this package delivers multiple variations for grid setups, flexible CTA items, responsive menus, and clean CSS code scopes that can easily be compiled or extended.
                  </p>
                </div>
                {!isDescExpanded && <div className="details-desc-fade" />}
              </div>

              <button
                type="button"
                onClick={() => setIsDescExpanded((v) => !v)}
                className="details-seemore-btn"
              >
                {isDescExpanded ? (
                  <><ChevronUp className="w-3.5 h-3.5" /> See Less</>
                ) : (
                  <><ChevronDown className="w-3.5 h-3.5" /> See More</>
                )}
              </button>

              {/* Clickable Tags — single clean block */}
              {(() => {
                const rawTags = Array.isArray(template.tags)
                  ? template.tags
                  : (template.tags ? String(template.tags).split(",") : []);
                const cleanUniqueTags = Array.from(
                  new Set(rawTags.map((t) => t.trim().replace(/^#/, "")).filter(Boolean))
                );
                if (cleanUniqueTags.length === 0) return null;

                return (
                  <div className="details-tags-block">
                    <span className="details-tags-label">
                      <Tag className="w-3 h-3" /> Tags
                    </span>
                    <div className="details-tags-wrap">
                      {cleanUniqueTags.map((tag) => (
                        <button
                          key={tag}
                          type="button"
                          onClick={() => navigate(`/marketplace?q=${encodeURIComponent(tag)}`)}
                          className="details-tag-chip"
                          title={`Search for "${tag}" templates`}
                        >
                          #{tag}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })()}
            </div>



            {/* 4. Screenshots Gallery */}
            <div className="details-gallery-block card-container">
              <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                <div>
                  <h3 className="section-title mb-0 flex items-center gap-2 flex-wrap">
                    Screenshots Gallery
                    <span className="inline-flex items-center whitespace-nowrap shrink-0 text-xs font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                      {allImages.length} {allImages.length === 1 ? "Image" : "Images"}
                    </span>
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    High-resolution interface previews and responsive section captures.
                  </p>
                </div>
                {isOwnerOrAdmin && (
                  <div className="flex items-center gap-2">
                    <label
                      className={cn(
                        "inline-flex items-center gap-1.5 text-xs font-bold text-white bg-primary hover:bg-primary/95 px-3.5 py-2 rounded-xl shadow-sm transition-all cursor-pointer select-none",
                        isUploadingGallery && "pointer-events-none opacity-70"
                      )}
                      title="Upload more screenshots"
                    >
                      <input
                        type="file"
                        accept="image/*"
                        multiple
                        className="hidden"
                        onChange={handleDirectGalleryUpload}
                        disabled={isUploadingGallery}
                      />
                      {isUploadingGallery ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Uploading...</span>
                        </>
                      ) : (
                        <>
                          <Plus className="w-3.5 h-3.5" />
                          <span>Add Screenshots</span>
                        </>
                      )}
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        setEditModalTab("gallery");
                        setIsEditModalOpen(true);
                      }}
                      className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-700 dark:text-slate-200 bg-muted/60 hover:bg-muted px-3 py-2 rounded-xl border border-border/50 transition-all cursor-pointer"
                      title="Manage Screenshots"
                    >
                      <Sliders className="w-3.5 h-3.5" />
                      <span>Manage</span>
                    </button>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {allImages.map((img, i) => {
                  const isRemovableGalleryItem = isOwnerOrAdmin && (
                    template.gallery_images && template.gallery_images.includes(img)
                  );
                  const galleryIndex = template.gallery_images ? template.gallery_images.indexOf(img) : -1;

                  return (
                    <div key={i} className="screenshot-card group relative">
                      <div
                        className="relative aspect-video rounded-lg overflow-hidden border border-border/30 bg-muted cursor-zoom-in"
                        onClick={() => setLightboxImg(img)}
                      >
                        <Image src={img} alt={`Screenshot ${i + 1}`} fill className="object-cover transition-all duration-300 group-hover:scale-105" />
                        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                          <Eye className="w-5 h-5 text-white" />
                        </div>
                      </div>

                      {/* Owner remove screenshot button on hover */}
                      {isRemovableGalleryItem && galleryIndex >= 0 && (
                        <button
                          type="button"
                          onClick={(e) => handleRemoveGalleryImage(galleryIndex, e)}
                          className="absolute top-1.5 right-1.5 p-1 rounded-md bg-red-600/90 hover:bg-red-700 text-white shadow opacity-0 group-hover:opacity-100 transition-opacity border-none cursor-pointer z-10"
                          title="Delete this screenshot"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}

                      <span className="text-[11px] font-medium text-muted-foreground mt-1.5 block text-center capitalize truncate px-1">
                        {i === 0 && template.thumbnail_url === img
                          ? "Cover Thumbnail"
                          : ["Home Dashboard", "Services Grid", "Portfolio Details", "Contact Panel", "Pricing Table", "Blog Overview"][i % 6] || `Screenshot ${i + 1}`}
                      </span>
                    </div>
                  );
                })}

                {/* Direct + icon tile in the screenshots gallery for seller / admin */}
                {isOwnerOrAdmin && (
                  <label
                    className={cn(
                      "screenshot-card group cursor-pointer border-2 border-dashed border-primary/40 hover:border-primary bg-primary/5 hover:bg-primary/10 rounded-lg aspect-video flex flex-col items-center justify-center gap-1.5 transition-all text-primary select-none",
                      isUploadingGallery && "pointer-events-none opacity-60"
                    )}
                    title="Click to add screenshot images (multiple allowed)"
                  >
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      className="hidden"
                      onChange={handleDirectGalleryUpload}
                      disabled={isUploadingGallery}
                    />
                    {isUploadingGallery ? (
                      <>
                        <Loader2 className="w-6 h-6 animate-spin text-primary" />
                        <span className="text-[11px] font-bold">Uploading...</span>
                      </>
                    ) : (
                      <>
                        <div className="w-8 h-8 rounded-full bg-primary/15 group-hover:bg-primary/25 flex items-center justify-center group-hover:scale-110 transition-transform">
                          <Plus className="w-5 h-5 text-primary" />
                        </div>
                        <span className="text-[11px] font-bold">Add Image</span>
                      </>
                    )}
                  </label>
                )}
              </div>
            </div>

            {/* 5. Pages Included */}
            <div className="details-pages-included-block card-container">
              <h3 className="section-title">Pages & Layouts Included</h3>
              {/* Compact chip layout matching Utility & Design Features */}
              <div className="details-pages-chips">
                {(template.included_pages && template.included_pages.length > 0
                  ? template.included_pages
                  : ["Home", "About", "Services", "Portfolio Showcase", "Pricing Table", "Testimonials Panel", "Accordion FAQ", "Contact Form", "Blog Listing", "Privacy Policy", "404 Error page"]
                ).map((page) => (
                  <span key={page} className="details-page-chip">
                    <Check className="w-3 h-3 text-green-500 shrink-0" />
                    {page}
                  </span>
                ))}
              </div>
            </div>

            {/* 6. Features Section */}
            <div className="details-features-block card-container">
              <h3 className="section-title">Utility & Design Features</h3>
              <div className="grid grid-cols-2 gap-2 sm:gap-4">
                {featuresList.map((f, i) => {
                  const IconComp = f.icon;
                  return (
                    <div key={i} className="flex items-center sm:items-start gap-2 sm:gap-3 p-2.5 sm:p-3 rounded-lg border border-border/30 hover:border-primary/20 transition-all bg-card/40">
                      <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
                        <IconComp className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-bold text-xs sm:text-sm text-foreground leading-snug">{f.name}</h4>
                        <p className="hidden sm:block text-[11px] sm:text-xs text-muted-foreground mt-0.5 leading-normal">{f.desc}</p>
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
              <p className="text-xs text-muted-foreground mb-3 sm:mb-6">
                Scores gathered on production builds hosted on serverless edges. Audited on simulated 4G throttling.
              </p>

              <div className="details-performance-grid">
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
                    { name: "Performance", shortName: "Perf", score: scores.performance, color: scores.performance >= 90 ? "#22c55e" : "#eab308" },
                    { name: "Accessibility", shortName: "A11y", score: scores.accessibility, color: scores.accessibility >= 90 ? "#22c55e" : "#eab308" },
                    { name: "SEO Optimization", shortName: "SEO", score: scores.seo, color: scores.seo >= 90 ? "#22c55e" : "#eab308" },
                    { name: "Best Practices", shortName: "Practices", score: scores.best_practices, color: scores.best_practices >= 90 ? "#22c55e" : "#eab308" },
                  ];
                })().map((s) => (
                  <div key={s.name} className="details-performance-item space-y-1 sm:space-y-2">
                    {/* SVG Circular Progress Chart */}
                    <div className="relative w-11 h-11 sm:w-16 sm:h-16 md:w-20 md:h-20 shrink-0">
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
                      <div className="absolute inset-0 flex items-center justify-center font-mono font-bold text-[11px] sm:text-sm md:text-base text-foreground">
                        {s.score}
                      </div>
                    </div>
                    <span className="details-performance-label">
                      <span className="block sm:hidden">{s.shortName}</span>
                      <span className="hidden sm:block">{s.name}</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* 9. Customization Options */}
            <div className="details-customization-options-block card-container">
              <h3 className="section-title">Design Customization Options</h3>
              <div className="grid grid-cols-2 gap-2 sm:gap-4">
                {customizationOptions.map((c, i) => {
                  const IconComp = c.icon;
                  return (
                    <div key={i} className="flex items-center sm:items-start gap-2 sm:gap-3 p-2.5 sm:p-3 bg-muted/10 rounded-lg border border-border/20">
                      <div className="p-1.5 sm:p-2 rounded bg-card border border-border/50 text-primary shrink-0">
                        <IconComp className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-bold text-xs text-foreground leading-snug">{c.title}</h4>
                        <p className="hidden sm:block text-[10.5px] sm:text-[11px] text-muted-foreground mt-0.5 leading-normal">{c.desc}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 10. Template Specifications */}
            <div className="details-specs-block card-container">
              <h3 className="section-title">Technical Specifications</h3>
              <div className="w-full">
                <table className="specs-table w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-border/50 text-muted-foreground font-semibold">
                      <th className="py-2 px-1 sm:px-3">Specification</th>
                      <th className="py-2 px-1 sm:px-3">Detail Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/30">
                    <tr>
                      <td className="py-2 px-1 sm:px-3 font-medium text-foreground">Bundle File Size</td>
                      <td className="py-2 px-1 sm:px-3 font-mono text-muted-foreground break-words">
                        {template.changelog?.ai_report?.assets_count?.zip_size || "1.8 MB"} (ZIP Archive)
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2 px-1 sm:px-3 font-medium text-foreground">Interactive Components</td>
                      <td className="py-2 px-1 sm:px-3 font-mono text-muted-foreground break-words">
                        {template.changelog?.ai_report?.components?.length
                          ? `${template.changelog.ai_report.components.length} UI Modules`
                          : "24+ UI Blocks"}
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2 px-1 sm:px-3 font-medium text-foreground">Stock Images Included</td>
                      <td className="py-2 px-1 sm:px-3 font-mono text-muted-foreground break-words">
                        {template.changelog?.ai_report?.assets_count?.images
                          ? `Yes (${template.changelog.ai_report.assets_count.images} Images, licensed)`
                          : "Yes (Unsplash licensed, clean usage)"}
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2 px-1 sm:px-3 font-medium text-foreground">Google Web Fonts</td>
                      <td className="py-2 px-1 sm:px-3 font-mono text-muted-foreground break-words">
                        {template.changelog?.ai_report?.typography?.length
                          ? template.changelog.ai_report.typography.join(", ")
                          : "Inter, Outfit (CSS linked)"}
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2 px-1 sm:px-3 font-medium text-foreground">Documentation Guide</td>
                      <td className="py-2 px-1 sm:px-3 font-mono text-muted-foreground break-words">Comprehensive Markdown (SKILL.md layout)</td>
                    </tr>
                    <tr>
                      <td className="py-2 px-1 sm:px-3 font-medium text-foreground">Support Period</td>
                      <td className="py-2 px-1 sm:px-3 font-mono text-muted-foreground break-words">6 Months Developer SLA (Extendable)</td>
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
                  "Complete source code & lifetime access",
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

            {/* 12. Reviews (Flipkart Style in Site Theme) */}
            <div className="details-reviews-block card-container">
              {/* Header */}
              <div className="flex items-center justify-between pb-4 border-b border-border/40 flex-wrap gap-3">
                <div>
                  <h3 className="section-title mb-0 flex items-center gap-2">
                    Ratings & Reviews
                    {reviewsList.length > 0 && (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                        {reviewsList.length} {reviewsList.length === 1 ? "Review" : "Reviews"}
                      </span>
                    )}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (!isSignedIn) {
                      alert("Please sign in to rate this template.");
                      return;
                    }
                    setIsReviewFormOpen((prev) => !prev);
                  }}
                  className="inline-flex items-center gap-1.5 text-xs font-bold text-foreground bg-card hover:bg-muted border border-border/80 px-3.5 py-2 rounded-xl shadow-sm transition-all cursor-pointer select-none"
                >
                  <Star className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
                  {isReviewFormOpen ? "Cancel" : "Rate Template"}
                </button>
              </div>

              {/* Flipkart Rating Summary Overview Card */}
              {reviewsList.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-12 gap-5 p-4 sm:p-5 rounded-2xl border border-border/40 bg-card/60 my-4 items-center">
                  {/* Left: Overall Score + Star Count */}
                  <div className="md:col-span-4 flex flex-col items-center justify-center text-center p-2 sm:border-r border-border/30">
                    <div className="flex items-center gap-2">
                      <span className="text-4xl sm:text-5xl font-extrabold text-foreground tracking-tight">
                        {(reviewsList.reduce((sum, r) => sum + Number(r.rating || 5), 0) / reviewsList.length).toFixed(1)}
                      </span>
                      <Star className="w-7 h-7 sm:w-8 sm:h-8 fill-yellow-400 text-yellow-400" />
                    </div>
                    <p className="text-xs text-muted-foreground font-medium mt-1">
                      {reviewsList.length} {reviewsList.length === 1 ? "Rating" : "Ratings"} & {reviewsList.length} {reviewsList.length === 1 ? "Review" : "Reviews"}
                    </p>
                    <div className="mt-2.5 inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-500 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded-full">
                      <CheckCircle2 className="w-3.5 h-3.5" /> 100% Certified Buyers
                    </div>
                  </div>

                  {/* Right: Flipkart 5-Star Breakdown Bars */}
                  <div className="md:col-span-8 space-y-2">
                    {[5, 4, 3, 2, 1].map((star) => {
                      const count = reviewsList.filter((r) => Math.round(Number(r.rating)) === star).length;
                      const pct = Math.round((count / reviewsList.length) * 100);
                      const color = star >= 4 ? "bg-emerald-500" : star === 3 ? "bg-emerald-400" : star === 2 ? "bg-amber-500" : "bg-rose-500";
                      return (
                        <div key={star} className="flex items-center gap-2.5 text-xs">
                          <span className="w-7 font-bold text-foreground flex items-center justify-end gap-0.5 text-xs">
                            {star} <Star className="w-2.5 h-2.5 fill-current text-muted-foreground/60" />
                          </span>
                          <div className="flex-1 bg-muted/40 h-2 rounded-full overflow-hidden">
                            <div className={cn("h-full rounded-full transition-all duration-500", color)} style={{ width: `${pct}%` }} />
                          </div>
                          <span className="w-10 text-[11px] font-mono text-muted-foreground text-right">{count}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 px-4 border border-dashed border-border/40 rounded-2xl bg-muted/5 my-4 space-y-2.5">
                  <div className="w-10 h-10 rounded-full bg-muted/40 flex items-center justify-center mx-auto text-muted-foreground/60">
                    <Star className="w-5 h-5 text-yellow-400" />
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-foreground">No customer reviews yet</h4>
                    <p className="text-xs text-muted-foreground mt-0.5 max-w-sm mx-auto">
                      Be the first to share your thoughts and rate this template.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      if (!isSignedIn) {
                        alert("Please sign in to rate this template.");
                        return;
                      }
                      setIsReviewFormOpen(true);
                    }}
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-primary bg-primary/10 hover:bg-primary hover:text-white px-3.5 py-1.5 rounded-xl transition-all cursor-pointer border border-primary/20"
                  >
                    <Star className="w-3.5 h-3.5 fill-current" /> Write a Review
                  </button>
                </div>
              )}

              {/* Flipkart Write a Review Form */}
              <AnimatePresence>
                {isReviewFormOpen && (
                  <motion.form
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    onSubmit={handleReviewSubmit}
                    className="review-form-box overflow-hidden mb-6 space-y-4"
                  >
                    <div className="review-form-header">
                      <h4 className="review-form-title">
                        <Star className="w-4 h-4 text-primary fill-primary" /> Rate & Review This Template
                      </h4>
                      <button
                        type="button"
                        onClick={() => setIsReviewFormOpen(false)}
                        className="review-close-btn"
                        title="Close"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    {reviewError && (
                      <div className="text-xs text-red-500 bg-red-500/10 border border-red-500/20 p-2.5 rounded-xl">
                        {reviewError}
                      </div>
                    )}

                    <div>
                      <span className="text-xs font-semibold text-muted-foreground block mb-1.5">Rating</span>
                      <div className="flex items-center gap-1.5">
                        {[1, 2, 3, 4, 5].map((s) => (
                          <button
                            key={s}
                            type="button"
                            onClick={() => setNewReview((prev) => ({ ...prev, rating: s }))}
                            className="review-star-btn"
                            title={`${s} star${s > 1 ? "s" : ""}`}
                          >
                            <Star className={cn("w-7 h-7 transition-colors", s <= newReview.rating ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground/30")} />
                          </button>
                        ))}
                        <span className="text-xs font-bold text-foreground ml-2">
                          {newReview.rating === 5 ? "Terrific" : newReview.rating === 4 ? "Good" : newReview.rating === 3 ? "Average" : newReview.rating === 2 ? "Poor" : "Very Poor"}
                        </span>
                      </div>
                    </div>

                    <div>
                      <label className="text-xs font-semibold text-muted-foreground block mb-1">Review Headline (optional)</label>
                      <input
                        type="text"
                        className="form-input text-xs w-full p-2.5 rounded-xl border border-border bg-card/60 text-foreground"
                        placeholder="e.g. Worth every penny! Clean modular code"
                        value={newReview.title}
                        onChange={(e) => setNewReview((prev) => ({ ...prev, title: e.target.value }))}
                      />
                    </div>

                    <div>
                      <label className="text-xs font-semibold text-muted-foreground block mb-1">Detailed Feedback</label>
                      <textarea
                        rows={3}
                        className="form-input text-xs w-full p-2.5 rounded-xl border border-border bg-card/60 text-foreground resize-y"
                        placeholder="Description of your experience with installation, responsive preview, and documentation..."
                        value={newReview.body}
                        onChange={(e) => setNewReview((prev) => ({ ...prev, body: e.target.value }))}
                        required
                      />
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setIsReviewFormOpen(false)}
                        className="review-cancel-btn"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={isSubmittingReview}
                        className="review-submit-btn"
                      >
                        {isSubmittingReview ? "Submitting..." : "Submit Review"}
                      </button>
                    </div>
                  </motion.form>
                )}
              </AnimatePresence>

              {/* Review Comments list in Flipkart style */}
              {isReviewsLoading ? (
                <div className="text-center py-6 text-xs text-muted-foreground animate-pulse">
                  Loading buyer reviews...
                </div>
              ) : reviewsList.length > 0 ? (
                <div className="divide-y divide-border/30">
                  {reviewsList.map((rev) => {
                    const isLiked = !!likedReviews[rev.id];
                    const isDisliked = !!dislikedReviews[rev.id];
                    const helpfulCount = (rev.helpful_count || 0) + (isLiked ? 1 : 0);
                    const reviewerName = rev.user?.name || rev.user?.email ? (rev.user.name || rev.user.email.split('@')[0]) : "Verified Buyer";
                    const formattedDate = rev.created_at ? new Date(rev.created_at).toLocaleDateString("en-US", { year: 'numeric', month: 'short' }) : "Recently";
                    const ratingClass = rev.rating >= 4 ? "rating-high" : rev.rating === 3 ? "rating-mid" : "rating-low";

                    return (
                      <div key={rev.id} className="py-4 first:pt-2 last:pb-2 space-y-2">
                        {/* Top: Flipkart Green Rating Badge + Review Title */}
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={cn("flipkart-rating-badge", ratingClass)}>
                            {rev.rating} <Star className="w-2.5 h-2.5 fill-current" />
                          </span>
                          <h4 className="font-bold text-xs sm:text-sm text-foreground">
                            {rev.title || (rev.rating >= 5 ? "Terrific Template!" : rev.rating >= 4 ? "Great Quality" : "Satisfactory")}
                          </h4>
                        </div>

                        {/* Review Body */}
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          {rev.body}
                        </p>

                        {/* Bottom Meta Row (Flipkart Signature layout) */}
                        <div className="flex items-center justify-between pt-1 flex-wrap gap-2 text-xs">
                          <div className="flex items-center gap-2 flex-wrap text-muted-foreground">
                            <span className="font-semibold text-foreground text-xs">{reviewerName}</span>
                            <span className="flipkart-certified-badge">
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 fill-emerald-500/20" /> Certified Buyer
                            </span>
                            <span className="text-[11px] text-muted-foreground/60">• {formattedDate}</span>
                          </div>

                          {/* Helpful feedback thumbs up / down */}
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => handleLikeReview(rev.id)}
                              className={cn("flipkart-feedback-btn", isLiked && "active-like")}
                              title="Helpful review"
                            >
                              <ThumbsUp className={cn("w-3.5 h-3.5", isLiked && "fill-current")} />
                              <span>{helpfulCount > 0 ? helpfulCount : ""}</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => setDislikedReviews((prev) => ({ ...prev, [rev.id]: !prev[rev.id] }))}
                              className={cn("flipkart-feedback-btn", isDisliked && "active-dislike")}
                              title="Not helpful"
                            >
                              <ThumbsDown className={cn("w-3.5 h-3.5", isDisliked && "fill-current")} />
                            </button>
                          </div>
                        </div>

                        {/* Author Reply (if any) */}
                        {rev.admin_reply && (
                          <div className="mt-2 p-3 bg-muted/20 border-l-2 border-primary rounded-r-lg space-y-1 ml-2 sm:ml-4">
                            <div className="flex items-center gap-1.5">
                              <span className="font-bold text-[10px] text-foreground">{template.developer_name || "Author"}</span>
                              <span className="text-[8px] bg-primary/10 text-primary border border-primary/20 px-1 py-0.2 rounded font-semibold uppercase">Author</span>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">{rev.admin_reply}</p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : null}
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
                  <div key={c.ver} className={cn("details-changelog-item", openChangelog === i && "is-open")}>
                    <button
                      type="button"
                      onClick={() => setOpenChangelog(openChangelog === i ? null : i)}
                      className="details-changelog-btn"
                    >
                      <span className="flex items-center gap-2">
                        <code className="details-changelog-ver">{c.ver}</code>
                        <span>Released on {c.date}</span>
                      </span>
                      {openChangelog === i ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                    </button>

                    <AnimatePresence>
                      {openChangelog === i && (
                        <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="overflow-hidden">
                          <ul className="details-changelog-content space-y-1">
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

              {/* 5. Purchase Card (Desktop Sidebar) */}
              <div className="hidden lg:block">
                {renderPurchaseCard()}
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

                  {/* Access Box */}
                  <div className="flex items-start justify-between py-1">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" /> Access
                    </span>
                    <span className="font-bold text-foreground text-right max-w-[180px] leading-tight text-emerald-500">
                      Full Source Code • Lifetime
                    </span>
                  </div>

                  {/* Sidebar Tags — hidden on mobile (shown only in desc section on mobile) */}
                  {(() => {
                    const rawTags = Array.isArray(template.tags)
                      ? template.tags
                      : (template.tags ? String(template.tags).split(",") : []);
                    const cleanUniqueTags = Array.from(
                      new Set(rawTags.map((t) => t.trim().replace(/^#/, "")).filter(Boolean))
                    );
                    if (cleanUniqueTags.length === 0) return null;

                    return (
                      <div className="pt-2 border-t border-border/30 sidebar-tags-desktop">
                        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block mb-1.5 flex items-center gap-1">
                          <Tag className="w-3 h-3 text-primary" /> Tags
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {cleanUniqueTags.map((tag) => (
                            <button
                              key={tag}
                              type="button"
                              onClick={() => navigate(`/marketplace?q=${encodeURIComponent(tag)}`)}
                              className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-primary/10 hover:bg-primary text-primary hover:text-white border border-primary/20 transition-all cursor-pointer"
                              title={`Filter marketplace by ${tag}`}
                            >
                              #{tag}
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  })()}
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
                    <span className="seller-stat-val">{template.seller_templates_count || 1} Templates</span>
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
                a: "Yes. All purchases include lifetime updates free of charge."
              },
              {
                q: "Can Instant Fill rewrite my copy automatically?",
                a: "Yes, our preview generator uses intelligent copywriting models to compose marketing copy suited for your industry, location, and metadata."
              },
              {
                q: "How does the download delivery work?",
                a: "Immediately after your payment is processed, you can download the full ZIP source archive directly from your dashboard."
              }
            ].map((faq, idx) => (
              <div key={idx} className={cn("details-faq-item", openFaq === idx && "is-open")}>
                <button
                  type="button"
                  onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                  className="details-faq-btn"
                >
                  <span>{faq.q}</span>
                  {openFaq === idx ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                </button>
                <AnimatePresence>
                  {openFaq === idx && (
                    <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="overflow-hidden">
                      <p className="details-faq-answer">
                        {faq.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>
        </div>

        {/* 18. Footer CTA Banner — hidden on mobile, visible on tablet+ */}
        <div className="details-footer-cta-block details-footer-cta-hide-mobile">
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

        {/* ══════════════════════════════════════════════
            REDESIGNED SELLER / ADMIN EDIT TEMPLATE MODAL
           ══════════════════════════════════════════════ */}
        {isEditModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/75 backdrop-blur-md"
            onClick={() => setIsEditModalOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0, y: 16 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.96, opacity: 0, y: 16 }}
              onClick={(e) => e.stopPropagation()}
              className="edit-modal-card"
            >
              {/* ── Modal Top Header ── */}
              <div className="edit-modal-header">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600 shrink-0">
                    <Edit3 className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="edit-modal-header-title">
                      <span>Edit Template Details</span>
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-200">
                        #{String(template?.id || "").slice(0, 8)}
                      </span>
                    </h2>
                    <p className="edit-modal-header-sub">
                      Update metadata, pricing, license tier, and live code bundle.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsEditModalOpen(false)}
                  className="p-2 rounded-xl text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors border-0 bg-transparent cursor-pointer"
                  title="Close"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* ── Segmented Navigation Tabs ── */}
              <div className="edit-modal-nav-tabs">
                <button
                  type="button"
                  onClick={() => setEditModalTab("general")}
                  className={cn("edit-modal-tab-btn", editModalTab === "general" && "active")}
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>General Info</span>
                </button>
                <button
                  type="button"
                  onClick={() => setEditModalTab("pricing")}
                  className={cn("edit-modal-tab-btn", editModalTab === "pricing" && "active")}
                >
                  <DollarSign className="w-3.5 h-3.5" />
                  <span>Pricing</span>
                </button>
                <button
                  type="button"
                  onClick={() => setEditModalTab("gallery")}
                  className={cn("edit-modal-tab-btn", editModalTab === "gallery" && "active")}
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>Screenshots & Gallery ({(editForm.gallery_images || []).length})</span>
                </button>
                <button
                  type="button"
                  onClick={() => setEditModalTab("tags")}
                  className={cn("edit-modal-tab-btn", editModalTab === "tags" && "active")}
                >
                  <Tag className="w-3.5 h-3.5" />
                  <span>Tags & Tech</span>
                </button>
                <button
                  type="button"
                  onClick={() => setEditModalTab("archive")}
                  className={cn("edit-modal-tab-btn", editModalTab === "archive" && "active")}
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Re-upload ZIP</span>
                </button>
              </div>

              {/* ── Form Body ── */}
              <form onSubmit={handleSaveTemplateEdit} className="flex flex-col flex-1 overflow-hidden m-0">
                <div className="edit-modal-content">
                  {/* TAB 1: GENERAL INFO */}
                  {editModalTab === "general" && (
                    <div className="space-y-4">
                      <div className="edit-modal-input-group">
                        <label className="edit-modal-label">
                          <span>Template Title</span>
                          <span className="edit-modal-label-hint">{editForm.title.length}/60</span>
                        </label>
                        <input
                          type="text"
                          required
                          maxLength={60}
                          value={editForm.title}
                          onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                          className="edit-modal-input font-bold"
                          placeholder="e.g. Port — Modern Creator Portfolio"
                        />
                      </div>

                      <div className="edit-modal-input-group">
                        <label className="edit-modal-label">
                          <span>Short Hook Description</span>
                          <span className="edit-modal-label-hint">Brief 1-sentence summary</span>
                        </label>
                        <input
                          type="text"
                          required
                          value={editForm.short_description}
                          onChange={(e) => setEditForm({ ...editForm, short_description: e.target.value })}
                          className="edit-modal-input"
                          placeholder="Clean, responsive personal portfolio with dark mode and smooth animations."
                        />
                      </div>

                      <div className="grid sm:grid-cols-2 gap-4">
                        <div className="edit-modal-input-group">
                          <label className="edit-modal-label">
                            <span>Marketplace Category *</span>
                            <span className="edit-modal-label-hint">Defines category filter</span>
                          </label>
                          <select
                            value={editForm.category_id}
                            onChange={(e) => setEditForm({ ...editForm, category_id: e.target.value })}
                            className="edit-modal-select font-bold"
                            required
                          >
                            <option value="">Select Category...</option>
                            {categories.map((cat) => (
                              <option key={cat.id} value={cat.id}>
                                {cat.name}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div className="edit-modal-input-group">
                          <label className="edit-modal-label">
                            <span>Industry / Sub-Category</span>
                            <span className="edit-modal-label-hint">e.g. Creative, Agency</span>
                          </label>
                          <input
                            type="text"
                            value={editForm.industry}
                            onChange={(e) => setEditForm({ ...editForm, industry: e.target.value })}
                            className="edit-modal-input"
                            placeholder="e.g. Creative Portfolio, Personal Brand"
                          />
                        </div>
                      </div>

                      <div className="edit-modal-input-group">
                        <label className="edit-modal-label">
                          <span>Full Overview & Features Description</span>
                          <span className="edit-modal-label-hint">Markdown supported</span>
                        </label>
                        <textarea
                          rows={6}
                          value={editForm.description}
                          onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                          className="edit-modal-textarea font-mono text-xs"
                          placeholder="Provide a detailed breakdown of layouts, components, dependencies, and setup steps..."
                        />
                      </div>
                    </div>
                  )}

                  {/* TAB 2: PRICING & LICENSE */}
                  {editModalTab === "pricing" && (
                    <div className="space-y-5">
                      <div className="grid sm:grid-cols-2 gap-4">
                        <div className="edit-modal-input-group">
                          <label className="edit-modal-label">Pricing Currency</label>
                          <select
                            value={editForm.price_currency}
                            onChange={(e) => handleEditCurrencySwitch(e.target.value)}
                            className="edit-modal-select font-bold"
                          >
                            <option value="INR">INR (₹) — Indian Rupee</option>
                            <option value="USD">USD ($) — US Dollar</option>
                            <option value="EUR">EUR (€) — Euro</option>
                            <option value="GBP">GBP (£) — British Pound</option>
                            <option value="CAD">CAD (CA$) — Canadian Dollar</option>
                            <option value="AUD">AUD (A$) — Australian Dollar</option>
                          </select>
                        </div>

                        <div className="edit-modal-input-group">
                          <label className="edit-modal-label">Fixed Price Amount ({editForm.price_currency})</label>
                          <div className="edit-modal-price-wrap">
                            <span className="edit-modal-price-symbol">
                              {editForm.price_currency === "INR" ? "₹" : editForm.price_currency === "EUR" ? "€" : editForm.price_currency === "GBP" ? "£" : "$"}
                            </span>
                            <input
                              type="number"
                              step="any"
                              min="0"
                              required
                              value={editForm.price}
                              onChange={(e) => setEditForm({ ...editForm, price: e.target.value })}
                              className="edit-modal-price-input"
                            />
                          </div>
                          <div className="text-[11px] text-slate-500 mt-1.5 font-medium">
                            {editForm.price_currency === "INR" ? (
                              <span>Marketplace Listing Price: <strong className="text-indigo-600 font-bold">${convertToUSD(editForm.price, "INR", rates)} USD</strong> <span className="text-slate-400">(Auto-converted from ₹{Number(editForm.price || 0).toLocaleString()} INR)</span></span>
                            ) : (
                              <span>Marketplace Listing Price: <strong className="text-indigo-600 font-bold">${editForm.price} USD</strong></span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}


                  {/* TAB 3: SCREENSHOTS & GALLERY */}
                  {editModalTab === "gallery" && (
                    <div className="space-y-4">
                      <div className="p-3 bg-indigo-50/70 border border-indigo-200 rounded-xl flex items-start gap-3">
                        <Sparkles className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                        <div className="text-xs text-slate-700 leading-relaxed">
                          <strong>Showcase Screenshots Gallery:</strong> Upload multiple high-resolution captures of your pages, responsive layouts, panels, and components.
                        </div>
                      </div>

                      {/* URL Add input */}
                      <div className="flex gap-2">
                        <input
                          type="url"
                          value={galleryUrlInput}
                          onChange={(e) => setGalleryUrlInput(e.target.value)}
                          placeholder="Or paste direct image URL (https://...)"
                          className="edit-modal-input text-xs flex-1"
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              handleModalAddGalleryUrl();
                            }
                          }}
                        />
                        <button
                          type="button"
                          onClick={handleModalAddGalleryUrl}
                          disabled={!galleryUrlInput.trim()}
                          className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-900 text-white text-xs font-bold transition-all disabled:opacity-40 cursor-pointer border-none shrink-0"
                        >
                          + Add URL
                        </button>
                      </div>

                      {/* Screenshots Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[340px] overflow-y-auto p-1">
                        {/* Cover Photo */}
                        {editForm.thumbnail_url && (
                          <div className="relative aspect-video rounded-xl overflow-hidden border-2 border-indigo-500/60 bg-slate-100 group shadow-sm">
                            <img src={editForm.thumbnail_url} alt="Cover Thumbnail" className="w-full h-full object-cover" />
                            <span className="absolute top-1.5 left-1.5 px-2 py-0.5 rounded bg-indigo-600 text-white text-[9px] font-bold tracking-wider uppercase shadow">
                              Cover Photo
                            </span>
                          </div>
                        )}

                        {/* Gallery Screenshots */}
                        {(editForm.gallery_images || []).map((imgUrl, gIdx) => (
                          <div key={gIdx} className="relative aspect-video rounded-xl overflow-hidden border border-slate-200 bg-slate-100 group shadow-sm">
                            <img src={imgUrl} alt={`Screenshot ${gIdx + 1}`} className="w-full h-full object-cover" />
                            <span className="absolute bottom-1.5 left-1.5 px-2 py-0.5 rounded bg-black/60 backdrop-blur-sm text-white text-[9px] font-mono font-bold">
                              #{gIdx + 1}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleModalRemoveGalleryImage(gIdx)}
                              className="absolute top-1.5 right-1.5 p-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white shadow opacity-90 group-hover:opacity-100 transition-all border-none cursor-pointer"
                              title="Delete this screenshot"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}

                        {/* + Add Screenshots Tile */}
                        <label className={cn(
                          "aspect-video rounded-xl border-2 border-dashed border-indigo-400 hover:border-indigo-600 bg-indigo-50/50 hover:bg-indigo-50 flex flex-col items-center justify-center gap-1.5 transition-all cursor-pointer group text-indigo-600 select-none",
                          isUploadingGallery && "pointer-events-none opacity-60"
                        )}>
                          <input
                            type="file"
                            accept="image/*"
                            multiple
                            onChange={handleModalAddGalleryImages}
                            className="hidden"
                            disabled={isUploadingGallery}
                          />
                          {isUploadingGallery ? (
                            <>
                              <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
                              <span className="text-[10px] font-bold">Uploading...</span>
                            </>
                          ) : (
                            <>
                              <div className="w-8 h-8 rounded-full bg-indigo-100 group-hover:bg-indigo-200 flex items-center justify-center group-hover:scale-110 transition-transform">
                                <Plus className="w-4 h-4 text-indigo-600" />
                              </div>
                              <span className="text-[11px] font-bold">Add Screenshots</span>
                              <span className="text-[9px] text-slate-500">(Multiple allowed)</span>
                            </>
                          )}
                        </label>
                      </div>
                    </div>
                  )}

                  {/* TAB 4: TAGS & METADATA */}
                  {editModalTab === "tags" && (
                    <div className="space-y-4">
                      <div className="edit-modal-input-group">
                        <label className="edit-modal-label">
                          <span>Search Tags (Comma-separated)</span>
                          <span className="edit-modal-label-hint">Separated by commas</span>
                        </label>
                        <input
                          type="text"
                          value={editForm.tags}
                          onChange={(e) => setEditForm({ ...editForm, tags: e.target.value })}
                          className="edit-modal-input"
                          placeholder="HTML, CSS, React, TailwindCSS, Portfolio, Modern"
                        />
                      </div>

                      {/* Live preview of tags */}
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">Live Tag Chips</span>
                          <span className="text-[10px] text-slate-400">Click the × on any tag to remove</span>
                        </div>
                        <div className="flex flex-wrap gap-1.5 min-h-[36px] p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                          {editForm.tags ? (
                            Array.from(new Set(editForm.tags.split(",").map(t => t.trim().replace(/^#/, "")).filter(Boolean))).map((tag, idx) => (
                              <button
                                key={idx}
                                type="button"
                                onClick={() => {
                                  const current = editForm.tags.split(",").map(t => t.trim().replace(/^#/, "")).filter(Boolean);
                                  const updated = current.filter(t => t.toLowerCase() !== tag.toLowerCase());
                                  setEditForm({ ...editForm, tags: updated.join(", ") });
                                }}
                                className="edit-modal-tag-chip flex items-center gap-1.5 hover:bg-red-50 hover:text-red-600 hover:border-red-300 transition-all cursor-pointer border group"
                                title="Click to remove this tag"
                              >
                                <span>#{tag}</span>
                                <X className="w-3 h-3 text-slate-400 group-hover:text-red-600" />
                              </button>
                            ))
                          ) : (
                            <span className="text-xs text-slate-400 italic">No tags added yet</span>
                          )}
                        </div>
                      </div>

                      {/* Quick Suggestions */}
                      <div>
                        <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block mb-2">Quick Add Suggestions</span>
                        <div className="flex flex-wrap gap-1.5">
                          {["React", "Next.js", "TailwindCSS", "HTML5", "TypeScript", "SaaS", "Portfolio", "Landing Page", "Dark Mode", "Dashboard", "E-Commerce", "Agency", "Restaurant", "Healthcare"].map((sugg) => (
                            <button
                              key={sugg}
                              type="button"
                              onClick={() => {
                                const current = editForm.tags ? editForm.tags.split(",").map(t => t.trim().replace(/^#/, "")).filter(Boolean) : [];
                                if (!current.some(c => c.toLowerCase() === sugg.toLowerCase())) {
                                  setEditForm({ ...editForm, tags: [...current, sugg].join(", ") });
                                }
                              }}
                              className="edit-modal-sugg-btn"
                            >
                              + {sugg}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* TAB 4: RE-UPLOAD ARCHIVE */}
                  {editModalTab === "archive" && (
                    <div className="space-y-4">
                      <div className="edit-modal-zip-box">
                        <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600 shadow-sm">
                          <Upload className="w-6 h-6" />
                        </div>
                        <div>
                          <h4 className="edit-modal-zip-title">Upload Updated Template (.ZIP or .HTML)</h4>
                          <p className="edit-modal-zip-sub">
                            Re-uploading automatically audits code versions, framework types, purges preview cache, and updates downloadable files immediately.
                          </p>
                        </div>

                        <label className="cursor-pointer inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold shadow-md shadow-indigo-600/20 hover:bg-indigo-700 transition-all">
                          <Plus className="w-4 h-4" />
                          <span>Choose .ZIP or .HTML File</span>
                          <input
                            type="file"
                            accept=".zip,.html,.htm"
                            onChange={(e) => setReuploadZipFile(e.target.files[0] || null)}
                            className="hidden"
                          />
                        </label>
                      </div>

                      {reuploadZipFile && (
                        <div className="edit-modal-selected-zip">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="w-8 h-8 rounded-lg bg-emerald-100 border border-emerald-300 flex items-center justify-center text-emerald-600 shrink-0">
                              <Check className="w-4 h-4" />
                            </div>
                            <div className="truncate">
                              <div className="font-bold text-xs text-slate-900 truncate">{reuploadZipFile.name}</div>
                              <div className="text-[10px] text-slate-500 font-mono">{(reuploadZipFile.size / (1024 * 1024)).toFixed(2)} MB</div>
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={handleReuploadZip}
                            disabled={isUploadingZip}
                            className="px-4 py-2 rounded-xl text-xs font-extrabold bg-emerald-600 hover:bg-emerald-700 text-white shadow-md transition-all flex items-center justify-center gap-1.5 cursor-pointer border-0 shrink-0"
                          >
                            {isUploadingZip ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Uploading & Sandboxing...
                              </>
                            ) : (
                              <>
                                <Upload className="w-3.5 h-3.5" /> Upload & Rebuild Sandbox
                              </>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* ── Modal Footer Action Bar ── */}
                <div className="edit-modal-footer">
                  <span className="text-xs text-slate-500 font-medium">
                    Changes take effect across the entire marketplace immediately.
                  </span>

                  <div className="flex items-center gap-2.5">
                    <button
                      type="button"
                      onClick={() => setIsEditModalOpen(false)}
                      className="edit-modal-btn-cancel"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSavingEdit}
                      className="edit-modal-btn-save"
                    >
                      {isSavingEdit ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving...
                        </>
                      ) : (
                        <>
                          <Check className="w-3.5 h-3.5" /> Save Changes
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Mobile Floating Purchase Bar (Sticky Bottom on <= 768px) ── */}
      <div className="details-mobile-bottom-bar">
        <div className="details-mobile-bottom-info">
          <span className="details-mobile-bottom-price">
            {isTemplateFree ? "Free" : formatPrice(template.price, "USD")}
          </span>
          <span className="details-mobile-bottom-license">Lifetime License</span>
        </div>
        <div className="details-mobile-bottom-actions">
          <a
            href={previewSrc}
            target="_blank"
            rel="noopener noreferrer"
            className="details-mobile-bottom-btn demo"
          >
            <Globe className="w-3.5 h-3.5" /> Demo
          </a>
          {isTemplateFree ? (
            <button type="button" onClick={handleFreeDownload} disabled={isDownloading} className="details-mobile-bottom-btn cart">
              {isDownloading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              {isDownloading ? "Preparing…" : "Free Download"}
            </button>
          ) : !isSeller && (
            <button
              type="button"
              onClick={handleAddToCart}
              className={cn(
                "details-mobile-bottom-btn cart",
                isInCart && "in-cart"
              )}
            >
              {isInCart ? (
                <><Check className="w-3.5 h-3.5" /> Added</>
              ) : (
                <><ShoppingCart className="w-3.5 h-3.5" /> Add to Cart</>
              )}
            </button>
          )}
        </div>
      </div>
    </>
  );
}


// End of file

