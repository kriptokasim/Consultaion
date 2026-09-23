from services.migration_safety import REQUIRED_TABLES


def test_promotions_is_a_required_runtime_table():
    assert "promotions" in REQUIRED_TABLES
