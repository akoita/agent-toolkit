# Tooling

Install command, exact invocation, output format, and false-positive character
for every analyzer this skill uses. The procedure that sequences them lives in
`../SKILL.md`; this file is the detail.

Status notes were verified on 2026-07-29 by querying each project's GitHub
repository and release metadata. Maintenance status is the fastest-moving fact
in this file — re-check `pushed_at` and the latest release before treating any
"active" or "stale" label here as current.

## Preflight

Detect before you invoke. If a tool is missing, print its install command and
continue with agent-native reasoning rather than aborting.

```bash
for t in forge slither aderyn solhint wake echidna medusa halmos hevm; do
  command -v "$t" >/dev/null 2>&1 && echo "found: $t" || echo "MISSING: $t"
done
```

Never hardcode a detector count. Enumerate at runtime:

```bash
slither --list-detectors
aderyn registry all
```

## Slither — the primary tool

Version `0.11.6`, released 2026-07-28. Actively maintained.

```bash
uv tool install slither-analyzer      # or: pip install slither-analyzer
brew install slither-analyzer         # macOS alternative
```

Requires Python 3.10 or newer. Pair it with `solc-select` so the compiler
matches each file's pragma — a mismatch produces compilation errors that look
like tool failures:

```bash
uv tool install solc-select
solc-select install 0.8.36 && solc-select use 0.8.36
```

### Invocations

Reconnaissance printers, which feed Phase 1's role and value-flow map:

```bash
slither . --print human-summary,contract-summary,vars-and-auth,entry-points,not-pausable
```

`vars-and-auth` is the one that earns its place: it prints, per contract, the
state variables written by each function and the authorization checks guarding
them. That is the access-control table Phase 2 Pass B asks you to build.

Human-readable report with clickable source links:

```bash
slither . --checklist \
  --markdown-root "https://github.com/ORG/REPO/blob/$(git rev-parse HEAD)/" \
  --filter-paths "lib/|test/|script/" \
  --exclude-dependencies
```

Machine-readable output for deduplication and for any SARIF consumer:

```bash
slither . --json slither.json --sarif slither.sarif --fail-none
```

`--fail-none` makes the exit code always zero, which is what a non-fatal
pipeline step needs. Without it Slither's exit code reflects findings and will
abort a shell running under `set -e`.

### Configuration and suppression

`slither.config.json` in the project root, read automatically:

| Key | Effect |
| --- | --- |
| `detectors_to_run` | Restrict the run to a named detector list |
| `exclude_dependencies` | Drop findings in installed dependencies |
| `exclude_informational` | Drop the informational tier |
| `filter_paths` | Regex of paths to exclude |
| `fail_on` | Which severity, if any, sets a non-zero exit code |

Interactive triage writes a persistent suppression database:

```bash
slither . --triage-mode        # writes slither.db.json
```

Inline, for a single site, with the detector named so the suppression does not
silently widen:

```solidity
// slither-disable-next-line reentrancy-no-eth
```

Prefer inline suppression with a comment explaining why over a config-wide
exclusion. A config exclusion hides the next occurrence too.

### Companion binaries

Installed by the same package, and each is worth knowing:

| Binary | Use |
| --- | --- |
| `slither-check-upgradeability` | Storage-layout and initializer checks across two implementations |
| `slither-read-storage` | Reads and prints on-chain or local storage layout |
| `slither-check-erc` | Conformance check against ERC-20, ERC-721, and related interfaces |
| `slither-mutate` | Mutation testing — measures whether the test suite would catch a change |
| `slither-flat` | Flattens a project into a single file |
| `slither-interface` | Generates an interface from a contract |
| `slither-doctor` | Diagnoses installation and compilation problems |
| `slither-prop` | Generates property tests for supported standards |

`slither-mutate` deserves more use than it gets: a high mutation-survival rate
tells you the invariant suite in `invariants-and-fuzzing.md` is decorative.

### False-positive character

High volume in the informational and low tiers — naming conventions, solc
version warnings, low-level calls, dead code, unused state. These are noise for
an audit and should be filtered before triage.

- `reentrancy-benign` and `reentrancy-events` are usually non-issues. Suppress
  both by default.
- `arbitrary-send-eth` and `unchecked-transfer` are the highest-signal
  detectors in the set. Read every hit.
- `reentrancy-eth` and `reentrancy-no-eth` are worth reading but frequently
  fire on a state write that is provably after the last external call in
  practice; validate with the call chain, not the detector name.

