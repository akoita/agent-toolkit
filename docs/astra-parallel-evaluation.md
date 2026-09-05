# Astra low worker: initial parser microbenchmark

This preliminary trial measured individual worker turns. The later
[Maestro routing and advisor evaluation](research/2026-09-maestro-routing-evaluation.md)
compares complete workflows on three repository tasks and is the main report.
This page retains the small parser experiment and its reproducible acceptance fixtures.

## Trial on 2026-09-05

An Astra/medium root supervised two native `default` workers in Codex Desktop
0.153.3. Both used `fork_turns="none"`, a minimal READY handshake, persisted
routing verification, and the same parser specification. One worker used low;
the medium worker was an explicit benchmark comparator, outside the production
low-worker profile. Each worker owned a separate temporary output file. Neither
was assigned repository implementation or final review.

The shared assignment required `parse_duration(value)` to accept ASCII integer
h/m/s terms in strictly descending order, optional ASCII spaces outside terms,
leading zeros, and totals from zero through 86,400 seconds. Other types require
TypeError; malformed strings and over-limit totals require ValueError. Units
may be adjacent. Signs, decimals, Unicode digits, other whitespace, repeated
units, and reordered units are invalid. Workers were instructed to use only
the standard library, avoid test execution, and perform no other writes,
delegation, publication, or external actions.

The root independently reviewed both outputs and ran the same 315 acceptance
cases, including boundaries, long zero padding, whitespace, type errors, and
unit order. Both passed on their first attempt.

| Measurement | Astra low | Astra medium comparator |
| --- | ---: | ---: |
| Acceptance cases passed | 315 / 315 | 315 / 315 |
| Implementation turn | 15.647 s | 10.657 s |
| Handshake turn | 4.792 s | 5.291 s |
| Sum of active worker turns | 20.439 s | 15.948 s |
| Reported input tokens, including handshake | 69,881 | 69,916 |
| Cached input tokens (subset of input) | 45,824 | 52,608 |
| Output tokens | 493 | 433 |
| Reported total tokens | 70,374 | 70,349 |
| Outer tool calls | 1 | 1 |
| Repair rounds | 0 | 0 |

Low took about 47% longer for implementation in this sample, or 28% longer when
including its handshake. Total reported tokens were effectively equal. Each
worker made one outer `functions.exec` call containing one shell call to write
its file. No tests were run by the workers; the root performed the common gate.
Reported reasoning-output tokens were zero for both; the verified route comes
from turn metadata, not inference from token counters.

## Interpretation and limits

This is one task and one run per effort, without randomized order. The short
handshake wording and output filenames differed; the implementation contract
was the same. Cache conditions differed, and the implementation turns did not
overlap. Service latency can dominate a task this small. These numbers do not
establish a general ranking of reasoning efforts or dollar cost savings.

The comparator was a medium native worker, not a solo-root implementation.
Active-turn duration excludes root planning, routing checks, scheduling gaps,
review, and test time. Root work also included developing the new profile, so
its aggregate tokens would not be an equivalent solo baseline. The table
therefore cannot establish end-to-end orchestrator-plus-worker efficiency or
parallel speedup. Handshake input alone was approximately 23,000 tokens per
worker despite requesting no inherited conversation turns; fresh workers still
carry the runtime's instructions and tool context.

The later workflow study compares solo Astra/medium with Astra/medium plus low
workers on three equivalent repository tasks using isolated starting states and
common acceptance gates. Further studies should randomize order, repeat runs, and account for all
root and worker tokens, cache use, handshakes, review, retries, elapsed time to
acceptance, and regressions. Prefer reused workers and sufficiently substantial
assignments to amortize startup overhead. No default-policy change is justified
by this initial trial.

## Reproduce the acceptance check

The [low output](evaluations/astra-parallel/low.py),
[medium output](evaluations/astra-parallel/medium.py), and
[metrics](evaluations/astra-parallel/metrics.json) are retained as evaluation
fixtures, not shipped parser implementations. From the repository root:

```sh
python docs/evaluations/astra-parallel/verify.py
```

[collect.py](evaluations/astra-parallel/collect.py) extracts the table's worker
metrics from two persisted rollouts. It excludes prompts, private filesystem
paths, and account information from its output. Private rollouts are not
committed. Re-extracting metrics requires the original local rollouts; rerunning
the acceptance check does not regenerate model timing or token measurements.
