import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { Printer, ArrowLeft, Loader2, FileText, CheckCircle } from "lucide-react";
import { formatPrice } from "@/lib/utils";

export default function ReceiptPage() {
  const { orderId } = useParams();
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchOrderReceipt() {
      try {
        if (!token) return;
        const res = await fetch(`http://localhost:8000/api/v1/orders/${orderId}`, {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        if (!res.ok) {
          throw new Error("Failed to fetch order details.");
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

    if (orderId && orderId !== "undefined") {
      fetchOrderReceipt();
    } else {
      setError("Invalid or missing Order ID.");
      setLoading(false);
    }
  }, [orderId, token]);

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-950 text-white">
        <Loader2 className="w-8 h-8 animate-spin text-primary mb-2" />
        <p className="text-xs text-muted-foreground">Loading receipt details...</p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-950 text-white space-y-4">
        <p className="text-sm text-red-500 font-semibold">Error: {error || "Order not found"}</p>
        <button onClick={() => navigate("/dashboard")} className="px-4 py-2 bg-primary rounded-xl text-xs font-semibold text-white">
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-10 px-4 sm:px-6 lg:px-8 print:bg-white print:text-slate-900 print:py-0 print:px-0">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Back and Print Actions (Hidden in Print) */}
        <div className="flex justify-between items-center print:hidden">
          <button
            onClick={() => navigate("/dashboard")}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Dashboard
          </button>
          <button
            onClick={handlePrint}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary text-white rounded-xl text-xs font-bold hover:bg-primary/95 transition-all shadow-lg"
          >
            <Printer className="w-4 h-4" /> Print / Save PDF
          </button>
        </div>

        {/* Invoice Container */}
        <div className="bg-slate-900/40 border border-white/5 rounded-2xl p-8 space-y-8 shadow-xl backdrop-blur-md print:bg-white print:border-none print:shadow-none print:p-0">
          {/* Header */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-white/10 pb-6 print:border-slate-200">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-lg text-primary uppercase tracking-wider print:text-primary">
                  AI Site Studio
                </span>
                <span className="text-[9px] bg-green-500/10 text-green-400 border border-green-500/20 px-2 py-0.5 rounded-full font-bold uppercase flex items-center gap-1">
                  <CheckCircle className="w-2.5 h-2.5" /> PAID
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-1 print:text-slate-500">Premium AI-Powered Website Template Marketplace</p>
            </div>
            <div className="mt-4 sm:mt-0 text-left sm:text-right text-xs text-muted-foreground space-y-1 print:text-slate-500">
              <p className="font-bold text-white print:text-slate-900 text-sm">INVOICE</p>
              <p>Invoice No: <span className="font-mono text-white print:text-slate-950 font-bold">{order.order_number}</span></p>
              <p>Date: {new Date(order.created_at).toLocaleDateString(undefined, { dateStyle: "long" })}</p>
            </div>
          </div>

          {/* Billing Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-xs border-b border-white/10 pb-6 print:border-slate-200 print:text-slate-600">
            <div>
              <p className="font-bold text-muted-foreground uppercase tracking-wider mb-2 print:text-slate-400">Sold By</p>
              <p className="font-bold text-white print:text-slate-900">AI Site Studio LLC</p>
              <p className="text-muted-foreground print:text-slate-500">Global Website Marketplace</p>
              <p className="text-muted-foreground print:text-slate-500">billing@aisitestudio.com</p>
            </div>
            <div>
              <p className="font-bold text-muted-foreground uppercase tracking-wider mb-2 print:text-slate-400">Customer Details</p>
              <p className="font-bold text-white print:text-slate-900">{order.user?.full_name || order.user?.username || "Valued Buyer"}</p>
              <p className="text-muted-foreground print:text-slate-500">{order.user?.email}</p>
              <p className="text-muted-foreground print:text-slate-500">Payment Ref: <span className="font-mono">{order.id.slice(0, 8).toUpperCase()}</span></p>
            </div>
          </div>

          {/* Items Table */}
          <div className="space-y-3">
            <h4 className="font-bold text-xs text-muted-foreground uppercase tracking-wider print:text-slate-400">Purchased Templates</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-muted-foreground font-bold print:border-slate-200 print:text-slate-400">
                    <th className="pb-2">Description</th>
                    <th className="pb-2">License Type</th>
                    <th className="pb-2 text-right">Price</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 print:divide-slate-100">
                  {order.items?.map((item) => (
                    <tr key={item.id} className="text-slate-300 print:text-slate-800">
                      <td className="py-3 font-semibold">
                        {item.template?.title || "Template Package"}
                      </td>
                      <td className="py-3">
                        <span className="bg-primary/5 text-primary border border-primary/10 px-2 py-0.5 rounded font-bold uppercase text-[9px] print:border-slate-200">
                          {item.license_type}
                        </span>
                      </td>
                      <td className="py-3 text-right font-mono font-bold">
                        {formatPrice(item.price)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Totals */}
          <div className="flex justify-end pt-4">
            <div className="w-64 space-y-2 text-xs">
              <div className="flex justify-between text-muted-foreground print:text-slate-500">
                <span>Subtotal:</span>
                <span className="font-mono">{formatPrice(order.subtotal)}</span>
              </div>
              {order.discount > 0 && (
                <div className="flex justify-between text-green-400 print:text-green-600">
                  <span>Discount:</span>
                  <span className="font-mono">-{formatPrice(order.discount)}</span>
                </div>
              )}
              <div className="flex justify-between text-muted-foreground print:text-slate-500 border-b border-white/10 pb-2 print:border-slate-200">
                <span>VAT/Taxes (0%):</span>
                <span className="font-mono">$0.00</span>
              </div>
              <div className="flex justify-between text-sm font-extrabold text-white print:text-slate-950 pt-1">
                <span>Total Paid:</span>
                <span className="font-mono text-primary print:text-primary">{formatPrice(order.total)}</span>
              </div>
            </div>
          </div>

          {/* Note Footer */}
          <div className="border-t border-white/5 pt-6 text-[10px] text-muted-foreground text-center space-y-1 print:border-slate-200 print:text-slate-400">
            <p>Thank you for your purchase from AI Site Studio!</p>
            <p>For support or licensing inquiries, please visit your dashboard or contact support@aisitestudio.com.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
