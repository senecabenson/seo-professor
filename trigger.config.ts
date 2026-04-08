import { defineConfig } from "@trigger.dev/sdk";

export default defineConfig({
  project: "proj_xdhswbiabwvujqcdztkh",
  dirs: ["./trigger"],
  build: {
    dockerfile: "Dockerfile.trigger",
  },
  maxDuration: 3600,
  retries: {
    enabledInDev: false,
    default: {
      maxAttempts: 2,
      minTimeoutInMs: 1000,
      maxTimeoutInMs: 10000,
      factor: 2,
    },
  },
});
