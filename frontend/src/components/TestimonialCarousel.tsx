import React, { useState, useEffect } from "react";
import { Quote } from "lucide-react";

interface Testimonial {
  id: number;
  quote: string;
  author: string;
  title: string;
  organization: string;
}

const TESTIMONIALS: Testimonial[] = [
  {
    id: 1,
    quote:
      "DocChat eliminated our research team's citation hunting. Every answer directly references exact chunk IDs and page numbers with zero hallucinations.",
    author: "Dr. Elena Rostova",
    title: "Lead AI Researcher",
    organization: "BioSynth Labs",
  },
  {
    id: 2,
    quote:
      "The strict multi-tenant isolation and TiDB backing gave our compliance officer complete peace of mind. Our proprietary financial reports stay isolated.",
    author: "Marcus Vance",
    title: "Chief Compliance Officer",
    organization: "Apex Capital Partners",
  },
  {
    id: 3,
    quote:
      "Instant streaming responses, beautiful Apple design, and complete grounding against our 500-page engineering manuals. A game-changer.",
    author: "Sarah Chen",
    title: "Head of Infrastructure",
    organization: "Nordic Engineering",
  },
];

export const TestimonialCarousel: React.FC = () => {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % TESTIMONIALS.length);
    }, 6000);
    return () => clearInterval(timer);
  }, []);

  const current = TESTIMONIALS[activeIndex];

  return (
    <div
      data-testid="testimonial-carousel"
      className="relative overflow-hidden rounded-2xl bg-neutral-900 border border-neutral-800 text-white p-6 sm:p-8 flex flex-col justify-between shadow-lg"
    >
      <div className="space-y-4">
        <Quote className="w-6 h-6 text-apple-blue opacity-80" />
        <p className="text-sm sm:text-base font-normal text-neutral-200 leading-relaxed italic">
          "{current.quote}"
        </p>
      </div>

      <div className="mt-6 pt-4 border-t border-neutral-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold text-white tracking-tight">
            {current.author}
          </p>
          <p className="text-[11px] text-neutral-400">
            {current.title} · {current.organization}
          </p>
        </div>

        {/* Carousel Dot Indicators
            Rule: The white dot represents active testimonial.
                  The blue dot represents inactive testimonial. */}
        <div
          className="flex items-center gap-2"
          role="tablist"
          aria-label="Testimonial navigation"
        >
          {TESTIMONIALS.map((t, idx) => {
            const isActive = idx === activeIndex;
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={isActive}
                aria-label={`Testimonial ${idx + 1}`}
                onClick={() => setActiveIndex(idx)}
                className={`transition-all duration-300 rounded-full focus:outline-none cursor-pointer ${
                  isActive
                    ? "w-3 h-3 bg-white shadow-sm ring-2 ring-white/50" // Active: White dot
                    : "w-2.5 h-2.5 bg-apple-blue hover:opacity-80" // Inactive: Blue dot
                }`}
                data-testid={`testimonial-dot-${idx}`}
                data-active={isActive ? "true" : "false"}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};
