import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from PIL import Image, ImageTk
from exporter import *
from scraper import *

MIN_HEIGHT = 700
MIN_WIDTH = 400
START_HEIGHT = 1000
START_WIDTH = 800
EXPORT_WINDOW_HEIGHT = 500
EXPORT_WINDOW_WIDTH = 600
CONVERT_TYPES = ["csv", "xlsx"]

class CheckboxTreeview(ttk.Treeview):
    def __init__(self, master=None, **kwargs):
        ttk.Treeview.__init__(self, master, **kwargs)
        self.im_checked = self.image_config("checked.png", 20, 20)
        self.im_unchecked = self.image_config("unchecked.png", 20, 20)
        self.im_tristate = self.image_config("tristate.png", 20, 20)
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

    def image_config(self, file_path, width, height):
        img = Image.open(file_path)
        new_img = img.resize((width, height), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(new_img)

    def fetch_response(self, root):
        print("Fetching response")
        loginwindow = LoginWindow.start_login(root)
        self.responses = get_responses()
        self.time_responses = [epoch_to_datetime(float(x)) for x in self.responses]
        self.update_responsebox()

    def update_responsebox(self):
        response_box['values'] = self.time_responses
        current_response.set(self.time_responses[0])

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
            self.item(self.node.obj["uuid"], open=True)

    def insert_tree(self, parent, node):
        new_node = self.insert(parent, "end", iid=node.obj["uuid"], text=node.name, values=(len(node.children)))
        for c in node.children:
            self.insert_tree(node.obj["uuid"], c)
    
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
        options = ["Option 1", "Option 2", "Option 3"]
        
        combobox1 = ttk.Combobox(self, justify="left", height="20", state="readonly", values=options, width=15)
        combobox1.grid(row=self.rows, column=0, padx=10, pady=5)
        
        combobox2 = ttk.Combobox(self, justify="left", height="20", state="readonly", values=options, width=15)
        combobox2.grid(row=self.rows, column=1, padx=10, pady=5)

        combobox3 = ttk.Combobox(self, justify="left", height="20", state="readonly", values=options, width=15)
        combobox3.grid(row=self.rows, column=2, padx=10, pady=5)

        btn_img = ExpandableTable.image_config("cross.png", 20, 20)
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

def pick_folder(folder_entry):
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        folder_entry.configure(state = tk.NORMAL)
        if folder_entry.get():
            folder_entry.delete(0, tk.END)
        folder_entry.insert(0, folder_selected)
        folder_entry.configure(state = tk.DISABLED)

def open_export_window():
    export_window = tk.Toplevel()
    export_window.title("Export Options")
    export_window.geometry(f"{EXPORT_WINDOW_WIDTH}x{EXPORT_WINDOW_HEIGHT}")
    export_window.minsize(width=EXPORT_WINDOW_WIDTH, height=EXPORT_WINDOW_HEIGHT)
    export_window.attributes('-topmost', True)
    export_window.grab_set()
    export_window.grid_columnconfigure(2, weight=1)
    export_window.grid_rowconfigure(2, weight=1)

    groupby_frame = ttk.Labelframe(export_window, text="Group By", padding="10 10 10 10")
    groupby_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
    groupby_frame.rowconfigure(0, weight=1)
    groupby_frame.columnconfigure(0, weight=1)

    scrollable_frame_1 = ScrollableFrame(groupby_frame)
    scrollable_frame_1.grid(row=0, column=0, ipadx=5, ipady=5, sticky="NEW")

    groupby_table = ExpandableTable(scrollable_frame_1.frame)
    groupby_table.pack(fill=tk.BOTH, expand=True)

    add_row_button = ttk.Button(groupby_frame, text="Add Row", command=groupby_table.add_row)
    add_row_button.grid(row=1, column=0, pady=10, sticky="N")

    sortby_frame = ttk.Labelframe(export_window, text="Sort By", padding="10 10 10 10")
    sortby_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
    sortby_frame.rowconfigure(0, weight=1)
    sortby_frame.columnconfigure(0, weight=1)

    options = ["Alphabetical", "Created at", "Ascending", "Descending"]
    sortby_box = ttk.Combobox(sortby_frame, justify="left", height="20", state="readonly", values=options, width=15)
    sortby_box.grid(row=0, column=0, padx=5, pady=5)

    flatten_frame = ttk.Labelframe(export_window, text="Flattening Algorithm", padding="10 10 10 10")
    flatten_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
    flatten_frame.rowconfigure(0, weight=1)
    flatten_frame.columnconfigure(0, weight=1)

    options = ["Intermediate-level", "Top-level"]
    flatten_box = ttk.Combobox(flatten_frame, justify="left", height="20", state="readonly", values=options, width=15)
    flatten_box.grid(row=0, column=0, padx=5, pady=5)

    export_frame = ttk.Labelframe(export_window, text="Export All/Selected", padding="10 10 10 10")
    export_frame.grid(row=1, column=2, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
    export_frame.rowconfigure(0, weight=1)
    export_frame.columnconfigure(1, weight=1)

    export_selection = tk.StringVar(value="Selected")
    radio1 = ttk.Radiobutton(export_frame, text="All", variable=export_selection, value="All")
    radio1.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
    radio2 = ttk.Radiobutton(export_frame, text="Selected", variable=export_selection, value="Selected")
    radio2.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

    path_frame = ttk.Labelframe(export_window, text="Save Folder Location", padding="10 10 10 10")
    path_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
    path_frame.rowconfigure(0, weight=1)
    path_frame.columnconfigure(1, weight=1)

    folder_entry = ttk.Entry(path_frame, state=tk.DISABLED)
    folder_entry.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

    open_button = ttk.Button(path_frame, text="Open Folder", command=lambda: pick_folder(folder_entry))
    open_button.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

    next_button = ttk.Button(export_window, text="Next")
    next_button.grid(row=2, column=0, columnspan=3, pady=10, sticky="S")

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Sofia Scraper")
    root.geometry(f"{START_WIDTH}x{START_HEIGHT}")
    root.minsize(width=MIN_WIDTH, height=MIN_HEIGHT)
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=3)
    root.grid_rowconfigure(1, weight=1)

    treeview_frame = ttk.Frame(root, padding="10 10 10 10")
    treeview_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    treeview_frame.columnconfigure(0, weight=1)
    treeview_frame.rowconfigure(0, weight=1)

    tree = CheckboxTreeview(treeview_frame, show="tree headings", selectmode="extended", columns=("children"))
    tree.column("#0", stretch=True)
    tree.column("children", width=100, stretch=False)
    tree.heading("#0", text="Node")
    tree.heading("children", text="Children")
    tree.grid(row=0, column=0, sticky="NSWE")

    combobox_frame = ttk.Frame(root, padding="10 10 10 10", height=40)
    combobox_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
    combobox_frame.grid_propagate(False)
    combobox_frame.columnconfigure(0, weight=1)
    combobox_frame.columnconfigure(1, weight=1)

    current_response = tk.StringVar()
    response_box = ttk.Combobox(combobox_frame, justify="left", height="20", state="readonly", values=tree.time_responses, textvariable=current_response)
    response_box.grid(row=0, column=0, ipadx=5, ipady=5, sticky="NEW")

    current_curriculum = tk.StringVar()
    curriculum_box = PropagateCombobox(combobox_frame, justify="left", height="20", state="readonly", values="", textvariable=current_curriculum)
    curriculum_box.grid(row=0, column=1, ipadx=5, ipady=5, sticky="NEW")

    left_frame = ttk.Frame(root, padding="10 10 10 10")
    left_frame.grid(row=0, rowspan=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
    left_frame.rowconfigure(0, weight=1)
    left_frame.rowconfigure(1, weight=5)
    left_frame.columnconfigure(0, weight=1)
    
    label_frame = ttk.Frame(left_frame)
    label_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N))
    label_frame.rowconfigure(0, weight=1)
    label_frame.rowconfigure(1, weight=1)
    label_frame.columnconfigure(0, weight=1)

    control_frame = ttk.Labelframe(label_frame, text="Control Panel")
    control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=5)
    control_frame.columnconfigure(0, weight=1)
    control_frame.columnconfigure(1, weight=1)
    control_frame.columnconfigure(2, weight=1)
    control_frame.rowconfigure(0, weight=1)

    check_hidden_box = ttk.Checkbutton(control_frame, text="Select hidden items", variable=tree.check_hidden)
    check_hidden_box.grid(row=0, column=0, ipadx=5, ipady=5)

    response_btn = ttk.Button(control_frame, text="Get response", command=lambda: tree.fetch_response(root))
    response_btn.grid(row=0, column=1, ipadx=5, ipady=5)

    export_frame = ttk.Labelframe(label_frame, text="Export to Files")
    export_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N), pady=5)
    export_frame.columnconfigure(0, weight=1)
    export_frame.columnconfigure(1, weight=1)
    export_frame.columnconfigure(2, weight=1)
    export_frame.rowconfigure(0, weight=1)

    current_convert_type = tk.StringVar(value="csv")
    export_btn = ttk.Button(export_frame, text="Export", padding="5 5 5 5", name="export", command=open_export_window)
    export_btn.grid(row=0, column=0, columnspan=2, ipadx=5, ipady=5, padx=5, pady=5)
    convert_type_box = ttk.Combobox(export_frame, justify="left", height="20", state="readonly", values=CONVERT_TYPES, textvariable=current_convert_type)
    convert_type_box.grid(row=0, column=2, ipadx=5, ipady=5, padx=5, pady=5)

    current_response.trace_add("write", lambda *args: curriculum_box.update_list(current_response))
    current_response.trace_add("write", lambda *args : tree.update_tree(current_response, curriculum_box.current()))
    current_curriculum.trace_add("write", lambda *args : tree.update_tree(current_response, curriculum_box.current()))    

    properties_frame = ttk.Frame(left_frame)
    properties_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
    properties_frame.columnconfigure(0, weight=1)
    properties_frame.rowconfigure(0, weight=1)

    properties_tree = PropertyTreeview(properties_frame, show="tree headings", selectmode="browse", columns=("value"))
    properties_tree.column("#0", width=100, stretch=False)
    properties_tree.column("value", stretch=True)
    properties_tree.heading("#0", text="Property")
    properties_tree.heading("value", text="Value")
    properties_tree.grid(row=0, column=0, sticky="NSWE")

    tree.prop_node_id.trace_add("write", lambda *args: properties_tree.get_properties(tree.update_properties()))

    if len(tree.time_responses) > 0:
        current_response.set(tree.time_responses[0])
        if len(curriculum_box["values"]) > 0:
            current_curriculum.set(curriculum_box["values"][0])
            tree.update_tree(current_response, curriculum_box.current())

    root.mainloop()