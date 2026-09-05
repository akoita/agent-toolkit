The plan is sound. Keep dry-run decisions in the helpers, but share validation with normal execution so conflict behavior cannot drift.

Key corrections and edge cases:

- Detect destinations with `destination.exists() or destination.is_symlink()`. `exists()` alone misses dangling symlinks; dry-run must reject or preview replacing them exactly as real installation does.
- Preserve the current same-source guard, including its behavior under `--force` and `--link`. Inspect what that guard actually returns or raises before changing ordering.
- Inspect `remove_existing` for special handling beyond existence and force. Prefer extracting a read-only conflict check used by both paths, or gating its mutations explicitly; do not invoke a potentially destructive helper during preview.
- Preserve normal operation ordering unless required for dry-run. Moving every check before `mkdir` would also change ordinary behavior on failures, beyond this request.
- A missing source/template or unreadable modified-agent destination should not silently produce a successful preview. Inspect current validation and exception handling, then preserve applicable errors without simulating every possible filesystem permission failure.
- Ensure uninstall selection and legacy-agent warnings still run through the existing main path. Preview must never remove the legacy agent.

Verification should establish both correct decisions and absence of mutation:

1. Use temporary roots with nonexistent parents; preview install and uninstall, then assert the complete absent parent chain remains absent.
2. Snapshot existing destination content, directory entries, and symlink targets before/after force install and force uninstall. Include an unrelated sentinel file.
3. Exercise existing regular files, directories, valid symlinks, and dangling symlinks as install conflicts. Verify nonzero exit without force and unchanged destinations with either force setting.
4. Test unchanged and modified agent uninstall: unchanged previews removal; modified previews “kept” without force and removal with force, preserving bytes in both cases.
5. Assert selectors suppress unselected actions, custom paths appear in output, and link previews describe linking.
6. Consider a direct-helper test patching the module’s mutation entry points to raise if called during dry-run. State snapshots cannot detect a write followed by restoration or incidental metadata changes.

Check whether `main` catches `FileExistsError` and where it stops the template loop; dry-run should retain the same exit behavior, rather than collecting conflicts into an inadvertently successful preview.
