"""Streamlit UI: streamlit run app.py"""
import io,json,csv,hashlib
from dataclasses import asdict
from random import Random
import streamlit as st
import pandas as pd
from engine import Team,Rules,Tournament,NoLegalDraw
from editor import draw_editor

st.set_page_config(page_title='DrawLab — Tournament Draw Analyzer',layout='wide')
st.title('DrawLab · Swiss & Knockout Draw Optimizer')
st.caption('Compare actual draws vs legal random baseline, best and worst candidates, and individual team advance probabilities.')

with st.sidebar:
    st.header('Tournament setup')
    fmt=st.selectbox('Tournament format',['swiss','knockout'])
    choices=[4,6,8,10,12,14,16,18,20,24,32] if fmt=='swiss' else [2,4,8,16,32]
    n=st.selectbox('Starting teams',choices,index=choices.index(16))
    wins=st.number_input('Wins to qualify (Swiss)',1,8,3,disabled=fmt!='swiss')
    losses=st.number_input('Losses to eliminate (Swiss)',1,8,3,disabled=fmt!='swiss')
    same=st.selectbox('Same-region avoidance',['off','first','always'],index=1)
    rematch=st.checkbox('Avoid past opponents',value=True)
    grouping=st.checkbox('Pair within the same W-L record',value=True,disabled=fmt!='swiss')
    seed_pairs=st.text_input('Opening seed pairs (optional)','',help='Example: 1-4,2-3. Leave blank for unrestricted round 1.')
    bo1=st.selectbox('Normal Swiss match',['BO1','BO3','BO5'],index=0)
    decider=st.selectbox('Qualification/elimination match',['BO1','BO3','BO5'],index=1)
    knockout_bo=st.selectbox('Knockout match',['BO1','BO3','BO5'],index=2)
    scale=st.number_input('Elo scale',min_value=50.,max_value=2000.,value=400.)
    st.header('Analysis controls')
    samples=st.number_input('Simulations per candidate',100,50000,500,step=100)
    baseline_samples=st.number_input('Random baseline simulations',100,100000,3000,step=500)
    cap=st.number_input('Enumeration cap',10,20000,2000,step=100)
    sampled=st.number_input('Fallback: sampled candidate draws',10,1000,100,step=10)
    random_seed=st.number_input('Random seed',1,2147483647,42)
    st.header('Live draw preview')
    live_preview=st.checkbox('Automatically analyze after each legal drag',value=True)
    preview_samples=st.number_input('Preview simulations per draw',min_value=50,max_value=5000,value=200,step=50)
    preview_baseline=st.number_input('Preview baseline simulations',min_value=100,max_value=10000,value=600,step=100)
    st.caption('Preview is approximate. Full analysis is still available below.')

st.markdown('### 1. Teams and regions')
file=st.file_uploader('Upload a tournament JSON (teams, rules, history, actual_draw)',type='json')
if file is not None:
    cfg=json.load(file);st.session_state['upload_cfg']=cfg
