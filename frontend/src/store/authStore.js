/**
 * Auth store — persisted user session using Zustand + localStorage.
 * Integrates with FastAPI backend JWT.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

const SESSION_KEY = "aisitestudio_auth";
const API_BASE = "http://localhost:8000/api/v1";

export const useAuthStore = create(
  persist(
    (set, get) => ({
      // ── State ──────────────────────────────────────────
      user: null,
      token: null,
      isSignedIn: false,
      isLoaded: false,          // true once hydrated
      pendingRedirect: null,    // set after OAuth redirect; consumed by App to navigate()

      // ── Actions ────────────────────────────────────────
      /** Called once on app mount to mark as hydrated */
      setLoaded: async () => {
        // Check URL for token after redirect
        const urlParams = new URLSearchParams(window.location.search);
        const urlToken = urlParams.get('token');
        const urlRedirect = urlParams.get('redirect');
        if (urlToken) {
          get().setToken(urlToken);
          await get().fetchProfile();
          // Store redirect path for the React app to handle (avoids hard page reload)
          if (urlRedirect) {
            set({ pendingRedirect: urlRedirect });
          }
          // Clean up URL
          window.history.replaceState({}, document.title, window.location.pathname);
          set({ isLoaded: true });
        } else if (get().token) {
          if (get().user && get().isSignedIn) {
            // Already hydrated from localStorage, render UI immediately
            set({ isLoaded: true });
            // Fetch in background to sync profile
            get().fetchProfile();
          } else {
            // No user in storage, fetch before rendering
            await get().fetchProfile();
            set({ isLoaded: true });
          }
        } else {
          set({ isLoaded: true });
        }
      },

      setToken: (token) => set({ token, isSignedIn: !!token }),

      clearPendingRedirect: () => set({ pendingRedirect: null }),

      fetchProfile: async () => {
        const { token } = get();
        if (!token) return;
        
        try {
          const res = await fetch(`${API_BASE}/auth/me`, {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          });
          if (res.ok) {
            const dbUser = await res.json();
            const mappedUser = {
              ...dbUser,
              firstName: dbUser.full_name ? dbUser.full_name.split(" ")[0] : "User",
              fullName: dbUser.full_name || "User",
              imageUrl: dbUser.avatar_url || "https://picsum.photos/seed/default/100/100",
              primaryEmailAddress: { emailAddress: dbUser.email }
            };
            set({ user: mappedUser, isSignedIn: true });
          } else if (res.status === 401 || res.status === 403) {
            get().signOut();
          } else {
            console.warn("fetchProfile returned non-OK status:", res.status);
          }
        } catch (err) {
          // Do NOT sign out on network errors or server restarts! Keep existing user session in localStorage.
          console.warn("fetchProfile network error (server restarting or offline):", err);
        }
      },

      /** Redirect to backend OAuth (Google) */
      beginGoogleAuth: (role) => {
        window.location.href = `${API_BASE}/auth/google/login?role=${role || 'buyer'}`;
        return { success: true };
      },

      /** Email Login */
      signInWithEmail: async ({ email, password }) => {
        try {
          const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
          });
          
          if (res.status === 429) {
            throw new Error("Account temporarily locked due to too many failed attempts. Please try again later.");
          }
          
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Invalid email or password");
          }
          const data = await res.json();
          
          if (data.status === "otp_required") {
            return { requires_otp: true, email: data.email };
          }
          
          set({ token: data.access_token, isSignedIn: true });
          await get().fetchProfile();
          return { success: true };
        } catch (err) {
          if (err.name === "TypeError" || err.message?.includes("Failed to fetch") || err.message?.includes("fetch")) {
            throw new Error("Unable to connect to Site Studio server. Please check if the backend is running on http://localhost:8000.");
          }
          console.error("Login failed:", err);
          throw err;
        }
      },

      /** OTP Verification */
      verifyOtp: async ({ email, code }) => {
        try {
          const res = await fetch(`${API_BASE}/auth/verify-otp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, otp: code })
          });
          
          if (res.status === 429) {
            throw new Error("Too many attempts. Please try again later.");
          }
          
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Invalid or expired verification code");
          }
          
          const data = await res.json();
          set({ token: data.access_token, isSignedIn: true });
          await get().fetchProfile();
          return { success: true };
        } catch (err) {
          console.error("OTP verification failed:", err);
          throw err;
        }
      },
      
      /** Resend OTP */
      resendOtp: async ({ email }) => {
        try {
          const res = await fetch(`${API_BASE}/auth/resend-otp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email })
          });
          if (!res.ok) {
            throw new Error("Failed to resend code");
          }
          return { success: true };
        } catch (err) {
          console.error("Resend OTP failed:", err);
          throw err;
        }
      },

      /** Email Register */
      registerWithEmail: async ({ email, password, role }) => {
        try {
          const res = await fetch(`${API_BASE}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password, role })
          });

          if (!res.ok) {
            const err = await res.json();
            // Attach signup_method from response header so the UI can show tailored message
            const signupMethod = res.headers.get("x-signup-method") || null;
            const error = new Error(err.detail || "Registration failed");
            error.status = res.status;
            error.signupMethod = signupMethod;
            throw error;
          }

          const data = await res.json();

          // Backend returns otp_required after new registration
          if (data.status === "otp_required") {
            return { requires_otp: true, email: data.email };
          }

          // If backend directly returns a token (fallback)
          if (data.access_token) {
            set({ token: data.access_token, isSignedIn: true });
            await get().fetchProfile();
          }
          return { success: true };
        } catch (err) {
          if (err.name === "TypeError" || err.message?.includes("Failed to fetch") || err.message?.includes("fetch")) {
            throw new Error("Unable to connect to Site Studio server. Please check if the backend is running on http://localhost:8000.");
          }
          console.error("Registration failed:", err);
          throw err;
        }
      },

      /** Forgot Password — request reset OTP */
      forgotPassword: async ({ email }) => {
        try {
          const res = await fetch(`${API_BASE}/auth/forgot-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email })
          });
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to send reset code");
          }
          return { success: true };
        } catch (err) {
          console.error("Forgot password failed:", err);
          throw err;
        }
      },

      /** Reset Password — verify OTP + set new password */
      resetPassword: async ({ email, otp, newPassword }) => {
        try {
          const res = await fetch(`${API_BASE}/auth/reset-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, otp, new_password: newPassword })
          });
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to reset password");
          }
          return { success: true };
        } catch (err) {
          console.error("Reset password failed:", err);
          throw err;
        }
      },

      /** Complete Onboarding — save profile to backend */
      completeOnboarding: async (profileData) => {
        const { token } = get();
        if (!token) return;
        try {
          const fullName = [profileData.firstName, profileData.lastName].filter(Boolean).join(" ");
          const res = await fetch(`${API_BASE}/auth/me`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
              full_name: fullName,
              bio: profileData.businessName ? `Business: ${profileData.businessName}` : undefined,
            })
          });
          if (res.ok) {
            const updatedUser = await res.json();
            const mappedUser = {
              ...updatedUser,
              firstName: updatedUser.full_name ? updatedUser.full_name.split(" ")[0] : "User",
              fullName: updatedUser.full_name || "User",
              imageUrl: updatedUser.avatar_url || "https://picsum.photos/seed/default/100/100",
              primaryEmailAddress: { emailAddress: updatedUser.email }
            };
            set({ user: mappedUser });
          }
          return { success: true };
        } catch (err) {
          console.error("Complete onboarding failed:", err);
          throw err;
        }
      },

      signOut: () => {
        try {
          localStorage.removeItem("aisitestudio_auth");
        } catch (e) {}
        set({
          user: null,
          token: null,
          isSignedIn: false,
        });
      },

      // Internal helper
      _pendingRole: "buyer",
      setPendingRole: (role) => set({ _pendingRole: role }),
    }),
    {
      name: SESSION_KEY,
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isSignedIn: state.isSignedIn,
      }),
    }
  )
);
