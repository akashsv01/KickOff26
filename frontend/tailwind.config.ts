/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        champagne: {
          DEFAULT: "var(--app-gold)",
          light: "var(--app-gold-light)",
          dark: "var(--app-gold-dark)",
        },
        pitch: { DEFAULT: "var(--app-pitch)", dark: "var(--app-pitch-dark)" },
        night: "var(--app-bg)",
      },
    },
  },
  plugins: [],
};
