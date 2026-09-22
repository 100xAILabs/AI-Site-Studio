"use client";

import React, { useState, useEffect, useRef } from "react";
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
} from "lucide-react";
import { api } from "../../lib/api";
import "./DeploymentFixConsole.css";

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

  // AI Site Doctor State
  const [isAiFixing, setIsAiFixing] = useState(false);
  const [aiReport, setAiReport] = useState(null);

  // Bottom Terminal
  const [terminalLogs, setTerminalLogs] = useState([]);
  const [isTerminalOpen, setIsTerminalOpen] = useState(true);

  const editorRef = useRef(null);

  const siteId = deployment?.site_id || `SITE-${deployment?.id?.slice(0, 6)?.toUpperCase()}`;

  // 1. Fetch file list when opened
  useEffect(() => {
    if (!isOpen || !deployment?.id) return;

    let mounted = true;
    const fetchFiles = async () => {
      setLoadingFiles(true);
      try {
        const res = await api.get(`/admin/deployments/${deployment.id}/files`, authToken ?? undefined);
        if (mounted) {
          const files = res.files || [];
          setFileList(files);
          // Auto-select index.html or first file
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
          `/admin/deployments/${deployment.id}/file-content?path=${encodeURIComponent(selectedFilePath)}`,
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
    // Save shortcut Ctrl+S or Cmd+S
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      handleSaveFile();
      return;
    }

    // Tab indentation
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
  const handleSaveFile = async () => {
    if (!selectedFilePath || !deployment?.id) return;

    setSavingFile(true);
    setSaveSuccess(false);
    try {
      const payload = {
        path: selectedFilePath,
        content: fileContent,
        incident_id: incident?.id || undefined,
      };

      const res = await api.put(
        `/admin/deployments/${deployment.id}/files`,
        payload,
        authToken ?? undefined
      );

      setOriginalContent(fileContent);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);

      setTerminalLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ✓ Saved ${selectedFilePath}. Site hot-reloaded: ${res.health || "HTTP 200 OK"}`,
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

  // 4. Trigger Autonomous AI Site Doctor
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

      // Reload current open file if it was among the patched files
      if (res.patched_files && res.patched_files.includes(selectedFilePath)) {
        const fileRes = await api.get(
          `/admin/deployments/${deployment.id}/file-content?path=${encodeURIComponent(selectedFilePath)}`,
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
  const liveSiteUrl = deployment.live_url || `http://localhost:8000/sites/${deployment.site_id}/`;

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
                {isDirty && <span className="dfc-dirty-pill">● Unsaved</span>}
              </div>
              <p className="dfc-sub">
                Live Deployment Code Studio &amp; AI Incident Healing Console
              </p>
            </div>
          </div>

          <div className="dfc-header-actions">
            <a
              href={liveSiteUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="dfc-btn-secondary"
              title="Open deployed website in new tab"
            >
              <ExternalLink className="w-4 h-4" />
              <span className="hidden sm:inline">Visit Site</span>
            </a>

            <button
              type="button"
              onClick={handleAiAutoFix}
              disabled={isAiFixing}
              className="dfc-btn-ai"
              title="Run Autonomous AI Site Doctor to automatically patch and heal issues"
            >
              {isAiFixing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>AI Healing...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-amber-300" />
                  <span>⚡ AI Auto-Fix</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleSaveFile}
              disabled={savingFile || !isDirty}
              className={`dfc-btn-save ${saveSuccess ? "success" : ""}`}
              title="Save changes and hot-redeploy (Ctrl+S)"
            >
              {savingFile ? (
                <Loader2 className="w-4 h-4 animate-spin text-white" />
              ) : saveSuccess ? (
                <Check className="w-4 h-4 text-white" />
              ) : (
                <Save className="w-4 h-4 text-white" />
              )}
              <span>{saveSuccess ? "Saved & Live!" : "Save & Redeploy"}</span>
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

        {/* Studio Workspace Layout: Sidebar + Code Editor */}
        <div className="dfc-workspace">
          {/* Left File Tree Sidebar */}
          <div className="dfc-sidebar">
            <div className="dfc-sidebar-header">
              <Folder className="w-4 h-4 text-primary" />
              <span>Project Files</span>
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

          {/* Center Code Editor Area */}
          <div className="dfc-editor-pane">
            {/* Editor Breadcrumb Strip */}
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

            {/* Code Textarea with Line Numbers */}
            {loadingContent ? (
              <div className="dfc-editor-loading">
                <Loader2 className="w-6 h-6 animate-spin text-primary" />
                <span className="text-xs text-muted-foreground mt-2 font-mono">Opening {selectedFilePath}...</span>
              </div>
            ) : (
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
          </div>
        </div>

        {/* Bottom Drawer: Live Terminal & Health Log */}
        <div className={`dfc-terminal-drawer ${isTerminalOpen ? "open" : "collapsed"}`}>
          <div className="dfc-terminal-header" onClick={() => setIsTerminalOpen(!isTerminalOpen)}>
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-indigo-500" />
              <span className="font-bold text-xs text-foreground">Deployment Runtime &amp; Healing Log</span>
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
