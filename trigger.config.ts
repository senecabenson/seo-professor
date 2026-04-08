import { defineConfig } from "@trigger.dev/sdk/v3";

export default defineConfig({
  project: "proj_xdhswbiabwvujqcdztkh",
  dirs: ["./trigger"],
  build: {
    dockerfile: "Dockerfile.trigger",
  },
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
