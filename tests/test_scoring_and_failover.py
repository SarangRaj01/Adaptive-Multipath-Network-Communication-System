"""
Unit tests for Path Scoring, Traffic Distribution and Automatic Failover.
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.scorer import PathScorer, RoutingMode

class TestScoringAndFailover(unittest.TestCase):
    def setUp(self):
        self.scorer = PathScorer()

    def test_lower_latency_gets_higher_share(self):
        metrics = {
            "R1": {"rtt_ms": 15.0, "loss_rate": 0.0, "jitter_ms": 2.0, "is_alive": True},
            "R2": {"rtt_ms": 40.0, "loss_rate": 0.0, "jitter_ms": 4.0, "is_alive": True},
            "R3": {"rtt_ms": 80.0, "loss_rate": 0.0, "jitter_ms": 8.0, "is_alive": True}
        }
        dist = self.scorer.calculate_traffic_distribution(metrics, mode=RoutingMode.ADAPTIVE)
        
        # R1 should receive significantly higher traffic than R2 and R3
        self.assertGreater(dist["R1"], dist["R2"])
        self.assertGreater(dist["R2"], dist["R3"])
        self.assertAlmostEqual(sum(dist.values()), 1.0, places=2)

    def test_automatic_rerouting_on_failure(self):
        # Simulate R1 going down completely
        metrics = {
            "R1": {"rtt_ms": 15.0, "loss_rate": 1.0, "jitter_ms": 2.0, "is_alive": False},
            "R2": {"rtt_ms": 35.0, "loss_rate": 0.0, "jitter_ms": 4.0, "is_alive": True},
            "R3": {"rtt_ms": 70.0, "loss_rate": 0.0, "jitter_ms": 8.0, "is_alive": True}
        }
        dist = self.scorer.calculate_traffic_distribution(metrics, mode=RoutingMode.ADAPTIVE)
        
        # R1 should have 0% traffic share
        self.assertEqual(dist["R1"], 0.0)
        # R2 and R3 should divide 100% of the traffic
        self.assertAlmostEqual(dist["R2"] + dist["R3"], 1.0, places=2)
        self.assertGreater(dist["R2"], dist["R3"])

    def test_round_robin_distribution(self):
        metrics = {
            "R1": {"rtt_ms": 10.0, "loss_rate": 0.0, "jitter_ms": 1.0, "is_alive": True},
            "R2": {"rtt_ms": 50.0, "loss_rate": 0.0, "jitter_ms": 5.0, "is_alive": True},
            "R3": {"rtt_ms": 90.0, "loss_rate": 0.0, "jitter_ms": 9.0, "is_alive": True}
        }
        dist = self.scorer.calculate_traffic_distribution(metrics, mode=RoutingMode.ROUND_ROBIN)
        self.assertAlmostEqual(dist["R1"], 1/3, places=2)
        self.assertAlmostEqual(dist["R2"], 1/3, places=2)
        self.assertAlmostEqual(dist["R3"], 1/3, places=2)

if __name__ == "__main__":
    unittest.main()
