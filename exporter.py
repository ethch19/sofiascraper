import os
import json
import pytz
from datetime import datetime

json_name_dict = ["user", "curriculum-groups", "bundle-settings", "curriculum", "resources", "notes", "attachments", "learning-events", "calendar-events", "clinical"]

def rename_files(names_dict, directory=".", start_with="responses_", separator="_", uuid_search="user"):
    path_dict = {}
    for folder in sorted(os.listdir(directory)):
        if folder.startswith(start_with):
            folder_dict = {}
            uuid = ""
            for file in sorted(os.listdir(folder)):
                file_path = os.path.join(folder, file)
                if os.path.isfile(file_path):
                    file_name = os.path.splitext(file)[0].split(separator)[1]
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
                                folder_dict["items"] = file_path
                            continue
                    folder_dict[file_name] = file_path
            folder_dict['uuid-curriculum'] = uuid
            path_dict[folder.split("_")[1]] = folder_dict
    return path_dict

def epoch_to_datetime(epoch, timezone="Europe/London"):
    timezone = pytz.timezone(timezone)
    return datetime.fromtimestamp(epoch).astimezone(timezone).strftime('%Y-%m-%d %H:%M:%S %Z %z')

script_dir = os.path.dirname(os.path.abspath(__file__))

paths = rename_files(json_name_dict)
print(paths)
print(epoch_to_datetime(float(next(iter(paths)))))