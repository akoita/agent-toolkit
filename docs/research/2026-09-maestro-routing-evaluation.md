# Maestro routing and advisor evaluation

The September 5, 2026 pilot favored Astra/medium alone for speed and first-submission success on three bounded repository tasks. Adding an Astra/low worker increased cost and time. Sol/medium with mandatory Astra/medium plan review also increased cost and time without improving first-submission success. On-demand advice remains untested in practice: the executor never requested it.

These are observations from 21 isolated workflow trials across seven configurations, with one run per configuration and task. They support retaining the solo default for this workload, not a general ranking of models. This report records experiments; it does not enable or release a routing profile.

## Orchestrator and worker results

The original nine trials compared Sol/Luna, Astra/Luna, and Astra alone. Three later trials added Astra/medium with one Astra/low worker using the same frozen tasks and acceptance checks. The earlier configurations were not rerun for that extension.

| Configuration | First submission passes | Final acceptance | Estimated cost | Total time |
| --- | ---: | ---: | ---: | ---: |
| Sol/medium + Luna/max | 2/3 | 3/3 | $1.21 | 18m 06s |
| Astra/medium + Luna/max | 3/3 | 3/3 | $4.48 | 21m 41s |
| Astra/medium alone | 3/3 | 3/3 | $2.00 | 8m 07s |
| Astra/medium + Astra/low | 3/3 | 3/3 | $5.46 | 10m 32s |

Astra/low workers produced accepted results, but their workflow cost 2.73 times as much and took 30% longer than Astra alone. Compared with Astra/Luna, it was 51% faster and 22% more expensive. The root accounted for $3.22 of the $5.46 Astra/low total; workers accounted for $2.24. In Astra/Luna, the root accounted for 96.6% of cost. A cheaper worker therefore did not imply a cheaper complete workflow.

These trials used one implementation worker per orchestrated task. They do not measure speedup from multiple workers doing independent work concurrently. Astra workers used the native `default` role with explicit model and effort; Luna workers used custom roles, another difference between conditions.

A preliminary [parser microbenchmark](../astra-parallel-evaluation.md) separately compared low and medium native workers. Both passed 315 acceptance cases. Low took 20.439 seconds including its handshake, versus 15.948 seconds for medium, with nearly equal total tokens. That small worker-only experiment excludes root overhead and cannot establish complete-workflow efficiency.

## Inverting the relationship: executor and advisor

