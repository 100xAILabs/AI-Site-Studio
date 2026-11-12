"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  X,
  Download,
  Check,
  Sparkles,
  FileCode2,
  AlertCircle,
} from "lucide-react";
import "./DownloadWarningModal.css";

/**
 * DownloadWarningModal:
 * Clean, readable, and modern modal presenting template usage guidelines.
 */
export default function DownloadWarningModal({
  isOpen,
  onClose,
  onConfirm,
  templateTitle = "Template Source Code",
  licenseType = "regular",
  isPro = false,
  isDownloading = false,
}) {
  const [agreed, setAgreed] = useState(false);

  if (!isOpen) return null;

  const isExtended =
    String(licenseType).toLowerCase() === "extended" ||
    String(licenseType).toLowerCase().includes("full") ||
    String(licenseType).toLowerCase() === "commercial";

  return (
    <div className="dwm-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="dwm-container" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="dwm-header">
          <div className="dwm-header-left">
            <div className={`dwm-icon-pill ${isExtended ? "success" : "indigo"}`}>
              {isExtended ? (
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
              ) : (
                <FileCode2 className="w-5 h-5 text-indigo-400" />
              )}
            </div>
            <div>
              <h3 className="dwm-title">
                {isExtended ? "Full Commercial License" : "Standard Edition Guidelines"}
              </h3>
              <p className="dwm-subtitle">
                {isExtended
                  ? "Clean Source Code • Zero Watermarks • Full Commercial Rights"
                  : "Usage terms for free trial and evaluation source code"}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="dwm-close-btn"
            onClick={onClose}
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body Content */}
        <div className="dwm-body">
          {/* Template Info Pill Banner */}
          <div className="dwm-template-banner">
            <div className="flex items-center gap-1.5 truncate">
              <span className="dwm-template-label">Target Template:</span>
              <strong className="dwm-template-name truncate">{templateTitle}</strong>
            </div>
            <span
              className={`dwm-tier-badge ${
                isExtended ? "badge-extended" : "badge-standard"
              }`}
            >
              {isExtended ? "Commercial (Clean)" : "Standard (Attribution)"}
            </span>
          </div>

          {isExtended ? (
            /* Commercial License Clean Points */
            <div className="dwm-commercial-summary">
              <div className="dwm-commercial-box">
                <div className="dwm-commercial-item">
                  <div className="dwm-mini-icon success">
                    <Check className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <strong>100% Clean White-Label Code:</strong> All watermark overlays, corner badges, and attribution files are completely removed.
                  </div>
                </div>

                <div className="dwm-commercial-item">
                  <div className="dwm-mini-icon success">
                    <Check className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <strong>Commercial & Client Rights:</strong> Deploy for unlimited personal, business, or client production websites without attribution.
                  </div>
                </div>

                <div className="dwm-commercial-item">
                  <div className="dwm-mini-icon success">
                    <Check className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <strong>Full Source Assets:</strong> Complete production bundle including components, styles, fonts, and assets.
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* Standard Edition Clean 2-Column Overview */
            <div className="dwm-standard-content">
              {/* Comparison Grid: Allowed vs Prohibited */}
              <div className="dwm-comparison-grid">
                {/* Permitted */}
                <div className="dwm-compare-col allowed">
                  <div className="dwm-compare-header">
                    <span className="dwm-compare-icon-wrap allowed">
                      <Check className="w-3.5 h-3.5" />
                    </span>
                    <span className="dwm-compare-title">What You Can Do</span>
                  </div>
                  <ul className="dwm-compare-list">
                    <li>
                      <Check className="w-3 h-3 text-emerald-400 shrink-0 mt-0.5" />
                      <span>Inspect & test complete source code locally</span>
                    </li>
                    <li>
                      <Check className="w-3 h-3 text-emerald-400 shrink-0 mt-0.5" />
                      <span>Customize text, photos, and brand color palette</span>
                    </li>
                    <li>
                      <Check className="w-3 h-3 text-emerald-400 shrink-0 mt-0.5" />
                      <span>Connect backend APIs, databases, and contact forms</span>
                    </li>
                  </ul>
                </div>

                {/* Prohibited / Standard Restrictions */}
                <div className="dwm-compare-col prohibited">
                  <div className="dwm-compare-header">
                    <span className="dwm-compare-icon-wrap prohibited">
                      <X className="w-3.5 h-3.5" />
                    </span>
                    <span className="dwm-compare-title">Standard Restrictions</span>
                  </div>
                  <ul className="dwm-compare-list">
                    <li>
                      <X className="w-3 h-3 text-rose-400 shrink-0 mt-0.5" />
                      <span>Watermark & corner attribution remain visible</span>
                    </li>
                    <li>
                      <X className="w-3 h-3 text-rose-400 shrink-0 mt-0.5" />
                      <span>Do not delete or bypass attribution files</span>
                    </li>
                    <li>
                      <X className="w-3 h-3 text-rose-400 shrink-0 mt-0.5" />
                      <span>No standalone code reselling on theme markets</span>
                    </li>
                  </ul>
                </div>
              </div>

              {/* White-Label Upgrade Callout Card */}
              <div className="dwm-upgrade-card">
                <div className="dwm-upgrade-header">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-bold text-xs">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Want 100% Clean White-Label Code?</span>
                  </div>
                  <span className="dwm-upgrade-tag">One-Time Buy</span>
                </div>
                <p className="dwm-upgrade-desc">
                  Purchase this template to instantly download clean source code with zero watermarks, no attribution badges, and full commercial client rights.
                </p>
              </div>
            </div>
          )}

          {/* Acknowledgement Checkbox */}
          <label className="dwm-checkbox-label">
            <input
              type="checkbox"
              className="dwm-checkbox-input"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
            />
            <span className="dwm-checkbox-text">
              {isExtended ? (
                <>I acknowledge and accept the <strong>Commercial License</strong> terms.</>
              ) : (
                <>
                  I understand this is a <strong>Standard Edition</strong> package with community attribution.
                </>
              )}
            </span>
          </label>
        </div>

        {/* Footer */}
        <div className="dwm-footer">
          <button
            type="button"
            className="dwm-cancel-btn"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className={`dwm-confirm-btn ${!agreed || isDownloading ? "disabled" : ""}`}
            disabled={!agreed || isDownloading}
            onClick={() => {
              if (agreed && !isDownloading) {
                onConfirm();
              }
            }}
          >
            {isDownloading ? (
              <span>Preparing Download...</span>
            ) : (
              <>
                <Download className="w-4 h-4 mr-1.5" />
                <span>
                  {isExtended ? "Download Clean Package" : "Acknowledge & Download"}
                </span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
