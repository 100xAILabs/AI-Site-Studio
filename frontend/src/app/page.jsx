"use client";

import Navbar from "@/components/layout/Navbar";
import { HomepageDesignScope } from "@/components/homepage/HomepageDesignSystem";
import HeroSection from "@/components/landing/HeroSection";
import PopularTemplatesSection from "@/components/landing/PopularTemplatesSection";
import "./Page.css";

export default function HomePage() {
  return (
    <HomepageDesignScope className="home-studio-page">
      <Navbar />
      <main className="home-studio-main">
        {/* Main Hero with Big 3D Studio Mockup & 5-Column Feature Bar */}
        <HeroSection />

        {/* Popular Templates Section with Big Curated Cards */}
        <PopularTemplatesSection />
      </main>
    </HomepageDesignScope>
  );
}
