"""Streamlit UI: streamlit run app.py"""
import io,json,csv,hashlib
from dataclasses import asdict
from random import Random
import streamlit as st
import pandas as pd
from engine import Team,Rules,Tournament,NoLegalDraw
from editor import draw_editor
from elo_calibration import estimate_scale
from localize import tr, options

st.set_page_config(page_title='DrawLab — Tournament Draw Analyzer',layout='wide')
lang=st.sidebar.selectbox('Language / 语言',['中文','English'],key='drawlab_language')
T=lambda text:tr(text,lang)
st.title(T('DrawLab · Swiss & Knockout Draw Optimizer'))
st.caption(T('Compare actual draws vs legal random baseline, best and worst candidates, and individual team advance probabilities.'))
file=st.file_uploader(T('Upload a tournament JSON (teams, rules, history, actual_draw)'),type='json')
if file is not None:
    raw=file.getvalue()
    fingerprint=hashlib.sha256(raw).hexdigest()
    if st.session_state.get('uploaded_json_fingerprint') != fingerprint:
        st.session_state['upload_cfg']=json.loads(raw.decode('utf-8'))
        st.session_state['uploaded_json_fingerprint']=fingerprint
cfg=st.session_state.get('upload_cfg')
loaded_rules=cfg.get('rules',{}) if cfg else {}

with st.sidebar:
    st.header(T('Tournament setup'))
    fmt=st.selectbox(T('Tournament format'),['swiss','knockout'],index=['swiss','knockout'].index(loaded_rules.get('format','swiss')))
    choices=[4,6,8,10,12,14,16,18,20,24,32] if fmt=='swiss' else [2,4,8,16,32]
    n=st.selectbox(T('Starting teams'),choices,index=choices.index(len(cfg['teams']) if cfg and len(cfg['teams']) in choices else 16))
    wins=st.number_input(T('Wins to qualify (Swiss)'),1,8,int(loaded_rules.get('wins_to_advance',3)),disabled=fmt!='swiss')
    losses=st.number_input(T('Losses to eliminate (Swiss)'),1,8,int(loaded_rules.get('losses_to_eliminate',3)),disabled=fmt!='swiss')
    same=st.selectbox(T('Same-region avoidance'),['off','first','always'],index=['off','first','always'].index(loaded_rules.get('same_region','first')),format_func=lambda v:T(v))
    rematch=st.checkbox(T('Avoid past opponents'),value=bool(loaded_rules.get('avoid_rematches',True)))
    grouping=st.checkbox(T('Pair within the same W-L record'),value=bool(loaded_rules.get('swiss_same_record',True)),disabled=fmt!='swiss')
    seed_pairs=st.text_input(T('Opening seed pairs (optional)'),','.join(f'{a}-{b}' for a,b in loaded_rules.get('opening_seed_pairs',[])),help=T('Example: 1-4,2-3. Leave blank for unrestricted round 1.'))
    bo1=st.selectbox(T('Normal Swiss match'),['BO1','BO3','BO5'],index=[1,3,5].index(int(loaded_rules.get('bo1',1))))
    decider=st.selectbox(T('Qualification/elimination match'),['BO1','BO3','BO5'],index=[1,3,5].index(int(loaded_rules.get('bo_decider',3))))
    knockout_bo=st.selectbox(T('Knockout match'),['BO1','BO3','BO5'],index=[1,3,5].index(int(loaded_rules.get('bo_knockout',5))))
    scale=st.number_input(T('Elo scale'),min_value=50.,max_value=2000.,value=float(loaded_rules.get('rating_scale',400.)),key='manual_elo_scale')
    auto_elo=st.checkbox('根据 JSON 自动估计 Elo scale / Auto-fit Elo scale',value=True)
    st.header(T('Analysis controls'))
    samples=st.number_input(T('Simulations per candidate'),100,50000,500,step=100)
    baseline_samples=st.number_input(T('Random baseline simulations'),100,100000,3000,step=500)
    cap=st.number_input(T('Enumeration cap'),10,20000,2000,step=100)
    sampled=st.number_input(T('Fallback: sampled candidate draws'),10,1000,100,step=10)
    random_seed=st.number_input(T('Random seed'),1,2147483647,42)
    st.header(T('Live draw preview'))
    live_preview=st.checkbox(T('Automatically analyze after each legal drag'),value=True)
    preview_samples=st.number_input(T('Preview simulations per draw'),min_value=50,max_value=5000,value=200,step=50)
    preview_baseline=st.number_input(T('Preview baseline simulations'),min_value=100,max_value=10000,value=600,step=100)
    st.caption(T('Preview is approximate. Full analysis is still available below.'))

