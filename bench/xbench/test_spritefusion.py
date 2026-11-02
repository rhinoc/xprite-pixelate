"""Adapter checks for output, CLI failure and timeout."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import subprocess
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
import methods

class SpriteFusionAdapterTest(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((4, 4, 4), dtype=np.uint8)
        self.method = methods.SpriteFusion()

    def test_output_and_environment(self):
        def fake(argv, **kwargs):
            self.assertEqual(kwargs['env']['RAYON_NUM_THREADS'], '1')
            self.assertEqual(len(argv), 3)
            Image.fromarray(self.image).save(argv[2])
            return subprocess.CompletedProcess(argv, 0, '', '')
        with patch.object(methods.subprocess, 'run', side_effect=fake):
            result = self.method.run(self.image)
        self.assertIsNone(result.error)
        np.testing.assert_array_equal(result.native, self.image)

    def test_failure_is_recorded(self):
        with patch.object(methods.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'bad input')):
            result = self.method.run(self.image)
        self.assertIsNone(result.native)
        self.assertEqual(result.error, 'bad input')

    def test_timeout_is_recorded(self):
        with patch.object(methods.subprocess, 'run', side_effect=subprocess.TimeoutExpired('snapper', methods.TIMEOUT_S)):
            result = self.method.run(self.image)
        self.assertIsNone(result.native)
        self.assertEqual(result.error, 'timeout')

if __name__ == '__main__':
    unittest.main()
