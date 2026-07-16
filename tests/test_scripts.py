from scripts.load_test import classify_status, empty_summary
from scripts.seed import CLIENTS, _historical_log


def test_seed_defines_three_fictional_clients_with_three_users_supported():
    assert [client[0] for client in CLIENTS] == ["alphabank", "zetafin", "novahr"]
    assert all(client[2] for client in CLIENTS)
    assert all(len(client[3]) >= 1 for client in CLIENTS)


def test_historical_seed_log_contains_only_masked_and_hashed_pii():
    document = _historical_log("alphabank", "al_ops_01", 3)
    assert document["id_number_masked"].endswith("234F")
    assert len(document["id_number_hash"]) == 64
    assert len(document["name_hash"]) == 64
    serialized = repr(document)
    assert "ABCDE1234F" not in serialized
    assert "Synthetic User" not in serialized


def test_load_test_status_classification_counts_all_outcomes():
    summary = empty_summary()
    for status in [200, 200, 429, 403, 500, 0]:
        classify_status(summary, status)
    assert summary == {
        "sent": 6,
        "succeeded": 2,
        "rate_limited": 1,
        "blocked": 1,
        "failed": 2,
    }
