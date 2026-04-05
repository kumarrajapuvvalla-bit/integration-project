//! log-parser — Jenkins Build Log Parser
//!
//! Parses Jenkins console output and produces a structured failure summary.
//! Designed to run as a post-build step or CI validation tool.
//!
//! # Usage
//!
//! ```bash
//! # Parse a local log file
//! log-parser --input build.log
//!
//! # Parse and output JSON (useful for downstream tooling)
//! log-parser --input build.log --format json
//!
//! # Read from stdin (piped from Jenkins API)
//! curl -s "$JENKINS_URL/job/my-job/lastBuild/consoleText" | log-parser --stdin
//!
//! # Exit 1 if any failures found (CI gate)
//! log-parser --input build.log --fail-on-error
//! ```

pub mod parser;
pub mod report;

pub use parser::{LogEntry, ParsedLog, Severity};
pub use report::{OutputFormat, Report};
