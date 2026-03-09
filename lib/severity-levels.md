# Severity Levels

| Level    | Description                                              | Fix Timeline    |
|----------|----------------------------------------------------------|-----------------|
| Critical | Security vulnerability exploitable now, data loss risk   | Immediate       |
| High     | Security issue, significant bug, or broken functionality | Before deploy   |
| Medium   | Performance issue, minor bug, or code quality concern    | Next sprint     |
| Low      | Style issue, minor optimization, or enhancement          | When convenient |
| Info     | Observation, documentation, or informational note        | Optional        |

## Category Definitions

| Category         | What It Covers                                              |
|------------------|-------------------------------------------------------------|
| security         | Authentication, authorization, injection, XSS, CSRF, etc.  |
| input-validation | Missing or weak input validation on user-facing endpoints   |
| performance      | Slow queries, unbounded loops, memory issues, missing cache |
| code-quality     | Dead code, error handling, race conditions, resource leaks  |
| test-failure     | Failing tests from the test suite                           |
| lint-error       | Linter violations                                           |

## Effort Estimates

| Effort | Lines Changed | Typical Time |
|--------|---------------|--------------|
| Tiny   | < 5           | Minutes      |
| Small  | < 20          | Under 1 hour |
| Medium | < 100         | 1-4 hours    |
| Large  | > 100         | Half day+    |
