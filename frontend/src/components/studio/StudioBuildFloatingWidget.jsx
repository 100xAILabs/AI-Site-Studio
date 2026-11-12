import { useEffect } from "react";
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

  // If user is already on /studio during building, we can keep it minimized or hidden to avoid duplication
  const isCurrentlyInStudio = location.pathname === "/studio";

  // Hide floating widget when inside editor, launch hub, or deploy
  const isCurrentlyInLaunch = location.pathname.startsWith("/studio/launch");
  const isCurrentlyInPreview = location.pathname.startsWith("/preview");
  const isCurrentlyInDeploy = location.pathname.startsWith("/studio/deploy");

  if (!shouldShow || isCurrentlyInLaunch || isCurrentlyInPreview || isCurrentlyInDeploy) {
    return null;
  }

  // If user is already in /studio and building, the main page already shows the full pipeline
  if (isCurrentlyInStudio && isBuilding && !isMinimized) {
    return null;
  }

  const buildQuery = buildSessionId ? `&build=${encodeURIComponent(buildSessionId)}` : "";
  const launchHubUrl = `/studio/launch?template=${encodeURIComponent(completedTemplateId)}${buildQuery}`;

  return (
    <aside
      aria-label="Studio process notification"
      className="fixed bottom-6 right-6 z-50 transition-all duration-300 ease-out"
    >
      <div className="w-[340px] sm:w-[380px] overflow-hidden rounded-2xl border border-[#c89666]/30 bg-[#0c121e]/95 backdrop-blur-xl shadow-2xl shadow-violet-950/50 text-white">
        {/* Top Header Bar */}
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 bg-slate-900/40">
          <div className="flex items-center gap-2.5 truncate pr-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isComplete ? "bg-emerald-400" : "bg-[#c89666]/15"}`} />
              <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isComplete ? "bg-emerald-500" : "bg-[#c89666]/15"}`} />
            </span>
            <span className="text-xs font-bold text-white truncate max-w-[200px]">
              {projectTitle || "AI Website Studio"}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={toggleMinimized}
              className="rounded-lg p-1 text-slate-400 hover:bg-white/10 hover:text-white transition"
              title={isMinimized ? "Expand process" : "Minimize process"}
            >
              {isMinimized ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>
            {isComplete && (
              <button
                onClick={resetBuild}
                className="rounded-lg p-1 text-slate-400 hover:bg-white/10 hover:text-white transition"
                title="Dismiss"
              >
                <X size={15} />
              </button>
            )}
          </div>
        </div>

        {/* Content Body (visible when not minimized) */}
        {!isMinimized && (
          <div className="p-4 space-y-3.5">
            {isComplete ? (
              /* Completed State */
              <div className="space-y-3">
                <div className="flex items-center gap-2.5 text-xs text-emerald-400 font-semibold">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                  <span>Website Generated Successfully!</span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Your pages, components, and code are ready. Moving to your Launch Hub...
                </p>
                <Link
                  to={launchHubUrl}
                  onClick={resetBuild}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-[#c89666]/15 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-violet-600/30 hover:bg-[#c89666]/15 transition cursor-pointer"
                >
                  <Rocket className="h-3.5 w-3.5" />
                  <span>Open Launch Hub</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            ) : isPlanning ? (
              /* Planning State */
              <div className="space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="inline-flex items-center gap-1.5 text-[#dfb180] font-semibold">
                    <Brain className="h-3.5 w-3.5 animate-pulse" />
                    <span>Planning Agent</span>
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">Analyzing Brief...</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                  <div className="h-full w-2/3 animate-pulse rounded-full bg-gradient-to-r from-[#c89666] to-[#b5804f] from-[#c89666] to-[#b5804f]" />
                </div>
                <div className="flex items-center justify-between pt-1">
                  <span className="text-[10px] text-slate-400">Architecting project blueprint</span>
                  <button
                    onClick={() => navigate("/studio")}
                    className="text-[11px] font-bold text-[#dfb180] hover:text-[#dfb180] transition"
                  >
                    View in Studio →
                  </button>
                </div>
              </div>
            ) : (
              /* Building / Multi-Agent Generating State */
              <div className="space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="inline-flex items-center gap-1.5 text-[#dfb180] font-semibold truncate max-w-[220px]">
                    <LoaderCircle className="h-3.5 w-3.5 animate-spin text-[#dfb180] shrink-0" />
                    <span>{activeAgent || "Agents Working"}</span>
                  </span>
                  <span className="text-[11px] font-bold font-mono text-emerald-400">{progress}%</span>
                </div>

                {/* Animated Progress Bar */}
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/10 p-0.5">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[#c89666] to-[#b5804f] from-[#c89666] to-[#b5804f] to-emerald-400 transition-all duration-500"
                    style={{ width: `${Math.max(8, progress)}%` }}
                  />
                </div>

                <div className="flex items-center justify-between pt-1 text-[11px]">
                  <span className="text-slate-400">Running in background...</span>
                  <button
                    onClick={() => navigate("/studio")}
                    className="inline-flex items-center gap-1 font-bold text-[#dfb180] hover:text-[#dfb180] transition"
                  >
                    <span>Open Full Screen</span>
                    <ExternalLink size={11} />
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
            className="flex items-center justify-between px-4 py-2 text-xs cursor-pointer hover:bg-white/5 transition"
          >
            <span className="text-[11px] text-slate-300 font-medium truncate">
              {isComplete ? "✓ Generation Complete" : `${activeAgent || "Building"} (${progress}%)`}
            </span>
            <span className="text-[10px] text-[#dfb180] font-bold ml-2">Click to expand</span>
          </div>
        )}
      </div>
    </aside>
  );
}

