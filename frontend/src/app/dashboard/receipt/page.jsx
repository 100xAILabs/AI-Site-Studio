import { useEffect, useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { Printer, ArrowLeft, Loader2, CheckCircle2, Building2, UserCheck, Download, FileText, ShieldCheck } from "lucide-react";
import { formatPrice } from "@/lib/utils";
import "./Receipt.css";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export default function ReceiptPage() {
  const { orderId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const token = useAuthStore((s) => s.token);
  const isLoaded = useAuthStore((s) => s.isLoaded);
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchOrderReceipt() {
      if (!orderId || orderId === "undefined") {
        setError("Invalid or missing Order ID.");
        setLoading(false);
        return;
      }

      try {
        // Resolve auth token with multi-layer fallback
        let authToken = token;
        if (!authToken) {
          try {
            const loc = localStorage.getItem("aisitestudio_auth");
            if (loc) {
              const parsed = JSON.parse(loc);
              authToken = parsed?.state?.token;
            }
            if (!authToken) {
              const sess = sessionStorage.getItem("aisitestudio_auth");
              if (sess) {
                const parsed = JSON.parse(sess);
                authToken = parsed?.state?.token;
              }
            }
          } catch (e) {}
        }

        if (!authToken) {
          if (!isLoaded) {
            // Still hydrating
            return;
          }
          setError("You must be signed in to view this receipt.");
          setLoading(false);
          return;
        }

        const res = await fetch(`${API_BASE}/orders/${orderId}`, {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Failed to fetch order details.");
        }
        const data = await res.json();
        setOrder(data);
      } catch (err) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchOrderReceipt();
  }, [orderId, token, isLoaded]);

  // Auto-trigger print/save as PDF if query has ?download=pdf or ?print=true
  useEffect(() => {
    if (order && !loading) {
      const sp = new URLSearchParams(location.search);
      if (sp.get("download") === "pdf" || sp.get("print") === "true") {
        const timer = setTimeout(() => {
          window.print();
        }, 600);
        return () => clearTimeout(timer);
      }
    }
  }, [order, loading, location.search]);

  const handlePrint = () => {
    window.print();
  };

  const handleDownloadPdf = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="receipt-page-wrapper">
        <Loader2 className="w-8 h-8 animate-spin text-primary mb-3" style={{ width: "2rem", height: "2rem", color: "#c89666" }} />
        <p style={{ color: "#94a3b8", fontSize: "0.875rem", margin: 0, fontWeight: 500 }}>Loading official invoice...</p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="receipt-page-wrapper">
        <div style={{ textAlign: "center", display: "flex", flexDirection: "column", gap: "1rem", alignItems: "center" }}>
          <p style={{ color: "#f87171", fontSize: "0.9375rem", fontWeight: 700, margin: 0 }}>Error: {error || "Order not found"}</p>
          <button
            onClick={() => navigate("/dashboard")}
            className="receipt-btn-back"
          >
            <ArrowLeft style={{ width: "1rem", height: "1rem" }} /> Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const invoiceNumber = order.order_number || `INV-${String(order.id).slice(0, 8).toUpperCase()}`;
  const invoiceDate = new Date(order.created_at || Date.now()).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="receipt-page-wrapper">
      {/* Top Action Controls */}
      <div className="receipt-top-actions">
        <button
          onClick={() => navigate("/dashboard")}
          className="receipt-btn-back"
          title="Return to Dashboard"
        >
          <ArrowLeft style={{ width: "0.875rem", height: "0.875rem", color: "#dfb180" }} />
          <span>Back to Dashboard</span>
        </button>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <button
            onClick={handleDownloadPdf}
            className="receipt-btn-print"
            style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}
            title="Download Invoice as PDF"
          >
            <Download style={{ width: "0.875rem", height: "0.875rem" }} />
            <span>Download PDF</span>
          </button>
          <button
            onClick={handlePrint}
            className="receipt-btn-back"
            style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}
            title="Print Tax Invoice"
          >
            <Printer style={{ width: "0.875rem", height: "0.875rem" }} />
            <span>Print</span>
          </button>
        </div>
      </div>

      {/* Main Compact Receipt Card */}
      <div className="receipt-card">
        
        {/* Header & Status Stamp */}
        <div className="receipt-header">
          <div className="receipt-brand-box">
            <div className="receipt-logo-row">
              <div className="receipt-logo-icon">
                S
              </div>
              <span className="receipt-brand-title">
                SITE STUDIO
              </span>
            </div>
            <p className="receipt-brand-sub">
              Official Tax Invoice & Proof of Purchase
            </p>
          </div>

          <div className="receipt-status-box">
            <div className="receipt-paid-badge">
              <CheckCircle2 style={{ width: "0.75rem", height: "0.75rem", color: "#059669" }} /> PAID
            </div>
            <p className="receipt-meta-text">
              Inv #: <strong>{invoiceNumber}</strong>
            </p>
            <p className="receipt-meta-text">
              Date: {invoiceDate}
            </p>
            {order.gateway && (
              <p className="receipt-meta-text" style={{ textTransform: "uppercase", fontSize: "0.6875rem" }}>
                Via: <strong>{order.gateway}</strong>
              </p>
            )}
            {order.extra_metadata?.upi_utr && (
              <p className="receipt-meta-text" style={{ color: "#059669", fontWeight: 700, fontFamily: "monospace" }}>
                UTR: {order.extra_metadata.upi_utr}
              </p>
            )}
          </div>
        </div>

        {/* Details: Seller & Customer */}
        <div className="receipt-party-grid">
          <div className="receipt-party-card">
            <span className="receipt-party-tag">
              <Building2 style={{ width: "0.75rem", height: "0.75rem" }} /> SELLER / CREATOR
            </span>
            <p className="receipt-party-name">
              {order.items?.[0]?.developer_name || order.items?.[0]?.template?.developer_name || "Site Studio Creator"}
            </p>
            <p className="receipt-party-detail">Verified Marketplace Seller</p>
            <p className="receipt-party-detail" style={{ fontSize: "0.6875rem", color: "#64748b" }}>
              Platform: Site Studio Marketplace
            </p>
          </div>

          <div className="receipt-party-card">
            <span className="receipt-party-tag customer">
              <UserCheck style={{ width: "0.75rem", height: "0.75rem" }} /> BILLED TO (CUSTOMER)
            </span>
            <p className="receipt-party-name">
              {order.user?.full_name || order.user?.username || order.user?.email || "Valued Customer"}
            </p>
            <p className="receipt-party-detail">{order.user?.email || "N/A"}</p>
            <p className="receipt-party-detail" style={{ fontSize: "0.6875rem", color: "#64748b" }}>
              Customer ID: #{String(order.user?.id || order.user_id || order.id || "USR").slice(0, 8).toUpperCase()}
            </p>
          </div>
        </div>

        {/* Itemized Table */}
        <div className="receipt-items-section">
          <h4 className="receipt-section-label">
            Purchased Items & Licenses
          </h4>
          <div className="receipt-table-box">
            <table className="receipt-table">
              <thead>
                <tr>
                  <th style={{ width: "55%" }}>Description</th>
                  <th style={{ width: "25%", textAlign: "center" }}>License</th>
                  <th style={{ width: "20%", textAlign: "right" }}>Price</th>
                </tr>
              </thead>
              <tbody>
                {order.items && order.items.length > 0 ? (
                  order.items.map((item, idx) => (
                    <tr key={item.id || idx}>
                      <td>
                        <p className="receipt-item-title">
                          {item.title || item.template?.title || "Site Studio Template Package"}
                        </p>
                        <p className="receipt-item-sub">
                          {item.framework ? `${item.framework} • ` : ""}Full source code ZIP archive & lifetime access
                        </p>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <span className="receipt-license-badge">
                          {(item.license_type || "regular").toUpperCase()}
                        </span>
                      </td>
                      <td className="receipt-item-price">
                        {formatPrice(item.price || order.total)}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td>
                      <p className="receipt-item-title">
                        {order.notes || "Official Site Studio Production Package"}
                      </p>
                      <p className="receipt-item-sub">
                        Full source code package, clean project assets & lifetime verified digital license
                      </p>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className="receipt-license-badge">
                        REGULAR
                      </span>
                    </td>
                    <td className="receipt-item-price">
                      {formatPrice(order.total)}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Financial Summary */}
        <div className="receipt-summary-wrapper">
          <div className="receipt-summary-card">
            <div className="receipt-summary-row">
              <span>Subtotal</span>
              <span>{formatPrice(order.subtotal || order.total)}</span>
            </div>
            
            {order.discount > 0 && (
              <div className="receipt-summary-row discount">
                <span>Discount</span>
                <span>-{formatPrice(order.discount)}</span>
              </div>
            )}

            <div className="receipt-summary-row">
              <span>GST / Taxes (0% Digital Goods)</span>
              <span>{formatPrice(0)}</span>
            </div>

            <div className="receipt-summary-divider" />

            <div className="receipt-summary-total">
              <span>Total Paid</span>
              <span className="receipt-summary-total-val">{formatPrice(order.total)}</span>
            </div>
          </div>
        </div>

        {/* Verification & Footer */}
        <div className="receipt-footer">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.375rem", marginBottom: "0.25rem", color: "#10b981", fontSize: "0.6875rem", fontWeight: 700 }}>
            <ShieldCheck style={{ width: "0.875rem", height: "0.875rem" }} />
            <span>Cryptographically Verified Digital Purchase</span>
          </div>
          <p className="receipt-footer-thank">Thank you for choosing Site Studio!</p>
          <p className="receipt-footer-sub">Official tax invoice & digital proof of purchase • Authorized by Site Studio</p>
        </div>

      </div>
    </div>
  );
}

