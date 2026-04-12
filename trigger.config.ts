import { defineConfig } from "@trigger.dev/sdk";

const pythonExtension = {
  name: "python-deps",
  onBuildStart: async (context: any) => {
    context.addLayer({
      id: "python-system-deps",
      image: {
        instructions: [
          "RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info fonts-liberation && rm -rf /var/lib/apt/lists/*",
          "RUN pip3 install --no-cache-dir --break-system-packages anthropic weasyprint supabase httpx beautifulsoup4 lxml jinja2 python-dotenv google-api-python-client google-auth google-analytics-data",
        ],
      },
    });
  },
};

export default defineConfig({
  project: "proj_xdhswbiabwvujqcdztkh",
  dirs: ["./trigger"],
  compatibilityFlags: ["run_engine_v2"],
  build: {
    extensions: [pythonExtension],
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
