Plan is sound, with two checks before editing:

- Inspect how `updated_text()` handles marker order. Equal counts alone permit an end marker before a start marker, which is malformed and must exit 2. If that case is currently accepted, add an explicit order check and regression coverage. Also test lone start/end markers and duplicated pairs.
- Inspect whether `read_existing()` normalizes line endings before comparison. Preserve the existing LF/CRLF generation behavior, and ensure a clean CRLF target returns 0 with its bytes untouched.

Returning 2 for caught `ValueError` is appropriate under the stated invalid-input contract, although it changes those errors for preview/apply too. Preserve their successful behavior and messages. Do not broaden exception handling indiscriminately; inspect existing filesystem-error handling and conventions first.

Recommended test organization:

1. Create valid policy fixtures using the normal apply CLI in a temporary directory, then run checks against clean LF and CRLF targets.
2. Exercise stale content, a missing target in an existing directory, and a missing target beneath nonexistent parents. Check returns 1 and leaves each filesystem state unchanged.
3. Snapshot target bytes and directory entries before and after clean, stale, and malformed checks. This catches writes and backups, including writes that preserve visible text.
4. Test exit 2 for conflicting flags, invalid project root, incompatible global/project-root arguments, malformed markers, symlinks, non-file targets, and invalid UTF-8 where applicable.
5. Include a preview/apply smoke test in the new test file: preview still returns 0 without mutation; apply repairs drift; the subsequent check returns 0.

The check branch should occur after generation/validation and before every mutation path. Existing diff output is reasonable; no separate output contract was specified. Keep all tests in temporary directories and preserve existing tests.
