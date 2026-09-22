"use client";

import React, { useState, useEffect } from "react";
import {
  AlertTriangle,
  Sparkles,
  Wrench,
  CheckCircle2,
  ExternalLink,
  Search,
  RefreshCw,
  Loader2,
  Bug,
  Flame,
  FileCode,
  ShieldAlert,
  Clock,
  User,
  Filter,
  Check,
} from "lucide-react";
import { api } from "../../lib/api";
import "./AdminIncidentsCenter.css";

export default function AdminIncidentsCenter({
  authToken,
  onOpenCodeStudio,
}) {
  const [incidents, setIncidents] = useState([]);
  const [stats, setStats] = useState({ total: 0, open: 0, auto_fixed: 0, resolved: 0 });
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [healingIncidentId, setHealingIncidentId] = useState(null);

  const fetchIncidents = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter && statusFilter !== "all") params.append("status", statusFilter);
      if (searchQuery.trim()) params.append("search", searchQuery.trim());

      const res = await api.get(`/admin/incidents?${params.toString()}`, authToken ?? undefined);
      setIncidents(res.items || []);
      if (res.stats) setStats(res.stats);
    } catch (err) {
      console.error("Failed to load incidents:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, [statusFilter, authToken]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchIncidents();
  };

  // Quick 1-click AI Auto-Heal from Incident Table
  const handleTriggerAiFix = async (incident) => {
    setHealingIncidentId(incident.id);
    try {
      const res = await api.post(
        `/admin/deployments/${incident.deployment_id}/auto-fix`,
        {
          incident_id: incident.id,
          issue_description: incident.description,
          error_logs: incident.error_logs,
          issue_type: incident.issue_type,
        },
        authToken ?? undefined
      );

      alert(
        `✓ AI Site Doctor successfully healed website ${incident.site_id} in under 3 seconds!\n\nDiagnosis: ${res.diagnosis || "Patches applied"}\nPatched Files: ${(res.patched_files || []).join(", ") || "index.html"}`
      );
      fetchIncidents();
    } catch (err) {
      alert("AI Auto-Fix error: " + err.message);
    } finally {
      setHealingIncidentId(null);
    }
  };

  // Status toggle
  const handleUpdateStatus = async (incidentId, newStatus) => {
    try {
      await api.patch(
        `/admin/incidents/${incidentId}/status`,
        { status: newStatus, resolved_by: "admin_manual" },
        authToken ?? undefined
      );
      fetchIncidents();
    } catch (err) {
      alert("Failed to update status: " + err.message);
    }
  };

  return (
    <div className="aic-container">
      {/* Header Banner */}
      <div className="aic-header-card">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="aic-title">Platform Website Incidents &amp; AI Healer</h2>
              <span className="aic-pill-live">
                <span className="aic-dot-pulse" />
                Live Sentinel
              </span>
            </div>
            <p className="aic-desc">
              Monitor broken website reports, edit deployment source code in real-time, or dispatch the Autonomous AI Site Doctor to restore sites instantly.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={fetchIncidents}
              disabled={loading}
              className="aic-btn-refresh"
              title="Refresh incident list"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>
        </div>

        {/* 4 KPI Stat Ribbon Cards */}
        <div className="aic-stats-grid">
          <div className="aic-stat-card">
            <div className="aic-stat-label">Total Failures Reported</div>
            <div className="aic-stat-value">{stats.total}</div>
            <div className="aic-stat-sub">Across all customer websites</div>
          </div>

          <div className="aic-stat-card border-amber-500/30">
            <div className="aic-stat-label flex items-center justify-between">
              <span>Open &amp; Degraded</span>
              {stats.open > 0 && <span className="aic-warn-dot" />}
            </div>
            <div className="aic-stat-value text-amber-500">{stats.open}</div>
            <div className="aic-stat-sub">Requires admin or AI action</div>
          </div>

          <div className="aic-stat-card border-indigo-500/30">
            <div className="aic-stat-label flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
              <span>AI Auto-Healed</span>
            </div>
            <div className="aic-stat-value text-indigo-600 dark:text-indigo-400">{stats.auto_fixed}</div>
            <div className="aic-stat-sub">Resolved autonomously (&lt;3s)</div>
          </div>

          <div className="aic-stat-card border-emerald-500/30">
            <div className="aic-stat-label flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              <span>Resolved</span>
            </div>
            <div className="aic-stat-value text-emerald-600 dark:text-emerald-400">{stats.resolved}</div>
            <div className="aic-stat-sub">Total healthy &amp; restored</div>
          </div>
        </div>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div className="aic-toolbar">
        <div className="aic-tabs">
          {[
            { id: "all", label: "All Incidents", count: stats.total },
            { id: "open", label: "Open Issues", count: stats.open },
            { id: "auto_fixed", label: "Auto-Fixed by AI", count: stats.auto_fixed },
            { id: "resolved", label: "Resolved", count: stats.resolved },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setStatusFilter(tab.id)}
              className={`aic-tab-btn ${statusFilter === tab.id ? "active" : ""}`}
            >
              <span>{tab.label}</span>
              <span className={`aic-tab-badge ${statusFilter === tab.id ? "active" : ""}`}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        <form onSubmit={handleSearchSubmit} className="aic-search-form">
          <Search className="w-4 h-4 aic-search-icon" />
          <input
            type="text"
            placeholder="Search site ID, title, or reporter..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="aic-search-input"
          />
        </form>
      </div>

      {/* Incidents Table */}
      {loading ? (
        <div className="aic-empty-state">
          <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-2" />
          <p className="text-sm font-semibold text-foreground">Loading reported incidents...</p>
        </div>
      ) : incidents.length === 0 ? (
        <div className="aic-empty-state">
          <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2 opacity-80" />
          <h4 className="text-base font-extrabold text-foreground">Zero Active Failure Incidents</h4>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
            All customer deployments are running healthy with no open downtime reports.
          </p>
        </div>
      ) : (
        <div className="aic-table-wrapper">
          <table className="aic-table">
            <thead>
              <tr>
                <th>Site &amp; Deployment</th>
                <th>Category</th>
                <th>Issue Summary</th>
                <th>Reporter</th>
                <th>Status</th>
                <th className="text-right">Action Studio</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((incident) => {
                const isOpen = incident.status === "open" || incident.status === "investigating";
                const isAutoFixed = incident.resolved_by === "ai_site_doctor";
                const isHealingThis = healingIncidentId === incident.id;

                return (
                  <tr key={incident.id} className={isOpen ? "row-open" : ""}>
                    {/* Site ID & Name */}
                    <td>
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-2">
                          <span className="aic-site-tag">{incident.site_id}</span>
                          <span className="font-extrabold text-sm text-foreground truncate max-w-[170px]" title={incident.project_name}>
                            {incident.project_name}
                          </span>
                        </div>
                        {incident.live_url && (
                          <a
                            href={incident.live_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="aic-live-link"
                          >
                            <ExternalLink className="w-3 h-3" /> Visit Live Site
                          </a>
                        )}
                      </div>
                    </td>

                    {/* Category */}
                    <td>
                      <span className="aic-cat-badge">
                        {incident.issue_type === "broken_script" ? (
                          <><Bug className="w-3 h-3 text-indigo-500" /> JS Error</>
                        ) : incident.issue_type === "page_crash" ? (
                          <><Flame className="w-3 h-3 text-red-500" /> Crash</>
                        ) : incident.issue_type === "asset_404" ? (
                          <><FileCode className="w-3 h-3 text-amber-500" /> 404 Asset</>
                        ) : (
                          <><Wrench className="w-3 h-3 text-sky-500" /> Layout</>
                        )}
                      </span>
                    </td>

                    {/* Summary & Error Preview */}
                    <td className="max-w-[280px]">
                      <div className="font-bold text-xs text-foreground truncate" title={incident.title}>
                        {incident.title}
                      </div>
                      <div className="text-[11px] text-muted-foreground line-clamp-1 mt-0.5" title={incident.description}>
                        {incident.description}
                      </div>
                      {incident.ai_patch_summary && (
                        <div className="aic-ai-patch-pill">
                          <Sparkles className="w-2.5 h-2.5" /> {incident.ai_patch_summary}
                        </div>
                      )}
                    </td>

                    {/* Reporter & Time */}
                    <td>
                      <div className="text-xs text-foreground font-semibold truncate max-w-[140px]">
                        {incident.reporter_email || "Anonymous Visitor"}
                      </div>
                      <div className="text-[10px] text-muted-foreground flex items-center gap-1 mt-0.5">
                        <Clock className="w-3 h-3" />
                        {new Date(incident.created_at).toLocaleDateString()} {new Date(incident.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </td>

                    {/* Status Badge */}
                    <td>
                      {isOpen ? (
                        <span className="aic-status-badge open">
                          <span className="aic-badge-dot pulse-amber" /> Open
                        </span>
                      ) : isAutoFixed ? (
                        <span className="aic-status-badge auto-healed">
                          <Sparkles className="w-3 h-3 text-indigo-500" /> AI Fixed
                        </span>
                      ) : (
                        <span className="aic-status-badge resolved">
                          <Check className="w-3 h-3 text-emerald-500" /> Resolved
                        </span>
                      )}
                    </td>

                    {/* Action Hub */}
                    <td className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {/* 1-Click AI Auto-Heal Button */}
                        <button
                          type="button"
                          onClick={() => handleTriggerAiFix(incident)}
                          disabled={isHealingThis}
                          className="aic-btn-ai-heal"
                          title="Auto-Fix website immediately with AI Site Doctor"
                        >
                          {isHealingThis ? (
                            <Loader2 className="w-3 h-3 animate-spin text-white" />
                          ) : (
                            <Sparkles className="w-3 h-3 text-amber-300" />
                          )}
                          <span>Auto-Fix</span>
                        </button>

                        {/* Open Manual Code Studio Button */}
                        <button
                          type="button"
                          onClick={() => {
                            if (onOpenCodeStudio) {
                              onOpenCodeStudio({
                                id: incident.deployment_id,
                                site_id: incident.site_id,
                                project_name: incident.project_name,
                                live_url: incident.live_url,
                                current_version: "v1.0",
                              }, incident);
                            }
                          }}
                          className="aic-btn-studio"
                          title="Open Code Studio to inspect and edit code directly"
                        >
                          <Wrench className="w-3 h-3 text-indigo-500" />
                          <span>Code Studio</span>
                        </button>

                        {isOpen && (
                          <button
                            type="button"
                            onClick={() => handleUpdateStatus(incident.id, "resolved")}
                            className="aic-btn-dismiss"
                            title="Mark as Resolved"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
