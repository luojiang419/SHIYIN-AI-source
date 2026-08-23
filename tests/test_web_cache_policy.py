from fastapi.testclient import TestClient

import main


def authenticated_client():
    client = TestClient(main.app, client=("127.0.0.1", 50112))
    identity = main.AccountIdentity("admin", main.ADMIN_ACCOUNT, "admin", "")
    client.cookies.set(main.ACCOUNT_SESSION_COOKIE, main.ACCOUNT_STORE.create_session(identity))
    return client


def test_html_and_service_worker_do_not_reuse_stale_page_shells():
    with authenticated_client() as client:
        page = client.get("/")
        canvas = client.get("/static/canvas.html?id=cache-test")
        worker = client.get("/media-cache-sw.js")

    assert page.status_code == 200
    assert page.headers["cache-control"] == main.HTML_CACHE_CONTROL
    assert page.headers["pragma"] == "no-cache"
    assert canvas.status_code == 200
    assert canvas.headers["cache-control"] == main.HTML_CACHE_CONTROL
    assert canvas.headers["pragma"] == "no-cache"
    assert worker.headers["cache-control"] == main.HTML_CACHE_CONTROL


def test_static_resources_are_immutable_only_when_their_url_has_a_version():
    with authenticated_client() as client:
        versioned = client.get("/static/js/theme.js?v=1.0.272.test")
        direct = client.get("/static/js/theme.js")

    assert versioned.status_code == 200
    assert versioned.headers["cache-control"] == main.VERSIONED_STATIC_CACHE_CONTROL
    assert direct.status_code == 200
    assert direct.headers["cache-control"] == main.UNVERSIONED_STATIC_CACHE_CONTROL
