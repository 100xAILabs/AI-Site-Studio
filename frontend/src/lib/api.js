/**
 * API client configuration.
 * All API calls go through this client so auth headers are consistently applied.
 */

import { useAuthStore } from "../store/authStore";

const API_URL = import.meta.env.VITE_API_URL ?? import.meta.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(status, message, data) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function request(path, options = {}) {
  const { token, ...fetchOptions } = options;

  const headers = {
    "Content-Type": "application/json",
    ...fetchOptions.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (!res.ok) {
    if (res.status === 401) {
      useAuthStore.getState().signOut();
    }
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail ?? res.statusText, data);
  }

  if (res.status === 204) return undefined;
  return res.json();
}

// Convenience methods
export const api = {
  get: (path, token) =>
    request(path, { method: "GET", token }),

  post: (path, body, token) =>
    request(path, {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),

  patch: (path, body, token) =>
    request(path, {
      method: "PATCH",
      body: JSON.stringify(body),
      token,
    }),

  delete: (path, token) =>
    request(path, { method: "DELETE", token }),
};

export { API_URL };
