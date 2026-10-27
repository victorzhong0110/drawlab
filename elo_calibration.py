"""Fit a probability temperature/scale from observed matches (not Elo rating re-estimation)."""
from math import log
from dataclasses import dataclass

@dataclass(frozen=True)
class Calibration:
    scale: float
    observed: int
    source: str
    message: str
    logloss: float | None = None


def estimate_scale(cfg, default=400.0, min_games=20):
    """Estimate Elo logistic scale from JSON calibration_matches (or history).

    Match data: a, b, winner, optional weight. `best_of` > 1 is not
    accepted for auto-fit: series outcomes are not individual map outcomes.
    Missing or weak evidence leaves the supplied/default scale intact.
    """
    ratings = {str(t['id']): float(t['elo']) for t in cfg.get('teams', []) if 'elo' in t}
    matches = cfg.get('calibration_matches', cfg.get('history', []))
    valid = []
    for m in matches:
        if not isinstance(m, dict): continue
        a,b,w = (str(m.get(k, '')) for k in ('a','b','winner'))
        if a not in ratings or b not in ratings or a==b or w not in (a,b): continue
        bo=int(m.get('best_of',1))
        if bo!=1: continue
        weight=float(m.get('weight', 1.0))
        if not (0 < weight <= 100): continue
        valid.append((ratings[a]-ratings[b], 1.0 if w==a else 0.0, weight))
    source = 'calibration_matches' if 'calibration_matches' in cfg else 'history'
    if len(valid)<min_games:
        return Calibration(default,len(valid),source,f'Insufficient BO1/map-level results ({len(valid)}/{min_games}); using default scale.')
    if max(abs(d) for d,_,_ in valid)<25:
        return Calibration(default,len(valid),source,'Not enough rating spread to identify a reliable scale; using default scale.')
    def loss(s):
        out=0.;n=0.
        for diff,y,w in valid:
            p=1/(1+10**(-diff/s));p=max(1e-12,min(1-1e-12,p))
            out-=w*(y*log(p)+(1-y)*log(1-p));n+=w
        return out/n
    # Properly documented shrinkage to the conventional Elo 400 prior.
    # This keeps small samples from driving scale to an extreme.
    def objective(s):
        return len(valid)*loss(s)+10*(log(s/400.0))**2
    lo,hi=100.,1200.
    for _ in range(90):
        x=lo+(hi-lo)/3;y=hi-(hi-lo)/3
        if objective(x)<objective(y):hi=y
        else:lo=x
    scale=round((lo+hi)/2,2)
    return Calibration(scale,len(valid),source,'Estimated from recorded BO1/map results; not a guarantee of calibrated probabilities.',round(loss(scale),4))
