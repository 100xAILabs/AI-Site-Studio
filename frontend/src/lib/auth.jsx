/**
 * Auth context & hooks — powered by the local Zustand authStore.
 * Drop-in replacement for the previous mock/Clerk auth.jsx.
 */

import React, { createContext, useContext, useEffect, useCallback } from "react";
import { useAuthStore, resolveMediaUrl } from "@/store/authStore";

const AuthContext = createContext(null);

export function AppAuthProvider({ children }) {
  const setLoaded = useAuthStore((s) => s.setLoaded);

  useEffect(() => {
    // Mark as hydrated after first render
    setLoaded();
  }, [setLoaded]);

  return <AuthContext.Provider value={null}>{children}</AuthContext.Provider>;
}

// ── Unified Hooks ──────────────────────────────────────────────────────────

export function useAppUser() {
  const { user, isSignedIn, isLoaded } = useAuthStore();
  return { user, isSignedIn, isLoaded: isLoaded !== false };
}

export function useAppAuth() {
  const { token, user, isSignedIn, isLoaded } = useAuthStore();
  const getToken = useCallback(async () => token, [token]);
  return {
    userId: user?.id ?? null,
    getToken,
    isLoaded: isLoaded !== false,
    isSignedIn,
  };
}

// ── Auth Action Hooks ──────────────────────────────────────────────────────

export function useSignIn() {
  return useAuthStore((s) => s.signInWithEmail);
}

export function useSignOut() {
  return useAuthStore((s) => s.signOut);
}

export function useRegister() {
  return useAuthStore((s) => s.registerWithEmail);
}

export function useGoogleAuth() {
  return useAuthStore((s) => s.beginGoogleAuth);
}

export function useGithubAuth() {
  return useAuthStore((s) => s.beginGithubAuth);
}

export function useCompleteOnboarding() {
  return useAuthStore((s) => s.completeOnboarding);
}

export function useNeedsOnboarding() {
  return useAuthStore((s) => s.needsOnboarding);
}

// ── UI Components ──────────────────────────────────────────────────────────

export function AppUserButton() {
  const { user, isSignedIn } = useAppUser();
  const signOut = useSignOut();

  if (!isSignedIn || !user) return null;

  return (
    <div className="flex items-center gap-2">
      <img
        src={resolveMediaUrl(user.imageUrl)}
        alt={user.fullName}
        className="w-8 h-8 rounded-full object-cover border-2 border-[#c89666]/50"
      />
      <button
        onClick={signOut}
        className="hidden md:inline text-xs font-medium px-2.5 py-1.5 rounded-lg bg-[#18181d] hover:bg-red-900/30 hover:text-red-400 border border-[#27272a] transition-all"
      >
        Sign Out
      </button>
    </div>
  );
}

export function AppSignInButton({ children }) {
  const { isSignedIn } = useAppUser();
  if (isSignedIn) return null;
  return children;
}

export function AppSignUpButton({ children }) {
  const { isSignedIn } = useAppUser();
  if (isSignedIn) return null;
  return children;
}
