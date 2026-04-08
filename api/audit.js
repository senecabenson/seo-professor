/**
 * POST /api/audit
 * Body: { url: string, max_pages?: number, single_page?: boolean }
 * Returns: { run_id: string }
 *
 * Triggers the "seo-audit" Trigger.dev task and returns the run ID.
 * The client polls /api/status/:runId to track progress.
 */

const { tasks } = require("@trigger.dev/sdk/v3");

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { url, max_pages = 50, single_page = false } = req.body;

  if (!url || typeof url !== "string") {
    return res.status(400).json({ error: "url is required" });
  }

  try {
    const handle = await tasks.trigger("seo-audit", {
      url,
      max_pages: Number(max_pages),
      single_page: Boolean(single_page),
    });

    return res.status(200).json({ run_id: handle.id });
  } catch (err) {
    console.error("Failed to trigger audit task:", err);
    return res.status(500).json({ error: "Failed to start audit", detail: err.message });
  }
};
