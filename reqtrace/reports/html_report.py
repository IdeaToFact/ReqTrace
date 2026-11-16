# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Interactive Standalone HTML Report Generator for ReqTrace.
Produces a self-contained, zero-external-dependency (100% air-gapped) HTML dashboard.
Includes real-time client-side search, category filtering, coverage metrics, and diff/assertion views.
"""

import html
import json
from pathlib import Path
from typing import Dict, List, Optional
from reqtrace.models.requirement import Requirement
from reqtrace.models.test_artifact import TestArtifact
from reqtrace.models.trace_link import TraceLink
from reqtrace.models.rtm import GapAnalysisResult


class HTMLReportGenerator:
    def generate(
        self,
        requirements: List[Requirement],
        tests: List[TestArtifact],
        links: List[TraceLink],
        gap_result: GapAnalysisResult,
        project_name: str = "Regulated-System",
        standard: str = "DO-178C",
        output_file: Path | str = "rtm_report.html",
    ) -> Path:
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        req_map: Dict[str, Requirement] = {r.id: r for r in requirements}
        test_map: Dict[str, TestArtifact] = {t.id: t for t in tests}
        links_by_req: Dict[str, List[TraceLink]] = {}
        for link in links:
            links_by_req.setdefault(link.req_id, []).append(link)

        # Build rows data structure for frontend search
        rows = []
        for req in requirements:
            req_links = links_by_req.get(req.id, [])
            if not req_links:
                rows.append({
                    "req_id": req.id,
                    "title": req.title,
                    "description": req.description,
                    "level": req.level.value,
                    "is_normative": req.is_normative,
                    "parents": req.parent_ids,
                    "test_id": "[ORPHAN - NO TEST]",
                    "evidence": "",
                    "file_path": "",
                    "line_span": "",
                    "execution_status": "unexecuted",
                    "confidence": "none",
                    "review_status": "pending",
                    "reviewed_by": "",
                    "review_comment": "",
                    "is_stale": False,
                    "is_verified": False,
                    "category": "orphan" if req.is_normative else "informational",
                })
            else:
                for link in req_links:
                    t_art = test_map.get(link.test_id)
                    category = "verified" if link.is_verified else ("stale" if link.is_stale else "unverified")
                    rows.append({
                        "req_id": req.id,
                        "title": req.title,
                        "description": req.description,
                        "level": req.level.value,
                        "is_normative": req.is_normative,
                        "parents": req.parent_ids,
                        "test_id": link.test_id,
                        "evidence": link.evidence_span,
                        "file_path": t_art.file_path if t_art else "",
                        "line_span": f"L{t_art.line_start}-{t_art.line_end}" if t_art else "",
                        "execution_status": t_art.execution_status.value if t_art else "unexecuted",
                        "confidence": link.confidence.value,
                        "review_status": link.review_status.value,
                        "reviewed_by": link.reviewed_by or "",
                        "review_comment": link.review_comment or "",
                        "is_stale": link.is_stale,
                        "is_verified": link.is_verified,
                        "category": category,
                    })

        rows_json = json.dumps(rows, ensure_ascii=False)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ReqTrace RTM Dashboard — {html.escape(project_name)}</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --heading: #f0f6fc;
      --green: #2ea043;
      --red: #da3633;
      --yellow: #d29922;
      --purple: #a371f7;
      --blue: #58a6ff;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
      line-height: 1.5;
    }}
    .container {{ max-width: 1400px; margin: 0 auto; }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }}
    h1 {{ font-size: 24px; color: var(--heading); display: flex; align-items: center; gap: 10px; }}
    .badge {{
      font-size: 12px;
      padding: 3px 8px;
      border-radius: 12px;
      font-weight: 600;
      text-transform: uppercase;
    }}
    .badge-std {{ background: #1f6feb26; color: var(--blue); border: 1px solid var(--blue); }}
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }}
    .card-title {{ font-size: 13px; color: #8b949e; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; }}
    .card-val {{ font-size: 28px; font-weight: 700; color: var(--heading); }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-bottom: 20px;
    }}
    .search-input {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 8px 14px;
      font-size: 14px;
      flex: 1;
      min-width: 250px;
    }}
    .filter-btn {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      transition: all 0.2s;
    }}
    .filter-btn:hover, .filter-btn.active {{
      background: #21262d;
      border-color: var(--blue);
      color: var(--heading);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      font-size: 13px;
    }}
    th {{
      background: #21262d;
      color: var(--heading);
      font-weight: 600;
      text-align: left;
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
    }}
    td {{
      padding: 12px 14px;
      border-bottom: 1px solid #21262d;
      vertical-align: top;
    }}
    tr:hover td {{ background: #1c2128; }}
    .status-tag {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }}
    .status-verified {{ background: #23863626; color: #3fb950; border: 1px solid #238636; }}
    .status-orphan {{ background: #da363326; color: #f85149; border: 1px solid #da3633; }}
    .status-unverified {{ background: #d2992226; color: #e3b341; border: 1px solid #d29922; }}
    .status-stale {{ background: #a371f726; color: #bc8cff; border: 1px solid #a371f7; }}
    .code-span {{
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 12px;
      background: #0d1117;
      padding: 4px 8px;
      border-radius: 4px;
      border: 1px solid #30363d;
      color: #79c0ff;
      display: inline-block;
      margin-top: 4px;
      word-break: break-all;
    }}
    .subtext {{ font-size: 11px; color: #8b949e; margin-top: 4px; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>🎯 ReqTrace RTM Dashboard <span class="badge badge-std">{html.escape(standard)}</span></h1>
        <div class="subtext">Project: <b>{html.escape(project_name)}</b> | Self-Contained Air-Gapped Verification Package</div>
      </div>
      <div style="text-align: right;">
        <span class="badge" style="background: {'#238636' if gap_result.is_passing else '#da3633'}; color: #fff;">
          {'✔ CI AUDIT PASSED' if gap_result.is_passing else '✖ AUDIT FAILED'}
        </span>
      </div>
    </header>

    <div class="metrics-grid">
      <div class="card">
        <div class="card-title">Live Coverage</div>
        <div class="card-val" style="color: {'var(--green)' if gap_result.coverage_percentage >= 95 else 'var(--red)'};">
          {gap_result.coverage_percentage:.1f}%
        </div>
        <div class="subtext">Target: 95.0%</div>
      </div>
      <div class="card">
        <div class="card-title">Normative Reqs</div>
        <div class="card-val">{gap_result.normative_requirements}</div>
        <div class="subtext">Total: {gap_result.total_requirements}</div>
      </div>
      <div class="card">
        <div class="card-title">Live Verified</div>
        <div class="card-val" style="color: var(--green);">{gap_result.covered_requirements}</div>
        <div class="subtext">Passed CI tests</div>
      </div>
      <div class="card">
        <div class="card-title">Orphan Reqs</div>
        <div class="card-val" style="color: {'var(--red)' if gap_result.orphan_requirements else 'var(--text)'};">
          {len(gap_result.orphan_requirements)}
        </div>
        <div class="subtext">Untested / Failing</div>
      </div>
      <div class="card">
        <div class="card-title">Rogue Tests</div>
        <div class="card-val" style="color: {'var(--yellow)' if gap_result.unlinked_tests else 'var(--text)'};">
          {len(gap_result.unlinked_tests)}
        </div>
        <div class="subtext">No req mapping</div>
      </div>
      <div class="card">
        <div class="card-title">Stale Links</div>
        <div class="card-val" style="color: {'var(--purple)' if gap_result.stale_links else 'var(--text)'};">
          {len(gap_result.stale_links)}
        </div>
        <div class="subtext">Modified specs</div>
      </div>
    </div>

    <div class="controls">
      <input type="text" id="searchInput" class="search-input" placeholder="Search requirements, tests, assertions, IDs..." onkeyup="filterRows()">
      <button class="filter-btn active" onclick="setCategoryFilter('all', this)">All Items</button>
      <button class="filter-btn" onclick="setCategoryFilter('verified', this)">Live Verified ({gap_result.covered_requirements})</button>
      <button class="filter-btn" onclick="setCategoryFilter('orphan', this)">Orphans ({len(gap_result.orphan_requirements)})</button>
      <button class="filter-btn" onclick="setCategoryFilter('stale', this)">Stale Revisions ({len(gap_result.stale_links)})</button>
    </div>

    <table>
      <thead>
        <tr>
          <th style="width: 140px;">Requirement ID</th>
          <th>Requirement Specification</th>
          <th style="width: 120px;">Level</th>
          <th style="width: 140px;">Status</th>
          <th>Linked Verification Artifact & Assertion</th>
        </tr>
      </thead>
      <tbody id="matrixBody"></tbody>
    </table>
  </div>

  <script>
    const data = {rows_json};
    let currentCategory = 'all';

    function renderTable(items) {{
      const tbody = document.getElementById('matrixBody');
      if (items.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 30px; color: #8b949e;">No requirements match the selected criteria.</td></tr>';
        return;
      }}
      tbody.innerHTML = items.map(r => {{
        let statusTag = '';
        if (r.is_verified) {{
          statusTag = '<span class="status-tag status-verified">LIVE VERIFIED</span>';
        }} else if (r.category === 'orphan') {{
          statusTag = '<span class="status-tag status-orphan">ORPHAN</span>';
        }} else if (r.is_stale) {{
          statusTag = '<span class="status-tag status-stale">STALE REVISION</span>';
        }} else {{
          statusTag = '<span class="status-tag status-unverified">UNVERIFIED</span>';
        }}

        let parentsHtml = r.parents && r.parents.length ? `<div class="subtext">Allocated From: <b>${{r.parents.join(', ')}}</b></div>` : '';
        let testInfo = r.test_id === '[ORPHAN - NO TEST]'
          ? '<span style="color: #f85149; font-weight: 500;">No test case linked. Verification gap.</span>'
          : `<div><b>${{r.test_id}}</b> <span class="subtext">(${{r.file_path}} ${{r.line_span}})</span></div>` +
            (r.evidence ? `<div class="code-span">${{r.evidence}}</div>` : '') +
            `<div class="subtext">Execution: <b>${{r.execution_status.toUpperCase()}}</b> | Confidence: <b>${{r.confidence.toUpperCase()}}</b></div>`;

        return `<tr>
          <td><b>${{r.req_id}}</b>${{parentsHtml}}</td>
          <td>
            <div style="font-weight: 600; color: #f0f6fc;">${{r.title}}</div>
            <div style="color: #8b949e; font-size: 12px; margin-top: 4px;">${{r.description}}</div>
          </td>
          <td><span class="subtext" style="text-transform: uppercase;">${{r.level}}</span></td>
          <td>${{statusTag}}</td>
          <td>${{testInfo}}</td>
        </tr>`;
      }}).join('');
    }}

    function setCategoryFilter(cat, btn) {{
      currentCategory = cat;
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filterRows();
    }}

    function filterRows() {{
      const query = document.getElementById('searchInput').value.toLowerCase().trim();
      const filtered = data.filter(item => {{
        const matchesCategory = (currentCategory === 'all') || (item.category === currentCategory);
        if (!matchesCategory) return false;
        if (!query) return true;
        const searchCorpus = `${{item.req_id}} ${{item.title}} ${{item.description}} ${{item.test_id}} ${{item.evidence}}`.toLowerCase();
        return searchCorpus.includes(query);
      }});
      renderTable(filtered);
    }}

    // Initial render
    renderTable(data);
  </script>
</body>
</html>
"""
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return out_path

