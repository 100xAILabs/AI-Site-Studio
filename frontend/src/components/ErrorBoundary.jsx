import { Component } from 'react';

/**
 * Enterprise-grade React Error Boundary for AI Site Studio.
 * Features:
 * - In-memory retry without full page reload (preserves user session)
 * - Offline / network disconnect awareness with live connectivity listeners
 * - 1-Click "Copy Diagnostic Info" for effortless bug reporting
 * - Automated silent crash telemetry dispatch to backend API
 * - Scoped fallback support for granular canvas/module protection
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      copied: false,
      isOffline: typeof navigator !== 'undefined' ? !navigator.onLine : false,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidMount() {
    window.addEventListener('online', this.handleOnlineStatus);
    window.addEventListener('offline', this.handleOnlineStatus);
  }

  componentWillUnmount() {
    window.removeEventListener('online', this.handleOnlineStatus);
    window.removeEventListener('offline', this.handleOnlineStatus);
  }

  handleOnlineStatus = () => {
    const isOffline = !navigator.onLine;
    this.setState({ isOffline });
    if (!isOffline && this.state.hasError && this.isNetworkRelatedError(this.state.error)) {
      // Auto-recover if error was network-induced and connection is restored
      this.handleReset();
    }
  };

  isNetworkRelatedError(error) {
    if (!error) return false;
    const msg = error.message?.toLowerCase() || '';
    return msg.includes('fetch') || msg.includes('network') || msg.includes('failed to fetch');
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('[AI Site Studio] Unhandled render error:', error, errorInfo);

    // Call optional custom error listener from props
    if (typeof this.props.onError === 'function') {
      try {
        this.props.onError(error, errorInfo);
      } catch (e) {
        console.warn('[ErrorBoundary] onError callback failed:', e);
      }
    }

    // Report crash to backend telemetry endpoint if online
    this.reportCrashTelemetry(error, errorInfo);
  }

  reportCrashTelemetry = (error, errorInfo) => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) return;
    try {
      const payload = {
        message: error?.message || String(error),
        stack: error?.stack || null,
        componentStack: errorInfo?.componentStack || null,
        url: typeof window !== 'undefined' ? window.location.href : '',
        userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
        timestamp: new Date().toISOString(),
      };

      // Non-blocking fire-and-forget report
      if (typeof fetch === 'function') {
        fetch('/api/v1/telemetry/crash', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          keepalive: true,
        }).catch(() => {
          // Telemetry endpoints fail silently to avoid secondary cascades
        });
      }
    } catch {
      // Ignore background telemetry errors
    }
  };

  /** In-memory reset without clearing local application memory */
  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null, copied: false });
    if (typeof this.props.onReset === 'function') {
      this.props.onReset();
    }
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  handleCopyDiagnostics = async () => {
    try {
      const diagnostics = {
        application: 'AI Site Studio',
        timestamp: new Date().toISOString(),
        url: window.location.href,
        userAgent: navigator.userAgent,
        online: navigator.onLine,
        error: {
          name: this.state.error?.name,
          message: this.state.error?.message,
          stack: this.state.error?.stack,
        },
        componentStack: this.state.errorInfo?.componentStack?.trim() || null,
      };

      await navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2));
      this.setState({ copied: true });
      setTimeout(() => this.setState({ copied: false }), 2500);
    } catch {
      // Fallback if clipboard API is restricted
      alert('Unable to copy automatically. Please open details and copy manually.');
    }
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    // Support custom render fallback if provided as a prop
    if (typeof this.props.fallback === 'function') {
      return this.props.fallback({
        error: this.state.error,
        reset: this.handleReset,
        isOffline: this.state.isOffline,
      });
    }

    const { isOffline, error, copied } = this.state;
    const isNetworkError = isOffline || this.isNetworkRelatedError(error);

    return (
      <div
        id="error-boundary-fallback"
        role="alert"
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'radial-gradient(ellipse at 50% 20%, #15112c 0%, #0a0a14 70%, #05050a 100%)',
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          padding: '2rem 1.5rem',
          color: '#e5e5f7',
        }}
      >
        <div
          style={{
            maxWidth: '560px',
            width: '100%',
            background: 'rgba(20, 18, 38, 0.85)',
            border: isNetworkError ? '1px solid rgba(245, 158, 11, 0.3)' : '1px solid rgba(167, 139, 250, 0.25)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            borderRadius: '20px',
            padding: '2.75rem 2.25rem',
            textAlign: 'center',
            boxShadow: isNetworkError
              ? '0 20px 60px rgba(245, 158, 11, 0.12)'
              : '0 20px 60px rgba(139, 92, 246, 0.15)',
          }}
        >
          {/* Status Badge & Icon */}
          <div
            style={{
              width: '72px',
              height: '72px',
              background: isNetworkError ? 'rgba(245, 158, 11, 0.12)' : 'rgba(239, 68, 68, 0.12)',
              border: isNetworkError ? '1px solid rgba(245, 158, 11, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.5rem',
              fontSize: '32px',
            }}
          >
            {isNetworkError ? '📡' : '⚠️'}
          </div>

          <h1
            style={{
              color: '#f3f4f6',
              fontSize: '1.5rem',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              marginBottom: '0.6rem',
            }}
          >
            {isNetworkError ? 'Network Connection Lost' : 'Something went wrong'}
          </h1>

          <p
            style={{
              color: '#9ca3af',
              fontSize: '0.95rem',
              lineHeight: '1.6',
              marginBottom: '1.75rem',
            }}
          >
            {isNetworkError
              ? 'Unable to communicate with the server. Please verify your internet connection. AI Site Studio will attempt to reconnect once online.'
              : 'An unexpected rendering error occurred. The incident has been recorded and you can attempt to resume without losing your place.'}
          </p>

          {/* Diagnostic Collapsible */}
          {error && (
            <details
              style={{
                textAlign: 'left',
                background: 'rgba(0, 0, 0, 0.4)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '10px',
                padding: '0.9rem 1.1rem',
                marginBottom: '1.75rem',
                cursor: 'pointer',
              }}
            >
              <summary
                style={{
                  color: isNetworkError ? '#fbbf24' : '#f87171',
                  fontSize: '0.82rem',
                  fontFamily: 'monospace',
                  userSelect: 'none',
                  outline: 'none',
                }}
              >
                Inspect technical details
              </summary>
              <pre
                style={{
                  color: '#fca5a5',
                  fontSize: '0.75rem',
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  marginTop: '0.75rem',
                  maxHeight: '180px',
                  overflowY: 'auto',
                  lineHeight: '1.5',
                }}
              >
                {error?.stack || error?.toString()}
              </pre>
            </details>
          )}

          {/* Action Button Bar */}
          <div
            style={{
              display: 'flex',
              gap: '0.75rem',
              justifyContent: 'center',
              flexWrap: 'wrap',
              marginBottom: '1.25rem',
            }}
          >
            {/* Primary Action: In-Memory Try Again */}
            <button
              id="error-boundary-try-again-btn"
              onClick={this.handleReset}
              style={{
                background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
                color: '#ffffff',
                border: 'none',
                borderRadius: '10px',
                padding: '0.7rem 1.6rem',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 4px 16px rgba(124, 58, 237, 0.35)',
                transition: 'transform 0.15s, opacity 0.15s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
            >
              🔄 Try Again
            </button>

            {/* Hard Reload */}
            <button
              id="error-boundary-reload-btn"
              onClick={this.handleReload}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                color: '#e0e7ff',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '10px',
                padding: '0.7rem 1.3rem',
                fontSize: '0.9rem',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'background 0.2s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.12)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)')}
            >
              Reload Page
            </button>

            {/* Return to Home */}
            <button
              id="error-boundary-home-btn"
              onClick={this.handleGoHome}
              style={{
                background: 'transparent',
                color: '#a78bfa',
                border: '1px solid rgba(167, 139, 250, 0.35)',
                borderRadius: '10px',
                padding: '0.7rem 1.3rem',
                fontSize: '0.9rem',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#c4b5fd')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'rgba(167, 139, 250, 0.35)')}
            >
              Return Home
            </button>
          </div>

          {/* Copy Diagnostics Utility */}
          <div style={{ marginTop: '0.5rem' }}>
            <button
              id="error-boundary-copy-btn"
              onClick={this.handleCopyDiagnostics}
              style={{
                background: 'transparent',
                border: 'none',
                color: copied ? '#34d399' : '#9ca3af',
                fontSize: '0.8rem',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                textDecoration: 'underline',
                textUnderlineOffset: '3px',
                transition: 'color 0.2s',
              }}
            >
              {copied ? '✓ Diagnostics copied to clipboard!' : '📋 Copy diagnostic details for support'}
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
