import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: {
          DEFAULT: "#f8f9fc",
          light: "#f8f9fc",
          dark: "#0b0c14",
          cardLight: "#ffffff",
          cardDark: "#13141f",
        },
        surface: {
          DEFAULT: "#ffffff",
          light: "#ffffff",
          dark: "#161726",
          borderLight: "#e2e8f0",
          borderDark: "#222438",
        },
        purple: {
          50: "#f5f3ff",
          100: "#ede9fe",
          200: "#ddd6fe",
          300: "#c4b5fd",
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
          700: "#6d28d9",
          800: "#5b21b6",
          900: "#4c1d95",
          950: "#2e1065",
        },
        accent: {
          purple: "#7c3aed",
          indigo: "#6366f1",
          cyan: "#06b6d4",
          violet: "#8b5cf6",
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "cognexa-gradient": "linear-gradient(135deg, #7c3aed 0%, #6366f1 50%, #06b6d4 100%)",
        "purple-gradient": "linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)",
      },
      boxShadow: {
        subtle: "0 2px 10px rgba(0, 0, 0, 0.04)",
        card: "0 10px 30px -10px rgba(124, 58, 237, 0.08)",
        "card-dark": "0 10px 30px -10px rgba(0, 0, 0, 0.5)",
        glow: "0 0 25px -5px rgba(124, 58, 237, 0.3)",
      },
    },
  },
  plugins: [],
};

export default config;
