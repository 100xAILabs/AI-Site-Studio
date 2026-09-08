import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  X,
  Sparkles,
  Layers,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Globe,
  ShoppingCart,
  Zap,
  Lock,
  Info,
  Cpu,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import "./FigmaImportModal.css";

export default function FigmaImportModal({ isOpen, onClose, onDeploy }) {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  // Check if current user has Seller or Admin privileges
  const isSeller =
    user?.role === "seller" ||
    user?.role === "SELLER" ||
    user?.role === "admin" ||
    user?.role === "super_admin" ||
    user?.role === "ADMIN" ||
    user?.role === "SUPER_ADMIN";

  const [figmaUrl, setFigmaUrl] = useState("");
  const [title, setTitle] = useState("");
  // Buyers always default to "personal", Sellers can pick "personal" or "sell"
  const [purpose, setPurpose] = useState("personal");
  const [price, setPrice] = useState("49.00");
  const [originalPrice, setOriginalPrice] = useState("89.00");
  const [framework, setFramework] = useState("HTML");
  const [category, setCategory] = useState("Technology");
  const [accessToken, setAccessToken] = useState("");
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [buyerClickAlert, setBuyerClickAlert] = useState(false);

  // Validation state
  const [isValidating, setIsValidating] = useState(false);
  const [validationData, setValidationData] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  // Importing state
  const [isImporting, setIsImporting] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [importLogs, setImportLogs] = useState([]);
  const [importSuccessResult, setImportSuccessResult] = useState(null);

  // Reset states whenever modal is opened
  useEffect(() => {
    if (isOpen) {
      setImportSuccessResult(null);
      setIsImporting(false);
      setErrorMsg("");
    }
  }, [isOpen]);

  const IMPORT_STEPS = [
    "Analyzing Figma Document AST & Layout Modes...",
    "Extracting Color Palette & Typography Tokens...",
    "Synthesizing Multi-Page Blueprint (Home, About, Services, Pricing, Contact)...",
    "Compiling Clean Production Assets & High-Res Snapshot...",
    "Mounting into Live Visual Studio Editor...",
  ];

  // Auto-validate Figma URL with debounce
  useEffect(() => {
    if (!figmaUrl.trim()) {
      setValidationData(null);
      setErrorMsg("");
      return;
    }

    if (!figmaUrl.includes("figma.com")) {
      setErrorMsg("URL must be from figma.com (e.g. https://www.figma.com/file/...)");
      setValidationData(null);
      return;
    }

    const timer = setTimeout(async () => {
      setIsValidating(true);
      setErrorMsg("");
      try {
        const res = await api.post("/figma/validate-url", { figma_url: figmaUrl });
        if (res.valid) {
          setValidationData(res);
          if (!title && res.title_slug) {
            setTitle(res.title_slug);
          }
        } else {
          setErrorMsg(res.message || "Invalid Figma link.");
          setValidationData(null);
        }
      } catch (err) {
        setErrorMsg("Failed to validate Figma URL.");
        setValidationData(null);
      } finally {
        setIsValidating(false);
      }
    }, 600);

    return () => clearTimeout(timer);
  }, [figmaUrl]);

  const handleSelectPurpose = (chosenPurpose) => {
    if (chosenPurpose === "sell" && !isSeller) {
      setBuyerClickAlert(true);
      setTimeout(() => setBuyerClickAlert(false), 5000);
      return;
    }
    setPurpose(chosenPurpose);
    setBuyerClickAlert(false);
  };

  const handleStartImport = async () => {
    if (!figmaUrl.trim() || isImporting) return;

    setIsImporting(true);
    setErrorMsg("");
    setCurrentStepIndex(0);
    setImportLogs([]);

    // Step animation runner
    const stepInterval = setInterval(() => {
      setCurrentStepIndex((prev) => {
        if (prev < IMPORT_STEPS.length - 1) {
          const next = prev + 1;
          setImportLogs((logs) => [...logs, IMPORT_STEPS[next]]);
          return next;
        }
        return prev;
      });
    }, 1200);

    setImportLogs([IMPORT_STEPS[0]]);

    try {
      const finalPurpose = isSeller ? purpose : "personal";
      const payload = {
        figma_url: figmaUrl.trim(),
        framework: framework,
        title: title.trim() || validationData?.title_slug || "Modern Flagship Studio",
        category: category,
        access_token: accessToken.trim() || null,
        purpose: finalPurpose,
        price: finalPurpose === "sell" ? parseFloat(price) || 49.0 : 0.0,
        original_price: finalPurpose === "sell" ? parseFloat(originalPrice) || 89.0 : 0.0,
      };

      const result = await api.post("/figma/import", payload);

      clearInterval(stepInterval);
      setCurrentStepIndex(IMPORT_STEPS.length - 1);
      setIsImporting(false);
      setImportSuccessResult(result);
    } catch (err) {
      clearInterval(stepInterval);
      setIsImporting(false);
      setErrorMsg(err.message || "Import failed. Please verify your link or connection.");
    }
  };

  if (!isOpen) return null;

  return (
    <div className="figma-modal-overlay" onClick={onClose}>
      <div className="figma-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="figma-modal-header">
          <div className="figma-header-left">
            <div className="figma-header-icon">
              <Sparkles size={22} />
            </div>
            <div>
              <div className="figma-header-title-row">
                <h3 className="figma-header-title">Import from Figma</h3>
                <span className="figma-badge-pill">AI Synthesizer</span>
              </div>
              <p className="figma-header-desc">
                Paste any Figma file link to synthesize a production, multi-page website
              </p>
            </div>
          </div>
          {!isImporting && (
            <button
              type="button"
              onClick={onClose}
              className="figma-close-btn"
              title="Close modal"
            >
              <X size={18} />
            </button>
          )}
        </div>

        {/* Modal Body */}
        {isImporting ? (
          /* Active Processing State */
          <div className="figma-importing-view">
            <div className="figma-spinner-ring">
              <div className="figma-spin-circle" />
              <div className="figma-spin-icon">
                <Zap size={22} />
              </div>
            </div>

            <div>
              <h4 style={{ fontSize: "1.05rem", fontWeight: 800, color: "#0f172a", marginBottom: "0.25rem" }}>
                {IMPORT_STEPS[currentStepIndex]}
              </h4>
              <p style={{ fontSize: "0.82rem", color: "#64748b", margin: 0 }}>
                Synthesizing responsive code, design tokens & live preview...
              </p>
            </div>

            {/* Progress Bar */}
            <div className="figma-progress-track">
              <div
                className="figma-progress-bar"
                style={{
                  width: `${((currentStepIndex + 1) / IMPORT_STEPS.length) * 100}%`,
                }}
              />
            </div>

            {/* Step Checkpoints */}
            <div className="figma-steps-container">
              {IMPORT_STEPS.map((step, idx) => {
                const isPast = idx < currentStepIndex;
                const isCurrent = idx === currentStepIndex;
                return (
                  <div
                    key={step}
                    className={`figma-step-row ${
                      isPast ? "figma-step-past" : isCurrent ? "figma-step-active" : "figma-step-future"
                    }`}
                  >
                    {isPast ? (
                      <CheckCircle2 size={16} style={{ color: "#059669", flexShrink: 0 }} />
                    ) : isCurrent ? (
                      <Loader2 size={16} className="animate-spin" style={{ color: "#4f46e5", flexShrink: 0 }} />
                    ) : (
                      <div
                        style={{
                          width: "14px",
                          height: "14px",
                          borderRadius: "50%",
                          border: "1.5px solid #cbd5e1",
                          flexShrink: 0,
                        }}
                      />
                    )}
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {step}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ) : importSuccessResult ? (
          /* Success Screen with Direct Live Deployment Option */
          <div className="figma-success-view">
            <div className="figma-success-icon-badge">
              <CheckCircle2 size={36} style={{ color: "#10b981" }} />
            </div>
            <h4 className="figma-success-title">Website Successfully Synthesized!</h4>
            <p className="figma-success-subtitle">
              Your Figma design <strong>{importSuccessResult.title}</strong> has been converted into a production 5-page responsive website package.
            </p>

            <div className="figma-success-features">
              <div className="figma-success-feature-chip">✓ Multi-page code bundle (Home, About, Services, Pricing, Contact)</div>
              <div className="figma-success-feature-chip">✓ Tailored design tokens, typography, and responsive layouts</div>
              <div className="figma-success-feature-chip">✓ Saved in your private Studio Projects (Never listed on Marketplace)</div>
            </div>

            <div className="figma-success-actions">
              <button
                type="button"
                onClick={() => {
                  onClose();
                  if (onDeploy) {
                    onDeploy({
                      id: importSuccessResult.template_id || importSuccessResult.id,
                      title: importSuccessResult.title,
                    });
                  } else {
                    navigate("/dashboard");
                  }
                }}
                className="figma-success-deploy-btn"
              >
                <Zap size={18} />
                <span>Deploy Live Website Now</span>
                <ArrowRight size={16} />
              </button>

              <button
                type="button"
                onClick={() => {
                  onClose();
                  const templateId = importSuccessResult.template_id || importSuccessResult.id;
                  navigate(`/preview?template=${templateId}&mode=live`);
                }}
                className="figma-success-studio-btn"
              >
                <Cpu size={16} />
                <span>Open in Visual Studio Editor</span>
              </button>
            </div>
          </div>
        ) : (
          /* Form Input State */
          <div className="figma-modal-body">
            {/* Purpose Selector: Live Site VS Marketplace (Seller Only) */}
            <div className="figma-purpose-section">
              <label className="figma-field-label">
                <span>Select Purpose & Destination</span>
                <span style={{ fontSize: "0.72rem", color: "#4f46e5", textTransform: "none", fontWeight: 600 }}>
                  {purpose === "personal" ? "✦ Saved in Studio Projects" : "✦ Listed on Marketplace"}
                </span>
              </label>

              <div className="figma-purpose-grid">
                {/* Option 1: Personal Live Website */}
                <div
                  className={`figma-purpose-card ${purpose === "personal" ? "selected" : ""}`}
                  onClick={() => handleSelectPurpose("personal")}
                >
                  <div className="figma-purpose-top">
                    <div className="figma-purpose-title">
                      <Globe size={16} style={{ color: "#0284c7" }} />
                      <span>Live Website</span>
                    </div>
                    <span className="figma-purpose-badge">Personal / Client</span>
                  </div>
                  <p className="figma-purpose-desc">
                    Deploy live to your custom domain or subdomain. Saved in your private Studio Projects.
                  </p>
                </div>

                {/* Option 2: Marketplace Template (Seller Only) */}
                <div
                  className={`figma-purpose-card ${purpose === "sell" ? "selected" : ""} ${
                    !isSeller ? "disabled" : ""
                  }`}
                  onClick={() => handleSelectPurpose("sell")}
                  title={
                    !isSeller
                      ? "Marketplace template listing is only available for Seller accounts"
                      : "Sell this template on the marketplace"
                  }
                >
                  <div className="figma-purpose-top">
                    <div className="figma-purpose-title">
                      <ShoppingCart size={16} style={{ color: isSeller ? "#7c3aed" : "#94a3b8" }} />
                      <span>Marketplace</span>
                    </div>
                    <span className="figma-purpose-badge">
                      {isSeller ? "Monetize & Sell" : "🔒 Seller Only"}
                    </span>
                  </div>
                  <p className="figma-purpose-desc">
                    {isSeller
                      ? "List on the public marketplace to sell to other creators and earn revenue."
                      : "Marketplace selling is reserved for Sellers. Buyers import to Live Website."}
                  </p>
                </div>
              </div>

              {/* Buyer explanation notice */}
              {!isSeller && (
                <div className="figma-role-notice buyer-hint">
                  <Info size={16} style={{ flexShrink: 0 }} />
                  <span>
                    You are logged in as a <strong>Buyer</strong>. Your Figma design will be synthesized directly into your private <strong>Studio Projects</strong> for your personal live website.
                  </span>
                </div>
              )}

              {/* Alert when buyer clicks on the disabled Marketplace card */}
              {buyerClickAlert && (
                <div className="figma-feedback-error animate-in fade-in duration-200">
                  <Lock size={15} style={{ flexShrink: 0 }} />
                  <span>
                    Selling on Marketplace is only allowed for <strong>Seller</strong> accounts. As a buyer, your project is ready for personal live deployment.
                  </span>
                </div>
              )}
            </div>

            {/* Conditional Pricing Row (Only when "Sell on Marketplace" is active for Sellers) */}
            {isSeller && purpose === "sell" && (
              <div
                className="figma-grid-2"
                style={{
                  background: "#f5f3ff",
                  padding: "0.85rem",
                  borderRadius: "0.85rem",
                  border: "1px solid #ddd6fe",
                }}
              >
                <div className="figma-field-group">
                  <label className="figma-field-label">
                    <span>Listing Price ($ USD)</span>
                    <span className="req">*</span>
                  </label>
                  <div className="figma-input-wrapper">
                    <input
                      type="number"
                      step="1"
                      min="0"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                      placeholder="49.00"
                      className="figma-input"
                    />
                  </div>
                </div>

                <div className="figma-field-group">
                  <label className="figma-field-label">
                    <span>Original Price (Display)</span>
                  </label>
                  <div className="figma-input-wrapper">
                    <input
                      type="number"
                      step="1"
                      min="0"
                      value={originalPrice}
                      onChange={(e) => setOriginalPrice(e.target.value)}
                      placeholder="89.00"
                      className="figma-input"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Figma URL Input */}
            <div className="figma-field-group">
              <label className="figma-field-label">
                <span>Figma File or Design Link</span>
                <span className="req">*</span>
              </label>
              <div className="figma-input-wrapper">
                <input
                  type="url"
                  value={figmaUrl}
                  onChange={(e) => setFigmaUrl(e.target.value)}
                  placeholder="https://www.figma.com/file/..."
                  className="figma-input font-mono"
                  autoFocus
                />
                <div className="figma-input-icon">
                  {isValidating && (
                    <Loader2 size={16} className="animate-spin" style={{ color: "#4f46e5" }} />
                  )}
                  {validationData?.valid && (
                    <CheckCircle2 size={16} style={{ color: "#059669" }} />
                  )}
                </div>
              </div>

              {/* Validation Feedback */}
              {validationData?.valid && (
                <div className="figma-feedback-success">
                  <span style={{ fontWeight: 600 }}>✓ Identified: {validationData.title_slug}</span>
                  <span style={{ fontFamily: "monospace", opacity: 0.85 }}>
                    Key: {validationData.file_key.slice(0, 8)}...
                  </span>
                </div>
              )}

              {errorMsg && (
                <div className="figma-feedback-error">
                  <AlertCircle size={15} style={{ flexShrink: 0 }} />
                  <span>{errorMsg}</span>
                </div>
              )}
            </div>

            {/* Template Title Override */}
            <div className="figma-field-group">
              <label className="figma-field-label">
                <span>Template Project Title</span>
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Apex SaaS Flagship, Aura Clinic, Luxe Atelier"
                className="figma-input"
              />
            </div>

            {/* Framework & Category */}
            <div className="figma-grid-2">
              <div className="figma-field-group">
                <label className="figma-field-label">
                  <span>Export Framework</span>
                </label>
                <select
                  value={framework}
                  onChange={(e) => setFramework(e.target.value)}
                  className="figma-select"
                >
                  <option value="HTML">HTML5 + Modern CSS</option>
                  <option value="React">React (Vite Components)</option>
                  <option value="Next.js">Next.js (App Router)</option>
                </select>
              </div>

              <div className="figma-field-group">
                <label className="figma-field-label">
                  <span>Category / Industry</span>
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="figma-select"
                >
                  <option value="Technology">Technology & SaaS</option>
                  <option value="E-Commerce">E-Commerce & Retail</option>
                  <option value="Agency">Agency & Portfolio</option>
                  <option value="Health">Health & Wellness</option>
                  <option value="Hospitality">Food & Hospitality</option>
                  <option value="Corporate">Corporate & Finance</option>
                </select>
              </div>
            </div>

            {/* Optional Personal Access Token */}
            <div>
              <button
                type="button"
                onClick={() => setShowTokenInput(!showTokenInput)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#4f46e5",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.35rem",
                  padding: 0,
                }}
              >
                <span>{showTokenInput ? "− Hide" : "+ Add"} Figma Personal Access Token</span>
                <span style={{ color: "#64748b", fontWeight: 400 }}>(Optional)</span>
              </button>

              {showTokenInput && (
                <div style={{ marginTop: "0.5rem" }} className="figma-field-group">
                  <input
                    type="password"
                    value={accessToken}
                    onChange={(e) => setAccessToken(e.target.value)}
                    placeholder="figd_..."
                    className="figma-input font-mono"
                  />
                  <p style={{ fontSize: "0.74rem", color: "#64748b", margin: "0.35rem 0 0 0", lineHeight: 1.4 }}>
                    <strong style={{ color: "#475569" }}>Pro Tip:</strong> Adding your Figma token (from Figma Profile &rarr; Settings &rarr; Security) enables 1:1 color space, typography, and headline extraction directly from your private frames. If omitted, smart AI heuristic synthesis is used.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Modal Footer Actions */}
        {!isImporting && !importSuccessResult && (
          <div className="figma-modal-footer">
            <div className="figma-footer-badge">
              <Layers size={15} style={{ color: "#4f46e5" }} />
              <span>Includes 5 pre-configured subpages</span>
            </div>

            <div className="figma-footer-actions">
              <button
                type="button"
                onClick={onClose}
                className="figma-btn-cancel"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleStartImport}
                disabled={!figmaUrl.trim()}
                className="figma-btn-submit"
              >
                <Sparkles size={15} />
                <span>
                  {isSeller && purpose === "sell"
                    ? "Publish to Marketplace"
                    : "Synthesize Live Website"}
                </span>
                <ArrowRight size={15} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
