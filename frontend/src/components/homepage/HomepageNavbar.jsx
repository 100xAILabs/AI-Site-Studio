import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BriefcaseBusiness,
  ChevronDown,
  FileText,
  HelpCircle,
  Layers3,
  Menu,
  Search,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import Link from "@/components/Link";
import { useAppUser, useSignOut } from "@/lib/auth";
import { useCartStore } from "@/store";
import ThemeToggle from "@/components/layout/ThemeToggle";
import styles from "./HomepageNavbar.module.css";

const TEMPLATE_LINKS = [
  { label: "All Templates", description: "Browse the full collection", href: "/marketplace", icon: Layers3 },
  { label: "AI & SaaS", description: "Software and technology", href: "/marketplace?category=saas-technology", icon: Zap },
  { label: "E-commerce", description: "Retail and online stores", href: "/marketplace?category=ecommerce", icon: ShoppingBag },
  { label: "Business", description: "Corporate and agency sites", href: "/marketplace?category=business", icon: BriefcaseBusiness },
];

const RESOURCE_LINKS = [
  { label: "About Site Studio", description: "Learn about the platform", href: "/about", icon: FileText },
  { label: "Platform features", description: "Explore the creative toolkit", href: "/#features", icon: Sparkles },
  { label: "Help & support", description: "Get in touch with our team", href: "/contact", icon: HelpCircle },
];

function BrandMark() {
  return (
    <svg className={styles.logoMark} viewBox="0 0 36 36" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="homepage-studio-logo-a" x1="6" y1="30" x2="29" y2="4" gradientUnits="userSpaceOnUse">
          <stop stopColor="#8B5CF6" />
          <stop offset="1" stopColor="#C4B5FD" />
        </linearGradient>
      </defs>
      <path d="M23.8 4.2C25.4 2.6 28 2.6 29.6 4.2C31.2 5.8 31.2 8.4 29.6 10L14.4 25.2C12.8 26.8 10.2 26.8 8.6 25.2C7 23.6 7 21 8.6 19.4L23.8 4.2Z" fill="url(#homepage-studio-logo-a)" />
      <path d="M19.2 12.8C20.8 11.2 23.4 11.2 25 12.8C26.6 14.4 26.6 17 25 18.6L13.8 29.8C12.2 31.4 9.6 31.4 8 29.8C6.4 28.2 6.4 25.6 8 24L19.2 12.8Z" fill="#6D28D9" />
    </svg>
  );
}

