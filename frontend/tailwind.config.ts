import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        void:     "#07071A",
        base:     "#0D0D1F",
        card:     "#131326",
        elevated: "#1B1B35",
        border:   "#2A2A4A",
        text:     "#E8E8F8",
        muted:    "#6B6B9A",
        // Neon purple/pink palette
        npurple:  "#A855F7",   // violet
        nviolet:  "#8B5CF6",   // indigo-violet
        nmagenta: "#E879F9",   // fuchsia
        npink:    "#EC4899",   // pink
        nrose:    "#FB7185",   // rose (negative)
        ngreen:   "#34D399",   // emerald (positive)
        nyellow:  "#FCD34D",   // amber
        // aliases
        primary:  "#A855F7",
        danger:   "#FB7185",
        success:  "#34D399",
        warning:  "#FCD34D",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "SF Pro Display", "sans-serif"],
        mono: ["SF Mono", "JetBrains Mono", "Fira Code", "monospace"],
      },
      boxShadow: {
        "neon-purple":  "0 0 14px rgba(168,85,247,0.45), 0 0 40px rgba(168,85,247,0.15)",
        "neon-magenta": "0 0 14px rgba(232,121,249,0.45), 0 0 40px rgba(232,121,249,0.15)",
        "neon-pink":    "0 0 14px rgba(236,72,153,0.45), 0 0 40px rgba(236,72,153,0.15)",
        "neon-green":   "0 0 12px rgba(52,211,153,0.4),  0 0 32px rgba(52,211,153,0.12)",
        "neon-red":     "0 0 12px rgba(251,113,133,0.4), 0 0 32px rgba(251,113,133,0.12)",
        "card":         "0 1px 4px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)",
      },
      keyframes: {
        "pulse-neon": {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0.5" },
        },
        "glow-pulse": {
          "0%, 100%": { boxShadow: "0 0 8px rgba(168,85,247,0.4)" },
          "50%":      { boxShadow: "0 0 20px rgba(168,85,247,0.8)" },
        },
      },
      animation: {
        "pulse-neon": "pulse-neon 2s ease-in-out infinite",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
