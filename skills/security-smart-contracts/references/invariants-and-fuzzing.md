# Invariants and fuzzing

Every High or Medium finding should carry a failing Foundry proof-of-concept
test, or be tagged explicitly as `theoretical`. This file is how to write that
test, and how to build the invariant suite that finds the next finding without
being asked.

Versions were verified on 2026-07-29 from each project's release metadata.

## Foundry

Version v1.7.1.

```bash
curl -L https://foundry.paradigm.xyz | bash && foundryup
```

### Stateless fuzzing

A `testFuzz_*` function takes parameters and Foundry generates values for them.
Stateless fuzzing finds input-handling bugs — bad bounds, truncation, division
by zero — but cannot find anything requiring a sequence of calls.

```toml
[fuzz]
runs = 10000
max_test_rejects = 65536
seed = "0x1"
```

Set `seed` when you need a reproducible run, and unset it the rest of the time
so successive runs explore different space.

### Stateful invariants

An `invariant_*()` function is re-checked after sequences of calls into the
targeted contracts. This is where real findings come from.

```solidity
function setUp() public {
    handler = new Handler(vault, asset);
    targetContract(address(handler));
    bytes4[] memory selectors = new bytes4[](3);
    selectors[0] = Handler.deposit.selector;
    selectors[1] = Handler.withdraw.selector;
    selectors[2] = Handler.transfer.selector;
    targetSelector(FuzzSelector({addr: address(handler), selectors: selectors}));
}

function invariant_solvency() public view {
    assertGe(asset.balanceOf(address(vault)), vault.totalDeposits());
}
```

Targeting primitives:

| Primitive | Effect |
| --- | --- |
| `targetContract(addr)` | Restrict fuzzing to this contract, called in `setUp()` |
| `targetSelector(FuzzSelector(...))` | Restrict to named selectors on a contract |
| `excludeSelector(...)` | Remove a selector from an otherwise targeted contract |
| `excludeContract(addr)` | Remove a contract from automatic targeting |

**Use `bound(x, lo, hi)` rather than `vm.assume`.** `vm.assume` discards inputs
that fail the predicate, so a narrow predicate throws away most of the run and
the fuzzer explores far less than the `runs` count suggests. `bound` maps every
input into the valid range instead, so no run is wasted. Reserve `vm.assume`
for cheap predicates that reject a small fraction of inputs, such as
`vm.assume(addr != address(0))`.

### The handler pattern

Do not target the protocol contracts directly. Target a **handler** that bounds
inputs, tracks ghost variables, and rotates through an actor array. Direct
targeting produces a run in which almost every call reverts on input validation
and the fuzzer never reaches interesting state.

```solidity
contract Handler is Test {
    uint256 public ghost_depositSum;      // ghost variable
    address[] internal actors;

    function deposit(uint256 actorSeed, uint256 amount) public {
        address actor = actors[bound(actorSeed, 0, actors.length - 1)];
        amount = bound(amount, 1, asset.balanceOf(actor));
        vm.startPrank(actor);
        asset.approve(address(vault), amount);
        vault.deposit(amount, actor);
        vm.stopPrank();
        ghost_depositSum += amount;       // the invariant compares against this
    }
}
```

Ghost variables let an invariant assert a relationship the contract does not
itself store — the sum of everything ever deposited, the maximum share price
seen, the count of successful withdrawals. Most interesting invariants need
one.

### Invariant configuration

```toml
[invariant]
runs = 256
depth = 500
fail_on_revert = true
shrink_run_limit = 5000
check_interval = 1
max_time_delay = 604800
max_block_delay = 50000
```

| Knob | Effect |
| --- | --- |
| `runs` | Number of independent call sequences |
| `depth` | Calls per sequence |
| `fail_on_revert` | Whether a reverting call fails the run |
| `shrink_run_limit` | Effort spent minimizing a failing sequence |
| `check_interval` | `0` checks only after the last call; `N` checks every N calls |
| `max_time_delay` | Upper bound on simulated `block.timestamp` jumps |
| `max_block_delay` | Upper bound on simulated `block.number` jumps |

Two of these decide whether the suite is real:

- **Start with `fail_on_revert = true` and a handler that bounds inputs.**
  Relaxing it early is the standard way to end up with a green suite that
  explores nothing: every call reverts on a `require`, no state changes, the
  invariant trivially holds, and the run reports success. If a run fails
  immediately with `fail_on_revert = true`, the fix is to tighten the handler's
  bounds, not to turn the flag off.
- **Use `max_time_delay` for anything time or interest-rate dependent.**
  Without it the fuzzer never advances the clock far enough to accrue interest,
  expire a deadline, or cross a vesting boundary, and an entire class of bugs is
  unreachable.

`check_interval` is the other underused knob: with the default of checking only
at the end of a sequence, an invariant that is violated mid-sequence and
restored before the last call is never seen.

