# MCP server and client review

The **current MCP specification revision is `2026-07-28`**; the previous
stable revision is `2025-11-25`. Both the revision list and the normative
requirements below were verified against
`https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization`.
Re-check the revision before quoting it — this specification moves.

Review in two passes. First the normative requirements, which are checkable
against the server's source. Then the ecosystem risks, which the
specification does not cover and which produce most real incidents.

## Pass 1: normative requirements

### Roles and token audience

- A protected MCP server acts as an **OAuth 2.1 resource server**.
- The server **MUST validate that every access token was issued specifically
  for it as the intended audience** (RFC 8707 Section 2). Read the token
  validation path and confirm the audience check exists and fails closed.
- The server **MUST NOT** accept a token issued for anything else, and
  **MUST NOT** forward a received token upstream. Token pass-through is the
  confused-deputy bug of this ecosystem.
- Clients **MUST NOT** send the server any token other than one issued by
  that server's own authorization server.
- Invalid or expired tokens **MUST** receive HTTP 401.
- Authorization is OPTIONAL overall, but implementations on an HTTP-based
  transport SHOULD conform. **STDIO transports SHOULD NOT use this flow** —
  they retrieve credentials from the environment, so a stdio server carrying
  an OAuth implementation is a smell worth questioning.

### Discovery and resource indicators

- **RFC 9728** Protected Resource Metadata must be served by the server, and
  clients must use it for authorization-server discovery.
- **RFC 8707** resource indicators must be sent in **both** the authorization
  request and the token request, carrying the canonical server URI, and
  clients **MUST send this parameter regardless of whether the authorization
  server supports it**. Grep the client for `resource=` on both legs; sending
  it on only one is the common defect.
- The **RFC 9207 `iss`** parameter must be validated against a recorded
  issuer before the authorization code is sent to any token endpoint. The
  specification is explicit that after decoding `iss`, clients **MUST NOT
  apply scheme or host case folding, default-port elision, trailing-slash, or
  percent-encoding normalization** before comparison. Any URI-normalizing
  helper in that code path is a finding. The rule **applies to error
  responses too**: on mismatch the client must not act on or display `error`,
  `error_description`, or `error_uri`.

### Tokens, registration, and scopes

- **Access tokens MUST NOT appear in the URI query string.** Tokens go in the
  `Authorization: Bearer` header on every request. Grep for tokens in URLs,
  in redirect targets, and in log statements.
- **Dynamic Client Registration (RFC 7591) is now deprecated** and retained
  only for backwards compatibility. **Client ID Metadata Documents**
  (`draft-ietf-oauth-client-id-metadata-document-00`) are the preferred
  mechanism. A new implementation standing up open DCR should justify it.
- `scopes_supported` should advertise a **minimal baseline**, with step-up
  handled through a `WWW-Authenticate` challenge carrying `scope=` and a 403
  `insufficient_scope` response. No wildcard scopes, no omnibus
  read-write-everything scope.

### Sessions

- **Sessions MUST NEVER be used for authentication.** A session identifier is
  not a credential.
- Session identifiers must be non-deterministic, and should be bound to the
  user as `<user_id>:<session_id>`.
- **Every inbound request must be independently authorized.** Look for
  handlers that trust a session lookup and skip the token check.

### Third-party API proxying

A server that proxies a third-party API on the user's behalf must:

- keep a **per-client consent registry**, checked before initiating the
  upstream flow, so an unapproved client cannot ride an existing grant;
- use **exact-match `redirect_uri`** comparison, never prefix or wildcard;
- set the `state` cookie **only after** consent is granted;
- use `__Host-` prefixed cookies with `Secure`, `HttpOnly`, and
  `SameSite=Lax`.

### Server-side request forgery and URL handling

- OAuth discovery fetches must **block RFC 1918 ranges, loopback, and
  `169.254.169.254`**, enforce HTTPS, and **re-validate every redirect hop**
  rather than only the initial URL. Consider DNS rebinding: resolve-then-pin,
  or re-check the resolved address at connect time.
