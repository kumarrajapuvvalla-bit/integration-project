# Jenkins Build Log Parser

A Rust CLI tool that parses Jenkins console output and produces a structured
failure summary. Designed as a post-build step to surface failures clearly
in CI/CD pipelines.

## Why Rust?

Rust produces a single, statically linked binary with no runtime dependencies.
This makes it ideal for DevOps tooling that runs inside containers, Kubernetes
Jobs, or minimal CI environments where you can't guarantee Python or Go is
available. The binary is typically under 5MB.

## Build

```bash
cd tools/log-parser
cargo build --release
# Binary at: target/release/log-parser
```

## Usage

```bash
# Parse a local log file
./log-parser --input build.log

# Output structured JSON (for downstream tooling or dashboards)
./log-parser --input build.log --format json

# Pipe directly from Jenkins API
curl -s "$JENKINS_URL/job/my-pipeline/lastBuild/consoleText" \
  | ./log-parser --stdin

# Use as a CI gate — exits 1 if failures detected
./log-parser --input build.log --fail-on-error
```

## What It Extracts

| Category | Examples |
|----------|----------|
| **Errors** | `ERROR`, `FAILED`, `BUILD FAILED`, `Exception in thread`, Java exceptions |
| **Warnings** | `WARNING`, `WARN`, `DEPRECATED` |
| **Test results** | Maven Surefire `Tests run: N, Failures: N, Errors: N, Skipped: N` |
| **Build duration** | `Finished: 3.5 minutes`, `Total time: 120 seconds` |
| **Pipeline stages** | `[Pipeline] (Stage Name)` |

## Output Example

```
=== Jenkins Build Log Analysis ===
Errors: 2  |  Warnings: 1  |  Stages: 3
Build duration: 120.0s
Tests: 10 total | 6 passed | 3 failed | 1 errors | 0 skipped

Pipeline stages:
  → Checkout
  → Build
  → Test

Failures (2):
  L6 [Build]: [ERROR] Failed to execute goal: compilation failure
  L7 [Build]: [ERROR] src/main/java/App.java:42: error: cannot find symbol
```

## Run Tests

```bash
cargo test --all -- --nocapture
```
