import argparse
import io
import sys
import time
import uuid
import requests


def run_smoke_test(base_url: str) -> bool:
    print(f"=== Starting DocChat Smoke Test against {base_url} ===")
    session = requests.Session()

    # 1. Health check
    print("[1/7] Testing health endpoint...")
    try:
        health_res = session.get(f"{base_url}/api/health", timeout=5)
        if health_res.status_code != 200:
            print(f"FAIL: Health check returned status {health_res.status_code}: {health_res.text}")
            return False
        health_data = health_res.json()
        print(f"  OK: Health status={health_data.get('status')}, db={health_data.get('db')}")
    except Exception as e:
        print(f"FAIL: Cannot connect to {base_url}: {e}")
        return False

    # 2. Register
    uid = uuid.uuid4().hex[:8]
    email = f"smoketest_{uid}@example.com"
    password = "SmokeTestPassword123!"
    print(f"[2/7] Registering new user ({email})...")

    reg_res = session.post(
        f"{base_url}/api/auth/register",
        json={"name": "Smoke Tester", "email": email, "password": password},
        timeout=10,
    )
    if reg_res.status_code != 201:
        print(f"FAIL: Registration failed ({reg_res.status_code}): {reg_res.text}")
        return False
    print("  OK: Registered successfully.")

    # 3. Login
    print("[3/7] Logging in...")
    login_res = session.post(
        f"{base_url}/api/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    if login_res.status_code != 200:
        print(f"FAIL: Login failed ({login_res.status_code}): {login_res.text}")
        return False
    token = login_res.json().get("access_token")
    if not token:
        print("FAIL: No access token in login response.")
        return False
    headers = {"Authorization": f"Bearer {token}"}
    print("  OK: Logged in, JWT token obtained.")

    # 4. Upload PDF fixture
    print("[4/7] Uploading PDF document fixture...")
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 120 >> stream\n"
        b"BT /F1 12 Tf 72 712 Td (DocChat Smoke Test document. Artificial Intelligence and retrieval augmented generation.) Tj ET\n"
        b"endstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000216 00000 n\n"
        b"trailer << /Size 5 /Root 1 0 R >>\nstartxref\n386\n%%EOF"
    )
    files = {"file": ("smoke_test.pdf", io.BytesIO(pdf_content), "application/pdf")}
    upload_res = session.post(f"{base_url}/api/documents", headers=headers, files=files, timeout=15)
    if upload_res.status_code != 202:
        print(f"FAIL: Upload failed ({upload_res.status_code}): {upload_res.text}")
        return False
    doc_id = upload_res.json().get("id")
    print(f"  OK: Upload accepted (Document ID: {doc_id}). Polling for 'ready' status...")

    # Wait for processing
    status = "pending"
    for attempt in range(30):
        time.sleep(1)
        check_res = session.get(f"{base_url}/api/documents/{doc_id}", headers=headers, timeout=5)
        if check_res.status_code == 200:
            status = check_res.json().get("status")
            if status in ("ready", "failed"):
                break
        print(f"  ...status: {status} (attempt {attempt+1}/30)")

    if status != "ready":
        print(f"FAIL: Document failed to reach 'ready' state: {status}")
        return False
    print("  OK: Document processed and indexed (status: ready).")

    # 5. Create chat session and send message
    print("[5/7] Creating chat session and posting question...")
    sess_res = session.post(
        f"{base_url}/api/chat/sessions",
        headers=headers,
        json={"title": "Smoke Test Chat", "document_id": doc_id},
        timeout=10,
    )
    if sess_res.status_code != 201:
        print(f"FAIL: Create chat session failed ({sess_res.status_code}): {sess_res.text}")
        return False
    session_id = sess_res.json().get("id")

    msg_res = session.post(
        f"{base_url}/api/chat/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "What is this document about?"},
        timeout=30,
    )
    if msg_res.status_code != 200:
        print(f"FAIL: Send message failed ({msg_res.status_code}): {msg_res.text}")
        return False
    msg_data = msg_res.json()
    assistant_msg = msg_data.get("assistant_message", {})
    content = assistant_msg.get("content", "")
    sources = assistant_msg.get("sources", [])
    if not content:
        print("FAIL: Assistant message content is empty.")
        return False
    print(f"  OK: Received answer: \"{content[:80]}...\" with {len(sources)} source citations.")

    # 6. Delete document
    print(f"[6/7] Deleting document ({doc_id})...")
    del_res = session.delete(f"{base_url}/api/documents/{doc_id}", headers=headers, timeout=10)
    if del_res.status_code != 200:
        print(f"FAIL: Document deletion failed ({del_res.status_code}): {del_res.text}")
        return False
    print("  OK: Document deleted.")

    # 7. Verify 404
    print("[7/7] Verifying document is gone...")
    get_res = session.get(f"{base_url}/api/documents/{doc_id}", headers=headers, timeout=5)
    if get_res.status_code != 404:
        print(f"FAIL: Expected 404 for deleted document, got {get_res.status_code}")
        return False
    print("  OK: Confirmed document returned 404.")

    print("\n=== ALL SMOKE TEST CHECKS PASSED SUCCESSFULLY ===")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DocChat End-to-End Smoke Test")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="Base URL of running DocChat backend")
    args = parser.parse_args()

    success = run_smoke_test(args.base_url)
    sys.exit(0 if success else 1)