- URLs received from a server must be **scheme-allowlisted to `http` and
  `https`**. Never `javascript:`, `data:`, `file:`, or `vbscript:`.
- URLs must **never be opened by shelling out** to a browser or opener
  command, which reintroduces argument injection.

### Local server installation

A one-click local server configuration flow must **display the full,
untruncated command** and require explicit approval. A truncated command
string in an install prompt is a finding on its own.

## Pass 2: ecosystem risks the specification does not cover

These are where the incidents are. None is addressed by the authorization
specification, and a fully conformant server can have all of them.

| Risk | What to look for |
| --- | --- |
| **Tool poisoning** | Malicious instructions inside a tool *description*. The description reaches the model verbatim and is usually invisible to the user. Read every description in full, including whitespace-padded and non-ASCII content. |
| **Rug-pulls** | A description that mutates after the user approved it. Pin or hash-check tool descriptions and alert on change. |
| **Cross-server tool shadowing** | One server's description redefining or intercepting another server's tool. Review the full merged tool catalog, not one server at a time. |
| **Injection through tool results** | Result payloads are attacker-controlled text arriving in an instruction-adjacent position. See `references/llm-application-review.md`. |
| **Over-broad scopes** | A server requesting far more than its tools need, so one compromise yields a wide token. |
| **Mutable launch commands** | Servers launched with a bare `npx pkg@latest` or `uvx pkg@latest` pull a mutable version on every start. Pin a version or a digest. |
| **Registry trust** | The official MCP registry authenticates **namespaces only** — reverse-DNS ownership via GitHub OAuth or a DNS TXT record. It does not review or attest code. A namespaced entry is not a vetted entry. |

Map findings to the OWASP MCP Top 10 identifiers where useful; note in the
report that the project is at **v0.1, Phase 3 beta**, not a final release.

## Scanners

- **`snyk-agent-scan`** (formerly Invariant Labs' `mcp-scan`, Apache-2.0,
  actively maintained). Run `uvx snyk-agent-scan@latest`, then
  `snyk-agent-scan scan [CONFIG…]` or `snyk-agent-scan inspect`. It
  auto-discovers agent configurations and **scans agent skills by default**
  (`--no-skills` to skip). Real constraints to state before recommending it:
  it requires a `SNYK_TOKEN`, it **sends tool names, descriptions, and skills
  to Snyk**, and non-interactive use requires
  `--dangerously-run-mcp-servers`. That data-egress property disqualifies it
  in some environments; say so rather than discovering it later.
- **Tencent AI-Infra-Guard** (Apache-2.0) is the fully local alternative. Its
  standalone skill scanner installs with `pip install aig-skill-scan` and runs
  as `aig-skill-scan --repo ./skill -o result.json`.
- **Generic SAST on the server source.** Semgrep or Opengrep remains the right
  tool for the server's own code. Note that Semgrep's own MCP server
  repository was archived in October 2025 — that is the MCP integration, not
  the scanner, which is unaffected.

Two negative results worth stating plainly, because both get recommended from
memory:

- **There is no single authoritative `mcp-audit` project. Do not recommend
  one by name.**
- The `mcpsafetyscanner` reference implementation from the MCP safety-audit
  paper still exists at `johnhalloran321/mcpSafetyScanner`, but it has had no
  commits since **April 2025**. Treat it as unmaintained research code rather
  than a scanner to put in CI. (Repository state checked via the GitHub API;
  the brief for this skill described it as deleted, which no longer matches
  what the API returns — re-check before citing either way.)

## Related surface

A repository that ships agent skills or plugins has the same trust problem as
a tool description: text authored by a third party that reaches a model's
context verbatim. That checklist — the ToxicSkills findings,
`SKILL.md`/`CLAUDE.md`/`AGENTS.md`/settings files as executable content,
CVE-2025-59536, and the reviewer steps — lives under "Repositories that ship
agent skills and plugins" in `references/agent-runtime-hardening.md`, since
the enforcing controls are harness permissions and hooks.
