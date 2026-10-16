import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      colors: {
        obsidian: {
          950: "#06080d",
          900: "#0a0d14",
          850: "#0d121c",
          800: "#111726",
          700: "#182033",
          600: "#222d47",
        },
        emerald: {
          400: "#34d399",
          500: "#10b981",
          DEFAULT: "#10b981",
        },
        cyan: {
          400: "#22d3ee",
          500: "#06b6d4",
        },
        neon: {
          green: "#00ff88",
          cyan: "#00e5ff",
        },
      },
      boxShadow: {
        "glow-emerald": "0 0 20px -3px rgba(16, 185, 129, 0.35)",
        "glow-emerald-lg": "0 0 30px -4px rgba(0, 255, 136, 0.45)",
        "glow-cyan": "0 0 20px -3px rgba(6, 182, 212, 0.35)",
        "glow-rose": "0 0 20px -3px rgba(244, 63, 94, 0.35)",
      },
    },
  },
  plugins: [],
};

export default config;
