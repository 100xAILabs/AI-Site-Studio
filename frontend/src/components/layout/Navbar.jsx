"use client";

/**
 * Navbar — modern sleek studio header with search, dropdowns, theme toggle, and auth.
 */

import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Link from "@/components/Link";
const usePathname = () => window.location.pathname;
import { useTheme } from "@/hooks/useTheme";
import { useAppUser, useSignOut } from "@/lib/auth";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Sun,
  Moon,
  ShoppingCart,
  Menu,
  X,
  ChevronDown,
  ArrowRight,
  Sparkles,
  Zap,
  Globe,
  Layers,
  ShoppingBag,
  Briefcase,
  FileText,
  HelpCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCartStore } from "@/store";
import { useCurrencyStore } from "@/store/currencyStore";
import { SiteStudioLogoIcon } from "./SiteStudioLogo";
import ThemeToggle from "./ThemeToggle";
import "./Navbar.css";

function NavbarComponent() {
  const { theme, setTheme } = useTheme();
  const { isSignedIn, user } = useAppUser();
  const signOut = useSignOut();
  const pathname = usePathname();
  const navigate = useNavigate();
  const cartItems = useCartStore((s) => s.items);
  const { userCurrency, setUserCurrency, fetchRates } = useCurrencyStore();
  const [scrolled, setScrolled] = useState(false);

  const isSeller = isSignedIn && (user?.role === "seller" || user?.role === "SELLER");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [templatesDropdown, setTemplatesDropdown] = useState(false);
  const [resourcesDropdown, setResourcesDropdown] = useState(false);

  const templatesRef = useRef(null);
  const resourcesRef = useRef(null);

  useEffect(() => {
    fetchRates();
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [fetchRates]);

  useEffect(() => {
    if (user?.currency) {
      setUserCurrency(user.currency);
    }
  }, [user?.currency, setUserCurrency]);

  // Click outside to close dropdowns
  useEffect(() => {
    function handleClickOutside(e) {
      if (templatesRef.current && !templatesRef.current.contains(e.target)) {
        setTemplatesDropdown(false);
      }
      if (resourcesRef.current && !resourcesRef.current.contains(e.target)) {
        setResourcesDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/marketplace?q=${encodeURIComponent(searchQuery.trim())}`);
      setMobileOpen(false);
    } else {
      navigate(`/marketplace`);
    }
  };

  const isSolidNavbar = scrolled || (pathname && pathname !== "/");

  return (
    <header
      className={cn(
        "navbar-header",
        isSolidNavbar && "scrolled",
        pathname === "/" && "navbar-home"
      )}
    >
      <div className="container-xl navbar-inner">
        {/* Left: Brand Logo */}
        <Link href="/" className="logo-container">
          <SiteStudioLogoIcon className="navbar-logo-icon" />
          <span className="logo-text">
            Site Studio
          </span>
        </Link>

        {/* Center: Navigation Links */}
        <nav className="navbar-center-nav">
          {/* Home Link with Active Indicator */}
          <Link
            href="/"
            className={cn("nav-center-item", pathname === "/" && "nav-item-active")}
          >
            <span>Home</span>
            {pathname === "/" && <span className="nav-active-pill" />}
          </Link>

          {/* Templates Dropdown */}
          <div
            className="nav-dropdown-wrapper"
            ref={templatesRef}
            onMouseEnter={() => setTemplatesDropdown(true)}
            onMouseLeave={() => setTemplatesDropdown(false)}
          >
            <button
              type="button"
              className={cn(
                "nav-center-item nav-dropdown-btn",
                pathname.startsWith("/marketplace") && "nav-item-active"
              )}
              onClick={() => setTemplatesDropdown((v) => !v)}
            >
              <span>Templates</span>
              <ChevronDown className={cn("w-3.5 h-3.5 nav-chevron", templatesDropdown && "rotate-180")} />
            </button>

            <AnimatePresence>
              {templatesDropdown && (
                <motion.div
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 6, scale: 0.96 }}
                  transition={{ duration: 0.15 }}
                  className="nav-dropdown-menu"
                >
                  <Link
                    href="/marketplace"
                    className="dropdown-menu-item"
                    onClick={() => setTemplatesDropdown(false)}
                  >
                    <Layers className="dropdown-item-icon" />
                    <div>
                      <div className="dropdown-item-title">All Templates</div>
                      <div className="dropdown-item-desc">Browse entire collection</div>
                    </div>
                  </Link>
                  <Link
                    href="/marketplace?category=saas-technology"
                    className="dropdown-menu-item"
                    onClick={() => setTemplatesDropdown(false)}
                  >
                    <Zap className="dropdown-item-icon text-[#dfb180]" />
                    <div>
                      <div className="dropdown-item-title">AI & SaaS</div>
                      <div className="dropdown-item-desc">Modern tech & software designs</div>
                    </div>
                  </Link>
                  <Link
                    href="/marketplace?category=ecommerce"
                    className="dropdown-menu-item"
                    onClick={() => setTemplatesDropdown(false)}
                  >
                    <ShoppingBag className="dropdown-item-icon text-pink-400" />
                    <div>
                      <div className="dropdown-item-title">E-Commerce & Retail</div>
                      <div className="dropdown-item-desc">Online shops & storefronts</div>
                    </div>
                  </Link>
                  <Link
                    href="/marketplace?category=business"
                    className="dropdown-menu-item"
                    onClick={() => setTemplatesDropdown(false)}
                  >
                    <Briefcase className="dropdown-item-icon text-[#c89666]" />
                    <div>
                      <div className="dropdown-item-title">Business & Agency</div>
                      <div className="dropdown-item-desc">Hotels, agencies & corporate</div>
                    </div>
                  </Link>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Marketplace Link */}
          <Link
            href="/marketplace"
            className={cn("nav-center-item", pathname === "/marketplace" && "nav-item-active")}
          >
            <span>Marketplace</span>
          </Link>

          {/* Resources Dropdown */}
          <div
            className="nav-dropdown-wrapper"
            ref={resourcesRef}
            onMouseEnter={() => setResourcesDropdown(true)}
            onMouseLeave={() => setResourcesDropdown(false)}
          >
            <button
              type="button"
              className="nav-center-item nav-dropdown-btn"
              onClick={() => setResourcesDropdown((v) => !v)}
            >
              <span>Resources</span>
              <ChevronDown className={cn("w-3.5 h-3.5 nav-chevron", resourcesDropdown && "rotate-180")} />
            </button>

            <AnimatePresence>
              {resourcesDropdown && (
                <motion.div
                  initial={{ opacity: 0, y: 8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 6, scale: 0.96 }}
                  transition={{ duration: 0.15 }}
                  className="nav-dropdown-menu"
                >
                  <Link
                    href="/about"
                    className="dropdown-menu-item"
                    onClick={() => setResourcesDropdown(false)}
                  >
                    <FileText className="dropdown-item-icon" />
                    <div>
                      <div className="dropdown-item-title">Documentation & About</div>
                      <div className="dropdown-item-desc">Learn how Site Studio operates</div>
                    </div>
                  </Link>
                  <Link
                    href="/#features"
                    className="dropdown-menu-item"
                    onClick={() => setResourcesDropdown(false)}
                  >
                    <Sparkles className="dropdown-item-icon text-amber-400" />
                    <div>
                      <div className="dropdown-item-title">Platform Features</div>
                      <div className="dropdown-item-desc">Smart Fill, live canvas & export</div>
                    </div>
                  </Link>
                  <Link
                    href="/contact"
                    className="dropdown-menu-item"
                    onClick={() => setResourcesDropdown(false)}
                  >
                    <HelpCircle className="dropdown-item-icon text-cyan-400" />
                    <div>
                      <div className="dropdown-item-title">Help & Support</div>
                      <div className="dropdown-item-desc">Contact our community team</div>
                    </div>
                  </Link>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Pricing Link */}
          <Link
            href="/pricing"
            className={cn("nav-center-item", pathname === "/pricing" && "nav-item-active")}
          >
            <span>Pricing</span>
          </Link>
        </nav>

        {/* Right Actions */}
        <div className="navbar-actions">
          {/* Search Pill Input */}
          <form onSubmit={handleSearchSubmit} className="navbar-search-pill-form">
            <Search className="navbar-search-icon" />
            <input
              type="text"
              placeholder="Search templates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="navbar-search-pill-input"
            />
          </form>

          {/* Cart Icon (if items exist or buyer) */}
          {!isSeller && (
            <Link
              href="/checkout"
              className="navbar-cart-btn"
              aria-label={`Cart (${cartItems.length} items)`}
            >
              <ShoppingCart className="w-4 h-4 text-slate-300" />
              {cartItems.length > 0 && (
                <span className="cart-badge">
                  {cartItems.length}
                </span>
              )}
            </Link>
          )}

          {/* Theme Selector */}
          <ThemeToggle />

          {/* Sign In & Get Started Free or User Profile */}
          {isSignedIn ? (
            <div className="navbar-auth-group">
              <Link
                href="/dashboard"
                className="navbar-user-pill-link"
                title="Go to Dashboard"
              >
                <div className="navbar-avatar-circle">
                  {user?.avatar_url || user?.picture ? (
                    <img
                      src={user?.avatar_url || user?.picture}
                      alt=""
                      className="navbar-avatar-img"
                      onError={(e) => {
                        e.currentTarget.style.setProperty('display', 'none', 'important');
                        const fb = e.currentTarget.parentElement?.querySelector('.navbar-avatar-fallback');
                        if (fb) fb.style.setProperty('display', 'flex', 'important');
                      }}
                    />
                  ) : null}
                  <span
                    className="navbar-avatar-fallback"
                    style={{ display: (user?.avatar_url || user?.picture) ? "none" : "flex" }}
                  >
                    {(user?.name || user?.full_name || user?.email || "N")[0].toUpperCase()}
                  </span>
                </div>
                <div className="navbar-user-info-text">
                  <span className="navbar-user-display-name">
                    {user?.name || user?.full_name || (user?.email ? user.email.split("@")[0] : "Navin Bharath.N")}
                  </span>
                  <span className="navbar-user-role-label">
                    {user?.role === "seller" || user?.role === "SELLER" ? "Seller" : "Buyer"}
                  </span>
                </div>
              </Link>
              <button
                onClick={() => signOut()}
                className="btn-studio-logout"
                title="Log Out"
              >
                Log Out
              </button>
            </div>
          ) : (
            <div className="navbar-auth-group">
              <Link
                href="/sign-in"
                className="btn-studio-signin"
              >
                Sign In
              </Link>
              <Link
                href="/get-started"
                className="btn-studio-getstarted"
              >
                <span>Get Started Free</span>
                <ArrowRight className="w-3.5 h-3.5 ml-1" />
              </Link>
            </div>
          )}

          {/* Mobile menu toggle */}
          <button
            className="mobile-toggle"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? (
              <X className="w-5 h-5 text-white" />
            ) : (
              <Menu className="w-5 h-5 text-white" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="mobile-dropdown"
          >
            <div className="container-xl mobile-nav">
              {/* Mobile Search */}
              <form onSubmit={handleSearchSubmit} className="mobile-search-form">
                <Search className="w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search templates..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="mobile-search-input"
                />
              </form>

              <div className="mobile-links-container">
                <Link
                  href="/"
                  className={cn("mobile-link", pathname === "/" && "mobile-link-active")}
                  onClick={() => setMobileOpen(false)}
                >
                  Home
                </Link>
                <Link
                  href="/marketplace"
                  className={cn("mobile-link", pathname.startsWith("/marketplace") && "mobile-link-active")}
                  onClick={() => setMobileOpen(false)}
                >
                  Marketplace & Templates
                </Link>
                <Link
                  href="/pricing"
                  className="mobile-link"
                  onClick={() => setMobileOpen(false)}
                >
                  Pricing
                </Link>
                <Link
                  href="/about"
                  className="mobile-link"
                  onClick={() => setMobileOpen(false)}
                >
                  Resources & Docs
                </Link>
                <div className="mobile-theme-section py-2 px-1 flex items-center justify-between border-t border-b border-border my-2">
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Theme</span>
                  <ThemeToggle variant="pill" />
                </div>

                {isSignedIn ? (
                  <>
                    <Link href="/dashboard" className="mobile-link" onClick={() => setMobileOpen(false)}>
                      Dashboard
                    </Link>
                    <button
                      onClick={() => {
                        signOut();
                        setMobileOpen(false);
                      }}
                      className="mobile-link text-rose-400"
                      style={{ textAlign: "left", width: "100%", background: "none", border: "none" }}
                    >
                      Log Out
                    </button>
                  </>
                ) : (
                  <div className="mobile-auth-actions pt-2">
                    <Link
                      href="/sign-in"
                      className="btn-studio-signin w-full text-center mb-2"
                      onClick={() => setMobileOpen(false)}
                    >
                      Sign In
                    </Link>
                    <Link
                      href="/get-started"
                      className="btn-studio-getstarted w-full text-center justify-center"
                      onClick={() => setMobileOpen(false)}
                    >
                      <span>Get Started Free</span>
                      <ArrowRight className="w-3.5 h-3.5 ml-1" />
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

export default NavbarComponent;
