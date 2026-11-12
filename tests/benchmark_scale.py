# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Large-Scale Synthetic Benchmark for ReqTrace.
Validates the MVP quantitative success criteria:
- 5,000 requirements
- 20,000 test artifacts
- End-to-end trace generation and orphan detection under 5 minutes (<300s)
"""

import sys
import time
from pathlib import Path
from typing import List

# Ensure reqtrace is in path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from reqtrace.engine.linker import TraceLinker
from reqtrace.analysis.gap_auditor import GapAuditor
from reqtrace.models.requirement import Requirement, RequirementLevel, RequirementType
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus


def run_benchmark(num_reqs: int = 5000, num_tests: int = 20000) -> None:
    print(f"\n=======================================================")
    print(f"🚀 REQTRACE SCALE BENCHMARK: {num_reqs:,} Reqs vs {num_tests:,} Tests")
    print(f"=======================================================")

    t0 = time.perf_counter()

    # 1. Synthesize 5,000 requirements with multi-tier hierarchy
    print(f"1. Synthesizing {num_reqs:,} requirements...")
    requirements: List[Requirement] = []
    for i in range(1, num_reqs + 1):
        level = RequirementLevel.HIGH_LEVEL if i % 4 != 0 else RequirementLevel.LOW_LEVEL
        parent = [f"SYS-REQ-{(i // 10) + 1:04d}"] if level == RequirementLevel.LOW_LEVEL else []
        req = Requirement(
            id=f"REQ-{i:05d}",
            title=f"Subsystem Functional Requirement {i}",
            description=f"The flight controller shall maintain operational parameter {i} within tolerance limit of +/- {i % 10 + 1}ms.",
            level=level,
            parent_ids=parent,
            source_file="synthetic_avionics.reqif",
            req_type=RequirementType.FUNCTIONAL if i % 5 != 0 else RequirementType.SAFETY,
        )
        requirements.append(req)

    t_synth_reqs = time.perf_counter() - t0
    print(f"   Done in {t_synth_reqs:.2f}s ({len(requirements):,} requirements)")

    # 2. Synthesize 20,000 tests with ~95% coverage and 5% unlinked rogue tests
    print(f"2. Synthesizing {num_tests:,} test artifacts with execution verdicts...")
    t1 = time.perf_counter()
    tests: List[TestArtifact] = []
    for j in range(1, num_tests + 1):
        # Link most tests to a requirement; leave some as rogue unlinked
        if j <= num_reqs * 3.8:
            target_req_num = (j % num_reqs) + 1
            refs = [f"REQ-{target_req_num:05d}"]
        else:
            refs = []

        status = TestExecutionStatus.PASSED if j % 100 != 0 else TestExecutionStatus.FAILED
        test = TestArtifact(
            id=f"test_flight_module_{j // 100:03d}.py::test_case_{j:05d}",
            file_path=f"tests/test_module_{j // 100:03d}.py",
            line_start=(j % 200) * 10 + 1,
            line_end=(j % 200) * 10 + 9,
            framework="pytest",
            declared_req_refs=refs,
            assertion_statements=[f"assert status_code == 0", f"assert latency_ms <= {(j % 10 + 1) * 20}"],
            execution_status=status,
            execution_time_sec=0.012,
        )
        tests.append(test)

    t_synth_tests = time.perf_counter() - t1
    print(f"   Done in {t_synth_tests:.2f}s ({len(tests):,} tests)")

    # 3. Benchmark TraceLinker
    print(f"3. Benchmarking TraceLinker...")
    t2 = time.perf_counter()
    linker = TraceLinker()
    links = linker.link(requirements, tests)
    t_link = time.perf_counter() - t2
    print(f"   Generated {len(links):,} trace links in {t_link:.2f}s ({len(links) / t_link:,.1f} links/sec)")

    # 4. Benchmark GapAuditor
    print(f"4. Benchmarking GapAuditor (Orphan & Discrepancy Detection)...")
    t3 = time.perf_counter()
    auditor = GapAuditor()
    gap_result = auditor.analyze(requirements, tests, links)
    t_audit = time.perf_counter() - t3
    print(f"   Audited {gap_result.total_requirements:,} requirements in {t_audit:.2f}s")

    total_time = time.perf_counter() - t0
    print(f"\n=======================================================")
    print(f"🏆 BENCHMARK RESULTS SUMMARY")
    print(f"=======================================================")
    print(f"Total Requirements:         {gap_result.total_requirements:,}")
    print(f"Total Test Artifacts:       {gap_result.total_tests:,}")
    print(f"Generated Links:            {len(links):,}")
    print(f"Live Verified:              {gap_result.covered_requirements:,}")
    print(f"Orphan Requirements:        {len(gap_result.orphan_requirements):,}")
    print(f"Unlinked Rogue Tests:       {len(gap_result.unlinked_tests):,}")
    print(f"Failing Tests in CI:        {len(gap_result.failed_tests):,}")
    print(f"Coverage Percentage:        {gap_result.coverage_percentage:.2f}%")
    print(f"Total Wall-Clock Time:      {total_time:.2f}s (Target: <300.0s)")
    print(f"Scale Success Threshold:    {'✅ PASSED' if total_time < 300.0 else '❌ FAILED'}")
    print(f"=======================================================\n")

    assert total_time < 300.0, f"Benchmark exceeded 5 minutes target: {total_time:.2f}s"
    assert len(links) > 0


if __name__ == "__main__":
    run_benchmark(num_reqs=5000, num_tests=20000)
