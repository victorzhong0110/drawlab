import unittest
from elo_calibration import estimate_scale

class CalibrationTests(unittest.TestCase):
    def test_without_matches_fallback(self):
        c=estimate_scale({'teams':[{'id':'A','elo':1800},{'id':'B','elo':1500}], 'history':[]})
        self.assertEqual(c.scale,400)
        self.assertEqual(c.observed,0)
    def test_with_games(self):
        data={'teams':[{'id':'A','elo':1800},{'id':'B','elo':1500}], 'calibration_matches':[]}
        for i in range(40):
            data['calibration_matches'].append({'a':'A','b':'B','winner':'A' if i<30 else 'B','best_of':1})
        c=estimate_scale(data)
        self.assertEqual(c.observed,40)
        self.assertTrue(100<=c.scale<=1200)
    def test_bo3_skipped(self):
        data={'teams':[{'id':'A','elo':1800},{'id':'B','elo':1500}], 'calibration_matches':[{'a':'A','b':'B','winner':'A','best_of':3}]*30}
        self.assertEqual(estimate_scale(data).observed,0)
if __name__=='__main__':unittest.main()
