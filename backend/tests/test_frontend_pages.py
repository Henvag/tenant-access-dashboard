"""The backend serves each prerendered public page at its own address, and a real 404
for unknown paths, while API and OIDC routes keep answering as before."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_frontend


def _static(tmp_path: Path, *, prerendered: bool = True) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app-123.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("home-en")
    (tmp_path / "robots.txt").write_text("User-agent: *")
    if prerendered:
        for name, body in {
            "no/index.html": "home-no",
            "privacy/index.html": "privacy-en",
            "personvern/index.html": "privacy-no",
            "dpa/index.html": "dpa-en",
            "databehandleravtale/index.html": "dpa-no",
            "no/guider/index.html": "guides",
            "no/guider/stenge-tilgang-ansatt-slutter/index.html": "guide-offboarding",
            "404.html": "not-found",
        }.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(body)
    return tmp_path


def _client(static_dir: Path) -> TestClient:
    app = FastAPI()

    @app.get("/.well-known/openid-configuration")
    async def discovery():
        return {"issuer": "https://tenantaccess.me"}

    mount_frontend(app, static_dir)
    return TestClient(app)


def test_each_page_has_its_own_address(tmp_path: Path) -> None:
    client = _client(_static(tmp_path))
    for path, body in {
        "/": "home-en",
        "/?_=123": "home-en",
        "/no": "home-no",
        "/no/": "home-no",
        "/privacy": "privacy-en",
        "/personvern": "privacy-no",
        "/dpa": "dpa-en",
        "/databehandleravtale": "dpa-no",
        "/no/guider": "guides",
        "/no/guider/": "guides",
        "/no/guider/stenge-tilgang-ansatt-slutter": "guide-offboarding",
    }.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.text == body, path
        assert response.headers["cache-control"] == "no-cache, must-revalidate"


def test_files_and_api_routes_still_answer(tmp_path: Path) -> None:
    client = _client(_static(tmp_path))
    assert client.get("/robots.txt").text == "User-agent: *"
    assert client.get("/assets/app-123.js").status_code == 200
    assert client.get("/.well-known/openid-configuration").json()["issuer"] == "https://tenantaccess.me"


def test_unknown_paths_are_a_real_404(tmp_path: Path) -> None:
    client = _client(_static(tmp_path))
    for path in ["/nope", "/no/such/page", "/no/guider/finnes-ikke", "/../etc/passwd", "/assets/missing.js"]:
        response = client.get(path)
        assert response.status_code == 404, path
    assert client.get("/nope").text == "not-found"


def test_build_without_prerender_still_draws_every_page(tmp_path: Path) -> None:
    client = _client(_static(tmp_path, prerendered=False))
    assert client.get("/no").text == "home-en"
    assert client.get("/nope").status_code == 404
    assert client.get("/nope").text == "home-en"
