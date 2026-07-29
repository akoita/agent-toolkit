# AI and ML supply chain review

Corresponds to LLM03 Supply Chain and LLM04 Data and Model Poisoning, and to
ASI04 Agentic Supply Chain Vulnerabilities on the agentic list. The unit of
review is every artifact that enters the process: weights, configuration,
tokenizer files, custom code, datasets, and the registry they came from.

## Pickles and `torch.load`

`weights_only=True` became the **default in PyTorch 2.6.0**. It is a large
improvement and **not a hard boundary**:

- **CVE-2025-32434** (published 2025-04-18, CVSS 9.3) is remote code execution
  in `torch.load` **with `weights_only=True`** on PyTorch 2.5.1 and earlier,
  patched in 2.6.0. Verified against the CVE record.
- Every explicit `weights_only=False` is a live remote-code-execution path,
  regardless of PyTorch version. Treat each one as a finding requiring a
  written justification and a pinned, digest-verified artifact.

## safetensors is not "safe model"

safetensors guarantees no code execution **for the tensor file**. It covers
none of the following, all of which ship in the same repository and all of
which execute or are interpreted:

- `config.json`
- `modeling_*.py` and any other custom module
- tokenizer files and tokenizer configuration
- the Jinja `chat_template`

Read those files. Grep them for `eval`, `exec`, `os.system`, `subprocess`,
`__import__`, `pickle`, and outbound network calls. A repository advertised as
"safetensors only" that ships a `modeling_*.py` has not removed the risk.

## `trust_remote_code` and the bypass

`trust_remote_code` defaults to `False` in `transformers`, and that default is
load-bearing — but it has been bypassed.

**CVE-2026-4372** (published 2026-05-24, CVSS 7.8, verified against the CVE
record): a malicious `config.json` containing an `_attn_implementation_internal`
field set to an attacker-controlled Hub repository ID reached dynamic module
import on a standard `from_pretrained()` call, **without** the user setting
`trust_remote_code=True`. The CVE record states it affects **all versions
before 5.3.0**, patched in **transformers 5.3.0**.

Minimum version bars to assert in a review:

| Package | Minimum |
| --- | --- |
| `torch` | ≥ 2.6.0 |
| `transformers` | ≥ 5.3.0 |
| `datasets` | ≥ 4.0 |
| `safetensors` | ≥ 0.8.0 |

## The greps that pay

```bash
grep -rn "trust_remote_code" .
grep -rn "weights_only=False" .
grep -rn "from_pretrained(" . | grep -v "revision="
```

- Every `trust_remote_code=True` needs a pinned `revision=<sha>` **and** a
  written justification. Without the pinned revision it is a standing
  invitation, because the upstream repository can change under it.
- Every `weights_only=False` is an RCE path, as above.
- Every `from_pretrained()` without `revision=` is a mutable reference to
  third-party code and weights. A tag is not a pin; use a commit SHA.

## Scanners, and their limits

| Tool | Install | Invocation | Notes |
| --- | --- | --- | --- |
| `picklescan` | `pip install picklescan` | `picklescan --path DIR --strict` | Exit 0 clean, 1 malware, 2 error — a clean CI gate |
| `modelscan` | `pip install 'modelscan[tensorflow,h5py]'` | `modelscan -p path/` | Broader format coverage than picklescan |
| `modelaudit` (MIT) | `pip install modelaudit` | `modelaudit scan model.pkl --format sarif` | Best CI story: 42+ formats, SARIF output |
| `fickling` (Trail of Bits) | `pip install fickling` | AST-level analysis of pickle streams | Use for deeper manual investigation of a suspicious artifact |

**Scanners are a filter, not a boundary.** A July 2026 preprint
(arXiv 2607.17503) claims 0% detection by both picklescan and modelscan for a
new evasion family; the result is **author-reported and unrefereed**, so treat
it as unverified. The engineering conclusion holds either way: fail closed on
a scanner hit, but never treat a clean scan as proof that an artifact is safe.
The boundary is provenance plus sandboxed loading, not detection.

## Provenance and signing

**OpenSSF Model Signing** is at **Sandbox stage** — `ossf/model-signing-spec`
for the specification, `sigstore/model-transparency` for the implementation,
and the `model-signing` package on PyPI (latest release 1.1.1, uploaded
October 2025).

The property that makes it worth adopting: a signature is a **detached
Sigstore bundle over an in-toto statement that hashes every file** in the
model directory. That covers the configuration, custom code, and tokenizer
gap that safetensors leaves open. Verify signatures before load, and make the
verification a hard gate rather than a log line.

Emit a **CycloneDX ≥ 1.5 ML-BOM** or an **SPDX 3.0 AI-profile BOM** listing
every model and dataset with digests. Without digests a BOM records intent,
not what actually loaded.

## Dataset poisoning

The important recent correction: **poisoning scales with document count, not
percentage.** A 2025 study across model sizes found that backdoor poisoning
needs a near-constant number of poisoned documents — around 250 — regardless
of model size or dataset size. This invalidates the common assumption that an
attacker needs to control a meaningful percentage of the training corpus, and
it means scale is not a defence.

Web-scale datasets are additionally vulnerable to **split-view poisoning** (the
content at a URL changes between the crawler's visit and the consumer's
download) and **frontrunning poisoning** (transient edits to a source timed to
land in a snapshot), described in arXiv 2302.10149. Ask for content digests
recorded at crawl time and verified at use time.

For fine-tuning and RAG ingestion specifically, ask who can write to the
corpus, whether ingestion is authenticated, and whether provenance survives
chunking.

## The model hub is not a trust anchor

Hugging Face disclosed a security incident in July 2026
(`https://huggingface.co/blog/security-incident-july-2026`): initial access
through two dataset code-execution paths led to remote code execution on
data-processing workers and to credential harvesting. HF reported impact
limited to internal datasets and service credentials, with no evidence of
tampering with public models, datasets, or Spaces, and advised rotating
tokens.

Reported attribution to an AI agent run without production safety classifiers
comes from **secondary sources and is unverified** — do not repeat it as fact.

The engineering consequence is what belongs in a review, and it does not
depend on the attribution: pin `revision=<sha>`, verify digests on every
artifact, verify signatures where available, and treat **registry-side
compromise as in scope** rather than as an assumption you get to make.
