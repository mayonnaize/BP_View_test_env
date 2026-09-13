import os
import re
import unreal

# プロジェクトルートのREADME.md出力先指定
OUTPUT = os.path.join(
    unreal.Paths.project_dir(),
    "README.md"
)
ROOT = "/Game/"


def class_name(obj):
    return obj.get_class().get_name() if obj else "-"


def escape_md(value):
    return str(value).replace("|", r"\|").replace("\n", " ")


def asset_to_filename(asset_path):
    package_path = asset_path.split(".", 1)[0]
    if package_path.startswith("/Game/"):
        return "Content/" + package_path[len("/Game/"):] + ".uasset"
    return package_path + ".uasset"


def get_tags(asset_path):
    # TagValueマップキー値文字列変換
    tag_map = unreal.EditorAssetLibrary.get_tag_values(asset_path)
    return {str(k): str(v) for k, v in tag_map.items()}


def clean_class_path(value):
    if not value or value == "None":
        return "-"

    value = str(value)
    value = value.replace("Class'", "").replace("'", "")
    if "." in value:
        value = value.rsplit(".", 1)[-1]
    return value


def get_parent_class(tags):
    parent = tags.get("ParentClass")
    if not parent or parent == "None":
        parent = tags.get("NativeParentClass")
    return clean_class_path(parent)


def get_asset_type(asset, tags):
    asset_class = class_name(asset)

    if asset_class == "AnimBlueprint":
        return "Animation Blueprint"

    if asset_class == "WidgetBlueprint":
        return "Widget Blueprint"

    if isinstance(asset, unreal.Blueprint):
        bp_type = str(tags.get("BlueprintType", ""))
        if "MacroLibrary" in bp_type:
            return "Blueprint Macro Library"
        if "Interface" in bp_type:
            return "Blueprint Interface"
        if "FunctionLibrary" in bp_type:
            return "Blueprint Function Library"
        if "LevelScript" in bp_type:
            return "Level Blueprint"
        return "Blueprint Class"

    if isinstance(asset, unreal.Material):
        return "Material Blueprint"

    if isinstance(asset, unreal.MaterialFunction):
        return "Material Function"

    return asset_class


# UE Python API制約: UBlueprint.FunctionGraphs / UberGraphPages等はprotectedのため直接読み取り不可
# EdGraphNodeからOuter階層とノード構成を走査してユーザー編集対象グラフを判定

INTERNAL_NAME_PATTERNS = [
    re.compile(r"^ExecuteUbergraph_"),
    re.compile(r"^EvaluateGraphExposedInputs_"),
    re.compile(r"^EdGraph(_\d+)?$"),
    re.compile(r".*__AnimFunc$"),
    re.compile(r".*_MERGED$"),
    re.compile(r"^Inp(Axis|Act|Tch|Key|Gesture|Motion)Evt_"),
]


def is_user_editable_graph(graph_name, graph_class, graph_path, node_classes):
    # 所有関係判定: ExecuteUbergraph配下の複製グラフを除外
    if ":ExecuteUbergraph" in graph_path:
        return False

    # コンパイラ内部ノード判定: 永続フレーム変数設定ノードを含むイベントスタブを除外
    if "K2Node_SetVariableOnPersistentFrame" in node_classes:
        return False

    # コンパイラ自動生成グラフ名の除外
    for pattern in INTERNAL_NAME_PATTERNS:
        if pattern.match(graph_name):
            return False

    # アニメーション系グラフクラスの判定
    anim_classes = (
        "AnimationStateMachineGraph",
        "AnimationTransitionGraph",
        "AnimationStateGraph",
        "AnimationGraph",
    )
    if any(c in graph_class for c in anim_classes):
        return True

    # 標準ルートグラフの判定
    if graph_name in ("EventGraph", "UserConstructionScript"):
        return True

    # ユーザー定義Function判定
    if "K2Node_FunctionEntry" in node_classes:
        return True

    # ユーザー定義Macro判定
    if "K2Node_Tunnel" in node_classes:
        return True

    return False


