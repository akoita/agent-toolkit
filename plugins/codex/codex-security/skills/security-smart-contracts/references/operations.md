# Operations

Everything that decides whether audited code stays safe after deployment:
upgrade safety, source verification, key custody and governance, monitoring,
incident response, and a short pointer set for non-EVM chains.

A review that stops at the source misses the majority of realized losses. An
EOA owner with no timelock defeats a clean audit; so does an unverified proxy
implementation that nobody can read.

Status notes were verified on 2026-07-29 from each project's repository and
release metadata.

## Upgrade safety

**OpenZeppelin Upgrades**, actively maintained, is the reference tooling for
validating that an upgrade does not corrupt storage or introduce an unsafe
operation.

Foundry:

```bash
forge install OpenZeppelin/openzeppelin-foundry-upgrades
```

```solidity
Upgrades.deployUUPSProxy("V1.sol:V1", abi.encodeCall(V1.initialize, (owner)));
Upgrades.validateUpgrade("V2.sol:V2", opts);
```

Both require `ffi = true` and `build_info = true` in `foundry.toml`, because
validation runs an external process over the compiler's build info. A team that
has `ffi` disabled for good reasons should run validation in a dedicated
profile rather than enabling it globally.

Hardhat: `@openzeppelin/hardhat-upgrades` provides `validateUpgrade` and
`upgradeProxy`, which run a storage-layout diff and check for unsafe
operations — `selfdestruct`, `delegatecall`, constructors, and mutable state
initialized outside an initializer.

**Cross-check with a second implementation.** These checks are static and
conservative, and they disagree with Slither's in useful ways:

```bash
slither-check-upgradeability . ContractV1 --new-contract-name ContractV2
slither-read-storage . --contract-name Contract
```

`slither-read-storage` also reads live storage from a node, which is the only
way to confirm that a *deployed* proxy's layout matches what the repository
says it should be. Reviewing the source diff is not a substitute for either
check.

## Source verification

An unverified contract cannot be reviewed by users, integrators, or incident
responders. Verification is a security control, not a nicety.

```bash
forge verify-contract <address> src/Contract.sol:Contract \
  --chain <chain-id> --etherscan-api-key "$ETHERSCAN_API_KEY"
```

Etherscan V2 uses **a single multichain API key**, with the chain identified
per request rather than by hostname, so one key covers every supported chain.

For chain-agnostic, free verification with no account:

```bash
forge verify-contract <address> src/Contract.sol:Contract \
  --chain <chain-id> --verifier sourcify
```

`forge script --verify` performs deployment and verification in one pass, which
is the practical way to avoid an unverified window on a multichain deploy.

Assert all four before calling a deployment done:

1. Deployed bytecode matches the reviewed source.
2. Constructor arguments are published.
3. **No proxy is left with an unverified implementation.** Verifying the proxy
   and not the implementation verifies nothing that matters.
4. The metadata hash is reproducible from the repository at the tagged commit.

## Keys and governance

The controls here are usually the difference between an incident and a
catastrophe.

- **A Safe with a genuine M-of-N of independent signers.** "Genuine" is the
  operative word: three signers who are three laptops belonging to the same
  person is 1-of-1 with extra steps. Check that signers are distinct people, in
  distinct locations, with distinct devices.
- **A 24 to 72 hour timelock on every upgrade and every parameter change.** The
  timelock is what gives users an exit and gives monitoring time to fire. A
  timelock that admin functions can bypass is not a timelock.
- **Separate deployer, owner, pauser, and upgrader roles.** The pauser should
  be the fastest and lowest-ceremony of the four, because pausing is the action
  you want to be able to take in ninety seconds.
- **Hardware wallets or MPC for every signer.** A hot key on a server that can
  upgrade a contract is the single highest-value target in the system.
- **No EOA owner on anything holding funds.** Ever.
- **Publish the timelock queue** somewhere users actually read. A timelock
  nobody can observe provides no exit window.

