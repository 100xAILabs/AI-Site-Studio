"use client";

/**
 * SidebarFilters — collapsible filter cards for marketplace (React JSX).
 */

import { useState } from "react";
import { ChevronDown, ChevronUp, X, SlidersHorizontal } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { useFilterStore } from "@/store";
import "./SidebarFilters.css";

/* ─────────────────────────────────────────────────────────────
   Collapsible section wrapper
───────────────────────────────────────────────────────────── */
function FilterSection({ title, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="filter-section">
      <button onClick={() => setOpen(!open)} className="filter-toggle-btn">
        {title}
        {open
          ? <ChevronUp className="filter-toggle-icon" />
          : <ChevronDown className="filter-toggle-icon" />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="filter-collapsible-wrapper"
          >
            <div className="filter-collapsible-content">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   Single checkbox row
───────────────────────────────────────────────────────────── */
function CheckboxOption({ label, count, checked, onChange }) {
  return (
    <label className="checkbox-option">
      <div className="checkbox-content-wrapper">
        <div
          className={cn("checkbox-indicator", checked && "checked")}
          onClick={() => onChange(!checked)}
        >
          {checked && (
            <svg className="check-svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>
        <span className="checkbox-label">{label}</span>
      </div>
      {count !== undefined && (
        <span className="checkbox-count">{count}</span>
      )}
    </label>
  );
}

/* ─────────────────────────────────────────────────────────────
   Data
───────────────────────────────────────────────────────────── */
const MAIN_CATEGORIES = [
  { label: "Business",          value: "business" },
  { label: "SaaS & Technology", value: "saas-technology" },
  { label: "Ecommerce",         value: "ecommerce" },
  { label: "Restaurant & Food", value: "restaurant-food" },
  { label: "Healthcare",        value: "healthcare" },
  { label: "Education",         value: "education" },
  { label: "Real Estate",       value: "real-estate" },
  { label: "Portfolio",         value: "portfolio" },
  { label: "Creative Agency",   value: "creative-agency" },
  { label: "Events",            value: "events" },
  { label: "Travel",            value: "travel" },
  { label: "Fitness",           value: "fitness" },
  { label: "Beauty",            value: "beauty" },
  { label: "Legal",             value: "legal" },
  { label: "NGO & Charity",     value: "ngo-charity" },
  { label: "Automotive",        value: "automotive" },
  { label: "Blog & Magazine",   value: "blog-magazine" },
  { label: "Gaming",            value: "gaming" },
  { label: "Finance",           value: "finance" },
  { label: "Entertainment",     value: "entertainment" },
  { label: "Landing Pages",     value: "landing-pages" },
  { label: "Dashboard",         value: "dashboards" },
  { label: "Documentation",     value: "documentation" },
  { label: "Authentication",    value: "authentication" },
  { label: "Marketplace",       value: "marketplace" },
];

const SUB_CATEGORIES = {
  business:         ["Corporate", "Startup", "Small Business", "Enterprise", "Consulting", "Finance", "Insurance", "Accounting", "Manufacturing", "Logistics"],
  "saas-technology":["SaaS", "AI Startup", "Software", "Mobile App", "Web App", "Cyber Security", "Cloud Computing", "Data Analytics", "CRM", "DevOps"],
  ecommerce:        ["Fashion", "Electronics", "Furniture", "Jewelry", "Beauty", "Grocery", "Pet Store", "Book Store", "Sports", "Digital Products", "Multi Vendor"],
  "restaurant-food":["Restaurant", "Cafe", "Bakery", "Fast Food", "Hotel", "Food Delivery", "Catering", "Cloud Kitchen", "Ice Cream", "Juice Bar"],
  healthcare:       ["Hospital", "Clinic", "Dentist", "Pharmacy", "Medical Lab", "Veterinary", "Mental Health", "Physiotherapy", "Eye Clinic", "Nursing Home"],
  education:        ["School", "College", "University", "Online Courses", "Coaching Center", "LMS", "Kindergarten", "Library", "Tuition", "E-learning"],
  "real-estate":    ["Property Listing", "Builder", "Interior Design", "Architecture", "Home Rental", "Apartment", "Commercial Property", "Villa", "Construction"],
  portfolio:        ["Designer", "Developer", "Photographer", "Artist", "Freelancer", "Writer", "Musician", "Architect", "Videographer", "Fashion Designer"],
  "creative-agency":["Marketing Agency", "Digital Agency", "Branding", "SEO Agency", "Advertising", "UI/UX Studio", "Creative Studio", "PR Agency"],
  events:           ["Wedding", "Conference", "Event Planner", "Exhibition", "Music Festival", "Birthday", "Corporate Event", "Meetup"],
  travel:           ["Tour Agency", "Hotel Booking", "Resort", "Travel Blog", "Visa Agency", "Adventure", "Car Rental", "Airline"],
  fitness:          ["Gym", "Yoga", "Personal Trainer", "CrossFit", "Nutrition", "Sports Club", "Martial Arts", "Dance Studio"],
  beauty:           ["Salon", "Spa", "Makeup Artist", "Skincare", "Barber Shop", "Cosmetics", "Nail Studio"],
  finance:          ["Banking", "Investment", "Cryptocurrency", "Trading", "FinTech", "Loan Company"],
  legal:            ["Lawyer", "Law Firm", "Legal Consultant", "Notary", "Immigration", "Tax Consultant"],
  "blog-magazine":  ["Personal Blog", "Technology", "Lifestyle", "Travel", "Food", "News", "Fashion", "Sports", "Magazine"],
  automotive:       ["Car Dealer", "Bike Dealer", "Auto Service", "Garage", "Car Rental", "EV Company"],
  "ngo-charity":    ["Charity", "Foundation", "Community", "Volunteer", "Donations", "Religious Organization"],
  "landing-pages":  ["Product Launch", "Startup", "App Landing", "Webinar", "Coming Soon", "Waitlist", "Lead Generation"],
  dashboards:       ["Admin Dashboard", "CRM Dashboard", "Analytics Dashboard", "Ecommerce Dashboard", "Finance Dashboard", "HR Dashboard", "LMS Dashboard"],
  gaming:           ["eSports", "Gaming Community", "Game Studio", "Streamer", "Gaming Shop"],
  entertainment:    ["Music", "Movies", "Podcast", "Streaming", "TV Show", "Celebrity"],
  marketplace:      ["Digital Products", "Multi Vendor", "Auctions", "Freelance Marketplace", "Job Board"],
  authentication:   ["Login", "Register", "Forgot Password", "OTP", "Multi-factor Authentication"],
  documentation:    ["API Docs", "Product Docs", "Knowledge Base", "Help Center", "Wiki"],
};

const DESIGN_STYLES = [
  { label: "Modern",          value: "modern" },
  { label: "Minimal",         value: "minimal" },
  { label: "Premium",         value: "premium" },
  { label: "Luxury",          value: "luxury" },
  { label: "Elegant",         value: "elegant" },
  { label: "Professional",    value: "professional" },
  { label: "Creative",        value: "creative" },
  { label: "Dark",            value: "dark" },
  { label: "Light",           value: "light" },
  { label: "Glassmorphism",   value: "glassmorphism" },
  { label: "Neumorphism",     value: "neumorphism" },
  { label: "Material Design", value: "material-design" },
  { label: "Flat Design",     value: "flat-design" },
  { label: "Gradient",        value: "gradient" },
  { label: "Futuristic",      value: "futuristic" },
  { label: "Brutalist",       value: "brutalist" },
  { label: "Retro",           value: "retro" },
  { label: "Corporate",       value: "corporate" },
  { label: "Vibrant",         value: "vibrant" },
];

const TECHNOLOGIES = [
  { label: "HTML",         value: "html" },
  { label: "React",        value: "react" },
  { label: "Next.js",      value: "nextjs" },
  { label: "Vue",          value: "vue" },
  { label: "Angular",      value: "angular" },
  { label: "Svelte",       value: "svelte" },
  { label: "Nuxt",         value: "nuxt" },
  { label: "Astro",        value: "astro" },
  { label: "Tailwind CSS", value: "tailwind" },
  { label: "Bootstrap",    value: "bootstrap" },
  { label: "Material UI",  value: "material-ui" },
  { label: "Shadcn UI",    value: "shadcn" },
  { label: "Chakra UI",    value: "chakra" },
];




const SALES_TIERS = [
  { label: "No sales",   value: "no-sales" },
  { label: "Low",        value: "low" },
  { label: "Medium",     value: "medium" },
  { label: "High",       value: "high" },
  { label: "Top seller", value: "top-seller" },
];

const DATE_RANGES = [
  { label: "Last 24 Hours", value: "last-24h" },
  { label: "Last Week",     value: "last-week" },
  { label: "Last Month",    value: "last-month" },
  { label: "Last Year",     value: "last-year" },
];

/* ─────────────────────────────────────────────────────────────
   Main component
───────────────────────────────────────────────────────────── */
export default function SidebarFilters({ categories }) {
  const { filters, setFilter, resetFilters, isFilterActive } = useFilterStore();
  const [expandedCategory, setExpandedCategory] = useState(null);
  const active = isFilterActive();

  /* Toggle main category selection + expand its sub-list */
  const handleCategoryClick = (value) => {
    if (expandedCategory === value) {
      // collapse — but keep the category filter active if sub is selected
      setExpandedCategory(null);
    } else {
      setExpandedCategory(value);
      // selecting a new parent resets sub_category
      if (filters.category !== value) {
        setFilter("category", value);
        setFilter("sub_category", undefined);
      }
    }
  };

  const handleSubCategoryClick = (sub) => {
    const slug = sub.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    setFilter("sub_category", filters.sub_category === slug ? undefined : slug);
  };

  // Always use static categories (API categories are ignored)

  return (
    <aside className="sidebar-filters-aside">
      {/* ── Header ─────────────────────────────────── */}
      <div className="filters-header">
        <div className="filters-header-title">
          <SlidersHorizontal className="filters-sliders-icon" />
          <span className="filters-header-text">Filters</span>
          {active && <span className="filters-active-badge">!</span>}
        </div>
        {active && (
          <button onClick={resetFilters} className="filters-clear-btn">
            <X className="filters-clear-icon" /> Clear all
          </button>
        )}
      </div>

      <div className="filters-sections-container">

        {/* ── Category ──────────────────────────────── */}
        <FilterSection title="Category">
          <div className="filters-options-container">
            {MAIN_CATEGORIES.map((cat) => (
              <div key={cat.value} className="category-row-wrapper">
                <button
                  className={cn(
                    "category-row-btn",
                    filters.category === cat.value && "category-row-selected",
                    expandedCategory === cat.value && "category-row-expanded"
                  )}
                  onClick={() => handleCategoryClick(cat.value)}
                >
                  <span className="category-row-label">{cat.label}</span>
                  <ChevronDown
                    className={cn(
                      "category-row-chevron",
                      expandedCategory === cat.value && "rotated"
                    )}
                  />
                </button>

                <AnimatePresence>
                  {expandedCategory === cat.value && SUB_CATEGORIES[cat.value] && (
                    <motion.div
                      key="subs"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2, ease: "easeInOut" }}
                      className="sub-categories-wrapper"
                    >
                      {SUB_CATEGORIES[cat.value].map((sub) => {
                        const slug = sub.toLowerCase().replace(/[^a-z0-9]+/g, "-");
                        return (
                          <button
                            key={sub}
                            className={cn(
                              "sub-category-btn",
                              filters.sub_category === slug && "sub-category-selected"
                            )}
                            onClick={() => handleSubCategoryClick(sub)}
                          >
                            {sub}
                          </button>
                        );
                      })}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>
        </FilterSection>

        {/* ── Design Style ──────────────────────────── */}
        <FilterSection title="Design Style" defaultOpen={false}>
          <div className="filters-options-container">
            {DESIGN_STYLES.map((style) => (
              <CheckboxOption
                key={style.value}
                label={style.label}
                checked={filters.design_style === style.value}
                onChange={(v) => setFilter("design_style", v ? style.value : undefined)}
              />
            ))}
          </div>
        </FilterSection>

        {/* ── Technology ────────────────────────────── */}
        <FilterSection title="Technology" defaultOpen={false}>
          <div className="filters-options-container">
            {TECHNOLOGIES.map((tech) => (
              <CheckboxOption
                key={tech.value}
                label={tech.label}
                checked={filters.technology === tech.value}
                onChange={(v) => setFilter("technology", v ? tech.value : undefined)}
              />
            ))}
          </div>
        </FilterSection>



        {/* ── Price ─────────────────────────────────── */}
        <FilterSection title="Price">
          <div className="price-range-inputs">
            <div className="price-input-wrapper">
              <span className="price-currency-symbol">$</span>
              <input
                type="number"
                placeholder="Min"
                min="0"
                value={filters.min_price ?? ""}
                onChange={(e) => {
                  const val = e.target.value;
                  setFilter("min_price", val !== "" ? Number(val) : undefined);
                }}
                className="price-num-input"
              />
            </div>
            <span className="price-range-separator">to</span>
            <div className="price-input-wrapper">
              <span className="price-currency-symbol">$</span>
              <input
                type="number"
                placeholder="Max"
                min="0"
                value={filters.max_price ?? ""}
                onChange={(e) => {
                  const val = e.target.value;
                  setFilter("max_price", val !== "" ? Number(val) : undefined);
                }}
                className="price-num-input"
              />
            </div>
          </div>
        </FilterSection>

        {/* ── On Sale & Sales ───────────────────────── */}
        <FilterSection title="On Sale & Sales">
          <div className="filters-options-container">
            <CheckboxOption
              label="On Sale"
              checked={!!filters.is_on_sale}
              onChange={(v) => setFilter("is_on_sale", v || undefined)}
            />
            <div className="sales-separator-line" />
            {SALES_TIERS.map((tier) => (
              <CheckboxOption
                key={tier.value}
                label={tier.label}
                checked={filters.sales === tier.value}
                onChange={(v) => setFilter("sales", v ? tier.value : undefined)}
              />
            ))}
          </div>
        </FilterSection>

        {/* ── Rating ────────────────────────────────── */}
        <FilterSection title="Rating">
          <div className="filters-options-container">
            {[5, 4, 3].map((r) => (
              <CheckboxOption
                key={r}
                label={`${r}+ Stars`}
                checked={filters.rating === r}
                onChange={(v) => setFilter("rating", v ? r : undefined)}
              />
            ))}
          </div>
        </FilterSection>

        {/* ── Date Added ────────────────────────────── */}
        <FilterSection title="Date Added">
          <div className="filters-options-container">
            {DATE_RANGES.map((range) => (
              <CheckboxOption
                key={range.value}
                label={range.label}
                checked={filters.date_added === range.value}
                onChange={(v) => setFilter("date_added", v ? range.value : undefined)}
              />
            ))}
          </div>
        </FilterSection>

      </div>
    </aside>
  );
}
