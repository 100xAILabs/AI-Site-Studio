import { useState, useEffect } from "react";
import { Sparkles, ArrowLeft, ArrowRight, Loader2, CheckCircle2, Image as ImageIcon, Globe, Layers, FileText, LayoutGrid, Plus, Trash2, Info } from "lucide-react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import Navbar from "@/components/layout/Navbar";
import "./Page.css";

const GENERATION_STEPS = [
  { id: 1, label: "Analyzing prompt & architecture requirements...", duration: 2500 },
  { id: 2, label: "Crafting description & marketplace metadata...", duration: 3500 },
  { id: 3, label: "Designing developer brand logo...", duration: 2500 },
  { id: 4, label: "Generating high-fidelity page screenshots & code structure...", duration: 3500 },
  { id: 5, label: "Indexing in vector space...", duration: 2000 },
];

export default function GenerateTemplatePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const token = useAuthStore((s) => s.token);
  const [prompt, setPrompt] = useState(location.state?.prompt || "");
  const [framework, setFramework] = useState("html");
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [error, setError] = useState("");
  const [generatedTemplate, setGeneratedTemplate] = useState(null);

  // Advanced Prompt Analysis and Customization States
  const [step, setStep] = useState("prompt"); // "prompt" | "questions"
  const [modelTier, setModelTier] = useState("pro"); // "pro" (Gemini Pro / GPT-4o) | "flash" (Gemini Flash)
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [enhancedSpecs, setEnhancedSpecs] = useState(null);
  const [architectureType, setArchitectureType] = useState("multi_page"); // "single_page" | "multi_page"
  const [isMultipage, setIsMultipage] = useState(true);
  const [architectureReasoning, setArchitectureReasoning] = useState("");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [pages, setPages] = useState([]);
  const [multiPageCache, setMultiPageCache] = useState([]);
  const [newPageName, setNewPageName] = useState("");
  const [isPreparing, setIsPreparing] = useState(false);

  // Handle AI Prompt Enhancement
  const handleEnhancePrompt = async () => {
    if (!prompt.trim() || prompt.length < 5) {
      setError("Please write a short prompt description first (at least 5 characters).");
      return;
    }
    setError("");
    setIsEnhancing(true);
    try {
      const res = await api.post("/ai/enhance-prompt", { prompt }, token);
      if (res?.enhanced_prompt) {
        setPrompt(res.enhanced_prompt);
        setEnhancedSpecs(res);
      }
    } catch (err) {
      console.error(err);
      setError("Something error happens please try again later");
    } finally {
      setIsEnhancing(false);
    }
  };

  // Handle steps animation during generation
  useEffect(() => {
    if (!isGenerating || currentStep >= GENERATION_STEPS.length) return;

    const step = GENERATION_STEPS[currentStep];
    const timer = setTimeout(() => {
      setCompletedSteps((prev) => [...prev, step.id]);
      if (currentStep < GENERATION_STEPS.length - 1) {
        setCurrentStep((prev) => prev + 1);
      }
    }, step.duration);

    return () => clearTimeout(timer);
  }, [isGenerating, currentStep]);

  const handlePrepare = async (e) => {
    e.preventDefault();
    if (!prompt.trim() || prompt.length < 10) {
      setError("Please describe your template in at least 10 characters.");
      return;
    }

    setError("");
    setIsPreparing(true);

    try {
      const res = await api.post("/templates/generate/prepare", { prompt, model_tier: modelTier }, token);
      const arch = res.architecture_type || "multi_page";
      setArchitectureType(arch);
      setIsMultipage(res.is_multipage !== false);
      setArchitectureReasoning(res.architecture_reasoning || "");
      setQuestions(res.questions || []);

      // Initialize default answers with first options
      const defaultAnswers = {};
      res.questions?.forEach((q) => {
        if (q.options && q.options.length > 0) {
          defaultAnswers[q.id] = q.options[0];
        }
      });
      setAnswers(defaultAnswers);

      const fetchedPages = res.suggested_pages || [];
      setPages(fetchedPages);
      setMultiPageCache(fetchedPages);
      setStep("questions");
    } catch (err) {
      console.error(err);
      setError("Something error happens please try again later");
    } finally {
      setIsPreparing(false);
    }
  };

  const handleToggleArchitecture = (targetType) => {
    if (targetType === architectureType) return;
    setArchitectureType(targetType);

    if (targetType === "single_page") {
      setIsMultipage(false);
      if (pages.length > 1) {
        setMultiPageCache(pages);
      }
      setPages([
        {
          name: "Home Landing Page",
          filename: "index.html",
          content_summary: "Unified single-page layout featuring Hero header, Features grid, Showcase cards, Interactive tabs, Pricing tiers, and Contact section.",
          selected: true
        }
      ]);
    } else {
      setIsMultipage(true);
      if (multiPageCache.length > 1) {
        setPages(multiPageCache);
      } else {
        setPages([
          { name: "Home Page", filename: "index.html", content_summary: "Hero section, primary features grid, CTA banner, and multi-column footer.", selected: true },
          { name: "About Details", filename: "about.html", content_summary: "Company mission, vision, team profiles, and story timeline.", selected: true },
          { name: "Services", filename: "services.html", content_summary: "Service offerings, pricing cards, features list, and inquiry form.", selected: true },
          { name: "Contact Page", filename: "contact.html", content_summary: "Interactive contact form, location details, map placeholder, and FAQs.", selected: true }
        ]);
      }
    }
  };

  const handleAddCustomPage = (e) => {
    e.preventDefault();
    if (!newPageName.trim()) return;

    const name = newPageName.trim();
    const filename = `${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}.html`;

    const newPage = {
      name,
      filename,
      content_summary: `Custom ${name} page layout tailored to your specific business requirements.`,
      selected: true
    };

    setPages((prev) => [...prev, newPage]);
    if (architectureType === "multi_page") {
      setMultiPageCache((prev) => [...prev, newPage]);
    }
    setNewPageName("");
  };

  const handleRemovePage = (filename) => {
    if (filename === "index.html") return;
    setPages((prev) => prev.filter((p) => p.filename !== filename));
    setMultiPageCache((prev) => prev.filter((p) => p.filename !== filename));
  };

  const handleGenerate = async () => {
    setError("");
    setIsGenerating(true);
    setCurrentStep(0);
    setCompletedSteps([]);
    setGeneratedTemplate(null);

    const selectedPages = pages.filter((p) => p.selected !== false);

    try {
      const response = await api.post("/templates/generate", {
        prompt,
        framework,
        answers,
        pages: selectedPages,
        architecture_type: architectureType,
        is_multipage: isMultipage,
        model_tier: modelTier
      }, token);

      setGeneratedTemplate(response);
    } catch (err) {
      console.error(err);
      setError("Something error happens please try again later");
      setIsGenerating(false);
    }
  };

  // If backend returns template, wait until all steps are complete before showing success
  const isGenerationComplete = generatedTemplate && completedSteps.length === GENERATION_STEPS.length;

  return (
    <>
      <Navbar />
      <div className="generate-page">
        <div className="generate-container">

          {/* Header */}
          <div className="generate-header">
            <Link to="/marketplace" className="back-link">
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Marketplace</span>
            </Link>
            <h1 className="generate-title">
              <Sparkles className="title-icon text-primary animate-pulse" />
              <span>AI Template Generator</span>
            </h1>
            <p className="generate-subtitle">
              Describe your website template idea, and Gemini Pro will analyze your prompt, structure single or multi-page layouts, and generate a complete codebase.
            </p>
          </div>

          <div className="generate-card-wrapper">
            {error && (
              <div className="p-4 mb-6 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-center justify-between animate-fade-in shadow-lg shadow-rose-950/20">
                <span className="font-medium flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-rose-400 animate-ping" />
                  {error}
                </span>
                <button
                  type="button"
                  onClick={() => setError("")}
                  className="text-rose-400 hover:text-white text-xs underline ml-4 font-medium transition-colors"
                >
                  Dismiss
                </button>
              </div>
            )}

            {!isGenerating && !generatedTemplate && step === "prompt" && (
              /* Prompt Input Form */
              <form onSubmit={handlePrepare} className="prompt-form glass-panel animate-fade-in">
                
                {/* AI Model Tier Selector */}
                <div className="form-group mb-6">
                  <label className="prompt-label flex items-center justify-between">
                    <span>AI Model & Reasoning Tier</span>
                    <span className="text-xs text-emerald-400 font-normal">Powered by Gemini & OpenAI Flagship Models</span>
                  </label>
                  <div className="model-tier-grid grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
                    <button
                      type="button"
                      onClick={() => setModelTier("pro")}
                      className={`model-tier-card p-4 rounded-xl border transition-all text-left flex flex-col justify-between ${
                        modelTier === "pro"
                          ? "bg-slate-900/90 border-emerald-500/60 shadow-lg shadow-emerald-500/10 ring-1 ring-emerald-500/40"
                          : "bg-slate-900/40 border-white/10 hover:border-white/20"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-semibold text-white text-base flex items-center gap-2">
                          <Sparkles className="w-4 h-4 text-emerald-400" />
                          Gemini 2.5 Pro / GPT-4o
                        </span>
                        <span className="px-2 py-0.5 text-[10px] font-bold tracking-wide uppercase rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                          Recommended Flagship
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        Deep architectural reasoning, rich component hierarchy, multi-file code synthesis, and flawless styling.
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setModelTier("flash")}
                      className={`model-tier-card p-4 rounded-xl border transition-all text-left flex flex-col justify-between ${
                        modelTier === "flash"
                          ? "bg-slate-900/90 border-teal-500/60 shadow-lg shadow-teal-500/10 ring-1 ring-teal-500/40"
                          : "bg-slate-900/40 border-white/10 hover:border-white/20"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-semibold text-white text-base flex items-center gap-2">
                          <Globe className="w-4 h-4 text-teal-400" />
                          Gemini 3.1 Flash-Lite
                        </span>
                        <span className="px-2 py-0.5 text-[10px] font-bold tracking-wide uppercase rounded-full bg-teal-500/20 text-teal-300 border border-teal-500/30">
                          Ultra-Fast
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        Optimized for fast execution and lightweight structural template prototypes.
                      </p>
                    </button>
                  </div>
                </div>

                {/* Prompt Textarea */}
                <div className="form-group">
                  <div className="flex items-center justify-between mb-2">
                    <label htmlFor="prompt" className="prompt-label mb-0">
                      Describe your dream website template
                    </label>
                    <button
                      type="button"
                      onClick={handleEnhancePrompt}
                      disabled={isEnhancing || !prompt.trim()}
                      className="px-3 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
                      title="Refine simple prompt ideas into detailed architectural design specs with Gemini Pro"
                    >
                      {isEnhancing ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Enhancing Brief...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>Enhance Prompt with AI</span>
                        </>
                      )}
                    </button>
                  </div>

                  <textarea
                    id="prompt"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="e.g., 'A premium glassmorphic portfolio for a cyber-security engineer, featuring a dark neon-blue theme, terminal-style blog page, and a visual project grid...'"
                    className="prompt-textarea"
                    rows={5}
                  />
                  {error && <p className="error-text mt-2">{error}</p>}
                </div>

                {/* Enhanced Prompt Specs Pill Summary */}
                {enhancedSpecs && (
                  <div className="p-3 mb-6 bg-emerald-950/30 border border-emerald-500/30 rounded-xl text-xs text-slate-200">
                    <div className="flex items-center gap-2 mb-1 text-emerald-400 font-semibold">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>AI Design Brief Applied</span>
                    </div>
                    <p className="text-slate-300 mb-2">{enhancedSpecs.enhanced_prompt}</p>
                    <div className="flex flex-wrap gap-2 text-[11px]">
                      {enhancedSpecs.industry && (
                        <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-300 rounded-md border border-emerald-500/30">
                          Industry: {enhancedSpecs.industry}
                        </span>
                      )}
                      {enhancedSpecs.color_scheme && (
                        <span className="px-2 py-0.5 bg-teal-500/20 text-teal-300 rounded-md border border-teal-500/30">
                          Theme: {enhancedSpecs.color_scheme}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                <div className="form-group">
                  <label className="prompt-label">Code Framework</label>
                  <div className="framework-selector">
                    <div className="framework-card active cursor-default">
                      <Globe className="framework-icon" />
                      <div className="framework-text">
                        <h3>HTML5 & CSS</h3>
                        <p>Fully responsive, high-fidelity HTML5 website package</p>
                      </div>
                    </div>
                  </div>
                </div>

                <button type="submit" disabled={isPreparing} className="submit-btn group">
                  {isPreparing ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin mr-2" />
                      <span>Analyzing Prompt & Scope...</span>
                    </>
                  ) : (
                    <>
                      <span>Next: Analyze Prompt & Customize Architecture</span>
                      <ArrowRight className="submit-btn-icon group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </button>
              </form>
            )}

            {!isGenerating && !generatedTemplate && step === "questions" && (
              /* Custom Questions Form */
              <div className="prompt-form glass-panel animate-fade-in">
                
                {/* AI Prompt Analysis & Rationale Banner */}
                <div className="ai-analysis-banner">
                  <div className="ai-analysis-header">
                    <div className="ai-badge">
                      <Sparkles className="w-4 h-4 text-emerald-400" />
                      <span>AI Prompt Analysis</span>
                    </div>
                    <span className="arch-recommendation-tag">
                      Recommended: {architectureType === "single_page" ? "Single Page (SPA)" : "Multi-Page Site"}
                    </span>
                  </div>

                  {architectureReasoning && (
                    <p className="ai-reasoning-text">
                      <Info className="w-4 h-4 text-teal-400 shrink-0 inline-block mr-1.5 -mt-0.5" />
                      {architectureReasoning}
                    </p>
                  )}

                  {/* Architecture Mode Selector */}
                  <div className="arch-toggle-container">
                    <label className="arch-toggle-label">Select Page Architecture:</label>
                    <div className="arch-toggle-buttons">
                      <button
                        type="button"
                        onClick={() => handleToggleArchitecture("single_page")}
                        className={`arch-toggle-btn ${architectureType === "single_page" ? "active" : ""}`}
                      >
                        <FileText className="w-4 h-4 mr-1.5" />
                        <span>Single Page</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleToggleArchitecture("multi_page")}
                        className={`arch-toggle-btn ${architectureType === "multi_page" ? "active" : ""}`}
                      >
                        <Layers className="w-4 h-4 mr-1.5" />
                        <span>Multi-Page ({pages.length > 1 ? pages.length : multiPageCache.length} Pages)</span>
                      </button>
                    </div>
                  </div>
                </div>

                {error && <p className="error-text mb-4">{error}</p>}

                {/* Questions */}
                {questions.length > 0 && (
                  <div className="questions-container mt-6">
                    <h3 className="section-subtitle">Styling & Design Preferences</h3>
                    {questions.map((q) => (
                      <div key={q.id} className="question-group">
                        <label className="prompt-label">{q.question}</label>
                        <div className="options-grid">
                          {q.options.map((opt) => (
                            <button
                              key={opt}
                              type="button"
                              onClick={() => setAnswers(prev => ({ ...prev, [q.id]: opt }))}
                              className={`option-button ${answers[q.id] === opt ? "active" : ""}`}
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Pages checklist & Content Summary */}
                <div className="form-group mb-6 mt-6">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="section-subtitle text-white font-semibold">Planned Page & Content Breakdown</h3>
                    <span className="text-xs text-slate-400">{pages.length} page(s) configured</span>
                  </div>

                  <div className="pages-list-container">
                    {pages.map((p, idx) => (
                      <div key={p.filename} className="page-item-card">
                        <div className="page-item-top">
                          <label className="page-item-label">
                            <input
                              type="checkbox"
                              checked={p.selected !== false}
                              disabled={p.filename === "index.html" || architectureType === "single_page"}
                              onChange={(e) => {
                                const updated = [...pages];
                                updated[idx] = { ...updated[idx], selected: e.target.checked };
                                setPages(updated);
                              }}
                              className="page-item-checkbox"
                            />
                            <span className="font-semibold text-white">{p.name}</span>
                          </label>

                          <div className="flex items-center space-x-2">
                            <span className="page-item-filename">{p.filename}</span>
                            {p.filename !== "index.html" && architectureType === "multi_page" && (
                              <button
                                type="button"
                                onClick={() => handleRemovePage(p.filename)}
                                className="remove-page-btn"
                                title="Remove Page"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </div>

                        {p.content_summary && (
                          <div className="page-summary-box">
                            <LayoutGrid className="w-3.5 h-3.5 text-teal-400 shrink-0 mt-0.5" />
                            <p className="text-xs text-slate-300">{p.content_summary}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Custom Page Adder for Multi-Page mode */}
                  {architectureType === "multi_page" && (
                    <div className="add-page-row mt-3">
                      <input
                        type="text"
                        value={newPageName}
                        onChange={(e) => setNewPageName(e.target.value)}
                        placeholder="Add another page (e.g. 'Pricing', 'Blog', 'Portfolio')..."
                        className="add-page-input"
                      />
                      <button
                        type="button"
                        onClick={handleAddCustomPage}
                        disabled={!newPageName.trim()}
                        className="add-page-btn"
                      >
                        <Plus className="w-4 h-4 mr-1" />
                        <span>Add Page</span>
                      </button>
                    </div>
                  )}
                </div>

                {/* Navigation Buttons */}
                <div className="flex space-x-3 mt-8">
                  <button
                    type="button"
                    onClick={() => setStep("prompt")}
                    className="flex-1 px-4 py-3 bg-slate-800 hover:bg-slate-750 border border-white/10 rounded-xl font-medium text-slate-300 transition-colors"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={handleGenerate}
                    className="flex-1 submit-btn group"
                  >
                    <span>Generate Template ({pages.filter(p => p.selected !== false).length} Pages)</span>
                    <Sparkles className="submit-btn-icon group-hover:rotate-12 transition-transform" />
                  </button>
                </div>
              </div>
            )}

            {isGenerating && !isGenerationComplete && (
              /* Progress Step Indicator */
              <div className="generation-loading-panel glass-panel">
                <div className="loading-title-row">
                  <Loader2 className="loading-spinner text-primary animate-spin" />
                  <h2>Generating Template</h2>
                </div>
                <p className="loading-desc">
                  Our advanced AI model is creating structure, mockups, and assets based on your prompt.
                </p>

                <div className="steps-list">
                  {GENERATION_STEPS.map((step, idx) => {
                    const isCompleted = completedSteps.includes(step.id);
                    const isActive = currentStep === idx;
                    return (
                      <div
                        key={step.id}
                        className={`step-item ${isCompleted ? "completed" : ""} ${isActive ? "active" : ""}`}
                      >
                        <div className="step-bullet">
                          {isCompleted ? (
                            <CheckCircle2 className="w-5 h-5 text-emerald-500 fill-emerald-500/10" />
                          ) : isActive ? (
                            <div className="pulse-bullet" />
                          ) : (
                            <div className="empty-bullet" />
                          )}
                        </div>
                        <span className="step-label">{step.label}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {isGenerationComplete && (
              /* Success template preview card */
              <div className="success-panel glass-panel">
                <div className="success-header">
                  <CheckCircle2 className="success-icon text-emerald-500 animate-bounce" />
                  <h2>Generation Successful!</h2>
                  <p>Your custom website template has been successfully generated and published to the marketplace.</p>
                </div>

                <div className="generated-preview-card">
                  <div className="card-media">
                    <img
                      src={generatedTemplate.thumbnail_url}
                      alt={generatedTemplate.title}
                      className="card-image"
                    />
                    <div className="card-badge">AI Generated</div>
                  </div>
                  <div className="card-info">
                    <div className="card-meta">
                      <span className="category-tag">{generatedTemplate.industry}</span>
                      <span className="price-tag">${generatedTemplate.price}</span>
                    </div>
                    <h3 className="card-title">{generatedTemplate.title}</h3>
                    <p className="card-desc">{generatedTemplate.short_description}</p>
                    <div className="card-tags">
                      {generatedTemplate.tags?.slice(0, 3).map((tag) => (
                        <span key={tag} className="meta-tag">#{tag}</span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="success-actions">
                  <button
                    onClick={() => {
                      setIsGenerating(false);
                      setGeneratedTemplate(null);
                      setPrompt("");
                    }}
                    className="secondary-action-btn"
                  >
                    Generate Another
                  </button>
                  <Link
                    to={`/marketplace/${generatedTemplate.slug}`}
                    className="primary-action-btn"
                  >
                    <span>View Template Details</span>
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  );
}
