-- sites
CREATE TABLE IF NOT EXISTS sites (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    domain text UNIQUE NOT NULL,
    name text,
    created_at timestamptz DEFAULT now(),
    metadata jsonb DEFAULT '{}'::jsonb
);

-- audit_runs
CREATE TABLE IF NOT EXISTS audit_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id uuid REFERENCES sites(id) ON DELETE CASCADE,
    started_at timestamptz DEFAULT now(),
    completed_at timestamptz,
    status text NOT NULL DEFAULT 'running',
    pages_crawled int DEFAULT 0,
    overall_score int,
    summary jsonb DEFAULT '{}'::jsonb
);

-- page_results
CREATE TABLE IF NOT EXISTS page_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_run_id uuid REFERENCES audit_runs(id) ON DELETE CASCADE,
    url text NOT NULL,
    status_code int,
    html_hash text,
    crawled_at timestamptz DEFAULT now()
);

-- audit_findings
CREATE TABLE IF NOT EXISTS audit_findings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    page_result_id uuid REFERENCES page_results(id) ON DELETE CASCADE,
    tool text NOT NULL,
    severity text NOT NULL,
    issue_type text NOT NULL,
    detail text,
    data jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now()
);

-- reports
CREATE TABLE IF NOT EXISTS reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_run_id uuid REFERENCES audit_runs(id) ON DELETE CASCADE,
    ai_analysis text,
    recommendations jsonb DEFAULT '[]'::jsonb,
    report_url text,
    generated_at timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_audit_runs_site_id ON audit_runs(site_id);
CREATE INDEX IF NOT EXISTS idx_page_results_audit_run_id ON page_results(audit_run_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_page_result_id ON audit_findings(page_result_id);
CREATE INDEX IF NOT EXISTS idx_sites_domain ON sites(domain);
