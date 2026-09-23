// import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router'
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  useNavigate
} from "react-router-dom";
import { useEffect } from 'react'
import { Toaster } from 'sonner'
import { useAppUser } from './lib/auth.jsx'
import { useAuthStore } from './store/authStore.js';
import './App.css';
import Home from './app/page.jsx'
import Marketplace from './app/marketplace/page.jsx'
import Dashboard from './app/dashboard/page.jsx'
import Checkout from './app/checkout/page.jsx'
import GetStarted from './app/get-started/page.jsx'
import SignIn from './app/sign-in/page.jsx'
import Register from './app/register/page.jsx'
import Onboarding from './app/onboarding/page.jsx'
import AdminPanel from './app/admin/page.jsx'
import TemplateDetailsPage from './app/marketplace/[slug]/page.jsx'
import GenerateTemplatePage from './app/marketplace/generate.jsx'
import PreviewPage from './app/preview/page.jsx'
import StorybookPage from './app/storybook/page.jsx'
import PricingPage from './app/pricing/page.jsx'
import AboutPage from './app/about/page.jsx'
import ContactPage from './app/contact/page.jsx'
import VerifyOTPPage from './app/verify-otp/page.jsx'
import ForgotPasswordPage from './app/forgot-password/page.jsx'
import ReceiptPage from './app/dashboard/receipt/page.jsx'
import PayoutReceiptPage from './app/dashboard/payout-receipt/page.jsx'


import SupportButton from './components/support/SupportButton.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';

/** Handles the post-OAuth soft redirect without a full page reload */
function OAuthRedirectHandler() {
  const navigate = useNavigate();
  const pendingRedirect = useAuthStore((s) => s.pendingRedirect);
  const clearPendingRedirect = useAuthStore((s) => s.clearPendingRedirect);

  useEffect(() => {
    if (pendingRedirect) {
      clearPendingRedirect();
      navigate(pendingRedirect, { replace: true });
    }
  }, [pendingRedirect, navigate, clearPendingRedirect]);

  return null;
}

function ProtectedRoute({ children, requiredRole }) {
  const { user, isSignedIn, isLoaded } = useAppUser();
  const location = useLocation();
  if (!isLoaded) {
    return (
      <div className="app-loading-screen">
        <div className="app-loading-spinner">
          <div className="app-spinner-track" />
          <div className="app-spinner-head" />
        </div>
      </div>
    );
  }
  if (!isSignedIn) {
    return <Navigate to={`/sign-in?from=${encodeURIComponent(location.pathname)}`} replace />;
  }
  if (requiredRole && user?.role !== requiredRole && user?.role !== 'admin') {
    // Basic role restriction (admin bypasses)
    return <Navigate to="/dashboard" replace />;
  }
  return children;
}

function App() {
  return (
    <BrowserRouter>
      <OAuthRedirectHandler />
      <div className="app-root-container">
        {/* Premium Dark Background glow effects */}
        <div className="app-bg-glow app-bg-glow-top-left" />
        <div className="app-bg-glow app-bg-glow-bottom-right" />
        <div className="app-bg-glow app-bg-glow-center-right" />

        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/marketplace" element={<Marketplace />} />
            <Route path="/marketplace/generate" element={<ProtectedRoute><GenerateTemplatePage /></ProtectedRoute>} />
            <Route path="/marketplace/:slug" element={<TemplateDetailsPage />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/get-started" element={<GetStarted />} />
            <Route path="/sign-in" element={<SignIn />} />
            <Route path="/sign-up" element={<Navigate to="/register" replace />} />
            <Route path="/register" element={<Register />} />
            <Route path="/verify-otp" element={<VerifyOTPPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/preview" element={<PreviewPage />} />
            <Route path="/storybook" element={<StorybookPage />} />
            <Route path="/checkout" element={<ProtectedRoute><Checkout /></ProtectedRoute>} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/dashboard/receipt/:orderId" element={<ProtectedRoute><ReceiptPage /></ProtectedRoute>} />
            <Route path="/dashboard/payout-receipt/:withdrawalId" element={<ProtectedRoute><PayoutReceiptPage /></ProtectedRoute>} />
            <Route path="/admin" element={<ProtectedRoute requiredRole="admin"><AdminPanel /></ProtectedRoute>} />
          </Routes>
        </ErrorBoundary>
        <SupportButton />
        <Toaster richColors position="top-center" theme="dark" />
      </div>
    </BrowserRouter>
  )
}

export default App
