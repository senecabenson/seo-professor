"""AI Analyzer: formats aggregated audit data into a structured prompt for Claude analysis.

This module does NOT call the Claude API. It prepares the data and prompt
so Claude can analyze it in-session.
"""
import copy
import json
import anthropic


# Plain-English labels for every issue type the audit tools can produce.
# Used in the report template so readers see "Page loads too slowly" instead of "poor_lcp".
# Each entry has:
#   label   — short plain-English name (shown as the issue headline)
#   explain — one sentence defining the term and why it matters (shown as a tooltip/footnote)
ISSUE_LABELS: dict[str, dict[str, str]] = {
    # --- On-Page ---
    "missing_title": {
        "label": "Page has no title",
        "explain": "The title tag is the text that shows up as the blue link in Google search results. Without one, Google doesn't know what your page is about.",
    },
    "title_too_long": {
        "label": "Title is too long",
        "explain": "Google cuts off titles longer than ~60 characters in search results. Visitors can't read the full title, so they may skip your link.",
    },
    "title_too_short": {
        "label": "Title is too short",
        "explain": "A title under 30 characters doesn't give Google enough context about your page's topic, which can hurt your rankings.",
    },
    "missing_meta_description": {
        "label": "Missing page description",
        "explain": "The meta description is the short paragraph shown under your link in Google. Without it, Google picks random text from your page — usually poorly.",
    },
    "description_too_long": {
        "label": "Description is too long",
        "explain": "Google cuts off descriptions over ~160 characters. Your key message gets hidden before visitors can read it.",
    },
    "description_too_short": {
        "label": "Description is too short",
        "explain": "A very short description wastes the space Google gives you to convince people to click your link.",
    },
    "missing_canonical": {
        "label": "Missing 'official page' tag",
        "explain": "A canonical tag tells Google which version of a URL is the 'real' one. Without it, Google might treat similar pages as duplicates and split their ranking power.",
    },
    "missing_h1": {
        "label": "Missing main heading",
        "explain": "Every page should have one H1 — the main headline. It tells Google (and visitors) the single most important topic of the page.",
    },
    "multiple_h1": {
        "label": "Too many main headings",
        "explain": "Having more than one H1 on a page confuses Google about which topic is most important. Think of H1 like a book title — you only need one.",
    },
    "heading_hierarchy_skip": {
        "label": "Heading levels skip a step",
        "explain": "Headings should go H1 → H2 → H3 in order, like an outline. Skipping levels (H1 → H3) confuses both Google and screen readers.",
    },
    "missing_og_tags": {
        "label": "Missing social sharing tags",
        "explain": "Open Graph tags control how your page looks when shared on Facebook, LinkedIn, and iMessage. Without them, shares look broken or generic.",
    },
    "missing_twitter_tags": {
        "label": "Missing Twitter/X card tags",
        "explain": "Twitter Card tags control the preview image and text when someone shares your link on Twitter/X. Without them, posts look like plain links.",
    },
    "noindex_detected": {
        "label": "Page is hidden from Google",
        "explain": "A noindex instruction tells Google 'don't include this page in search results.' If this is unintentional, your page can't rank at all.",
    },
    "nofollow_detected": {
        "label": "Page links are marked no-follow",
        "explain": "Nofollow tells Google not to follow or pass authority through the links on this page. This can unintentionally block your own site from passing ranking power between pages.",
    },
    "low_word_count": {
        "label": "Not enough content",
        "explain": "Pages with very little text (under 300 words) are often seen as 'thin content' by Google, which can hurt rankings. More helpful content = better visibility.",
    },
    # --- Indexation ---
    "noindex_meta": {
        "label": "Page blocked from search via meta tag",
        "explain": "A <meta name='robots' content='noindex'> tag tells Google to skip this page entirely. Confirm this is intentional.",
    },
    "canonical_mismatch": {
        "label": "'Official page' tag points elsewhere",
        "explain": "The canonical tag on this page points to a different URL, telling Google this isn't the real version. Google may ignore this page in rankings.",
    },
    "x_robots_noindex": {
        "label": "Page blocked from search via server header",
        "explain": "The server is sending a noindex signal in the HTTP headers — Google won't index this page. Usually unintentional.",
    },
    "redirect_302": {
        "label": "Temporary redirect (should be permanent)",
        "explain": "A 302 redirect means 'temporarily moved.' Google keeps the original URL in its index instead of updating to the new one. Use 301 for permanent moves.",
    },
    "redirect_301": {
        "label": "Permanent redirect",
        "explain": "A 301 redirect correctly passes ranking power to the new URL. This is usually intentional and healthy.",
    },
    "meta_refresh_redirect": {
        "label": "Old-style page redirect",
        "explain": "Meta refresh redirects are an outdated method that Google doesn't follow as reliably as a proper 301 redirect.",
    },
    "missing_self_hreflang": {
        "label": "Missing language self-reference tag",
        "explain": "Hreflang tags tell Google which language/country each version of your page targets. Missing the self-reference can cause Google to ignore your hreflang setup.",
    },
    "invalid_hreflang_code": {
        "label": "Invalid language code in hreflang",
        "explain": "The language code used in your hreflang tag isn't a valid locale (e.g., 'en-us' should be 'en-US'). Google may ignore it.",
    },
    # --- Links ---
    "broken_link": {
        "label": "Broken link",
        "explain": "This link leads nowhere — clicking it either shows an error or goes to a page that doesn't exist. Broken links frustrate visitors and waste the ranking power you'd otherwise pass to that page.",
    },
    "empty_anchor_text": {
        "label": "Link with no visible text",
        "explain": "Anchor text is the clickable words on a link. If a link has no text (e.g., just an icon), Google can't understand where it leads. Screen readers also can't describe it to blind visitors.",
    },
    "poor_anchor_text": {
        "label": "Unhelpful link text",
        "explain": "Link text like 'click here' or 'read more' tells Google nothing about the destination page. Descriptive text like 'see our backdrop gallery' is much stronger.",
    },
    "no_internal_links": {
        "label": "No links to other pages on your site",
        "explain": "Internal links help Google discover your other pages and understand how your content connects. A page with no internal links is like a dead end.",
    },
    "no_links": {
        "label": "Page has no links at all",
        "explain": "A page with no links — internal or external — is completely isolated. Google can't use it to discover more of your site.",
    },
    # --- Images ---
    "missing_alt": {
        "label": "Image has no description",
        "explain": "Alt text is the written description of an image. Google can't 'see' images, so alt text tells it what's in the photo. It also helps blind visitors using screen readers.",
    },
    "filename_alt": {
        "label": "Image description looks like a filename",
        "explain": "Alt text like 'IMG_4923.jpg' is meaningless to Google. Write a real description: 'Ivory sequin backdrop rental for weddings.'",
    },
    "non_modern_format": {
        "label": "Image not in the fastest format",
        "explain": "WebP and AVIF are newer image formats that load up to 30% faster than JPG or PNG at the same quality. Faster images = better Google rankings and happier visitors.",
    },
    "missing_lazy_load": {
        "label": "Images load before visitors can see them",
        "explain": "Lazy loading tells the browser to wait and only load images when a visitor scrolls close to them. Without it, all images load at once, slowing your page down.",
    },
    "missing_dimensions": {
        "label": "Image size not declared",
        "explain": "When images don't have width/height set in the code, the page 'jumps' as images load in — this is called layout shift and Google penalizes it.",
    },
    "large_base64": {
        "label": "Image embedded directly in code (too large)",
        "explain": "Base64 images are baked into your HTML instead of loaded separately. Large ones bloat your page's code and slow down the initial load.",
    },
    # --- Security ---
    "http_url": {
        "label": "Page not using secure HTTPS",
        "explain": "HTTPS encrypts data between your site and visitors. Pages using plain HTTP are flagged as 'Not Secure' by browsers and ranked lower by Google.",
    },
    "mixed_content": {
        "label": "Insecure content on a secure page",
        "explain": "Mixed content means your HTTPS page loads some resources (images, scripts) over insecure HTTP. Browsers may block these, breaking your page.",
    },
    "missing_security_header": {
        "label": "Missing website security setting",
        "explain": "Security headers are server instructions that protect visitors from attacks like clickjacking and cross-site scripting. Missing ones leave your site more vulnerable.",
    },
    # --- Core Web Vitals (CWV) ---
    "poor_lcp": {
        "label": "Page takes too long to load",
        "explain": "LCP (Largest Contentful Paint) measures how long it takes for the main content to appear on screen. Google's passing grade is under 2.5 seconds. Slow pages rank lower and lose visitors.",
    },
    "needs_improvement_lcp": {
        "label": "Page load speed needs improvement",
        "explain": "LCP is between 2.5–4 seconds — Google's 'needs improvement' zone. You're not being penalized yet, but you're not getting the speed bonus either.",
    },
    "poor_tbt": {
        "label": "Page is unresponsive while loading",
        "explain": "TBT (Total Blocking Time) measures how long your page freezes and won't respond to clicks while loading. High TBT means visitors can't interact with your site until JavaScript finishes running.",
    },
    "needs_improvement_tbt": {
        "label": "Page responsiveness needs improvement",
        "explain": "TBT is in Google's 'needs improvement' range. The page occasionally freezes during load, which hurts user experience scores.",
    },
    "poor_cls": {
        "label": "Page content jumps around while loading",
        "explain": "CLS (Cumulative Layout Shift) measures how much your page's content moves around while loading. High CLS means visitors accidentally click the wrong thing — and Google penalizes it.",
    },
    "needs_improvement_cls": {
        "label": "Page layout shifts need improvement",
        "explain": "CLS is in Google's 'needs improvement' range — some content movement is happening during load, but it's not yet severe.",
    },
    "api_error": {
        "label": "Could not measure page speed",
        "explain": "The PageSpeed measurement tool returned an error for this page. Speed scores couldn't be calculated — check if the page is publicly accessible.",
    },
    # --- JavaScript Rendering ---
    "empty_body_or_spa_root": {
        "label": "Page content requires JavaScript to appear",
        "explain": "The page's HTML is empty until JavaScript runs. Google can index JS-rendered content, but it's slower and less reliable than content in the initial HTML.",
    },
    "very_heavy_scripts": {
        "label": "Extremely large JavaScript files",
        "explain": "Your page loads a very large amount of JavaScript code. This significantly slows down the page for visitors, especially on mobile.",
    },
    "heavy_scripts": {
        "label": "Large JavaScript files",
        "explain": "Your page loads more JavaScript than recommended. Extra scripts slow the page and delay when visitors can start clicking and scrolling.",
    },
    "deprecated_fragment_meta": {
        "label": "Using outdated JavaScript rendering hint",
        "explain": "The _escaped_fragment_ meta tag is an old way of helping Google index JavaScript pages. Google no longer uses it — it's just unnecessary code now.",
    },
    "no_noscript_fallback": {
        "label": "No backup for visitors without JavaScript",
        "explain": "A <noscript> tag shows content to visitors whose browsers can't run JavaScript. Without it, those visitors see a blank page.",
    },
    "low_content_to_script_ratio": {
        "label": "Too much code, too little content",
        "explain": "Your page has far more JavaScript code than actual content. This often means the page is script-heavy from a website builder platform and can slow load times.",
    },
    # --- Structured Data ---
    "no_structured_data": {
        "label": "No data labels for Google",
        "explain": "Structured data (JSON-LD) is hidden code that describes your business to Google — what you sell, your reviews, your hours. It powers rich results (star ratings, FAQs) in search and feeds AI search answers.",
    },
    "invalid_json_ld": {
        "label": "Data labels have errors",
        "explain": "Your structured data code exists but has syntax errors, so Google can't read it. It won't appear in rich results until fixed.",
    },
    "missing_schema_property": {
        "label": "Data labels are missing key details",
        "explain": "Your structured data is missing required fields (like a business address or phone number). Incomplete data labels reduce your chances of appearing in rich results.",
    },
    "no_ai_bot_governance": {
        "label": "No instructions for AI search bots",
        "explain": "Your robots.txt file doesn't include rules for AI crawlers like GPTBot (ChatGPT) or Google-Extended. Without them, you have no control over whether AI tools scrape your content.",
    },
    # --- Authority / E-E-A-T ---
    "no_author_attribution": {
        "label": "No author credited on this content",
        "explain": "Google's quality guidelines (E-E-A-T) reward content written by identifiable, credible people. No author name signals lower trust, especially for professional service businesses.",
    },
    "no_about_link": {
        "label": "No link to an About page",
        "explain": "An About page is a basic trust signal. Google's quality reviewers look for it. If visitors and Google can't learn who you are, they trust you less.",
    },
    "no_contact_link": {
        "label": "No link to a Contact page",
        "explain": "A Contact page signals that a real business is behind the site. Missing it reduces trust with both Google and potential customers.",
    },
    "no_privacy_link": {
        "label": "No Privacy Policy link",
        "explain": "A Privacy Policy is legally required in many jurisdictions and shows visitors you handle their data responsibly. Google also uses it as a trust signal.",
    },
    "no_social_links": {
        "label": "No links to social media profiles",
        "explain": "Social media links help Google connect your website to your broader online presence, reinforcing that you're a real, active business.",
    },
    "trust_bottleneck": {
        "label": "Unverified claim may reduce AI trust",
        "explain": "Words like 'best' or 'top-rated' without supporting data (reviews, statistics) are red flags for AI search engines evaluating whether to cite your content.",
    },
    # --- AEO (AI Engine Optimization) ---
    "no_direct_answers": {
        "label": "Content doesn't directly answer questions",
        "explain": "AI search engines (ChatGPT, Perplexity, Google AI Overviews) prefer content that directly answers questions in clear sentences. 'X is...' or 'To do X, you...' patterns make your content easy to cite.",
    },
    "no_structured_content": {
        "label": "Content isn't organized for AI extraction",
        "explain": "AI engines extract information from well-structured content — clear headings, short paragraphs, bullet lists. Dense, unstructured text is harder to cite.",
    },
    "no_question_headings": {
        "label": "No question-format headings",
        "explain": "Headings like 'What backdrops do you offer?' or 'How does booking work?' match exactly how people ask questions to AI search. They increase your chances of appearing in AI answers.",
    },
    "no_citation_signals": {
        "label": "No statistics or verifiable facts",
        "explain": "AI engines prefer to cite content with specific, verifiable data (numbers, dates, named sources). Content with no data points is harder for AI to trust and quote.",
    },
    "no_date_signals": {
        "label": "No dates or freshness signals",
        "explain": "AI search engines favor recently updated content. If your pages show no dates or timestamps, AI tools assume the content might be outdated.",
    },
    "no_llms_txt": {
        "label": "No AI crawler guide file",
        "explain": "An llms.txt file (like robots.txt but for AI) tells AI tools which pages are most important and how you want your content represented in AI answers.",
    },
    "generic_meta_description": {
        "label": "Page description is too generic for AI",
        "explain": "AI engines use your meta description to summarize your page in search answers. A generic description ('Welcome to our site') won't get you cited.",
    },
    "no_meta_description_for_aeo": {
        "label": "Missing description for AI search",
        "explain": "Without a meta description, AI search engines have no concise summary to pull for your page. They'll either skip it or generate their own, which may be inaccurate.",
    },
}


