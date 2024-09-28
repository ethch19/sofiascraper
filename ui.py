import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from PIL import Image, ImageTk
from exporter import *
from scraper import *
from anytree import Node, find_by_attr, RenderTree
import re
import asyncio

MIN_HEIGHT = 700
MIN_WIDTH = 400
START_HEIGHT = 1000
START_WIDTH = 800
EXPORT_WINDOW_HEIGHT = 500
EXPORT_WINDOW_WIDTH = 600

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.abspath(".")

class CheckboxTreeview(ttk.Treeview):
    def __init__(self, master=None, **kwargs):
        ttk.Treeview.__init__(self, master, **kwargs)
        self.im_checked = self.image_config(os.path.join(base_path, "img", "checked.png"), 20, 20)
        self.im_unchecked = self.image_config(os.path.join(base_path, "img", "unchecked.png"), 20, 20)
        self.im_tristate = self.image_config(os.path.join(base_path, "img", "tristate.png"), 20, 20)
        self.tag_configure("unchecked", image=self.im_unchecked)
        self.tag_configure("tristate", image=self.im_tristate)
        self.tag_configure("checked", image=self.im_checked)
        self.tag_configure('has_children', foreground="#004FFF")
        self.bind("<Button-1>", self.box_click, True)
        self.bind("<Return>", self.check_items, False)
        self.bind("<<TreeviewSelect>>", self.on_select)
        self.bind("<<TreeviewOpen>>", self.on_open)
        self.check_hidden = tk.BooleanVar(value=False)
        self.prop_node_id = tk.StringVar()
        self.responses = get_responses()
        self.time_responses = [epoch_to_datetime(float(x)) for x in self.responses]
        self.loop = asyncio.get_event_loop()

    def get_checked(self):
        checked_nodes = self.tag_has("checked")
        tristate_nodes = self.tag_has("tristate")
        if not checked_nodes:
            return None
        nodes = {}
        print(checked_nodes)
        print(tristate_nodes)

        def add_node(node):
            if node.name not in nodes:
                nodes[node.name] = Node(name=node.name, obj=node.obj)
            parent = node.parent
            if parent:
                if parent.name in checked_nodes or parent.name in tristate_nodes:
                    if parent.name not in nodes:
                        if parent.is_root:
                            nodes[parent.name] = Node(name=parent.name, obj=parent.obj)
                        else:
                            add_node(parent)
                    nodes[node.name].parent = nodes[parent.name]

        for item in checked_nodes:
            node = find_by_attr(self.node, item)
            if node:
                add_node(node)

        for node in nodes.values():
            node.children = tuple(child for child in node.children if child.name in checked_nodes or child.name in tristate_nodes)

        root_nodes = [node for node in nodes.values() if node.is_root]
        if not root_nodes:
            return None
        root_node = root_nodes[0]
        title = root_node.obj["title"]
        print(f"Rootnode title: {title}")
        for pre, fill, node in RenderTree(root_node):
            print("%s%s" % (pre, node.name))
        print(nodes.keys())
        return root_node

    def image_config(self, file_path, width, height):
        img = Image.open(file_path)
        new_img = img.resize((width, height), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(new_img)

    def fetch_response(self, root, mainwindow_callback):
        print("Fetching response")
        LoginWindow.start_login(root, self.response_callback, mainwindow_callback)
    
    def response_callback(self):
        self.responses = get_responses()
        self.time_responses = [epoch_to_datetime(float(x)) for x in self.responses]

    def update_tree(self, *args):
        response = args[0].get()
        curriculum = args[1]
        if int(curriculum) < 0 or response == "":
            print("Empty")
            return
        if response != "":
            dt = str(datetime_to_epoch(response))
            print(f"Changed to {dt}, {curriculum}")
            self.node = get_tree([dt], curriculum)
            if len(self.get_children()) > 0:
                self.delete(*self.get_children())
            self.insert_tree("", self.node)
            self.item(self.node.name, open=True)

    def insert_tree(self, parent, node):
        new_node = self.insert(parent, "end", iid=node.name, text=node.obj["title"], values=(len(node.children)))
        for c in node.children:
            self.insert_tree(node.name, c)
    
    def insert(self, parent, index, iid=None, **kwargs):
        if not "tags" in kwargs:
            kwargs["tags"] = ["unchecked"]
        elif not ("unchecked" in kwargs["tags"] or "checked" in kwargs["tags"] or "tristate" in kwargs["tags"]):
            kwargs["tags"] = ["unchecked"]
        ttk.Treeview.insert(self, parent, index, iid, **kwargs)
        self.update_child_tags(parent)

    def check_descendant(self, item):
        children = self.get_children(item)
        self.item(item, option='open')
        if self.check_hidden.get() or self.item(item, option='open'):
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
        print(self.item(item, option='open'))
        if self.check_hidden.get() or self.item(item, option='open'):
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
            item = self.identify_row(y)
            self.select_item(item)

    def select_item(self, iid):
        tags = self.item(iid, "tags")
        if ("unchecked" in tags) or ("tristate" in tags):
            self.check_ancestor(iid)
            self.check_descendant(iid)
        else:
            self.uncheck_descendant(iid)
            self.uncheck_ancestor(iid)

    def is_descendant(self, item, ancestor):
        if item == ancestor:
            return False
        if item in self.get_children(ancestor):
            return True
        for c in self.get_children(ancestor):
            if self.is_descendant(item, c):
                return True

    def check_items(self, event):
        for i in self.selection():
            self.select_item(i)

    def on_select(self, event):
        self.unbind("<<TreeviewSelect>>")
        selected_items = self.selection()
        visible_items = [item for item in selected_items if self.is_visible(item)]
        self.selection_set(visible_items)
        if len(visible_items) == 1:
            self.prop_node_id.set(visible_items[0])
        self.after(10, lambda: self.bind("<<TreeviewSelect>>", self.on_select))

    def on_open(self, event):
        selected_item = self.focus()
        for child in self.get_children(selected_item):
            current_tags = self.item(child, "tags")
            if self.get_children(child):
                new_tags = current_tags + ("has_children",)
                self.item(child, tags=new_tags)

    def update_child_tags(self, parent):
        for child in self.get_children(parent):
            current_tags = self.item(child, "tags")
            if self.get_children(child):
                new_tags = current_tags + ("has_children",)
                self.item(child, tags=new_tags)

    def is_visible(self, item):
        parent = self.parent(item)
        while parent:
            if not self.item(parent, 'open'):
                return False
            parent = self.parent(parent)
        return True

    def update_properties(self):
        if self.prop_node_id is None:
            return
        return properties(self.node, self.prop_node_id.get())

class PropertyTreeview(ttk.Treeview):
    def __init__(self, master=None, **kwargs):
        ttk.Treeview.__init__(self, master, **kwargs)

    def get_properties(self, node):
        if node is None:
            return
        data_dict = node.obj
        if len(self.get_children()) > 0:
            self.delete(*self.get_children())
        for key, value in data_dict.items():
            if value is None:
                value = ""
            else:
                value = (str(value),)
            self.insert("", "end", text=key, values=value)

class PropagateCombobox(ttk.Combobox):
    def __init__(self, master=None, **kwargs):
        ttk.Combobox.__init__(self, master, **kwargs)

    def update_list(self, *args):
        response = args[0].get()
        dt = str(datetime_to_epoch(response))
        paths = get_files([dt])
        if dt in paths:
            _, self["values"] = get_curriculum(paths[dt])

class ScrollableFrame(ttk.Frame):
    def __init__(self, master=None, **kwargs):
        ttk.Frame.__init__(self, master, **kwargs)
        self.canvas = tk.Canvas(self, width=380, height=150)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        self.frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        
        self.frame.bind("<Configure>", self.on_frame_configure)
        
    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

class ExpandableTable(ttk.Frame):
    def __init__(self, master=None, **kwargs):
        ttk.Frame.__init__(self, master, **kwargs)
        self.rows = 0
        self.row_widgets = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.create_table()

    def create_table(self):
        ttk.Label(self, text="Property", width=15).grid(row=0, column=0, padx=10, pady=5)
        ttk.Label(self, text="Criteria", width=15).grid(row=0, column=1, padx=10, pady=5)
        ttk.Label(self, text="Value", width=15).grid(row=0, column=2, padx=10, pady=5)
        self.add_row()

    def add_row(self):
        self.rows += 1
        options = ["option1", "option2", "option3"]

        combobox1 = ttk.Combobox(self, justify="left", height="20", state="readonly", values=options, width=15)
        combobox1.grid(row=self.rows, column=0, padx=10, pady=5)
        
        combobox2 = ttk.Combobox(self, justify="left", height="20", state="readonly", values=options, width=15)
        combobox2.grid(row=self.rows, column=1, padx=10, pady=5)

        combobox3 = ttk.Combobox(self, justify="left", height="20", state="readonly", values=options, width=15)
        combobox3.grid(row=self.rows, column=2, padx=10, pady=5)

        btn_img = ExpandableTable.image_config(os.path.join(base_path, "img", "cross.png"), 20, 20)
        delete_btn = ttk.Button(self, image=btn_img, command=lambda r=self.rows: self.delete_row(r), width=5)
        delete_btn.image = btn_img
        delete_btn.grid(row=self.rows, column=3, padx=5, pady=5)
        
        self.row_widgets[self.rows] = (combobox1, combobox2, combobox3, delete_btn)

    def image_config(file_path, width, height):
        img = Image.open(file_path)
        new_img = img.resize((width, height), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(new_img)

    def delete_row(self, row):
        for widget in self.row_widgets[row]:
            widget.destroy()

        del self.row_widgets[row]

class ExportWindow(tk.Toplevel):
    def __init__(self, tree, file_type, master=None, *args, **kwargs):
        tk.Toplevel.__init__(self, master=master, *args, **kwargs)
        self.tree = tree
        self.file_type = file_type

        self.title("Export Options")
        self.geometry(f"{EXPORT_WINDOW_WIDTH}x{EXPORT_WINDOW_HEIGHT}")
        self.minsize(width=EXPORT_WINDOW_WIDTH, height=EXPORT_WINDOW_HEIGHT)
        self.attributes('-topmost', True)
        self.grab_set()
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.create_widgets()

    def create_widgets(self):
        sortby_frame = ttk.Labelframe(self, text="Sort By", padding="10 10 10 10")
        sortby_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
        sortby_frame.rowconfigure(0, weight=1)
        sortby_frame.columnconfigure(0, weight=1)

        self.sortby = tk.StringVar(value="Alphabetical (A-Z)")
        sortby_box = ttk.Combobox(sortby_frame, justify="left", height="20", state="readonly", textvariable=self.sortby, values=SORTBY_OPTIONS, width=15)
        sortby_box.grid(row=0, column=0, padx=5, pady=5)

        flatten_frame = ttk.Labelframe(self, text="Flattening Algorithm", padding="10 10 10 10")
        flatten_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
        flatten_frame.rowconfigure(0, weight=1)
        flatten_frame.columnconfigure(0, weight=1)

        self.flatten = tk.StringVar(value="Intermediate-level")
        flatten_box = ttk.Combobox(flatten_frame, justify="left", height="20", state="readonly", textvariable=self.flatten, values=FLATTEN_OPTIONS, width=15)
        flatten_box.grid(row=0, column=0, padx=5, pady=5)

        export_frame = ttk.Labelframe(self, text="Export All/Selected", padding="10 10 10 10")
        export_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
        export_frame.rowconfigure(0, weight=1)
        export_frame.columnconfigure(1, weight=1)

        self.export_selection = tk.StringVar(value="All")
        radio1 = ttk.Radiobutton(export_frame, text="All", variable=self.export_selection, value="All")
        radio1.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        radio2 = ttk.Radiobutton(export_frame, text="Selected", variable=self.export_selection, value="Selected")
        radio2.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        lo_frame = ttk.Labelframe(self, text="Learning Objectives", padding="10 10 10 10")
        lo_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
        lo_frame.rowconfigure(0, weight=1)
        lo_frame.columnconfigure(0, weight=1)

        self.lo = tk.BooleanVar(value=True)
        self.lo_btn = ttk.Checkbutton(lo_frame, text="Include LO's", variable=self.lo)
        self.lo_btn.grid(row=0, column=0, sticky="NWSE", padx=10, pady=10)

        path_frame = ttk.Labelframe(self, text="Save Folder Location", padding="10 10 10 10")
        path_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
        path_frame.rowconfigure(0, weight=1)
        path_frame.columnconfigure(1, weight=1)

        self.folder_path = tk.StringVar(value=base_path) #os.path.expanduser("~")
        self.folder_entry = ttk.Entry(path_frame, state=tk.DISABLED, textvariable=self.folder_path)
        self.folder_entry.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        open_button = ttk.Button(path_frame, text="Open Folder", command=self.pick_folder)
        open_button.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        next_button = ttk.Button(self, text="Next", command=self.export)
        next_button.grid(row=2, column=0, columnspan=3, pady=10, sticky="S")
    
    def export(self):
        if self.export_selection.get() == "Selected":
            checked_root_node = self.tree.get_checked()
        else:
            checked_root_node = self.tree.node
        paths, spreadsheet_name = extract_paths(checked_root_node, self.lo.get())
        flattened_dict = level_flattening(paths, self.flatten.get())
        spreadsheet_name = re.sub(r'[<>:"/\\|?*\x00-\x1F\s]+', '_', spreadsheet_name)
        spreadsheet_name = spreadsheet_name + f"_{int(time.time())}"
        file_path = os.path.join(self.folder_entry.get(), spreadsheet_name)
        sofia_exporter(file_path, flattened_dict, self.sortby.get(), self.file_type)

    def pick_folder(self):
        folder_selected = filedialog.askdirectory(initialdir=self.folder_path.get())
        if folder_selected:
            self.folder_entry.configure(state = tk.NORMAL)
            if self.folder_entry.get():
                self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder_selected)
            self.folder_entry.configure(state = tk.DISABLED)

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Sofia Scraper")
        self.root.geometry(f"{START_WIDTH}x{START_HEIGHT}")
        self.root.minsize(width=MIN_WIDTH, height=MIN_HEIGHT)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=3)
        self.root.grid_rowconfigure(1, weight=1)

        self.create_widgets()

        self.root.mainloop()

    def create_widgets(self):
        self.treeview_frame = ttk.Frame(self.root, padding="10 10 10 10")
        self.treeview_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.treeview_frame.columnconfigure(0, weight=1)
        self.treeview_frame.rowconfigure(0, weight=1)

        self.tree = CheckboxTreeview(self.treeview_frame, show="tree headings", selectmode="extended", columns=("children"))
        self.tree.column("#0", stretch=True)
        self.tree.column("children", width=100, stretch=False)
        self.tree.heading("#0", text="Node")
        self.tree.heading("children", text="Children")
        self.tree.grid(row=0, column=0, sticky="NSWE")

        self.combobox_frame = ttk.Frame(self.root, padding="10 10 10 10", height=40)
        self.combobox_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.combobox_frame.grid_propagate(False)
        self.combobox_frame.columnconfigure(0, weight=1)
        self.combobox_frame.columnconfigure(1, weight=1)

        self.current_response = tk.StringVar()
        self.response_box = ttk.Combobox(self.combobox_frame, justify="left", height="20", state="readonly", values=self.tree.time_responses, textvariable=self.current_response)
        self.response_box.grid(row=0, column=0, ipadx=5, ipady=5, sticky="NEW")

        self.current_curriculum = tk.StringVar()
        self.curriculum_box = PropagateCombobox(self.combobox_frame, justify="left", height="20", state="readonly", values="", textvariable=self.current_curriculum)
        self.curriculum_box.grid(row=0, column=1, ipadx=5, ipady=5, sticky="NEW")

        self.left_frame = ttk.Frame(self.root, padding="10 10 10 10")
        self.left_frame.grid(row=0, rowspan=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.left_frame.rowconfigure(0, weight=1)
        self.left_frame.rowconfigure(1, weight=5)
        self.left_frame.columnconfigure(0, weight=1)
        
        self.label_frame = ttk.Frame(self.left_frame)
        self.label_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N))
        self.label_frame.rowconfigure(0, weight=1)
        self.label_frame.rowconfigure(1, weight=1)
        self.label_frame.columnconfigure(0, weight=1)

        self.control_frame = ttk.Labelframe(self.label_frame, text="Control Panel")
        self.control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=5)
        self.control_frame.columnconfigure(0, weight=1)
        self.control_frame.columnconfigure(1, weight=1)
        self.control_frame.columnconfigure(2, weight=1)
        self.control_frame.rowconfigure(0, weight=1)

        self.check_hidden_box = ttk.Checkbutton(self.control_frame, text="Select hidden items", variable=self.tree.check_hidden)
        self.check_hidden_box.grid(row=0, column=0, ipadx=5, ipady=5, pady=5)

        self.response_btn = ttk.Button(self.control_frame, text="Get response", command=lambda: self.tree.fetch_response(self.root, self.response_callback))
        self.response_btn.grid(row=0, column=1, ipadx=5, ipady=5, pady=5)

        self.export_frame = ttk.Labelframe(self.label_frame, text="Export to Files")
        self.export_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N), pady=5)
        self.export_frame.columnconfigure(0, weight=1)
        self.export_frame.columnconfigure(1, weight=1)
        self.export_frame.columnconfigure(2, weight=1)
        self.export_frame.rowconfigure(0, weight=1)

        self.current_convert_type = tk.StringVar(value="xlsx")
        self.export_btn = ttk.Button(self.export_frame, text="Export", padding="5 5 5 5", name="export", command=self.open_export_window)
        self.export_btn.grid(row=0, column=0, columnspan=2, ipadx=5, ipady=5, padx=5, pady=5)
        self.convert_type_box = ttk.Combobox(self.export_frame, justify="left", height="20", state="readonly", values=FILE_TYPES, textvariable=self.current_convert_type)
        self.convert_type_box.grid(row=0, column=2, ipadx=5, ipady=5, padx=5, pady=5)

        self.current_response.trace_add("write", lambda *args: self.curriculum_box.update_list(self.current_response))
        self.current_response.trace_add("write", lambda *args : self.tree.update_tree(self.current_response, self.curriculum_box.current()))
        self.current_curriculum.trace_add("write", lambda *args : self.tree.update_tree(self.current_response, self.curriculum_box.current()))    

        self.properties_frame = ttk.Frame(self.left_frame)
        self.properties_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        self.properties_frame.columnconfigure(0, weight=1)
        self.properties_frame.rowconfigure(0, weight=1)

        self.properties_tree = PropertyTreeview(self.properties_frame, show="tree headings", selectmode="browse", columns=("value"))
        self.properties_tree.column("#0", width=100, stretch=False)
        self.properties_tree.column("value", stretch=True)
        self.properties_tree.heading("#0", text="Property")
        self.properties_tree.heading("value", text="Value")
        self.properties_tree.grid(row=0, column=0, sticky="NSWE")

        self.tree.prop_node_id.trace_add("write", lambda *args: self.properties_tree.get_properties(self.tree.update_properties()))

        if len(self.tree.time_responses) > 0:
            self.current_response.set(self.tree.time_responses[0])
            if len(self.curriculum_box["values"]) > 0:
                self.current_curriculum.set(self.curriculum_box["values"][0])
                self.tree.update_tree(self.current_response, self.curriculum_box.current())

    def open_export_window(self):
        self.export_window = ExportWindow(master=self.root, tree=self.tree, file_type=self.current_convert_type.get())

    def response_callback(self):
        self.response_box['values'] = self.tree.time_responses
        self.current_response.set(self.tree.time_responses[0])

if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)