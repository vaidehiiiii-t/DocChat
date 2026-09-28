from app.extensions import db
from app.models.user import User

# --- M2-T1: Registration Tests ---


def test_register_success(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "Alice Tester", "email": "alice@example.com", "password": "password123"},
    )
    assert res.status_code == 201
    data = res.get_json()
    assert "user" in data
    assert "access_token" in data
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["name"] == "Alice Tester"
    assert "password_hash" not in data["user"]
    assert "password" not in data["user"]


def test_register_duplicate_email(client):
    payload = {"name": "Bob", "email": "bob@example.com", "password": "securepassword"}
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 409
    data = res2.get_json()
    assert data["error"]["code"] == "CONFLICT"


def test_register_invalid_email(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "Bad", "email": "not-an-email", "password": "password123"},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "email" in data["error"]["details"]


def test_register_short_password(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "Short", "email": "short@example.com", "password": "123"},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "password" in data["error"]["details"]


def test_register_password_hash_not_plaintext(app, client):
    raw_pass = "supersecretpass"
    res = client.post(
        "/api/auth/register",
        json={"name": "Hashed", "email": "hashed@example.com", "password": raw_pass},
    )
    assert res.status_code == 201

    with app.app_context():
        user = db.session.query(User).filter_by(email="hashed@example.com").first()
        assert user is not None
        assert user.password_hash != raw_pass
        assert not user.password_hash.startswith(raw_pass)
        assert len(user.password_hash) > 20


# --- M2-T2: Login Tests ---


def test_login_success(client):
    # Register first
    client.post(
        "/api/auth/register",
        json={"name": "Login User", "email": "login@example.com", "password": "correctpassword"},
    )

    # Login
    res = client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "correctpassword"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "access_token" in data
    assert data["user"]["email"] == "login@example.com"
    assert "password_hash" not in data["user"]


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={
            "name": "Wrong Pass",
            "email": "wrongpass@example.com",
            "password": "correctpassword",
        },
    )

    res = client.post(
        "/api/auth/login",
        json={"email": "wrongpass@example.com", "password": "incorrectpassword"},
    )
    assert res.status_code == 401
    data = res.get_json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert data["error"]["message"] == "Invalid email or password"


def test_login_unknown_email(client):
    res = client.post(
        "/api/auth/login",
        json={"email": "neverregistered@example.com", "password": "somepassword"},
    )
    assert res.status_code == 401
    data = res.get_json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    # Identical message for security
    assert data["error"]["message"] == "Invalid email or password"


# --- M2-T3: /auth/me & JWT Error Tests ---


def test_me_no_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    data = res.get_json()
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_me_garbage_token(client):
    res = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer this-is-total-garbage-token"},
    )
    assert res.status_code == 401
    data = res.get_json()
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_me_valid_token(client):
    reg_res = client.post(
        "/api/auth/register",
        json={"name": "Me User", "email": "me@example.com", "password": "password123"},
    )
    token = reg_res.get_json()["access_token"]

    res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "user" in data
    assert data["user"]["email"] == "me@example.com"
    assert data["user"]["name"] == "Me User"
    assert "password_hash" not in data["user"]


# --- M2-T4: Login Rate Limiting Tests ---


def test_login_rate_limiting(client):
    # Attempt 5 rapid logins with bad credentials (within the 5 per minute limit)
    for _ in range(5):
        client.post(
            "/api/auth/login",
            json={"email": "ratelimit@example.com", "password": "wrong"},
        )

    # 6th rapid attempt must trigger rate limit
    res6 = client.post(
        "/api/auth/login",
        json={"email": "ratelimit@example.com", "password": "wrong"},
    )
    assert res6.status_code == 429
    data = res6.get_json()
    assert data["error"]["code"] == "RATE_LIMITED"
