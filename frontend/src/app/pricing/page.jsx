import Navbar from "@/components/layout/Navbar";
import PricingSection from "@/components/landing/PricingSection";
import "./Page.css";

export default function PricingPage() {
  return (
    <>
      <Navbar />
      <main className="pricing-page-main">
        <PricingSection />
      </main>
    </>
  );
}
