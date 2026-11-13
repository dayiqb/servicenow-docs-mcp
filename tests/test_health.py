"""The index health check: counts of what the tools read out of an index, against floors."""

from __future__ import annotations

import pytest
from conftest import DOCS, build_fixture_index
from test_api_table import GLOBAL, GLOBAL_PATH, PAGE, PATH, REST, REST_PATH
from test_compare_tool import AU_DOCS, BR_CHUNKS, BR_DOCS

from snow_docs_mcp import health
from snow_docs_mcp.server import main


@pytest.fixture
def brazil_db(tmp_path):
    docs = {**BR_DOCS, PATH: PAGE, GLOBAL_PATH: GLOBAL, REST_PATH: REST}
    return build_fixture_index(tmp_path / "br.db", docs=docs, chunks=BR_CHUNKS)


@pytest.fixture
def australia_db(tmp_path):
    docs = {**AU_DOCS, PATH: PAGE, GLOBAL_PATH: GLOBAL, REST_PATH: REST}
    return build_fixture_index(tmp_path / "au.db", docs=docs)


SMALL = {
    "api_methods": 6,
    "api_classes": 1,
    "api_methods_with_return_type": 0.5,
    "rest_endpoints": 2,
    "rest_apis": 1,
    "rest_endpoints_with_parameters": 1.0,
    "rest_endpoints_with_default_url": 0.5,
    "table_names": 0,
    "release_notes_applications": 5,
    "release_notes_families": 2,
}


def test_counts_what_the_tools_can_read(brazil_db):
    c = health.counts(brazil_db, "brazil")
    assert c["api_methods"] == 6 and c["api_classes"] == 1
    assert c["rest_endpoints"] == 2 and c["rest_apis"] == 1
    assert c["rest_endpoints_with_default_url"] == 1.0
    assert c["release_notes_applications"] >= 10 and c["release_notes_families"] >= 2


def test_an_index_below_a_floor_is_reported_by_name(brazil_db):
    assert health.problems(health.counts(brazil_db, "brazil"), SMALL) == []
    found = health.problems(health.counts(brazil_db, "brazil"), {**SMALL, "api_methods": 4000})
    assert len(found) == 1 and "api_methods" in found[0] and "4000" in found[0] and "6" in found[0]


def test_release_notes_are_only_expected_in_brazil(australia_db):
    c = health.counts(australia_db, "australia")
    assert "release_notes_applications" not in c
    assert health.problems(c, {"api_methods": 6, "release_notes_applications": 5}) == []


def test_compare_noise_is_the_share_of_shared_pages_reported_as_changed(australia_db, brazil_db):
    share, compared = health.compare_noise(australia_db, brazil_db)
    assert (share, compared) == (0.286, 7)  # incident.md and big.md really changed


def test_cli_prints_the_counts_and_fails_on_a_problem(brazil_db, australia_db, capsys, monkeypatch):
    monkeypatch.setattr(health, "FLOORS", SMALL)
    monkeypatch.setattr(health, "MAX_COMPARE_NOISE", 0.9)
    with pytest.raises(SystemExit) as ok:
        main(["check-index", "--brazil", str(brazil_db), "--australia", str(australia_db)])
    out = capsys.readouterr().out
    assert ok.value.code == 0 and "api_methods" in out and "index health: OK" in out
    monkeypatch.setattr(health, "FLOORS", {**SMALL, "rest_endpoints": 600})
    with pytest.raises(SystemExit) as bad:
        main(["check-index", "--brazil", str(brazil_db)])
    out = capsys.readouterr().out
    assert bad.value.code == 1 and "rest_endpoints" in out and "index health: FAILED" in out


def test_cli_needs_an_index_and_an_existing_file(tmp_path, capsys):
    with pytest.raises(SystemExit) as none:
        main(["check-index"])
    with pytest.raises(SystemExit) as missing:
        main(["check-index", "--brazil", str(tmp_path / "nope.db")])
    assert none.value.code == 2 and missing.value.code == 2


def test_the_floors_cover_every_count(brazil_db):
    assert set(health.FLOORS) == set(health.counts(brazil_db, "brazil"))
    assert DOCS  # the standard fixture is what australia_db extends
