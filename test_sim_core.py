# -*- coding: utf-8 -*-
"""계산 엔진 검증:  python -m unittest discover -s tests -v"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sim_core as sc  # noqa: E402


class VacuumTests(unittest.TestCase):
    def setUp(self):
        self._c = sc.C_DRAG
        sc.C_DRAG = 0.0          # 공기저항 끄기 -> 진공 포물선

    def tearDown(self):
        sc.C_DRAG = self._c

    def test_euler_height_error_matches_theory(self):
        """진공에서 오일러의 높이 오차는 정확히 (1/2)·g·h·t"""
        h, steps = 0.05, 60
        s = (0.0, 0.0, 10.0, 20.0, 25.0)
        for _ in range(steps):
            s = sc.euler_step(s, h, 0.0)
        t = s[0]
        exact_y = 10.0 + 25.0 * t - 0.5 * sc.G * t * t
        self.assertAlmostEqual(s[2] - exact_y, 0.5 * sc.G * h * t, places=9)

    def test_rk4_matches_analytic(self):
        s = (0.0, 0.0, 10.0, 20.0, 25.0)
        for _ in range(1000):
            s = sc.rk4_step(s, 0.002, 0.0)
        t = s[0]
        self.assertAlmostEqual(s[1], 20.0 * t, places=8)
        self.assertAlmostEqual(s[2], 10.0 + 25.0 * t - 0.5 * sc.G * t * t, places=8)


class ErrorOrderTests(unittest.TestCase):
    def test_euler_global_error_is_first_order(self):
        field = sc.Field(7)
        for shooter in (0, 1):
            ref, rows = sc.error_study(field, shooter, 45, 70, 3.0)
            slope = sc.loglog_slope(rows)
            self.assertIsNotNone(ref)
            self.assertAlmostEqual(slope, 1.0, delta=0.1)

    def test_halving_h_halves_error(self):
        _, rows = sc.error_study(sc.Field(7), 0, 45, 70, 3.0, hs=[0.1, 0.05])
        ratio = rows[0][2] / rows[1][2]
        self.assertAlmostEqual(ratio, 2.0, delta=0.15)


class FieldTests(unittest.TestCase):
    def test_terrain_is_deterministic(self):
        self.assertEqual(sc.make_terrain(3), sc.make_terrain(3))
        self.assertNotEqual(sc.make_terrain(3), sc.make_terrain(4))

    def test_shot_lands_on_ground_or_leaves_field(self):
        field = sc.Field(7)
        s0 = field.launch(0, 45, 60)
        _, hit = field.simulate(sc.euler_step, 0.05, s0, 0, 0.0)
        self.assertIsNotNone(hit)
        self.assertIn(hit[3][0], ("ground", "tank", "out"))


if __name__ == "__main__":
    unittest.main()
