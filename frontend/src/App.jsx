// import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router'
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  useNavigate
} from "react-router-dom";
import { useEffect, lazy, Suspense } from 'react'
import { Toaster } from 'sonner'
import { useTheme } from './hooks/useTheme'
import { useAppUser } from './lib/auth.jsx'
import { useAuthStore } from './store/authStore.js';
import './App.css';

const Home = lazy(() => import('./app/page.jsx'));
const Marketplace = lazy(() => import('./app/marketplace/page.jsx'));
const Dashboard = lazy(() => import('./app/dashboard/page.jsx'));
const Checkout = lazy(() => import('./app/checkout/page.jsx'));
const GetStarted = lazy(() => import('./app/get-started/page.jsx'));
const SignIn = lazy(() => import('./app/sign-in/page.jsx'));
const Register = lazy(() => import('./app/register/page.jsx'));
const Onboarding = lazy(() => import('./app/onboarding/page.jsx'));
const AdminPanel = lazy(() => import('./app/admin/page.jsx'));
const TemplateDetailsPage = lazy(() => import('./app/marketplace/[slug]/page.jsx'));
const StudioPage = lazy(() => import('./app/studio/page.jsx'));
const StudioLaunchPage = lazy(() => import('./app/studio/launch/page.jsx'));
const StudioDeployPage = lazy(() => import('./app/studio/deploy/page.jsx'));
const PreviewPage = lazy(() => import('./app/preview/page.jsx'));
const LiveDemoPage = lazy(() => import('./app/demo/page.jsx'));
const StorybookPage = lazy(() => import('./app/storybook/page.jsx'));
const PricingPage = lazy(() => import('./app/pricing/page.jsx'));
const SubscribePage = lazy(() => import('./app/subscribe/page.jsx'));
const AboutPage = lazy(() => import('./app/about/page.jsx'));
const ContactPage = lazy(() => import('./app/contact/page.jsx'));
const VerifyOTPPage = lazy(() => import('./app/verify-otp/page.jsx'));
const ForgotPasswordPage = lazy(() => import('./app/forgot-password/page.jsx'));
const ReceiptPage = lazy(() => import('./app/dashboard/receipt/page.jsx'));
const PayoutReceiptPage = lazy(() => import('./app/dashboard/payout-receipt/page.jsx'));
const DeployedWebsiteDetailsPage = lazy(() => import('./app/deployments/[id]/page.jsx'));
const DomainPurchasePage = lazy(() => import('./app/domains/buy/page.jsx'));
const PrivacyPolicyPage = lazy(() => import('./app/privacy/page.jsx'));
const TermsPage = lazy(() => import('./app/terms/page.jsx'));
const CreatorSetupPage = lazy(() => import('./app/creator/setup/page.jsx'));
const CreatorStorefrontPage = lazy(() => import('./app/creator/[slug]/page.jsx'));
const CreatorAuthPage = lazy(() => import('./app/creator/auth/page.jsx'));
const CreatorCheckoutPage = lazy(() => import('./app/creator/checkout/page.jsx'));
const CreatorTemplateDetailsPage = lazy(() => import('./app/creator/template/page.jsx'));
const CreatorDemoPage = lazy(() => import('./app/creator/demo/page.jsx'));
const AuthCompletePage = lazy(() => import('./app/auth/complete/page.jsx'));


import SupportButton from './components/support/SupportButton.jsx';
import StudioBuildFloatingWidget from './components/studio/StudioBuildFloatingWidget.jsx';
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

function AppRouteContent() {
  const location = useLocation();

  return (
    <div key={location.pathname} className="app-route-transition">
      <ErrorBoundary>
        <Suspense fallback={
          <div className="app-loading-screen">
            <div className="app-loading-spinner">
              <div className="app-spinner-track" />
              <div className="app-spinner-head" />
            </div>
          </div>
        }>
          <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/marketplace" element={<Marketplace />} />
          <Route path="/studio" element={<ProtectedRoute><StudioPage /></ProtectedRoute>} />
          <Route path="/studio/launch" element={<ProtectedRoute><StudioLaunchPage /></ProtectedRoute>} />
          <Route path="/studio/deploy" element={<ProtectedRoute><StudioDeployPage /></ProtectedRoute>} />
          <Route path="/marketplace/generate" element={<Navigate to="/studio" replace />} />
          <Route path="/marketplace/:slug" element={<TemplateDetailsPage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/subscribe" element={<SubscribePage />} />
          <Route path="/subscription" element={<Navigate to="/subscribe" replace />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/get-started" element={<GetStarted />} />
          <Route path="/sign-in" element={<SignIn />} />
          <Route path="/login" element={<Navigate to="/sign-in" replace />} />
          <Route path="/sign-up" element={<Navigate to="/register" replace />} />
          <Route path="/register" element={<Register />} />
          <Route path="/verify-otp" element={<VerifyOTPPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/auth/complete" element={<AuthCompletePage />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/preview" element={<PreviewPage />} />
          <Route path="/demo/:slug" element={<LiveDemoPage />} />
          <Route path="/demo" element={<LiveDemoPage />} />
          <Route path="/storybook" element={<StorybookPage />} />
          <Route path="/cart" element={<Checkout />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/deployments/:id" element={<ProtectedRoute><DeployedWebsiteDetailsPage /></ProtectedRoute>} />
          <Route path="/dashboard/deployments/:id" element={<ProtectedRoute><DeployedWebsiteDetailsPage /></ProtectedRoute>} />
          <Route path="/domains/buy" element={<ProtectedRoute><DomainPurchasePage /></ProtectedRoute>} />
          <Route path="/dashboard/receipt/:orderId" element={<ReceiptPage />} />
          <Route path="/dashboard/payout-receipt/:withdrawalId" element={<PayoutReceiptPage />} />
          <Route path="/admin" element={<ProtectedRoute requiredRole="admin"><AdminPanel /></ProtectedRoute>} />
          <Route path="/creator" element={<Navigate to="/creator/setup" replace />} />
          <Route path="/creator/setup" element={<ProtectedRoute><CreatorSetupPage /></ProtectedRoute>} />
          <Route path="/creator/:creatorSlug/template/:slug" element={<CreatorTemplateDetailsPage />} />
          <Route path="/creator/:creatorSlug/demo/:slug" element={<CreatorDemoPage />} />
          <Route path="/creator/:creatorSlug/checkout" element={<CreatorCheckoutPage />} />
          <Route path="/creator/:creatorSlug/login" element={<CreatorAuthPage />} />
          <Route path="/creator/:creatorSlug/register" element={<CreatorAuthPage isRegister={true} />} />
          <Route path="/creator/:slug" element={<CreatorStorefrontPage />} />
          <Route path="/privacy" element={<PrivacyPolicyPage />} />
          <Route path="/terms" element={<TermsPage />} />
        </Routes>
        </Suspense>
      </ErrorBoundary>
    </div>
  );
}

function AdaptiveToaster() {
  const { resolvedTheme } = useTheme();
  return <Toaster richColors position="top-center" theme={resolvedTheme === "light" ? "light" : "dark"} />;
}

function App() {
  return (
    <BrowserRouter>
      <OAuthRedirectHandler />
      <div className="app-root-container">
        <AppRouteContent />
        <SupportButton />
        <StudioBuildFloatingWidget />
        <AdaptiveToaster />
      </div>
    </BrowserRouter>
  )
}

export default App
