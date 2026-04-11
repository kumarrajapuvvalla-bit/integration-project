use log_parser::{
    parser::parse_log,
    report::{OutputFormat, Report},
};

// ── Fixtures ──────────────────────────────────────────────────────────────────

const SUCCESSFUL_BUILD: &str = r#"
[Pipeline] stage (Checkout)
[Pipeline] stage (Build)
[Pipeline] stage (Test)
Tests run: 42, Failures: 0, Errors: 0, Skipped: 2
Finished: 3.5 min
BUILD SUCCESS
"#;

const FAILED_BUILD: &str = r#"
[Pipeline] stage (Checkout)
[Pipeline] stage (Build)
ERROR: compilation failed
[Pipeline] stage (Test)
Tests run: 10, Failures: 2, Errors: 1, Skipped: 0
Build failed
Finished: 45 sec
"#;

const MULTI_STAGE_BUILD: &str = r#"
[Pipeline] stage (Lint)
WARNING: deprecated API usage
[Pipeline] stage (Build)
[Pipeline] stage (Test)
Tests run: 100, Failures: 0, Errors: 0, Skipped: 5
[Pipeline] stage (Deploy)
Finished: 2.0 min
"#;

// ── Tests ──────────────────────────────────────────────────────────────────

#[test]
fn successful_build_has_no_errors() {
    let parsed = parse_log(SUCCESSFUL_BUILD);
    assert_eq!(
        parsed.error_count(),
        0,
        "successful build should have no errors"
    );
}

#[test]
fn successful_build_has_test_summary() {
    let parsed = parse_log(SUCCESSFUL_BUILD);
    let summary = parsed.test_summary.expect("test summary should be present");
    assert_eq!(summary.total, 42);
    assert_eq!(summary.failures, 0);
    assert_eq!(summary.skipped, 2);
    assert_eq!(summary.passed(), 40);
}

#[test]
fn successful_build_extracts_duration() {
    let parsed = parse_log(SUCCESSFUL_BUILD);
    let duration = parsed
        .build_duration_seconds
        .expect("duration should be present");
    assert!(
        (duration - 210.0).abs() < 1.0,
        "expected ~210s (3.5 min), got {}",
        duration
    );
}

#[test]
fn failed_build_detects_errors() {
    let parsed = parse_log(FAILED_BUILD);
    assert!(
        parsed.error_count() >= 1,
        "failed build should have at least one error"
    );
}

#[test]
fn failed_build_has_test_summary() {
    let parsed = parse_log(FAILED_BUILD);
    let summary = parsed.test_summary.expect("test summary should be present");
    assert_eq!(summary.failures, 2);
    assert_eq!(summary.errors, 1);
}

#[test]
fn failed_build_extracts_duration_in_seconds() {
    let parsed = parse_log(FAILED_BUILD);
    let duration = parsed
        .build_duration_seconds
        .expect("duration should be present");
    assert!(
        (duration - 45.0).abs() < 1.0,
        "expected 45s, got {}",
        duration
    );
}

#[test]
fn multi_stage_build_extracts_stages() {
    let parsed = parse_log(MULTI_STAGE_BUILD);
    assert!(parsed.stages.contains(&"Lint".to_string()));
    assert!(parsed.stages.contains(&"Build".to_string()));
    assert!(parsed.stages.contains(&"Test".to_string()));
    assert!(parsed.stages.contains(&"Deploy".to_string()));
}

#[test]
fn multi_stage_build_has_warnings() {
    let parsed = parse_log(MULTI_STAGE_BUILD);
    assert!(parsed.warning_count() >= 1, "expected at least one warning");
}

#[test]
fn report_text_output_does_not_panic() {
    let parsed = parse_log(FAILED_BUILD);
    let report = Report::new(parsed);
    report.print(OutputFormat::Text);
}

#[test]
fn report_json_output_does_not_panic() {
    let parsed = parse_log(FAILED_BUILD);
    let report = Report::new(parsed);
    report.print(OutputFormat::Json);
}
