"""Unit tests for Task 2 rotation metrics."""

import unittest

import numpy as np

from src.modeling.rotation_classifier import (
    alternation_score,
    alternation_score_batch,
    classify_pixel,
    cornsoy_years_count,
    crop_share,
    max_run_length,
    pattern_edit_distance,
    shannon_entropy,
    transition_counts_corn_soy_other,
)


class TestRotationMetrics(unittest.TestCase):
    def test_alternation_perfect_corn_soy(self):
        seq = np.array([1, 5, 1, 5, 1, 5, 1, 5, 1, 5], dtype=np.int16)
        self.assertAlmostEqual(alternation_score(seq), 1.0)

    def test_alternation_batch_matches_scalar(self):
        seqs = np.array([[1, 5, 1, 5, 1, 5, 1, 5, 1, 5], [1, 1, 1, 5, 5, 5, 1, 5, 1, 5]], dtype=np.int16)
        b = alternation_score_batch(seqs)
        self.assertAlmostEqual(float(b[0]), alternation_score(seqs[0]))
        self.assertAlmostEqual(float(b[1]), alternation_score(seqs[1]))

    def test_monoculture_run(self):
        seq = np.array([1] * 10, dtype=np.int16)
        self.assertEqual(max_run_length(seq), 10)
        self.assertAlmostEqual(crop_share(seq), 1.0)

    def test_pattern_distance_zero_for_canonical(self):
        seq = np.array([1, 5, 1, 5, 1, 5, 1, 5, 1, 5], dtype=np.int16)
        self.assertEqual(pattern_edit_distance(seq), 0)

    def test_entropy_binary(self):
        seq = np.array([1, 1, 5, 5], dtype=np.int16)
        h = shannon_entropy(seq)
        self.assertAlmostEqual(h, 1.0)

    def test_classify_monoculture_first(self):
        self.assertEqual(classify_pixel(0.9, 8, 0, 10, 0.5, mono_run=7), 1)
        self.assertEqual(
            classify_pixel(0.8, 3, 2, 8, 0.5, alt_min=0.7, dist_max=3, cs_min=7, mono_run=7),
            0,
        )
        self.assertEqual(classify_pixel(0.2, 2, 10, 8, 0.5), 2)

    def test_cornsoy_count(self):
        seq = np.array([1, 2, 5, 5, 0, 1, 5, 1, 5, 1], dtype=np.int16)
        self.assertEqual(cornsoy_years_count(seq), 8)

    def test_markov_counts_shape_and_stochastic_rows(self):
        seqs = np.array([[1, 5, 1, 5, 1, 5], [5, 5, 1, 1, 5, 5]], dtype=np.int16)
        counts, probs = transition_counts_corn_soy_other(seqs, corn=1, soy=5)
        self.assertEqual(counts.shape, (3, 3))
        self.assertEqual(probs.shape, (3, 3))
        row_sums = probs.sum(axis=1)
        self.assertTrue(np.all((row_sums >= 0.0) & (row_sums <= 1.0 + 1e-9)))
        active = counts.sum(axis=1) > 0
        np.testing.assert_allclose(row_sums[active], 1.0, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
