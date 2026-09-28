import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TestimonialCarousel } from "../components/TestimonialCarousel";

describe("TestimonialCarousel and Dot Indicators Rule", () => {
  it("enforces white dot for active testimonial and blue dot for inactive testimonials", () => {
    render(<TestimonialCarousel />);

    const dots = [
      screen.getByTestId("testimonial-dot-0"),
      screen.getByTestId("testimonial-dot-1"),
      screen.getByTestId("testimonial-dot-2"),
    ];

    // Initially active index is 0
    expect(dots[0]).toHaveAttribute("data-active", "true");
    expect(dots[0].className).toContain("bg-white"); // Active dot is white
    expect(dots[1]).toHaveAttribute("data-active", "false");
    expect(dots[1].className).toContain("bg-apple-blue"); // Inactive dot is blue
    expect(dots[2]).toHaveAttribute("data-active", "false");
    expect(dots[2].className).toContain("bg-apple-blue"); // Inactive dot is blue

    // Click second dot
    fireEvent.click(dots[1]);

    expect(dots[0]).toHaveAttribute("data-active", "false");
    expect(dots[0].className).toContain("bg-apple-blue"); // Now inactive: blue
    expect(dots[1]).toHaveAttribute("data-active", "true");
    expect(dots[1].className).toContain("bg-white"); // Now active: white
    expect(dots[2]).toHaveAttribute("data-active", "false");
    expect(dots[2].className).toContain("bg-apple-blue"); // Inactive: blue
  });
});