## Aderyn — the complementary static analyzer

Cyfrin's Rust analyzer. Active: the repository was last pushed 2026-07-26; the
most recent tagged release is `aderyn-v0.6.8`, 2026-01-22. The gap between the
two is worth noting — the tooling is developed continuously but tagged
infrequently, so an installer pulling "latest release" lags the branch.

```bash
curl --proto '=https' --tlsv1.2 -LsSf \
  https://github.com/cyfrin/aderyn/releases/latest/download/aderyn-installer.sh | bash
brew install cyfrin/tap/aderyn        # macOS
npm i -g @cyfrin/aderyn               # Node
cyfrinup                              # via the Cyfrin toolchain installer
```

Auto-detects Foundry and Hardhat projects, so it usually needs no
configuration.

```bash
aderyn . -x lib,test,script -o aderyn.json
aderyn . -x lib,test,script -o aderyn.md
```

**The output format is inferred from the file extension** — `.md`, `.json`, or
`.sarif`. There is no separate format flag. The default output path is
`report.md`.

| Flag | Meaning |
| --- | --- |
| positional | Project root directory, defaults to `.` |
| `-s`, `--src` | Source directory relative to root; auto-detected by default |
| `-i`, `--path-includes` | Comma-delimited path fragments to include |
| `-x`, `--path-excludes` | Comma-delimited path fragments to exclude |
| `-o`, `--output` | Report path; extension selects the format |
| `--highs-only` | Restrict to high-severity detectors |

Subcommands:

```bash
aderyn init                       # writes aderyn.toml for scan customization
aderyn registry all               # browse the detector registry
aderyn mcp stdio                  # MCP server over stdio
aderyn mcp http-stream --port 6277
```

**Aderyn ships an MCP server**, which is directly useful for agent use: an
agent can query detectors and drive scans over a protocol connection instead of
parsing CLI output. The `http-stream` transport binds port 6277 by default.

False positives: notably lower volume than Slither, and mostly stylistic when
they occur. That lower volume is exactly why running only Aderyn is a mistake —
it is a different detector set, not a better one. **Run both.** Where they
disagree, the disagreement is the interesting part; where they agree, raise
confidence but still keep one deduplicated record per `(file, line, class)`.

## Solhint — style gate, not an audit input

Version 6.2.3, actively maintained.

```bash
npm i -g solhint
solhint --init                                    # writes .solhint.json
solhint 'src/**/*.sol' -f sarif > solhint.sarif
```

Mostly style rules, with a few genuine security rules worth having in CI:
`avoid-tx-origin`, `not-rely-on-time`, `reentrancy`, `check-send-result`.

**Keep its output out of the findings report entirely.** Solhint findings are
lint, and mixing lint into an audit report is the fastest way to get the audit
report skimmed rather than read.

## Wake — proxy and storage detectors, plus a fuzzing framework

Ackee's Python toolkit, version 4.22.1.

```bash
pip3 install eth-wake
wake init
wake detect all --min-impact medium --min-confidence medium
wake print <printer>
```

Configuration lives in `wake.toml`.

Unique value over Slither and Aderyn: its proxy and storage-layout detectors,
and a pytest-based fuzzing framework using `@flow()` and `@invariant()`
decorators, which suits teams already fluent in Python better than a Solidity
harness does.

**Unverified: a SARIF or JSON export flag for `wake detect` could not be
confirmed from primary documentation.** Probe at runtime before scripting
around it:

```bash
wake detect --help
```

If no export flag exists, capture stdout and parse it, or treat Wake as an
interactive tool rather than a pipeline stage.

## Deliberately excluded

- **Mythril** — last release v0.24.8, March 2024. Stale for over two years.
  **Do not put it in the default pipeline.** Halmos and hevm cover the symbolic
  execution role with maintained code. It is named here only so a reader who
  expects it knows why it is absent.
- **4naly3er** — unmaintained; last repository push August 2024. Excluded.

## Semgrep for Solidity — optional, for ad-hoc rules

Best used not as a rule pack but as the vehicle for **project-specific rules
the agent writes during the review**. When Phase 1 establishes a project
convention — every ERC-20 movement routes through `SafeERC20`, every privileged
function carries a specific modifier — encoding that convention as a Semgrep
pattern turns "did they follow it everywhere" from a reading exercise into a
grep.

Caveats:

- `Decurity/semgrep-smart-contracts`, the best-known Solidity rule pack, has
  been stale since June 2025.
