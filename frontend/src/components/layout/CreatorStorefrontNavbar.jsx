"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import Link from "@/components/Link";
import { useAppUser } from "@/lib/auth";
import { useAuthStore } from "@/store/authStore";
import {
  Store,
  ArrowLeft,
  UserCheck,
  Mail,
  ShoppingCart,
  User,
  LogOut,
  SlidersHorizontal,
  ChevronDown,
  Layers,
  Users,
} from "lucide-react";
import "./CreatorStorefrontNavbar.css";

export default function CreatorStorefrontNavbar({
  storefront,
  creatorSlug,
  cartItems = [],
  activeNav = "",
  onSelectTab = null,
}) {
  const { user, isSignedIn } = useAppUser();
  const signOut = useAuthStore((s) => s.signOut);
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef(null);

  const storeSlug = storefront?.store_slug || creatorSlug;
  const brandName = storefront?.brand_name || "Creator Storefront";
  const domainHost = typeof window !== "undefined" ? window.location.host : "aisitestudio.com";

  // Authoritative store owner detection
  const isOwner = Boolean(
    (user?.id && storefront?.user_id && user.id === storefront.user_id) ||
    (user?.email && storefront?.support_email && user.email.toLowerCase() === storefront.support_email.toLowerCase()) ||
    (user?.creator_store_slug && storeSlug && user.creator_store_slug.toLowerCase() === storeSlug.toLowerCase())
  );

  const handleSignOut = async () => {
    setProfileOpen(false);
    try {
      if (signOut) {
        await signOut();
      }
    } catch (e) {
      console.error("Sign out error", e);
    }
    // Clean reload to reset auth state
    window.location.reload();
  };

  const handleStorefrontClick = () => {
    setProfileOpen(false);
    if (onSelectTab) {
      onSelectTab("templates");
    }
  };

  // Close profile dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setProfileOpen(false);
      }
    }
    if (profileOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [profileOpen]);

  // Creator-scoped cart items count
  const creatorCartCount = useMemo(() => {
    if (!Array.isArray(cartItems)) return 0;
    if (!storeSlug) return cartItems.length;
    const scoped = cartItems.filter(
      (i) => !i.creator_slug || i.creator_slug.toLowerCase() === storeSlug.toLowerCase()
    );
    return scoped.length > 0 ? scoped.length : cartItems.length;
  }, [cartItems, storeSlug]);

  const handleNavClick = (tabKey) => {
    if (onSelectTab) {
      onSelectTab(tabKey);
    }
  };

  return (
    <header className="sf-navbar">
      <div className="sf-navbar-inner">
        {/* Creator Brand Identity */}
        <Link href={`/creator/${storeSlug}`} className="sf-nav-brand">
          <div className="sf-nav-logo-box">
            {storefront?.logo_url ? (
              <img
                src={storefront.logo_url}
                alt={brandName}
                className="sf-nav-logo-img"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
            ) : (
              <Store className="w-5 h-5 text-[#dfb180]" />
            )}
          </div>
          <div className="sf-nav-brand-text">
            <span className="sf-nav-brand-title">{brandName}</span>
            <span className="sf-nav-domain-label">
              {domainHost}/creator/{storeSlug}
            </span>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="sf-nav-links">
          {onSelectTab ? (
            <>
              <button
                type="button"
                onClick={() => handleNavClick("templates")}
                className={`sf-nav-link-btn ${activeNav === "templates" ? "active" : ""}`}
              >
                <span>Templates</span>
              </button>
              <button
                type="button"
                onClick={() => handleNavClick("about")}
                className={`sf-nav-link-btn ${activeNav === "about" ? "active" : ""}`}
              >
                <span>About</span>
              </button>
              <button
                type="button"
                onClick={() => handleNavClick("contact")}
                className={`sf-nav-link-btn ${activeNav === "contact" ? "active" : ""}`}
              >
                <span>Contact</span>
              </button>
              <button
                type="button"
                onClick={() => handleNavClick("payments")}
                className={`sf-nav-link-btn ${activeNav === "payments" ? "active" : ""}`}
              >
                <span>Payment Channels</span>
              </button>
              {isOwner && (
                <button
                  type="button"
                  onClick={() => handleNavClick("customers")}
                  className={`sf-nav-link-btn ${activeNav === "customers" ? "active" : ""}`}
                >
                  <span>Clients & Audience</span>
                </button>
              )}
            </>
          ) : (
            <>
              <Link href={`/creator/${storeSlug}`} className="sf-nav-link-btn active">
                <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
                <span>Back to {brandName}</span>
              </Link>
              <Link href={`/creator/${storeSlug}?tab=about`} className="sf-nav-link-btn">
                <span>About</span>
              </Link>
              <Link href={`/creator/${storeSlug}?tab=contact`} className="sf-nav-link-btn">
                <span>Contact</span>
              </Link>
            </>
          )}
        </nav>

        {/* Right Actions: Email, Cart, User Profile / Client Login */}
        <div className="sf-nav-actions">
          {storefront?.support_email && (
            <a
              href={`mailto:${storefront.support_email}`}
              className="sf-nav-email-pill"
              title={`Direct email to ${brandName}`}
            >
              <Mail className="w-3.5 h-3.5 text-[#dfb180]" />
              <span className="sf-nav-email-text">{storefront.support_email}</span>
            </a>
          )}

          {/* Whitelabeled Cart Button */}
          <Link
            href={`/creator/${storeSlug}/checkout`}
            className="sf-nav-cart-btn"
            title="View Creator Cart & Checkout"
          >
            <ShoppingCart className="w-4 h-4 text-zinc-300" />
            {creatorCartCount > 0 && <span className="sf-nav-cart-badge">{creatorCartCount}</span>}
          </Link>

          {/* Owner Manage Button */}
          {isOwner && (
            <Link to="/creator/setup" className="sf-nav-manage-btn" title="Edit Storefront Settings">
              <SlidersHorizontal className="w-3.5 h-3.5 text-[#dfb180]" />
              <span>Manage</span>
            </Link>
          )}

          {/* Client Authentication & Account Pill */}
          {isSignedIn && user ? (
            <div className="sf-nav-profile-wrapper" ref={profileRef}>
              <button
                type="button"
                onClick={() => setProfileOpen(!profileOpen)}
                className="sf-nav-user-pill flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.06] hover:bg-white/[0.1] border border-white/10 text-xs text-white transition-all cursor-pointer"
                aria-expanded={profileOpen}
              >
                <div className="w-6 h-6 rounded-full bg-[#dfb180]/20 text-[#dfb180] flex items-center justify-center font-bold text-[10px]">
                  {(user.first_name || user.email || "U").charAt(0).toUpperCase()}
                </div>
                <span className="max-w-[100px] truncate">{user.first_name || user.email?.split("@")[0]}</span>
                <ChevronDown className="w-3 h-3 text-zinc-400" />
              </button>

              {profileOpen && (
                <div className="sf-nav-profile-menu">
                  <div className="sf-nav-profile-header">
                    <p className="sf-nav-profile-email">{user.email}</p>
                    <p className="sf-nav-profile-brand">
                      {isOwner ? "Store Owner & Creator ✦" : `Client of ${brandName}`}
                    </p>
                  </div>
                  <div className="sf-nav-profile-body">
                    {isOwner ? (
                      <>
                        <Link
                          to="/creator/setup"
                          className="sf-nav-profile-link"
                          onClick={() => setProfileOpen(false)}
                        >
                          <SlidersHorizontal className="w-3.5 h-3.5 text-[#dfb180]" />
                          <span>Manage Storefront</span>
                        </Link>
                        {onSelectTab && (
                          <button
                            type="button"
                            onClick={() => {
                              setProfileOpen(false);
                              onSelectTab("customers");
                            }}
                            className="sf-nav-profile-link"
                          >
                            <Users className="w-3.5 h-3.5 text-[#dfb180]" />
                            <span>Clients &amp; Audience CRM</span>
                          </button>
                        )}
                        <Link
                          href={`/creator/${storeSlug}`}
                          className="sf-nav-profile-link"
                          onClick={handleStorefrontClick}
                        >
                          <Store className="w-3.5 h-3.5 text-zinc-400" />
                          <span>View Storefront</span>
                        </Link>
                      </>
                    ) : (
                      <>
                        <Link
                          href={`/creator/${storeSlug}/checkout`}
                          className="sf-nav-profile-link"
                          onClick={() => setProfileOpen(false)}
                        >
                          <ShoppingCart className="w-3.5 h-3.5 text-[#dfb180]" />
                          <span>My Cart &amp; Checkout</span>
                        </Link>
                        <Link
                          href={`/creator/${storeSlug}`}
                          className="sf-nav-profile-link"
                          onClick={handleStorefrontClick}
                        >
                          <Store className="w-3.5 h-3.5 text-zinc-400" />
                          <span>{brandName}&apos;s Storefront</span>
                        </Link>
                      </>
                    )}
                    <button
                      type="button"
                      onClick={handleSignOut}
                      className="sf-nav-profile-signout"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <Link
              href={`/creator/${storeSlug}/login`}
              className="sf-nav-login-btn inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[#dfb180]/15 hover:bg-[#dfb180]/25 text-[#dfb180] border border-[#dfb180]/30 text-xs font-semibold transition-all"
              title={`Sign in as a client of ${brandName}`}
            >
              <User className="w-3.5 h-3.5" />
              <span>Client Login</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
