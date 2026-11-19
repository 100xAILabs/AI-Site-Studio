import React, { useEffect, useState } from "react";
import {
  Key,
  Shield,
  ExternalLink,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  RefreshCw,
  HelpCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "@/lib/api";

export default function SecretsEnvManager({
  templateId,
  stackKey,
  initialEnv = {},
  onChange,
}) {
  const [loading, setLoading] = useState(false);
  const [specs, setSpecs] = useState([]);
  const [envValues, setEnvValues] = useState({ ...initialEnv });
  const [showSecrets, setShowSecrets] = useState({});
  const [isExpanded, setIsExpanded] = useState(true);

  // Fetch detected environment requirements
  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    api
      .post("/deployments/scan-env", {
        template_id: templateId || undefined,
        stack_key: stackKey || undefined,
        existing_env: envValues,
      })
      .then((res) => {
        if (!isMounted) return;
        const vars = res?.env_vars || [];
        setSpecs(vars);

        // Auto-seed default values if not already entered
        setEnvValues((prev) => {
          const updated = { ...prev };
          vars.forEach((v) => {
            if (updated[v.key] === undefined && v.has_default && v.default_value) {
              updated[v.key] = v.default_value;
            }
          });
          return updated;
        });
      })
      .catch((err) => {
        console.warn("Failed to scan environment variables:", err);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [templateId, stackKey]);

  // Notify parent of changes & validation status
  useEffect(() => {
    if (onChange) {
      const missingCritical = specs.filter(
        (s) => s.is_required && !s.has_default && (!envValues[s.key] || !envValues[s.key].trim())
      );
      const isValid = missingCritical.length === 0;
      onChange(envValues, isValid, missingCritical);
    }
  }, [envValues, specs, onChange]);

  const handleChange = (key, value) => {
    setEnvValues((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleApplyDefaults = () => {
    const updated = { ...envValues };
    specs.forEach((s) => {
      if (s.has_default && s.default_value) {
        updated[s.key] = s.default_value;
      } else if (s.key === "SECRET_KEY" || s.key === "JWT_SECRET") {
        if (!updated[s.key]) {
          // Generate client-side secure random string
          const randomBytes = new Uint8Array(24);
          window.crypto.getRandomValues(randomBytes);
          updated[s.key] = Array.from(randomBytes, (b) => b.toString(16).padStart(2, "0")).join("");
        }
      }
    });
    setEnvValues(updated);
  };

  const toggleSecretVisibility = (key) => {
    setShowSecrets((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  if (specs.length === 0 && !loading) {
    return null;
  }

  const missingCount = specs.filter(
    (s) => s.is_required && !s.has_default && (!envValues[s.key] || !envValues[s.key].trim())
  ).length;

  return (
    <div className="space-y-2 rounded-xl border border-border/80 bg-background/50 p-3 text-xs">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 font-bold text-foreground hover:text-primary transition-colors cursor-pointer bg-transparent border-none p-0"
        >
          <Shield className="w-4 h-4 text-[#dfb180]" />
          <span>Environment &amp; Secrets Manager</span>
          {missingCount > 0 ? (
            <span className="px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-[10px] text-amber-300 font-semibold">
              {missingCount} Missing Required
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-[10px] text-emerald-400 font-semibold flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              <span>Ready</span>
            </span>
          )}
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        <button
          type="button"
          onClick={handleApplyDefaults}
          className="text-[10px] font-semibold text-[#dfb180] hover:underline flex items-center gap-1 bg-transparent border-none cursor-pointer"
          title="Fill safe development defaults into variables that support them"
        >
          <Sparkles className="w-3 h-3" />
          <span>Use Safe Defaults</span>
        </button>
      </div>

      <p className="text-[11px] text-muted-foreground m-0">
        Credentials are encrypted and injected into your container/serverless runtime. Never hardcode keys in client code.
      </p>

      {isExpanded && (
        <div className="space-y-3 pt-2">
          {specs.map((spec) => {
            const currentVal = envValues[spec.key] ?? "";
            const isSecret = spec.is_secret;
            const isVisible = showSecrets[spec.key];
            const isMissing = spec.is_required && !spec.has_default && !currentVal.trim();

            return (
              <div
                key={spec.key}
                className={`p-2.5 rounded-lg border transition-all ${
                  isMissing
                    ? "border-amber-500/40 bg-amber-500/5"
                    : "border-border/60 bg-muted/20"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5 flex-wrap">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono font-bold text-foreground text-xs">
                      {spec.key}
                    </span>
                    {spec.is_required && (
                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-red-500/20 text-red-300 font-semibold uppercase">
                        Required
                      </span>
                    )}
                    {spec.has_default && (
                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-semibold uppercase">
                        Default Available
                      </span>
                    )}
                  </div>

                  {spec.provider_url && (
                    <a
                      href={spec.provider_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-[#dfb180] hover:underline flex items-center gap-1 shrink-0"
                    >
                      <span>Get key from {spec.provider_name}</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  )}
                </div>

                <p className="text-[10px] text-muted-foreground mb-2 leading-relaxed">
                  {spec.description}
                </p>

                <div className="relative flex items-center">
                  <input
                    type={isSecret && !isVisible ? "password" : "text"}
                    value={currentVal}
                    onChange={(e) => handleChange(spec.key, e.target.value)}
                    placeholder={spec.placeholder || (spec.has_default ? `Default: ${spec.default_value}` : `Enter ${spec.key}...`)}
                    className="w-full px-2.5 py-1.5 pr-8 rounded bg-background border border-border/80 focus:border-primary focus:outline-none text-foreground font-mono text-[11px]"
                  />
                  {isSecret && (
                    <button
                      type="button"
                      onClick={() => toggleSecretVisibility(spec.key)}
                      className="absolute right-2 text-muted-foreground hover:text-foreground cursor-pointer bg-transparent border-none p-0 flex items-center"
                      aria-label="Toggle secret visibility"
                    >
                      {isVisible ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  )}
                </div>

                {isMissing && (
                  <div className="flex items-center gap-1 mt-1 text-[10px] text-amber-400">
                    <AlertCircle className="w-3 h-3 shrink-0" />
                    <span>This credential is required to deploy this template.</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
