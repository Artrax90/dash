from fastapi.testclient import TestClient
from backend.app.main import app

def test_favicon_endpoints():
    client = TestClient(app)
    res_ico = client.get("/favicon.ico")
    assert res_ico.status_code == 200
    assert len(res_ico.content) > 0
    res_png = client.get("/favicon.png")
    assert res_png.status_code == 200
    assert res_png.headers.get("content-type") == "image/png"
    res_apple = client.get("/apple-touch-icon.png")
    assert res_apple.status_code == 200
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert b"favicon.ico" in res_root.content
    assert b"favicon-32x32.png" in res_root.content
