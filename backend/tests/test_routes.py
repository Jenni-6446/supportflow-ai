import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


from app.main import app  # noqa: E402


client = TestClient(app)


def vpn_ticket_payload() -> dict:
    return {
        "title": "VPN authentication failed",
        "userMessage": "Cannot connect to VPN from home.",
        "affectedService": "VPN",
        "deviceType": "Windows laptop",
        "location": "home",
        "affectedUsers": "single_user",
        "agentSelectedUrgency": "medium",
        "businessImpact": "User cannot access internal systems.",
        "errorMessage": "Authentication failed",
        "environmentContext": {
            "operatingSystem": "windows",
            "accountPlatform": "microsoft_365",
            "applicationPlatform": "vpn_client",
        },
    }


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_ticket_returns_structured_triage_json():
    response = client.post("/api/analyze-ticket", json=vpn_ticket_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["classification"]["category"] == "vpn_remote_access"
    assert data["priorityAssessment"]["priority"] == "P3"
    assert data["checklist"]
    assert data["safetyNotes"]
    assert "summary" in data


def test_analyze_ticket_rejects_invalid_ticket_payload():
    payload = vpn_ticket_payload()
    payload["location"] = "invalid_location"

    response = client.post("/api/analyze-ticket", json=payload)

    assert response.status_code == 422


def test_update_diagnosis_returns_structured_diagnosis_json():
    response = client.post(
        "/api/update-diagnosis",
        json={
            "ticket": vpn_ticket_payload(),
            "checklistResults": [
                {
                    "stepId": "vpn-confirm-internet",
                    "result": "works",
                    "evidence": "Public websites open normally.",
                    "recordedAt": datetime.now().astimezone().isoformat(),
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["currentLikelyCause"]["cause"]
    assert data["confidence"] in {"low", "medium", "high"}
    assert data["status"] == "in_progress"
    assert data["ruledOutCauses"][0]["cause"] == "General internet connectivity issue"


def test_update_diagnosis_rejects_naive_recorded_at():
    response = client.post(
        "/api/update-diagnosis",
        json={
            "ticket": vpn_ticket_payload(),
            "checklistResults": [
                {
                    "stepId": "vpn-confirm-internet",
                    "result": "works",
                    "evidence": "Public websites open normally.",
                    "recordedAt": "2026-06-03T15:30:00",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_generate_documentation_returns_structured_documentation_json():
    diagnosis_response = client.post(
        "/api/update-diagnosis",
        json={
            "ticket": vpn_ticket_payload(),
            "checklistResults": [],
        },
    )
    assert diagnosis_response.status_code == 200

    response = client.post(
        "/api/generate-documentation",
        json={
            "ticket": vpn_ticket_payload(),
            "diagnosis": diagnosis_response.json(),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "VPN authentication failed" in data["internalNote"]
    assert data["userResponseDraft"]
    assert data["resolutionNote"]
    assert data["escalationNote"]
