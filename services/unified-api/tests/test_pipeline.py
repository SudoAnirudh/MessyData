import unittest
import sys
import os

# Add parent directory to path to enable module resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.normalizer import normalize_name, normalize_email, normalize_phone, normalize_address
from pipeline.matcher import calculate_match_score, find_best_match

class TestNormalizer(unittest.TestCase):
    def test_normalize_name(self):
        self.assertEqual(normalize_name("john doe"), "John Doe")
        self.assertEqual(normalize_name("DOE, JOHN"), "John Doe")
        self.assertEqual(normalize_name("  smith,  jane  "), "Jane Smith")
        self.assertEqual(normalize_name(""), "")
        self.assertEqual(normalize_name(None), "")

    def test_normalize_email(self):
        self.assertEqual(normalize_email(" John.Doe@Gmail.com "), "john.doe@gmail.com")
        self.assertEqual(normalize_email(""), "")
        self.assertEqual(normalize_email(None), "")

    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("+1 (555) 123-4567"), "5551234567")
        self.assertEqual(normalize_phone("1-555-123-4567"), "5551234567")
        self.assertEqual(normalize_phone("555.123.4567"), "5551234567")
        self.assertEqual(normalize_phone("12345"), "")  # too short
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")

    def test_normalize_address(self):
        self.assertEqual(normalize_address("123 Main Street"), "123 main st")
        self.assertEqual(normalize_address("456 Oak Road, Suite 100"), "456 oak rd suite 100")
        self.assertEqual(normalize_address("789 Pine Ave | Austin | TX"), "789 pine ave austin tx")
        self.assertEqual(normalize_address(""), "")
        self.assertEqual(normalize_address(None), "")


class TestMatcher(unittest.TestCase):
    def test_calculate_match_score_exact_email(self):
        record = {
            "name": "John Doe",
            "email": "john.doe@gmail.com",
            "phone": "5551234567",
            "address": "123 main st"
        }
        candidate = {
            "full_name": "John Doe",
            "email": "john.doe@gmail.com",
            "phone": "5551234567",
            "address": "123 main st"
        }
        score, reasons = calculate_match_score(record, candidate)
        self.assertEqual(score, 98)
        self.assertTrue(any("email" in r for r in reasons))

    def test_calculate_match_score_fuzzy_name(self):
        record = {
            "name": "Jessica Young",
            "email": "jyoung@gmail.com",
            "phone": "5551112222",
            "address": "4832 elm st austin tx"
        }
        candidate = {
            "full_name": "Jessica Young",
            "email": "diff_email@gmail.com",
            "phone": "diff_phone",
            "address": "4832 elm st austin tx"
        }
        score, reasons = calculate_match_score(record, candidate)
        # Fuzzy match score should be high confidence due to name + address similarity
        self.assertGreaterEqual(score, 85)
        self.assertTrue(any("address" in r for r in reasons))

    def test_find_best_match(self):
        record = {
            "name": "Jane Smith",
            "email": "jane.smith@gmail.com",
            "phone": "5559998888",
            "address": "999 pine ave"
        }
        candidates = [
            {
                "full_name": "John Doe",
                "email": "john.doe@gmail.com",
                "phone": "5551234567",
                "address": "123 main st"
            },
            {
                "full_name": "Jane Smith",
                "email": "jane.smith@gmail.com",
                "phone": "5550000000",
                "address": "999 pine ave"
            }
        ]
        best_cand, score, reasons = find_best_match(record, candidates)
        self.assertIsNotNone(best_cand)
        self.assertEqual(best_cand["full_name"], "Jane Smith")
        self.assertGreaterEqual(score, 75)

if __name__ == "__main__":
    unittest.main()
