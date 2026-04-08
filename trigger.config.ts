import { defineConfig } from "@trigger.dev/sdk/v3";

export default defineConfig({
  // Find this in your Trigger.dev dashboard → Project Settings → Project Ref
  project: "proj_xdhswbiabwvujqcdztkh",
  dirs: ["./trigger"],
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
