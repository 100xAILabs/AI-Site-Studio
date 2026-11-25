import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  BriefcaseBusiness,
  Check,
  Code2,
  Eye,
  Globe2,
  HeartHandshake,
  Layers3,
  Monitor,
  Palette,
  PenTool,
  Rocket,
  ShoppingBag,
  ShoppingCart,
  Smartphone,
  Sparkles,
  Star,
  WandSparkles,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import Link from "@/components/Link";
import { api } from "@/lib/api";
import Footer from "@/components/layout/Footer";
import { useTemplates, useToggleWishlist } from "@/hooks/useTemplates";
import { formatPrice } from "@/lib/utils";
import { useAppUser } from "@/lib/auth";
import { useAuthStore } from "@/store/authStore";
import { useCartStore } from "@/store";
import {
  HomepageBadge,
  HomepageButton,
  HomepageCard,
  HomepageContainer,
  HomepageSectionHeading,
} from "./HomepageDesignSystem";
import styles from "./HomepageContentSections.module.css";

const CATEGORIES = [
  { title: "Business & Corporate", slug: "business", icon: BriefcaseBusiness, palette: "business" },
  { title: "Portfolio", slug: "portfolio", icon: PenTool, palette: "portfolio" },
  { title: "E-commerce", slug: "ecommerce", icon: ShoppingBag, palette: "commerce" },
  { title: "SaaS & Technology", slug: "saas-technology", icon: Code2, palette: "saas" },
  { title: "Landing Pages", slug: "landing-pages", icon: Sparkles, palette: "landing" },
  { title: "Creative & Agency", slug: "creative-agency", icon: Palette, palette: "creative" },
];

const PLATFORM_FEATURES = [
  { icon: WandSparkles, title: "Automated Studio Builder", description: "Turn a clear idea into a structured website plan and generated starting point.", href: "/studio" },
  { icon: Layers3, title: "Premium Templates", description: "Browse published website templates with their real previews, details, and prices.", href: "/marketplace" },
  { icon: ShoppingBag, title: "Marketplace", description: "Discover work from independent creators and manage your purchases in one place.", href: "/marketplace" },
  { icon: Palette, title: "Advanced Customization", description: "Open the Studio to personalize a site and review changes as you work.", href: "/studio" },
  { icon: Rocket, title: "One-Click Publishing", description: "Take a finished site into the available deployment flow from your Studio.", href: "/studio/deploy" },
];

