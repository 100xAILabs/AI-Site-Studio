import { useNavigate, useLocation, Link } from "react-router-dom";
import {
  Sparkles,
  LoaderCircle,
  CheckCircle2,
  ExternalLink,
  ChevronUp,
  ChevronDown,
  X,
  Rocket,
  ArrowRight,
  Brain,
} from "lucide-react";
import { useStudioBuildStore } from "@/store/studioBuildStore";
import "./StudioBuildFloatingWidget.css";

export default function StudioBuildFloatingWidget() {
  const navigate = useNavigate();
  const location = useLocation();

  const {
    isBuilding,
    isComplete,
    isPlanning,
    projectTitle,
    activeAgent,
    progress,
    completedTemplateId,
    buildSessionId,
    isMinimized,
    toggleMinimized,
    resetBuild,
  } = useStudioBuildStore();

  // If nothing is building, planning, or recently completed, don't show the widget
  const shouldShow = isBuilding || isPlanning || (isComplete && completedTemplateId);

  // CRITICAL: Never show this background widget when user is inside any studio or preview route
  // (/studio, /studio/launch, /studio/deploy, /preview), because those routes already have their
  // own dedicated full-page interactive pipeline!
  const currentPath = location.pathname.toLowerCase();
  const isInsideStudioFlow =
    currentPath.startsWith("/studio") ||
    currentPath.startsWith("/preview");

  if (!shouldShow || isInsideStudioFlow) {
    return null;
  }

  const buildQuery = buildSessionId ? `&build=${encodeURIComponent(buildSessionId)}` : "";
  const launchHubUrl = `/studio/launch?template=${encodeURIComponent(completedTemplateId)}${buildQuery}`;

  return (
    <aside
      aria-label="Studio process notification"
      className="studio-floating-widget-root"
    >
      {/* Top Header Bar */}
      <div className="studio-floating-header">
        <div className="studio-floating-title-group">
          <span className="studio-floating-dot">
            <span
              className={`studio-floating-dot-ping ${
                isComplete ? "complete" : "active"
              }`}
            />
            <span
              className={`studio-floating-dot-solid ${
                isComplete ? "complete" : "active"
              }`}
            />
          </span>
          <span className="studio-floating-title-text">
            {projectTitle || "Site Studio"}
          </span>
        </div>

        <div className="studio-floating-actions">
          <button
            onClick={toggleMinimized}
            className="studio-floating-icon-btn"
            title={isMinimized ? "Expand process" : "Minimize process"}
          >
            {isMinimized ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          <button
            onClick={resetBuild}
            className="studio-floating-icon-btn"
            title="Dismiss notification"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Content Body (visible when not minimized) */}
      {!isMinimized && (
        <div className="studio-floating-body">
          {isComplete ? (
            /* Completed State */
            <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
              <div className="studio-floating-complete-title">
                <CheckCircle2 size={16} />
                <span>Website Generated Successfully!</span>
              </div>
              <p className="studio-floating-complete-desc">
                Your pages, components, and code are ready. Open Launch Hub to preview, edit, or deploy.
              </p>
              <Link
                to={launchHubUrl}
                onClick={resetBuild}
                className="studio-floating-launch-link"
              >
                <Rocket size={14} />
                <span>Open Launch Hub</span>
                <ArrowRight size={14} />
              </Link>
            </div>
          ) : isPlanning ? (
            /* Planning State */
            <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
              <div className="studio-floating-status-row">
                <span className="studio-floating-agent-name">
                  <Brain size={14} />
                  <span>Planning Agent</span>
                </span>
                <span className="studio-floating-sub-status" style={{ fontFamily: "var(--font-mono)" }}>
                  Analyzing Brief...
                </span>
              </div>
              <div className="studio-floating-progress-track">
                <div
                  className="studio-floating-progress-fill"
                  style={{ width: "60%" }}
                />
              </div>
              <div className="studio-floating-footer-row">
                <span className="studio-floating-sub-status">
                  Architecting project plan
                </span>
                <button
                  onClick={() => navigate("/studio")}
                  className="studio-floating-view-btn"
                >
                  View in Studio →
                </button>
              </div>
            </div>
          ) : (
            /* Multi-Agent Generating State */
            <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
              <div className="studio-floating-status-row">
                <span className="studio-floating-agent-name">
                  <LoaderCircle size={14} className="animate-spin" />
                  <span>{activeAgent || "Agents Generating"}</span>
                </span>
                <span className="studio-floating-progress-pct">{progress}%</span>
              </div>

              <div className="studio-floating-progress-track">
                <div
                  className="studio-floating-progress-fill"
                  style={{ width: `${Math.max(8, progress)}%` }}
                />
              </div>

              <div className="studio-floating-footer-row">
                <span className="studio-floating-sub-status">
                  Running in background...
                </span>
                <button
                  onClick={() => navigate("/studio")}
                  className="studio-floating-view-btn"
                >
                  <span>Open Full Screen</span>
                  <ExternalLink size={12} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Minimized Compact Bar */}
      {isMinimized && (
        <div
          onClick={toggleMinimized}
          className="studio-floating-minimized-bar"
        >
          <span className="studio-floating-min-status">
            {isComplete
              ? "✓ Website Generated"
              : `${activeAgent || "Building"} (${progress}%)`}
          </span>
          <span className="studio-floating-min-hint">Click to expand</span>
        </div>
      )}
    </aside>
  );
}
