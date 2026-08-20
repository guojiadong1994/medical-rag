from pathlib import Path

from fastapi.testclient import TestClient

from medical_rag.api.app import app


def test_restored_product_accounts_login():
    client = TestClient(app)
    cases = [
        ("user001", "123456", "user"),
        ("admin", "admin123", "admin"),
        ("doctor", "123456", "user"),
    ]
    for username, password, role in cases:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["accessToken"]
        assert payload["user"]["role"] == role


def test_restored_frontend_source_tree_is_complete():
    root = Path(__file__).resolve().parents[2]
    required = [
        "apps/web/src/views/LoginView.vue",
        "apps/web/src/views/UserHomeView.vue",
        "apps/web/src/views/UserHealthView.vue",
        "apps/web/src/views/UserRecordsView.vue",
        "apps/web/src/views/UserAssistantView.vue",
        "apps/web/src/views/UserSettingsView.vue",
        "apps/web/src/views/AdminKnowledgeView.vue",
        "apps/web/src/layouts/AppLayout.vue",
        "apps/web/src/router/index.ts",
        "apps/web/src/stores/auth.ts",
        "apps/web/src/styles/global.css",
        "apps/web/package.json",
        "apps/web/vite.config.ts",
    ]
    missing = [item for item in required if not (root / item).exists()]
    assert not missing, f"missing restored frontend files: {missing}"
