import json
import sqlite3

from arc_arena.arcstore import ArcStore
from arc_arena.artifacts import Artifacts


def test_reviewed_prose_keeps_scientific_identity_and_decision(tmp_path):
    db = tmp_path / 'arc.sqlite'
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE discovery_ideas(id TEXT,run_id TEXT,data TEXT)')
    original = {'idea_id':'idea_1','seed':{'title':'Original title'},
                'status':'checked','note':{'decision':'lead','limits':['Abstract only']}}
    conn.execute('INSERT INTO discovery_ideas VALUES (?,?,?)',('idea_1','run_1',json.dumps(original)))
    conn.commit()
    reports = tmp_path / 'reports'
    folder = reports / 'run_1'
    folder.mkdir(parents=True)
    manifest = {'run_id':'run_1','candidates':[
        {'idea_id':'idea_1','presentation_title':'Readable title','text':'A conditional lead.'},
        {'idea_id':'unrelated','presentation_title':'Do not add','text':'Different candidate'}]}
    (folder/'PRESENTATION.json').write_text(json.dumps(manifest))
    arts = Artifacts(ArcStore(db),reports)
    card, = arts.discover_detail(folder,{})['cards']
    assert card['seed'] == original['seed']
    assert card['note'] == original['note']
    assert card['presentation']['presentation_title'] == 'Readable title'
    assert json.loads(conn.execute('SELECT data FROM discovery_ideas').fetchone()[0]) == original
    manifest['run_id'] = 'another_run'
    (folder/'PRESENTATION.json').write_text(json.dumps(manifest))
    assert arts.discover_detail(folder,{})['cards'][0]['presentation'] is None


def test_malformed_presentation_does_not_break_original_detail(tmp_path):
    folder = tmp_path/'run_1'
    folder.mkdir()
    arts = Artifacts(ArcStore(tmp_path/'absent.sqlite'),tmp_path)
    for value in [None, [], {'run_id':'run_1','candidates':[None]},
                  {'run_id':'run_1','candidates':[{'idea_id':'idea_1','text':[],'presentation_title':'x'}]}]:
        (folder/'PRESENTATION.json').write_text(json.dumps(value))
        assert arts.discover_detail(folder,{})['presentation'] is None
