"use client";

/**
 * Navbar — glassmorphic sticky header with search, theme toggle, cart, and auth (React JSX).
 */

import { useState, useEffect } from "react";
import Link from "@/components/Link";
const usePathname = () => window.location.pathname;
import { useTheme } from "@/hooks/useTheme";
import { AppSignInButton, AppSignUpButton, AppUserButton, useAppUser, useSignOut } from "@/lib/auth";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Sun,
  Moon,
  ShoppingCart,
  Menu,
  X,
  Sparkles,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCartStore } from "@/store";
import "./Navbar.css";


function NavbarComponent() {
  const { theme, setTheme } = useTheme();
  const { isSignedIn, user } = useAppUser();
  const signOut = useSignOut();
  const pathname = usePathname();
  const cartItems = useCartStore((s) => s.items);
  const [scrolled, setScrolled] = useState(false);

  const isSeller = isSignedIn && (user?.role === "seller" || user?.role === "SELLER");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={cn(
        "navbar-header",
        scrolled && "scrolled"
      )}
    >
      <div className="container-xl navbar-inner">
        {/* Left group: Logo + primary nav links */}
        <div className="navbar-left-group">
          <Link href="/" className="logo-container">
            <img
              src="/logo.png"
              alt="AI Site Studio Logo"
              className="navbar-logo-img"
              width={36}
              height={36}
            />
            <span className="logo-text gradient-text">
              AI Site Studio
            </span>
          </Link>

          {/* Primary nav links — left side, with active state */}
          <nav className="navbar-left-nav">
            <Link
              href="/"
              className={cn("nav-link-left", pathname === "/" && "nav-link-active")}
            >
              Home
            </Link>
            <Link
              href="/marketplace"
              className={cn("nav-link-left", (pathname === "/marketplace" || pathname.startsWith("/marketplace")) && "nav-link-active")}
            >
              Marketplace
            </Link>
          </nav>
        </div>



        {/* Right Actions */}
        <div className="navbar-actions">
          {/* Pricing */}
          <Link
            href="/pricing"
            className="search-btn"
          >
            Pricing
          </Link>

          {/* Search — icon only, links to marketplace */}
          <Link
            href="/marketplace"
            className="icon-btn"
            aria-label="Search templates"
            title="Search templates"
          >
            <Search className="w-4 h-4" />
          </Link>



          {/* Cart */}
          {!isSeller && (
            <Link
              href="/checkout"
              className="icon-btn cart-btn-link"
              aria-label={`Cart (${cartItems.length} items)`}
            >
              <ShoppingCart className="w-4 h-4" />
              {cartItems.length > 0 && (
                <span className="cart-badge">
                  {cartItems.length}
                </span>
              )}
            </Link>
          )}

          {/* Auth */}
          {isSignedIn ? (
            <>
              <Link
                href="/dashboard"
                className="search-btn"
              >
                Dashboard
              </Link>
              <button
                onClick={() => signOut()}
                className="btn-signin"
                style={{ marginLeft: "0.5rem", padding: "0.4rem 1rem", fontSize: "0.8rem", height: "36px", display: "inline-flex", alignItems: "center" }}
              >
                Log Out
              </button>
            </>
          ) : (
            <div className="desktop-auth">
              <Link
                href="/sign-in"
                className="btn-signin"
              >
                Sign In
              </Link>
              <Link
                href="/get-started"
                className="btn-getstarted"
              >
                Get Started
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
              <X className="w-5 h-5" />
            ) : (
              <Menu className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="mobile-dropdown"
          >
            <nav className="container-xl mobile-nav">
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
                  Marketplace
                </Link>
                <Link
                  href="/pricing"
                  className="mobile-link"
                  onClick={() => setMobileOpen(false)}
                >
                  Pricing
                </Link>
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
                      className="mobile-link"
                      style={{ textAlign: "left", width: "100%", background: "none", border: "none" }}
                    >
                      Log Out
                    </button>
                  </>
                ) : (
                  <>
                    <Link
                      href="/sign-in"
                      className="mobile-link-signin"
                      onClick={() => setMobileOpen(false)}
                    >
                      Sign In
                    </Link>
                    <Link
                      href="/get-started"
                      className="mobile-link-getstarted"
                      onClick={() => setMobileOpen(false)}
                    >
                      Get Started Free
                    </Link>
                  </>
                )}
              </div>

            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

export default NavbarComponent;