st.markdown(T('### 1. Teams and regions'))
if auto_elo and cfg:
    fit=estimate_scale(cfg,default=float(cfg.get('rules',{}).get('rating_scale',scale)))
    scale=fit.scale
    st.info(('自动 Elo scale: ' if lang=='中文' else 'Auto Elo scale: ')+f'{scale:.2f} | {fit.observed} BO1/map samples | {fit.message}')
elif auto_elo:
    st.caption('自动 Elo scale：请先上传 JSON；当前使用手动值。' if lang=='中文' else 'Auto Elo scale: upload JSON first; manual scale in use.')
rows=cfg['teams'] if cfg else [{'id':f'T{i+1:02d}',T('region'):f'R{i%4+1}','elo':1500.,'seed':i//4+1} for i in range(n)]
if len(rows)!=n:st.info(f'Uploaded {len(rows)} teams; selecting {n} teams will slice or pad the table.')
rows=(rows+[{'id':f'T{i+1:02d}',T('region'):'R1','elo':1500.,'seed':0} for i in range(len(rows),n)])[:n]
df=st.data_editor(pd.DataFrame(rows),num_rows='fixed',use_container_width=True,hide_index=True,key=f'teams_{n}')
st.markdown(T('### 2. Past results / current state'))
st.caption(T('Enter complete chronological rounds as JSON. Each completed round must include every active team exactly once. Empty list starts from 0-0.'))
history_default=json.dumps(cfg.get('history',[]) if cfg else [],indent=2,ensure_ascii=False)
history_txt=st.text_area(T('History events'),history_default,height=135)
st.markdown(T('### 3. Real/observed draw (optional)'))
actual_default=json.dumps(cfg.get('actual_draw',[]) if cfg else [],indent=2,ensure_ascii=False)
actual_txt=st.text_area(T('Pairs [ [team_id, team_id], ... ]'),actual_default,height=100)

st.markdown(T('### 4. Drag-and-drop draw editor'))
st.caption(T('Drag a team onto another team to swap their positions, or click two teams. Invalid swaps are blocked. This works from any round based on the entered history.'))
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
                st.warning(T('The supplied actual draw is invalid; the editor starts with a random legal draw.'))
                live_pairs=live_t.random_draw(live_s,Random(int(random_seed)))
        else:live_pairs=live_t.random_draw(live_s,Random(int(random_seed)))
        editor_state=draw_editor(live_t,live_s,live_pairs,key='drag_editor',lang=lang)
        if editor_state and editor_state.get('pairs'):
            proposed=tuple((live_t.ids[a],live_t.ids[b]) for a,b in editor_state['pairs'])
            if live_t.is_legal(live_s,proposed):
                st.success(T('Edited pairing is legal — ready to analyze.'))
            else:
                st.error(T('Edited pairing is illegal; no analysis will be run on it.'))
        else:
            st.info(T('Editor is showing the current pairing. Drag a team to change opponents.'))
    else:st.info(T('Tournament is complete: no remaining draw.'))
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
            st.error(T('Live preview disabled: illegal draw.'))
        else:
            context = {'teams':[asdict(t) for t in live_t.teams], 'rules':asdict(live_t.rules),
                       'state':{'wins':live_s.wins,'losses':live_s.losses,'met':sorted(live_s.met),
                                'round':live_s.round,'alive':live_s.alive}}
            context_key=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
            baseline_key=('baseline',context_key,int(preview_baseline),int(random_seed))
            report_key=('draw',context_key,normalized,int(preview_samples),int(random_seed))
            preview_base,_=_preview_cached(baseline_key,lambda:live_t.baseline(live_s,int(preview_baseline),int(random_seed)+1))
            preview_report,_=_preview_cached(report_key,lambda:live_t.analyze(live_s,[normalized],int(preview_samples),int(random_seed))[0])
            st.markdown(T('### Live impact — edited draw vs random baseline'))
            st.caption(T('Automatically refreshed on valid drag. Cached results are reused when you return to an earlier pairing. Estimates are preliminary; use full analysis for higher precision.'))
            live_rows=[]
            for region in live_t.regions:
                observed=preview_report.region_expected[region]
                random_mean=preview_base['region_expected'][region]
                live_rows.append({T('Region'):region,T('Edited expected'):observed,T('Random expected'):random_mean,
                                  T('Impact'):observed-random_mean,
                                  T('MC SE (difference, approx)'):(preview_report.region_se[region]**2+preview_base['region_se'][region]**2)**0.5})
            st.dataframe(pd.DataFrame(live_rows).round(4),hide_index=True,use_container_width=True)
            st.bar_chart(pd.DataFrame(live_rows).set_index(T('Region'))[[T('Impact')]],horizontal=True)
            with st.expander(T('Team advancement probabilities for edited draw')):
                st.dataframe(pd.DataFrame([{T('Team'):t.id,T('Region'):t.region,
                    T('Edited'):preview_report.team_advance[t.id],
                    T('Random'):preview_base['team_advance'][t.id],
                    T('Impact'):preview_report.team_advance[t.id]-preview_base['team_advance'][t.id]}
                    for t in live_t.teams]).round(4),hide_index=True,use_container_width=True)
            if preview_report.unfinished or preview_base['failed']:
                st.warning(T('Some simulation paths had no legal next draw. Estimates condition on completed runs; inspect the rule fallback.'))
    except Exception as exc:
        st.warning(f'Live preview unavailable: {type(exc).__name__}: {exc}')

analyze_edited = st.button(T('Analyze edited draw'),type='primary',disabled=not bool(editor_state and editor_state.get('pairs')))
analyze_all = st.button(T('Analyze all legal draws'))
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
        with st.spinner(T('Running future tournament simulations...')):
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
    st.success((f'当前轮次 {s.round} | 剩余 {len(t.active(s))} 队 | 已分析 {len(draws)} 套签表 | ' if lang=='中文' else f'Current round {s.round} | {len(t.active(s))} active teams | {len(draws)} evaluated draws | ')+(('仅分析当前编辑签表（非全局最优）' if lang=='中文' else 'Single edited draw (not a global optimum)') if len(reports)==1 and not exhaustive else (('候选已穷举' if lang=='中文' else 'Exhaustive candidate coverage') if exhaustive else ('候选抽样：最优/最差仅为近似' if lang=='中文' else 'Sampled candidates: best/worst are approximate'))))
    res=[]
    for r in t.regions:
        ranked=t.rank(reports,r);b=baseline['region_expected'][r]
        row={T('Region'):r,T('Random baseline'):b,T('Best candidate'):ranked[0].region_expected[r] if exhaustive or len(reports)>1 else None,
             T('Worst candidate'):ranked[-1].region_expected[r] if exhaustive or len(reports)>1 else None, T('Best minus random'):ranked[0].region_expected[r]-b if exhaustive or len(reports)>1 else None}
        if real: row.update({T('Actual'):real.region_expected[r],T('Actual minus random'):real.region_expected[r]-b,T('Actual SE'):real.region_se[r]})
        res.append(row)
    st.markdown(T('### Region outcomes')); st.dataframe(pd.DataFrame(res).round(4),hide_index=True,use_container_width=True)
    focal=st.selectbox(T('Inspect region'),t.regions)
    ranked=t.rank(reports,focal)
    st.markdown(T('### Best, worst, and observed draws'))
    a,b,c=st.columns(3)
    for col,label,rep in ((a,T('Best'),ranked[0]),(b,T('Worst'),ranked[-1]),(c,T('Edited / actual'),real)):
        with col:
            st.subheader(label)
            if rep:
                st.metric(T('Expected qualifying teams'),f'{rep.region_expected[focal]:.4f}')
                st.code('\n'.join(f'{x} vs {y}' for x,y in t.draw_names(rep.matches)))
                st.caption(f'SE ± {rep.region_se[focal]:.4f}; {rep.simulations} feasible simulations; {rep.unfinished} stuck')
            else:st.caption(T('No actual draw provided'))
    st.markdown(T('### Candidate ranking'))
    rankdata=[]
    for pos,rep in enumerate(ranked,1):
        rankdata.append({T('rank'):pos,T('expected'):rep.region_expected[focal],'SE':rep.region_se[focal],T('matches'):'; '.join(a+'-'+b for a,b in t.draw_names(rep.matches))})
    st.dataframe(pd.DataFrame(rankdata).round(4),hide_index=True,use_container_width=True)
    st.download_button(T('Download full candidate CSV'),pd.DataFrame(rankdata).to_csv(index=False).encode(),'drawlab_rankings.csv','text/csv')
    st.markdown(T('### Team qualifying probabilities'))
    st.dataframe(pd.DataFrame([{T('team'):tt.id,T('region'):tt.region,T('baseline'):baseline['team_advance'][tt.id],
       T('best'):ranked[0].team_advance[tt.id],T('worst'):ranked[-1].team_advance[tt.id],
       T('actual'):real.team_advance[tt.id] if real else None} for tt in t.teams]).round(4),hide_index=True,use_container_width=True)
    st.warning('蒙特卡洛为近似估计；标准误仅反映抽样误差，不表示 Elo 模型准确度。无法继续配对的模拟会单独报告，不会悄悄修改规则。' if lang=='中文' else 'Monte Carlo estimates are not exact. SE describes sampling uncertainty, not Elo-model accuracy. If simulations get stuck, change the matching fallback rules; stuck trajectories are reported rather than quietly repaired.')
