/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // Stitch "Stealth Surveillance" type system
        sans: ["Geist", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Geist", "Inter", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      letterSpacing: {
        caps: "0.15em",
        hud: "0.1em",
        widestx: "0.2em",
      },
      colors: {
        // Surface / border tokens
        panel:     "#111111",
        panelSoft: "#141414",
        line:      "#2a2a2a",

        // Stealth surveillance surface scale
        surface: {
          DEFAULT: "#131313",
          dim:     "#131313",
          bright:  "#393939",
          lowest:  "#0e0e0e",
          low:     "#1c1b1b",
          mid:     "#20201f",
          high:    "#2a2a2a",
          highest: "#353535",
        },
        // Functional status accents (only non-monochrome elements allowed)
        status: {
          green: "#46ff78",
          amber: "#ffb347",
          red:   "#ff4646",
          blue:  "#4696ff",
        },

        // Remap cyan → white / light-gray scale (no teal anywhere)
        cyan: {
          50:  "#f9f9f9",
          100: "#f0f0f0",
          200: "#dedede",
          300: "#cccccc",
          400: "#ffffff",
          500: "#e0e0e0",
          600: "#c8c8c8",
          700: "#aaaaaa",
          800: "#888888",
          900: "#555555",
          950: "#333333",
        },

        // Remap slate → true blacks / dark grays
        slate: {
          50:  "#f5f5f5",
          100: "#ebebeb",
          200: "#cccccc",
          300: "#aaaaaa",
          400: "#888888",
          500: "#555555",
          600: "#3a3a3a",
          700: "#2a2a2a",
          800: "#1a1a1a",
          900: "#111111",
          950: "#000000",
        },
      },
      boxShadow: {
        "glow-green": "0 0 12px rgba(70, 255, 120, 0.45)",
        "glow-amber": "0 0 12px rgba(255, 179, 71, 0.45)",
        "glow-red":   "0 0 12px rgba(255, 70, 70, 0.45)",
        "glow-blue":  "0 0 12px rgba(70, 150, 255, 0.45)",
        "glow-white": "0 0 80px 20px rgba(255, 255, 255, 0.05)",
        "glass-top":  "inset 0 1px 0 rgba(255, 255, 255, 0.05)",
      },
      keyframes: {
        fadeInUp: {
          "0%":   { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        ambientPulse: {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0.45" },
        },
      },
      animation: {
        "fade-in-up": "fadeInUp 0.3s ease forwards",
        "ambient-pulse": "ambientPulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