- The Solidity parser is a community tree-sitter grammar, not a first-party
  frontend, so parse coverage of newer syntax is not guaranteed.
- Semgrep patterns for Solidity are pattern-only. Any rule that actually needs
  dataflow will have high false positives. Write rules that assert a syntactic
  convention, not rules that try to find a vulnerability.

## Formal and symbolic

Highest assurance, highest cost, and the tier where maintenance status matters
most because a dormant symbolic tool silently stops supporting new syntax.

### Halmos

Version v0.3.3. Write `check_*` functions inside ordinary Foundry tests, so
there is no separate harness language to learn.

```bash
uv tool install halmos
halmos --function check_ --solver-timeout-assertion 0
```

**Maintenance caveat.** As observed on 2026-07-29 via the GitHub API, the
repository had no commits since 2025-08-06 and no release since 2025-07-31.
Whether that represents abandonment or a quiet period is a judgment, not a
verified fact — the project may resume. Treat Halmos as **at-risk**: use it if
it is installed and working, never hard-depend on it, and re-check the
repository before recommending it to a team.

### hevm

The repository **moved to `argotorg/hevm`**; `ethereum/hevm` redirects there.
Release 0.58.0, June 2026. Active.

```bash
hevm test                       # runs Foundry prove_* tests symbolically
hevm equivalence --code-a <bytecode> --code-b <bytecode>
```

`hevm equivalence` is uniquely useful and underused: it proves two bytecode
objects have equivalent semantics. For an upgrade that is supposed to be a
refactor with no behavior change, it converts "we reviewed the diff" into a
proof. Nothing else in this file does that.

### Kontrol

Version v1.0.255, June 2026. Active. Highest assurance and highest cost.

```bash
kup install kontrol
kontrol build
kontrol prove --match-test <TestName>
```

Budget days per property, not minutes. Realistic only for a protocol holding
meaningful value, and only for the two or three properties whose violation
would be catastrophic.

### Certora Prover

```bash
pip install certora-cli
certoraRun <spec and config>
```

Requires a `CERTORAKEY` environment variable and runs on Certora's cloud, so it
is **not usable unattended** and not usable at all without an account.

**There is no self-serve free tier.** Free access for academic and open-source
projects exists by request; **the current terms of that program are
unverified** and should be checked with Certora directly rather than assumed.
Do not put Certora in a default pipeline for a project-agnostic skill.

### SMTChecker

Built into `solc` (v0.8.36, July 2026). Free, zero-install, and off by default.

**It does not check overflow at Solidity 0.8.7 and above**, because checked
arithmetic makes the check redundant for ordinary expressions — which also
means it does not help with the `unchecked`, assembly, and downcast cases that
`../SKILL.md` calls out as the real arithmetic risk.

```bash
solc --model-checker-engine chc \
  --model-checker-targets "underflow,overflow,assert,divByZero,outOfBounds" \
  --model-checker-timeout 20000 <file>
```

Or, in `foundry.toml`, under `[profile.default.model_checker]`.

On a real codebase, expect heavy timeouts and a large volume of "unproved
target" output that is neither a pass nor a failure. Genuinely useful for small
pure-math libraries — a fixed-point library, a curve implementation — and close
to useless on a full protocol.

## Summary

| Tool | Role | Status (2026-07-29) | In default pipeline |
| --- | --- | --- | --- |
| Slither | Primary static analysis, printers | Active, 0.11.6 | Yes |
| Aderyn | Complementary static analysis, MCP server | Active | Yes |
| Solhint | Style gate | Active, 6.2.3 | Yes, output kept separate |
| Wake | Proxy and storage detectors, Python fuzzing | Active, 4.22.1 | Optional |
| Semgrep | Ad-hoc project-specific rules | Engine active, Solidity packs stale | On demand |
| Halmos | Symbolic checks in Foundry tests | At-risk, dormant since 2025-08 | Best effort |
| hevm | Symbolic tests, bytecode equivalence | Active, 0.58.0 | Best effort |
| Kontrol | Deep formal proofs | Active, v1.0.255 | On demand only |
| Certora | Commercial formal verification | Active, no free self-serve tier | No |
| SMTChecker | Built-in bounded model checking | Ships with solc | Math libraries only |
| Mythril | Symbolic execution | Stale since 2024-03 | No |
| 4naly3er | Static analysis | Unmaintained since 2024-08 | No |
