"""Command-line interface for the STE checker."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

import click

from ste100 import __version__
from ste100.core.analyzer import analyze, get_spacy_model_name, set_spacy_model
from ste100.core.explain import explain_rule
from ste100.core.git_files import NotAGitRepositoryError, run_check_changed
from ste100.core.schema import TextType
from ste100.core.serialize import format_output
from ste100.core.spacy_ready import check_spacy_model, download_spacy_model
from ste100.dictionary.engine import get_default_engine
from ste100.lsp.server import run_server as run_lsp_server
from ste100.mcp.server import run_server as run_mcp_server


def _read_input(file: Path | None, stdin: TextIO) -> str:
    if file is None:
        return stdin.read()
    return file.read_text(encoding="utf-8")


def _emit(payload: dict[str, Any] | str, quiet: bool) -> None:
    if quiet:
        return
    if isinstance(payload, str):
        click.echo(payload)
    else:
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@click.group()
@click.version_option(package_name="asd-ste100-checker")
def main() -> None:
    """Unofficial ASD-STE100 Simplified Technical English checker."""


@main.command("check")
@click.argument("file", type=click.Path(path_type=Path, exists=True, dir_okay=False), required=False)
@click.option(
    "--text-type",
    "text_type",
    type=click.Choice([t.value for t in TextType], case_sensitive=False),
    default=TextType.AUTO.value,
    show_default=True,
    help="Text classification driving sentence limits.",
)
@click.option(
    "--output",
    "output",
    type=click.Choice(["json", "sarif"], case_sensitive=False),
    default="json",
    show_default=True,
)
@click.option(
    "--glossary",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Project glossary YAML path.",
)
@click.option(
    "--spacy-model",
    "spacy_model",
    default=None,
    help=(
        "spaCy model name (default: en_core_web_sm or STE100_SPACY_MODEL env). "
        "MCP server uses the env var only."
    ),
)
@click.option("--quiet", is_flag=True, help="Suppress stdout; still set exit code.")
def check_cmd(
    file: Path | None,
    text_type: str,
    output: str,
    glossary: Path | None,
    spacy_model: str | None,
    quiet: bool,
) -> None:
    """Check FILE (or stdin) for STE Tier-1/Tier-2/Tier-3 issues."""
    if spacy_model:
        set_spacy_model(spacy_model)

    try:
        text = _read_input(file, sys.stdin)
    except OSError as exc:
        click.echo(f"error: failed to read input: {exc}", err=True)
        raise SystemExit(2) from exc

    try:
        result = analyze(
            text,
            text_type=text_type,
            glossary_path=str(glossary) if glossary else None,
        )
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        click.echo(f"error: analysis failed: {exc}", err=True)
        raise SystemExit(2) from exc

    if output.lower() == "sarif":
        payload: dict[str, Any] = format_output(result, "sarif")
    else:
        payload = format_output(result, "json")

    _emit(payload, quiet=quiet)
    raise SystemExit(0 if result.compliant else 1)


@main.command("lookup")
@click.argument("word")
def lookup_cmd(word: str) -> None:
    """Look up WORD in the STE dictionary."""
    engine = get_default_engine()
    payload = engine.lookup_payload(word)
    click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    raise SystemExit(0)


@main.command("explain")
@click.argument("rule_id")
def explain_cmd(rule_id: str) -> None:
    """Explain a checker rule_id (title, severity, STE ref, fix hints, PDF rule)."""
    payload = explain_rule(rule_id)
    click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    raise SystemExit(0 if payload.get("found") else 1)


@main.command("check-changed")
@click.option(
    "--glob",
    "globs",
    multiple=True,
    help=(
        "Filename glob to include (repeatable). "
        "Default: *.md, *.txt, *.rst, *.adoc."
    ),
)
@click.option(
    "--text-type",
    "text_type",
    type=click.Choice([t.value for t in TextType], case_sensitive=False),
    default=TextType.AUTO.value,
    show_default=True,
    help="Text classification driving sentence limits.",
)
@click.option(
    "--output",
    "output",
    type=click.Choice(["json", "sarif"], case_sensitive=False),
    default="json",
    show_default=True,
)
@click.option(
    "--glossary",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Project glossary YAML path.",
)
@click.option(
    "--base",
    "base",
    default=None,
    help=(
        "Compare against git merge-base of HEAD and this ref/branch "
        "(default: working tree vs HEAD)."
    ),
)
@click.option(
    "--spacy-model",
    "spacy_model",
    default=None,
    help=(
        "spaCy model name (default: en_core_web_sm or STE100_SPACY_MODEL env). "
        "MCP server uses the env var only."
    ),
)
@click.option("--quiet", is_flag=True, help="Suppress stdout; still set exit code.")
def check_changed_cmd(
    globs: tuple[str, ...],
    text_type: str,
    output: str,
    glossary: Path | None,
    base: str | None,
    spacy_model: str | None,
    quiet: bool,
) -> None:
    """Check working-tree doc changes vs HEAD (or --base merge-base)."""
    if spacy_model:
        set_spacy_model(spacy_model)

    glob_list = list(globs) if globs else None
    glossary_path = str(glossary) if glossary else None
    fmt = output.lower()
    try:
        payload = run_check_changed(
            output=fmt,
            globs=glob_list,
            text_type=text_type,
            glossary=glossary_path,
            base=base,
        )
        compliant = (
            bool(payload["runs"][0]["properties"]["compliant"])
            if fmt == "sarif"
            else bool(payload["compliant"])
        )
    except NotAGitRepositoryError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(2) from exc
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        click.echo(f"error: check-changed failed: {exc}", err=True)
        raise SystemExit(2) from exc

    _emit(payload, quiet=quiet)
    raise SystemExit(0 if compliant else 1)


@main.command("serve")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "http", "sse", "streamable-http"], case_sensitive=False),
    default="stdio",
    show_default=True,
    help="MCP transport. HTTP/SSE require STE100_MCP_TOKEN bearer auth.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Bind host for HTTP/SSE (localhost recommended for demos).",
)
@click.option(
    "--port",
    default=8765,
    show_default=True,
    type=int,
    help="Bind port for HTTP/SSE.",
)
@click.option(
    "--path",
    "mcp_path",
    default="/mcp",
    show_default=True,
    help="URL path for the streamable HTTP MCP endpoint.",
)
def serve_cmd(transport: str, host: str, port: int, mcp_path: str) -> None:
    """Start the MCP server (stdio or HTTP/SSE with bearer token)."""
    run_mcp_server(
        transport=transport,
        host=host,
        port=port,
        path=mcp_path,
    )


@main.command("lsp")
def lsp_cmd() -> None:
    """Start the thin diagnostics LSP over stdio (md/txt/rst/adoc)."""
    run_lsp_server()


def _print_doctor_report(*, model_ok: bool, model: str, error: str | None) -> None:
    click.echo(f"python: {sys.version.split()[0]}")
    click.echo(f"package: asd-ste100-checker {__version__}")
    click.echo(f"spacy_model: {model}")
    if model_ok:
        click.echo("spacy_model_load: ok")
    else:
        click.echo("spacy_model_load: FAIL")
        if error:
            click.echo(f"  detail: {error}")
        click.echo(
            "fix: python -m ste100 setup   # or: ste100 doctor --fix"
        )


@main.command("doctor")
@click.option(
    "--fix",
    "do_fix",
    is_flag=True,
    help="If the spaCy model is missing, download it (may use the network).",
)
def doctor_cmd(do_fix: bool) -> None:
    """Check environment readiness (no network unless --fix)."""
    model = get_spacy_model_name()
    status = check_spacy_model(model)
    if not status.ok and do_fix:
        click.echo(f"downloading spaCy model {model!r} …", err=True)
        status = download_spacy_model(model)
    _print_doctor_report(model_ok=status.ok, model=status.model, error=status.error)
    raise SystemExit(0 if status.ok else 1)


@main.command("setup")
def setup_cmd() -> None:
    """Install the configured spaCy model if missing (may use the network)."""
    model = get_spacy_model_name()
    status = check_spacy_model(model)
    if status.ok:
        click.echo(f"spaCy model {model!r} already available.")
        raise SystemExit(0)
    click.echo(f"downloading spaCy model {model!r} …", err=True)
    status = download_spacy_model(model)
    if status.ok:
        click.echo(f"spaCy model {model!r} installed.")
        raise SystemExit(0)
    click.echo(
        f"error: failed to install spaCy model {model!r}: {status.error}",
        err=True,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    main()
