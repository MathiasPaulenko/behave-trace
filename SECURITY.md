# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in behave-trace, please report it
responsibly.

- Email: **mathias@paulenko.dev**
- Do not open a public GitHub issue for security vulnerabilities.

## Response time

We aim to acknowledge reported vulnerabilities within **48 hours** and to
provide a fix or mitigation according to severity.

## Scope

behave-trace is a trace viewer for Behave BDD. It captures execution data
during test runs and serves a local web viewer. Vulnerabilities related to
the local HTTP server (path traversal, arbitrary file access), trace JSON
deserialization, or the formatter plugin registration mechanism are in scope.
