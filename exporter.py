import os
import json
import pytz
from datetime import datetime
from anytree import Node, PreOrderIter
from anytree.search import find
from collections import deque
import pandas as pd

json_name_dict = ["user", "curriculum-groups", "bundle-settings", "curriculum", "resources", "notes", "attachments", "learning-events", "calendar-events", "clinical"]

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
                file_name = file_sep[1]
                if file_name == uuid_search:
                    with open(file_path, "r") as f:
                        json_dict = json.load(f)
                        uuid = str(json_dict['curriculum'])
                elif file_name == uuid:
                    with open(file_path, "r") as f:
                        json_dict = json.load(f)
                        if "user_schema" in json_dict:
                            folder_dict["schemas"] = file_path
                        else:
                            if len(file_sep) > 2:
                                folder_dict["items-cache"] = file_path
                                continue
                            folder_dict["items"] = file_path
                            save_dir = os.path.join(folder_path, file_split[0]+"_cache"+file_split[1])
                            if not os.path.isfile(save_dir):
                                flip_dict_keys(file_path, save_dir)
                                folder_dict["items-cache"] = save_dir
                        continue
                folder_dict[file_name] = file_path
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
    root = Node(tree_dict[root]["title"], parent=None, obj=tree_dict[root])
    queue = deque([root])
    while queue:
        node = queue.popleft()
        if node.obj["children"] == None:
            continue
        for x in node.obj["children"]:
            title = tree_dict[x]["title"]
            #title = (title[:20] + "..") if len(title) > 20 else title
            child_node = Node(title, parent=node, obj=tree_dict[x])
            queue.append(child_node)
    return root

def properties(root_node, node_id):
    return find(root_node, filter_=lambda node: node.obj["uuid"] == node_id)

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

def extract_paths(node, code_filter):
    paths = []
    for leaf in PreOrderIter(node, filter_=lambda n: n.is_leaf and n.obj and n.obj["code"].startswith(code_filter)):
        path = []
        current = leaf
        while current:
            path.append(current)
            current = current.parent
        paths.append(path[::-1])  # Reverse to get root to leaf order
    return paths

def level_flattening(paths):
    data_dict = {}
    for path in paths:
        level1_topic = path[1].topic if len(path) > 1 else None
        if level1_topic not in data_dict:
            data_dict[level1_topic] = []
        entry = {
            'Groupings/Tags': ' > '.join([n.topic for n in path[2:-1]]),  # Combine intermediate levels starting from level 2
            'Content': path[-1].text,
            'Module': path[-1].module,
            'Code': path[-1].code
        }
        data_dict[level1_topic].append(entry)
    return data_dict

def excel_exporter(file_path, data_dict, root_node):
    with pd.ExcelWriter(file_path) as writer:
        for level1_topic, data in data_dict.items():
            df = pd.DataFrame(data)
            startrow = writer.sheets[root_node.topic].max_row + 2 if writer.sheets[root_node.topic].max_row > 0 else 0
            df.to_excel(writer, sheet_name=root_node.topic, startrow=startrow, index=False)
            worksheet = writer.sheets[root_node.topic]
            worksheet.write(startrow - 1, 0, level1_topic)  # Write the title for each table
    print(f"Excel file '{file_path}' created successfully.")


if __name__ == "__main__":
    responses = get_responses()
    paths = get_files(responses)
    print(paths)
    print(epoch_to_datetime(float(next(iter(paths)))))

    get_curriculum(paths, "1726788990")