function normalize(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function flattenCategories(categories = [], parents = []) {
  return categories.flatMap((category) => [
    { ...category, parents },
    ...flattenCategories(category.children || [], [...parents, category.slug, category.name]),
  ]);
}

function matchesCategory(template, slug, categoriesById) {
  const sourceCategory = categoriesById.get(String(template.category_id));
  const categoryText = normalize([
    sourceCategory?.slug,
    sourceCategory?.name,
    ...(sourceCategory?.parents || []),
  ].filter(Boolean).join(" "));
  if (slug === "saas-technology") return /saas|technology|tech/.test(categoryText);
  if (slug === "creative-agency") return /creative|agency/.test(categoryText);
  if (slug === "business") return /business|corporate/.test(categoryText);
  if (slug === "ecommerce") return /e-?commerce|retail|shop/.test(categoryText);
  if (slug === "landing-pages") return /landing/.test(categoryText);
  return categoryText.includes(slug);
}

function CategoryCard({ category, template, categoryImage }) {
  const [imageFailed, setImageFailed] = useState(false);
  const reduceMotion = useReducedMotion();
  const { icon: Icon } = category;
  const image = !imageFailed ? categoryImage || template?.thumbnail_url || null : null;
  const title = template?.title || "";
  return (
    <motion.div className={styles.categoryLink} whileHover={reduceMotion ? undefined : { y: -4 }} transition={{ duration: 0.2 }} initial={reduceMotion ? false : { opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.15 }}>
    <Link href={`/marketplace?category=${encodeURIComponent(category.slug)}`} className={styles.categoryLinkInner}>
      <HomepageCard as="article" variant="quiet" className={`${styles.categoryCard} ${styles[`category${category.palette[0].toUpperCase()}${category.palette.slice(1)}`]}`}>
        <div className={styles.categoryArtwork}>
          {image ? (
            <img src={image} alt={title ? `${title} template preview` : `${category.title} website template preview`} loading="lazy" onError={() => setImageFailed(true)} />
          ) : (
            <div className={styles.categoryFallbackArt} aria-label={`${category.title} preview is not available yet`}><Icon size={28} strokeWidth={1.5} /><span>{category.title}</span></div>
          )}
          <span className={styles.categoryOpen}><ArrowUpRight size={17} /></span>
        </div>
        <div className={styles.categoryInfo}>
          <span className={styles.categoryIcon}><Icon size={16} /></span>
          <span>{category.title}</span>
          <ArrowRight className={styles.categoryArrow} size={15} />
        </div>
      </HomepageCard>
    </Link>
    </motion.div>
  );
}

function FeaturedTemplateCard({ template, wishlistMutation, token }) {
  const [imageFailed, setImageFailed] = useState(false);
  const reduceMotion = useReducedMotion();
  const navigate = useNavigate();
  const id = template.id;
  const slug = template.slug || id;
  const inCart = useCartStore((state) => state.isInCart(id));
  const addItem = useCartStore((state) => state.addItem);
  const priceExists = template.price !== null && template.price !== undefined && Number.isFinite(Number(template.price));
  const price = priceExists ? Number(template.price) : null;
  const currency = template.price_currency || "USD";
  const isPurchased = Boolean(template.is_purchased);
  const previewHref = template.seller?.creator_store_slug
    ? `/creator/${encodeURIComponent(template.seller.creator_store_slug)}/demo/${encodeURIComponent(slug)}`
    : `/demo/${encodeURIComponent(slug)}`;

  const handleWishlist = () => {
    if (!token) {
      navigate(`/sign-in?from=${encodeURIComponent("/")}`);
      return;
    }
    wishlistMutation.mutate(id, {
      onSuccess: () => toast.success(template.is_wishlisted ? "Removed from your wishlist." : "Added to your wishlist."),
      onError: () => toast.error("Could not update your wishlist. Please try again."),
    });
  };

  const handlePurchase = () => {
    if (isPurchased) {
      navigate("/purchases");
      return;
    }
    if (!priceExists) {
      navigate(`/marketplace/${encodeURIComponent(slug)}`);
      return;
    }
    addItem({
      templateId: id || slug,
      title: template.title,
      price,
      price_currency: currency,
      thumbnail: template.thumbnail_url,
      framework: template.framework,
      licenseType: "regular",
      seller_id: template.seller_id,
      creator_slug: template.seller?.creator_store_slug,
      creator_brand_name: template.seller?.creator_brand_name || template.developer_name,
    });
    navigate("/checkout");
  };

  return (
    <motion.div initial={reduceMotion ? false : { opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.15 }} whileHover={reduceMotion ? undefined : { y: -4 }} transition={{ duration: 0.22 }}><HomepageCard as="article" variant="quiet" className={styles.templateCard}>
      <Link href={`/marketplace/${encodeURIComponent(slug)}`} className={styles.templatePreview} aria-label={`View ${template.title} details`}>
        {template.thumbnail_url && !imageFailed ? (
          <img src={template.thumbnail_url} alt={`${template.title} preview`} loading="lazy" onError={() => setImageFailed(true)} />
        ) : (
          <div className={styles.templateNoImage}><Layers3 size={32} /><span>Preview unavailable</span></div>
        )}
        {template.is_featured && <HomepageBadge className={styles.featuredBadge}>Featured</HomepageBadge>}
      </Link>
      <div className={styles.templateBody}>
        <div className={styles.templateTitleLine}>
          <Link href={`/marketplace/${encodeURIComponent(slug)}`} className={styles.templateTitle}>{template.title}</Link>
          <button
            type="button"
            className={`${styles.wishlistButton} ${template.is_wishlisted ? styles.wishlisted : ""}`}
            aria-label={template.is_wishlisted ? `Remove ${template.title} from wishlist` : `Add ${template.title} to wishlist`}
            aria-pressed={Boolean(template.is_wishlisted)}
            disabled={wishlistMutation.isPending}
            onClick={handleWishlist}
          >
            <Bookmark size={17} fill={template.is_wishlisted ? "currentColor" : "none"} />
          </button>
        </div>
        {(Number(template.rating_avg) > 0 || Number(template.rating_count) > 0) && (
          <div className={styles.templateRating}>
            <Star size={14} fill="currentColor" />
            {Number(template.rating_avg) > 0 && <span>{Number(template.rating_avg).toFixed(1)}</span>}
            {Number(template.rating_count) > 0 && <span className={styles.ratingCount}>({Number(template.rating_count).toLocaleString()})</span>}
          </div>
        )}
        <div className={styles.templatePriceRow}>
          <span className={styles.templatePrice}>{priceExists ? formatPrice(price, currency) : "Price unavailable"}</span>
          {template.framework && <span className={styles.templateFramework}>{template.framework}</span>}
        </div>
        <div className={styles.templateActions}>
          <Link href={previewHref} className={styles.previewAction} target="_blank" rel="noreferrer"><Eye size={15} /> Preview</Link>
          <button type="button" className={styles.purchaseAction} onClick={handlePurchase}>
            {isPurchased ? <><Check size={15} /> In your library</> : inCart ? <><ShoppingCart size={15} /> Checkout</> : <>Purchase <ArrowRight size={15} /></>}
          </button>
        </div>
      </div>
    </HomepageCard></motion.div>
  );
}

function BuilderShowcase() {
  const reduceMotion = useReducedMotion();
  return (
    <motion.section className={styles.builderSection} initial={reduceMotion ? false : { opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.1 }} transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}>
      <HomepageContainer className={styles.sectionContainer}>
        <div className={styles.builderLayout}>
          <div className={styles.builderCopy}>
            <HomepageBadge><Sparkles size={13} /> AI-powered builder</HomepageBadge>
            <HomepageSectionHeading
              className={styles.builderHeading}
              title={<>Design faster.<br /><span>Make it yours.</span></>}
              description="Start with an idea, shape a site through the Studio workflow, and keep your work visible in the editor as it comes together."
            />
            <ul className={styles.builderChecklist}>
              <li><Check size={16} /> Turn your prompt into a guided site plan</li>
              <li><Check size={16} /> Adjust the structure and visual direction</li>
              <li><Check size={16} /> Review layouts across screen sizes</li>
            </ul>
            <HomepageButton href="/studio" size="large">Start Building <ArrowRight size={16} /></HomepageButton>
          </div>

          <div className={styles.builderVisual} aria-label="Illustration of the Site Studio website generation workflow">
            <div className={styles.builderGlow} />
            <div className={styles.builderWindow}>
              <div className={styles.builderWindowBar}><span><i /><i /><i /></span><b>Site Studio · New project</b><span className={styles.generationState}><span /> Building preview</span></div>
              <div className={styles.builderToolbar}><span className={styles.activeTool}><Monitor size={14} /></span><span><Smartphone size={14} /></span><span><Layers3 size={14} /></span><span className={styles.builderToolbarGap} /><span>Preview width <b>1440 px</b></span></div>
              <div className={styles.builderCanvas}>
                <img src="/landing/hero_template_canvas.png" alt="A website being customized in the Site Studio canvas" loading="lazy" />
                <div className={styles.promptCard}><span className={styles.promptIcon}><WandSparkles size={15} /></span><span><small>Your idea</small><strong>A modern website for a new creative business</strong></span><ArrowUpRight size={15} /></div>
              </div>
              <div className={styles.builderInspector}>
                <div><span className={styles.inspectorTitle}>Customize</span><span className={styles.inspectorSaved}><Check size={12} /> Saved</span></div>
                <div className={styles.inspectorControls}><span><small>Theme color</small><i className={styles.colorDot} /><i /><i /><i /></span><span><small>Typography</small><b>Inter <ArrowRight size={11} /></b></span><span><small>Layout</small><b>Responsive <ArrowRight size={11} /></b></span></div>
              </div>
            </div>
            <div className={styles.responsiveCard}><span className={styles.responsiveIcon}><Smartphone size={17} /></span><span><strong>Responsive preview</strong><small>Desktop · Tablet · Mobile</small></span><Check size={14} /></div>
          </div>
        </div>
      </HomepageContainer>
    </motion.section>
  );
}

