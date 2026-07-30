from __future__ import annotations

from fastapi.testclient import TestClient

from app.web.app import create_web_app


def test_dashboard_page_exposes_recommendation_controls() -> None:
    client: TestClient = TestClient(create_web_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "오늘의 뉴스를 기준으로 추천받기" in response.text
    assert "실시간 작업" in response.text
    assert "선택된 뉴스" in response.text
    assert "매수 · 판매 추천" in response.text


def test_dashboard_rejects_unknown_run() -> None:
    client: TestClient = TestClient(create_web_app())

    response = client.get("/api/runs/not-found")

    assert response.status_code == 404
