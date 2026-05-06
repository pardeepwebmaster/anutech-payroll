/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#7F77DD",
          50: "#F1F0FB",
          100: "#E2DFF7",
          200: "#C6BFEF",
          300: "#A99FE7",
          400: "#8D7FE0",
          500: "#7F77DD",
          600: "#5C52C9",
          700: "#463E9C",
          800: "#302A6F",
          900: "#1A1742",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
