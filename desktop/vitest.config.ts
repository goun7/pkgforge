import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    // Coverage enstrumantasyonu render'lari yavaslatir; dar timeout flaky
    // uretmesin diye genis pay birakilir (Faz 11).
    testTimeout: 30000,
    hookTimeout: 30000,
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/__tests__/**",
        "src/test/**",
        "src/main.tsx",
        "src/**/*.d.ts",
        // Tip-only dosyalar: calisan kod icermez, coverage'i yaniltir.
        "src/lib/types.ts",
      ],
    },
  },
});
