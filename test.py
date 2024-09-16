import json

file_path = "test.json"

with open(file_path, "r") as file:
    first_line = file.readline().strip()

first_line_str = str(first_line)

json_obj = json.loads(first_line_str)

new_file_path = "converted_test.json"

with open(new_file_path, "w") as new_file:
    json.dump(json_obj, new_file, indent=4)
