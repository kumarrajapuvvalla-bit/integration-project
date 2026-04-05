use clap::Parser as ClapParser;
use log_parser::{
    parser::parse_log,
    report::{OutputFormat, Report},
};
use std::{
    fs,
    io::{self, Read},
    process,
};

/// Jenkins Build Log Parser
///
/// Parses Jenkins console output and produces a structured failure
/// summary with exit codes suitable for CI/CD gates.
#[derive(ClapParser, Debug)]
#[command(author, version, about, long_about = None)]
struct Cli {
    /// Path to the Jenkins log file to parse
    #[arg(short, long, conflicts_with = "stdin")]
    input: Option<String>,

    /// Read log from stdin instead of a file
    #[arg(long)]
    stdin: bool,

    /// Output format: text (default) or json
    #[arg(short, long, default_value = "text")]
    format: String,

    /// Exit with code 1 if any build failures are detected
    #[arg(long)]
    fail_on_error: bool,

    /// Suppress all output except errors (useful in scripts)
    #[arg(short, long)]
    quiet: bool,
}

fn main() {
    let cli = Cli::parse();

    let raw_log = if cli.stdin {
        let mut buf = String::new();
        io::stdin()
            .read_to_string(&mut buf)
            .expect("failed to read from stdin");
        buf
    } else if let Some(path) = &cli.input {
        fs::read_to_string(path).unwrap_or_else(|e| {
            eprintln!("error: could not read '{}': {}", path, e);
            process::exit(2);
        })
    } else {
        eprintln!("error: provide --input <file> or --stdin");
        process::exit(2);
    };

    let parsed = parse_log(&raw_log);

    let format = match cli.format.to_lowercase().as_str() {
        "json" => OutputFormat::Json,
        _ => OutputFormat::Text,
    };

    let report = Report::new(parsed);

    if !cli.quiet {
        report.print(format);
    }

    if cli.fail_on_error && report.has_failures() {
        process::exit(1);
    }
}
