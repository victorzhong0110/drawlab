"""DrawLab: reproducible Swiss and single-elimination draw simulator (stdlib only)."""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from functools import lru_cache
from collections import defaultdict
from itertools import product
from math import comb, sqrt
from random import Random
from typing import Optional

@dataclass(frozen=True)
class Team:
    id: str
    region: str
    elo: float = 1500.0
    seed: int = 0

@dataclass(frozen=True)
class Rules:
    format: str = 'swiss'              # swiss / knockout
    wins_to_advance: int = 3
    losses_to_eliminate: int = 3
    same_region: str = 'first'        # off / first / always
    avoid_rematches: bool = True
    swiss_same_record: bool = True
    # Each tier is a pair of lists of seed numbers eligible to meet in round 1.
    opening_seed_pairs: tuple = ()   # ((1,4),(2,3)); empty = unrestricted
    bo1: int = 1
    bo_decider: int = 3
    bo_knockout: int = 5
    rating_scale: float = 400.0
    # All complete legal pairings are sampled uniformly. Other physical draw
    # procedures can have different distributions.

@dataclass(frozen=True)
class State:
    wins: tuple[int,...]
    losses: tuple[int,...]
    met: frozenset[tuple[int,int]] = frozenset()
    round: int = 1
    alive: tuple[int,...] = ()  # knockout only

@dataclass
class Report:
    matches: tuple[tuple[int,int],...]
    simulations: int
    region_expected: dict[str,float]
    team_advance: dict[str,float]
    region_se: dict[str,float]
    unfinished: int = 0

class NoLegalDraw(ValueError):
    pass

def edge(a,b):
    return (min(a,b), max(a,b))

def elo_probability(ra,rb,scale=400.):
    return 1.0/(1.0+10**((rb-ra)/scale))

def series_probability(p, best_of):
    if best_of%2!=1 or best_of<1: raise ValueError('Best-of must be positive odd integer')
    n=best_of; need=n//2+1
    return sum(comb(n,k)*p**k*(1-p)**(n-k) for k in range(need,n+1))

