# Standards and compliance obligations

This is engineering guidance, not legal advice. Everything below is stated as
an artifact you have to produce or a control you have to run, because that is
the part an engineer can act on. Where a legal question is genuinely open, say
so and route it to counsel rather than guessing.

Two rules apply throughout. Pin the version of any standard you cite, because
identifiers and counts move between releases. And distinguish an adopted
obligation from a draft — a deadline that rests on an unadopted instrument is
not a deadline.

## EU Cyber Resilience Act

**Regulation (EU) 2024/2847**, in force since 10 December 2024.

Two dates matter to an engineering team:

| Date | What applies |
| --- | --- |
| 11 September 2026 | Article 14 reporting obligations |
| 11 December 2027 | Full application |

### Article 14 reporting, from 11 September 2026

Actively exploited vulnerabilities and severe incidents are reported through
the ENISA Single Reporting Platform on a three-stage clock:

| Stage | Deadline |
| --- | --- |
| Early warning | 24 hours |
| Notification | 72 hours |
| Final report | 14 days after a corrective measure is available; one month for a severe incident |

This applies to products already on the market, not only to new releases. The
engineering consequence is that a team needs a rehearsed path from "we noticed
active exploitation" to "a submission exists" that fits inside 24 hours. That
is an on-call runbook problem, not a documentation problem.

### Who is a manufacturer

A manufacturer is someone who markets a product with digital elements under
their own name or trademark, in the course of a commercial activity.

Unmonetised free and open-source software is out of scope. The regulation also
creates an **open-source steward** role — organizations that support the
development of open-source products used commercially — under a lighter regime
that carries no administrative fines. If a project is a hobby release with no
commercial activity attached, do not tell the user they have CRA obligations.

### Artifacts to have

- a machine-readable SBOM covering at minimum the top-level dependencies;
- a published coordinated vulnerability disclosure policy and a contact point;
- free security updates for the support period — at least five years, or the
  expected product lifetime if shorter — shipped separately from feature
  updates, so a user can take a security fix without taking a behaviour change;
- technical documentation;
- an EU declaration of conformity and CE marking.

The "separately from feature updates" requirement is the one most likely to
force a real change to a release process. A single rolling `latest` channel
does not satisfy it.

### Marked unverified

Harmonised-standards deadlines circulating for late 2026 rest on a **draft**
Commission amendment rather than an adopted act. Treat any specific date for
harmonised standards as **unverified** and do not plan against it.

## NIST Secure Software Development Framework

| Publication | Status | Use |
| --- | --- | --- |
| SP 800-218 v1.1 (February 2022) | **Final** | The citable SSDF. Gate on this one |
| SP 800-218r1 (SSDF v1.2) | **Draft** — initial public draft 17 December 2025 | Read for direction; do not gate on it |
| SP 800-218A (26 July 2024) | **Final** | Generative-AI community profile over the same structure |

SSDF organizes practices as `PO` (prepare the organization), `PS` (protect the
software), `PW` (produce well-secured software), and `RV` (respond to
vulnerabilities). SP 800-218A extends the same PO/PS/PW/RV structure to
generative AI and dual-use foundation models, so a team already mapped to
800-218 can adopt it without a second framework.

When a customer questionnaire asks for "SSDF compliance", it almost always
means v1.1. Answering with v1.2 practice ids will not match their spreadsheet.

## OWASP ASVS

**ASVS 5.0.0**, released 30 May 2025. 17 chapters (V1 Encoding and
Sanitization through V17 WebRTC) and 345 requirements, counted from the
machine-readable release.

Requirement identifiers are `<chapter>.<section>.<requirement>`, for example
`1.11.3`. ASVS explicitly asks external documents, reports, and tools to carry
the version: `v<version>-<chapter>.<section>.<requirement>`, for example
`v5.0.0-1.2.5`. Do that — the numbering is only stable within a major version,
and a bare `1.2.5` in a report becomes ambiguous the moment 5.1.0 ships.

