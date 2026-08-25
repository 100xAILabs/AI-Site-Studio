"use client";

import { motion } from "framer-motion";
import { Star, Quote } from "lucide-react";
import "./TestimonialsSection.css";

const TESTIMONIALS = [
  {
    name: "Sarah Chen",
    role: "Freelance Web Designer",
    avatar: "https://picsum.photos/seed/sarah/80/80",
    rating: 5,
    review: "The live preview feature is incredible. I showed my client a preview with their actual logo and colors before they even purchased. Closed the deal in one call!",
  },
  {
    name: "Marcus Williams",
    role: "Founder, LaunchFast Agency",
    avatar: "https://picsum.photos/seed/marcus/80/80",
    rating: 5,
    review: "We've saved 40+ hours per client project using Site Studio templates. The Instant Fill generator crafts 80% of the copy automatically. Game changer.",
  },
  {
    name: "Priya Patel",
    role: "E-Commerce Consultant",
    avatar: "https://picsum.photos/seed/priya/80/80",
    rating: 5,
    review: "The semantic search is mind-blowing. I typed 'I need a luxury jewelry store website' and it returned exactly the right templates. Zero wasted time filtering.",
  },
  {
    name: "Tom Brooks",
    role: "Full-Stack Developer",
    avatar: "https://picsum.photos/seed/tom/80/80",
    rating: 5,
    review: "Clean React code, proper TypeScript, great documentation. As a developer, I can customize these templates in hours instead of days. Worth every penny.",
  },
  {
    name: "Aisha Mohamed",
    role: "Small Business Owner",
    avatar: "https://picsum.photos/seed/aisha/80/80",
    rating: 5,
    review: "I have zero coding experience. Instant Fill generated my business content, I chose my colors, and my restaurant website was live in a single afternoon. Magical!",
  },
  {
    name: "Lucas Silva",
    role: "Digital Marketing Manager",
    avatar: "https://picsum.photos/seed/lucas/80/80",
    rating: 5,
    review: "The SEO generator alone is worth the Pro subscription. It saved us from paying an SEO consultant for basic meta tags. Highly recommend.",
  },
];

export default function TestimonialsSection() {
  return (
    <section className="section">
      <div className="container-xl">
        <div className="section-header">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="section-title"
          >
            Loved by <span className="gradient-text">12,000+</span> creators
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="section-subtitle"
          >
            From solo freelancers to agencies — here's what people are saying.
          </motion.p>
        </div>

        <div className="testimonials-grid">
          {TESTIMONIALS.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="testimonial-card"
            >
              <Quote className="testimonial-quote-icon" />
              <p className="testimonial-text">
                &ldquo;{t.review}&rdquo;
              </p>
              <div className="testimonial-author-wrapper">
                <img
                  src={t.avatar}
                  alt={t.name}
                  className="testimonial-avatar"
                />
                <div>
                  <div className="testimonial-author-name">{t.name}</div>
                  <div className="testimonial-author-role">{t.role}</div>
                </div>
                <div className="testimonial-rating">
                  {Array.from({ length: t.rating }).map((_, j) => (
                    <Star key={j} className="testimonial-star-icon" />
                  ))}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