export default function HomepageNavbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isSignedIn } = useAppUser();
  const signOut = useSignOut();
  const cartItems = useCartStore((state) => state.items);
  const [query, setQuery] = useState("");
  const [activeMenu, setActiveMenu] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const navRef = useRef(null);

  const isExtreme = Boolean(
    user?.can_retail_templates ||
    user?.is_extreme_subscriber ||
    ["extreme", "agency", "enterprise"].includes(String(user?.subscription_tier || "").toLowerCase()) ||
    ["admin", "super_admin"].includes(user?.role)
  );
  const creatorHref = isExtreme
    ? user?.is_creator_onboarding_completed
      ? "/dashboard?tab=creator-studio"
      : "/creator/setup"
    : "/creator/setup";
  const displayName = user?.name || user?.full_name || user?.email?.split("@")[0] || "Account";
  const cartCount = cartItems.reduce((count, item) => count + Math.max(1, Number(item.quantity) || 1), 0);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 12);
    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    setActiveMenu(null);
    setMobileOpen(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    const handlePointerDown = (event) => {
      if (navRef.current && !navRef.current.contains(event.target)) setActiveMenu(null);
    };
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setActiveMenu(null);
        setMobileOpen(false);
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const handleSearch = (event) => {
    event.preventDefault();
    const clean = query.trim();
    navigate(clean ? `/marketplace?q=${encodeURIComponent(clean)}` : "/marketplace");
    setMobileOpen(false);
  };

  const toggleMenu = (name) => setActiveMenu((current) => current === name ? null : name);

  const renderDropdown = (name, items) => (
    <AnimatePresence>
      {activeMenu === name && (
        <motion.div
          className={styles.dropdown}
          initial={{ opacity: 0, y: 8, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 6, scale: 0.98 }}
          transition={{ duration: 0.16 }}
          id={`homepage-${name}-menu`}
        >
          {items.map(({ label, description, href, icon: Icon }) => (
            <Link key={href} href={href} className={styles.dropdownItem} onClick={() => setActiveMenu(null)}>
              <span className={styles.dropdownIcon}><Icon size={17} aria-hidden="true" /></span>
              <span className={styles.dropdownCopy}>
                <span className={styles.dropdownTitle}>{label}</span>
                <span className={styles.dropdownDescription}>{description}</span>
              </span>
            </Link>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );

  const renderNavMenu = (name, label, items) => (
    <div className={styles.navMenu}>
      <button
        type="button"
        className={styles.navItem}
        aria-haspopup="true"
        aria-expanded={activeMenu === name}
        aria-controls={`homepage-${name}-menu`}
        onClick={() => toggleMenu(name)}
      >
        {label}<ChevronDown size={14} className={activeMenu === name ? styles.chevronOpen : ""} aria-hidden="true" />
      </button>
      {renderDropdown(name, items)}
    </div>
  );

  return (
    <header className={`${styles.header} ${scrolled ? styles.headerScrolled : ""}`} ref={navRef}>
      <div className={styles.navShell}>
        <Link href="/" className={styles.brand} aria-label="Site Studio home">
          <BrandMark />
          <span>Site Studio</span>
        </Link>

        <nav className={styles.desktopNav} aria-label="Main navigation">
          {renderNavMenu("templates", "Templates", TEMPLATE_LINKS)}
          <Link href="/marketplace" className={styles.navItem}>Marketplace</Link>
          {renderNavMenu("resources", "Resources", RESOURCE_LINKS)}
          <Link href="/pricing" className={styles.navItem}>Pricing</Link>
        </nav>

        <div className={styles.actions}>
          <form className={styles.searchForm} onSubmit={handleSearch} role="search">
            <Search size={17} aria-hidden="true" />
            <input
              aria-label="Search templates"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search templates..."
            />
          </form>
          <Link href="/checkout" className={styles.iconButton} aria-label={`Shopping cart, ${cartCount} items`}>
            <ShoppingCart size={18} aria-hidden="true" />
            {cartCount > 0 && <span className={styles.cartCount}>{cartCount > 99 ? "99+" : cartCount}</span>}
          </Link>
          <ThemeToggle />

          {isSignedIn ? (
            <>
              <Link href={creatorHref} className={styles.creatorLink} title="Open creator studio">
                <ShoppingBag size={15} aria-hidden="true" />
                <span>Creator</span>
              </Link>
              <Link href="/dashboard" className={styles.profile} title="Open your dashboard">
                <span className={styles.avatar}>
                  {user?.avatar_url || user?.picture
                    ? <img src={user.avatar_url || user.picture} alt="" onError={(event) => { event.currentTarget.hidden = true; }} />
                    : displayName.slice(0, 1).toUpperCase()}
                </span>
                <span className={styles.profileName}>{displayName}</span>
              </Link>
              <button type="button" className={styles.logoutButton} onClick={() => signOut()}>Log Out</button>
            </>
          ) : (
            <div className={styles.authActions}>
              <Link href="/sign-in" className={styles.signInLink}>Sign In</Link>
              <Link href="/get-started" className={styles.getStartedLink}>Get Started <ArrowRight size={14} /></Link>
            </div>
          )}

          <button
            type="button"
            className={styles.mobileToggle}
            aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((open) => !open)}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className={styles.mobilePanel}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.16 }}
          >
            <form className={styles.mobileSearch} onSubmit={handleSearch} role="search">
              <Search size={17} aria-hidden="true" />
              <input aria-label="Search templates" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search templates..." />
            </form>
            <Link href="/marketplace" className={styles.mobileLink}>Marketplace</Link>
            <Link href="/pricing" className={styles.mobileLink}>Pricing</Link>
            <div className={styles.mobileGroupLabel}>Templates</div>
            {TEMPLATE_LINKS.map((item) => <Link key={item.href} href={item.href} className={styles.mobileSubLink}>{item.label}</Link>)}
            <div className={styles.mobileGroupLabel}>Resources</div>
            {RESOURCE_LINKS.map((item) => <Link key={item.href} href={item.href} className={styles.mobileSubLink}>{item.label}</Link>)}
            {isSignedIn ? (
              <>
                <Link href="/dashboard" className={styles.mobileLink}>My Dashboard</Link>
                <Link href={creatorHref} className={styles.mobileLink}>Creator Studio</Link>
                <button type="button" className={styles.mobileLogout} onClick={() => signOut()}>Log Out</button>
              </>
            ) : (
              <div className={styles.mobileAuth}>
                <Link href="/sign-in" className={styles.mobileLink}>Sign In</Link>
                <Link href="/get-started" className={styles.mobileGetStarted}>Get Started <ArrowRight size={14} /></Link>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
