import unittest,random
from engine import Team,Rules,Tournament,NoLegalDraw,elo_probability,series_probability
class TestEngine(unittest.TestCase):
 def setup(self,n=8,**kwargs):
  return Tournament([Team(str(i),str(i%4),1500+10*i) for i in range(n)],Rules(wins_to_advance=2,losses_to_eliminate=2,**kwargs))
 def test_probs(self):
  self.assertAlmostEqual(elo_probability(1500,1500),.5)
  self.assertAlmostEqual(series_probability(.5,3),.5)
  self.assertAlmostEqual(series_probability(.75,3),.84375)
 def test_all_matching(self):
  t=self.setup(8,same_region='off');self.assertEqual(len(t.enumerate_draws(t.initial())),105)
 def test_uniform_matching(self):
  t=self.setup(4,same_region='off');s=t.initial();rng=random.Random(5)
  from collections import Counter
  c=Counter(tuple(sorted(tuple(sorted(p)) for p in t.random_draw(s,rng))) for _ in range(9000))
  self.assertEqual(len(c),3)
  self.assertTrue(all(2700<v<3300 for v in c.values()))
 def test_simple_swiss(self):
  t=self.setup(8,same_region='off');s=t.initial()
  base=t.baseline(s,40)
  self.assertAlmostEqual(sum(base['region_expected'].values()),4.)
 def test_rematch_avoidance(self):
  t=self.setup(4,same_region='off');s=t.initial();s=t.advance(s,((0,1),(2,3)),winners={(0,1):0,(2,3):2})
  self.assertTrue(all((0,1) not in [tuple(sorted(p)) for p in d] for d in t.enumerate_draws(s)))
 def test_history(self):
  t=self.setup(4,same_region='off');s=t.from_history([{'a':'0','b':'1','winner':'0','round':1},{'a':'2','b':'3','winner':'2','round':1}]);self.assertEqual(s.round,2)
 def test_knockout(self):
  t=Tournament([Team(str(i),'R',1550) for i in range(8)],Rules(format='knockout',same_region='off'))
  q=t.simulate(t.initial(),rng=random.Random(123));self.assertEqual(len(t.qualified(q)),1)
if __name__=='__main__':unittest.main()
