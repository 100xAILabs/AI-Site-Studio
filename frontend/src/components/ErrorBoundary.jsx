import { Component } from 'react';

/**
 * Global React Error Boundary for AI Site Studio.
 * Catches any unhandled rendering errors and shows a branded
 * fallback UI instead of a blank white screen.
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('[AI Site Studio] Unhandled render error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div id="error-boundary-fallback" style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #0a0a14 0%, #0f0f1e 60%, #0a0a14 100%)',
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
        padding: '2rem',
      }}>
        <div style={{
          maxWidth: '520px',
          width: '100%',
          background: 'rgba(26, 26, 46, 0.9)',
          border: '1px solid rgba(167, 139, 250, 0.2)',
          borderRadius: '16px',
          padding: '2.5rem',
          textAlign: 'center',
          boxShadow: '0 0 60px rgba(139, 92, 246, 0.1)',
        }}>
          <div style={{
            width: '64px',
            height: '64px',
            background: 'rgba(239, 68, 68, 0.1)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1.5rem',
            fontSize: '28px',
          }}>
            ⚠️
          </div>

          <h1 style={{
            color: '#e5e5f7',
            fontSize: '1.4rem',
            fontWeight: 700,
            marginBottom: '0.75rem',
          }}>
            Something went wrong
          </h1>

          <p style={{
            color: '#9ca3af',
            fontSize: '0.95rem',
            lineHeight: '1.6',
            marginBottom: '1.75rem',
          }}>
            An unexpected error occurred in the application.
            This has been logged automatically.
          </p>

          {this.state.error && (
            <details style={{
              textAlign: 'left',
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(239,68,68,0.2)',
              borderRadius: '8px',
              padding: '1rem',
              marginBottom: '1.75rem',
              cursor: 'pointer',
            }}>
              <summary style={{ color: '#f87171', fontSize: '0.82rem', fontFamily: 'monospace', cursor: 'pointer' }}>
                Error details
              </summary>
              <pre style={{
                color: '#fca5a5',
                fontSize: '0.75rem',
                fontFamily: 'monospace',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                marginTop: '0.75rem',
                maxHeight: '160px',
                overflow: 'auto',
              }}>
                {this.state.error?.toString()}
              </pre>
            </details>
          )}

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              id="error-boundary-reload-btn"
              onClick={this.handleReload}
              style={{
                background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                padding: '0.65rem 1.5rem',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'opacity 0.2s',
              }}
              onMouseEnter={e => e.target.style.opacity = '0.85'}
              onMouseLeave={e => e.target.style.opacity = '1'}
            >
              Reload Application
            </button>
            <button
              id="error-boundary-home-btn"
              onClick={this.handleGoHome}
              style={{
                background: 'transparent',
                color: '#a78bfa',
                border: '1px solid rgba(167, 139, 250, 0.4)',
                borderRadius: '8px',
                padding: '0.65rem 1.5rem',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={e => e.target.style.borderColor = '#a78bfa'}
              onMouseLeave={e => e.target.style.borderColor = 'rgba(167,139,250,0.4)'}
            >
              Return to Home
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
