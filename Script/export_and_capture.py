"""
export_and_capture.py
Export and capture all renderable Blueprint/Animation graphs at 1:1 scale with zero cut-off.
"""

import os
import re
import json
import shutil
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_DIR = os.path.join(PROJECT_ROOT, 'exported_t3d')
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, 'screenshots')
ARTIFACT_DIR = r'C:\Users\matoi\.gemini\antigravity\brain\c8339c92-b300-42bf-9663-69f45ab79ead\screenshots'
CHROME_EXE = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

os.makedirs(EXPORT_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)

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

def capture_graph(asset_name, graph_id, title, code_text, node_names):
    asset_dir = os.path.join(SCREENSHOT_DIR, asset_name)
    os.makedirs(asset_dir, exist_ok=True)
    
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

def main():
    manifest = []
    
    # ----------------------------------------------------
    # 1. ThirdPersonGameMode - UserConstructionScript (1 node)
    # ----------------------------------------------------
    cs_code = '''Begin Object Class=/Script/BlueprintGraph.K2Node_FunctionEntry Name="K2Node_FunctionEntry_19"
   NodePosX=0
   NodePosY=0
   NodeGuid=00000000000000000000000000000001
   CustomProperties Pin (PinId=00000000000000000000000000000002,PinName="then",Direction="EGPD_Output",PinType.PinCategory="exec")
End Object
'''
    res = capture_graph(
        'ThirdPersonGameMode',
        'UserConstructionScript',
        'ThirdPersonGameMode - UserConstructionScript',
        cs_code,
        ['K2Node_FunctionEntry_19']
    )
    manifest.append(res)
    
    # ----------------------------------------------------
    # 2. ThirdPersonCharacter
    # ----------------------------------------------------
    # 2.1 UserConstructionScript (1 node)
    res = capture_graph(
        'ThirdPersonCharacter',
        'UserConstructionScript',
        'ThirdPersonCharacter - UserConstructionScript',
        cs_code,
        ['K2Node_FunctionEntry_19']
    )
    manifest.append(res)
    
    # 2.2 EventGraph (40 nodes) -> 5 clusters (1:1 scale, zero cut-off)
    with open(os.path.join(PROJECT_ROOT, 'EventGraph_clipboard.txt'), 'r', encoding='utf-8') as f:
        ev_text = f.read()
        
    ev_nodes = []
    cur_lines = []
    cur_name = None
    cur_x, cur_y = 0, 0
    for line in ev_text.splitlines():
        s = line.strip()
        if s.startswith('Begin Object'):
            cur_lines = [line]
            m = re.search(r'Name="([^"]+)"', s)
            cur_name = m.group(1) if m else 'Unknown'
            cur_x, cur_y = 0, 0
        elif s.startswith('End Object'):
            cur_lines.append(line)
            ev_nodes.append({
                'name': cur_name,
                'lines': cur_lines,
                'x': cur_x,
                'y': cur_y
            })
            cur_lines = []
            cur_name = None
        else:
            if cur_lines:
                cur_lines.append(line)
                if s.startswith('NodePosX='):
                    cur_x = int(s.split('=')[1])
                elif s.startswith('NodePosY='):
                    cur_y = int(s.split('=')[1])
                    
    clusters = [
        ('EventGraph_cluster1_gamepad_vr', 'ThirdPersonCharacter - EventGraph: Gamepad & VR Input', lambda n: n['y'] <= -650),
        ('EventGraph_cluster2_mouse', 'ThirdPersonCharacter - EventGraph: Mouse Input', lambda n: n['x'] < 450 and -650 < n['y'] < -180),
        ('EventGraph_cluster3_movement', 'ThirdPersonCharacter - EventGraph: Movement Input', lambda n: n['x'] >= 450 and -650 < n['y'] < 120),
        ('EventGraph_cluster4_jump', 'ThirdPersonCharacter - EventGraph: Jump Input', lambda n: n['x'] < 450 and -180 <= n['y'] < 130),
        ('EventGraph_cluster5_touch', 'ThirdPersonCharacter - EventGraph: Touch Input', lambda n: n['y'] >= 130)
    ]
    
    total_ev_nodes = 0
    for c_id, c_title, c_filter in clusters:
        matched = [n for n in ev_nodes if c_filter(n)]
        total_ev_nodes += len(matched)
        c_lines = []
        for n in matched:
            c_lines.extend(n['lines'])
            c_lines.append('')
        res = capture_graph(
            'ThirdPersonCharacter',
            c_id,
            c_title,
            '\n'.join(c_lines),
            [n['name'] for n in matched]
        )
        manifest.append(res)
    print(f"[ThirdPersonCharacter] EventGraph total matched nodes: {total_ev_nodes} / {len(ev_nodes)}")

    # ----------------------------------------------------
    # 3. ThirdPerson_AnimBP - EventGraph (12 nodes: 9 logic + 3 comments)
    # ----------------------------------------------------
    with open(os.path.join(EXPORT_DIR, 'ThirdPerson_AnimBP.t3d'), 'r', encoding='utf-16') as f:
        anim_text = f.read()
        
    class_map = {}
    for m in re.finditer(r'Begin Object Class=/Script/([^\s]+) Name="([^"]+)"', anim_text):
        class_map[m.group(2)] = f"/Script/{m.group(1)}"
        
    def get_anim_node_def(node_name):
        cls = class_map.get(node_name, '')
        pattern = r'Begin Object (?:Class=[^\s]+ )?Name="' + re.escape(node_name) + r'"\s*\n(.*?)\n\s*End Object'
        for m in re.finditer(pattern, anim_text, re.DOTALL):
            body = m.group(1)
            if 'NodePosX' in body or 'NodeComment' in body or 'CustomProperties Pin' in body:
                return f'Begin Object Class={cls} Name="{node_name}"\n{body}\nEnd Object'
        return None

    # Correct node assignment:
    # Part 1: Validation and Setting 'IsInAir'
    isinair_nodes = [
        'K2Node_Comment_22',          # Comment: "See if PawnOwner is valid (will not be in Persona)"
        'K2Node_Event_14',            # BlueprintUpdateAnimation event
        'K2Node_CallFunction_11813',  # TryGetPawnOwner
        'K2Node_MacroInstance_40',    # IsValid macro
        'EdGraphNode_Comment_19',     # Comment: "Set 'IsInAir' (used in state machine)"
        'K2Node_CallFunction_2246',   # GetMovementComponent
        'K2Node_CallFunction_2731',   # IsFalling
        'K2Node_VariableSet_64'       # Set IsInAir?
    ]
    
    # Part 2: Setting 'Speed' (Self-contained cluster without distant PawnOwner)
    speed_nodes = [
        'K2Node_Comment_25',          # Comment: "Setting 'Speed' (use in 1D blend space)"
        'K2Node_CallFunction_11990',  # GetVelocity
        'K2Node_CallFunction_846',    # VSize
        'K2Node_VariableSet_24'       # Set Speed
    ]
    
    isinair_blocks = [get_anim_node_def(n) for n in isinair_nodes if get_anim_node_def(n)]
    res = capture_graph(
        'ThirdPerson_AnimBP',
        'EventGraph_part1_isinair',
        'ThirdPerson_AnimBP - EventGraph: PawnOwner Validation & Set IsInAir',
        '\n\n'.join(isinair_blocks),
        isinair_nodes
    )
    manifest.append(res)
    
    speed_blocks = [get_anim_node_def(n) for n in speed_nodes if get_anim_node_def(n)]
    res = capture_graph(
        'ThirdPerson_AnimBP',
        'EventGraph_part2_speed',
        'ThirdPerson_AnimBP - EventGraph: Calculate & Set Speed',
        '\n\n'.join(speed_blocks),
        speed_nodes
    )
    manifest.append(res)

    manifest_path = os.path.join(PROJECT_ROOT, 'capture_manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        
    print(f"\nAll captures completed! Total captured images: {len(manifest)}")
    print(f"Manifest saved to: {manifest_path}")

if __name__ == '__main__':
    main()
