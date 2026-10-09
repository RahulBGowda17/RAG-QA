import io
import time
import pytest


def test_api_upload_document(client):
    file_content = f"Supervised learning requires labeled training data pairs. Timestamp: {time.time()}".encode("utf-8")
    data = {
        "file": (io.BytesIO(file_content), f"test_api_doc_{int(time.time())}.txt")
    }
    res = client.post("/api/documents/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    json_data = res.get_json()
    assert json_data["success"] is True


def test_api_list_documents(client):
    res = client.get("/api/documents")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert isinstance(json_data["documents"], list)


def test_api_chat_flow(client):
    res = client.post("/api/chat", json={
        "question": "What does supervised learning require?"
    })
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert "answer" in json_data["data"]
    assert "citations" in json_data["data"]


def test_api_analytics(client):
    res = client.get("/api/analytics")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert json_data["metrics"]["total_documents"] >= 1


def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code in (200, 503)
    json_data = res.get_json()
    assert "status" in json_data
    assert "database" in json_data
    assert "faiss" in json_data
    assert "bm25" in json_data


def test_api_chat_scope_filtering(client):
    res = client.post("/api/chat", json={
        "question": "What does supervised learning require?",
        "document_ids": ["non-existent-doc-id"]
    })
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert json_data["data"]["citations"] == []
    assert json_data["data"]["evidence_status"] == "INSUFFICIENT EVIDENCE"


def test_api_feedback(client):
    chat_res = client.post("/api/chat", json={
        "question": "What is machine learning?"
    })
    assert chat_res.status_code == 200
    query_id = chat_res.get_json()["data"]["query_id"]

    res = client.post("/api/feedback", json={
        "query_id": query_id,
        "rating": 1,
        "comment": "Accurate extraction!"
    })
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert "feedback_id" in json_data



