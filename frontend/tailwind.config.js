/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        apple: {
          blue: "#0066cc",
          "blue-focus": "#0071e3",
          "blue-sky": "#2997ff",
          parchment: "#f5f5f7",
          ink: "#1d1d1f",
          pearl: "#fafafc",
          "tile-1": "#272729",
          "tile-2": "#2a2a2c",
          hairline: "#e0e0e0",
          "muted-80": "#333333",
          "muted-48": "#7a7a7a",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Text",
          "SF Pro Display",
          "Inter",
          "system-ui",
          "sans-serif",
        ],
      },
      borderRadius: {
        pill: "9999px",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
}
