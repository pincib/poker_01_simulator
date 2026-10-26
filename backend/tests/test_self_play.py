"""Self-play accounting and rake behavior tests."""

import unittest

from backend.simulation.self_play import RakePolicy, SelfPlaySimulator


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


if __name__ == "__main__":
    unittest.main()
