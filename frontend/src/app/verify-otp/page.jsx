import { useState, useRef, useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { ShieldCheck, AlertCircle, ArrowLeft } from "lucide-react";
import { motion } from "framer-motion";
import { useAuthStore } from "@/store/authStore";
import { useAppUser } from "@/lib/auth";
import "./otp.css";

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0, transition: { delay, duration: 0.45 } },
});

export default function VerifyOTPPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const email = new URLSearchParams(location.search).get("email");
  const { isSignedIn, isLoaded } = useAppUser();

  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendTimer, setResendTimer] = useState(30);
  
  const inputRefs = useRef([]);
  const verifyOtp = useAuthStore((s) => s.verifyOtp); // We need to add this
  const resendOtp = useAuthStore((s) => s.resendOtp); // Optional

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      navigate("/dashboard", { replace: true });
    }
  }, [isLoaded, isSignedIn, navigate]);

  useEffect(() => {
    if (!email) {
      navigate("/sign-in", { replace: true });
    }
  }, [email, navigate]);

  useEffect(() => {
    let interval;
    if (resendTimer > 0) {
      interval = setInterval(() => {
        setResendTimer((prev) => prev - 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [resendTimer]);

  const handleChange = (index, value) => {
    // Only allow numbers
    if (!/^\d*$/.test(value)) return;

    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);

    // Auto-focus next input
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index, e) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData("text").slice(0, 6).split("");
    if (pastedData.some(char => !/^\d$/.test(char))) return;
    
    const newOtp = [...otp];
    pastedData.forEach((char, i) => {
      newOtp[i] = char;
    });
    setOtp(newOtp);
    
    // Focus the next empty input, or the last one
    const nextIndex = Math.min(pastedData.length, 5);
    inputRefs.current[nextIndex]?.focus();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const code = otp.join("");
    if (code.length !== 6) {
      setError("Please enter all 6 digits.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      if (verifyOtp) {
        await verifyOtp({ email, code });
        navigate("/dashboard", { replace: true });
      } else {
        // Mock fallback if backend isn't ready
        setTimeout(() => {
          if (code === "123456") {
            navigate("/dashboard", { replace: true });
          } else {
            setError("Invalid verification code (Try 123456)");
            setLoading(false);
          }
        }, 1500);
      }
    } catch (err) {
      setError(err?.message || "Verification failed. Please try again.");
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendTimer > 0) return;
    try {
      if (resendOtp) {
        await resendOtp({ email });
      }
      setResendTimer(30);
      setError("");
    } catch (err) {
      setError("Failed to resend code. Please try again later.");
    }
  };

  return (
    <div className="otp-page-container">
      <div className="otp-glow-top" />
      <div className="otp-glow-bottom" />

      <motion.div {...fadeUp(0)} className="otp-card">
        <button 
          onClick={() => navigate("/sign-in")} 
          className="absolute top-6 left-6 text-muted-foreground hover:text-white transition-colors"
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
        >
          <ArrowLeft size={20} />
        </button>

        <div className="otp-icon-container">
          <ShieldCheck size={32} />
        </div>

        <h1 className="otp-title">Security Verification</h1>
        <p className="otp-subtitle">
          We've sent a 6-digit verification code to <br />
          <span className="otp-email-highlight">{email}</span>
        </p>

        {error && (
          <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="otp-error-alert">
            <AlertCircle size={16} />
            {error}
          </motion.div>
        )}

        <form onSubmit={handleSubmit} style={{ width: "100%" }}>
          <div className="otp-input-group" onPaste={handlePaste}>
            {otp.map((digit, index) => (
              <input
                key={index}
                ref={(el) => (inputRefs.current[index] = el)}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleChange(index, e.target.value)}
                onKeyDown={(e) => handleKeyDown(index, e)}
                className={`otp-input-box ${error ? 'error' : ''}`}
                autoComplete="one-time-code"
              />
            ))}
          </div>

          <button type="submit" disabled={loading} className="otp-submit-btn">
            {loading ? (
              <div style={{ width: 16, height: 16, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "white", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
            ) : (
              "Verify Code"
            )}
          </button>
        </form>

        <div className="otp-resend-wrapper">
          Didn't receive the code? 
          <button 
            type="button" 
            className="otp-resend-btn"
            onClick={handleResend}
            disabled={resendTimer > 0}
          >
            {resendTimer > 0 ? `Resend in ${resendTimer}s` : "Resend"}
          </button>
        </div>
      </motion.div>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
