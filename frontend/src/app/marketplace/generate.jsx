import { useState, useEffect } from "react";
import { Sparkles, ArrowLeft, ArrowRight, Loader2, CheckCircle2, Image as ImageIcon, Globe, Shield } from "lucide-react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import Navbar from "@/components/layout/Navbar";
import "./Page.css";

const GENERATION_STEPS = [
  { id: 1, label: "Parsing your vision...", duration: 2500 },
  { id: 2, label: "Crafting description & marketplace metadata...", duration: 3500 },
  { id: 3, label: "Designing developer brand logo...", duration: 2500 },
  { id: 4, label: "Generating high-fidelity page screenshots...", duration: 3500 },
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

  // Advanced Questioning and Page Customization States
  const [step, setStep] = useState("prompt"); // "prompt" | "questions"
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [pages, setPages] = useState([]);
  const [isPreparing, setIsPreparing] = useState(false);

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
      const res = await api.post("/templates/generate/prepare", { prompt }, token);
      setQuestions(res.questions || []);

      // Initialize default answers with first options
      const defaultAnswers = {};
      res.questions?.forEach((q) => {
        if (q.options && q.options.length > 0) {
          defaultAnswers[q.id] = q.options[0];
        }
      });
      setAnswers(defaultAnswers);
      setPages(res.suggested_pages || []);
      setStep("questions");
    } catch (err) {
      console.error(err);
      setError(err?.message || "Failed to analyze template prompt. Please try again.");
    } finally {
      setIsPreparing(false);
    }
  };

  const handleGenerate = async () => {
    setError("");
    setIsGenerating(true);
    setCurrentStep(0);
    setCompletedSteps([]);
    setGeneratedTemplate(null);

    const selectedPages = pages.filter((p) => p.selected !== false);

    try {
      // Initiate backend generation with answers and explicit page structures
      const response = await api.post("/templates/generate", {
        prompt,
        framework,
        answers,
        pages: selectedPages
      }, token);

      setGeneratedTemplate(response);
    } catch (err) {
      console.error(err);
      setError(err?.message || "An error occurred during template generation. Please try again.");
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
              Describe your website template idea, and Gemini will generate a high-fidelity marketplace listing, brand logo, and matching interior screenshots.
            </p>
          </div>

          <div className="generate-card-wrapper">
            {!isGenerating && !generatedTemplate && step === "prompt" && (
              /* Prompt Input Form */
              <form onSubmit={handlePrepare} className="prompt-form glass-panel animate-fade-in">
                <div className="form-group">
                  <label htmlFor="prompt" className="prompt-label">
                    Describe your dream website template
                  </label>
                  <textarea
                    id="prompt"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="e.g., 'A premium glassmorphic portfolio for a cyber-security engineer, featuring a dark neon-blue theme, terminal-style terminal blog page, and a visual project grid...'"
                    className="prompt-textarea"
                    rows={5}
                  />
                  {error && <p className="error-text">{error}</p>}
                </div>

                <div className="form-group">
                  <label className="prompt-label">Code Framework</label>
                  <div className="framework-selector">
                    <div className="framework-card active cursor-default">
                      <Globe className="framework-icon" />
                      <div className="framework-text">
                        <h3>HTML5 & CSS</h3>
                        <p>Single-file responsive high-fidelity SPA page</p>
                      </div>
                    </div>
                  </div>
                </div>

                <button type="submit" disabled={isPreparing} className="submit-btn group">
                  {isPreparing ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin mr-2" />
                      <span>Analyzing Prompt...</span>
                    </>
                  ) : (
                    <>
                      <span>Next: Customize Layout & Style</span>
                      <ArrowRight className="submit-btn-icon group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </button>
              </form>
            )}

            {!isGenerating && !generatedTemplate && step === "questions" && (
              /* Custom Questions Form */
              <div className="prompt-form glass-panel animate-fade-in">
                <h2 className="text-xl font-bold text-white mb-1">Customize Your Template</h2>
                <p className="text-sm text-slate-400 mb-6">
                  Fine-tune the style preferences and select exactly which pages should be included in your multi-page template code.
                </p>

                {error && <p className="error-text mb-4">{error}</p>}

                {/* Questions */}
                <div className="questions-container">
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

                {/* Pages checklist */}
                <div className="form-group mb-6">
                  <label className="prompt-label">Select Pages to Generate</label>
                  <div className="pages-list-container">
                    {pages.map((p, idx) => (
                      <div key={p.filename} className="page-item-row">
                        <label className="page-item-label">
                          <input
                            type="checkbox"
                            checked={p.selected !== false}
                            disabled={p.filename === "index.html"}
                            onChange={(e) => {
                              const updated = [...pages];
                              updated[idx] = { ...updated[idx], selected: e.target.checked };
                              setPages(updated);
                            }}
                            className="page-item-checkbox"
                          />
                          <span>{p.name}</span>
                        </label>
                        <span className="page-item-filename">{p.filename}</span>
                      </div>
                    ))}
                  </div>
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
                    <span>Generate Template</span>
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
