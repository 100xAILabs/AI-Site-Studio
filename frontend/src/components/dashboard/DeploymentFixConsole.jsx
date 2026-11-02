"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  Folder,
  FileCode,
  FileText,
  Save,
  Sparkles,
  ExternalLink,
  X,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Terminal,
  Code,
  Check,
  Columns,
  Eye,
  Monitor,
  Tablet,
  Smartphone,
  RotateCcw,
  Edit3,
  Bot,
  Type,
  Send,
  Wand2,
} from "lucide-react";
import { api } from "../../lib/api";
import "./DeploymentFixConsole.css";

const AI_MODEL_OPTIONS = [
  { id: "gemini-1.5-flash", name: "⚡ Google Gemini 1.5 Flash", desc: "Ultra-fast, high-precision copywriting (Recommended)" },
  { id: "gemini-1.5-pro", name: "🧠 Google Gemini 1.5 Pro", desc: "Deep reasoning, complex page restructure & rich copy" },
  { id: "gpt-4o", name: "✨ OpenAI GPT-4o", desc: "Creative marketing and persuasive conversion copy" },
  { id: "ollama", name: "💻 Local Ollama / CUDA AI", desc: "Private local GPU model execution" },
];

const QUICK_AI_PROMPTS = [
  { label: "✨ Rewrite Hero Copy", prompt: "Rewrite the hero section headline and subheadline to be punchy, high-converting, and modern." },
  { label: "🏨 Luxury Tone Upgrade", prompt: "Elevate all copywriting across this page to sound like a 5-star ultra-luxury boutique hospitality destination." },
  { label: "📞 Update Contact Details", prompt: "Update phone number to +1 (800) 555-0199 and email to concierge@residency.com across all headers and footers." },
  { label: "🎨 Modern Color Polish", prompt: "Refine CSS styling with smooth transitions, modern card shadows, and improved typography contrast." },
  { label: "🌐 Translate to Spanish", prompt: "Translate all user-facing headings, descriptions, and button labels on this page to fluent Spanish." },
];

