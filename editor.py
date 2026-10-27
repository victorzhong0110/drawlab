"""Native Streamlit drag and drop editor component (no external frontend dependencies)."""
import hashlib
import json
from pathlib import Path
import streamlit.components.v1 as components

_component = components.declare_component('drawlab_drag_editor', path=str(Path(__file__).parent / 'draw_editor'))

def draw_editor(t, s, initial, key='drawlab_editor', lang='中文'):
    """Return {'pairs': [[id,id],...], 'change_id': number} after edits."""
    active = t.active(s)
    groups = {}
    for group in t.groups(s):
        name = ('Record '+str(s.wins[group[0]])+'-'+str(s.losses[group[0]]) if t.rules.format=='swiss' and not (s.round==1 and t.rules.opening_seed_pairs) else 'Active teams')
        for i in group: groups[t.teams[i].id] = name
    allowed={}
    for a in active:
        for b in active:
            if a>=b:continue
            if t.eligible(s,a,b) and groups[t.teams[a].id]==groups[t.teams[b].id]:
                allowed['||'.join(sorted([t.teams[a].id,t.teams[b].id]))] = True
    pairs=[[t.teams[a].id,t.teams[b].id] for a,b in initial]
    identity=json.dumps({'pairs':pairs,'groups':groups,'allowed':allowed},sort_keys=True)
    fingerprint=hashlib.sha256(identity.encode()).hexdigest()[:20]
    return _component(teams=[t.teams[i].id for i in active],info={t.teams[i].id:{'region':t.teams[i].region} for i in active},groups=groups,allowed=allowed,pairs=pairs,fingerprint=fingerprint,language=lang,key=key,default=None)
