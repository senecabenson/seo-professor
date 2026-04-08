/**
 * GET /api/status/:runId
 * Returns the current status and output of a Trigger.dev run.
 *
 * Response:
 *   { status: string, output: object|null, error: string|null }
 *
 * status values (Trigger.dev v3):
 *   WAITING_FOR_DEPLOY | QUEUED | EXECUTING | COMPLETED | FAILED | CANCELED | TIMED_OUT | CRASHED
 *
 * output is populated when status === "COMPLETED":
 *   { domain, pdf_url, aggregated, ai_analysis }
 */

import { runs } from "@trigger.dev/sdk/v3";

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { runId } = req.query;

  if (!runId) {
    return res.status(400).json({ error: "runId is required" });
  }

  try {
    const run = await runs.retrieve(runId);
    return res.status(200).json({
      status: run.status,
      output: run.output ?? null,
      error: run.error?.message ?? null,
    });
  } catch (err) {
    console.error("Failed to retrieve run:", err);
    return res.status(500).json({ error: "Failed to get run status", detail: err.message });
  }
}