## Monitoring

**Important 2026 change.** **OpenZeppelin Defender's hosted service sunsets
2026-07-01**, and new sign-ups closed 2025-06-30. **Do not recommend its free
tier** — it is the most commonly cited option in older material and it is gone.
The replacement is the **self-hosted, open-source Relayer and Monitor**.

**`forta-network/forta-bot-sdk` has not been pushed since January 2024.** Flag
it as stale wherever a project still depends on it.

Practical free options today:

| Option | Shape | Notes |
| --- | --- | --- |
| Self-hosted OpenZeppelin Monitor | Runs in your infrastructure | The direct successor to Defender's monitoring |
| Tenderly alerts, free tier | Hosted | Fastest to stand up; check current free-tier limits |
| A small `cast logs` or viem watcher | A few dozen lines you own | No vendor, no limits, no dashboard |

Whatever the vehicle, monitor at least: every privileged-role call, every
timelock queue and execute, every pause and unpause, every upgrade, large or
anomalous transfers relative to TVL, and any invariant from
`invariants-and-fuzzing.md` that can be evaluated on chain. An invariant worth
fuzzing is an invariant worth alerting on.

## Incident response

- **A pause or circuit breaker that is deployed *and tested*.** An untested
  pause is a hypothesis. Exercise it on a fork, and time how long it takes from
  decision to executed transaction.
- **A documented war room and on-call rotation**: who is paged, on what
  channel, with what authority to act without further approval.
- **Pre-drafted disclosure.** Writing the first public statement during the
  incident guarantees it is late and badly worded.
- **A bug bounty** with a stated scope, a stated payout range, and a real
  response time. An unanswered report becomes a public disclosure.
- **A rehearsed upgrade-under-pressure runbook.** The first time the team
  executes an emergency upgrade should not be during an emergency, and the
  timelock interacts with this — know in advance whether the emergency path
  bypasses it and who can authorize that.
- **An off-chain kill switch for relayers and keepers.** Much of a protocol's
  activity is driven by off-chain infrastructure you control directly, and
  stopping it is faster than any on-chain transaction.

## Non-EVM, briefly

Enough to recognize the surface and reach for the right tool. Depth for these
chains is outside this skill's scope.

### Solana

```bash
cargo install cargo-audit && cargo audit     # dependency advisories
radar -p <program-dir>                       # Auditware/radar, Docker-based
```

**Radar** (`Auditware/radar`) is actively maintained and supports custom
detectors written in YAML, which makes it the closest analogue to Semgrep for
Anchor programs. **Trident** (`Ackee-Blockchain/trident`) is the actively
maintained fuzzer for Anchor.

Manual class list, which no tool covers completely:

- Missing `Signer` check, or a missing owner check on an account.
- Missing account discriminator check, or a missing `has_one` constraint.
- **PDA seed collisions**, and missing bump canonicalization — accepting a
  caller-supplied bump instead of the canonical one.
- **Arbitrary CPI target** — invoking a program id taken from an account rather
  than a constant.
- **`close` without zeroing**, leaving a revivable account.
- **Unvalidated `remaining_accounts`**, which are entirely caller-controlled.
- **Overflow in release profiles without `overflow-checks`** — Rust wraps in
  release builds by default, and the Cargo profile is the only thing standing
  between you and silent wrapping.

### Move

`aptos move prove` ships in the Aptos CLI and runs the Move Prover against
specifications written alongside the code. A **Sui Prover** was open-sourced in
January 2026; **its canonical repository path could not be resolved and is
therefore unverified** — locate it from current Sui documentation rather than
guessing a path.

### Cairo and Starknet

The weakest tooling story of the three. `crytic/caracal` has been stale since
January 2024, and `crytic/amarna` is **archived**. Lean on `snforge` fuzzing
and on manual review; do not present static analysis coverage for Cairo as
comparable to Solidity's.
