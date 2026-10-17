import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", '"Plus Jakarta Sans"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      colors: {
        obsidian: {
          950: "#090b0f",
          900: "#111418",
          850: "#161a20",
          800: "#1d222a",
          700: "#262c36",
          600: "#323a46",
        },
        emerald: {
          400: "#40c977",
          500: "#10b981",
          DEFAULT: "#10b981",
        },
        cyan: {
          400: "#38bdf8",
          500: "#0ea5e9",
        },
        neon: {
          green: "#40c977",
          cyan: "#38bdf8",
        },
      },
      boxShadow: {
        "glow-emerald": "0 2px 10px -2px rgba(16, 185, 129, 0.18)",
        "glow-emerald-lg": "0 4px 16px -3px rgba(16, 185, 129, 0.22)",
        "glow-cyan": "0 2px 10px -2px rgba(14, 165, 233, 0.18)",
        "glow-rose": "0 2px 10px -2px rgba(244, 63, 94, 0.18)",
      },
    },
  },
  plugins: [],
};

export default config;
