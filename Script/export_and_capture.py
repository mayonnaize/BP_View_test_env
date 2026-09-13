# -*- coding: utf-8 -*-
"""
Script/export_and_capture.py
Execute UE Commandlet (ResavePackages & T3D Export) directly on current engine version,
parse actual exported T3D files, and capture graphs at 1:1 scale using Chrome Headless.
"""

import os
import re
import json
import shutil
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPROJECT_PATH = os.path.join(PROJECT_ROOT, 'MyProject.uproject')
EXPORT_DIR = os.path.join(PROJECT_ROOT, 'exported_t3d')
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, 'screenshots')
ARTIFACT_DIR = r'C:\Users\matoi\.gemini\antigravity\brain\c8339c92-b300-42bf-9663-69f45ab79ead\screenshots'
CHROME_EXE = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <link href="https://blueprintue.com/site.css" rel="stylesheet">
    <link href="https://blueprintue.com/bue-render/render.css" rel="stylesheet">
    <style>
        body, html {{ margin: 0; padding: 0; width: 1920px; height: 1080px; background: #222; overflow: hidden; }}
        #blueprint-render-playground {{ width: 1920px; height: 1080px; }}
    </style>
</head>
<body>
    <div id="blueprint-render-playground"></div>
    <script src="https://blueprintue.com/site.js"></script>
    <script src="https://blueprintue.com/bue-render/render.js"></script>
    <script>
        window.onload = function() {{
            var code = {code_json};
            var playground = document.getElementById('blueprint-render-playground');
            if (window.blueprintUE && window.blueprintUE.render && window.blueprintUE.render.Main) {{
                new window.blueprintUE.render.Main(
                    code,
                    playground,
                    {{height: "1080px", width: "1920px"}}
                ).start();
            }}
        }};
    </script>
</body>
</html>
'''

def get_engine_editor_cmd():
    with open(UPROJECT_PATH, 'r', encoding='utf-8') as f:
        uproj = json.load(f)
    assoc = uproj.get('EngineAssociation', '')
    if assoc.startswith('5.'):
        candidate = f"E:/UE_{assoc}/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
        if os.path.exists(candidate):
            return candidate
    elif assoc.startswith('{') or assoc == '4.27':
        candidate = "E:/UE_4.27/Engine/Binaries/Win64/UE4Editor-Cmd.exe"
        if os.path.exists(candidate):
            return candidate
            
    # Default fallbacks
    for ver in ['5.3', '5.6', '5.8']:
        candidate = f"E:/UE_{ver}/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
        if os.path.exists(candidate):
            return candidate
    raise RuntimeError("Unreal Editor commandlet executable not found.")

def run_ue_resave_and_export(editor_cmd):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    
    # 1. ResavePackages
    print(f"=== Running ResavePackages via {editor_cmd} ===")
    cmd_resave = [editor_cmd, UPROJECT_PATH.replace('\\', '/'), '-run=ResavePackages', '-clean', '-unattended', '-stdout']
    subprocess.run(cmd_resave, check=False)
    
    # 2. Export T3D via python script
    print("=== Running T3D Export via Unreal Python ===")
    export_py_path = os.path.join(PROJECT_ROOT, 'tmp_export_runner.py')
    export_code = f'''import unreal, os

out_dir = r"{EXPORT_DIR}".replace('\\\\', '/')
assets = [
    ('/Game/ThirdPersonBP/Blueprints/ThirdPersonCharacter', 'ThirdPersonCharacter.t3d'),
    ('/Game/ThirdPersonBP/Blueprints/ThirdPersonGameMode', 'ThirdPersonGameMode.t3d'),
    ('/Game/Mannequin/Animations/ThirdPerson_AnimBP', 'ThirdPerson_AnimBP.t3d')
]

for asset_path, filename in assets:
    obj = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not obj:
        print(f"[ERROR] Failed to load {{asset_path}}")
        continue
    task = unreal.AssetExportTask()
    task.object = obj
    task.filename = os.path.join(out_dir, filename).replace('\\\\', '/')
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    task.exporter = unreal.ObjectExporterT3D()
    ok = unreal.Exporter.run_asset_export_task(task)
    print(f"[EXPORT] {{asset_path}} -> {{filename}} (success={{ok}})")
'''
    with open(export_py_path, 'w', encoding='utf-8') as f:
        f.write(export_code)
        
    cmd_export = [editor_cmd, UPROJECT_PATH.replace('\\', '/'), '-run=pythonscript', f"-script={export_py_path.replace('\\', '/')}", '-unattended', '-stdout', '-nopause']
    subprocess.run(cmd_export, check=False)
    if os.path.exists(export_py_path):
        os.remove(export_py_path)

def extract_graphs_from_t3d(t3d_path):
    with open(t3d_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()
    graphs = {}
    current_graph = None
    for line in lines:
        stripped = line.strip()
        m_graph = re.match(r'Begin Object Class=/Script/Engine\.EdGraph Name="([^"]+)"', stripped)
        if m_graph:
            current_graph = m_graph.group(1)
            graphs[current_graph] = {}
            continue
        if current_graph:
            m_node = re.match(r'Begin Object Class=([^ ]+) Name="([^"]+)"', stripped)
            if m_node:
                graphs[current_graph][m_node.group(2)] = {'class': m_node.group(1), 'body': []}

    current_node_name = None
    current_body = []
    for line in lines:
        stripped = line.strip()
        m_start = re.match(r'Begin Object Name="([^"]+)"', stripped)
        if m_start:
            current_node_name = m_start.group(1)
            current_body = []
            continue
        if stripped == 'End Object' and current_node_name:
            for g_name, g_nodes in graphs.items():
                if current_node_name in g_nodes:
                    g_nodes[current_node_name]['body'] = list(current_body)
            current_node_name = None
            current_body = []
            continue
        if current_node_name:
            current_body.append(line)
    return graphs

def capture_graph(asset_name, graph_id, title, code_text, node_names):
    asset_dir = os.path.join(SCREENSHOT_DIR, asset_name)
    os.makedirs(asset_dir, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    
    html_content = HTML_TEMPLATE.format(title=title, code_json=json.dumps(code_text))
    html_path = os.path.join(asset_dir, f"{graph_id}.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    shot_path = os.path.join(asset_dir, f"{graph_id}.png")
    cmd = [
        CHROME_EXE,
        '--headless',
        '--disable-gpu',
        '--window-size=1920,1080',
        '--virtual-time-budget=5000',
        '--run-all-compositor-stages-before-draw',
        f'--screenshot={shot_path}',
        'file:///' + html_path.replace('\\', '/')
    ]
    subprocess.run(cmd, check=True)
    
    artifact_path = os.path.join(ARTIFACT_DIR, f"{asset_name}_{graph_id}.png")
    shutil.copyfile(shot_path, artifact_path)
    
    size = os.path.getsize(shot_path)
    print(f"[{asset_name}] Captured {graph_id} ({len(node_names)} nodes, {size} bytes)")
    return {
        'asset': asset_name,
        'graph_id': graph_id,
        'title': title,
        'nodes': node_names,
        'node_count': len(node_names),
        'file_path': shot_path,
        'artifact_path': artifact_path,
        'size_bytes': size
    }

def format_node_block(name, info):
    lines = [f'Begin Object Class={info["class"]} Name="{name}"']
    lines.extend(info['body'])
    lines.append('End Object')
    return '\n'.join(lines)

def main():
    editor_cmd = get_engine_editor_cmd()
    run_ue_resave_and_export(editor_cmd)
    
    manifest = []
    
    # 1. ThirdPersonGameMode - UserConstructionScript
    gm_t3d = os.path.join(EXPORT_DIR, 'ThirdPersonGameMode.t3d')
    gm_graphs = extract_graphs_from_t3d(gm_t3d)
    gm_ucs = gm_graphs.get('UserConstructionScript', {})
    gm_ucs_nodes = [n for n, info in gm_ucs.items() if 'K2Node' in info['class'] or 'EdGraphNode' in info['class']]
    gm_ucs_code = '\n\n'.join([format_node_block(n, gm_ucs[n]) for n in gm_ucs_nodes])
    manifest.append(capture_graph(
        'ThirdPersonGameMode',
        'UserConstructionScript',
        'ThirdPersonGameMode - UserConstructionScript',
        gm_ucs_code,
        gm_ucs_nodes
    ))
    
    # 2. ThirdPersonCharacter
    tpc_t3d = os.path.join(EXPORT_DIR, 'ThirdPersonCharacter.t3d')
    tpc_graphs = extract_graphs_from_t3d(tpc_t3d)
    
    # 2.1 UserConstructionScript
    tpc_ucs = tpc_graphs.get('UserConstructionScript', {})
    tpc_ucs_nodes = [n for n, info in tpc_ucs.items() if 'K2Node' in info['class'] or 'EdGraphNode' in info['class']]
    tpc_ucs_code = '\n\n'.join([format_node_block(n, tpc_ucs[n]) for n in tpc_ucs_nodes])
    manifest.append(capture_graph(
        'ThirdPersonCharacter',
        'UserConstructionScript',
        'ThirdPersonCharacter - UserConstructionScript',
        tpc_ucs_code,
        tpc_ucs_nodes
    ))
    
    # 2.2 EventGraph (5 clusters)
    tpc_eg = tpc_graphs.get('EventGraph', {})
    eg_nodes = []
    for name, info in tpc_eg.items():
        if not ('K2Node' in info['class'] or 'EdGraphNode' in info['class']):
            continue
        x, y = 0, 0
        for l in info['body']:
            s = l.strip()
            if s.startswith('NodePosX='): x = int(s.split('=')[1])
            elif s.startswith('NodePosY='): y = int(s.split('=')[1])
        eg_nodes.append({'name': name, 'info': info, 'x': x, 'y': y})
        
    clusters = [
        ('EventGraph_cluster1_gamepad_vr', 'ThirdPersonCharacter - EventGraph: Gamepad & VR Input', lambda n: n['y'] <= -650),
        ('EventGraph_cluster2_mouse', 'ThirdPersonCharacter - EventGraph: Mouse Input', lambda n: n['x'] < 450 and -650 < n['y'] < -180),
        ('EventGraph_cluster3_movement', 'ThirdPersonCharacter - EventGraph: Movement Input', lambda n: n['x'] >= 450 and -650 < n['y'] < 120),
        ('EventGraph_cluster4_jump', 'ThirdPersonCharacter - EventGraph: Jump Input', lambda n: n['x'] < 450 and -180 <= n['y'] < 130),
        ('EventGraph_cluster5_touch', 'ThirdPersonCharacter - EventGraph: Touch Input', lambda n: n['y'] >= 130)
    ]
    for cid, title, cfilter in clusters:
        matched = [n for n in eg_nodes if cfilter(n)]
        code_blocks = [format_node_block(n['name'], n['info']) for n in matched]
        manifest.append(capture_graph(
            'ThirdPersonCharacter',
            cid,
            title,
            '\n\n'.join(code_blocks),
            [n['name'] for n in matched]
        ))
        
    # 3. ThirdPerson_AnimBP - EventGraph (2 parts)
    anim_t3d = os.path.join(EXPORT_DIR, 'ThirdPerson_AnimBP.t3d')
    anim_graphs = extract_graphs_from_t3d(anim_t3d)
    anim_eg = anim_graphs.get('EventGraph', {})
    
    isinair_node_names = [
        'K2Node_Comment_22', 'K2Node_Event_14', 'K2Node_CallFunction_11813',
        'K2Node_MacroInstance_40', 'EdGraphNode_Comment_19', 'K2Node_CallFunction_2246',
        'K2Node_CallFunction_2731', 'K2Node_VariableSet_64'
    ]
    speed_node_names = [
        'K2Node_Comment_25', 'K2Node_CallFunction_11990', 'K2Node_CallFunction_846', 'K2Node_VariableSet_24'
    ]
    
    matched_isinair = [n for n in isinair_node_names if n in anim_eg]
    code_isinair = '\n\n'.join([format_node_block(n, anim_eg[n]) for n in matched_isinair])
    manifest.append(capture_graph(
        'ThirdPerson_AnimBP',
        'EventGraph_part1_isinair',
        'ThirdPerson_AnimBP - EventGraph: PawnOwner Validation & Set IsInAir',
        code_isinair,
        matched_isinair
    ))
    
    matched_speed = [n for n in speed_node_names if n in anim_eg]
    code_speed = '\n\n'.join([format_node_block(n, anim_eg[n]) for n in matched_speed])
    manifest.append(capture_graph(
        'ThirdPerson_AnimBP',
        'EventGraph_part2_speed',
        'ThirdPerson_AnimBP - EventGraph: Calculate & Set Speed',
        code_speed,
        matched_speed
    ))
    
    manifest_path = os.path.join(PROJECT_ROOT, 'capture_manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        
    print(f"\nAll real-engine captures completed! Total captured images: {len(manifest)}")
    print(f"Manifest saved to: {manifest_path}")

if __name__ == '__main__':
    main()