The [advisor strategy described by Anthropic](https://claude.com/blog/the-advisor-strategy) motivated a second experiment: Sol executes directly and consults Astra for guidance. This pilot used isolated CLI roots and native advice-only children. It did not use Anthropic's integrated advisor tool or evaluate its published performance claims.

Nine new trials compared a fresh Sol baseline with on-demand advice and mandatory upfront plan review. The Astra-alone row below is the historical reference from the first study, not three additional trials.

| Configuration | First submission passes | Final acceptance | Estimated cost | Total time | Advice calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sol/medium alone | 2/3 | 3/3 | $1.31 | 8m 44s | 0 |
| Sol/medium + Astra/medium on demand | 2/3 | 3/3 | $1.25 | 8m 33s | 0 |
| Sol/medium + Astra/medium upfront plan review | 2/3 | 3/3 | $2.32 | 11m 31s | 3 |
| Astra/medium alone, prior run | 3/3 | 3/3 | $2.00 | 8m 07s | 0 |

Mandatory review cost 77% more and took 32% longer than Sol alone, with the same first-submission result. Its total included $1.535 for the executor and $0.782 for the advisor. All nine trials passed the 93 applicable acceptance scenarios after three repairs.

The on-demand policy made zero consultations, including during repair. Its approximately 5% lower cost and 2% shorter time cannot be attributed to Astra assistance. Those differences reflect executor behavior, prompts, cache conditions, and runtime variation. Whether actual on-demand consultation improves outcomes remains unresolved.

## Who analyzed the problem and planned the steps?

Sol owned the initial analysis, ordered file-level plan, implementation, tool use, tests, review, and final response in all three advisory conditions. The policy differences were:

- **Solo:** no advisor or other subagents.
- **On demand:** consult Astra for a concrete unresolved ambiguity, consequential tradeoff, or failed targeted fix. No automatic startup or final consultation.
- **Upfront review:** inspect the code and draft a plan, then obtain Astra's review before implementation edits. All three tasks were designated non-trivial in advance; this did not test automatic complexity classification.

Both advisory policies allowed at most two substantive consultations, including repair, reusing one advisor. The advisor received focused context without a conversation-history fork, returned text guidance, and could not use tools, edit files, or create agents. A routing handshake preceded substantive advice. Upfront review used exactly one consultation per task; the audit found zero advisor tool calls.

### What the advice changed

All three Sol conditions initially changed legacy preview/apply error exits from 1 to 2 while adding a new drift-check mode. Their own tests passed, but the independent validator caught the compatibility regression. Each needed one repair. The upfront advisor explicitly accepted the broader exit-code change, so it did not correct the executor's mistaken interpretation. The retained [drift-check advice](../evaluations/maestro-routing/check-advice.md) documents that failure.

The [timeout advisor](../evaluations/maestro-routing/timeout-advice.md) identified cleanup that could hang while waiting for I/O threads when inherited pipes remain open. The [installer advisor](../evaluations/maestro-routing/dryrun-advice.md) emphasized dangling-symlink conflicts and shared conflict validation. Sol incorporated that guidance. These are observable design contributions, but the acceptance results do not establish extra quality or how many defects the advice prevented.

For this workload, the evidence supports keeping analysis and planning with the executor and avoiding mandatory review of every plan. A future experiment could ask the advisor to independently identify compatibility invariants from the original task before seeing the executor's interpretation. That policy was not tested here. Harder tasks that actually trigger escalation are also necessary to evaluate on-demand advice.

## Shared tasks and acceptance

All workflow studies used source snapshot `f8eeefbda29b2624f5255c94433980f6908ac8e5`, frozen task descriptions, and a common external validator. Each configuration faced 31 scenarios:

| Task | Required behavior | Scenarios |
| --- | --- | ---: |
| CI drift check | Add `--check`: 0 for clean, 1 for drift/missing, 2 for invalid input; no writes; preserve preview/apply and line endings. | 12 |
| Worker timeout | Add a positive finite `--timeout`; handle ordinary and streaming hangs; terminate and reap the direct child; exit 124 without a success session file. | 10 |
| Installer dry run | Preview install/uninstall without filesystem changes; preserve selection, force, link, and conflict behavior, including modified agent files. | 9 |

Trials ran sequentially in fresh Git fixtures under codex-cli 0.153.4 and Python 3.13.6. Route order rotated across tasks. Roots used explicit medium effort and Standard service-tier requests. Persisted routing was checked before assignment; child routing was checked before substantive work. The workflow emulated bounded Maestro orchestration rather than exercising every step of the installed skill.

Each initial attempt had 12 minutes, with at most one 8-minute repair after external acceptance feedback. First-submission success means passing the first external evaluation; internal corrections are included. Initial harness/calibration failures were excluded from the original nine trials. Two legacy checks were added during preparation of the first trial before its first external evaluation, then held fixed for all configurations; this was not a preregistered study.

## Cost and time accounting

Dollar amounts are estimates under frozen Standard API-equivalent rates, not subscription charges or current price quotations. Rates per million tokens were:

| Model | Ordinary input | Cached input | Cache-write input | Output |
| --- | ---: | ---: | ---: | ---: |
| Astra | $10 | $1 | $12.50 | $50 |
| Sol | $4 | $0.40 | $5 | $20 |
| Luna | $0.20 | $0.02 | $0.25 | $1.20 |

Ordinary input equals total input minus cached and cache-write input. Output includes reasoning tokens, which are not charged twice. Actual caching was retained. Request usage was deduplicated by response ID within each task and reconciled against executor counters. The harness retained its input-2×/output-1.5× adjustment above 272,000 request input tokens; no trial triggered it. Rounded per-trial amounts can differ from aggregate component sums by a microdollar.

Time includes CLI startup, handshakes, analysis, planning, implementation, agent-run tests, review, and repairs. It excludes controller research, fixture preparation, independent acceptance validation, reporting, and gaps between trials. Cost includes root and child usage over those attempts. Reported time is therefore measured agent-workflow time through the accepted attempt, not all elapsed research time.

## Limits and retained evidence

There is one observation per configuration/task. Cache differences, service conditions, stochastic choices, prompts, and implementation approaches can affect these results. The studies were conducted in successive waves; historical baselines were not rerun in each wave. The results do not establish statistical superiority, large-project performance, multi-worker speedup, or absence of defects beyond the checks.

The [data directory](../evaluations/maestro-routing/README.md) retains all 21 trial summaries, aggregate totals, frozen task descriptions, provenance hashes, extension audits, and public advisor responses. Private rollout logs and isolated implementation workspaces are not included. The retained summaries support recalculating totals; they are not a complete model-benchmark replay package. The separate parser acceptance fixtures can be run locally.