function CreatorMarketplaceSection({ user }) {
  const reduceMotion = useReducedMotion();
  const isExtreme = Boolean(
    user?.can_retail_templates || user?.is_extreme_subscriber ||
    ["extreme", "agency", "enterprise"].includes(String(user?.subscription_tier || "").toLowerCase()) ||
    ["admin", "super_admin"].includes(user?.role)
  );
  const sellHref = isExtreme ? "/dashboard?tab=creator-studio" : "/pricing";

  return (
    <motion.section className={styles.creatorSection} initial={reduceMotion ? false : { opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.1 }} transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}>
      <HomepageContainer className={styles.sectionContainer}>
        <div className={styles.creatorPanel}>
          <div className={styles.creatorCopy}>
            <HomepageBadge tone="neutral"><HeartHandshake size={14} /> For independent creators</HomepageBadge>
            <HomepageSectionHeading
              className={styles.creatorHeading}
              title={<>Your work deserves<br /><span>a wider audience.</span></>}
              description="Bring your website templates to the Site Studio marketplace. Give buyers a clear preview, share your storefront, and manage your creator work from Studio."
            />
            <HomepageButton href={sellHref} size="large">Sell Your Template <ArrowRight size={16} /></HomepageButton>
          </div>
          <div className={styles.creatorShowcase}>
            <div className={styles.creatorDiscoveryCard}>
              <div className={styles.discoveryHeader}><span className={styles.discoveryMark}><ShoppingBag size={16} /></span><span><strong>Creator marketplace</strong><small>Discover independent work</small></span><ArrowUpRight size={17} /></div>
              <div className={styles.discoveryPreview}><img src="/landing/template_saas.png" alt="SaaS website template listing preview" loading="lazy" /><span className={styles.discoveryTag}>Website template</span></div>
              <div className={styles.discoveryFooter}><span><span className={styles.creatorAvatar}>S</span> Studio Creator</span><span>Explore work <ArrowRight size={13} /></span></div>
            </div>
            <div className={styles.creatorBenefitCard}><span className={styles.benefitIcon}><Globe2 size={17} /></span><strong>One storefront</strong><small>Let buyers browse your published work.</small></div>
            <div className={styles.creatorSparkle}>✦</div>
          </div>
        </div>
      </HomepageContainer>
    </motion.section>
  );
}