Drive a checklist from the machine-readable file rather than the PDF:

```
OWASP/ASVS @ v5.0.0_release
  5.0/docs_en/OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json
```

Each entry carries `chapter_id`, `chapter_name`, `section_id`, `section_name`,
`req_id`, `req_description`, and the level `L`, which is exactly the shape a
review checklist needs.

### Posture for a small team

Treat **L1 as the gate** and **L2 as the roadmap**. Do not attempt L2 across
all 17 chapters at once. Scope L2 first to the four chapters where a defect is
both likely and expensive:

- authentication (V6),
- session management (V7),
- authorization (V8),
- validation and business logic (V2).

L3 is for applications where a compromise is a safety or existential event. If
a user asks for L3 on a routine web application, ask what threat justifies it
before agreeing.

## OWASP SAMM

**SAMM v2.0** is current. There is no 2.1 — do not cite one.

The free self-assessment spreadsheet lives in `OWASP/samm` at
`Supporting Resources/v2.0/toolbox/SAMM_Assessment_Toolbox_v2.0.xlsx`. SAMM
answers a different question from ASVS: ASVS asks whether the application is
secure, SAMM asks whether the organization's practices produce secure
applications. Use SAMM when a user asks how to improve their process, and ASVS
when they ask whether a specific application is ready to ship.

## CIS benchmarks

CIS benchmark PDFs are free after registration, but CIS-CAT Lite covers only a
subset of benchmarks and configurations, so it cannot be the automation story
for most stacks. Free engineering substitutes cover most of what a team
actually needs:

| Target | Tool |
| --- | --- |
| Kubernetes nodes and control plane | `kube-bench` |
| Docker daemon and host | `docker-bench-security` |
| Kubernetes cluster, CIS-mapped | `trivy k8s --compliance k8s-cis` |
| Container images, CIS-mapped | `trivy image --compliance docker-cis-1.6.0` |

Confirm the exact `--compliance` identifier against the installed Trivy
version before quoting it; the compliance spec names are versioned and move.

## PCI DSS and SOC 2

Cover these only where they change engineering. Most of both frameworks is
policy and evidence collection that an engineer neither owns nor can fix.

### PCI DSS 4.0.1, the requirements that reach the codebase

| Requirement | Engineering meaning |
| --- | --- |
| 6.3.2 | A maintained inventory of bespoke and third-party software components. In practice this is a per-release SBOM |
| 6.3.3 | Patch critical and high severity vulnerabilities within one month |
| 6.4.3 and 11.6.1 | Inventory every script on a payment page, justify each one, and detect unauthorized change to page content and headers |
| 11.3.1.x | Internal and external vulnerability scanning on a defined cadence, with rescans until resolved |

6.4.3 plus 11.6.1 is the pair teams miss. A payment page that pulls a tag
manager or an analytics script has an inventory obligation and an integrity
monitoring obligation, and neither is satisfied by a scanner.

### SOC 2, the controls auditors actually test

- **CC8.1, change management.** Branch protection, required reviews, pull
  requests linked to a ticket, and a build that cannot be bypassed. An auditor
  will sample merged pull requests and look for the review and the link.
- **CC6.x, logical access.** Who can merge, who can publish, who holds
  production credentials, and evidence that access is reviewed and removed.

Both are satisfied mostly by repository and CI configuration, which means they
overlap heavily with pass 1 of this skill. Immutable CI logs and retained scan
artifacts are the evidence; retention that expires before the audit window is
the usual failure.

## Mapping once instead of many times

The OSPS Baseline controls carry mappings to the OpenSSF Best Practices Badge,
the CRA, NIST SSDF, the NIST CSF, OpenCRE, PCI DSS, SAMM, and SP 800-161. When
a team faces several of these at once, satisfy and evidence a Baseline control
once, then cite the mapping, rather than running a separate assessment per
framework.
