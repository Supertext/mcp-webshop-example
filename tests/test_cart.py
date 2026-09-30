from fastapi.testclient import TestClient

from app.main import app


def test_adding_a_product_puts_it_in_the_cart():
    client = TestClient(app)
    response = client.post("/cart/add", data={"sku": "arv-tx3"}, follow_redirects=True)
    assert response.status_code == 200
    assert 'data-sku="arv-tx3"' in response.text


def test_adding_the_same_product_twice_increments_quantity():
    client = TestClient(app)
    client.post("/cart/add", data={"sku": "arv-p240"})
    client.post("/cart/add", data={"sku": "arv-p240"})
    assert 'data-qty="2"' in client.get("/cart").text


def test_a_corrupt_cart_cookie_yields_an_empty_cart():
    client = TestClient(app)
    client.cookies.set("firn_cart", "not-json")
    response = client.get("/cart")
    assert response.status_code == 200
    assert "data-sku=" not in response.text


def test_a_deeply_nested_cart_cookie_does_not_crash():
    client = TestClient(app)
    client.cookies.set("firn_cart", "[" * 200000)
    response = client.get("/cart")
    assert response.status_code == 200
    assert "data-sku=" not in response.text


def test_a_boolean_cart_quantity_yields_an_empty_cart():
    client = TestClient(app)
    client.cookies.set("firn_cart", '{"arv-tx3": true}')
    response = client.get("/cart")
    assert response.status_code == 200
    assert "data-sku=" not in response.text


def test_adding_an_unknown_sku_is_rejected():
    client = TestClient(app)
    assert client.post("/cart/add", data={"sku": "nope"}).status_code == 404


def test_removing_a_product_empties_the_cart():
    client = TestClient(app)
    client.post("/cart/add", data={"sku": "arv-s1"})
    assert 'data-sku="arv-s1"' in client.get("/cart").text
    client.post("/cart/remove", data={"sku": "arv-s1"})
    assert 'data-sku="arv-s1"' not in client.get("/cart").text


def test_checkout_creates_an_order_and_clears_the_cart():
    client = TestClient(app)
    client.post("/cart/add", data={"sku": "clb-k2"})
    response = client.post(
        "/checkout",
        data={"name": "A Tester", "email": "a@example.com", "address": "Bahnhofstrasse 1",
              "postcode": "8001", "city": "Zürich", "shipping": "standard"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert 'data-sku="clb-k2"' in response.text
    assert 'data-sku="clb-k2"' not in client.get("/cart").text


def test_checkout_with_an_empty_cart_redirects_to_the_cart():
    client = TestClient(app)
    response = client.post(
        "/checkout",
        data={"name": "A", "email": "a@example.com", "address": "x",
              "postcode": "8001", "city": "Zürich", "shipping": "standard"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("/cart")


def test_unknown_order_is_404():
    client = TestClient(app)
    assert client.get("/order/does-not-exist").status_code == 404