def classify_blueprint_graph(graph_name, graph_class, node_classes):
    if "AnimationStateMachineGraph" in graph_class:
        return "StateMachine"

    if "AnimationTransitionGraph" in graph_class:
        return "Transition"

    if "AnimationStateGraph" in graph_class:
        return "State"

    if "AnimationGraph" in graph_class:
        return "AnimGraph"

    if graph_name == "EventGraph":
        return "EventGraph"

    if graph_name == "UserConstructionScript":
        return "ConstructionScript"

    if "K2Node_FunctionEntry" in node_classes:
        return "Function"

    if "K2Node_Tunnel" in node_classes:
        return "Macro"

    return graph_class


# 全アセットロード処理（同一ファイル重複エントリ除外）
assets = []
seen_files = set()
asset_paths = unreal.EditorAssetLibrary.list_assets(
    ROOT,
    recursive=True,
    include_folder=False
)

for asset_path in asset_paths:
    filename = asset_to_filename(asset_path)
    if filename in seen_files:
        continue
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset:
        seen_files.add(filename)
        assets.append((asset_path, asset))


# EdGraphNodeからBlueprintグラフ情報インデックス化
graph_index = {}

for node in unreal.ObjectIterator(unreal.EdGraphNode):
    bp = node.get_typed_outer(unreal.Blueprint)
    if not bp:
        continue

    graph = node.get_outer()
    if not graph:
        continue

    bp_path = bp.get_path_name()
    graph_path = graph.get_path_name()

    bp_graphs = graph_index.setdefault(bp_path, {})
    info = bp_graphs.setdefault(
        graph_path,
        {
            "name": graph.get_name(),
            "class": graph.get_class().get_name(),
            "path": graph_path,
            "node_classes": set(),
            "node_count": 0,
        }
    )

    info["node_classes"].add(node.get_class().get_name())
    info["node_count"] += 1


# レポート行データ生成
rows = []

for asset_path, asset in assets:
    asset_class = class_name(asset)
    tags = get_tags(asset_path)
    asset_type = get_asset_type(asset, tags)

    graph_family = "-"
    graph_count = 0
    graph_names = []
    graph_types = []
    node_count = 0
    has_graph = "×"
    note = ""
    parent_class = "-"

    if isinstance(asset, unreal.Blueprint):
        graph_family = "Blueprint"
        parent_class = get_parent_class(tags)

        all_graphs = list(graph_index.get(asset.get_path_name(), {}).values())
        graphs = [
            g for g in all_graphs
            if is_user_editable_graph(
                g["name"],
                g["class"],
                g["path"],
                g["node_classes"]
            )
        ]
        for graph in graphs:
            graph_names.append(graph["name"])
            graph_types.append(
                classify_blueprint_graph(
                    graph["name"],
                    graph["class"],
                    graph["node_classes"]
                )
            )
            node_count += graph["node_count"]

        graph_count = len(graphs)
        has_graph = "○" if graph_count > 0 else "×"

        if graph_count == 0:
            if tags.get("IsDataOnly") == "True":
                note = "Data-Only Blueprint（ロジックグラフなし）"
            else:
                note = "ノードを持たないBlueprintグラフは検出不能"

    elif isinstance(asset, unreal.Material):
        graph_family = "Material"
        graph_count = 1
        graph_names = ["MaterialGraph"]
        graph_types = ["MaterialGraph"]
        has_graph = "○"
        node_count = unreal.MaterialEditingLibrary.get_num_material_expressions(asset)

    elif isinstance(asset, unreal.MaterialFunction):
        graph_family = "Material"
        graph_count = 1
        graph_names = ["MaterialFunctionGraph"]
        graph_types = ["MaterialFunctionGraph"]
        has_graph = "○"
        node_count = unreal.MaterialEditingLibrary.get_num_material_expressions_in_function(asset)

    rows.append([
        asset_to_filename(asset_path),
        asset_class,
        asset_type,
        parent_class,
        graph_family,
        str(graph_count),
        "<br>".join(graph_names) if graph_names else "-",
        "<br>".join(graph_types) if graph_types else "-",
        str(node_count),
        has_graph,
        note,
    ])


# Markdownテーブル出力
headers = [
    "ファイル名",
    "アセットクラス",
    "アセット種別",
    "親クラス",
    "グラフ系統",
    "グラフ数",
    "グラフ名",
    "グラフ種別",
    "ノード数",
    "グラフ有無",
    "備考",
]

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("| " + " | ".join(headers) + " |\n")
    f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
    for row in rows:
        f.write("| " + " | ".join(escape_md(v) for v in row) + " |\n")

unreal.log("Blueprint graph report successfully generated: {}".format(OUTPUT))
