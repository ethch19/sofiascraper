import json
import os
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, "sample-data")

def dfs(struct, path=None, depth=None):
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
        v = tuple([item for item in path if not isinstance(item, int)])
        if len(str(v[0])) == 40: #check for uuid
            v = tuple(list(v)[1:]) 
        if v not in depth:
            depth[v] = set()
        depth[v].add(struct)
    return depth

dir_name = f"COMMON_{int(round(time.time()))}"
save_dir = os.path.join(script_dir, dir_name)
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

for f in os.listdir(data_dir):
    path = os.path.join(data_dir, f)
    filename = os.fsdecode(f)
    if filename.endswith(".json"):
        with open(path, "r") as file:
            print(f"------ START File: {f} ------")
            json_d = json.load(file)
            data = dfs(json_d)
            new_path = os.path.join(save_dir, f"{f[:-5]}_COMMON.txt")
            with open(new_path, "w") as new_file:
                for k, v in data.items():
                    new_file.write(f"{k}\n")
                    for q in v:
                        new_file.write(f"{q}\n")
                    new_file.write("\n")
    print(f"------ END File ------")


