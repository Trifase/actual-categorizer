"""
Tests for Actual Budget Transaction Categorizer
Verifies the suggestion engine logic using mock objects.
"""

import os
os.environ["ACTUAL_LANGUAGE"] = "en"

from categorize import suggest_categories


class MockPayee:

    def __init__(self, name):
        self.name = name


class MockCategory:

    def __init__(self, id, name, group_name):
        self.id = id
        self.name = name
        self.group = MockGroup(group_name)


class MockGroup:

    def __init__(self, name):
        self.name = name


class MockTransaction:

    def __init__(
        self, payee_id=None, payee_name=None, notes=None, imported_description=None
    ):
        self.payee_id = payee_id
        self.payee = MockPayee(payee_name) if payee_name else None
        self.notes = notes
        self.imported_description = imported_description


def test_exact_payee_id_match():
    # Setup
    cat1 = MockCategory("cat_food", "Food", "Living")
    category_by_id = {cat1.id: cat1}

    payee_id_categories = {"payee_123": ["cat_food"]}
    payee_name_categories = {}

    tx = MockTransaction(payee_id="payee_123", payee_name="Muzzica Food")

    # Run
    results = suggest_categories(
        tx, payee_id_categories, payee_name_categories, category_by_id
    )

    # Verify
    assert len(results) == 1
    assert results[0][0].id == "cat_food"
    assert "Exact payee match" in results[0][2]
    print("[OK] test_exact_payee_id_match passed")


def test_notes_substring_match():
    # Setup
    cat1 = MockCategory("cat_groceries", "Groceries", "Living")
    category_by_id = {cat1.id: cat1}

    payee_id_categories = {}
    payee_name_categories = {"coop": ["cat_groceries"]}

    # Transaction with "COOP" in notes
    tx = MockTransaction(notes="PAGAMENTO SU CIRCUITO COOP SUPERMERCATI")

    # Run
    results = suggest_categories(
        tx, payee_id_categories, payee_name_categories, category_by_id
    )

    # Verify
    assert len(results) == 1
    assert results[0][0].id == "cat_groceries"
    assert "found in transaction text" in results[0][2]
    print("[OK] test_notes_substring_match passed")


def test_fuzzy_payee_match():
    # Setup
    cat1 = MockCategory("cat_dining", "Restaurants", "Living")
    category_by_id = {cat1.id: cat1}

    payee_id_categories = {}
    payee_name_categories = {"muzzica food": ["cat_dining"]}

    # Transaction with slightly different payee spelling
    tx = MockTransaction(payee_name="Muzzica Foods")

    # Run
    results = suggest_categories(
        tx, payee_id_categories, payee_name_categories, category_by_id
    )

    # Verify
    assert len(results) == 1
    assert results[0][0].id == "cat_dining"
    assert "Fuzzy payee match" in results[0][2]
    print("[OK] test_fuzzy_payee_match passed")


if __name__ == "__main__":
    test_exact_payee_id_match()
    test_notes_substring_match()
    test_fuzzy_payee_match()
    print("All tests passed successfully!")
