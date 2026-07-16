from app.responses import error_response, success_response


def test_success_response_matches_uniform_envelope():
    assert success_response("req_1", "VP2000", {"verified": True}, 25) == {
        "request_id": "req_1",
        "status": "SUCCESS",
        "error_code": "VP2000",
        "data": {"verified": True},
        "latency_ms": 25,
    }


def test_error_response_matches_uniform_envelope():
    assert error_response("req_2", "VP4022", "Invalid payload") == {
        "request_id": "req_2",
        "status": "FAILED",
        "error_code": "VP4022",
        "message": "Invalid payload",
    }
