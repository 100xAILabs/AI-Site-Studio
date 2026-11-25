import {
  ArrowDownRight,
  ArrowRight,
  Check,
  ChevronDown,
  Crop,
  Image as ImageIcon,
  Infinity as InfinityIcon,
  Layers3,
  MousePointer2,
  Palette,
  Plus,
  Redo2,
  Settings2,
  Smartphone,
  Type,
  Undo2,
  Zap,
} from "lucide-react";
import Link from "@/components/Link";
import { motion, useReducedMotion } from "framer-motion";
import { HomepageBadge, HomepageButton, HomepageContainer } from "./HomepageDesignSystem";
import styles from "./HomepageHero.module.css";

const STATS = [
  { icon: Layers3, value: "Templates", label: "Marketplace" },
  { icon: Zap, value: "AI", label: "Studio Builder" },
  { icon: InfinityIcon, value: "Responsive", label: "Preview & Publish" },
];

function BuilderVisual() {
  return (
    <div className={styles.visualStage} aria-label="A preview of the Site Studio visual website editor">
      <div className={styles.purpleOrb} aria-hidden="true" />
      <div className={styles.purpleRing} aria-hidden="true" />
      <div className={styles.floatingTile} aria-hidden="true"><SparkleGlyph /></div>

      <div className={styles.browserWindow}>
        <div className={styles.browserTopbar}>
          <div className={styles.windowControls} aria-hidden="true"><i /><i /><i /></div>
          <div className={styles.addressBar}><span /> studio.sitestudio.app / canvas</div>
          <div className={styles.windowTopActions}><Undo2 size={14} /><Redo2 size={14} /><span className={styles.topbarDivider} /><span className={styles.previewLabel}>Preview</span><button type="button" className={styles.publishMini}>Publish</button></div>
        </div>

        <div className={styles.editorTopbar}>
          <span className={styles.projectName}><span className={styles.projectMark}>S</span> Your next great site</span>
          <div className={styles.deviceSwitch} aria-hidden="true"><span className={styles.deviceActive}><Layers3 size={13} /></span><span><Smartphone size={13} /></span></div>
          <span className={styles.saveStatus}><Check size={12} /> All changes saved</span>
        </div>

        <div className={styles.editorBody}>
          <aside className={styles.toolbar} aria-label="Editor tools">
            <span className={styles.toolActive}><MousePointer2 size={16} /></span>
            <span><Type size={16} /></span>
            <span><ImageIcon size={16} /></span>
            <span><Crop size={16} /></span>
            <span><Plus size={17} /></span>
            <span className={styles.toolbarSpacer} />
            <span><Settings2 size={16} /></span>
          </aside>
          <div className={styles.canvas}>
            <div className={styles.canvasImageFrame}>
              <img src="/landing/hero_template_canvas.png" alt="Website preview inside the Site Studio editor" loading="eager" fetchPriority="high" />
              <div className={styles.selectionOutline} aria-hidden="true"><span /><span /><span /><span /></div>
            </div>
            <div className={styles.canvasBottomBar}><span>Homepage · Desktop</span><span>100%</span></div>
          </div>
          <aside className={styles.customizePanel}>
            <div className={styles.panelHeading}><strong>Customize</strong><button type="button" aria-label="Panel options"><Settings2 size={14} /></button></div>
            <div className={styles.panelGroup}>
              <span className={styles.panelLabel}>Color palette</span>
              <div className={styles.swatches} aria-label="Color palette">
                <i className={styles.swatchSelected} /><i /><i /><i /><i />
              </div>
            </div>
            <div className={styles.panelGroup}>
              <span className={styles.panelLabel}>Typography</span>
              <button type="button" className={styles.selectButton}>Inter <ChevronDown size={13} /></button>
            </div>
            <div className={styles.panelGroup}>
              <span className={styles.panelLabel}>Heading size</span>
              <div className={styles.typeControl}><span>48 px</span><span className={styles.typeControlIcons}><Type size={13} /><ArrowDownRight size={13} /></span></div>
            </div>
            <div className={styles.panelDivider} />
            <div className={styles.panelHint}><Palette size={14} /><span>Brand colors applied</span><Check size={13} /></div>
          </aside>
        </div>
      </div>

      <div className={styles.floatingStatus}>
        <span className={styles.statusIcon}><Check size={15} /></span>
        <span><strong>Looking good</strong><small>Your site is responsive</small></span>
      </div>
      <div className={styles.floatingImageCard}>
        <img src="/landing/template_saas.png" alt="SaaS website template thumbnail" loading="lazy" />
        <span><strong>Live canvas</strong><small>Ready to customize</small></span>
      </div>
    </div>
  );
}

function SparkleGlyph() {
  return <span className={styles.sparkleGlyph}>✦</span>;
}

export default function HomepageHero() {
  const reduceMotion = useReducedMotion();
  return (
    <section className={styles.heroSection} aria-labelledby="homepage-hero-title">
      <HomepageContainer className={styles.heroContainer}>
        <motion.div className={styles.heroCopy} initial={reduceMotion ? false : { opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}>
          <HomepageBadge className={styles.heroBadge}><span className={styles.badgeSparkle}>✦</span> The Creative Platform</HomepageBadge>
          <h1 className={styles.heroTitle} id="homepage-hero-title">
            <span>Build Something</span>
            <span className={styles.heroTitleAccent}>Extraordinary.</span>
          </h1>
          <p className={styles.heroDescription}>
            Discover premium templates, create stunning websites, and bring your ideas to life with Site Studio.
          </p>
          <div className={styles.heroActions}>
            <HomepageButton href="/marketplace" size="large" className={styles.primaryCta}>
              Start Building <ArrowRight size={17} aria-hidden="true" />
            </HomepageButton>
            <HomepageButton href="/marketplace" variant="secondary" size="large" className={styles.secondaryCta}>
              Explore Templates
            </HomepageButton>
          </div>

          <div className={styles.statsRow} aria-label="Site Studio highlights">
            {STATS.map(({ icon: Icon, value, label }) => (
              <div className={styles.stat} key={label}>
                <Icon className={styles.statIcon} size={20} strokeWidth={2.2} aria-hidden="true" />
                <span className={styles.statCopy}><strong>{value}</strong><small>{label}</small></span>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div initial={reduceMotion ? false : { opacity: 0, scale: 0.96, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}><BuilderVisual /></motion.div>
      </HomepageContainer>
    </section>
  );
}
