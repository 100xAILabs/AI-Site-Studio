import { SignUp } from "@clerk/clerk-react";
import Link from "@/components/Link";
import { Sparkles } from "lucide-react";
import "./Page.css";

export default function SignUpPage() {
  return (
    <div className="signup-page-wrapper">
      {/* Glow Effects */}
      <div className="signup-glow-top" />
      <div className="signup-glow-bottom" />

      <div className="signup-content-container">
        <div className="signup-header">
          <Link href="/" className="signup-logo-link">
            <img src="/logo.png" alt="Site Studio Logo" className="navbar-logo-img" width={32} height={32} />
            <span className="signup-logo-text gradient-text">
              Site Studio
            </span>
          </Link>
          <h2 className="signup-title">Create your account</h2>
          <p className="signup-subtitle">Start building and customizing your dream site today</p>
        </div>

        <div className="signup-form-wrapper">
          <SignUp
            appearance={{
              elements: {
                card: "glass border border-border/40 shadow-glow-sm rounded-2xl",
                headerTitle: "hidden",
                headerSubtitle: "hidden",
                socialButtonsBlockButton: "glass border border-border/50 text-foreground hover:bg-muted/30 transition-colors",
                formButtonPrimary: "bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl font-semibold btn-glow",
                formFieldInput: "glass border border-border/50 text-foreground focus:border-primary/50 rounded-xl",
                footerActionLink: "text-primary hover:text-primary/90",
              },
            }}
            path="/sign-up"
            routing="path"
            signInUrl="/sign-in"
          />
        </div>
      </div>
    </div>
  );
}
