import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useAuthStore } from "../../../store/authStore";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export default function AuthCompletePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const setToken = useAuthStore((s) => s.setToken);
  const fetchProfile = useAuthStore((s) => s.fetchProfile);

  useEffect(() => {
    const code = searchParams.get("code");
    const redirect = searchParams.get("redirect") || "/";

    if (!code) {
      navigate("/", { replace: true });
      return;
    }

    let isMounted = true;

    async function exchange() {
      try {
        const res = await fetch(`${API_BASE}/auth/exchange`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ code }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Authentication exchange failed.");
        }

        const data = await res.json();
        if (data.access_token && isMounted) {
          setToken(data.access_token);
          await fetchProfile();
          const target = redirect.startsWith("/") && !redirect.startsWith("//") ? redirect : "/";
          navigate(target, { replace: true });
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || "Failed to complete sign-in. Please try again.");
        }
      }
    }

    exchange();

    return () => {
      isMounted = false;
    };
  }, [searchParams, navigate, setToken, fetchProfile]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="max-w-md w-full text-center p-8 rounded-2xl border border-border/40 bg-card/60 backdrop-blur-xl shadow-2xl">
        {error ? (
          <div>
            <div className="w-12 h-12 rounded-full bg-destructive/15 text-destructive flex items-center justify-center mx-auto mb-4 font-bold text-xl">
              !
            </div>
            <h2 className="text-xl font-bold mb-2">Sign-In Failed</h2>
            <p className="text-sm text-muted-foreground mb-6">{error}</p>
            <button
              onClick={() => navigate("/sign-in", { replace: true })}
              className="px-6 py-2.5 rounded-xl bg-primary text-primary-foreground font-semibold hover:opacity-90 transition-opacity"
            >
              Back to Sign In
            </button>
          </div>
        ) : (
          <div>
            <div className="w-10 h-10 border-3 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <h2 className="text-lg font-bold mb-1">Authenticating...</h2>
            <p className="text-xs text-muted-foreground">Finalizing your secure session...</p>
          </div>
        )}
      </div>
    </div>
  );
}