class Tournament:
    def __init__(self, teams: list[Team], rules: Rules):
        if len(teams)<2 or len({t.id for t in teams})!=len(teams): raise ValueError('Need >=2 teams with unique IDs')
        if rules.format not in ('swiss','knockout'): raise ValueError('format: swiss / knockout')
        if rules.same_region not in ('off','first','always'): raise ValueError('same_region: off / first / always')
        if rules.wins_to_advance<1 or rules.losses_to_eliminate<1: raise ValueError('Positive thresholds required')
        if rules.format=='swiss' and len(teams)%2: raise ValueError('Swiss needs an even number of teams (no bye policy configured)')
        if rules.format=='knockout' and len(teams)&(len(teams)-1): raise ValueError('Knockout currently supports 2,4,8,16,... teams only (no byes)')
        self.teams=teams;self.rules=rules;self.n=len(teams);self.ids={t.id:i for i,t in enumerate(teams)}
        self.regions=tuple(sorted({t.region for t in teams}))
        self._p=[[series_probability(elo_probability(a.elo,b.elo,rules.rating_scale),1) for b in teams] for a in teams]

    def initial(self):
        return State((0,)*self.n,(0,)*self.n,frozenset(),1,tuple(range(self.n)))

    def from_history(self, events):
        """Sequential games: list of {'a','b','winner'} (chronological order).
        Matches in a round should be fed before moving to the next round.
        Pass 'round' on each event; validation catches repeated participants.
        """
        s=self.initial(); grouped=defaultdict(list)
        for e in events: grouped[int(e.get('round',1))].append(e)
        for r in sorted(grouped):
            if r!=s.round: raise ValueError('History rounds must be contiguous starting at round 1')
            pairs=[]; winners={}
            for e in grouped[r]:
                a=self.ids[e['a']];b=self.ids[e['b']];win=self.ids[e['winner']]
                if win not in (a,b): raise ValueError('Winner must participate')
                pairs.append((a,b));winners[edge(a,b)]=win
            expected=set(self.active(s))
            participants=[x for a,b in pairs for x in (a,b)]
            if len(participants)!=len(set(participants)) or set(participants)!=expected:
                raise ValueError(f'Round {r} must include each active team exactly once')
            if not self.is_legal(s,tuple(pairs)): raise ValueError(f'Illegal round {r} pairing')
            s=self.advance(s,tuple(pairs),winners=winners)
        return s

    def active(self,s):
        if self.rules.format=='knockout':return s.alive
        w,l=self.rules.wins_to_advance,self.rules.losses_to_eliminate
        return tuple(i for i in range(self.n) if s.wins[i]<w and s.losses[i]<l)

    def groups(self,s):
        active=self.active(s)
        if self.rules.format=='knockout': return (active,)
        if s.round==1 and self.rules.opening_seed_pairs:
            # special first round seed constraints are enforced pairwise, not group split
            return (active,)
        if not self.rules.swiss_same_record:return (active,)
        d=defaultdict(list)
        for i in active:d[(s.wins[i],s.losses[i])].append(i)
        return tuple(tuple(sorted(d[k])) for k in sorted(d))

    def eligible(self,s,a,b):
        if a==b:return False
        if self.rules.avoid_rematches and edge(a,b) in s.met:return False
        if self.rules.same_region=='always' or (self.rules.same_region=='first' and s.round==1):
            if self.teams[a].region==self.teams[b].region:return False
        if self.rules.format=='swiss' and s.round==1 and self.rules.opening_seed_pairs:
            sa,sb=self.teams[a].seed,self.teams[b].seed
            if not any((sa==x and sb==y) or (sa==y and sb==x) for x,y in self.rules.opening_seed_pairs):return False
        return True

    def _pool_matches(self,s,pool,limit=None):
        """Enumerate all perfect matchings in a pool; limit is a hard safety bound."""
        pool=tuple(sorted(pool))
        if len(pool)%2:raise NoLegalDraw('Odd team count in a Swiss record group')
        @lru_cache(None)
        def rec(remaining):
            if not remaining:return ((),)
            a=remaining[0];out=[]
            for idx in range(1,len(remaining)):
                b=remaining[idx]
                if not self.eligible(s,a,b):continue
                rest=remaining[1:idx]+remaining[idx+1:]
                for tail in rec(rest):
                    out.append(((a,b),)+tail)
                    if limit and len(out)>limit: raise OverflowError('Too many legal draws: increase cap or use random sampling')
            return tuple(out)
        return rec(pool)

    def enumerate_draws(self,s,limit=5000):
        groups=self.groups(s)
        batches=[self._pool_matches(s,g,limit=limit) for g in groups]
        if any(not x for x in batches):raise NoLegalDraw('No complete legal matching; specify an official fallback rule')
        out=[]
        for chunk in product(*batches):
            out.append(tuple(pair for group in chunk for pair in group))
            if len(out)>limit:raise OverflowError(f'More than {limit} draws')
        return out

    def random_draw(self,s,rng):
        # Exact uniform perfect-matching sampler using continuation counts,
        # without enumerating all combinations into memory.
        out=[]
        for group in self.groups(s):
            group=tuple(sorted(group))
            if len(group)%2:raise NoLegalDraw('Odd group; no byes/cross-record policy configured')
            @lru_cache(None)
            def count(rest):
                if not rest:return 1
                a=rest[0];val=0
                for k in range(1,len(rest)):
                    if self.eligible(s,a,rest[k]):val+=count(rest[1:k]+rest[k+1:])
                return val
            if count(group)==0:raise NoLegalDraw('No legal matching')
            remaining=group
            while remaining:
                a=remaining[0];choices=[];weights=[]
                for k in range(1,len(remaining)):
                    b=remaining[k]
                    if not self.eligible(s,a,b):continue
                    rest=remaining[1:k]+remaining[k+1:]
                    w=count(rest)
                    if w:choices.append((b,rest));weights.append(w)
                total=sum(weights);q=rng.randrange(total)
                for (b,rest),w in zip(choices,weights):
                    if q<w:out.append((a,b));remaining=rest;break
                    q-=w
        return tuple(out)

    def is_legal(self,s,matches):
        participants=[i for p in matches for i in p]
        if sorted(participants)!=sorted(self.active(s)):return False
        if any(not self.eligible(s,a,b) for a,b in matches):return False
        if self.rules.format=='swiss' and self.rules.swiss_same_record and not (s.round==1 and self.rules.opening_seed_pairs):
            if any((s.wins[a],s.losses[a])!=(s.wins[b],s.losses[b]) for a,b in matches):return False
        return True

    def best_of(self,s,a,b):
        if self.rules.format=='knockout':return self.rules.bo_knockout
        dec=(s.wins[a]==self.rules.wins_to_advance-1 or s.losses[a]==self.rules.losses_to_eliminate-1 or s.wins[b]==self.rules.wins_to_advance-1 or s.losses[b]==self.rules.losses_to_eliminate-1)
        return self.rules.bo_decider if dec else self.rules.bo1

    def advance(self,s,matches,rng=None,winners=None):
        if not self.is_legal(s,matches):raise ValueError('Illegal draw / missing participants')
        wins=list(s.wins);losses=list(s.losses);met=set(s.met);alive=[]
        for a,b in matches:
            if winners is not None: win=winners[edge(a,b)]
            else:
                if rng is None:raise ValueError('Supply rng or winners')
                p=elo_probability(self.teams[a].elo,self.teams[b].elo,self.rules.rating_scale)
                p=series_probability(p,self.best_of(s,a,b))
                win=a if rng.random()<p else b
            loser=b if win==a else a
            wins[win]+=1;losses[loser]+=1;met.add(edge(a,b))
            if self.rules.format=='knockout':alive.append(win)
        if self.rules.format=='knockout':
            return State(tuple(wins),tuple(losses),frozenset(met),s.round+1,tuple(sorted(alive)))
        return State(tuple(wins),tuple(losses),frozenset(met),s.round+1,s.alive)

    def completed(self,s):
        if self.rules.format=='knockout':return len(s.alive)==1
        return not self.active(s)

    def qualified(self,s):
        if self.rules.format=='knockout':return set(s.alive) if self.completed(s) else set()
        return {i for i in range(self.n) if s.wins[i]>=self.rules.wins_to_advance}

    def simulate(self,start,first=None,rng=None):
        rng=rng or Random()
        s=start
        if self.completed(s):return s
        while not self.completed(s):
            m=first if first is not None else self.random_draw(s,rng)
            s=self.advance(s,m,rng=rng)
            first=None
            if s.round>self.n*3+5:raise RuntimeError('Unfinished after excessive rounds')
        return s

    def analyze(self,s,draws=None,samples=1000,seed=42,cap=5000):
        """Compare legal first decisions; common random seeds help reduce noise.

        Reporting uses expectations over full tournaments, with Monte Carlo SE.
        """
        if samples<1:raise ValueError('samples must be >=1')
        if draws is None:draws=self.enumerate_draws(s,limit=cap)
        regions=self.regions; reports=[]
        for draw_index,draw in enumerate(draws):
            if not self.is_legal(s,draw):raise ValueError('Illegal candidate draw')
            sums={r:0. for r in regions}; sums2={r:0. for r in regions}
            team_counts=[0]*self.n;failure=0
            for k in range(samples):
                rng=Random(seed+1000003*k) # identical stream by simulation number for each draw
                try: final=self.simulate(s,first=draw,rng=rng)
                except NoLegalDraw:failure+=1;continue
                q=self.qualified(final);counts=defaultdict(int)
                for i in q:counts[self.teams[i].region]+=1;team_counts[i]+=1
                for r in regions:
                    x=counts[r];sums[r]+=x;sums2[r]+=x*x
            valid=samples-failure
            if valid==0:raise NoLegalDraw('Every simulation got stuck. Official matching relaxation policy required')
            ex={r:sums[r]/valid for r in regions}
            se={r:sqrt(max(0.,sums2[r]/valid-ex[r]**2)/valid) for r in regions}
            reports.append(Report(tuple(draw),valid,ex,{t.id:team_counts[i]/valid for i,t in enumerate(self.teams)},se,failure))
        return reports

    def baseline(self,s,samples=5000,seed=2026):
        sums=dict.fromkeys(self.regions,0.);sum2=dict.fromkeys(self.regions,0.)
        team_counts=[0]*self.n;failure=0
        for k in range(samples):
            rng=Random(seed+7919*k)
            try:final=self.simulate(s,rng=rng)
            except NoLegalDraw:failure+=1;continue
            q=self.qualified(final);counts=defaultdict(int)
            for i in q:counts[self.teams[i].region]+=1;team_counts[i]+=1
            for r in self.regions:
                x=counts[r];sums[r]+=x;sum2[r]+=x*x
        n=samples-failure
        if n==0:raise NoLegalDraw('All baseline simulations infeasible')
        avg={r:sums[r]/n for r in self.regions}
        return {'region_expected':avg,'region_se':{r:sqrt(max(0.,sum2[r]/n-avg[r]**2)/n) for r in self.regions},'team_advance':{t.id:team_counts[i]/n for i,t in enumerate(self.teams)},'valid':n,'failed':failure}

    def rank(self,reps,region):
        return sorted(reps,key=lambda x:x.region_expected[region],reverse=True)

    def draw_names(self,m):return [(self.teams[a].id,self.teams[b].id) for a,b in m]