function PlatformFeaturesSection() {
  const reduceMotion = useReducedMotion();
  return (
    <motion.section className={styles.featuresSection} id="features" initial={reduceMotion ? false : { opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.1 }} transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}>
      <HomepageContainer className={styles.sectionContainer}>
        <HomepageSectionHeading
          eyebrow="Made for the full creative process"
          title={<>Everything you need to<br /><span>make a site your own.</span></>}
          description="Move from first idea to a polished, publishable website in one connected workspace."
          align="center"
          className={styles.featuresHeading}
        />
        <div className={styles.featuresGrid}>
          {PLATFORM_FEATURES.map(({ icon: Icon, title, description, href }, index) => (
            <Link href={href} className={styles.featureLink} key={title}>
              <HomepageCard variant="quiet" className={styles.featureCard}>
                <span className={styles.featureNumber}>0{index + 1}</span>
                <span className={styles.featureIcon}><Icon size={20} /></span>
                <h3>{title}</h3>
                <p>{description}</p>
                <span className={styles.featureLinkLabel}>Explore <ArrowUpRight size={14} /></span>
              </HomepageCard>
            </Link>
          ))}
        </div>
      </HomepageContainer>
    </motion.section>
  );
}

function ClosingSection() {
  const reduceMotion = useReducedMotion();
  return (
    <motion.section className={styles.closingSection} initial={reduceMotion ? false : { opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.1 }} transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}>
      <HomepageContainer className={styles.sectionContainer}>
        <div className={styles.closingPanel}>
          <div className={styles.closingOrnament} aria-hidden="true"><span /><span /><span /></div>
          <HomepageBadge className={styles.closingBadge}><Sparkles size={13} /> Your next project starts here</HomepageBadge>
          <h2>Your next great<br /><span>website starts here.</span></h2>
          <p>Explore templates, bring an idea into the Studio, and build a website that feels like yours.</p>
          <div className={styles.closingActions}>
            <HomepageButton href="/studio" size="large">Start Building <ArrowRight size={16} /></HomepageButton>
            <HomepageButton href="/marketplace" variant="secondary" size="large">Explore Templates</HomepageButton>
          </div>
        </div>
      </HomepageContainer>
    </motion.section>
  );
}

