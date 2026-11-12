# ReqTrace Sample Test Datasets (`demo_assets/`)

This directory provides ready-to-test sample files across every specification, test implementation, and execution result format supported by ReqTrace.

*(The root-level `spec.reqif`, `spec_v2.reqif`, `junit.xml`, and `tests/test_nav.py` files remain in place for quick smoke tests and CI workflow compatibility.)*

---

## Directory Structure

```text
demo_assets/
├── specs/                        # Requirement specifications (`reqtrace ingest` / UI Spec Dropzone)
│   ├── reqif/
│   │   ├── avionics_v1.reqif     # ReqIF 1.2 XML with heading exclusion + parent <SPEC-RELATION> links
│   │   └── avionics_v2.reqif     # Revised ReqIF v2 (modified/added/removed reqs for `reqtrace diff`)
│   ├── csv/
│   │   ├── avionics_requirements.csv            # Standard comma-delimited CSV matrix
│   │   └── avionics_requirements_semicolon.csv  # Semicolon-delimited (;) ALM/Excel export
│   └── docx/
│       └── avionics_specification.docx          # Word doc with heading-prefixed prose AND requirement table
├── test_sources/                 # Test code & BDD files (`reqtrace scan` / UI Test Dropzone)
│   ├── python/
│   │   ├── test_flight_nav.py    # PyTest explicit tags (@pytest.mark.req, docstring, comment) + rogue test
│   │   └── test_power_bus.py     # Untagged semantic test generating a Candidate Link for REQ-PWR-201
│   ├── cpp/
│   │   ├── test_avionics_gtest.cpp        # C++ GoogleTest TEST() / TEST_F() with ASSERT_*/EXPECT_*
│   │   └── test_embedded_c_harness.c      # Embedded C custom macros (MY_FLIGHT_TEST, VERIFY_SIGNAL)
│   └── gherkin/
│       └── flight_safety.feature          # Cucumber/BDD scenarios with @REQ-* tags and Then/And assertions
└── test_results/                 # Dynamic execution reports (`--junit` / UI Test Dropzone)
    └── junit/
        ├── junit_all_pass.xml             # All test cases PASSED (Python + C++ + C)
        └── junit_mixed_verdicts.xml       # Mixed PASSED, FAILED (<failure>/<error>), and SKIPPED verdicts
```

---

## Scenarios Covered Across These Samples

| Requirement ID | Level | Purpose in Demo |
| :--- | :--- | :--- |
| `SEC-01` | Heading | Non-normative section header (`Heading` / `normative=false`) excluded from gap denominator |
| `SYS-FLT-001` | System | Covered by Python docstring ref + C++ `TEST(FlightControlTest, ImuFailoverMaintenance)` |
| `REQ-NAV-101` | High-Level | Explicit `@pytest.mark.req("REQ-NAV-101")` + Gherkin `@REQ-NAV-101`; modified in `avionics_v2.reqif` |
| `REQ-NAV-102` | High-Level | Covered by Python + C++ `KalmanSuite.DeadReckoningDrift` (`PASSED` in all-pass, `FAILED` in mixed JUnit) |
| `REQ-PWR-201` | Low-Level | **No explicit tag** — exercises fuzzy semantic **Candidate Review Queue** match |
| `REQ-COM-301` | Low-Level | Embedded C custom macro `MY_FLIGHT_TEST` (`SKIPPED` in mixed JUnit; removed in `avionics_v2.reqif`) |
| `REQ-HYD-401` | High-Level | Gherkin `@REQ-HYD-401` behavioral scenario (`UNEXECUTED` until matched) |
| `REQ-ORPHAN-900` | Low-Level | Intentional **Orphan Requirement** (zero linked tests) |
| *(Rogue Test)* | — | `test_diagnostic_uart_banner` intentionally untagged for unlinked rogue test auditing |

---

## Quick Test Commands (CLI)

Run any combination against a temporary workspace or inside the project folder:

```bash
# 1. Ingest any supported specification format
reqtrace ingest demo_assets/specs/reqif/avionics_v1.reqif
# Or CSV / Semicolon CSV / Word .docx:
# reqtrace ingest demo_assets/specs/csv/avionics_requirements.csv
# reqtrace ingest demo_assets/specs/csv/avionics_requirements_semicolon.csv
# reqtrace ingest demo_assets/specs/docx/avionics_specification.docx

# 2. Scan Python + C++ + C + Gherkin test suites with mixed JUnit verdicts
reqtrace scan demo_assets/test_sources/ --junit demo_assets/test_results/junit/junit_mixed_verdicts.xml

# Or re-run with clean green CI results:
# reqtrace scan demo_assets/test_sources/ --junit demo_assets/test_results/junit/junit_all_pass.xml

# 3. Compute matrix, view scorecard, check gaps, and generate HTML report
reqtrace link --output trace_matrix.csv
reqtrace audit-summary
reqtrace report --out rtm_report.html

# 4. Compare specification revisions for drift & stale links
reqtrace diff demo_assets/specs/reqif/avionics_v1.reqif demo_assets/specs/reqif/avionics_v2.reqif
```

---

## Testing in the Web UI (`reqtrace ui` / Docker)

1. Open the cockpit -> click **Import Files**.
2. Drag any file from `demo_assets/specs/{reqif,csv,docx}/` into the **Requirements Specification** dropzone.
3. Drag any test source file from `demo_assets/test_sources/{python,cpp,gherkin}/` into **Test Artifacts & Verdicts**, followed by `demo_assets/test_results/junit/junit_mixed_verdicts.xml` (or `junit_all_pass.xml`) to attach dynamic PASS/FAIL/SKIP verdicts.
4. Inspect the **Candidate Review Queue** tab to approve/reject the heuristic match on `REQ-PWR-201`.

