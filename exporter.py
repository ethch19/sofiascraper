import os
import json
import pytz
from datetime import datetime
from anytree import Node, PreOrderIter
from anytree.search import find
from collections import deque, OrderedDict
import pandas as pd
import re

json_name_dict = ["user", "curriculum-groups", "bundle-settings", "curriculum", "resources", "notes", "attachments", "learning-events", "calendar-events", "clinical"]
FILE_TYPES = ["csv", "xlsx"]
SORTBY_OPTIONS = ["None", "Alphabetical (A-Z)", "Alphabetical (Z-A)"]
FLATTEN_OPTIONS = ["Intermediate-level"] # potentially Top-level flattening, but not that useful

def get_files(responses: list, start_with="responses_", separator="_", uuid_search="user"):
    path_dict = {}
    for folder in responses:
        folder_path = start_with+folder
        folder_dict = {}
        uuid = ""
        for file in sorted(os.listdir(folder_path)):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                file_split = os.path.splitext(file)
                file_sep = file_split[0].split(separator)
                if len(file_sep) > 1:
                    file_name = file_sep[1]
                else:
                    file_name = file_sep[0]
                if file_name == uuid_search:
                    with open(file_path, "r") as f:
                        json_dict = json.load(f)
                        uuid = str(json_dict['curriculum'])
                elif file_name == uuid:
                    with open(file_path, "r") as f:
                        json_dict = json.load(f)
                        if "user_schema" in json_dict:
                            new_path = os.path.join(folder_path, "schemas.json")
                            os.rename(file_path, new_path)
                            folder_dict["schemas"] = new_path
                        else:
                            if len(file_sep) > 2:
                                folder_dict["items-cache"] = file_path
                                continue
                            new_path = os.path.join(folder_path, "items.json")
                            os.rename(file_path, new_path)
                            folder_dict["items"] = new_path
                            save_dir = os.path.join(folder_path, "items-cache.json")
                            print(save_dir)
                            print(new_path)
                            if not os.path.isfile(save_dir):
                                flip_dict_keys(new_path, save_dir)
                                folder_dict["items-cache"] = save_dir
                        continue
                new_path = os.path.join(folder_path, f"{file_name}.json")
                os.rename(file_path, new_path)
                folder_dict[file_name] = new_path
        folder_dict['uuid-curriculum'] = uuid
        path_dict[folder] = folder_dict
    return path_dict

def epoch_to_datetime(epoch, timezone="Europe/London"):
    timezone = pytz.timezone(timezone)
    return datetime.fromtimestamp(epoch).astimezone(timezone).strftime("%Y-%m-%d %H:%M:%S")

def datetime_to_epoch(dt, timezone="Europe/London"):
    timezone = pytz.timezone(timezone)
    dtime = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
    dtime = timezone.localize(dtime.replace(tzinfo=None))
    return int(dtime.timestamp())

def flip_dict_keys(file_dir, save_dir):
    with open(file_dir, "r") as f:
        json_data = json.load(f)
        new_dict = {v["uuid"]: {"id": k, **v} for k, v in json_data.items()}
    with open(save_dir, "w") as f:
        json.dump(new_dict, f, indent=4)

def create_tree(tree_dict, root):
    root = Node(root, parent=None, obj=tree_dict[root])
    queue = deque([root])
    while queue:
        node = queue.popleft()
        if node.obj["children"] == None:
            continue
        for x in node.obj["children"]:
            child_node = Node(x, parent=node, obj=tree_dict[x])
            queue.append(child_node)
    return root

def properties(root_node, node_id):
    return find(root_node, filter_=lambda node: node.name == node_id)

def get_curriculum(link_dict):
    with open(link_dict["user"], "r") as f:
        json_data = json.load(f)
    steps = json_data["steps"]
    statement = []
    for index, element in enumerate(steps):
        code = element["code"]
        curriculum = element["curriculum"]
        statement.append(f"{code}/{curriculum}")
    return steps, statement

def get_responses(directory=".", start_with="responses_", separator="_"):
    responses = []
    for folder in sorted(os.listdir(directory), reverse=True):
        if folder.startswith(start_with):
            response_time = folder.split(separator)[1]
            responses.append(response_time)
    return responses

