/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0E0E0E",
        "bg-2": "#161616",
        "bg-3": "#1C1C1C",
        "bg-4": "#232323",
        line: "#2A2A2A",
        "line-2": "#383838",
        text: "#F2F1EE",
        "text-2": "#BDBAB3",
        "text-3": "#888581",
        "text-4": "#5C5A56",
        accent: "#FF5C3D",
        "accent-2": "#FF8467",
        "accent-ink": "#1A0A05",
        good: "#7CC79A",
        bad: "#E26A6A",
        warn: "#F5C26B",
        nyt: "#C7B8A8",
        npr: "#E26A6A",
        grd: "#6EA8DA",
      },
      fontFamily: {
        display: ["Anton", "Oswald", "Bebas Neue", "sans-serif"],
        serif: ["Fraunces", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "12px",
        sm: "8px",
        lg: "18px",
      },
    },
  },
  plugins: [],
};
