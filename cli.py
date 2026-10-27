import argparse,csv,json,sys
from pathlib import Path
from dataclasses import fields
from engine import Team,Rules,Tournament

def load(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    teams=[Team(**t) for t in data['teams']]
    rulefields={f.name for f in fields(Rules)}
    rr={k:v for k,v in data.get('rules',{}).items() if k in rulefields}
    if 'opening_seed_pairs' in rr:rr['opening_seed_pairs']=tuple(tuple(p) for p in rr['opening_seed_pairs'])
    t=Tournament(teams,Rules(**rr));s=t.from_history(data.get('history',[]))
    return t,s,data

def main():
    ap=argparse.ArgumentParser(description='DrawLab Swiss/knockout draw analyzer')
    ap.add_argument('config');ap.add_argument('--samples',type=int,default=500)
    ap.add_argument('--baseline',type=int,default=3000);ap.add_argument('--max-draws',type=int,default=5000)
    ap.add_argument('--sample-draws',type=int,default=100,help='On enumeration overflow, sample this many distinct legal draws')
    ap.add_argument('--seed',type=int,default=42);ap.add_argument('--csv',default='')
    args=ap.parse_args();t,s,d=load(args.config)
    from random import Random
    try:draws=t.enumerate_draws(s,args.max_draws);exhaustive=True
    except OverflowError:
        rng=Random(args.seed);seen=set();draws=[];exhaustive=False
        for _ in range(args.sample_draws*20):
            m=t.random_draw(s,rng);key=tuple(sorted(tuple(sorted(p)) for p in m))
            if key not in seen:seen.add(key);draws.append(m)
            if len(draws)>=args.sample_draws:break
    print('Candidates:',len(draws),'Exhaustive:',exhaustive,file=sys.stderr)
    base=t.baseline(s,args.baseline,args.seed+1)
    reports=t.analyze(s,draws,args.samples,args.seed)
    actual=None
    if d.get('actual_draw'):
        actual=tuple((t.ids[a],t.ids[b]) for a,b in d['actual_draw'])
        if not t.is_legal(s,actual):raise ValueError('Actual draw is not legal under current rules')
        actual=t.analyze(s,[actual],args.samples,args.seed)[0]
    result={'config':args.config,'round':s.round,'candidates':len(draws),'exhaustive':exhaustive,'baseline':base,'regions':{}}
    for region in t.regions:
        ranks=t.rank(reports,region)
        def pack(r):return {'expected':r.region_expected[region], 'se':r.region_se[region], 'draw':t.draw_names(r.matches),'team_probabilities':r.team_advance,'failed':r.unfinished}
        result['regions'][region]={'best':pack(ranks[0]),'worst':pack(ranks[-1]),'mean_of_evaluated_draws':sum(x.region_expected[region] for x in reports)/len(reports),'actual':pack(actual) if actual else None,'actual_minus_random':actual.region_expected[region]-base['region_expected'][region] if actual else None}
    if args.csv:
        with open(args.csv,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(['draw_id','matches']+list(t.regions))
            for k,r in enumerate(reports):w.writerow([k,'; '.join(a+'-'+b for a,b in t.draw_names(r.matches))]+[r.region_expected[reg] for reg in t.regions])
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