cfg=st.session_state.get('upload_cfg')
rows=cfg['teams'] if cfg else [{'id':f'T{i+1:02d}','region':f'R{i%4+1}','elo':1500.,'seed':i//4+1} for i in range(n)]
if len(rows)!=n:st.info(f'Uploaded {len(rows)} teams; selecting {n} teams will slice or pad the table.')
rows=(rows+[{'id':f'T{i+1:02d}','region':'R1','elo':1500.,'seed':0} for i in range(len(rows),n)])[:n]
df=st.data_editor(pd.DataFrame(rows),num_rows='fixed',use_container_width=True,hide_index=True,key=f'teams_{n}')
st.markdown('### 2. Past results / current state')
st.caption('Enter complete chronological rounds as JSON. Each completed round must include every active team exactly once. Empty list starts from 0-0.')
history_default=json.dumps(cfg.get('history',[]) if cfg else [],indent=2,ensure_ascii=False)
history_txt=st.text_area('History events',history_default,height=135)
st.markdown('### 3. Real/observed draw (optional)')
actual_default=json.dumps(cfg.get('actual_draw',[]) if cfg else [],indent=2,ensure_ascii=False)
actual_txt=st.text_area('Pairs [ [team_id, team_id], ... ]',actual_default,height=100)

st.markdown('### 4. Drag-and-drop draw editor')
st.caption('Drag a team onto another team to swap their positions, or click two teams. Invalid swaps are blocked. This works from any round based on the entered history.')
editor_state = None
try:
    def number_bo(x): return int(x[2:])
    seed_spec = [tuple(map(int,p.strip().split('-'))) for p in seed_pairs.split(',')] if seed_pairs.strip() else []
    live_rules=Rules(format=fmt,wins_to_advance=int(wins),losses_to_eliminate=int(losses),same_region=same,
        avoid_rematches=rematch,swiss_same_record=grouping,opening_seed_pairs=tuple(seed_spec),
        bo1=number_bo(bo1),bo_decider=number_bo(decider),bo_knockout=number_bo(knockout_bo),rating_scale=scale)
    live_teams=[Team(str(x['id']),str(x['region']),float(x['elo']),int(x.get('seed',0))) for x in df.to_dict('records')]
    live_t=Tournament(live_teams,live_rules)
    live_s=live_t.from_history(json.loads(history_txt))
    if not live_t.completed(live_s):
        specified=json.loads(actual_txt)
        if specified:
            live_pairs=tuple((live_t.ids[a],live_t.ids[b]) for a,b in specified)
            if not live_t.is_legal(live_s,live_pairs):
                st.warning('The supplied actual draw is invalid; the editor starts with a random legal draw.')
                live_pairs=live_t.random_draw(live_s,Random(int(random_seed)))
        else:live_pairs=live_t.random_draw(live_s,Random(int(random_seed)))
        editor_state=draw_editor(live_t,live_s,live_pairs,key='drag_editor')
        if editor_state and editor_state.get('pairs'):
            proposed=tuple((live_t.ids[a],live_t.ids[b]) for a,b in editor_state['pairs'])
            if live_t.is_legal(live_s,proposed):
                st.success('Edited pairing is legal — ready to analyze.')
            else:
                st.error('Edited pairing is illegal; no analysis will be run on it.')
        else:
            st.info('Editor is showing the current pairing. Drag a team to change opponents.')
    else:st.info('Tournament is complete: no remaining draw.')
except Exception as editor_error:
    st.warning(f'Draw editor cannot be initialized: {editor_error}')

# Live calculations use the same Tournament engine as the full analysis.
# Cache by normalized state + the *unordered* pair set, not the UI change timestamp.
# The baseline is shared by every edited draw in an unchanged tournament state.
if 'preview_cache' not in st.session_state:
    st.session_state['preview_cache'] = {}

def _preview_cached(key, compute):
    cache = st.session_state['preview_cache']
    if key not in cache:
        cache[key] = compute()
        while len(cache) > 100:
            cache.pop(next(iter(cache)))
    return cache[key], key in cache

if live_preview and editor_state and editor_state.get('pairs'):
    try:
        normalized = tuple(sorted(tuple(sorted((live_t.ids[a], live_t.ids[b]))) for a,b in editor_state['pairs']))
        if not live_t.is_legal(live_s, normalized):
            st.error('Live preview disabled: illegal draw.')
        else:
            context = {'teams':[asdict(t) for t in live_t.teams], 'rules':asdict(live_t.rules),
                       'state':{'wins':live_s.wins,'losses':live_s.losses,'met':sorted(live_s.met),
                                'round':live_s.round,'alive':live_s.alive}}
            context_key=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
            baseline_key=('baseline',context_key,int(preview_baseline),int(random_seed))
            report_key=('draw',context_key,normalized,int(preview_samples),int(random_seed))
            preview_base,_=_preview_cached(baseline_key,lambda:live_t.baseline(live_s,int(preview_baseline),int(random_seed)+1))
            preview_report,_=_preview_cached(report_key,lambda:live_t.analyze(live_s,[normalized],int(preview_samples),int(random_seed))[0])
            st.markdown('### Live impact — edited draw vs random baseline')
            st.caption('Automatically refreshed on valid drag. Cached results are reused when you return to an earlier pairing. '
                       'Estimates are preliminary; use full analysis for higher precision.')
            live_rows=[]
            for region in live_t.regions:
                observed=preview_report.region_expected[region]
                random_mean=preview_base['region_expected'][region]
                live_rows.append({'Region':region,'Edited expected':observed,'Random expected':random_mean,
                                  'Impact':observed-random_mean,
                                  'MC SE (difference, approx)':(preview_report.region_se[region]**2+preview_base['region_se'][region]**2)**0.5})
            st.dataframe(pd.DataFrame(live_rows).round(4),hide_index=True,use_container_width=True)
            st.bar_chart(pd.DataFrame(live_rows).set_index('Region')[['Impact']],horizontal=True)
            with st.expander('Team advancement probabilities for edited draw'):
                st.dataframe(pd.DataFrame([{'Team':t.id,'Region':t.region,
                    'Edited':preview_report.team_advance[t.id],
                    'Random':preview_base['team_advance'][t.id],
                    'Impact':preview_report.team_advance[t.id]-preview_base['team_advance'][t.id]}
                    for t in live_t.teams]).round(4),hide_index=True,use_container_width=True)
            if preview_report.unfinished or preview_base['failed']:
                st.warning('Some simulation paths had no legal next draw. Estimates condition on completed runs; inspect the rule fallback.')
    except Exception as exc:
        st.warning(f'Live preview unavailable: {type(exc).__name__}: {exc}')

analyze_edited = st.button('Analyze edited draw',type='primary',disabled=not bool(editor_state and editor_state.get('pairs')))
analyze_all = st.button('Analyze all legal draws')
if analyze_all or analyze_edited:

    try:
        def number_bo(x):return int(x[2:])
        pairs=[]
        if seed_pairs.strip():
            pairs=[tuple(map(int,p.strip().split('-'))) for p in seed_pairs.split(',')]
        rule=Rules(format=fmt,wins_to_advance=int(wins),losses_to_eliminate=int(losses),same_region=same,
                   avoid_rematches=rematch,swiss_same_record=grouping,opening_seed_pairs=tuple(pairs),
                   bo1=number_bo(bo1),bo_decider=number_bo(decider),bo_knockout=number_bo(knockout_bo),rating_scale=scale)
        teams=[Team(str(x['id']),str(x['region']),float(x['elo']),int(x.get('seed',0))) for x in df.to_dict('records')]
        t=Tournament(teams,rule);s=t.from_history(json.loads(history_txt));actual=editor_state['pairs'] if analyze_edited else json.loads(actual_txt)
        if t.completed(s):raise ValueError('Tournament is already finished.')
        try:draws=t.enumerate_draws(s,limit=int(cap));exhaustive=True
        except OverflowError:
            rng=Random(int(random_seed));draws=[];seen=set();exhaustive=False
            for _ in range(int(sampled)*30):
                d=t.random_draw(s,rng);k=tuple(sorted(tuple(sorted(p)) for p in d))
                if k not in seen:seen.add(k);draws.append(d)
                if len(draws)>=sampled:break
        with st.spinner('Running future tournament simulations...'):
            baseline=t.baseline(s,int(baseline_samples),int(random_seed)+1)
            reports=t.analyze(s,[tuple((t.ids[a],t.ids[b]) for a,b in actual)] if analyze_edited else draws,int(samples),int(random_seed))
            real=None
            if actual:
                d=tuple((t.ids[a],t.ids[b]) for a,b in actual)
                real=t.analyze(s,[d],int(samples),int(random_seed))[0]
        st.session_state['last_results']=(t,s,[reports[0].matches] if analyze_edited else draws,reports,baseline,real,exhaustive and not analyze_edited)
    except Exception as e:st.error(f'{type(e).__name__}: {e}')

if 'last_results' in st.session_state:
    t,s,draws,reports,baseline,real,exhaustive=st.session_state['last_results']
    st.success(f'Current round {s.round} | {len(t.active(s))} active teams | {len(draws)} evaluated draws | '+('Single edited draw (not a global optimum)' if len(reports)==1 and not exhaustive else ('Exhaustive candidate coverage' if exhaustive else 'Sampled candidates: best/worst are approximate')))
    res=[]
    for r in t.regions:
        ranked=t.rank(reports,r);b=baseline['region_expected'][r]
        row={'Region':r,'Random baseline':b,'Best candidate':ranked[0].region_expected[r] if exhaustive or len(reports)>1 else None,
             'Worst candidate':ranked[-1].region_expected[r] if exhaustive or len(reports)>1 else None, 'Best minus random':ranked[0].region_expected[r]-b if exhaustive or len(reports)>1 else None}
        if real: row.update({'Actual':real.region_expected[r],'Actual minus random':real.region_expected[r]-b,'Actual SE':real.region_se[r]})
        res.append(row)
    st.markdown('### Region outcomes'); st.dataframe(pd.DataFrame(res).round(4),hide_index=True,use_container_width=True)
    focal=st.selectbox('Inspect region',t.regions)
    ranked=t.rank(reports,focal)
    st.markdown('### Best, worst, and observed draws')
    a,b,c=st.columns(3)
    for col,label,rep in ((a,'Best',ranked[0]),(b,'Worst',ranked[-1]),(c,'Edited / actual',real)):
        with col:
            st.subheader(label)
            if rep:
                st.metric('Expected qualifying teams',f'{rep.region_expected[focal]:.4f}')
                st.code('\n'.join(f'{x} vs {y}' for x,y in t.draw_names(rep.matches)))
                st.caption(f'SE ± {rep.region_se[focal]:.4f}; {rep.simulations} feasible simulations; {rep.unfinished} stuck')
            else:st.caption('No actual draw provided')
    st.markdown('### Candidate ranking')
    rankdata=[]
    for pos,rep in enumerate(ranked,1):
        rankdata.append({'rank':pos,'expected':rep.region_expected[focal],'SE':rep.region_se[focal],'matches':'; '.join(a+'-'+b for a,b in t.draw_names(rep.matches))})
    st.dataframe(pd.DataFrame(rankdata).round(4),hide_index=True,use_container_width=True)
    st.download_button('Download full candidate CSV',pd.DataFrame(rankdata).to_csv(index=False).encode(),'drawlab_rankings.csv','text/csv')
    st.markdown('### Team qualifying probabilities')
    st.dataframe(pd.DataFrame([{'team':tt.id,'region':tt.region,'baseline':baseline['team_advance'][tt.id],
       'best':ranked[0].team_advance[tt.id],'worst':ranked[-1].team_advance[tt.id],
       'actual':real.team_advance[tt.id] if real else None} for tt in t.teams]).round(4),hide_index=True,use_container_width=True)
    st.warning('Monte Carlo estimates are not exact. SE describes sampling uncertainty, not Elo-model accuracy. If simulations get stuck, change the matching fallback rules; stuck trajectories are reported rather than quietly repaired.')
