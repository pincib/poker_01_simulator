"""Known-answer and edge-case tests for the Cactus Kev hand evaluator."""

import unittest
import random
from itertools import combinations

from backend.engine.card import Card
from backend.engine.evaluator import HandEvaluator


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes)


class HandEvaluatorTests(unittest.TestCase):
    def test_five_card_categories_match_classic_7462_rank_boundaries(self) -> None:
        examples = (
            (1, cards("As", "Ks", "Qs", "Js", "Ts")),
            (11, cards("As", "Ah", "Ad", "Ac", "Ks")),
            (167, cards("As", "Ah", "Ad", "Ks", "Kh")),
            (323, cards("As", "Ks", "Qs", "Js", "9s")),
            (1600, cards("As", "Kh", "Qd", "Jc", "Ts")),
            (1610, cards("As", "Ah", "Ad", "Ks", "Qh")),
            (2468, cards("As", "Ah", "Ks", "Kh", "Qd")),
            (3326, cards("As", "Ah", "Ks", "Qh", "Jd")),
            (7462, cards("7c", "5d", "4h", "3s", "2c")),
        )

        for expected, hand in examples:
            with self.subTest(expected=expected):
                self.assertEqual(HandEvaluator.evaluate_5(hand), expected)

    def test_seven_card_evaluation_uses_best_five_and_returns_the_combination(self) -> None:
        royal_flush = cards("As", "Ks", "Qs", "Js", "Ts", "2d", "3c")
        score, best_hand = HandEvaluator.evaluate_7_with_hand(royal_flush)

        self.assertEqual(score, 1)
        self.assertEqual({card.code for card in best_hand}, {"As", "Ks", "Qs", "Js", "Ts"})
        self.assertEqual(HandEvaluator.evaluate_7(royal_flush), 1)

    def test_direct_seven_card_rank_matches_the_five_card_subset_oracle(self) -> None:
        rng = random.Random(713)
        deck = [Card.from_code(f"{rank}{suit}") for suit in "cdhs" for rank in "23456789TJQKA"]

        for sample in range(500):
            hand = tuple(rng.sample(deck, 7))
            with self.subTest(sample=sample):
                self.assertEqual(
                    HandEvaluator.evaluate_7(hand),
                    min(HandEvaluator.evaluate_5(five) for five in combinations(hand, 5)),
                )

    def test_sample_hierarchy_and_wheel_straight(self) -> None:
        royal_flush = cards("As", "Ks", "Qs", "Js", "Ts", "2d", "3c")
        wheel_straight = cards("5h", "4c", "3d", "2s", "Ah", "9c", "Kd")
        full_house = cards("8s", "8h", "8d", "4c", "4s", "2h", "Jd")

        self.assertEqual(HandEvaluator.evaluate_7(royal_flush), 1)
        self.assertLess(HandEvaluator.evaluate_7(full_house), HandEvaluator.evaluate_7(wheel_straight))
        self.assertEqual(HandEvaluator.describe(wheel_straight), "Straight, Five-High")

    def test_describes_two_pair_with_ranked_kicker(self) -> None:
        hand = cards("As", "Ah", "Ks", "Kh", "Qd", "3c", "2h")

        self.assertEqual(HandEvaluator.describe(hand), "Two Pair, Aces and Kings, Queen Kicker")

    def test_rejects_wrong_card_count_and_duplicates(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly 5"):
            HandEvaluator.evaluate_5(cards("As", "Ks", "Qs", "Js"))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            HandEvaluator.evaluate_5(cards("As", "As", "Qs", "Js", "Ts"))


if __name__ == "__main__":
    unittest.main()
