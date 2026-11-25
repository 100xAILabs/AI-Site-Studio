import Link from "@/components/Link";
import styles from "./HomepageDesignSystem.module.css";

function joinClasses(...values) {
  return values.filter(Boolean).join(" ");
}

/** Homepage-only theme scope. Keeps its design tokens local to the homepage tree. */
export function HomepageDesignScope({ as: Element = "div", className = "", children, ...props }) {
  return (
    <Element className={joinClasses(styles.scope, className)} {...props}>
      {children}
    </Element>
  );
}

export function HomepageContainer({ as: Element = "div", size = "wide", className = "", children, ...props }) {
  return (
    <Element className={joinClasses(styles.container, styles[`container${size[0].toUpperCase()}${size.slice(1)}`], className)} {...props}>
      {children}
    </Element>
  );
}

export function HomepageButton({
  as: Element,
  href,
  variant = "primary",
  size = "medium",
  className = "",
  children,
  type = "button",
  ...props
}) {
  const buttonClass = joinClasses(styles.button, styles[`button${variant[0].toUpperCase()}${variant.slice(1)}`], styles[`button${size[0].toUpperCase()}${size.slice(1)}`], className);
  if (href) {
    const LinkElement = Element || Link;
    return <LinkElement href={href} className={buttonClass} {...props}>{children}</LinkElement>;
  }
  const ButtonElement = Element || "button";
  return <ButtonElement type={type} className={buttonClass} {...props}>{children}</ButtonElement>;
}

export function HomepageBadge({ tone = "accent", className = "", children, ...props }) {
  return (
    <span className={joinClasses(styles.badge, styles[`badge${tone[0].toUpperCase()}${tone.slice(1)}`], className)} {...props}>
      {children}
    </span>
  );
}

export function HomepageSectionHeading({
  as: Heading = "h2",
  eyebrow,
  title,
  description,
  align = "left",
  className = "",
}) {
  return (
    <header className={joinClasses(styles.sectionHeading, styles[`align${align[0].toUpperCase()}${align.slice(1)}`], className)}>
      {eyebrow && <p className={styles.eyebrow}>{eyebrow}</p>}
      <Heading className={styles.headingTitle}>{title}</Heading>
      {description && <p className={styles.headingDescription}>{description}</p>}
    </header>
  );
}

export function HomepageCard({ as: Element = "article", variant = "surface", className = "", children, ...props }) {
  return (
    <Element className={joinClasses(styles.card, styles[`card${variant[0].toUpperCase()}${variant.slice(1)}`], className)} {...props}>
      {children}
    </Element>
  );
}
