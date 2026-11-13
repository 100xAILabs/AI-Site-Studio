"use client";

import { useState, useRef, useEffect } from "react";
import { useTheme } from "@/hooks/useTheme";
import { Sun, Moon, Laptop, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import "./ThemeToggle.css";

/**
 * ThemeToggle — accessible 3-state theme selector (Light, Dark, System)
 * with fast 1-click quick-toggle and accessible dropdown.
 */
export default function ThemeToggle({ variant = "compact", className = "" }) {
  const { theme, setTheme, resolvedTheme, isMounted } = useTheme();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const containerRef = useRef(null);

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!isMounted) {
    return (
      <div className={`theme-toggle-skeleton ${className}`} aria-hidden="true">
        <span className="theme-toggle-skeleton-icon" />
      </div>
    );
  }

  const isDark = resolvedTheme === "dark";

  // Fast toggle handler: toggles light/dark directly on single click
  const handleQuickToggle = (e) => {
    if (e.shiftKey || e.altKey) {
      // Allow power users to open dropdown
      setDropdownOpen(!dropdownOpen);
      return;
    }
    setTheme(isDark ? "light" : "dark");
  };

  const handleSelectMode = (mode) => {
    setTheme(mode);
    setDropdownOpen(false);
  };

  if (variant === "pill") {
    // 3-way segmented pill control (used in Settings/Dashboard)
    return (
      <div className={`theme-pill-group ${className}`} role="radiogroup" aria-label="Theme selection">
        <button
          type="button"
          role="radio"
          aria-checked={theme === "light"}
          className={`theme-pill-option ${theme === "light" ? "active" : ""}`}
          onClick={() => handleSelectMode("light")}
        >
          <Sun className="theme-pill-icon" />
          <span>Light</span>
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={theme === "dark"}
          className={`theme-pill-option ${theme === "dark" ? "active" : ""}`}
          onClick={() => handleSelectMode("dark")}
        >
          <Moon className="theme-pill-icon" />
          <span>Dark</span>
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={theme === "system"}
          className={`theme-pill-option ${theme === "system" ? "active" : ""}`}
          onClick={() => handleSelectMode("system")}
        >
          <Laptop className="theme-pill-icon" />
          <span>System</span>
        </button>
      </div>
    );
  }

  // Compact navbar icon button with right-click / hover / chevron for options
  return (
    <div className={`theme-toggle-container ${className}`} ref={containerRef}>
      <button
        type="button"
        onClick={handleQuickToggle}
        onContextMenu={(e) => {
          e.preventDefault();
          setDropdownOpen(!dropdownOpen);
        }}
        aria-label={`Toggle theme (currently ${theme}). Right click or shift-click for options.`}
        title={`Theme: ${theme.charAt(0).toUpperCase() + theme.slice(1)} (Click to switch to ${isDark ? "Light" : "Dark"})`}
        className="theme-toggle-btn"
      >
        <AnimatePresence mode="wait" initial={false}>
          {isDark ? (
            <motion.div
              key="moon"
              initial={{ rotate: -90, opacity: 0, scale: 0.8 }}
              animate={{ rotate: 0, opacity: 1, scale: 1 }}
              exit={{ rotate: 90, opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.18 }}
              className="theme-toggle-icon-wrap"
            >
              <Moon className="w-4 h-4 theme-icon-moon" />
            </motion.div>
          ) : (
            <motion.div
              key="sun"
              initial={{ rotate: 90, opacity: 0, scale: 0.8 }}
              animate={{ rotate: 0, opacity: 1, scale: 1 }}
              exit={{ rotate: -90, opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.18 }}
              className="theme-toggle-icon-wrap"
            >
              <Sun className="w-4 h-4 theme-icon-sun" />
            </motion.div>
          )}
        </AnimatePresence>
      </button>

      {/* Dropdown Options */}
      <AnimatePresence>
        {dropdownOpen && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.95 }}
            transition={{ duration: 0.14 }}
            className="theme-dropdown-menu"
          >
            <div className="theme-dropdown-header">Appearance</div>
            <button
              type="button"
              className={`theme-dropdown-item ${theme === "light" ? "selected" : ""}`}
              onClick={() => handleSelectMode("light")}
            >
              <div className="theme-dropdown-item-left">
                <Sun className="w-4 h-4 theme-icon-sun" />
                <span>Light</span>
              </div>
              {theme === "light" && <Check className="w-3.5 h-3.5 theme-check-icon" />}
            </button>
            <button
              type="button"
              className={`theme-dropdown-item ${theme === "dark" ? "selected" : ""}`}
              onClick={() => handleSelectMode("dark")}
            >
              <div className="theme-dropdown-item-left">
                <Moon className="w-4 h-4 theme-icon-moon" />
                <span>Dark</span>
              </div>
              {theme === "dark" && <Check className="w-3.5 h-3.5 theme-check-icon" />}
            </button>
            <button
              type="button"
              className={`theme-dropdown-item ${theme === "system" ? "selected" : ""}`}
              onClick={() => handleSelectMode("system")}
            >
              <div className="theme-dropdown-item-left">
                <Laptop className="w-4 h-4 theme-icon-laptop" />
                <span>System</span>
              </div>
              {theme === "system" && <Check className="w-3.5 h-3.5 theme-check-icon" />}
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

