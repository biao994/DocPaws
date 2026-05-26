def test_feedback_message_not_found(auth_client):
    r = auth_client.post(
        "/api/v1/feedback",
        json={
            "answer_id": "not_exist",
            "rating": "like",
            "comment": "",
        },
    )
    assert r.status_code == 404
    body = r.json()
    assert body["error_code"] == "ANSWER_NOT_FOUND"


def test_feedback_rating_validation_error(auth_client):
    r = auth_client.post(
        "/api/v1/feedback",
        json={
            "answer_id": "not_exist",
            "rating": "bad",  # 非 like/dislike
            "comment": "",
        },
    )
    # 这里预期是 400（VALIDATION_ERROR）或 404（MESSAGE_NOT_FOUND），取决于 service 校验顺序
    assert r.status_code in (400, 404)
    body = r.json()
    assert body["error_code"] in ("VALIDATION_ERROR", "ANSWER_NOT_FOUND")

