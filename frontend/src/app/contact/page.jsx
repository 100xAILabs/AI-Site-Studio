import Navbar from "@/components/layout/Navbar";
import Link from "@/components/Link";
import { Mail, MessageSquare, MapPin, Sparkles, Send } from "lucide-react";
import "../Page.css"; // Imports footer and CTA styles from the homepage
import "./Page.css";  // Imports specific contact page layouts

export default function ContactPage() {
  const footerLinks = [
    {
      title: "Product",
      links: [
        { name: "Marketplace", path: "/marketplace" },
        { name: "Pricing", path: "/pricing" },
        { name: "Features", path: "/#features" }
      ]
    },
    {
      title: "Company",
      links: [
        { name: "About", path: "/about" },
        { name: "Contact", path: "/contact" }
      ]
    }
  ];

  return (
    <>
      <Navbar />
      
      <main className="contact-wrapper">
        {/* Decorative background glows */}
        <div className="contact-glow-orb-1" />
        <div className="contact-glow-orb-2" />

        <div className="container-xl">
          {/* Header Section */}
          <div className="contact-header">
            <div className="contact-badge">
              <Sparkles className="contact-badge-icon" />
              <span>Connect</span>
            </div>
            <h1 className="contact-title">
              Get in <span className="gradient-text">Touch</span>
            </h1>
            <p className="contact-subtitle">
              We're here to help you succeed. Reach out with any questions.
            </p>
          </div>

          {/* Grid Layout */}
          <div className="contact-layout-grid">
            
            {/* Quick Contact Info */}
            <div className="contact-side-info">
              <div className="contact-card glass">
                <div className="contact-icon-wrapper">
                  <Mail className="w-5 h-5" />
                </div>
                <div className="contact-card-info">
                  <h3 className="contact-card-title">Email Us</h3>
                  <p className="contact-card-desc">support@aisitestudio.com</p>
                </div>
              </div>

              <div className="contact-card glass">
                <div className="contact-icon-wrapper">
                  <MessageSquare className="w-5 h-5" />
                </div>
                <div className="contact-card-info">
                  <h3 className="contact-card-title">Live Chat</h3>
                  <p className="contact-card-desc">Available 9am - 5pm EST</p>
                </div>
              </div>

              <div className="contact-card glass">
                <div className="contact-icon-wrapper">
                  <MapPin className="w-5 h-5" />
                </div>
                <div className="contact-card-info">
                  <h3 className="contact-card-title">Office</h3>
                  <p className="contact-card-desc">San Francisco, CA</p>
                </div>
              </div>
            </div>

            {/* Messaging Form */}
            <div className="contact-form-box glass">
              <h2 className="contact-form-title">Send a Message</h2>
              <form className="contact-form" onSubmit={(e) => e.preventDefault()}>
                <div className="contact-form-row">
                  <input type="text" placeholder="First Name" className="contact-input" required />
                  <input type="text" placeholder="Last Name" className="contact-input" required />
                </div>
                <input type="email" placeholder="Email Address" className="contact-input" required />
                <textarea placeholder="How can we help?" rows="4" className="contact-input contact-textarea" required></textarea>
                <button type="submit" className="contact-submit-btn">
                  Send Message <Send className="w-4 h-4" />
                </button>
              </form>
            </div>

          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="footer-wrap">
        <div className="container-xl footer-container">
          <div className="footer-grid">
            <div className="footer-brand-col">
              <Link href="/" className="footer-brand-logo-link">
                <img
                  src="/logo.png"
                  alt="Site Studio Logo"
                  className="navbar-logo-img"
                  width={32}
                  height={32}
                />
                <span className="font-bold text-lg gradient-text">Site Studio</span>
              </Link>
              <p className="text-sm text-muted-foreground leading-relaxed max-w-xs">
                The next-generation website template marketplace. Build stunning websites in minutes, not months.
              </p>
              <div className="footer-social-row">
                <a href="#" className="footer-social-btn" aria-label="GitHub">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.579.688.481C19.137 20.164 22 16.418 22 12c0-5.523-4.477-10-10-10z" /></svg>
                </a>
                <a href="#" className="footer-social-btn" aria-label="Twitter">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg>
                </a>
                <a href="#" className="footer-social-btn" aria-label="LinkedIn">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" /></svg>
                </a>
              </div>
            </div>
            {footerLinks.map(({ title, links }) => (
              <div key={title}>
                <h4 className="footer-col-title">{title}</h4>
                <ul className="footer-links-list">
                  {links.map((l) => (
                    <li key={l.name}>
                      <Link href={l.path} className="footer-link-item">
                        {l.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="footer-bottom">
            <p>&copy; {new Date().getFullYear()} Site Studio. All rights reserved.</p>
            <p>Made with ❤️ for creators and developers</p>
          </div>
        </div>
      </footer>
    </>
  );
}
