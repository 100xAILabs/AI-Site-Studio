"use client";

import { HomepageDesignScope } from "@/components/homepage/HomepageDesignSystem";
import HomepageNavbar from "@/components/homepage/HomepageNavbar";
import HomepageHero from "@/components/homepage/HomepageHero";
import HomepageContentSections, { HomepageFooter } from "@/components/homepage/HomepageContentSections";
import "./Page.css";

export default function HomePage() {
  return (
    <HomepageDesignScope className="home-studio-page">
      <HomepageNavbar />
      <main className="home-studio-main">
        <HomepageHero />

        <HomepageContentSections />
      </main>
      <HomepageFooter />
    </HomepageDesignScope>
  );
}
