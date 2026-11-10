import { useEffect, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import {
  Rocket,
  Globe,
  Edit3,
  ExternalLink,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Server,
  Layers,
  ShieldCheck,
  ShoppingCart,
} from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useAppAuth } from "@/lib/auth";
import { api, API_URL } from "@/lib/api";
import { useStudioBuildStore } from "@/store/studioBuildStore";
import { useCartStore } from "@/store";
import { toast } from "sonner";
import "./Launch.css";

function StudioLaunchPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { getToken } = useAppAuth();
  const buildStore = useStudioBuildStore();
  const addItem = useCartStore((s) => s.addItem);

  const templateId = searchParams.get("template") || localStorage.getItem("last_studio_template_id") || "";
  const buildId = searchParams.get("build") || "";

  const [loading, setLoading] = useState(true);
  const [template, setTemplate] = useState(null);

  // Persist template ID to localStorage for seamless returns
  useEffect(() => {
    if (templateId) {
      localStorage.setItem("last_studio_template_id", templateId);
    }
  }, [templateId]);

  // Fetch Template Data safely with immediate fallback
  useEffect(() => {
    if (!templateId) {
      setLoading(false);
      return;
    }

    let isMounted = true;
    const safetyTimer = setTimeout(() => {
      if (isMounted) setLoading(false);
    }, 800);

    async function fetchProject() {
      try {
        const token = await getToken();
        const data = await api.get(`/templates/${templateId}`, token);
        if (isMounted && data) {
          setTemplate(data);
        }
      } catch (err) {
        console.warn("Could not load template directly, checking build data:", err);
        if (buildId) {
          try {
            const token = await getToken();
            const buildData = await api.get(`/studio/builds/${buildId}`, token);
            if (isMounted && buildData?.template_id) {
              const fallbackTemplate = await api.get(`/templates/${buildData.template_id}`, token);
              if (isMounted && fallbackTemplate) {
                setTemplate(fallbackTemplate);
              }
            }
          } catch (bErr) {
            console.error("Failed to load build data:", bErr);
          }
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    fetchProject();
    return () => {
      isMounted = false;
      clearTimeout(safetyTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [templateId, buildId]);

  // Synthesize effective template data immediately
  const effectiveTemplate = template || {
    id: templateId || buildStore.completedTemplateId || "studio-project",
    title: buildStore.projectTitle || buildStore.plan?.title || "My Studio Website",
    short_description: buildStore.plan?.summary || "Your custom compiled website is ready for live preview, visual edits, or production deployment.",
    framework: buildStore.plan?.stack?.frontend || "html",
    pages_count: buildStore.plan?.pages?.length || 1,
    status: "draft",
    price: 0,
  };

  // Website details
  const siteTitle = effectiveTemplate?.title || "My Studio Website";
  const selectedFramework = String(effectiveTemplate?.framework || "html").toLowerCase();
  const frameworkName = selectedFramework === "react"
    ? "React + FastAPI + PostgreSQL (Full-Stack)"
    : selectedFramework === "vue"
      ? "Vue + FastAPI + PostgreSQL (Full-Stack)"
      : selectedFramework === "angular"
        ? "Angular + FastAPI + PostgreSQL (Full-Stack)"
        : "HTML5 + Modern CSS + JavaScript (Lightweight)";

  const targetIdentifier = effectiveTemplate?.id || effectiveTemplate?.slug || templateId;
  const liveDemoUrl = targetIdentifier ? `${API_URL}/preview/live/${targetIdentifier}/` : "";
  const editorUrl = `/preview?template=${encodeURIComponent(targetIdentifier)}&mode=live${buildId ? `&build=${encodeURIComponent(buildId)}` : ""}`;
  const deployUrl = `/studio/deploy?template=${encodeURIComponent(targetIdentifier)}${buildId ? `&build=${encodeURIComponent(buildId)}` : ""}`;

  // Classified Token-based Price Calculation (Tokens used + 20% interest + taxes)
  const calculateClassifiedPrice = () => {
    // 1. Determine tokens used to create template
    const tokenCount = Number(effectiveTemplate?.changelog?.token_usage)
      || Number(effectiveTemplate?.token_usage)
      || ((effectiveTemplate?.pages_count || 1) * 6500) + 4000;

    // 2. Base token cost ($1.25 per 1,000 tokens)
    const baseCost = Number(((tokenCount / 1000) * 1.25).toFixed(2));

    // 3. 20% Interest (platform markup)
    const interest20 = Number((baseCost * 0.20).toFixed(2));

    // 4. Taxes (10% standard tax)
    const taxAmount = Number(((baseCost + interest20) * 0.10).toFixed(2));

    // 5. Total classified price
    const computedTotal = Number(Math.max(19.00, baseCost + interest20 + taxAmount).toFixed(2));

    // If template has a stored non-zero price, honor it, otherwise use computed
    const finalPrice = Number(effectiveTemplate?.price) > 0 ? Number(effectiveTemplate.price) : computedTotal;

    return {
      price: finalPrice,
      tokenCount,
      baseCost,
      interest20,
      taxAmount,
    };
  };

  // Handle Buy Template: Add to Cart and navigate to Cart/Checkout (Price is revealed in Cart)
  const handleBuyTemplate = () => {
    const pricing = calculateClassifiedPrice();

    addItem({
      templateId: effectiveTemplate.id,
      title: effectiveTemplate.title,
      price: pricing.price,
      price_currency: effectiveTemplate.price_currency || "USD",
      thumbnail: effectiveTemplate.thumbnail_url || "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=85",
      token_usage: pricing.tokenCount,
      base_cost: pricing.baseCost,
      interest_rate: "20%",
      interest_fee: pricing.interest20,
      taxes_amount: pricing.taxAmount,
    });

    toast.success("Template added to cart! Redirecting to checkout…");
    navigate("/checkout");
  };

  return (
    <div className="studio-launch-page">
      <Navbar />

      <main>
        {/* Navigation Breadcrumb with safe clearance below fixed navbar */}
        <div className="launch-top-bar">
          <div className="launch-breadcrumbs">
            <Link to="/studio" className="launch-crumb-link">
              <ArrowLeft size={14} /> Studio Creator
            </Link>
            <span className="launch-crumb-separator">/</span>
            <span className="launch-crumb-title">{siteTitle}</span>
            <span className="launch-crumb-separator">/</span>
            <span className="launch-crumb-badge">Launch Hub</span>
          </div>

          <div className="launch-top-actions">
            <Link to={deployUrl} className="launch-nav-btn launch-nav-btn-deploy">
              <Rocket size={14} />
              <span>Deploy Website</span>
            </Link>
            <Link to="/dashboard" className="launch-nav-btn launch-nav-btn-dash">
              Dashboard
            </Link>
          </div>
        </div>

        {/* Hero Success Card — Clean White/Light Serenity Design */}
        <div className="launch-hero-card">
          <div className="launch-status-pill">
            <CheckCircle2 size={15} />
            <span>Website Compilation Ready</span>
          </div>

          <h1 className="launch-site-title">{siteTitle}</h1>

          <p className="launch-site-desc">
            {effectiveTemplate?.short_description ||
              "Your custom website is completely synthesized with rich content, responsive styling, and production-ready source code."}
          </p>

          <div className="launch-meta-tags">
            <span className="launch-meta-pill">
              <Server size={14} className="launch-meta-icon-violet" />
              <span>{frameworkName}</span>
            </span>
            <span className="launch-meta-pill">
              <Layers size={14} className="launch-meta-icon-indigo" />
              <span>{effectiveTemplate?.pages_count || 1} Pages Generated</span>
            </span>
            <span className="launch-meta-pill">
              <ShieldCheck size={14} className="launch-meta-icon-emerald" />
              <span>100% Mobile Responsive</span>
            </span>
          </div>

          {/* Primary Action Buttons Stack */}
          <div className="launch-actions-stack">
            {/* 1. Buy Template Button (Amount hidden on button; price calculated & revealed in Cart) */}
            <button
              type="button"
              onClick={handleBuyTemplate}
              className="launch-btn-buy"
              title="Add template to cart and proceed to checkout"
            >
              <ShoppingCart size={17} />
              <span>Buy Template &amp; Commercial License</span>
              <ArrowRight size={16} />
            </button>

            {/* 2. Deploy Website (Directly opens Cloud Deploy view) */}
            <Link to={deployUrl} className="launch-btn-deploy">
              <Rocket size={17} />
              <span>Deploy Website</span>
              <ArrowRight size={16} />
            </Link>

            {/* 3. Open Live Demo (Clean browser tab) */}
            <a
              href={liveDemoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="launch-btn-demo"
            >
              <Globe size={16} />
              <span>Open Live Demo</span>
              <ExternalLink size={14} style={{ opacity: 0.75 }} />
            </a>

            {/* 4. Edit in Live Canvas */}
            <Link to={editorUrl} className="launch-btn-edit">
              <Edit3 size={16} style={{ color: "#6366f1" }} />
              <span>Edit in Live Canvas</span>
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

export default StudioLaunchPage;
export { StudioLaunchPage };