def get_tree(response: list, select_year: int):
    paths = get_files(response)
    link_dict = paths[response[0]]
    steps, _ = get_curriculum(link_dict)
    uuid = steps[select_year]["uuid"]
    with open(link_dict["items-cache"], "r") as f:
        json_data = json.load(f)
    try:
        entry_id = json_data[uuid]["id"]
    except KeyError:
        print("Uuid item not found")
        return
    with open(link_dict["items"], "r") as f:
        items_json = json.load(f)
    root_node = create_tree(items_json, entry_id)
    return root_node

def extract_paths(node, lo):
    paths = {} # list of all the nodes, each arranged in a hierachy list
    spreadsheet_name = node.obj["title"]
    for leaf in PreOrderIter(node, filter_=lambda n: n.is_leaf):
        path = []
        lo_path = []
        current = leaf
        while current:
            obj_type = current.obj["type"]
            if obj_type == "Y":
                break
            elif obj_type == "O":
                if lo:
                    lo_path.append(current)
                current = current.parent
                continue
            path.append(current) # Append nodes into a list of hierarchy
            current = current.parent
        if str(path[::-1]) not in paths:
            paths[str(path[::-1])] = {
                "path": path[::-1],
                "lo_path": lo_path[::-1]
            }  # Reverse to get root to leaf order
        elif len(lo_path) > 0:
            paths[str(path[::-1])]["lo_path"].extend(lo_path[::-1])
    return (paths, spreadsheet_name)

def level_flattening(paths, flatten):
    try:
        flatten_index = FLATTEN_OPTIONS.index(flatten)
    except ValueError:
        print("Invalid flatten option")
        flatten_index = 0
    match flatten_index:
        case _: #Intermediate-level
            data_dict = {}
            for key, path_dict in paths.items():
                path = path_dict["path"]
                lo_path = path_dict["lo_path"]
                if len(path) == 1:
                    if "level1" not in data_dict:
                        data_dict["level1"] = []
                    data_dict["level1"].append(path[0].obj["title"])
                    continue
                if len(path) > 1:
                    top_level = path[0]
                    row = path[-1]
                    if "title" in row.obj and row.obj["title"] != "":
                        row = row.obj["title"]
                    else:
                        row = row.obj["subtitle"]
                    bottom_level = "Values"
                    grouping = ""
                if len(path) > 2:
                    bottom_level = path[1].obj["title"]
                if len(path) > 3:
                    grouping = " > ".join([n.obj["title"] for n in path[2:-1]])
                top_level_name = top_level.obj["title"][:31]
                if top_level_name not in data_dict:
                    data_dict[top_level_name] = {}
                if bottom_level not in data_dict[top_level_name]:
                    data_dict[top_level_name][bottom_level] = []
                entry = {
                        bottom_level: row,
                }
                if grouping != "":
                    entry["Grouping"] = grouping # Combine intermediate levels starting from level 2 to n -1, where n is index of row
                if len(lo_path) > 0:
                    if "Learning Objectives" not in data_dict:
                        data_dict["Learning Objectives"] = []
                    prev_index = len(data_dict["Learning Objectives"])
                    new_index = prev_index + len(lo_path)
                    data_dict["Learning Objectives"].extend([i.obj["title"] if len(i.obj["title"]) > 0 else i.obj["subtitle"] for i in lo_path])
                    entry["Learning Objectives"] = " ,".join(map(str, range(prev_index, new_index)))
                data_dict[top_level_name][bottom_level].append(entry) # top-level = sheet name, bottom_level = column header
            return data_dict

