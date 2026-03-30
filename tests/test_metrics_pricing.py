import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from predictor import market_metrics, corners_market_catalog
from main import build_market_telemetry


class MetricsPricingTest(unittest.TestCase):
    def test_market_metrics_formula(self):
        m = market_metrics(2.00, 0.60, 0.52)
        self.assertAlmostEqual(m["implied_prob"], 0.5, places=6)
        self.assertAlmostEqual(m["delta_prob"], 0.10, places=6)
        self.assertAlmostEqual(m["edge"], 0.08, places=6)
        self.assertAlmostEqual(m["ev"], 0.20, places=6)
        self.assertTrue(m["pricing_complete"])

    def test_ev_and_edge_not_mixed_on_primary(self):
        row = {
            "mercado_principal": "Corners",
            "apuesta_principal": "Más de 8.5 corners",
            "prob_apuesta": 0.61,
            "cuota_principal": 1.92,
            "edge_principal": 0.089168,
            "probabilidad_justa_principal": 0.520833,
            "confianza": 70,
            "stake_sugerido_unidades": 1.0,
            "es_value_bet": True,
            "apuestas_fuertes": [],
        }
        telemetry = build_market_telemetry(row, None)
        primary = telemetry["Corners"]
        self.assertAlmostEqual(primary["edge"], 0.089168, places=6)
        self.assertAlmostEqual(primary["ev"], 0.1712, places=4)
        self.assertNotAlmostEqual(primary["edge"], primary["ev"], places=3)

    def test_incomplete_pricing_disables_value_badges(self):
        row = {
            "mercado_principal": "Corners",
            "apuesta_principal": "Más de 8.5 corners",
            "prob_apuesta": 0.61,
            "cuota_principal": 1.92,
            "edge_principal": None,
            "probabilidad_justa_principal": None,
            "confianza": 70,
            "stake_sugerido_unidades": 1.0,
            "es_value_bet": True,
            "apuestas_fuertes": [],
        }
        telemetry = build_market_telemetry(row, None)
        primary = telemetry["Corners"]
        self.assertFalse(primary["pricing_complete"])
        self.assertFalse(primary["flags"]["ev_plus"])
        self.assertFalse(primary["flags"]["value"])
        self.assertFalse(primary["flags"]["strong_signal"])

    def test_corners_structure_ready_for_growth(self):
        catalog = corners_market_catalog()
        self.assertIn("totals", catalog)
        self.assertIn("team_totals", catalog)
        self.assertIn("handicap", catalog)
        self.assertIn("periods", catalog)
        self.assertIn("race_to_x", catalog)


if __name__ == "__main__":
    unittest.main()
