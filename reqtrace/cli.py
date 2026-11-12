# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
ReqTrace Command Line Interface.
Built with Typer and Rich for offline-first safety verification.
"""

import json
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.table import Table

import reqtrace
from reqtrace.config import load_config
from reqtrace.models.requirement import Requirement
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus
from reqtrace.models.trace_link import TraceLink
from reqtrace.parsers.csv_parser import CSVParser
from reqtrace.parsers.docx_parser import DocxSpecificationParser
from reqtrace.parsers.junit_parser import JUnitParser
from reqtrace.parsers.reqif_parser import ReqIFParser
from reqtrace.parsers.code.python_ast import PythonASTParser
from reqtrace.parsers.code.cpp_harness import CppHarnessParser
from reqtrace.parsers.code.gherkin import GherkinFeatureParser
from reqtrace.analysis.review_store import ReviewStore
from reqtrace.models.trace_link import ReviewEvent, ReviewStatus
from reqtrace.engine.linker import TraceLinker
from reqtrace.reports.csv_exporter import CSVRTMExporter
from reqtrace.reports.html_report import HTMLReportGenerator
from reqtrace.reports.reqif_exporter import ReqIFExporter
from reqtrace.analysis.gap_auditor import GapAuditor
from reqtrace.analysis.diff_engine import SpecDiffEngine

app = typer.Typer(
    name="reqtrace",
    help="ReqTrace: Grounded Requirements Traceability & Audit Gap Copilot",
    add_completion=False,
)
console = Console()


@app.command()
def version() -> None:
    """Print the version of ReqTrace."""
    console.print(f"[bold green]ReqTrace[/bold green] version [cyan]{reqtrace.__version__}[/cyan] (GNU AGPLv3 Community Edition)")


@app.command()
def init(
    config_path: Path = typer.Option(
        Path("reqtrace.toml"), "--config", "-c", help="Path to config file"
    )
) -> None:
    """Initialize a default reqtrace.toml configuration file and .gitattributes merge rules."""
    if config_path.exists():
        console.print(f"[yellow]Notice:[/yellow] {config_path} already exists.")
    else:
        _ = load_config()
        console.print(f"[green]Initialized[/green] default ReqTrace configuration at {config_path}")

    gitattr_path = Path(".gitattributes")
    if not gitattr_path.exists():
        gitattr_path.write_text(".reqtrace/*.jsonl merge=union\n*.jsonl merge=union\n", encoding="utf-8")
        console.print("[green]Created[/green] .gitattributes with union merge strategy for review logs.")


@app.command()
def ingest(
    spec_file: Path = typer.Argument(..., help="Path to ReqIF or CSV specification file"),
    format_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Format type: 'reqif' or 'csv' (auto-detected if omitted)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o", "--out", help="Output JSON path (defaults to requirements.json)"
    ),
) -> None:
    """
    [Milestone 1] Ingest requirements from ReqIF XML or CSV specification matrices.
    """
    if not spec_file.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {spec_file}")
        raise typer.Exit(code=1)

    ext = spec_file.suffix.lower()
    if format_type:
        ftype = format_type.lower()
    elif ext in {".reqif", ".xml"}:
        ftype = "reqif"
    elif ext in {".docx"}:
        ftype = "docx"
    else:
        ftype = "csv"

    cfg = load_config()
    requirements: List[Requirement] = []

    if ftype in {"reqif", "xml"}:
        parser = ReqIFParser(cfg.reqif_mapping)
        requirements = parser.parse(spec_file)
    elif ftype in {"csv", "tsv"}:
        parser = CSVParser()
        requirements = parser.parse(spec_file)
    elif ftype in {"docx", "word"}:
        parser = DocxSpecificationParser()
        requirements = parser.parse(spec_file)
    else:
        console.print(f"[bold red]Error:[/bold red] Unsupported format: {ftype}. Use 'reqif', 'docx', or 'csv'.")
        raise typer.Exit(code=1)

    out_path = output_file or Path("requirements.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in requirements], f, indent=2)

    table = Table(title=f"Ingestion Summary: {spec_file.name}", border_style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    normative_count = sum(1 for r in requirements if r.is_normative)
    with_parents = sum(1 for r in requirements if r.parent_ids)

    table.add_row("Total Requirements", str(len(requirements)))
    table.add_row("Normative Requirements", f"[green]{normative_count}[/green]")
    table.add_row("Informational / Headings", f"[yellow]{len(requirements) - normative_count}[/yellow]")
    table.add_row("Hierarchical Allocations", f"[cyan]{with_parents}[/cyan]")
    table.add_row("Saved JSON To", str(out_path))

    console.print(table)


@app.command()
def scan(
    test_dir: Path = typer.Argument(..., help="Directory or file containing test cases"),
    junit: Optional[Path] = typer.Option(
        None, "--junit", "-j", help="Optional JUnit XML report to attach live test verdicts"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o", "--out", help="Output JSON path (defaults to tests.json)"
    ),
) -> None:
    """
    [Milestones 2 & 3] Scan Python test cases and attach dynamic JUnit execution verdicts.
    """
    if not test_dir.exists():
        console.print(f"[bold red]Error:[/bold red] Test path not found: {test_dir}")
        raise typer.Exit(code=1)

    cfg = load_config()
    ast_parser = PythonASTParser()
    cpp_parser = CppHarnessParser(cfg.parsers.cpp)
    gherkin_parser = GherkinFeatureParser()
    artifacts: List[TestArtifact] = []

    cpp_exts = {".cpp", ".cc", ".cxx", ".c"}
    if test_dir.is_dir():
        artifacts.extend(ast_parser.parse_directory(test_dir))
        artifacts.extend(cpp_parser.parse_directory(test_dir))
        artifacts.extend(gherkin_parser.parse_directory(test_dir))
    else:
        ext = test_dir.suffix.lower()
        if ext in cpp_exts:
            artifacts.extend(cpp_parser.parse_file(test_dir))
        elif ext == ".feature":
            artifacts.extend(gherkin_parser.parse_file(test_dir))
        else:
            artifacts.extend(ast_parser.parse_file(test_dir))

    if junit:
        if junit.exists():
            junit_parser = JUnitParser()
            artifacts = junit_parser.attach_verdicts(artifacts, junit)
        else:
            console.print(f"[yellow]Warning:[/yellow] JUnit report {junit} not found. Skipping execution verdicts.")

    out_path = output_file or Path("tests.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([a.model_dump() for a in artifacts], f, indent=2)

    table = Table(title=f"Test Suite Scan Summary: {test_dir}", border_style="magenta")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    tagged_count = sum(1 for a in artifacts if a.declared_req_refs)
    assertions_count = sum(len(a.assertion_statements) for a in artifacts)
    passed_count = sum(1 for a in artifacts if a.execution_status == TestExecutionStatus.PASSED)
    failed_count = sum(1 for a in artifacts if a.execution_status == TestExecutionStatus.FAILED)
    skipped_count = sum(1 for a in artifacts if a.execution_status == TestExecutionStatus.SKIPPED)

    table.add_row("Total Test Functions", str(len(artifacts)))
    table.add_row("Tests with Declared Requirement Tags", f"[cyan]{tagged_count}[/cyan]")
    table.add_row("Affirmative Assertions Extracted", str(assertions_count))
    if junit and junit.exists():
        table.add_row("Passed Tests", f"[green]{passed_count}[/green]")
        table.add_row("Failed Tests", f"[red]{failed_count}[/red]" if failed_count else "0")
        table.add_row("Skipped Tests", f"[yellow]{skipped_count}[/yellow]" if skipped_count else "0")
    table.add_row("Saved JSON To", str(out_path))

    console.print(table)


@app.command()
def link(
    reqs_file: Path = typer.Option(
        Path("requirements.json"), "--reqs", "-r", help="Path to requirements JSON"
    ),
    tests_file: Path = typer.Option(
        Path("tests.json"), "--tests", "-t", help="Path to tests JSON"
    ),
    output_csv: Path = typer.Option(
        Path("trace_matrix.csv"), "--output", "-o", "--out", help="Output path for RTM CSV"
    ),
    output_json: Optional[Path] = typer.Option(
        None, "--json", help="Optional output path for links JSON"
    ),
) -> None:
    """
    [Milestone 4] Generate live Requirements Traceability Matrix (RTM).
    """
    if not reqs_file.exists():
        console.print(f"[bold red]Error:[/bold red] Requirements file not found: {reqs_file}. Run 'reqtrace ingest' first.")
        raise typer.Exit(code=1)
    if not tests_file.exists():
        console.print(f"[bold red]Error:[/bold red] Tests file not found: {tests_file}. Run 'reqtrace scan' first.")
        raise typer.Exit(code=1)

    with open(reqs_file, "r", encoding="utf-8") as f:
        req_dicts = json.load(f)
        requirements = [Requirement.model_validate(r) for r in req_dicts]

    with open(tests_file, "r", encoding="utf-8") as f:
        test_dicts = json.load(f)
        tests = [TestArtifact.model_validate(t) for t in test_dicts]

    cfg = load_config()
    linker = TraceLinker(
        high_threshold=cfg.thresholds.high_confidence_threshold,
        medium_threshold=cfg.thresholds.medium_confidence_threshold,
    )
    links = linker.link(requirements, tests)

    # Export CSV
    exporter = CSVRTMExporter()
    exporter.export(requirements, links, output_csv)

    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump([l.model_dump() for l in links], f, indent=2)

    table = Table(title="Trace Link Generation Summary", border_style="green")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    verified_count = sum(1 for l in links if l.is_verified)
    stale_count = sum(1 for l in links if l.is_stale)

    table.add_row("Total Generated Links", str(len(links)))
    table.add_row("Live Verified Links (Passed CI)", f"[green]{verified_count}[/green]")
    table.add_row("Unverified Links (Failed/Unexecuted)", f"[yellow]{len(links) - verified_count}[/yellow]")
    table.add_row("Stale Links (Modified Reqs)", f"[red]{stale_count}[/red]" if stale_count else "0")
    table.add_row("Exported Matrix CSV", str(output_csv))

    console.print(table)


@app.command()
def check(
    reqs_file: Path = typer.Option(
        Path("requirements.json"), "--reqs", "-r", help="Path to requirements JSON"
    ),
    tests_file: Path = typer.Option(
        Path("tests.json"), "--tests", "-t", help="Path to tests JSON"
    ),
    min_coverage: Optional[float] = typer.Option(
        None, "--min-coverage", help="Minimum required coverage percentage (overrides config)"
    ),
) -> None:
    """
    [Milestone 5] Run bidirectional orphan detection and CI/CD quality gating.
    """
    if not reqs_file.exists() or not tests_file.exists():
        console.print("[bold red]Error:[/bold red] Missing requirements.json or tests.json. Run ingest and scan first.")
        raise typer.Exit(code=1)

    with open(reqs_file, "r", encoding="utf-8") as f:
        requirements = [Requirement.model_validate(r) for r in json.load(f)]
    with open(tests_file, "r", encoding="utf-8") as f:
        tests = [TestArtifact.model_validate(t) for t in json.load(f)]

    cfg = load_config()
    thresholds = cfg.thresholds.model_copy()
    if min_coverage is not None:
        thresholds.min_coverage_pct = min_coverage

    linker = TraceLinker(
        high_threshold=thresholds.high_confidence_threshold,
        medium_threshold=thresholds.medium_confidence_threshold,
    )
    links = linker.link(requirements, tests)

    auditor = GapAuditor(thresholds)
    gap_result = auditor.analyze(requirements, tests, links)

    table = Table(title="Bidirectional Gap & Audit Summary", border_style="bright_blue")
    table.add_column("Audit Metric", style="bold")
    table.add_column("Result", justify="right")

    cov_style = "green" if gap_result.coverage_percentage >= thresholds.min_coverage_pct else "red"
    table.add_row("Total Normative Requirements", str(gap_result.normative_requirements))
    table.add_row("Live Verified Requirements", f"[green]{gap_result.covered_requirements}[/green]")
    table.add_row("Coverage Percentage", f"[{cov_style}]{gap_result.coverage_percentage:.1f}%[/{cov_style}] (Min: {thresholds.min_coverage_pct:.1f}%)")
    table.add_row("Orphan Requirements (No Passing Test)", f"[red]{len(gap_result.orphan_requirements)}[/red]" if gap_result.orphan_requirements else "[green]0[/green]")
    table.add_row("Unlinked / Rogue Tests", f"[yellow]{len(gap_result.unlinked_tests)}[/yellow]" if gap_result.unlinked_tests else "0")
    table.add_row("Failing Tests in CI", f"[red]{len(gap_result.failed_tests)}[/red]" if gap_result.failed_tests else "[green]0[/green]")
    table.add_row("Stale Trace Links", f"[red]{len(gap_result.stale_links)}[/red]" if gap_result.stale_links else "0")
    console.print(table)

    if not gap_result.is_passing:
        console.print("\n[bold red]✖ CI QUALITY GATE FAILED:[/bold red]")
        for err in gap_result.gating_errors:
            console.print(f"  • [red]{err}[/red]")
        raise typer.Exit(code=1)
    else:
        console.print("\n[bold green]✔ CI QUALITY GATE PASSED:[/bold green] All requirements verified, zero orphan gaps.")


@app.command()
def diff(
    old_spec: Path = typer.Argument(..., help="Path to original specification (v1)"),
    new_spec: Path = typer.Argument(..., help="Path to revised specification (v2)"),
    format_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Format type: 'reqif' or 'csv' (auto-detected if omitted)"
    ),
) -> None:
    """
    [Milestone 6] Specification diff engine. Detects added, removed, and modified requirements across revisions.
    """
    if not old_spec.exists() or not new_spec.exists():
        console.print("[bold red]Error:[/bold red] Both specification files must exist.")
        raise typer.Exit(code=1)

    cfg = load_config()

    def parse_spec(p: Path) -> List[Requirement]:
        ext = p.suffix.lower()
        ftype = (format_type or ("reqif" if ext in {".reqif", ".xml"} else "csv")).lower()
        if ftype in {"reqif", "xml"}:
            return ReqIFParser(cfg.reqif_mapping).parse(p)
        return CSVParser().parse(p)

    old_reqs = parse_spec(old_spec)
    new_reqs = parse_spec(new_spec)

    diff_engine = SpecDiffEngine()
    diff_res = diff_engine.compare(old_reqs, new_reqs, old_name=old_spec.name, new_name=new_spec.name)

    table = Table(title=f"Specification Drift: {old_spec.name} ➔ {new_spec.name}", border_style="yellow")
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("Unchanged Requirements", f"[green]{diff_res.unchanged_count}[/green]")
    table.add_row("Added Requirements", f"[cyan]{len(diff_res.added)}[/cyan]")
    table.add_row("Modified Requirements", f"[yellow]{len(diff_res.modified)}[/yellow]" if diff_res.modified else "0")
    table.add_row("Removed / Deprecated Requirements", f"[red]{len(diff_res.removed)}[/red]" if diff_res.removed else "0")
    table.add_row("Invalidated (Stale) Trace Links", f"[red]{len(diff_res.stale_req_ids)}[/red]" if diff_res.stale_req_ids else "[green]0[/green]")
    console.print(table)

    if diff_res.modified:
        mod_table = Table(title="Modified Requirement Details", border_style="dim yellow")
        mod_table.add_column("ID", style="bold")
        mod_table.add_column("Detected Changes")
        for m in diff_res.modified:
            mod_table.add_row(m.req_id, ", ".join(m.changes))
        console.print(mod_table)


@app.command(name="audit-summary")
def audit_summary(
    reqs_file: Path = typer.Option(
        Path("requirements.json"), "--reqs", "-r", help="Path to requirements JSON"
    ),
    tests_file: Path = typer.Option(
        Path("tests.json"), "--tests", "-t", help="Path to tests JSON"
    ),
) -> None:
    """
    [Executive / Manager View] High-level audit status and gap metrics dashboard.
    """
    if not reqs_file.exists() or not tests_file.exists():
        console.print("[bold red]Error:[/bold red] Missing requirements.json or tests.json. Run ingest and scan first.")
        raise typer.Exit(code=1)

    with open(reqs_file, "r", encoding="utf-8") as f:
        requirements = [Requirement.model_validate(r) for r in json.load(f)]
    with open(tests_file, "r", encoding="utf-8") as f:
        tests = [TestArtifact.model_validate(t) for t in json.load(f)]

    cfg = load_config()
    linker = TraceLinker(
        high_threshold=cfg.thresholds.high_confidence_threshold,
        medium_threshold=cfg.thresholds.medium_confidence_threshold,
    )
    links = linker.link(requirements, tests)

    auditor = GapAuditor(cfg.thresholds)
    gap_result = auditor.analyze(requirements, tests, links)

    # Executive Manager Card
    status_color = "bold green" if gap_result.is_passing else "bold red"
    status_label = "PASS (Audit Ready)" if gap_result.is_passing else "FAIL (Action Required)"

    console.print(f"\n[{status_color}]==================================================[/{status_color}]")
    console.print(f"  [bold]ReqTrace Executive Audit Summary[/bold] — [cyan]{cfg.project.standard}[/cyan]")
    console.print(f"  Project: [bold]{cfg.project.name}[/bold] (v{cfg.project.version})")
    console.print(f"[{status_color}]==================================================[/{status_color}]\n")

    console.print(f"  Total Requirements:       [bold]{gap_result.total_requirements:,}[/bold]")
    console.print(f"  Normative Requirements:   [bold]{gap_result.normative_requirements:,}[/bold]")
    console.print(f"  Live Verified:            [bold green]{gap_result.covered_requirements:,}[/bold green]")
    console.print(f"  Unverified Gaps:          [bold {'red' if gap_result.normative_requirements - gap_result.covered_requirements else 'green'}]{gap_result.normative_requirements - gap_result.covered_requirements:,}[/bold {'red' if gap_result.normative_requirements - gap_result.covered_requirements else 'green'}]")
    console.print(f"  Orphans (No Test):        [bold {'red' if gap_result.orphan_requirements else 'green'}]{len(gap_result.orphan_requirements):,}[/bold {'red' if gap_result.orphan_requirements else 'green'}]")
    console.print(f"  Failed-Test Requirements: [bold {'red' if gap_result.failed_tests else 'green'}]{len(gap_result.failed_tests):,}[/bold {'red' if gap_result.failed_tests else 'green'}]")
    console.print(f"  Unlinked Rogue Tests:     [bold yellow]{len(gap_result.unlinked_tests):,}[/bold yellow]")
    console.print(f"  Stale Revisions:          [bold {'purple' if gap_result.stale_links else 'green'}]{len(gap_result.stale_links):,}[/bold {'purple' if gap_result.stale_links else 'green'}]")
    console.print(f"  Coverage:                 [bold {'green' if gap_result.coverage_percentage >= cfg.thresholds.min_coverage_pct else 'red'}]{gap_result.coverage_percentage:.1f}%[/bold {'green' if gap_result.coverage_percentage >= cfg.thresholds.min_coverage_pct else 'red'}] (Target: {cfg.thresholds.min_coverage_pct:.1f}%)")
    console.print(f"\n  Audit Gate Status:        [{status_color}]{status_label}[/{status_color}]\n")


@app.command()
def report(
    reqs_file: Path = typer.Option(
        Path("requirements.json"), "--reqs", "-r", help="Path to requirements JSON"
    ),
    tests_file: Path = typer.Option(
        Path("tests.json"), "--tests", "-t", help="Path to tests JSON"
    ),
    output_html: Path = typer.Option(
        Path("rtm_report.html"), "--output", "-o", "--out", help="Output path for standalone HTML report"
    ),
) -> None:
    """
    Generate an interactive, zero-dependency standalone HTML traceability report.
    """
    if not reqs_file.exists() or not tests_file.exists():
        console.print("[bold red]Error:[/bold red] Missing requirements.json or tests.json. Run ingest and scan first.")
        raise typer.Exit(code=1)

    with open(reqs_file, "r", encoding="utf-8") as f:
        requirements = [Requirement.model_validate(r) for r in json.load(f)]
    with open(tests_file, "r", encoding="utf-8") as f:
        tests = [TestArtifact.model_validate(t) for t in json.load(f)]

    cfg = load_config()
    linker = TraceLinker(
        high_threshold=cfg.thresholds.high_confidence_threshold,
        medium_threshold=cfg.thresholds.medium_confidence_threshold,
    )
    links = linker.link(requirements, tests)

    auditor = GapAuditor(cfg.thresholds)
    gap_result = auditor.analyze(requirements, tests, links)

    generator = HTMLReportGenerator()
    out = generator.generate(
        requirements=requirements,
        tests=tests,
        links=links,
        gap_result=gap_result,
        project_name=cfg.project.name,
        standard=cfg.project.standard,
        output_file=output_html,
    )
    console.print(f"[bold green]Generated[/bold green] interactive HTML report: [cyan]{out}[/cyan]")


@app.command(name="export-reqif")
def export_reqif(
    reqs_file: Path = typer.Option(
        Path("requirements.json"), "--reqs", "-r", help="Path to requirements JSON"
    ),
    tests_file: Path = typer.Option(
        Path("tests.json"), "--tests", "-t", help="Path to tests JSON"
    ),
    output_reqif: Path = typer.Option(
        Path("enriched_trace.reqif"), "--output", "-o", "--out", help="Output path for enriched ReqIF XML"
    ),
) -> None:
    """
    Export verified trace matrix into standard ReqIF XML with <SPEC-RELATION> elements
    for direct re-import into DOORS/Polarion.
    """
    if not reqs_file.exists() or not tests_file.exists():
        console.print("[bold red]Error:[/bold red] Missing requirements.json or tests.json. Run ingest and scan first.")
        raise typer.Exit(code=1)

    with open(reqs_file, "r", encoding="utf-8") as f:
        requirements = [Requirement.model_validate(r) for r in json.load(f)]
    with open(tests_file, "r", encoding="utf-8") as f:
        tests = [TestArtifact.model_validate(t) for t in json.load(f)]

    cfg = load_config()
    linker = TraceLinker(
        high_threshold=cfg.thresholds.high_confidence_threshold,
        medium_threshold=cfg.thresholds.medium_confidence_threshold,
    )
    links = linker.link(requirements, tests)

    exporter = ReqIFExporter()
    out = exporter.export(requirements, links, output_file=output_reqif)
    console.print(f"[bold green]Exported[/bold green] enriched ReqIF XML with SpecRelations: [cyan]{out}[/cyan]")


# --- Human Review Subcommands ---
review_app = typer.Typer(
    name="review",
    help="Human-in-the-loop review sign-off and state overrides.",
    add_completion=False,
)
app.add_typer(review_app, name="review")


@review_app.command(name="approve")
def review_approve(
    req_id: str = typer.Argument(..., help="Requirement ID to approve"),
    test_id: str = typer.Argument(..., help="Test ID linked to requirement"),
    by: str = typer.Option("reviewer", "--by", "-b", help="Reviewer identifier or DER name"),
    comment: Optional[str] = typer.Option(None, "--comment", "-m", help="Audit rationalization comment"),
) -> None:
    """Approve a requirement-to-test trace link with an audit sign-off entry."""
    store = ReviewStore()
    event = ReviewEvent(
        req_id=req_id,
        test_id=test_id,
        status=ReviewStatus.APPROVED,
        reviewed_by=by,
        comment=comment,
    )
    store.append_event(event)
    console.print(f"[bold green]✔ APPROVED[/bold green] link [cyan]{req_id}[/cyan] ➔ [cyan]{test_id}[/cyan] by [bold]{by}[/bold]")
    if comment:
        console.print(f"  Comment: [dim]{comment}[/dim]")


@review_app.command(name="reject")
def review_reject(
    req_id: str = typer.Argument(..., help="Requirement ID to reject"),
    test_id: str = typer.Argument(..., help="Test ID to reject"),
    by: str = typer.Option("reviewer", "--by", "-b", help="Reviewer identifier"),
    comment: Optional[str] = typer.Option(None, "--comment", "-m", help="Rejection rationale"),
) -> None:
    """Reject a proposed candidate trace link (e.g. insufficient assertion coverage)."""
    store = ReviewStore()
    event = ReviewEvent(
        req_id=req_id,
        test_id=test_id,
        status=ReviewStatus.REJECTED,
        reviewed_by=by,
        comment=comment,
    )
    store.append_event(event)
    console.print(f"[bold red]✖ REJECTED[/bold red] link [cyan]{req_id}[/cyan] ➔ [cyan]{test_id}[/cyan] by [bold]{by}[/bold]")
    if comment:
        console.print(f"  Reason: [dim]{comment}[/dim]")


@review_app.command(name="list")
def review_list() -> None:
    """List all active persistent human review sign-offs."""
    store = ReviewStore()
    latest_reviews = store.get_latest_reviews()

    if not latest_reviews:
        console.print("[yellow]No human reviews recorded yet in .reqtrace/reviews.jsonl[/yellow]")
        return

    table = Table(title="Persistent Human Review Overlay (.reqtrace/reviews.jsonl)", border_style="cyan")
    table.add_column("Requirement ID", style="bold", no_wrap=True)
    table.add_column("Test ID", overflow="fold")
    table.add_column("Status", justify="center")
    table.add_column("Reviewed By")
    table.add_column("Timestamp", style="dim")
    table.add_column("Comment")

    for (req_id, test_id), event in latest_reviews.items():
        status_style = "green" if event.status == ReviewStatus.APPROVED else ("red" if event.status == ReviewStatus.REJECTED else "yellow")
        table.add_row(
            req_id,
            test_id,
            f"[{status_style}]{event.status.value.upper()}[/{status_style}]",
            event.reviewed_by,
            event.timestamp[:19].replace("T", " "),
            event.comment or "",
        )

    console.print(table)


@app.command(name="ui")
def launch_ui(
    workspace: Path = typer.Option(
        Path("."), "--workspace", "-w", help="Path to workspace root"
    ),
    host: str = typer.Option(
        "127.0.0.1", "--host", "-h", help="Bind host address (use 0.0.0.0 for Docker containers)"
    ),
    port: int = typer.Option(
        8765, "--port", "-p", help="Loopback port to bind (default: 8765)"
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Do not automatically launch local web browser"
    ),
    ticket_timeout: int = typer.Option(
        60, "--ticket-timeout", help="Launch ticket expiration timeout in seconds"
    ),
) -> None:
    """
    [Milestone 1A] Launch the interactive local workspace web application (reqtrace ui).
    """
    from reqtrace.ui.server import run_server
    run_server(
        workspace_root=workspace,
        host=host,
        port=port,
        open_browser=not no_browser,
        ticket_timeout=ticket_timeout,
    )


@app.command(name="ticket")
def generate_ui_ticket(
    port: int = typer.Option(
        8765, "--port", "-p", help="Port of the running ReqTrace UI server (default: 8765)"
    ),
) -> None:
    """
    Mint a fresh single-use launch ticket for a running ReqTrace UI server or Docker container.
    """
    import urllib.error
    import urllib.request
    from reqtrace.ui.server import find_operator_state_path

    state_path = find_operator_state_path(port)
    if not state_path:
        console.print(
            f"[bold red]Error:[/bold red] No active ReqTrace UI server state found for port {port}."
        )
        console.print(
            "Ensure ReqTrace is running (e.g. [cyan]reqtrace ui[/cyan] or running inside the Docker container)."
        )
        raise typer.Exit(code=1)

    try:
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
        operator_secret = state_data["operator_secret"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        console.print(f"[bold red]Error:[/bold red] Unable to read operator credentials: {exc}")
        raise typer.Exit(code=1)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/internal/ticket",
        data=b"",
        method="POST",
        headers={
            "Host": f"127.0.0.1:{port}",
            "Origin": f"http://127.0.0.1:{port}",
            "X-ReqTrace-Operator": operator_secret,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        console.print(
            f"[bold red]Error:[/bold red] Could not reach running ReqTrace UI on 127.0.0.1:{port} ({exc})."
        )
        raise typer.Exit(code=1)

    ticket = payload["ticket"]
    timeout_sec = payload.get("timeout_sec", 60)
    launch_url = f"http://localhost:{port}/login?ticket={ticket}"

    print("\n" + "=" * 68)
    print("  Fresh ReqTrace Launch Ticket Minted")
    print(f"  Launch URL: {launch_url}")
    print(f"  Ticket:     {ticket}")
    print(f"  Note: Single-use ticket valid for {timeout_sec}s.")
    print("=" * 68 + "\n")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
