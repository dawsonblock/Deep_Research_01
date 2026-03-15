"""Canonical runtime package — the verified execution boundary.

Public API:
    CanonicalExecutor  — top-level entrypoint for node execution
    RuntimeContext     — context object for a single execution
    ExecutionResult    — structured execution output
    VerifiedExecutor   — verified operator execution pipeline
    RunRegistry        — run provenance tracking
    ArtifactValidator  — artifact validation
    PostconditionVerifier — postcondition verification
"""