export default function DeploymentFixConsole({
  isOpen,
  onClose,
  deployment,
  incident,
  authToken,
  onUpdateSuccess,
}) {
  const [fileList, setFileList] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [selectedFilePath, setSelectedFilePath] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [loadingContent, setLoadingContent] = useState(false);
  const [savingFile, setSavingFile] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Editor Sub-Tab: 'copy' (Visual Copy Edit) | 'ai' (AI Prompt with Model) | 'code' (Raw Code)
  const [editorSubTab, setEditorSubTab] = useState("copy");

  // View Mode: 'code' | 'split' | 'preview'
  const [viewMode, setViewMode] = useState("split");
  const [previewDevice, setPreviewDevice] = useState("desktop");
  const [iframeKey, setIframeKey] = useState(1);

  // AI Prompt & Model State
  const [selectedModel, setSelectedModel] = useState("gemini-1.5-flash");
  const [aiPromptInput, setAiPromptInput] = useState("");
  const [isAiGenerating, setIsAiGenerating] = useState(false);

  // Visual Copy Form State
  const [visualCopy, setVisualCopy] = useState({
    pageTitle: "",
    h1: "",
    h2: "",
    heroParagraph: "",
    buttonText: "",
    phone: "",
    email: "",
  });

  // Full Release Redeployment State
  const [isRedeploying, setIsRedeploying] = useState(false);

  // AI Site Doctor State
  const [isAiFixing, setIsAiFixing] = useState(false);
  const [aiReport, setAiReport] = useState(null);

  // Bottom Terminal
  const [terminalLogs, setTerminalLogs] = useState([]);
  const [isTerminalOpen, setIsTerminalOpen] = useState(true);

  const editorRef = useRef(null);

  const siteId = deployment?.site_id || `SITE-${deployment?.id?.slice(0, 6)?.toUpperCase()}`;
  const baseLiveUrl = deployment?.live_url || `http://localhost:8000/sites/${siteId}/`;

  // Compute live URL for the currently active HTML page
  const activePageUrl = useMemo(() => {
    if (!baseLiveUrl) return "";
    const cleanBase = baseLiveUrl.endsWith("/") ? baseLiveUrl : `${baseLiveUrl}/`;
    if (selectedFilePath && selectedFilePath.endsWith(".html")) {
      return `${cleanBase}${selectedFilePath}`;
    }
    return cleanBase;
  }, [baseLiveUrl, selectedFilePath]);

  // Extract visual copy fields from HTML content whenever file content changes
  useEffect(() => {
    if (!fileContent || !selectedFilePath.endsWith(".html")) return;

    try {
      const titleMatch = fileContent.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
      const h1Match = fileContent.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
      const h2Match = fileContent.match(/<h2[^>]*>([\s\S]*?)<\/h2>/i);
      const pMatch = fileContent.match(/<p[^>]*>([\s\S]*?)<\/p>/i);
      const btnMatch = fileContent.match(/<(?:button|a)[^>]*class="[^"]*(?:btn|cta)[^"]*"[^>]*>([\s\S]*?)<\/(?:button|a)>/i);
      const phoneMatch = fileContent.match(/(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/);
      const emailMatch = fileContent.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);

      const stripTags = (s) => (s ? s.replace(/<[^>]*>/g, "").trim() : "");

      setVisualCopy({
        pageTitle: stripTags(titleMatch ? titleMatch[1] : ""),
        h1: stripTags(h1Match ? h1Match[1] : ""),
        h2: stripTags(h2Match ? h2Match[1] : ""),
        heroParagraph: stripTags(pMatch ? pMatch[1] : ""),
        buttonText: stripTags(btnMatch ? btnMatch[1] : ""),
        phone: phoneMatch ? phoneMatch[0] : "",
        email: emailMatch ? emailMatch[0] : "",
      });
    } catch {
      // fallback
    }
  }, [fileContent, selectedFilePath]);

  // 1. Fetch file list when opened
  useEffect(() => {
    if (!isOpen || !deployment?.id) return;

    let mounted = true;
    const fetchFiles = async () => {
      setLoadingFiles(true);
      try {
        const res = await api.get(`/deployments/${deployment.id}/files`, authToken ?? undefined);
        if (mounted) {
          const files = res.files || [];
          setFileList(files);
          const defaultFile = files.find((f) => f.path === "index.html") || files[0];
          if (defaultFile) {
            setSelectedFilePath(defaultFile.path);
          }
          setTerminalLogs((prev) => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] Connected to deployment ${siteId}. Loaded ${files.length} source files.`,
          ]);
        }
      } catch (err) {
        if (mounted) {
          setTerminalLogs((prev) => [
            ...prev,
            `[${new Date().toLocaleTimeString()}] ❌ Failed to list files: ${err.message}`,
          ]);
        }
      } finally {
        if (mounted) setLoadingFiles(false);
      }
    };

    fetchFiles();
    return () => {
      mounted = false;
    };
  }, [isOpen, deployment?.id, siteId, authToken]);

  // 2. Load selected file content
  useEffect(() => {
    if (!selectedFilePath || !deployment?.id) return;

    let mounted = true;
    const loadContent = async () => {
      setLoadingContent(true);
      try {
        const res = await api.get(
          `/deployments/${deployment.id}/file-content?path=${encodeURIComponent(selectedFilePath)}`,
          authToken ?? undefined
        );
        if (mounted) {
          setFileContent(res.content);
          setOriginalContent(res.content);
          setSaveSuccess(false);
        }
      } catch (err) {
        if (mounted) {
          setFileContent(`/* Error reading ${selectedFilePath}: ${err.message} */`);
        }
      } finally {
        if (mounted) setLoadingContent(false);
      }
    };

    loadContent();
    return () => {
      mounted = false;
    };
  }, [selectedFilePath, deployment?.id, authToken]);

  // Handle Tab key in code editor
  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      handleSaveFile();
      return;
    }

    if (e.key === "Tab") {
      e.preventDefault();
      const textarea = e.target;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const val = textarea.value;

      textarea.value = val.substring(0, start) + "  " + val.substring(end);
      textarea.selectionStart = textarea.selectionEnd = start + 2;
      setFileContent(textarea.value);
    }
  };

  // 3. Save File & Hot-Redeploy
  const handleSaveFile = async (explicitContent = null) => {
    if (!selectedFilePath || !deployment?.id) return;

    const contentToSave = explicitContent !== null ? explicitContent : fileContent;
    setSavingFile(true);
    setSaveSuccess(false);
    try {
      const payload = {
        path: selectedFilePath,
        content: contentToSave,
        incident_id: incident?.id || undefined,
      };

      const res = await api.put(
        `/deployments/${deployment.id}/files`,
        payload,
        authToken ?? undefined
      );

      setFileContent(contentToSave);
      setOriginalContent(contentToSave);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);

      // Instantly refresh live preview iframe
      setIframeKey((prev) => prev + 1);

      setTerminalLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ✓ Saved & hot-reloaded ${selectedFilePath}. Live preview updated.`,
      ]);

      if (onUpdateSuccess) onUpdateSuccess();
    } catch (err) {
      alert("Failed to save file: " + err.message);
      setTerminalLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ❌ Save error: ${err.message}`,
      ]);
    } finally {
      setSavingFile(false);
    }
  };

  // 4. Apply Visual Copy to HTML (Eliminates raw copy-paste!)
  const handleApplyVisualCopy = () => {
    if (!fileContent || !selectedFilePath.endsWith(".html")) return;

    let updated = fileContent;

    if (visualCopy.pageTitle) {
      updated = updated.replace(/<title[^>]*>[\s\S]*?<\/title>/i, `<title>${visualCopy.pageTitle}</title>`);
    }
    if (visualCopy.h1) {
      updated = updated.replace(/(<h1[^>]*>)([\s\S]*?)(<\/h1>)/i, `$1${visualCopy.h1}$3`);
    }
    if (visualCopy.h2) {
      updated = updated.replace(/(<h2[^>]*>)([\s\S]*?)(<\/h2>)/i, `$1${visualCopy.h2}$3`);
    }
    if (visualCopy.heroParagraph) {
      updated = updated.replace(/(<p[^>]*>)([\s\S]*?)(<\/p>)/i, `$1${visualCopy.heroParagraph}$3`);
    }
    if (visualCopy.buttonText) {
      updated = updated.replace(/(<(?:button|a)[^>]*class="[^"]*(?:btn|cta)[^"]*"[^>]*>)([\s\S]*?)(<\/(?:button|a)>)/i, `$1${visualCopy.buttonText}$3`);
    }

    setFileContent(updated);
    handleSaveFile(updated);
  };

  // 5. Run AI Edit with Chosen AI Model
  const handleRunAiEdit = async (customPrompt = "") => {
    const promptToRun = customPrompt || aiPromptInput;
    if (!promptToRun.trim() || !deployment?.id) return;

    setIsAiGenerating(true);
    setTerminalLogs((prev) => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] 🤖 Calling ${selectedModel.toUpperCase()} AI model with instruction: "${promptToRun}"...`,
    ]);

    try {
      const payload = {
        prompt: promptToRun,
        model: selectedModel,
        file_path: selectedFilePath || undefined,
      };

      const res = await api.post(
        `/deployments/${deployment.id}/ai-edit`,
        payload,
        authToken ?? undefined
      );

      setTerminalLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ✓ AI Model (${res.model || selectedModel}) applied changes: ${res.summary || "Website code updated."}`,
        `[${new Date().toLocaleTimeString()}] ✓ Updated files: ${(res.patched_files || [selectedFilePath]).join(", ")}`,
      ]);

      // Reload current file content
      if (selectedFilePath) {
        const fileRes = await api.get(
          `/deployments/${deployment.id}/file-content?path=${encodeURIComponent(selectedFilePath)}`,
          authToken ?? undefined
        );
        setFileContent(fileRes.content);
        setOriginalContent(fileRes.content);
      }

      setIframeKey((prev) => prev + 1);
      setAiPromptInput("");
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);

      if (onUpdateSuccess) onUpdateSuccess();
    } catch (err) {
      alert("AI Edit error: " + err.message);
      setTerminalLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ❌ AI Edit error: ${err.message}`,
      ]);
    } finally {
      setIsAiGenerating(false);
    }
  };

  // 6. Trigger Release Snapshot Redeploy
  const handleRedeployRelease = async () => {
    if (!deployment?.id) return;
    if (!confirm(`Redeploy release snapshot for "${deployment.project_name}"? This increments the version and executes the deployment verification pipeline.`)) {
      return;
    }

    setIsRedeploying(true);
    try {
      setTerminalLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] 🚀 Initiating zero-downtime release pipeline...`,
      ]);
      const res = await api.post(`/deployments/${deployment.id}/redeploy`, {}, authToken ?? undefined);
      setTerminalLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ✓ Release redeployment queued. Version: ${res.current_version || "New Release"}.`,
      ]);
      setIframeKey((prev) => prev + 1);
      if (onUpdateSuccess) onUpdateSuccess();
    } catch (err) {
      alert("Redeploy error: " + err.message);
      setTerminalLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ❌ Redeployment error: ${err.message}`,
      ]);
    } finally {
      setIsRedeploying(false);
    }
  };

  // 7. Trigger Autonomous AI Site Doctor
  const handleAiAutoFix = async () => {
    if (!deployment?.id) return;

    setIsAiFixing(true);
    setAiReport(null);
    setTerminalLogs((prev) => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] ⚡ Dispatched Autonomous AI Site Doctor. Scanning code repository...`,
    ]);

    try {
      const payload = {
        incident_id: incident?.id || undefined,
        issue_description: incident?.description || "Manual AI Auto-Fix requested from Code Fix Studio.",
        error_logs: incident?.error_logs || undefined,
        issue_type: incident?.issue_type || "broken_website",
      };

      const res = await api.post(
        `/admin/deployments/${deployment.id}/auto-fix`,
        payload,
        authToken ?? undefined
      );

      setAiReport(res);
      setTerminalLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ✓ AI Doctor completed diagnosis: ${res.diagnosis || "Patches applied"}`,
        `[${new Date().toLocaleTimeString()}] ✓ Patched files: ${(res.patched_files || []).join(", ") || "index.html"}`,
      ]);

      setIframeKey((prev) => prev + 1);

      if (res.patched_files && res.patched_files.includes(selectedFilePath)) {
        const fileRes = await api.get(
          `/deployments/${deployment.id}/file-content?path=${encodeURIComponent(selectedFilePath)}`,
          authToken ?? undefined
        );
        setFileContent(fileRes.content);
        setOriginalContent(fileRes.content);
      }

      if (onUpdateSuccess) onUpdateSuccess();
    } catch (err) {
      alert("AI Auto-Fix failed: " + err.message);
      setTerminalLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ❌ AI Auto-Fix error: ${err.message}`,
      ]);
    } finally {
      setIsAiFixing(false);
    }
  };

  if (!isOpen || !deployment) return null;

  const isDirty = fileContent !== originalContent;
  const lineCount = fileContent.split("\n").length;
  const isHtmlFile = selectedFilePath.endsWith(".html");

  return (
    <div className="dfc-overlay" onClick={onClose}>
      <div className="dfc-container" onClick={(e) => e.stopPropagation()}>
        {/* Top Header Bar */}
        <div className="dfc-header">
          <div className="dfc-header-left">
            <div className="dfc-icon-badge">
              <Code className="w-5 h-5 text-indigo-500" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="dfc-title">{deployment.project_name}</h3>
                <span className="dfc-site-pill">{siteId}</span>
                <span className="dfc-version-pill">{deployment.current_version || "v1.0"}</span>
                {isDirty && <span className="dfc-dirty-pill">● Unsaved Edits</span>}
              </div>
              <p className="dfc-sub">
                Live Deployment Editor &amp; Zero-Downtime Redeploy Studio
              </p>
            </div>
          </div>

          {/* Center Mode Switcher */}
          <div className="dfc-view-switch">
            <button
              type="button"
              className={`dfc-view-pill ${viewMode === "code" ? "active" : ""}`}
              onClick={() => setViewMode("code")}
              title="Full Code View"
            >
              <Code className="w-3.5 h-3.5" />
              <span>Code</span>
            </button>
            <button
              type="button"
              className={`dfc-view-pill ${viewMode === "split" ? "active" : ""}`}
              onClick={() => setViewMode("split")}
              title="Side-by-side Code & Live Canvas"
            >
              <Columns className="w-3.5 h-3.5" />
              <span>Split View</span>
            </button>
            <button
              type="button"
              className={`dfc-view-pill ${viewMode === "preview" ? "active" : ""}`}
              onClick={() => setViewMode("preview")}
              title="Full Live Site Canvas"
            >
              <Eye className="w-3.5 h-3.5" />
              <span>Live Preview</span>
            </button>
          </div>

          <div className="dfc-header-actions">
            <a
              href={activePageUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="dfc-btn-secondary"
              title="Open deployed website in new tab"
            >
              <ExternalLink className="w-4 h-4" />
              <span className="hidden sm:inline">Visit Live</span>
            </a>

            <button
              type="button"
              onClick={handleAiAutoFix}
              disabled={isAiFixing}
              className="dfc-btn-ai"
              title="Run Autonomous AI Site Doctor to diagnose and patch code"
            >
              {isAiFixing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>Healing...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-amber-300" />
                  <span>AI Doctor</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => handleSaveFile()}
              disabled={savingFile || !isDirty}
              className={`dfc-btn-save ${saveSuccess ? "success" : ""}`}
              title="Save file changes and hot-reload live site (Ctrl+S)"
            >
              {savingFile ? (
                <Loader2 className="w-4 h-4 animate-spin text-white" />
              ) : saveSuccess ? (
                <Check className="w-4 h-4 text-white" />
              ) : (
                <Save className="w-4 h-4 text-white" />
              )}
              <span>{saveSuccess ? "Saved & Live!" : "Save & Hot-Reload"}</span>
            </button>

            <button
              type="button"
              onClick={handleRedeployRelease}
              disabled={isRedeploying}
              className="dfc-btn-redeploy"
              title="Trigger a full release build and bump version snapshot"
            >
              {isRedeploying ? (
                <Loader2 className="w-4 h-4 animate-spin text-white" />
              ) : (
                <RefreshCw className="w-4 h-4 text-white" />
              )}
              <span className="hidden md:inline">Redeploy</span>
            </button>

            <button type="button" onClick={onClose} className="dfc-close-btn" aria-label="Close">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* AI Diagnosis Alert Banner (if auto-fixed) */}
        {aiReport && (
          <div className="dfc-ai-banner">
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
              <div>
                <div className="font-bold text-sm text-foreground">
                  AI Site Doctor Patched {aiReport.patched_files?.length || 1} File(s)
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  <strong>Diagnosis:</strong> {aiReport.diagnosis}
                </div>
                {aiReport.patch_summary && (
                  <div className="text-xs text-indigo-600 dark:text-indigo-400 font-semibold mt-1">
                    ✓ {aiReport.patch_summary}
                  </div>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setAiReport(null)}
              className="text-xs text-muted-foreground hover:text-foreground cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Studio Workspace Layout */}
        <div className="dfc-workspace">
          {/* Left File Tree Sidebar */}
          {viewMode !== "preview" && (
            <div className="dfc-sidebar">
              <div className="dfc-sidebar-header">
                <Folder className="w-4 h-4 text-primary" />
                <span>Website Files</span>
                <span className="dfc-file-count">{fileList.length}</span>
              </div>

              {loadingFiles ? (
                <div className="p-4 text-center text-xs text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin mx-auto mb-1 text-primary" />
                  Loading file tree...
                </div>
              ) : fileList.length === 0 ? (
                <div className="p-4 text-center text-xs text-muted-foreground">
                  No files detected in deployment folder.
                </div>
              ) : (
                <div className="dfc-file-tree">
                  {fileList.map((file) => {
                    const isSelected = selectedFilePath === file.path;
                    const isHtml = file.ext === ".html";
                    const isJs = file.ext === ".js" || file.ext === ".jsx";
                    const isCss = file.ext === ".css";

                    return (
                      <button
                        key={file.path}
                        type="button"
                        onClick={() => setSelectedFilePath(file.path)}
                        className={`dfc-file-item ${isSelected ? "selected" : ""}`}
                      >
                        {isHtml ? (
                          <FileCode className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                        ) : isJs ? (
                          <FileCode className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                        ) : isCss ? (
                          <FileText className="w-3.5 h-3.5 text-sky-500 shrink-0" />
                        ) : (
                          <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        )}
                        <span className="dfc-file-name truncate" title={file.path}>
                          {file.path}
                        </span>
                        <span className="dfc-file-size">
                          {Math.round(file.size / 1024) || 1} KB
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Center Editor Area */}
          {viewMode !== "preview" && (
            <div className={`dfc-editor-pane ${viewMode === "split" ? "split" : "full"}`}>
              {/* Editor Sub-Tab Switcher: Visual Copy Edit vs AI Edit with Model vs Raw Code */}
              <div className="dfc-editor-subtabs">
                <button
                  type="button"
                  onClick={() => setEditorSubTab("copy")}
                  className={`dfc-subtab-btn ${editorSubTab === "copy" ? "active" : ""}`}
                  title="Visual Copy Editor — Edit text & headlines directly without code copy-pasting"
                >
                  <Type className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Visual Copy Edit</span>
                </button>

                <button
                  type="button"
                  onClick={() => setEditorSubTab("ai")}
                  className={`dfc-subtab-btn ${editorSubTab === "ai" ? "active" : ""}`}
                  title="AI Prompt Assistant — Choose model & write instructions"
                >
                  <Wand2 className="w-3.5 h-3.5 text-indigo-500" />
                  <span>AI Model Edit</span>
                </button>

                <button
                  type="button"
                  onClick={() => setEditorSubTab("code")}
                  className={`dfc-subtab-btn ${editorSubTab === "code" ? "active" : ""}`}
                  title="Raw Code Editor — Full HTML/CSS/JS source access"
                >
                  <Code className="w-3.5 h-3.5 text-amber-500" />
                  <span>Code Editor</span>
                </button>
              </div>

              {/* Breadcrumb Strip */}
              <div className="dfc-editor-strip">
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="text-muted-foreground">{siteId}</span>
                  <span className="text-muted-foreground">/</span>
                  <span className="text-foreground font-bold">{selectedFilePath || "No file selected"}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground font-mono">
                  <span>{lineCount} lines</span>
                  <span>UTF-8</span>
                  {isDirty ? (
                    <button
                      type="button"
                      onClick={() => setFileContent(originalContent)}
                      className="text-amber-500 hover:underline cursor-pointer"
                    >
                      Revert
                    </button>
                  ) : (
                    <span className="text-emerald-500 font-semibold">● Clean</span>
                  )}
                </div>
              </div>

              {/* Loading State */}
              {loadingContent ? (
                <div className="dfc-editor-loading">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                  <span className="text-xs text-muted-foreground mt-2 font-mono">Opening {selectedFilePath}...</span>
                </div>
              ) : (
                <>
                  {/* === SUBTAB 1: VISUAL COPY EDIT (No more copy-pasting code!) === */}
                  {editorSubTab === "copy" && (
                    <div className="dfc-visual-copy-container">
                      <div className="dfc-visual-copy-header">
                        <div className="font-bold text-sm text-foreground flex items-center gap-2">
                          <Edit3 className="w-4 h-4 text-emerald-500" />
                          <span>Quick Visual Copy Editor</span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Edit titles, marketing copy, and contact info directly. No manual code copy-pasting required.
                        </p>
                      </div>

                      {isHtmlFile ? (
                        <div className="dfc-visual-copy-fields">
                          <div className="space-y-1">
                            <label className="dfc-input-label">Browser Page Title</label>
                            <input
                              type="text"
                              value={visualCopy.pageTitle}
                              onChange={(e) => setVisualCopy({ ...visualCopy, pageTitle: e.target.value })}
                              placeholder="e.g. RR Residency — Tranquil Luxury"
                              className="dfc-text-input"
                            />
                          </div>

                          <div className="space-y-1">
                            <label className="dfc-input-label">Main Heading (H1)</label>
                            <input
                              type="text"
                              value={visualCopy.h1}
                              onChange={(e) => setVisualCopy({ ...visualCopy, h1: e.target.value })}
                              placeholder="e.g. Experience Elegant Tranquil Luxury"
                              className="dfc-text-input font-bold"
                            />
                          </div>

                          <div className="space-y-1">
                            <label className="dfc-input-label">Subheading (H2)</label>
                            <input
                              type="text"
                              value={visualCopy.h2}
                              onChange={(e) => setVisualCopy({ ...visualCopy, h2: e.target.value })}
                              placeholder="e.g. Curated Accommodations & World-Class Hospitality"
                              className="dfc-text-input"
                            />
                          </div>

                          <div className="space-y-1">
                            <label className="dfc-input-label">Lead Story / Paragraph</label>
                            <textarea
                              rows={3}
                              value={visualCopy.heroParagraph}
                              onChange={(e) => setVisualCopy({ ...visualCopy, heroParagraph: e.target.value })}
                              placeholder="e.g. Immerse yourself in timeless elegance, exquisite accommodations..."
                              className="dfc-text-input resize-none"
                            />
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div className="space-y-1">
                              <label className="dfc-input-label">Primary Call to Action</label>
                              <input
                                type="text"
                                value={visualCopy.buttonText}
                                onChange={(e) => setVisualCopy({ ...visualCopy, buttonText: e.target.value })}
                                placeholder="e.g. Reserve Your Stay"
                                className="dfc-text-input"
                              />
                            </div>

                            <div className="space-y-1">
                              <label className="dfc-input-label">Contact Phone</label>
                              <input
                                type="text"
                                value={visualCopy.phone}
                                onChange={(e) => setVisualCopy({ ...visualCopy, phone: e.target.value })}
                                placeholder="e.g. +1 (800) 555-0199"
                                className="dfc-text-input font-mono text-xs"
                              />
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={handleApplyVisualCopy}
                            className="dfc-btn-apply-copy"
                          >
                            <Check className="w-4 h-4" />
                            <span>Apply Copy &amp; Hot-Reload Live Site</span>
                          </button>
                        </div>
                      ) : (
                        <div className="p-8 text-center text-xs text-muted-foreground">
                          Visual Copy Edit is active for HTML pages. For CSS and JS files, use the Code Editor or AI Model Edit.
                        </div>
                      )}
                    </div>
                  )}

                  {/* === SUBTAB 2: AI EDIT WITH MODEL SELECTOR === */}
                  {editorSubTab === "ai" && (
                    <div className="dfc-ai-edit-container">
                      <div className="dfc-ai-edit-header">
                        <div className="flex items-center gap-2">
                          <Bot className="w-4 h-4 text-indigo-500" />
                          <span className="font-bold text-sm text-foreground">AI Website Copywriter &amp; Architect</span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Choose an AI model and describe any copywriting, design, or feature changes in natural language.
                        </p>
                      </div>

                      {/* AI Model Selector */}
                      <div className="space-y-1.5 mt-3">
                        <label className="dfc-input-label">Select AI Model Engine</label>
                        <select
                          value={selectedModel}
                          onChange={(e) => setSelectedModel(e.target.value)}
                          className="dfc-model-select"
                        >
                          {AI_MODEL_OPTIONS.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.name} — {m.desc}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* AI Prompt Input */}
                      <div className="space-y-1.5 mt-3">
                        <label className="dfc-input-label">Your Edit Instruction</label>
                        <div className="relative">
                          <textarea
                            rows={3}
                            value={aiPromptInput}
                            onChange={(e) => setAiPromptInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleRunAiEdit();
                              }
                            }}
                            placeholder="e.g. Rewrite the dining page hero to sound like a Michelin-starred restaurant and add a wine tasting section..."
                            className="dfc-ai-prompt-textarea"
                          />
                          <button
                            type="button"
                            onClick={() => handleRunAiEdit()}
                            disabled={!aiPromptInput.trim() || isAiGenerating}
                            className="dfc-ai-submit-btn"
                            title="Submit prompt to AI model"
                          >
                            {isAiGenerating ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Send className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* 1-Click Instant AI Transformations */}
                      <div className="mt-4 space-y-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                          ⚡ 1-Click AI Transformations:
                        </span>
                        <div className="flex flex-col gap-1.5">
                          {QUICK_AI_PROMPTS.map((item, idx) => (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => handleRunAiEdit(item.prompt)}
                              disabled={isAiGenerating}
                              className="dfc-quick-prompt-chip"
                            >
                              <Sparkles className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                              <div className="text-left">
                                <div className="font-semibold text-xs text-foreground">{item.label}</div>
                                <div className="text-[11px] text-muted-foreground truncate max-w-[340px]">{item.prompt}</div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* === SUBTAB 3: RAW CODE TEXTAREA === */}
                  {editorSubTab === "code" && (
                    <div className="dfc-editor-scroll">
                      {/* Line numbers column */}
                      <div className="dfc-line-numbers" aria-hidden="true">
                        {Array.from({ length: Math.max(lineCount, 1) }).map((_, i) => (
                          <div key={i + 1}>{i + 1}</div>
                        ))}
                      </div>

                      {/* Textarea */}
                      <textarea
                        ref={editorRef}
                        value={fileContent}
                        onChange={(e) => setFileContent(e.target.value)}
                        onKeyDown={handleKeyDown}
                        className="dfc-textarea"
                        spellCheck="false"
                        autoCapitalize="off"
                        autoComplete="off"
                        autoCorrect="off"
                      />
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Live Preview Pane */}
          {viewMode !== "code" && (
            <div className={`dfc-preview-pane ${viewMode === "preview" ? "full" : "split"}`}>
              {/* Preview Bar */}
              <div className="dfc-preview-bar">
                <div className="flex items-center gap-2 text-xs">
                  <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="font-bold text-foreground">Live Canvas</span>
                  <span className="text-muted-foreground font-mono text-[11px] truncate max-w-[200px]" title={activePageUrl}>
                    {selectedFilePath ? `/${selectedFilePath}` : "/"}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {/* Device Switcher */}
                  <div className="dfc-device-bar">
                    <button
                      type="button"
                      onClick={() => setPreviewDevice("desktop")}
                      className={`dfc-device-btn ${previewDevice === "desktop" ? "active" : ""}`}
                      title="Desktop (100%)"
                    >
                      <Monitor className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setPreviewDevice("tablet")}
                      className={`dfc-device-btn ${previewDevice === "tablet" ? "active" : ""}`}
                      title="Tablet (768px)"
                    >
                      <Tablet className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setPreviewDevice("mobile")}
                      className={`dfc-device-btn ${previewDevice === "mobile" ? "active" : ""}`}
                      title="Mobile (375px)"
                    >
                      <Smartphone className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => setIframeKey((k) => k + 1)}
                    className="dfc-btn-refresh-preview"
                    title="Reload live preview frame"
                  >
                    <RotateCcw className="w-3.5 h-3.5 text-muted-foreground hover:text-foreground" />
                  </button>
                </div>
              </div>

              {/* Iframe Frame Container */}
              <div className="dfc-iframe-container">
                <div className={`dfc-iframe-wrapper ${previewDevice}`}>
                  <iframe
                    key={iframeKey}
                    src={activePageUrl}
                    title="Live Deployment Preview"
                    className="dfc-iframe"
                    sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Bottom Drawer: Live Terminal & Health Log */}
        <div className={`dfc-terminal-drawer ${isTerminalOpen ? "open" : "collapsed"}`}>
          <div className="dfc-terminal-header" onClick={() => setIsTerminalOpen(!isTerminalOpen)}>
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-indigo-500" />
              <span className="font-bold text-xs text-foreground">Deployment Runtime &amp; Hot-Reload Log</span>
              <span className="dfc-terminal-status-dot" />
            </div>
            <button type="button" className="text-xs text-muted-foreground hover:text-foreground">
              {isTerminalOpen ? "Minimize" : "Expand"}
            </button>
          </div>

          {isTerminalOpen && (
            <div className="dfc-terminal-body">
              {terminalLogs.length === 0 ? (
                <div className="text-slate-500">Awaiting deployment console activity...</div>
              ) : (
                terminalLogs.map((log, idx) => (
                  <div key={idx} className="dfc-terminal-line">
                    {log}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
