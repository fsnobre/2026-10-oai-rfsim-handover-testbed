export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        monitor: {
          dark: "#111827",
          panel: "#1a1a2e",
          teal: "#0097A7",
          cyan: "#22d3ee",
        },
        // Semantic status tokens (map to the existing Tailwind palette) so status
        // color usage is consistent and swappable from one place.
        status: {
          ok: "#34d399", // emerald-400
          warn: "#fbbf24", // amber-400
          bad: "#f43f5e", // rose-500
        },
        accent: "#22d3ee", // cyan-400
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular"],
      },
    },
  },
  plugins: [],
};
