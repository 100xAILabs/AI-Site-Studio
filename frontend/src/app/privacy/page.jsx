import Navbar from "@/components/layout/Navbar";
import Link from "@/components/Link";
import "./PrivacyPage.css";

const LAST_UPDATED = "30 September 2026";

export default function PrivacyPolicyPage() {
  return (
    <>
      <Navbar />
      <main className="legal-page">
        <div className="legal-container">
          <header className="legal-header">
            <p className="legal-eyebrow">Legal</p>
            <h1 className="legal-title">Privacy Policy</h1>
            <p className="legal-updated">Last updated: {LAST_UPDATED}</p>
          </header>

          <div className="legal-body">
            <p>
              Site Studio ("we", "us", or "our") operates the website available
              at this domain. This Privacy Policy explains what personal data we
              collect, why we collect it, and how we use it when you use the
              Site Studio platform.
            </p>

            <h2>1. Information We Collect</h2>
            <h3>1.1 Account Information</h3>
            <p>
              When you register for an account, we collect your email address,
              a display name, and an encrypted password. If you sign in via a
              third-party OAuth provider (e.g., Google), we receive only the
              profile information that provider makes available — typically your
              name and email address.
            </p>

            <h3>1.2 Usage Data</h3>
            <p>
              We record which templates you view, preview, or download, along
              with timestamps and your IP address. This data is used to improve
              the platform's search relevance and to debug technical issues. We
              do not sell usage data to third parties.
            </p>

            <h3>1.3 Uploaded Content</h3>
            <p>
              If you upload template files as a creator, those files are stored
              on our servers. We may inspect uploaded files automatically as
              part of the code-quality auditing process described in our Terms
              & Conditions.
            </p>

            <h3>1.4 Payment Information</h3>
            <p>
              Payments are processed by a third-party payment provider. We do
              not store your full card number, CVV, or bank account details on
              our servers. We retain only a transaction reference and the amount
              for bookkeeping purposes.
            </p>

            <h2>2. How We Use Your Information</h2>
            <ul>
              <li>To operate and improve the Site Studio platform.</li>
              <li>To authenticate you when you sign in.</li>
              <li>To send transactional emails (e.g., purchase receipts, password reset).</li>
              <li>To detect and prevent fraud or abuse.</li>
              <li>To comply with legal obligations.</li>
            </ul>
            <p>
              We do not use your data to train external AI models, nor do we
              share it with advertisers.
            </p>

            <h2>3. Cookies and Local Storage</h2>
            <p>
              We use session cookies and browser local storage to keep you
              signed in between visits and to remember your preferences (e.g.,
              selected currency). We do not use third-party advertising cookies.
            </p>

            <h2>4. Data Sharing & Third-Party Sub-Processors</h2>
            <p>
              We share your data only with verified third-party service providers that operate
              infrastructure and services on our behalf. These sub-processors are contractually
              obligated to process your data only for authorized purposes:
            </p>
            <ul>
              <li><strong>Payment Gateways:</strong> Stripe, Inc. (global card processing and payouts) and Razorpay Software Pvt. Ltd. (UPI, NetBanking, INR payment gateway).</li>
              <li><strong>AI Model Providers:</strong> Google LLC (Gemini API for semantic search embeddings and live design filling) and OpenAI LLC. Prompts sent to AI APIs are never used to train external models.</li>
              <li><strong>Email Delivery & Notifications:</strong> Resend, Inc. and Brevo SAS (transactional emails, security OTP codes, order receipts).</li>
              <li><strong>Cloud Hosting & CDN:</strong> Cloudflare, Inc. and Render Services, Inc. (edge routing, DDoS mitigation, and container hosting).</li>
              <li><strong>Domain Registration:</strong> Namecheap, Inc. and registry partners (fulfilling custom domain registrations).</li>
            </ul>
            <p>
              We may disclose your data if required by law, court order, or competent government authority.
            </p>

            <h2>5. Data Retention</h2>
            <p>
              Account data is retained for as long as your account is active.
              If you delete your account, we will erase or anonymise your personal data
              within 30 days, except where statutory law requires retention
              (e.g., tax and financial transaction records, which are retained for 7 years for auditing).
            </p>

            <h2>6. Your Rights (DPDP Act 2023 & GDPR)</h2>
            <p>
              In accordance with the Digital Personal Data Protection (DPDP) Act 2023 and the General Data Protection Regulation (GDPR), you have the right to:
            </p>
            <ul>
              <li><strong>Right to Access & Review:</strong> View the personal data and transaction history held about you.</li>
              <li><strong>Right to Correction:</strong> Correct or update inaccurate account profile details.</li>
              <li><strong>Right to Erasure / Anonymization:</strong> Erase your personal details via our automated self-service account deletion endpoint (<code>DELETE /api/v1/auth/me</code>).</li>
              <li><strong>Right to Data Portability:</strong> Export your full personal data and purchased licenses in a machine-readable JSON format via <code>GET /api/v1/auth/me/export</code>.</li>
              <li><strong>Right to Grievance Redressal:</strong> Withdraw consent or register privacy concerns with our Data Protection Officer.</li>
            </ul>
            <p>
              To exercise any of these rights, use your account dashboard or contact us at privacy@aisitestudio.com.
            </p>

            <h2>7. Security</h2>
            <p>
              We use industry-standard practices to protect your data: HTTPS for
              all data in transit, hashed passwords, and access controls that
              restrict data access to authorised personnel only. No system is
              completely secure; we cannot guarantee absolute security.
            </p>

            <h2>8. Children's Privacy</h2>
            <p>
              Site Studio is not directed at children under the age of 13. We do
              not knowingly collect personal data from children. If you believe
              a child has provided us with personal data, contact us and we will
              delete it.
            </p>

            <h2>9. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. When we do,
              we will update the "Last updated" date at the top of this page. If
              changes are material, we will notify registered users by email.
            </p>

            <h2>10. Contact</h2>
            <p>
              For privacy-related questions or requests, contact us through our{" "}
              <Link href="/contact" className="legal-link">contact page</Link>.
            </p>
          </div>

          <div className="legal-footer-nav">
            <Link href="/terms" className="legal-link">Terms &amp; Conditions</Link>
            <span className="legal-footer-divider">·</span>
            <Link href="/" className="legal-link">Back to Home</Link>
          </div>
        </div>
      </main>
    </>
  );
}
