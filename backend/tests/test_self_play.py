"""Self-play accounting and rake behavior tests."""

import unittest

from backend.simulation.self_play import RakePolicy, SelfPlaySimulator
from backend.engine.rules import GameVariant


class SelfPlayTests(unittest.TestCase):
    def test_rake_obeys_no_flop_no_drop_percentage_and_cap(self) -> None:
        rake = RakePolicy(basis_points=500, cap=3)

        self.assertEqual(rake.collect(1_000, flop_dealt=False), 0)
        self.assertEqual(rake.collect(20, flop_dealt=True), 1)
        self.assertEqual(rake.collect(1_000, flop_dealt=True), 3)

    def test_seeded_bot_hands_conserve_chips_and_model_rake(self) -> None:
        result = SelfPlaySimulator(seed=29).run(hands=300)

        self.assertEqual(result.hands, 300)
        self.assertTrue(result.chips_conserved)
        self.assertGreater(result.actions, result.hands)
        self.assertGreater(result.showdowns, 0)
        self.assertGreater(result.rake_collected, 0)

    def test_self_play_is_reproducible_for_a_fixed_seed(self) -> None:
        first = SelfPlaySimulator(seed=31).run(hands=50)
        second = SelfPlaySimulator(seed=31).run(hands=50)

        self.assertEqual(first, second)

    def test_seeded_plo_self_play_audits_ties_all_ins_folds_and_chips(self) -> None:
        first = SelfPlaySimulator(
            seed=20261026,
            variant=GameVariant.POT_LIMIT_OMAHA,
            starting_stack=200,
            small_blind=1,
            big_blind=2,
        ).run(hands=500)
        second = SelfPlaySimulator(
            seed=20261026,
            variant=GameVariant.POT_LIMIT_OMAHA,
            starting_stack=200,
            small_blind=1,
            big_blind=2,
        ).run(hands=500)

        self.assertEqual(first, second)
        self.assertEqual(first.variant, GameVariant.POT_LIMIT_OMAHA.value)
        self.assertEqual(first.rake_collected, 0)
        self.assertTrue(first.chips_conserved)
        self.assertEqual(first.deadlocks, 0)
        self.assertGreater(first.showdowns, 0)
        self.assertGreater(first.ties, 0)
        self.assertGreater(first.all_in_hands, 0)
        self.assertGreater(first.all_in_events, 0)
        self.assertGreater(first.fold_actions, 0)


if __name__ == "__main__":
    unittest.main()
