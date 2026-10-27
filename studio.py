"""Partial-draw logic and Streamlit bracket studio bridge."""
from functools import lru_cache
from random import Random
from pathlib import Path
from engine import NoLegalDraw


def _groups(t,s):
    return [tuple(g) for g in t.groups(s)]

def partial_valid(t,s,locked):
    active=set(t.active(s)); seen=set()
    group={i:g for g,pool in enumerate(_groups(t,s)) for i in pool}
    for a,b in locked:
        if a not in active or b not in active or a in seen or b in seen:return False
        if group[a]!=group[b] or not t.eligible(s,a,b):return False
        seen.update((a,b))
    return True

def complete_draws(t,s,locked=(),limit=3000):
    """Exact completions until cap; throws OverflowError rather than silently truncating."""
    locked=tuple(locked)
    if not partial_valid(t,s,locked):raise ValueError('Illegal locked pairing')
    left=set(t.active(s))-set(i for p in locked for i in p)
    pools=[]
    for group in _groups(t,s):
        remaining=tuple(sorted(i for i in group if i in left))
        def rec(rest):
            if not rest:return [()]
            a=rest[0];out=[]
            for j in range(1,len(rest)):
                b=rest[j]
                if not t.eligible(s,a,b):continue
                for tail in rec(rest[1:j]+rest[j+1:]):
                    out.append(((a,b),)+tail)
                    if len(out)>limit:raise OverflowError('Too many completions')
            return out
        pools.append(rec(remaining))
    out=[locked]
    for pool in pools:
        out=[prefix+tail for prefix in out for tail in pool]
        if len(out)>limit:raise OverflowError('Too many completions')
    if not out:raise NoLegalDraw('No completion exists')
    return out

def random_completion(t,s,locked,rng):
    if not partial_valid(t,s,locked):raise ValueError('Illegal locked pairing')
    used=set(i for p in locked for i in p);out=list(locked)
    for group in _groups(t,s):
        remaining=tuple(sorted(i for i in group if i not in used))
        @lru_cache(None)
        def count(rest):
            if not rest:return 1
            a=rest[0]
            return sum(count(rest[1:j]+rest[j+1:]) for j in range(1,len(rest)) if t.eligible(s,a,rest[j]))
        if not count(remaining):raise NoLegalDraw('No completion for locked pairs')
        while remaining:
            a=remaining[0]; choices=[];weights=[]
            for j in range(1,len(remaining)):
                b=remaining[j]
                if t.eligible(s,a,b):
                    rest=remaining[1:j]+remaining[j+1:];w=count(rest)
                    if w:choices.append((b,rest));weights.append(w)
            k=rng.randrange(sum(weights))
            for (b,rest),weight in zip(choices,weights):
                if k<weight:
                    out.append((a,b));remaining=rest;break
                k-=weight
    return tuple(out)

def studio(t,s,initial,key='drawlab_swiss_studio',lang='中文'):
    active=t.active(s)
    groups={}
    for g in t.groups(s):
        for i in g:groups[t.teams[i].id]=(f'{s.wins[i]}-{s.losses[i]}' if t.rules.format=='swiss' else 'Bracket')
    allowed={}
    for a in active:
        for b in active:
            if a<b and groups[t.teams[a].id]==groups[t.teams[b].id] and t.eligible(s,a,b):
                allowed['||'.join(sorted((t.teams[a].id,t.teams[b].id)))]=True
    teams=[dict(id=t.teams[i].id,region=t.teams[i].region,elo=t.teams[i].elo,seed=t.teams[i].seed,group=groups[t.teams[i].id],wins=s.wins[i],losses=s.losses[i]) for i in active]
    import streamlit.components.v1 as components
    component=components.declare_component('drawlab_swiss_studio',path=str(Path(__file__).parent/'studio_frontend'))
    return component(teams=teams,allowed=allowed,round=s.round,format=t.rules.format,language=lang,
                     startingPairs=[[t.teams[a].id,t.teams[b].id] for a,b in initial],key=key,default=None)