### Coverage

```bash
forge coverage --report lcov --report-file lcov.info \
  --no-match-coverage "(test|script|mock)" --ir-minimum
```

`--ir-minimum` is the standard fix for "stack too deep" during coverage
instrumentation. Read coverage as a floor, not a target: an uncovered branch is
definitely unreviewed, but a covered branch is not necessarily correct. Pair it
with `slither-mutate` (see `tooling.md`) when the question is whether the tests
would actually catch a change.

## The six invariant families

Generate these for any protocol before inventing project-specific ones. They
cover the majority of what stateful fuzzing finds in practice.

| Family | Statement | Typical assertion |
| --- | --- | --- |
| Conservation | Nothing is created or destroyed outside mint and burn | Sum of user balances equals `totalSupply`, or sum of shares equals vault total |
| Solvency | The contract can honor its liabilities | `asset.balanceOf(vault) >= totalDeposits` |
| Monotonicity | A value that should only move one way does | Share price never decreases across a deposit or a withdrawal |
| Access | Only role holders mutate privileged state | Privileged state is unchanged after any sequence of non-role calls |
| Round trip | A user cannot profit from a no-op | Deposit then immediately withdraw never returns more than was deposited |
| No stuck funds | Every path in has a path out | For every deposit, some sequence of calls returns the assets |

Two notes that decide whether these find anything:

- **Rounding must favour the protocol**, so the round-trip invariant is an
  inequality, not an equality. Assert `received <= deposited`. Writing it as an
  equality produces a suite that fails on legitimate rounding and gets deleted.
- The **access** invariant is the one that maps to OWASP SC01, now the top
  class. It is also the easiest to write: snapshot every privileged storage
  slot in the invariant and assert the snapshot is unchanged unless a
  role-holding actor was used.

## `crytic/properties` — pre-built property suites

**This is the highest return per line of any item in this file** for a token or
vault repository. Instead of writing properties, inherit them.

```bash
forge install crytic/properties
```

| Standard | Properties |
| --- | --- |
| ERC-20 | 25 |
| ERC-721 | 19 |
| ERC-4626 | 37 |
| ABDKMath64x64 | 106 |

The harness inherits the relevant base — `CryticERC20BasicProperties`,
`CryticERC4626PropertyTests`, and so on — and wires the system under test in:

```solidity
contract VaultProperties is CryticERC4626PropertyTests {
    function setUp() public {
        asset = new TestERC20();
        vault = new Vault(address(asset));
        initialize(address(vault), address(asset), false);
    }
}
```

The ERC-4626 suite in particular encodes the rounding-direction and
inflation-attack properties that are tedious to derive and easy to get subtly
wrong by hand.

## Echidna

Version v2.3.3, July 2026. Very actively maintained.

```bash
brew install echidna
docker pull ghcr.io/crytic/echidna/echidna
```

```bash
echidna . --contract MyHarness --test-mode assertion \
  --corpus-dir echidna-corpus --config echidna.yaml
```

Test modes: `property`, `assertion`, `dapptest`, `optimization`, `overflow`,
`exploration`. Use `assertion` for a Foundry-style harness with `assert`
statements, `property` for `echidna_*` boolean functions, and `exploration`
when you want coverage without any property, as a way to see what the fuzzer
can reach.

The 2.3.x line **generates Foundry reproducers for failed assertions**, which
closes the loop back to the proof-of-concept requirement in `../SKILL.md`: a
counterexample arrives as a runnable failing test.

Keep `--corpus-dir` and commit the corpus. It is the accumulated exploration
work of every previous run, and discarding it means starting from zero.

False positives: near zero. A counterexample is a concrete call sequence that
actually produced the violation, so it is either real or the harness is wrong.
**The failure mode is false negatives** — a harness that bounds inputs too
tightly, forgets an actor, or never advances time reports success while
exploring a fraction of the state space. Judge a fuzzing campaign by its
coverage and corpus, not by its exit code.

## Medusa

Version v1.5.1.

```bash
go install github.com/crytic/medusa@latest
medusa init                    # writes medusa.json
medusa fuzz --target-contracts MyHarness --corpus-dir medusa-corpus
```

Parallelized across cores, which Echidna is not. **Prefer Medusa when cores are
available**, and Echidna when you need its more mature shrinker to reduce a
long failing sequence into something readable. Running both against the same
harness costs one command each and they explore differently.

## Hardhat repositories

Do not try to reproduce this in JavaScript. **Recommend adding a Foundry
sidecar** — Foundry and Hardhat coexist in one repository, and both Aderyn and
Slither auto-detect either build system. The invariant tooling, the property
libraries, and the fuzzer integrations described here all assume Solidity
harnesses, and reimplementing them against a JavaScript test runner gives up
every one of them.