export default function HomepageContentSections() {
  const { user } = useAppUser();
  const token = useAuthStore((state) => state.token);
  const { data, isLoading } = useTemplates({ page: 1, page_size: 100, sort: "best_sellers" }, token);
  const { data: categoryData } = useQuery({ queryKey: ["homepage-categories"], queryFn: () => api.get("/categories"), staleTime: 1000 * 60 * 15 });
  const categoriesById = useMemo(() => new Map(flattenCategories(Array.isArray(categoryData) ? categoryData : []).map((category) => [String(category.id), category])), [categoryData]);
  const templates = useMemo(() => (Array.isArray(data?.items) ? data.items : []), [data?.items]);
  const featuredTemplates = useMemo(() => {
    const featured = templates.filter((template) => template.is_featured);
    return (featured.length ? featured : templates).slice(0, 4);
  }, [templates]);
  const categoryTemplates = useMemo(() => {
    return CATEGORIES.map((category) => ({
      category,
      template: templates.find((template) => matchesCategory(template, category.slug, categoriesById) && template.thumbnail_url),
      categoryImage: flattenCategories(Array.isArray(categoryData) ? categoryData : []).find((item) => {
        const categoryName = normalize(`${item.slug} ${item.name} ${(item.parents || []).join(" ")}`);
        if (category.slug === "saas-technology") return /saas|technology|tech/.test(categoryName);
        if (category.slug === "creative-agency") return /creative|agency/.test(categoryName);
        if (category.slug === "business") return /business|corporate/.test(categoryName);
        if (category.slug === "ecommerce") return /e-?commerce|retail|shop/.test(categoryName);
        if (category.slug === "landing-pages") return /landing/.test(categoryName);
        return categoryName.includes(category.slug);
      })?.image_url,
    }));
  }, [templates, categoriesById, categoryData]);
  const wishlistMutation = useToggleWishlist(token || "");

  return (
    <>
      <section className={styles.categoriesSection} aria-labelledby="homepage-categories-heading">
        <HomepageContainer className={styles.sectionContainer}>
          <div className={styles.categoriesIntro}>
            <HomepageSectionHeading
              eyebrow="Explore categories"
              id="homepage-categories-heading"
              title={<>Find the perfect<br /><span>template for your next idea.</span></>}
              description="Browse published designs by the kind of website you want to create."
              className={styles.categoriesHeading}
            />
            <HomepageButton href="/marketplace" variant="secondary" className={styles.allTemplatesButton}>Browse all templates <ArrowRight size={15} /></HomepageButton>
          </div>
          <div className={styles.categoriesGrid}>
            {categoryTemplates.map(({ category, template, categoryImage }) => <CategoryCard key={category.slug} category={category} template={template} categoryImage={categoryImage} />)}
          </div>
        </HomepageContainer>
      </section>

      <section className={styles.featuredSection} aria-labelledby="homepage-featured-heading">
        <HomepageContainer className={styles.sectionContainer}>
          <div className={styles.featuredIntro}>
            <HomepageSectionHeading
              eyebrow="Featured templates"
              id="homepage-featured-heading"
              title={<>Made to make<br /><span>an impression.</span></>}
              description="Explore published templates from the Site Studio marketplace."
              className={styles.featuredHeading}
            />
            <HomepageButton href="/marketplace" variant="secondary" className={styles.allTemplatesButton}>View marketplace <ArrowRight size={15} /></HomepageButton>
          </div>
          {isLoading ? (
            <div className={styles.templateLoading} aria-live="polite">Loading published templates…</div>
          ) : featuredTemplates.length ? (
            <div className={styles.templatesGrid}>
              {featuredTemplates.map((template) => <FeaturedTemplateCard key={template.id || template.slug} template={template} wishlistMutation={wishlistMutation} token={token} />)}
            </div>
          ) : (
            <div className={styles.templateEmpty}>There are no published templates to feature right now. <Link href="/marketplace">Visit the marketplace <ArrowRight size={14} /></Link></div>
          )}
        </HomepageContainer>
      </section>

      <BuilderShowcase />
      <CreatorMarketplaceSection user={user} />
      <PlatformFeaturesSection />
      <ClosingSection />
    </>
  );
}

export function HomepageFooter() {
  return <div className={styles.footerScope}><Footer /></div>;
}
