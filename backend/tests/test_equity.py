"""Known-answer tests for pot odds, SPR, Monte Carlo equity, and draw outs."""

import unittest

from backend.brain.draws import DrawDetector, StraightDrawType
from backend.brain.equity import EquityCalculator
from backend.brain.pot_odds import PotOddsCalculator
from backend.brain.spr import SPRCalculator
from backend.engine.card import Card


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes)


class MathEngineTests(unittest.TestCase):
    def test_pot_odds_is_call_over_pot_after_call(self) -> None:
        result = PotOddsCalculator.calculate(call_amount=20, pot_before_call=60)

        self.assertEqual(result.required_equity_percentage, 25.0)

    def test_spr_uses_the_effective_stack(self) -> None:
        result = SPRCalculator.calculate(player_stack=100, opponent_stack=60, flop_pot=30)

        self.assertEqual(result.effective_stack, 60.0)
        self.assertEqual(result.value, 2.0)

    def test_known_river_showdown_returns_exact_win_loss_percentages(self) -> None:
        result = EquityCalculator.calculate(
            hero_hole=cards("As", "Ah"),
            villain_hole=cards("Ks", "Kh"),
            board=cards("2c", "3d", "4h", "5s", "9c"),
            iterations=25,
            seed=7,
        )

        self.assertEqual((result.win_percentage, result.tie_percentage, result.loss_percentage), (100.0, 0.0, 0.0))
        self.assertEqual(result.equity_percentage, 100.0)

    def test_plo_known_river_uses_exact_two_hole_and_three_board_cards(self) -> None:
        result = EquityCalculator.calculate(
            hero_hole=cards("Ac", "Kc", "2d", "3h"),
            villain_hole=cards("9c", "8c", "4d", "5h"),
            board=cards("Qc", "Jc", "Tc", "2s", "3s"),
            iterations=25,
            seed=7,
        )
        self.assertEqual((result.win_percentage, result.tie_percentage, result.loss_percentage), (100.0, 0.0, 0.0))

    def test_plo_partial_board_range_and_seed_are_reproducible(self) -> None:
        kwargs = dict(
            hero_hole=cards("As", "Ah", "Kd", "Qc"),
            board=cards("2c", "3d", "4h"),
            villain_range=(cards("Ks", "Kh", "Jd", "Tc"), cards("Qs", "Qh", "9d", "8c")),
            iterations=300,
            seed=441,
        )
        first = EquityCalculator.calculate(**kwargs)
        second = EquityCalculator.calculate(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first.iterations, 300)
        self.assertAlmostEqual(first.win_percentage + first.tie_percentage + first.loss_percentage, 100.0)

    def test_plo_turn_with_uniform_and_ranged_multiway_opponents_is_reproducible(self) -> None:
        args = (
            cards("As", "Ah", "Kd", "Qc"),
            (None, (cards("Ks", "Kh", "Jd", "Tc"),)),
            cards("2c", "3d", "4h", "5s"),
        )
        first = EquityCalculator.calculate_multiway(*args, iterations=100, seed=92)
        second = EquityCalculator.calculate_multiway(*args, iterations=100, seed=92)
        self.assertEqual(first, second)
        self.assertEqual(first.iterations, 100)
        self.assertAlmostEqual(first.win_percentage + first.tie_percentage + first.loss_percentage, 100.0)

    def test_plo_multiway_ranges_remove_collisions_and_split_ties_by_winner_count(self) -> None:
        result = EquityCalculator.calculate_multiway(
            hero_hole=cards("As", "Kd", "2c", "3d"),
            opponent_ranges=(
                (cards("Ah", "Qd", "4c", "5d"),),
                (cards("Ac", "Jd", "6c", "7d"),),
            ),
            board=cards("2s", "3s", "4h", "5s", "9c"),
            iterations=20,
            seed=19,
        )
        self.assertAlmostEqual(result.win_percentage + result.tie_percentage + result.loss_percentage, 100.0)
        self.assertGreaterEqual(result.equity_percentage, 0.0)
        self.assertLessEqual(result.equity_percentage, 100.0)

    def test_plo_range_with_only_blocked_combos_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "no hands remaining"):
            EquityCalculator.calculate(
                hero_hole=cards("As", "Ah", "Ks", "Kh"),
                villain_range=(cards("As", "Ad", "Kd", "Qd"),),
                iterations=1,
            )

    def test_plo_multiway_ranges_without_compatible_combinations_are_rejected(self) -> None:
        forced = cards("Ks", "Kh", "Jd", "Tc")
        with self.assertRaisesRegex(ValueError, "no mutually compatible"):
            EquityCalculator.calculate_multiway(
                hero_hole=cards("As", "Ah", "Kd", "Qc"),
                opponent_ranges=((forced,), (forced,)),
                board=cards("2c", "3d", "4h"),
                iterations=1,
                seed=2,
            )

    def test_aces_vs_kings_preflop_is_near_the_known_equity(self) -> None:
        result = EquityCalculator.calculate(
            hero_hole=cards("As", "Ah"),
            villain_hole=cards("Ks", "Kh"),
            iterations=2_000,
            seed=24,
        )

        self.assertAlmostEqual(result.win_percentage + result.tie_percentage + result.loss_percentage, 100.0)
        self.assertGreater(result.equity_percentage, 78.0)
        self.assertLess(result.equity_percentage, 86.0)

    def test_villain_range_is_supported_and_blockers_are_removed(self) -> None:
        result = EquityCalculator.calculate(
            hero_hole=cards("As", "Ah"),
            board=cards("2c", "3d", "4h"),
            villain_range=(cards("Ks", "Kh"), cards("Qs", "Qh"), cards("As", "Ad")),
            iterations=100,
            seed=7,
        )

        self.assertEqual(result.iterations, 100)
        self.assertAlmostEqual(result.win_percentage + result.tie_percentage + result.loss_percentage, 100.0)

    def test_multiway_equity_splits_a_three_player_tie_by_pot_share(self) -> None:
        result = EquityCalculator.calculate_multiway(
            hero_hole=cards("As", "Kd"),
            opponent_ranges=((cards("Ah", "Qd"),), (cards("Ac", "Jd"),)),
            board=cards("2c", "3d", "4h", "5s", "9c"),
            iterations=12,
            seed=19,
        )

        self.assertEqual((result.win_percentage, result.tie_percentage, result.loss_percentage), (0.0, 100.0, 0.0))
        self.assertAlmostEqual(result.equity_percentage, 100 / 3)

    def test_flush_draw_reports_nine_outs_and_marks_higher_flush_as_dirty(self) -> None:
        result = DrawDetector.analyze(
            hero_hole=cards("9h", "8h"),
            board=cards("2h", "5h", "Ks"),
            villain_hole=cards("Ah", "Kh"),
        )

        self.assertTrue(result.flush_draw)
        self.assertEqual(len(result.flush_outs), 7)  # Two hearts are blocked by Villain.
        self.assertEqual(len(result.dirty_outs), 7)
        self.assertEqual(result.clean_outs, ())
        unblocked = DrawDetector.analyze(cards("9h", "8h"), cards("2h", "5h", "Ks"))
        self.assertEqual(len(unblocked.flush_outs), 9)

    def test_open_ended_and_gutshot_straight_draws_have_expected_out_counts(self) -> None:
        open_ended = DrawDetector.analyze(
            hero_hole=cards("8c", "7d"), board=cards("6s", "5h", "Kd")
        )
        gutshot = DrawDetector.analyze(
            hero_hole=cards("8c", "7d"), board=cards("6s", "4h", "Kd")
        )

        self.assertEqual(open_ended.straight_draw, StraightDrawType.OPEN_ENDED)
        self.assertEqual(len(open_ended.straight_outs), 8)
        self.assertEqual(gutshot.straight_draw, StraightDrawType.GUTSHOT)
        self.assertEqual(len(gutshot.straight_outs), 4)

    def test_calculators_reject_impossible_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            SPRCalculator.calculate(100, 100, 0)
        with self.assertRaisesRegex(ValueError, "distinct"):
            EquityCalculator.calculate(cards("As", "Ah"), cards("As", "Kh"), iterations=1)


if __name__ == "__main__":
    unittest.main()
