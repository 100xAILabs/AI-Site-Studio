import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { Printer, ArrowLeft, Loader2, CheckCircle, Clock, AlertTriangle } from "lucide-react";
import { formatPrice } from "@/lib/utils";

export default function PayoutReceiptPage() {
  const { withdrawalId } = useParams();
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const [receipt, setReceipt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchPayoutReceipt() {
      try {
        if (!token) return;
        const res = await fetch(`http://localhost:8000/api/v1/payouts/withdrawals/${withdrawalId}/receipt`, {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        if (!res.ok) {
          throw new Error("Failed to fetch payout receipt details.");
        }
        const data = await res.json();
        setReceipt(data);
      } catch (err) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    if (withdrawalId) {
      fetchPayoutReceipt();
    }
  }, [withdrawalId, token]);

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

  if (error || !receipt) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-950 text-white space-y-4">
        <p className="text-sm text-red-500 font-semibold">Error: {error || "Receipt not found"}</p>
        <button onClick={() => navigate("/dashboard")} className="px-4 py-2 bg-primary rounded-xl text-xs font-semibold text-white">
          Back to Dashboard
        </button>
      </div>
    );
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case "paid":
        return (
          <span className="text-[10px] bg-green-500/10 text-green-400 border border-green-500/20 px-2 py-0.5 rounded-full font-bold uppercase flex items-center gap-1">
            <CheckCircle className="w-3 h-3" /> PAID / COMPLETED
          </span>
        );
      case "approved":
        return (
          <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full font-bold uppercase flex items-center gap-1">
            <CheckCircle className="w-3 h-3" /> APPROVED
          </span>
        );
      case "pending":
        return (
          <span className="text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full font-bold uppercase flex items-center gap-1">
            <Clock className="w-3 h-3" /> PENDING REVIEW
          </span>
        );
      default:
        return (
          <span className="text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-0.5 rounded-full font-bold uppercase flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> {status.toUpperCase()}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-10 px-4 sm:px-6 lg:px-8 print:bg-white print:text-slate-900 print:py-0 print:px-0">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Back and Print Actions */}
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
              <div className="flex items-center gap-2.5">
                <span className="font-extrabold text-lg text-primary uppercase tracking-wider print:text-primary">
                  AI Site Studio
                </span>
                {getStatusBadge(receipt.status)}
              </div>
              <p className="text-xs text-muted-foreground mt-1 print:text-slate-500">Earnings Payout / Withdrawal Receipt</p>
            </div>
            <div className="mt-4 sm:mt-0 text-left sm:text-right text-xs text-muted-foreground space-y-1 print:text-slate-500">
              <p className="font-bold text-white print:text-slate-900 text-sm">PAYOUT STATEMENT</p>
              <p>Statement No: <span className="font-mono text-white print:text-slate-950 font-bold">{receipt.receipt_number}</span></p>
              <p>Submitted: {new Date(receipt.date).toLocaleDateString(undefined, { dateStyle: "medium" })}</p>
              {receipt.payout_date && (
                <p>Processed: {new Date(receipt.payout_date).toLocaleDateString(undefined, { dateStyle: "medium" })}</p>
              )}
            </div>
          </div>

          {/* Billing Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-xs border-b border-white/10 pb-6 print:border-slate-200 print:text-slate-600">
            <div>
              <p className="font-bold text-muted-foreground uppercase tracking-wider mb-2 print:text-slate-400">Payout From</p>
              <p className="font-bold text-white print:text-slate-900">AI Site Studio LLC</p>
              <p className="text-muted-foreground print:text-slate-500">Global Website Marketplace</p>
              <p className="text-muted-foreground print:text-slate-500">finance@aisitestudio.com</p>
            </div>
            <div>
              <p className="font-bold text-muted-foreground uppercase tracking-wider mb-2 print:text-slate-400">Seller / Recipient Details</p>
              <p className="font-bold text-white print:text-slate-900">{receipt.seller_name}</p>
              <p className="text-muted-foreground print:text-slate-500">{receipt.seller_email}</p>
              <p className="text-muted-foreground print:text-slate-500">Reference: <span className="font-mono">{receipt.receipt_number}</span></p>
            </div>
          </div>

          {/* Bank details */}
          <div className="bg-muted/10 p-5 rounded-xl border border-white/5 space-y-3 print:bg-slate-50 print:border-slate-200">
            <h4 className="font-bold text-xs text-muted-foreground uppercase tracking-wider print:text-slate-500">Destination Account</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div>
                <p className="text-muted-foreground print:text-slate-500">Bank Name</p>
                <p className="font-bold text-white print:text-slate-900 mt-0.5">{receipt.bank_name}</p>
              </div>
              <div>
                <p className="text-muted-foreground print:text-slate-500">Account Number</p>
                <p className="font-bold text-white print:text-slate-900 mt-0.5">{receipt.account_number}</p>
              </div>
              <div>
                <p className="text-muted-foreground print:text-slate-500">IFSC/Swift Code</p>
                <p className="font-bold text-white print:text-slate-900 mt-0.5">{receipt.ifsc_code}</p>
              </div>
              <div>
                <p className="text-muted-foreground print:text-slate-500">Account Holder</p>
                <p className="font-bold text-white print:text-slate-900 mt-0.5">{receipt.account_holder_name}</p>
              </div>
            </div>
          </div>

          {/* Statement details */}
          <div className="space-y-3">
            <h4 className="font-bold text-xs text-muted-foreground uppercase tracking-wider print:text-slate-400">Statement breakdown</h4>
            <div className="border border-white/5 rounded-xl overflow-hidden print:border-slate-200">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-white/5 border-b border-white/10 text-muted-foreground font-bold print:bg-slate-100 print:border-slate-200 print:text-slate-500">
                    <th className="p-3">Description</th>
                    <th className="p-3 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="text-slate-300 print:text-slate-800 border-b border-white/5 print:border-slate-100">
                    <td className="p-3 font-medium">
                      Earnings Withdrawal Claim Request
                    </td>
                    <td className="p-3 text-right font-mono font-bold">
                      {formatPrice(receipt.amount)}
                    </td>
                  </tr>
                  <tr className="bg-white/[0.02] print:bg-slate-50">
                    <td className="p-3 font-extrabold text-white print:text-slate-950">
                      Total Payout Amount
                    </td>
                    <td className="p-3 text-right font-mono font-extrabold text-primary print:text-primary">
                      {formatPrice(receipt.amount)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Note Footer */}
          <div className="border-t border-white/5 pt-6 text-[10px] text-muted-foreground text-center space-y-1 print:border-slate-200 print:text-slate-400">
            <p>Withdrawals are processed within 3-5 business days depending on your banking institution.</p>
            <p>If you have any questions regarding this statement, please contact payout-support@aisitestudio.com.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
