import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { Printer, ArrowLeft, Loader2, CheckCircle2, Clock, AlertTriangle, Building2, UserCheck, Landmark } from "lucide-react";
import { formatPrice } from "@/lib/utils";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export default function PayoutReceiptPage() {
  const { withdrawalId } = useParams();
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const isLoaded = useAuthStore((s) => s.isLoaded);
  const [receipt, setReceipt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchPayoutReceipt() {
      if (!withdrawalId || withdrawalId === "undefined") {
        setError("Invalid or missing Withdrawal ID.");
        setLoading(false);
        return;
      }

      try {
        let authToken = token;
        if (!authToken) {
          try {
            const sess = sessionStorage.getItem("aisitestudio_auth");
            if (sess) {
              const parsed = JSON.parse(sess);
              authToken = parsed?.state?.token;
            }
            if (!authToken) {
              const loc = localStorage.getItem("aisitestudio_auth");
              if (loc) {
                const parsed = JSON.parse(loc);
                authToken = parsed?.state?.token;
              }
            }
          } catch (e) {}
        }

        if (!authToken) {
          if (!isLoaded) return;
          setError("You must be signed in to view this receipt.");
          setLoading(false);
          return;
        }

        const res = await fetch(`${API_BASE}/payouts/withdrawals/${withdrawalId}/receipt`, {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Failed to fetch payout receipt details.");
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

    fetchPayoutReceipt();
  }, [withdrawalId, token, isLoaded]);

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-950 text-white">
        <Loader2 className="w-8 h-8 animate-spin text-primary mb-2" />
        <p className="text-xs text-slate-400 font-medium">Loading payout receipt...</p>
      </div>
    );
  }

  if (error || !receipt) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-950 text-white space-y-4">
        <p className="text-sm text-red-400 font-semibold">Error: {error || "Receipt not found"}</p>
        <button
          onClick={() => navigate("/dashboard")}
          className="px-5 py-2.5 bg-primary rounded-xl text-xs font-bold text-white hover:bg-primary/95 transition-all"
        >
          Back to Dashboard
        </button>
      </div>
    );
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case "paid":
        return (
          <div className="border border-emerald-600 bg-emerald-50 text-emerald-800 px-2.5 py-1 rounded font-extrabold text-[10px] uppercase tracking-wider flex items-center gap-1 shadow-sm">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> PAID
          </div>
        );
      case "approved":
        return (
          <div className="border border-blue-600 bg-blue-50 text-blue-800 px-2.5 py-1 rounded font-extrabold text-[10px] uppercase tracking-wider flex items-center gap-1 shadow-sm">
            <CheckCircle2 className="w-3 h-3 text-blue-600" /> APPROVED
          </div>
        );
      case "pending":
        return (
          <div className="border border-amber-600 bg-amber-50 text-amber-800 px-2.5 py-1 rounded font-extrabold text-[10px] uppercase tracking-wider flex items-center gap-1 shadow-sm">
            <Clock className="w-3 h-3 text-amber-600" /> PENDING
          </div>
        );
      default:
        return (
          <div className="border border-red-600 bg-red-50 text-red-800 px-2.5 py-1 rounded font-extrabold text-[10px] uppercase tracking-wider flex items-center gap-1 shadow-sm">
            <AlertTriangle className="w-3 h-3 text-red-600" /> {status.toUpperCase()}
          </div>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 py-8 px-4 sm:px-6 flex flex-col items-center justify-center print:bg-white print:py-0 print:px-0">
      <style>{`
        @media print {
          @page {
            size: A4 portrait;
            margin: 10mm;
          }
          body, html {
            background: white !important;
            color: black !important;
          }
          header, footer, nav, button, .print\\:hidden, [class*="fixed"], [class*="floating"], [class*="bubble"] {
            display: none !important;
          }
          .receipt-card-container {
            max-width: 100% !important;
            width: 100% !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            margin: 0 !important;
            background: white !important;
          }
        }
      `}</style>

      {/* Top Floating Controls */}
      <div className="w-full max-w-xl flex justify-between items-center mb-4 print:hidden">
        <button
          onClick={() => navigate("/dashboard")}
          className="flex items-center gap-1.5 text-xs font-bold text-slate-300 hover:text-white transition-colors bg-slate-900 border border-slate-800 px-3.5 py-2 rounded-xl cursor-pointer shadow-md"
        >
          <ArrowLeft className="w-3.5 h-3.5 text-primary" /> Back to Dashboard
        </button>
        <button
          onClick={handlePrint}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-primary to-indigo-600 text-white rounded-xl text-xs font-bold hover:opacity-95 transition-all shadow-lg shadow-primary/20 cursor-pointer border-none"
        >
          <Printer className="w-3.5 h-3.5" /> Print / PDF
        </button>
      </div>

      {/* Compact Receipt Card */}
      <div className="receipt-card-container w-full max-w-xl bg-white text-slate-900 shadow-[0_20px_50px_rgba(0,0,0,0.6)] border border-slate-200 rounded-2xl p-6 sm:p-8 font-sans relative space-y-6 print:shadow-none print:border-none print:p-0 print:w-full print:max-w-none">
        
        {/* Header */}
        <div className="flex justify-between items-start border-b border-slate-200 pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-emerald-600 text-white flex items-center justify-center font-black text-sm shadow-sm">
                S
              </div>
              <span className="font-black text-lg tracking-tight text-slate-900 uppercase">
                SITE STUDIO
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-medium">
              Seller Payout Disbursal Statement
            </p>
          </div>

          <div className="flex flex-col items-end space-y-1">
            {getStatusBadge(receipt.status)}
            <div className="text-[10px] text-slate-500 font-mono text-right">
              Ref: <span className="text-slate-900 font-bold">{receipt.receipt_number}</span>
            </div>
            <div className="text-[10px] text-slate-400 font-mono text-right">
              {new Date(receipt.date).toLocaleDateString(undefined, { dateStyle: "medium" })}
            </div>
          </div>
        </div>

        {/* Details: Entity & Seller */}
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div className="bg-slate-50 border border-slate-200 p-3 rounded-xl space-y-0.5">
            <span className="text-[9px] uppercase font-black text-indigo-700 tracking-wider flex items-center gap-1">
              <Building2 className="w-3 h-3 text-indigo-600" /> DISBURSER
            </span>
            <p className="font-bold text-slate-900 text-xs">Site Studio LLC</p>
            <p className="text-slate-500 text-[10px]">finance@aisitestudio.com</p>
          </div>

          <div className="bg-slate-50 border border-slate-200 p-3 rounded-xl space-y-0.5">
            <span className="text-[9px] uppercase font-black text-emerald-700 tracking-wider flex items-center gap-1">
              <UserCheck className="w-3 h-3 text-emerald-600" /> RECIPIENT
            </span>
            <p className="font-bold text-slate-900 text-xs truncate">{receipt.seller_name}</p>
            <p className="text-slate-500 text-[10px] truncate">{receipt.seller_email}</p>
          </div>
        </div>

        {/* Destination Account */}
        <div className="bg-slate-50 border border-slate-200 p-3 rounded-xl space-y-1.5 text-xs">
          <span className="text-[9px] uppercase font-black text-slate-700 tracking-wider flex items-center gap-1">
            <Landmark className="w-3 h-3 text-emerald-600" /> DESTINATION BANK ACCOUNT
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px]">
            <div>
              <p className="text-slate-400 font-semibold uppercase">Bank</p>
              <p className="font-bold text-slate-900 truncate">{receipt.bank_name}</p>
            </div>
            <div>
              <p className="text-slate-400 font-semibold uppercase">Account No</p>
              <p className="font-mono font-bold text-slate-900 truncate">{receipt.account_number}</p>
            </div>
            <div>
              <p className="text-slate-400 font-semibold uppercase">IFSC Code</p>
              <p className="font-mono font-bold text-slate-900 truncate">{receipt.ifsc_code}</p>
            </div>
            <div>
              <p className="text-slate-400 font-semibold uppercase">Holder</p>
              <p className="font-bold text-slate-900 truncate">{receipt.account_holder_name}</p>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="space-y-2">
          <h3 className="font-extrabold text-[11px] text-slate-800 uppercase tracking-wider">
            Statement Item
          </h3>
          <div className="border border-slate-200 rounded-xl overflow-hidden text-xs">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold uppercase tracking-wider text-[10px]">
                  <th className="p-2.5">Line Item</th>
                  <th className="p-2.5 text-right">Net Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                <tr className="text-slate-900">
                  <td className="p-2.5">
                    <div className="font-bold text-xs text-slate-900">
                      Creator Marketplace Net Earnings Payout
                    </div>
                    <p className="text-[10px] text-slate-400">
                      Withdrawal for accumulated sales
                    </p>
                  </td>
                  <td className="p-2.5 text-right font-mono font-bold text-xs text-slate-900">
                    {formatPrice(receipt.amount)}
                  </td>
                </tr>
                <tr className="bg-slate-50 font-black">
                  <td className="p-2.5 text-slate-900 text-xs">
                    Total Disbursed
                  </td>
                  <td className="p-2.5 text-right font-mono text-xs text-emerald-700">
                    {formatPrice(receipt.amount)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div className="pt-4 border-t border-slate-200 text-center text-slate-400 text-[10px] space-y-0.5">
          <p className="font-semibold text-slate-600">Processed within 3-5 business days.</p>
          <p>Questions? Contact payout-support@aisitestudio.com</p>
        </div>

      </div>
    </div>
  );
}
