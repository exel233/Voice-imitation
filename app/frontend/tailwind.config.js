/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        studio: {
          ink: "#111215",
          fog: "#f6f1e8",
          ember: "#c96f3b",
          moss: "#5d7b66",
          lake: "#426d8f",
          gold: "#d8b05b"
        }
      },
      boxShadow: {
        panel: "0 24px 80px rgba(17,18,21,0.12)"
      },
      fontFamily: {
        display: ["Georgia", "serif"]
      }
    },
  },
  plugins: [],
};
