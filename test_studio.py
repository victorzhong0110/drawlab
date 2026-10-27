import unittest
from random import Random
from engine import Team,Rules,Tournament
from studio import complete_draws,random_completion,partial_valid
class StudioTests(unittest.TestCase):
 def setUp(self):
  self.t=Tournament([Team('A','A'),Team('B','B'),Team('C','C'),Team('D','D')],Rules(same_region='off'))
  self.s=self.t.initial()
 def test_empty_and_partial_counts(self):
  self.assertEqual(len(complete_draws(self.t,self.s)),3)
  self.assertEqual(len(complete_draws(self.t,self.s,((0,1),))),1)
 def test_partial_conflict(self):
  self.assertFalse(partial_valid(self.t,self.s,((0,1),(0,2))))
  with self.assertRaises(ValueError):complete_draws(self.t,self.s,((0,1),(0,2)))
 def test_uniform_completion(self):
  rng=Random(11)
  for _ in range(25):
   d=random_completion(self.t,self.s,((0,1),),rng)
   self.assertTrue(self.t.is_legal(self.s,d))
   self.assertIn((0,1),d)
if __name__=='__main__':unittest.main()
