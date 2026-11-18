"use client";

import { Link } from "react-router-dom";
import { Sparkles, Globe, Heart, Shield, Terminal } from "lucide-react";
import "./Footer.css";

const FOOTER_SECTIONS = [
  {
    title: "Marketplace",
    links: [
      { name: "Explore All Templates", path: "/marketplace" },
      { name: "React & Next.js", path: "/marketplace?framework=nextjs" },
      { name: "Vue & Nuxt", path: "/marketplace?framework=vue" },
      { name: "Svelte", path: "/marketplace?framework=svelte" },
      { name: "HTML5 & Tailwind", path: "/marketplace?framework=html" },
    ],
  },
  {
    title: "AI Studio & Creation",
    links: [
      { name: "AI Site Studio", path: "/studio" },
      { name: "Launch AI Project", path: "/studio/launch" },
      { name: "Live Preview Runner", path: "/preview" },
      { name: "Extreme Creator Portal", path: "/creator/setup" },
      { name: "Sell Templates", path: "/creator/setup" },
    ],
  },
  {
    title: "Company & Legal",
    links: [
      { name: "About Us", path: "/about" },
      { name: "Contact & Support", path: "/contact" },
      { name: "Pricing & Plans", path: "/pricing" },
      { name: "Privacy Policy", path: "/privacy" },
      { name: "Terms of Service", path: "/terms" },
    ],
  },
];

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="global-footer">
      <div className="global-footer-container">
        <div className="global-footer-top">
          {/* Brand Info */}
          <div className="global-footer-brand">
            <Link to="/" className="global-footer-logo">
              <div className="global-footer-logo-icon">
                <Sparkles className="w-5 h-5 text-[#dfb180]" />
              </div>
              <span className="global-footer-logo-text">AI Site Studio</span>
            </Link>
            <p className="global-footer-tagline">
              The premier AI website generator and production template marketplace. Discover,
              customize in real-time, or launch your own branded storefront on our domain.
            </p>
            <div className="global-footer-badges">
              <div className="global-footer-badge">
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                <span>Verified Code</span>
              </div>
              <div className="global-footer-badge">
                <Globe className="w-3.5 h-3.5 text-blue-400" />
                <span>Multi-Gateway Payouts</span>
              </div>
            </div>
          </div>

          {/* Links Columns */}
          <div className="global-footer-links-grid">
            {FOOTER_SECTIONS.map((section) => (
              <div key={section.title} className="global-footer-col">
                <h4 className="global-footer-col-title">{section.title}</h4>
                <ul className="global-footer-list">
                  {section.links.map((link) => (
                    <li key={link.name}>
                      <Link to={link.path} className="global-footer-link">
                        {link.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="global-footer-bottom">
          <p className="global-footer-copy">
            &copy; {currentYear} AI Site Studio Inc. All rights reserved.
          </p>
          <div className="global-footer-bottom-links">
            <Link to="/privacy" className="global-footer-sublink">
              Privacy
            </Link>
            <span className="global-footer-dot">•</span>
            <Link to="/terms" className="global-footer-sublink">
              Terms
            </Link>
            <span className="global-footer-dot">•</span>
            <Link to="/creator/setup" className="global-footer-sublink">
              Creator Program
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
