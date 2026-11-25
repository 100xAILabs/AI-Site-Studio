"use client";

import { HomepageDesignScope } from "@/components/homepage/HomepageDesignSystem";
import HomepageNavbar from "@/components/homepage/HomepageNavbar";
import HomepageHero from "@/components/homepage/HomepageHero";
import PopularTemplatesSection from "@/components/landing/PopularTemplatesSection";
import "./Page.css";

export default function HomePage() {
  return (
    <HomepageDesignScope className="home-studio-page">
      <HomepageNavbar />
      <main className="home-studio-main">
        <HomepageHero />

        {/* Popular Templates Section with Big Curated Cards */}
        <PopularTemplatesSection />
      </main>
    </HomepageDesignScope>
  );
}
