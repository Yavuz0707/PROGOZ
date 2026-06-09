/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surface / border tokens
        panel:     "#111111",
        panelSoft: "#141414",
        line:      "#2a2a2a",

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
    },
  },
  plugins: [],
};
