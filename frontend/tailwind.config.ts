import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}", "./lib/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#08111f",
        panel: "#0e1726",
        panelSoft: "#142135",
        line: "rgba(148, 163, 184, 0.22)",
        mint: "#3dd6a3",
        cyan: "#38bdf8",
        amber: "#fbbf24",
        rose: "#fb7185"
      },
      boxShadow: {
        glow: "0 24px 70px rgba(14, 165, 233, 0.16)",
        card: "0 18px 60px rgba(0, 0, 0, 0.28)"
      }
    }
  },
  plugins: []
};

export default config;