def sofia_exporter(file_path, data_dict, sortby, file_type):
    try:
        file_index = FILE_TYPES.index(file_type)
    except ValueError:
        print("Invalid filetype index")
        file_index = 0
    match file_index:
        case 0:
            if not os.path.exists(file_path):
                os.makedirs(file_path)
            if "Learning Objectives" in data_dict:
                    temp_dict = OrderedDict([("Learning Objectives", data_dict["Learning Objectives"])])
            if "level1" in data_dict:
                try:
                    temp_dict["level1"] = data_dict["level1"]
                except NameError:
                    temp_dict = OrderedDict([("level1", data_dict["level1"])])
            try:
                temp_dict
                for k, v in sorted(data_dict.items()):
                    if k != "level1" or k != "Learning Objectives":
                        temp_dict[k] = v
                data_dict = temp_dict
            except NameError:
                data_dict = sorted(data_dict.items())
                pass
            for top_level, sheet_data in data_dict.items():
                print(f"{top_level}")
                if top_level == "level1":
                    df = pd.DataFrame(sheet_data)
                    path = os.path.join(file_path, "level_1_only.csv")
                    df.to_csv(path, index=False)
                    continue
                elif top_level == "Learning Objectives":
                    df = pd.DataFrame(sheet_data)
                    path = os.path.join(file_path, "learning_objectives.csv")
                    df.to_csv(path, index=True)
                    continue
                if "Values" in sheet_data:
                    temp_dict = OrderedDict([("Values", sheet_data["Values"])])
                    for k, v in sheet_data.items():
                        if k != "Values":
                            temp_dict[k] = v
                    sheet_data = temp_dict
                for bottom_level, table_data in sheet_data.items():
                    try:
                        sortby_index = SORTBY_OPTIONS.index(sortby)
                    except ValueError:
                        print("Invalid sortby option")
                        sortby_index = 0
                    match sortby_index:
                        case 1: #Alphabetical (A-Z)
                            table_data = sorted(table_data, key=lambda i: i[bottom_level])
                        case 2: #Alphabetical (Z-A)
                            table_data = sorted(table_data, key=lambda i: i[bottom_level], reverse=True)
                        case _: #None
                            pass
                    print(f"{bottom_level}: {table_data}")
                    df = pd.DataFrame(table_data)
                    top_level = re.sub(r'[<>:"/\\|?*\x00-\x1F\s]+', '_', top_level)
                    path = os.path.join(file_path, f"{top_level}.csv")
                    df.to_csv(path, mode="a", index=False)
                    with open(path, 'a') as f:
                        f.write("\n")
            print(f"EXPORT: CSV files to directory '{file_path}' created successfully.")
        case 1:
            file_path = file_path + ".xlsx"
            with pd.ExcelWriter(file_path) as writer:
                if "Learning Objectives" in data_dict:
                    temp_dict = OrderedDict([("Learning Objectives", data_dict["Learning Objectives"])])
                if "level1" in data_dict:
                    try:
                        temp_dict["level1"] = data_dict["level1"]
                    except NameError:
                        temp_dict = OrderedDict([("level1", data_dict["level1"])])
                try:
                    temp_dict
                    for k, v in sorted(data_dict.items()):
                        if k != "level1" or k != "Learning Objectives":
                            temp_dict[k] = v
                    data_dict = temp_dict
                except NameError:
                    data_dict = sorted(data_dict.items())
                    pass
                for top_level, sheet_data in data_dict.items():
                    last_row = 0
                    print(f"{top_level}")
                    if top_level == "level1":
                        df = pd.DataFrame(sheet_data)
                        df.to_excel(writer, sheet_name="Level 1 Only", index=False)
                        continue
                    elif top_level == "Learning Objectives":
                        df = pd.DataFrame(sheet_data)
                        df.to_excel(writer, sheet_name="Learning Objectives", index=True)
                        continue
                    if "Values" in sheet_data:
                        temp_dict = OrderedDict([("Values", sheet_data["Values"])])
                        for k, v in sheet_data.items():
                            if k != "Values":
                                temp_dict[k] = v
                        sheet_data = temp_dict
                    for bottom_level, table_data in sheet_data.items():
                        try:
                            sortby_index = SORTBY_OPTIONS.index(sortby)
                        except ValueError:
                            print("Invalid sortby option")
                            sortby_index = 0
                        match sortby_index:
                            case 1: #Alphabetical (A-Z)
                                table_data = sorted(table_data, key=lambda i: i[bottom_level])
                            case 2: #Alphabetical (Z-A)
                                table_data = sorted(table_data, key=lambda i: i[bottom_level], reverse=True)
                            case _: #None
                                pass
                        print(f"{bottom_level}: {table_data}")
                        df = pd.DataFrame(table_data)
                        df.to_excel(writer, sheet_name=top_level, startrow=last_row, index=False)
                        last_row += df.shape[0] + 2
            print(f"EXPORT: Excel file '{file_path}' created successfully.")