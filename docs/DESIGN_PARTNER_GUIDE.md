# Phase 0.5: Design Partner Customer Discovery Guide
### Validating ReqTrace with Verification Leads, Certification Leads, and Engineering Managers

---

## 1. Discovery Objectives & Go / No-Go Threshold

Before commercializing or expanding the feature set into proprietary tiers, validate the core pain points and willingness-to-adopt across **three distinct regulated personas**:
1. **Lead V&V Engineers** (The hands-on creators of test suites and RTMs).
2. **Certification Leads / DERs / Independent Assessors** (Designated Engineering Representatives, Software Quality Assurance leads, and TÜV SÜD / regulatory assessors who audit DO-178C, DO-254, ISO 26262, or IEC 62304 programs).
3. **QA & Systems Engineering Managers** (The budget holders measuring audit preparation labor hours and verification cycle time).

### Quantitative Phase 0.5 Go / No-Go Decision Threshold:
> **Proceed to Phase 1 Commercialization ONLY if:**  
> $\ge 8$ of 15 Lead V&V Engineers confirm that manual RTM preparation, skipped/failing test blind spots, or specification revision drift represent a recurring schedule bottleneck or audit risk.

---

## 2. Interview Cohorts & Target Numbers

| Persona | Target Count | Key Validation Goal |
| :--- | :---: | :--- |
| **Lead V&V Engineers** | 10–15 | How do they currently map requirements to tests? What happens when specs or test assertions change? |
| **DERs / SQA / Assessors** | 3–5 | How are verification tools qualified? What evidence is required to accept automated trace matrices? |
| **QA / Systems Managers** | 3–5 | What is the total cycle time & labor cost of preparing an SVR? Who has budget authority to purchase tooling? |

---

## 3. Interview Protocol & Behavior-Grounded Question Bank

### Section A: Operational Realities (Past-Behavior Grounding)
1. *“Where do requirements originate in your programs (DOORS Classic, DOORS Next, Polarion, Word, Excel, Jama)?”*
2. *“How frequently do engineers exchange requirements across teams or suppliers? What formats do you use in practice (ReqIF XML, CSV, custom scripts)?”*
3. *“When an engineer writes a test case, how is the requirement trace link established today (docstrings, decorator tags, Jira issue keys, or a centralized ALM field)?”*
4. *“Tell me about the last time an audit or review flagged a trace link or verification discrepancy. How did you discover it, and how was it resolved?”*

### Section B: Live Traceability & Execution Gaps
5. *“In your current verification workflow, how do you verify that a test linked to a critical requirement actually executed and PASSED in the latest qualification run?”*
6. *“Have you ever encountered a situation where a requirement was marked 'verified' in an RTM, but the underlying test was skipped, aborted, or failing in CI?”*
7. *“How does your team currently treat skipped or disabled tests when calculating audit readiness coverage?”*

### Section C: Specification Drift & Re-Verification
8. *“When a customer or systems engineering team issues Rev 2.0 or Rev 3.0 of a specification mid-project, what is your exact process for identifying which tests are invalidated or stale?”*
9. *“How much engineering time is spent re-reviewing unchanged requirements just to prove that baseline delta impact was bounded?”*

### Section D: Tool Qualification & Regulatory Acceptance
10. *“How does your organization determine whether a verification assistance tool requires formal tool qualification under DO-330, ISO 26262-8 Clause 11, or IEC 62304, and what criteria or qualification levels (e.g. TQL-1 through TQL-5) typically apply?”*
11. *“If a tool generates trace links deterministically with character-exact code span citations and requires a human engineer or DER to sign off on each link, how does that affect your qualification assessment?”*
12. *“What specific documentation artifacts (e.g. TQP, TOR, structural coverage reports) would you need from a tool vendor to support your qualification submission?”*

### Section E: Procurement, ITAR, and Commercial Viability
13. *“Who in your engineering organization has budget authority for verification tooling? What is the approval threshold for discretionary departmental purchases vs. enterprise procurement?”*
14. *“What constraints apply to your verification labs regarding internet connectivity, ITAR, export control, or proprietary source code sharing? (e.g., must the tool run 100% air-gapped on classified subnets?)”*
15. *“If a tool eliminated 80% of the manual effort in generating audit-ready RTMs and flagging broken links, would your team consider sponsoring a pilot or signing a non-binding Letter of Intent (LOI)?”*

---

## 4. Scoring Rubric & Quantitative Validation Criteria

| Signal Category | Strong Validation (Proceed) | Moderate Friction (Refine) | Weak Signal (Pivot / Re-evaluate) |
| :--- | :--- | :--- | :--- |
| **RTM Maintenance Effort** | $> 20$ hours per engineer per release updating spreadsheets/ALM | $5 - 20$ hours per engineer per release | $< 5$ hours; ALM automation is already frictionless |
| **ReqIF Usage** | ReqIF XML or CSV is universally accessible in their pipeline | ReqIF is available but requires IT export tickets | Enterprise IT strictly blocks all file exports; live API only |
| **Live Traceability Pain** | Teams report audits flagged due to skipped/failing tests or stale links | Teams verify test results manually in separate spreadsheets | Teams insist static linking is sufficient and audits do not cross-check verdicts |
| **Air-Gap / Deployment** | Strict requirement for 100% offline local execution on isolated workstations | Self-hosted private network server acceptable | Insistence on multi-tenant SaaS / cloud-only hosting |
| **Willingness to Pay (WTP)** | Departmental budget available ($5k–$25k/seat/year); willing to sign pilot LOI | Purchase requires multi-departmental committee review | No discretionary budget; open-source only |

---

## 5. Interview Ethics, Consent & Data Handling

1. **NDA & Recording Consent**:
   - Confirm mutual Non-Disclosure Agreement (NDA) status prior to interview.
   - Always obtain explicit verbal consent prior to recording audio or taking transcribed notes.
2. **ITAR & Export-Controlled Information**:
   - Instruct participants **not** to share proprietary requirements text, defense system parameters, or export-controlled source code.
   - Discuss only generic processes, standard schemas (ReqIF/JUnit), and high-level verification workflows.