def _build_prompt(data: dict, domain: str, business_context: dict | None = None) -> str:
    """Build a structured analysis prompt from aggregated audit data."""
    sev = data.get("severity_counts", {})
    total_issues = sum(sev.values())
    business_context = business_context or {}

    lines = [
        "# SEO Audit Analysis Request",
        "",
        "## Site Overview",
        f"- Domain: {domain}",
        f"- Pages Audited: {data.get('pages_audited', 0)}",
        f"- Overall Score: {data.get('site_score', 0)}/100",
        f"- Issues Found: {total_issues} "
        f"({sev.get('critical', 0)} critical, {sev.get('high', 0)} high, "
        f"{sev.get('medium', 0)} medium, {sev.get('low', 0)} low)",
        "",
    ]

    # Business context (if provided)
    if business_context:
        lines.append("## Business Context")
        if business_context.get("business_type"):
            lines.append(f"- Business Type: {business_context['business_type']}")
        if business_context.get("locations"):
            lines.append(f"- Target Location(s): {', '.join(business_context['locations'])}")
        if business_context.get("target_keywords"):
            lines.append("- Target Keywords:")
            for kw in business_context["target_keywords"]:
                lines.append(f"  - {kw}")
        lines.extend([
            "",
            "Use this business context to:",
            "1. Evaluate whether the site's content, titles, and meta descriptions reflect the business type and locations.",
            "2. Cross-reference target keywords against GSC data (if present) to identify ranking gaps.",
            "3. Recommend location-specific pages that should exist but don't (e.g. '/san-diego-photo-booth-rental/').",
            "4. Flag pages that mention the wrong city, wrong service, or miss key local keywords.",
            "",
        ])

    # Top issues
    top_issues = data.get("top_issues", [])
    if top_issues:
        lines.append("## Top Issues (by frequency)")
        for i, issue in enumerate(top_issues, 1):
            lines.append(
                f"{i}. {issue['type']} — found on {issue['count']} pages "
                f"(severity: {issue['severity']})"
            )
        lines.append("")

    # Worst pages
    worst_pages = data.get("worst_pages", [])
    if worst_pages:
        lines.append("## Worst Performing Pages")
        for i, page in enumerate(worst_pages, 1):
            lines.append(
                f"{i}. {page['url']} — Score: {page['score']}/100, "
                f"{page['issue_count']} issues"
            )
        lines.append("")

    # Tool summaries
    tool_summaries = data.get("tool_summaries", {})
    if tool_summaries:
        lines.append("## Tool Performance Summary")
        lines.append("| Tool | Avg Score | Issues |")
        lines.append("|------|-----------|--------|")
        for tool, stats in tool_summaries.items():
            lines.append(f"| {tool} | {stats['avg_score']} | {stats['issue_count']} |")
        lines.append("")

    # Detailed page data (up to 10 worst)
    pages = data.get("pages", {})
    if pages:
        # Sort by score ascending to get worst first
        sorted_urls = sorted(pages, key=lambda u: pages[u]["score"])
        detail_urls = sorted_urls[:10]

        lines.append("## Detailed Page Data")
        for url in detail_urls:
            p = pages[url]
            lines.append(f"\n### {url}")
            lines.append(f"- Score: {p['score']}/100")
            lines.append(f"- Issues: {p['issue_count']}")
            if p.get("issues"):
                for issue in p["issues"]:
                    lines.append(
                        f"  - [{issue['severity'].upper()}] {issue['type']}: "
                        f"{issue['detail']}"
                    )
        lines.append("")

    # Instructions
    lines.extend([
        "## Writing Style",
        "Write everything at a 9th grade reading level. You are the SEO Professor — your job",
        "is to teach, not just diagnose. Follow these rules for every sentence you write:",
        "- Define every technical term the FIRST time you use it, in plain English, right after",
        "  the term. Example: 'LCP (how fast your main content appears on screen for visitors)'",
        "- Frame every issue in terms of real consequences for the business:",
        "  'This is slowing your page, which causes visitors to leave before they book.'",
        "- Use 'you / your site / your visitors' — not passive voice or third person.",
        "- Never use unexplained jargon. Terms that must always be defined when used:",
        "  LCP, CLS, TBT, CWV, JSON-LD, canonical tag, structured data, E-E-A-T, AEO,",
        "  hreflang, noindex, nofollow, robots.txt, meta description, schema, HTTPS, TLS,",
        "  CSP, HSTS, lazy load, alt text, anchor text, redirect, crawl budget.",
        "- For 'effort' and 'impact' ratings, add a plain-English note:",
        "  effort=low means 'about 15 minutes to fix', effort=medium means 'an hour or two',",
        "  effort=high means 'a developer project.'",
        "",
        "## Instructions",
        "Analyze this SEO audit data and provide your response as JSON with these exact keys:",
        '- "executive_summary": 3-5 sentences summarizing the site\'s SEO health',
        '- "priority_fixes": list of {"issue": str, "effort": "low|medium|high", '
        '"impact": "low|medium|high", "description": str}',
        '- "category_analysis": dict of tool_name -> {"score": int, "assessment": str, '
        '"key_issues": [str]}',
        '- "recommendations": list of {"action": str, "priority": int (1=highest), '
        '"rationale": str}',
    ])

    return "\n".join(lines)


