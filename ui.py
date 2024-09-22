import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from exporter import get_responses, get_tree, get_curriculum, get_files

class CheckboxTreeview(ttk.Treeview):
    def __init__(self, master=None, **kwargs):
        ttk.Treeview.__init__(self, master, **kwargs)
        self.im_checked = self.image_config("checked.png", 20, 20)
        self.im_unchecked = self.image_config("unchecked.png", 20, 20)
        self.im_tristate = self.image_config("tristate.png", 20, 20)
        self.tag_configure("unchecked", image=self.im_unchecked)
        self.tag_configure("tristate", image=self.im_tristate)
        self.tag_configure("checked", image=self.im_checked)
        self.bind("<Button-1>", self.box_click, True)

    def image_config(self, file_path, width, height):
        img = Image.open(file_path)
        new_img = img.resize((width, height), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(new_img)

    def update_tree(self, *args):
        response = args[0].get()
        curriculum = args[1]
        print(f"Changed to {response}, {curriculum}")
        if int(curriculum) < 0 or response == "":
            print("Empty")
            return
        if response != "":
            node = get_tree([response], curriculum)
            if len(self.get_children()) > 0:
                self.delete(*self.get_children())
            self.insert_tree("", node)
            
    def insert_tree(self, parent, node):
        self.insert(parent, "end", iid=node.obj["uuid"], text=node.name, values=(len(node.children)))
        for c in node.children:
            self.insert_tree(node.obj["uuid"], c)
    
    def insert(self, parent, index, iid=None, **kwargs):
        if not "tags" in kwargs:
            kwargs["tags"] = ["unchecked"]
        elif not ("unchecked" in kwargs["tags"] or "checked" in kwargs["tags"] or "tristate" in kwargs["tags"]):
            kwargs["tags"] = ["unchecked"]
        ttk.Treeview.insert(self, parent, index, iid, **kwargs)

    def check_descendant(self, item):
        children = self.get_children(item)
        for iid in children:
            self.item(iid, tags=("checked",))
            self.check_descendant(iid)

    def check_ancestor(self, item):
        self.item(item, tags=("checked",))
        parent = self.parent(item)
        if parent:
            children = self.get_children(parent)
            b = ["checked" in self.item(c, "tags") for c in children]
            if False in b:
                self.tristate_parent(parent)
            else:
                self.check_ancestor(parent)

    def tristate_parent(self, item):
        self.item(item, tags=("tristate",))
        parent = self.parent(item)
        if parent:
            self.tristate_parent(parent)

    def uncheck_descendant(self, item):
        children = self.get_children(item)
        for iid in children:
            self.item(iid, tags=("unchecked",))
            self.uncheck_descendant(iid)

    def uncheck_ancestor(self, item):
        self.item(item, tags=("unchecked",))
        parent = self.parent(item)
        if parent:
            children = self.get_children(parent)
            b = ["unchecked" in self.item(c, "tags") for c in children]
            if False in b:
                self.tristate_parent(parent)
            else:
                self.uncheck_ancestor(parent)

    def box_click(self, event):
        x, y, widget = event.x, event.y, event.widget
        elem = widget.identify("element", x, y)
        if "image" in elem:
            # a box was clicked
            item = self.identify_row(y)
            tags = self.item(item, "tags")
            if ("unchecked" in tags) or ("tristate" in tags):
                self.check_ancestor(item)
                self.check_descendant(item)
            else:
                self.uncheck_descendant(item)
                self.uncheck_ancestor(item)

class PropagateCombobox(ttk.Combobox):
    def __init__(self, master=None, **kwargs):
        ttk.Combobox.__init__(self, master, **kwargs)

    def update_list(self, *args):
        response = args[0].get()
        paths = get_files(list(responses))
        if response in paths:
            _, self["values"] = get_curriculum(paths[response])

if __name__ == '__main__':
    responses = get_responses()

    root = tk.Tk()
    root.title("Sofia Scraper")
    root.geometry("400x800")
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)
    root.grid_rowconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=9)

    current_response = tk.StringVar()
    response_box = PropagateCombobox(root, justify="left", height="20", state="readonly", values=responses, textvariable=current_response)
    response_box.grid(row=0, column=0, padx=10, pady=10, sticky="NSEW")
    

    current_curriculum = tk.StringVar()
    curriculum_box = PropagateCombobox(root, justify="left", height="20", state="readonly", values="", textvariable=current_curriculum)
    curriculum_box.grid(row=0, column=1, padx=10, pady=10, sticky="NSEW")

    current_response.trace_add("write", lambda *args: curriculum_box.update_list(current_response))

    t = CheckboxTreeview(root, show="tree headings", selectmode="browse", columns=("children"))
    t.heading("#0", text="Node")
    t.heading("children", text="Children Count")
    t.grid(column=0, row=1, columnspan=2, padx=10, pady=10, sticky="NSEW")

    current_response.trace_add("write", lambda *args : t.update_tree(current_response, curriculum_box.current()))
    current_curriculum.trace_add("write", lambda *args : t.update_tree(current_response, curriculum_box.current()))

    root.mainloop()