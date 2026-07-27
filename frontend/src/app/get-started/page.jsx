import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  ShoppingBag,
  Upload,
  Sparkles,
  CheckCircle2,
  X,
} from "lucide-react";
import { useAppUser } from "@/lib/auth";
import "./Page.css";

const BUYER_PERKS = [
  "Browse 500+ premium templates",
  "AI-powered brand customization",
  "Instant one-click deploy",
  "Preview before you buy",
];

const SELLER_PERKS = [
  "Sell to 12,000+ active buyers",
  "Keep up to 80% revenue share",
  "AI-assisted product listings",
  "Real-time sales analytics",
];

const cardVariants = {
  initial: { opacity: 0, y: 30 },
  animate: (i) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.12, duration: 0.5, ease: "easeOut" },
  }),
  hover: { y: -6, transition: { duration: 0.25 } },
};

export default function RoleSelectPage() {
  const navigate = useNavigate();
  const { isSignedIn } = useAppUser();

  if (isSignedIn) {
    navigate("/dashboard", { replace: true });
    return null;
  }

  return (
    <div className="get-started-page">
      {/* Ambient orbs */}
      <div className="get-started-glow-top" />
      <div className="get-started-glow-bottom" />

      {/* Back button */}
      <button
        onClick={() => navigate("/")}
        className="get-started-close-btn"
      >
        <X className="get-started-close-icon" /> Close
      </button>

      {/* Logo */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="get-started-logo"
      >
        <img src="/logo.png" alt="AI Site Studio Logo" className="navbar-logo-img" width={36} height={36} />
        <span className="logo-text">
          AI Site Studio
        </span>
      </motion.div>

      {/* Heading */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="get-started-header"
      >
        <h1 className="get-started-title">
          How will you use AI Site Studio?
        </h1>
        <p className="get-started-subtitle">
          Pick your role to get the best experience tailored for you.
        </p>
      </motion.div>

      {/* Role Cards */}
      <div className="get-started-cards-grid">
        {/* Buyer Card */}
        <motion.button
          variants={cardVariants}
          custom={0}
          initial="initial"
          animate="animate"
          whileHover="hover"
          onClick={() => navigate("/sign-in?role=buyer")}
          className="role-card"
        >
          <div className="role-icon-box">
            <ShoppingBag className="role-card-icon" />
          </div>

          <h2 className="role-card-title">I'm a Buyer</h2>
          <p className="role-card-desc">
            Find, preview, and purchase professional website templates with
            AI-powered customization.
          </p>

          <ul className="perks-list">
            {BUYER_PERKS.map((perk) => (
              <li key={perk} className="perk-item">
                <CheckCircle2 className="perk-icon" />
                <span className="perk-text">{perk}</span>
              </li>
            ))}
          </ul>
        </motion.button>

        {/* Seller Card */}
        <motion.button
          variants={cardVariants}
          custom={1}
          initial="initial"
          animate="animate"
          whileHover="hover"
          onClick={() => navigate("/sign-in?role=seller")}
          className="role-card"
        >
          <div className="role-icon-box">
            <Upload className="role-card-icon" />
          </div>

          <h2 className="role-card-title">I'm a Seller</h2>
          <p className="role-card-desc">
            Upload your best templates, reach thousands of buyers, and grow
            your passive income with AI tools.
          </p>

          <ul className="perks-list">
            {SELLER_PERKS.map((perk) => (
              <li key={perk} className="perk-item">
                <CheckCircle2 className="perk-icon" />
                <span className="perk-text">{perk}</span>
              </li>
            ))}
          </ul>
        </motion.button>
      </div>

      <p className="get-started-footer-text">
        Already have an account?{" "}
        <button
          onClick={() => navigate("/sign-in")}
          className="get-started-signin-link"
        >
          Sign in
        </button>
      </p>
    </div>
  );
}
