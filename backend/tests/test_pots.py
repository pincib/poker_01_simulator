"""Tests for contribution-layer pots and showdown payouts."""

import unittest

from backend.engine.player import Player
from backend.engine.pot import Pot, PotManager


class PotManagerTests(unittest.TestCase):
    def test_builds_main_and_side_pots_from_unequal_all_ins(self) -> None:
        players = (
            Player("short", "Short", 0, is_all_in=True, total_contributed=20),
            Player("middle", "Middle", 0, is_all_in=True, total_contributed=45),
            Player("deep", "Deep", 55, total_contributed=45),
        )

        pots = PotManager.build_side_pots(players)

        self.assertEqual(
            [(pot.label, pot.amount, pot.eligible_player_ids) for pot in pots],
            [
                ("Main Pot", 60, ("short", "middle", "deep")),
                ("Side Pot 1", 50, ("middle", "deep")),
            ],
        )
        self.assertEqual(PotManager.total(pots), 110)

    def test_returns_only_uncalled_top_layer(self) -> None:
        players = (
            Player("a", "A", 0, is_all_in=True, total_contributed=100),
            Player("b", "B", 0, is_all_in=True, total_contributed=60),
            Player("c", "C", 0, is_all_in=True, total_contributed=60),
        )

        pots = PotManager.build_side_pots(players)

        self.assertEqual([(pot.amount, pot.refund_to) for pot in pots], [(180, None), (40, "a")])

    def test_splits_ties_and_assigns_odd_chip_clockwise_after_button(self) -> None:
        players = (
            Player("button", "Button", 0, is_all_in=True, total_contributed=0),
            Player("left", "Left", 0, is_all_in=True, total_contributed=0),
            Player("right", "Right", 0, is_all_in=True, total_contributed=0),
        )
        payouts = PotManager.award(
            (Pot("Main Pot", 5, ("button", "left", "right")),),
            {"button": 2, "left": 1, "right": 1},
            players,
            button_index=0,
        )

        self.assertEqual(payouts, {"button": 0, "left": 3, "right": 2})


if __name__ == "__main__":
    unittest.main()
