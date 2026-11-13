"""The command line and the library: the same tools without MCP."""

from __future__ import annotations

import json

import pytest
from conftest import DOCS, build_fixture_index, fake_models_on_disk, install_index, make_entry
from test_api_table import GLOBAL, GLOBAL_PATH, PAGE, PATH

from snow_docs_mcp import api, config, setup
from snow_docs_mcp.server import main


@pytest.fixture
def installed(monkeypatch, tmp_path, fake_models):
    monkeypatch.setattr(setup, "start", lambda: None)
    monkeypatch.setattr(setup, "request", lambda release: None)
    monkeypatch.setattr(config, "BUILTIN_ENTRIES", {"australia": make_entry()})
    monkeypatch.delenv("SNOW_DOCS_INDEX_URL", raising=False)
    docs = {
        **DOCS,
        PATH: PAGE,
        GLOBAL_PATH: GLOBAL,
        "markdown/itsm/t.md": "The Incident [incident] table.",
    }
    install_index(
        build_fixture_index(tmp_path / "au.db", docs=docs), config.BUILTIN_ENTRIES["australia"]
    )
    fake_models_on_disk()
    fake_models.query_vectors["incident lifecycle"] = {0: 1.0}
    return fake_models


def run(capsys, *argv: str) -> tuple[int, dict]:
    with pytest.raises(SystemExit) as done:
        main(list(argv))
    out = capsys.readouterr().out
    return done.value.code, (json.loads(out) if out.strip() else {})


def test_search_then_read(installed, capsys):
    code, found = run(capsys, "search", "incident lifecycle", "--limit", "2")
    assert code == 0 and found["ok"] and found["release"] == "australia"
    hit = found["hits"][0]["id"]
    code, page = run(capsys, "read", hit, "--max-chars", "500")
    assert code == 0 and page["ok"] and page["id"] == hit


def test_api_browse_status_and_compare_without_brazil(installed, capsys):
    code, cls = run(capsys, "api", "GlideRecord")
    assert code == 0 and cls["kind"] == "class"
    code, tree = run(capsys, "browse", "itsm")
    assert code == 0 and tree["path"] == "itsm" and tree["pages"]
    code, status = run(capsys, "status")
    assert code == 0 and status["default_release"] == "australia"
    code, cmp_ = run(capsys, "compare", "incident")
    assert code == 1 and not cmp_["ok"] and "both" in cmp_["message"]


def test_check_script_reads_a_file_or_standard_input(installed, capsys, tmp_path, monkeypatch):
    script = tmp_path / "rule.js"
    script.write_text("var gr = new GlideRecord('incident');\ngr.qurey();\n", encoding="utf-8")
    code, found = run(capsys, "check-script", str(script))
    assert code == 0 and [f["name"] for f in found["findings"]] == ["GlideRecord.qurey"]
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("gs.nothing();"))
    code, found = run(capsys, "check-script", "-")
    assert code == 0 and found["ok"]


def test_bad_usage_exits_2_and_a_failed_call_exits_1(installed, capsys, tmp_path):
    assert run(capsys, "search")[0] == 2
    assert run(capsys, "check-script", str(tmp_path / "missing.js"))[0] == 2
    code, out = run(capsys, "search", "x", "--release", "zurich")
    assert code == 1 and "Unknown release" in out["message"]


def test_output_is_one_json_document_even_when_a_tool_prints(installed, capsys, monkeypatch):
    from snow_docs_mcp import server

    real = server.snow_docs_status

    def noisy():
        print("stray output")
        return real()

    monkeypatch.setattr(server, "snow_docs_status", noisy)
    code, status = run(capsys, "status")
    assert code == 0 and status["default_release"] == "australia"


def test_the_library_returns_the_same_results_as_the_tools(installed):
    found = api.search("incident lifecycle", limit=2)
    assert found.ok and found.hits[0].id.startswith("australia:")
    assert api.read(found.hits[0].id).ok
    assert api.lookup("GlideRecord.query").kind == "method"
    assert (
        api.check_script("gs.nope();").ok and api.browse().folders and api.status().default_release
    )
    assert not api.compare(query="incident").ok


def test_readme_shows_the_commands_and_the_library():
    from pathlib import Path

    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    assert "## Command line and library" in readme and "snow-docs-mcp check-script" in readme
    assert "from snow_docs_mcp import api" in readme
