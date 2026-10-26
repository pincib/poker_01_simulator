"""PLO bridge tests for exact-two evaluation, pot limits, and wrap outs."""

import unittest

from backend.brain.plo_draws import OmahaWrapDetector
from backend.engine.card import Card
from backend.engine.evaluator import HandEvaluator
from backend.engine.pot_limit import PotLimitBetSizer, pot_limit_max_raise


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes)


class PLOBridgeTests(unittest.TestCase):
    def test_plo_uses_exactly_two_hole_cards_and_three_board_cards(self) -> None:
        hole = cards("Ts", "3h", "4c", "5d")
        board = cards("As", "Ks", "Qs", "Js", "2d")

        score, chosen = HandEvaluator.evaluate_plo_with_hand(hole, board)

        self.assertEqual(len(chosen), 5)
        self.assertEqual(sum(card in hole for card in chosen), 2)
        self.assertEqual(sum(card in board for card in chosen), 3)
        # The four spades on the board cannot make a flush without two spades
        # in hand. Hold'em-style board-playing is not legal in Omaha.
        self.assertGreater(score, 1609)

    def test_complete_board_evaluates_best_of_exactly_sixty_combinations(self) -> None:
        hole = cards("As", "Ah", "Kc", "Qd")
        board = cards("Ac", "Kh", "Kd", "2s", "3d")

        score, chosen = HandEvaluator.evaluate_plo_with_hand(hole, board)

        self.assertEqual(score, HandEvaluator.evaluate_plo(hole, board))
        self.assertEqual(set(card.code for card in chosen), {"As", "Ah", "Ac", "Kh", "Kd"})

    def test_plo_evaluator_rejects_invalid_counts_and_duplicate_cards(self) -> None:
        with self.assertRaisesRegex(ValueError, "four hole cards"):
            HandEvaluator.evaluate_plo(cards("As", "Kh"), cards("2c", "3d", "4h"))
        with self.assertRaisesRegex(ValueError, "distinct"):
            HandEvaluator.evaluate_plo(cards("As", "Kh", "Qd", "Jc"), cards("As", "3d", "4h"))

    def test_pot_limit_raise_to_uses_pot_plus_twice_call_and_caps_to_stack(self) -> None:
        self.assertEqual(pot_limit_max_raise(150, 50), 250)
        self.assertEqual(PotLimitBetSizer.maximum_raise_to(150, 50), 250)
        self.assertEqual(
            PotLimitBetSizer.maximum_raise_to(150, 50, player_current_bet=10, player_stack=120),
            130,
        )

    def test_wrap_detector_counts_thirteen_unique_straight_outs(self) -> None:
        result = OmahaWrapDetector.analyze(
            cards("Qh", "Jh", "9c", "8s"),
            cards("Th", "7h", "2c"),
        )

        self.assertEqual(result.out_count, 13)
        self.assertTrue(result.is_wrap)
        self.assertEqual(len(set(result.straight_outs)), 13)
        self.assertEqual(result.clean_outs, result.straight_outs)

    def test_wrap_detector_removes_villain_blockers_and_stops_on_river(self) -> None:
        hero = cards("Qh", "Jh", "9c", "8s")
        board = cards("Th", "7h", "2c")
        result = OmahaWrapDetector.analyze(hero, board, cards("6s", "9s", "Ah", "Kh"))
        river = OmahaWrapDetector.analyze(hero, cards("Ts", "7d", "2c", "3s", "4h"))

        self.assertLess(result.out_count, 13)
        self.assertTrue(result.dirty_outs)
        self.assertEqual(result.out_count, len(result.clean_outs) + len(result.dirty_outs))
        self.assertEqual(river.out_count, 0)


if __name__ == "__main__":
    unittest.main()
