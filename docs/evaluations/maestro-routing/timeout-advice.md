The plan is sound, with one important correction: never unconditionally join the I/O threads after timeout. Killing the direct child may leave stdout or stdin open in a descendant, so a reader or writer can remain blocked indefinitely. Use daemon threads and bounded cleanup on the timeout path; kill and reap the direct child, print the diagnostic, and return 124 independently of thread completion. Avoid closing a text stream from another thread while it is blocked on that stream, since its internal lock can also block cleanup.

Additional points:

- Start one monotonic deadline immediately after `Popen`, and apply its remaining time after thread startup. Handle a child that exits concurrently with timeout cleanup without masking the intended 124 result.
- Preserve streaming visibility: forwarding each line should flush stdout. Have only the reader thread mutate the session result, and consume it after successful reader completion.
- On normal completion, finish processing buffered output before deciding whether to write the session file. Do not allow an unhandled reader exception to produce apparent successful capture; retain the wrapper’s existing error behavior where possible.
- Keep unlimited execution behavior unchanged when the option is absent. Consider retaining the existing implementation for that case if it materially reduces regression risk.
- Confirm how existing session files behave. A timeout must not create or overwrite a success file; it should not delete an unrelated pre-existing file.

Strengthen the offline tests with:

1. `0`, negative values, `nan`, positive/negative infinity, malformed text, and overflow such as `1e309`; assert exit 2 and no launch marker.
2. A fractional positive timeout, proving elapsed enforcement and useful precision.
3. A fake child that never reads stdin plus a prompt larger than pipe capacity, exercising the writer-thread necessity.
4. Capture emitting a valid session-ID event, then hanging; assert forwarded output, 124, timeout diagnostic, and no session write.
5. Normal success and nonzero exit in both modes, plus resume with timeout, because resume bypasses capture.
6. PID evidence that the direct child is gone when the wrapper returns. Give every test subprocess an outer timeout to keep a regression from hanging the suite.

Inspect existing tests and error handling before deciding how thread exceptions should map to wrapper exit status.
