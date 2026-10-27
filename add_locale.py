from pathlib import Path
p=Path(__file__).with_name('app.py');s=p.read_text()
s=s.replace('from editor import draw_editor','from editor import draw_editor\nfrom localize import tr, options')
s=s.replace("st.title('DrawLab · Swiss & Knockout Draw Optimizer')", "lang=st.sidebar.selectbox('Language / 语言',['中文','English'],key='drawlab_language')\nT=lambda text:tr(text,lang)\nst.title(T('DrawLab · Swiss & Knockout Draw Optimizer'))")
import ast
# Replace literal user-facing strings with translated equivalent; preserve identifiers and data fields.
entries=[
'Compare actual draws vs legal random baseline, best and worst candidates, and individual team advance probabilities.',
'Tournament setup','Tournament format','Starting teams','Wins to qualify (Swiss)','Losses to eliminate (Swiss)',
'Same-region avoidance','Avoid past opponents','Pair within the same W-L record','Opening seed pairs (optional)',
'Example: 1-4,2-3. Leave blank for unrestricted round 1.','Normal Swiss match',
'Qualification/elimination match','Knockout match','Elo scale','Analysis controls','Simulations per candidate',
'Random baseline simulations','Enumeration cap','Fallback: sampled candidate draws','Random seed','Live draw preview',
'Automatically analyze after each legal drag','Preview simulations per draw','Preview baseline simulations',
'Preview is approximate. Full analysis is still available below.',
'### 1. Teams and regions','Upload a tournament JSON (teams, rules, history, actual_draw)',
'### 2. Past results / current state','Enter complete chronological rounds as JSON. Each completed round must include every active team exactly once. Empty list starts from 0-0.',
'History events','### 3. Real/observed draw (optional)','Pairs [ [team_id, team_id], ... ]',
'### 4. Drag-and-drop draw editor','Drag a team onto another team to swap their positions, or click two teams. Invalid swaps are blocked. This works from any round based on the entered history.',
'The supplied actual draw is invalid; the editor starts with a random legal draw.',
'Edited pairing is legal — ready to analyze.','Edited pairing is illegal; no analysis will be run on it.',
'Editor is showing the current pairing. Drag a team to change opponents.',
'Tournament is complete: no remaining draw.',
'### Live impact — edited draw vs random baseline',
'Team advancement probabilities for edited draw','Analyze edited draw','Analyze all legal draws',
'Running future tournament simulations...','### Region outcomes','Inspect region',
'### Best, worst, and observed draws','Best','Worst','Edited / actual',
'Expected qualifying teams','No actual draw provided','### Candidate ranking','Download full candidate CSV','### Team qualifying probabilities',
'Some simulation paths had no legal next draw. Estimates condition on completed runs; inspect the rule fallback.',
'Live preview disabled: illegal draw.',
]
for e in sorted(entries,key=len,reverse=True):
    # use repr matching both single/double quote literals
    for q in ["'",'"']:
        lit=q+e+q
        s=s.replace(lit,'T('+lit+')')
# translated categorical options via format_func (internal selected values unchanged)
s=s.replace("st.selectbox('Tournament format',['swiss','knockout'])", "st.selectbox(T('Tournament format'),['swiss','knockout'],format_func=lambda v:T(v))")
s=s.replace("st.selectbox(T('Same-region avoidance'),['off','first','always'],index=1)","st.selectbox(T('Same-region avoidance'),['off','first','always'],index=1,format_func=lambda v:T(v))")
# dynamic text and columns: translate only display labels
for k in ['Region','Edited expected','Random expected','Impact','MC SE (difference, approx)','Team','Edited','Random',
          'Random baseline','Best candidate','Worst candidate','Best minus random','Actual','Actual minus random','Actual SE',
          'rank','expected','matches','team','region','baseline','best','worst','actual']:
    s=s.replace("'"+k+"':", "T('"+k+"'):")
# preserve Region index for chart by referring to translated key
s=s.replace(".set_index('Region')[['Impact']]", ".set_index(T('Region'))[[T('Impact')]]")
# draw component localization
s=s.replace("key='drag_editor')","key='drag_editor',lang=lang)")
# combine multi-line caption
s=s.replace("st.caption('Automatically refreshed on valid drag. Cached results are reused when you return to an earlier pairing. '\n                       'Estimates are preliminary; use full analysis for higher precision.')", "st.caption(T('Automatically refreshed on valid drag. Cached results are reused when you return to an earlier pairing. Estimates are preliminary; use full analysis for higher precision.'))")
s=s.replace("st.success(f'Current round {s.round} | {len(t.active(s))} active teams | {len(draws)} evaluated draws | '+('Single edited draw (not a global optimum)' if len(reports)==1 and not exhaustive else ('Exhaustive candidate coverage' if exhaustive else 'Sampled candidates: best/worst are approximate')))","st.success((f'当前轮次 {s.round} | 剩余 {len(t.active(s))} 队 | 已分析 {len(draws)} 套签表 | ' if lang=='中文' else f'Current round {s.round} | {len(t.active(s))} active teams | {len(draws)} evaluated draws | ')+(('仅分析当前编辑签表（非全局最优）' if lang=='中文' else 'Single edited draw (not a global optimum)') if len(reports)==1 and not exhaustive else (('候选已穷举' if lang=='中文' else 'Exhaustive candidate coverage') if exhaustive else ('候选抽样：最优/最差仅为近似' if lang=='中文' else 'Sampled candidates: best/worst are approximate'))))")
s=s.replace("st.warning('Monte Carlo estimates are not exact. SE describes sampling uncertainty, not Elo-model accuracy. If simulations get stuck, change the matching fallback rules; stuck trajectories are reported rather than quietly repaired.')", "st.warning('蒙特卡洛为近似估计；标准误仅反映抽样误差，不表示 Elo 模型准确度。无法继续配对的模拟会单独报告，不会悄悄修改规则。' if lang=='中文' else 'Monte Carlo estimates are not exact. SE describes sampling uncertainty, not Elo-model accuracy. If simulations get stuck, change the matching fallback rules; stuck trajectories are reported rather than quietly repaired.')")
p.write_text(s)
