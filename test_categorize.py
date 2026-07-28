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


from cleanup import normalize_payee_name, get_default_search_term, cluster_payees

class MockPayeeObj:
    def __init__(self, id, name, transfer_acct=None, tombstone=0):
        self.id = id
        self.name = name
        self.transfer_acct = transfer_acct
        self.tombstone = tombstone

def test_normalization():
    assert normalize_payee_name("Commissioni Octopus Energy Italia Sr N: 116204929") == "commissioni octopus energy italia sr"
    assert normalize_payee_name("Octopus Energy Italia Sr") == "octopus energy italia sr"
    assert normalize_payee_name("Enel Energia S.p.A. N: 2026/1234") == "enel energia s.p.a"
    assert normalize_payee_name("Enel S.p.A. 1234567") == "enel s.p.a"
    print("[OK] test_normalization passed")

def test_default_search_term():
    assert get_default_search_term("Octopus Energy Italia Sr") == "Octopus Energy Italia"
    assert get_default_search_term("Enel Energia S.p.A.") == "Enel Energia"
    assert get_default_search_term("Coop s.r.l.") == "Coop"
    print("[OK] test_default_search_term passed")

def test_clustering():
    p1 = MockPayeeObj("1", "Octopus Energy Italia Sr")
    p2 = MockPayeeObj("2", "Commissioni Octopus Energy Italia Sr N: 116204929")
    p3 = MockPayeeObj("3", "Octopus Energy")
    p4 = MockPayeeObj("4", "Other Payee")
    p_trans = MockPayeeObj("5", "Transfer Payee", transfer_acct="acc1")
    
    payees = [p1, p2, p3, p4, p_trans]
    clusters = cluster_payees(payees)
    
    assert len(clusters) == 1
    cluster_ids = {p.id for p in clusters[0]}
    assert "1" in cluster_ids
    assert "2" in cluster_ids
    assert "3" in cluster_ids
    assert "4" not in cluster_ids
    assert "5" not in cluster_ids
    print("[OK] test_clustering passed")


def test_persistent_ignore():
    p1 = MockPayeeObj("1", "Octopus Energy Italia Sr")
    p2 = MockPayeeObj("2", "Commissioni Octopus Energy Italia Sr N: 116204929")
    p3 = MockPayeeObj("3", "Other Payee A")
    p4 = MockPayeeObj("4", "Other Payee B N: 123")
    
    payees = [p1, p2, p3, p4]
    raw_clusters = cluster_payees(payees)
    assert len(raw_clusters) == 2
    
    ignored_groups = [{"1", "2"}]
    
    clusters = []
    for cluster in raw_clusters:
        cluster_ids = {p.id for p in cluster}
        is_ignored = False
        for ignored_group in ignored_groups:
            if cluster_ids.issubset(ignored_group):
                is_ignored = True
                break
        if not is_ignored:
            clusters.append(cluster)
            
    assert len(clusters) == 1
    assert clusters[0][0].id in ("3", "4")
    print("[OK] test_persistent_ignore passed")


if __name__ == "__main__":
    test_exact_payee_id_match()
    test_notes_substring_match()
    test_fuzzy_payee_match()
    test_normalization()
    test_default_search_term()
    test_clustering()
    test_persistent_ignore()
    print("All tests passed successfully!")