def _build_structured_input(data: dict) -> dict:
    """Build a clean, JSON-serializable copy of the aggregated data.

    For large sites (100+ pages), trims pages to the 10 worst.
    """
    result = copy.deepcopy(data)
    pages = result.get("pages", {})

    if result.get("pages_audited", 0) > 100 and len(pages) > 10:
        # Keep only 10 worst pages
        sorted_urls = sorted(pages, key=lambda u: pages[u]["score"])
        worst_10 = sorted_urls[:10]
        result["pages"] = {url: pages[url] for url in worst_10}
        result["pages_trimmed"] = True
        result["pages_included"] = 10

    return result


def format_for_analysis(aggregated_data: dict, domain: str, business_context: dict | None = None) -> dict:
    """Format aggregated audit data into a prompt and structured input for Claude.

    Args:
        aggregated_data: Output from src.aggregator.aggregate().
        domain: The domain being audited.
        business_context: Optional dict with business_type, locations, target_keywords.

    Returns:
        Dict with "prompt" (str) and "structured_input" (dict).
    """
    return {
        "prompt": _build_prompt(aggregated_data, domain, business_context or {}),
        "structured_input": _build_structured_input(aggregated_data),
    }


def analyze_with_claude(prompt: str, api_key: str) -> dict:
    """Call the Claude API with the audit prompt and return structured analysis.

    Used in automated mode (e.g. Trigger.dev) when ANTHROPIC_API_KEY is set.
    When running locally through Claude Code, skip this — Claude Code handles
    analysis in-session and writes .tmp/ai_analysis.json directly.

    Args:
        prompt: The formatted audit prompt from _build_prompt().
        api_key: Anthropic API key.

    Returns:
        Dict with keys: executive_summary, priority_fixes, category_analysis, recommendations.
        Falls back to a default analysis dict if the response cannot be parsed.
    """
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text

    # Strip ```json ... ``` fences if present
    if raw.strip().startswith("```"):
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {
            "executive_summary": "AI analysis could not be parsed. Review audit data manually.",
            "priority_fixes": [],
            "category_analysis": {},
            "recommendations": [],
        }
