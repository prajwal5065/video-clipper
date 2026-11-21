"""The Python server also serves the built React app."""
import pytest
from fastapi.testclient import TestClient

from server.main import create_app


@pytest.fixture
def web(tmp_path):
    site = tmp_path / "webui"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text("<html>APP</html>")
    (site / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("secret")
    return TestClient(create_app(tmp_path / "data", webui_dir=site))


def test_index_assets_and_client_side_routes(web):
    assert "APP" in web.get("/").text
    assert web.get("/assets/app.js").text == "console.log(1)"
    assert "APP" in web.get("/jobs/abc123").text and "APP" in web.get("/library").text  # page refresh keeps working


def test_api_is_not_shadowed_and_unknown_api_paths_404(web):
    assert web.get("/api/health").json() == {"ok": True}
    assert web.get("/api/nope").status_code == 404


def test_cannot_read_files_outside_the_site(web):
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        assert "secret" != web.get(path).text


def test_without_a_build_the_api_still_works(tmp_path):
    c = TestClient(create_app(tmp_path / "data", webui_dir=tmp_path / "missing"))
    assert c.get("/api/health").status_code == 200 and c.get("/").status_code == 404
