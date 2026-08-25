import { SignIn } from "@clerk/clerk-react";
import Link from "@/components/Link";
import { Sparkles } from "lucide-react";
import "./Page.css";

export default function SignInPage() {
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
          <h2 className="signup-title">Welcome back</h2>
          <p className="signup-subtitle">Sign in to manage your templates and previews</p>
        </div>

        <div className="signup-form-wrapper">
          <SignIn
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
            path="/sign-in"
            routing="path"
            signUpUrl="/sign-up"
          />
        </div>
      </div>
    </div>
  );
}
