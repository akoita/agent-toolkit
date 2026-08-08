# Component security context

> This is a nested engineering `SECURITY.md` for the component rooted at
> `<path>`. It helps maintainers and review tools understand this trust boundary.
> It does not replace the repository-root vulnerability disclosure policy.

## Scope and owner

- Component/path: `<path>`
- Human owner or maintainer role: `<owner>`
- Last reviewed: `<YYYY-MM-DD>`
- Applicable deployment/runtime: `<service, package, job, contract, or none>`
- Parent security context: `<path or none>`

## Assets and impact

| Asset | Why it matters | Maximum credible impact |
| --- | --- | --- |
| `<asset>` | `<security property>` | `<confidentiality, integrity, availability, funds, or control impact>` |

## Trust boundary

- Attacker-controlled inputs: `<requests, files, events, prompts, tool output>`
- Authenticated identities and how they are verified: `<identity sources>`
- Privileges held by this component: `<data, network, filesystem, cloud, signing, funds>`
- External systems trusted: `<system and exact trust assumption>`
- Data or actions that must never cross this boundary: `<constraint>`

## Security invariants

Write falsifiable statements and link their enforcement.

1. `<invariant>` — enforced by `<file:line, configuration, or test>`.
2. `<invariant>` — enforced by `<file:line, configuration, or test>`.

## Privileged and dangerous operations

| Operation | Required authorization | Guard and audit evidence |
| --- | --- | --- |
| `<operation>` | `<principal, role, approval>` | `<file:line, policy, log, test>` |

## Expected mitigations

- Input validation and normalization: `<implementation>`
- Authorization and tenant isolation: `<implementation>`
- Secret and credential isolation: `<implementation>`
- Network and egress restrictions: `<implementation>`
- Failure/rollback behavior: `<implementation>`
- Abuse limits and monitoring: `<implementation>`

## Known exceptions and residual risk

| Exception | Owner | Expiry/review date | Compensating control | Approval record |
| --- | --- | --- | --- | --- |
| `<exception>` | `<owner>` | `<date>` | `<control>` | `<link>` |

## Verification

- Regression, fuzz, property, or invariant tests: `<paths/commands>`
- Security review trigger: `<boundary change, release, incident, or cadence>`
- Incident/runbook link: `<private or public location without secrets>`

## Reporting vulnerabilities

Follow the repository-root `SECURITY.md`. Do not put reporter details, active
incident evidence, exploit instructions, or credentials in this file.
