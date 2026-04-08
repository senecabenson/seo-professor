/**
 * Trigger.dev v3 task — SEO Professor audit pipeline.
 *
 * This TypeScript task is the entry point Trigger.dev's Node.js scanner
 * finds. It spawns the Python audit pipeline as a subprocess and returns
 * the structured JSON result.
 *
 * Environment variables required in Trigger.dev project:
 *   ANTHROPIC_API_KEY
 *   SUPABASE_URL
 *   SUPABASE_KEY
 */

import { task, logger } from "@trigger.dev/sdk/v3";
import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";

const execFileAsync = promisify(execFile);

export const seoAuditTask = task({
  id: "seo-audit",
  maxDuration: 3600, // 1 hour max for large site crawls
  run: async (payload: {
    url: string;
    max_pages?: number;
    single_page?: boolean;
    business_context?: Record<string, unknown>;
  }) => {
    const scriptPath = path.join(process.cwd(), "trigger", "run_audit.py");

    logger.log("Starting Python audit subprocess", {
      url: payload.url,
      max_pages: payload.max_pages ?? 50,
      single_page: payload.single_page ?? false,
    });

    const { stdout, stderr } = await execFileAsync(
      "python3",
      [scriptPath, JSON.stringify(payload)],
      {
        maxBuffer: 50 * 1024 * 1024, // 50MB — large audits produce big JSON
        env: { ...process.env },
      }
    );

    if (stderr) {
      logger.warn("Python subprocess stderr", { stderr });
    }

    const result = JSON.parse(stdout);
    logger.log("Audit complete", {
      domain: result.domain,
      score: result.aggregated?.site_score,
      pages: result.aggregated?.pages_audited,
    });

    return result;
  },
});
