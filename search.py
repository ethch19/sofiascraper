import json
import os
import time
from exporter import get_responses, get_files

COMMON_VALUES = ["code"]

def dfs(struct, path=None, depth=None, closure=True):
    if path is None:
        path = []
    if depth is None:
        depth = {}
    if isinstance(struct, dict):
        for p, q in struct.items():
            dfs(q, path+[p], depth)
    elif isinstance(struct, list):
        for x, y in enumerate(struct):
            dfs(y, path+[x], depth)
    else:
        if not closure:
            v = str(path)
            if v not in depth:
                depth[v] = set()
            depth[v].add(struct)
        else:
            depth = common_search_closure(struct, path, depth)
    return depth

def common_search_closure(struct, path, depth):
    v = [item for item in path if not isinstance(item, int)]
    if len(str(v[0])) == 40: #check for uuid
        v = list(v)[1:]
    v = '>'.join(v)
    if v not in depth:
        depth[v] = set()
    depth[v].add(str(struct))
    return depth

def create_common_files(save_dir, response, start_with="responses_"):
    folder_path = start_with+response
    for f in os.listdir(folder_path):
        path = os.path.join(folder_path, f)
        filename = os.fsdecode(f)
        if filename.endswith(".json"):
            with open(path, "r") as file:
                print(f"------ START File: {f} ------")
                json_d = json.load(file)
                data = dfs(json_d)
                for k in data:
                    if isinstance(data[k], set):
                        data[k] = list(data[k])
                new_path = os.path.join(save_dir, f"{filename[:-5]}.json")
                with open(new_path, "w") as new_file:
                    json.dump(data, new_file, indent=4)
        print(f"------ END File ------")

def common_values(save_dir, response, start_with="COMMON_", separator="-"):
    folder_path = start_with+response
    for f in os.listdir(folder_path):
        file_path = os.path.join(folder_path, f)
        with open(file_path, "r") as file:
            json_data = json.load(file)
        for i in COMMON_VALUES:
            if i in json_data:
                values = json_data[i]
                new_values = {}
                for p in values:
                    if i == "code":
                        split = p.split(separator)
                        for k in range(len(split)):
                            key = separator.join(split[:k+1])
                            if key not in new_values:
                                new_values[key] = 0
                            new_values[key] += 1
                new_values = {k: v for k, v in new_values.items() if v > 1}
                new_path = os.path.join(save_dir, f"{i}_VALUES.json")
                with open(new_path, "w") as file:
                    json.dump(new_values, file, indent=4)

if __name__ == "__main__":
    responses = get_responses()
    path_dict = get_files(responses)
    for i in responses:
        dir_name = f"COMMON_{i}"
        save_dir = os.path.join('.', dir_name)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        create_common_files(save_dir, i)
        common_values(save_dir, i)