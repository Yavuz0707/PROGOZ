/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        panel: "#101821",
        panelSoft: "#142231",
        line: "#213245"
      }
    }
  },
  plugins: []
};

