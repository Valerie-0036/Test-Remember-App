import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import csv
import psycopg2
from PIL import Image, ImageTk
import os
import random

class FlashcardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Memory Test App")
        self.geometry("1050x700")
        
        self.db_conn = None
        self.test_data = []      # Data for the active test
        self.temp_set_data = []  # Data currently being previewed/edited
        self.current_q_index = 0
        self.current_set_name = ""
        
        self.show_db_login()

    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

    # ===================== DATABASE LOGIN =====================
    def show_db_login(self):
        self.clear_window()
        frame = tk.Frame(self)
        frame.pack(expand=True)
        
        tk.Label(frame, text="PostgreSQL Login (Port 5432)", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=10)
        
        tk.Label(frame, text="Username:").grid(row=1, column=0, pady=5)
        self.user_entry = tk.Entry(frame)
        self.user_entry.grid(row=1, column=1)
        
        tk.Label(frame, text="Password:").grid(row=2, column=0, pady=5)
        self.pass_entry = tk.Entry(frame, show="*")
        self.pass_entry.grid(row=2, column=1)
        
        tk.Label(frame, text="Database:").grid(row=3, column=0, pady=5)
        self.db_entry = tk.Entry(frame)
        self.db_entry.grid(row=3, column=1)
        
        tk.Button(frame, text="Connect", command=self.connect_db, width=20, bg="lightblue").grid(row=4, column=0, columnspan=2, pady=20)

    def connect_db(self):
        try:
            self.db_conn = psycopg2.connect(
                host="localhost",
                port="5432",
                user=self.user_entry.get(),
                password=self.pass_entry.get(),
                database=self.db_entry.get()
            )
            self.init_db()
            self.show_main_menu()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def init_db(self):
        cursor = self.db_conn.cursor()
        
        # Make sure question_text is included in the base table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_items (
                id SERIAL PRIMARY KEY,
                set_name VARCHAR(100),
                item_type VARCHAR(10),
                item_content TEXT,
                description TEXT,
                question_text TEXT
            )
        """)
        self.db_conn.commit()

        # Fallback to add column if table exists from an older version without it
        try:
            cursor.execute("ALTER TABLE test_items ADD COLUMN question_text TEXT")
            self.db_conn.commit()
        except psycopg2.Error:
            self.db_conn.rollback()

    # ===================== MAIN MENU =====================
    def show_main_menu(self):
        self.clear_window()
        frame = tk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=30)
        
        tk.Label(frame, text="Main Menu", font=("Arial", 18, "bold")).pack(pady=10)
        
        create_btn_frame = tk.Frame(frame)
        create_btn_frame.pack(pady=5)
        tk.Button(create_btn_frame, text="Create New Set from CSV", command=self.load_csv, width=28, bg="lightgreen").pack(side=tk.LEFT, padx=5)
        tk.Button(create_btn_frame, text="Create Combined Set (Text + Images)", command=self.create_combined_set, width=32, bg="#b2f2bb").pack(side=tk.LEFT, padx=5)
        
        tk.Frame(frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=15)
        
        tk.Label(frame, text="Select Set(s) to Test (Hold Ctrl/Shift to combine multiple sets):", font=("Arial", 12)).pack()
        
        list_frame = tk.Frame(frame)
        list_frame.pack(pady=10)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.set_listbox = tk.Listbox(list_frame, width=55, height=10, yscrollcommand=scrollbar.set, selectmode=tk.EXTENDED)
        self.set_listbox.pack(side=tk.LEFT, fill=tk.BOTH)
        scrollbar.config(command=self.set_listbox.yview)
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT DISTINCT set_name FROM test_items WHERE set_name IS NOT NULL ORDER BY set_name")
            sets = cursor.fetchall()
            for s in sets:
                if s[0]: 
                    self.set_listbox.insert(tk.END, s[0])
        except psycopg2.Error:
            self.db_conn.rollback()
            
        tk.Button(frame, text="Start Test (Selected Set / Combined)", command=self.start_test_from_menu, width=35, bg="lightblue").pack(pady=8)
        tk.Button(frame, text="Delete Selected Set(s)", command=self.delete_set_from_menu, width=35, bg="#ffcccb").pack(pady=5)

    def _parse_csv_and_images(self):
        filepath = filedialog.askopenfilename(title="Select CSV File", filetypes=[("CSV Files", "*.csv")])
        if not filepath:
            return []
        
        try:
            with open(filepath, 'r', encoding='utf-8-sig', errors='ignore') as f:
                reader = csv.reader(f)
                data = [row for row in reader if any(cell.strip() for cell in row)]
                
            if not data:
                messagebox.showerror("CSV Error", "The selected CSV file is empty.")
                return []
            
            # Optional header check
            if len(data[0]) >= 2 and data[0][0].strip().lower() == "question" and data[0][1].strip().lower() in ("answer", "image", "item"):
                data = data[1:]
                if not data:
                    messagebox.showerror("CSV Error", "The CSV file only contains header rows with no actual data items.")
                    return []

            cols = len(data[0]) if data else 0
            items = []
            image_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')

            if cols == 3:
                for row_idx, row in enumerate(data, start=1):
                    if len(row) < 3:
                        messagebox.showwarning("Row Warning", f"Row {row_idx} has fewer than 3 columns and was skipped.")
                        continue
                    question_text = row[0].strip()
                    img_path = row[1].strip()
                    desc = row[2].strip()
                    items.append({
                        'type': 'image', 
                        'content': img_path, 
                        'desc': desc, 
                        'question': question_text
                    })
            elif cols == 2:
                for row_idx, row in enumerate(data, start=1):
                    if len(row) < 2:
                        continue
                    content, desc = row[0].strip(), row[1].strip()
                    if content.lower().endswith(image_exts) and os.path.exists(content):
                        items.append({'type': 'image', 'content': content, 'desc': desc, 'question': ''})
                    else:
                        items.append({'type': 'text', 'content': content, 'desc': desc, 'question': ''})
            elif cols == 1:
                descriptions = [row[0].strip() for row in data]
                image_paths = filedialog.askopenfilenames(
                    title=f"Select {len(descriptions)} Images",
                    filetypes=[("Images", "*.jpg *.png *.jpeg *.bmp *.gif")]
                )
                if not image_paths:
                    return []
                paired = list(zip(image_paths, descriptions))
                items = [{'type': 'image', 'content': path, 'desc': desc, 'question': ''} for path, desc in paired]
            else:
                messagebox.showerror("CSV Error", f"Invalid CSV structure detected with {cols} columns.")
                return []
                
            return items

        except Exception as e:
            messagebox.showerror("CSV Loading Error", f"Failed to read CSV file properly.\n\nReason:\n{str(e)}")
            return []

    def load_csv(self):
        items = self._parse_csv_and_images()
        if not items:
            return
        self.temp_set_data = items
        self.show_preview_ui()

    def create_combined_set(self):
        self.temp_set_data = []
        if messagebox.askyesno("Add Text Questions", "Would you like to load a Text Questions CSV first?"):
            items = self._parse_csv_and_images()
            if items:
                self.temp_set_data.extend(items)
        if messagebox.askyesno("Add Image Questions", "Would you like to add an Image Questions CSV + Images now?"):
            items = self._parse_csv_and_images()
            if items:
                self.temp_set_data.extend(items)
        if self.temp_set_data:
            self.show_preview_ui()

    def add_more_csv_to_preview(self):
        items = self._parse_csv_and_images()
        if items:
            self.temp_set_data.extend(items)
            self.refresh_preview_tree()

    def add_images_manually_to_preview(self):
        image_paths = filedialog.askopenfilenames(
            title="Select Images to Add",
            filetypes=[("Images", "*.jpg *.png *.jpeg *.bmp *.gif")]
        )
        if not image_paths:
            return
        for path in image_paths:
            ans = simpledialog.askstring("Image Answer", f"Enter the correct answer/description for:\n{os.path.basename(path)}")
            if ans is not None:
                self.temp_set_data.append({'type': 'image', 'content': path, 'desc': ans, 'question': ''})
        self.refresh_preview_tree()

    def delete_set_from_menu(self):
        selections = self.set_listbox.curselection()
        if not selections:
            messagebox.showwarning("Warning", "Please select at least one set to delete.")
            return
            
        selected_names = [self.set_listbox.get(i) for i in selections]
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to completely delete: {', '.join(selected_names)}?")
        
        if confirm:
            try:
                cursor = self.db_conn.cursor()
                for set_name in selected_names:
                    cursor.execute("DELETE FROM test_items WHERE set_name = %s", (set_name,))
                self.db_conn.commit()
                messagebox.showinfo("Deleted", "Selected set(s) have been successfully deleted.")
                self.show_main_menu() 
            except psycopg2.Error as e:
                self.db_conn.rollback()
                messagebox.showerror("Database Error", f"Failed to delete set: {e}")

    # ===================== PREVIEW & EDIT SET UI =====================
    def show_preview_ui(self):
        self.clear_window()
        tk.Label(self, text="Preview & Edit Set (Supports Combined Text + Images)", font=("Arial", 16, "bold")).pack(pady=8)
        
        append_frame = tk.Frame(self)
        append_frame.pack(pady=5)
        tk.Button(append_frame, text="+ Add CSV (Text or Image CSV)", command=self.add_more_csv_to_preview, bg="#d0ebff").pack(side=tk.LEFT, padx=5)
        tk.Button(append_frame, text="+ Add Image Files Directly", command=self.add_images_manually_to_preview, bg="#e5dbff").pack(side=tk.LEFT, padx=5)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        tree_scroll = tk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Explicit 5 columns for full visibility
        columns = ("Index", "Type", "Question", "Content / Image Path", "Description")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10, yscrollcommand=tree_scroll.set)
        
        for col in columns: 
            self.tree.heading(col, text=col)
            if col in ("Index", "Type"):
                self.tree.column(col, width=60)
            elif col == "Question":
                self.tree.column(col, width=150)
            else:
                self.tree.column(col, width=250)
            
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_preview_select)
        
        self.refresh_preview_tree()
        
        edit_frame = tk.LabelFrame(self, text="Edit Selected Item")
        edit_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(edit_frame, text="Type:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.edit_type_var = tk.StringVar(value="text")
        type_combo = ttk.Combobox(edit_frame, textvariable=self.edit_type_var, values=["text", "image"], width=10, state="readonly")
        type_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        tk.Label(edit_frame, text="Question:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.edit_question_var = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.edit_question_var, width=80).grid(row=1, column=1, padx=5, pady=5)

        tk.Label(edit_frame, text="Content / Image Path:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.edit_content_var = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.edit_content_var, width=80).grid(row=2, column=1, padx=5, pady=5)
        
        tk.Label(edit_frame, text="Answer/Description:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.edit_desc_var = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.edit_desc_var, width=80).grid(row=3, column=1, padx=5, pady=5)
        
        btn_frame = tk.Frame(edit_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
        tk.Button(btn_frame, text="Update Item", command=self.update_preview_item).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Delete Item", command=self.delete_preview_item, fg="red").pack(side=tk.LEFT, padx=10)
        
        action_frame = tk.Frame(self)
        action_frame.pack(pady=10)
        tk.Button(action_frame, text="Cancel", command=self.show_main_menu).pack(side=tk.LEFT, padx=10)
        tk.Button(action_frame, text="Confirm & Save Set", command=self.save_set_to_db, bg="lightgreen", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)

    def refresh_preview_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, item in enumerate(self.temp_set_data):
            # Display Question, Content, and Answer clearly in separate columns
            self.tree.insert("", tk.END, iid=i, values=(i+1, item['type'], item.get('question', ''), item['content'], item['desc']))

    def on_preview_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        idx = int(selected[0])
        item = self.temp_set_data[idx]
        self.edit_type_var.set(item['type'])
        self.edit_question_var.set(item.get('question', ''))
        self.edit_content_var.set(item['content'])
        self.edit_desc_var.set(item['desc'])

    def update_preview_item(self):
        selected = self.tree.selection()
        if not selected: return
        idx = int(selected[0])
        self.temp_set_data[idx]['type'] = self.edit_type_var.get()
        new_val = self.edit_content_var.get()
        if self.temp_set_data[idx]['type'] == 'image' and os.path.exists(new_val):
            self.temp_set_data[idx]['content'] = new_val
        else:
            self.temp_set_data[idx]['question'] = new_val
        self.temp_set_data[idx]['desc'] = self.edit_desc_var.get()
        self.refresh_preview_tree()

    def delete_preview_item(self):
        selected = self.tree.selection()
        if not selected: return
        idx = int(selected[0])
        del self.temp_set_data[idx]
        self.edit_question_var.set("")
        self.edit_content_var.set("")
        self.edit_desc_var.set("")
        self.refresh_preview_tree()

    def save_set_to_db(self):
        if not self.temp_set_data:
            messagebox.showwarning("Warning", "No data to save.")
            return
            
        set_name = simpledialog.askstring("Save Set", "Enter a name for this Set:")
        if not set_name: return
        
        try:
            cursor = self.db_conn.cursor()
            for item in self.temp_set_data:
                cursor.execute(
                    "INSERT INTO test_items (set_name, item_type, item_content, description, question_text) VALUES (%s, %s, %s, %s, %s)", 
                    (set_name, item['type'], item['content'], item['desc'], item.get('question', ''))
                )
            self.db_conn.commit()
            messagebox.showinfo("Success", f"Set '{set_name}' saved successfully!")
            self.show_main_menu()
        except psycopg2.Error as e:
            self.db_conn.rollback()
            messagebox.showerror("Database Error", f"Failed to save set: {e}")

    # ===================== TESTING UI =====================
    def start_test_from_menu(self):
        selections = self.set_listbox.curselection()
        if not selections:
            messagebox.showwarning("Warning", "Please select at least one set from the list.")
            return
            
        selected_names = [self.set_listbox.get(i) for i in selections]
        cursor = self.db_conn.cursor()
        
        placeholders = ', '.join(['%s'] * len(selected_names))
        query = f"SELECT item_type, item_content, description, question_text FROM test_items WHERE set_name IN ({placeholders})"
        cursor.execute(query, tuple(selected_names))
        rows = cursor.fetchall()
        
        test_data = [{'type': r[0], 'content': r[1], 'desc': r[2], 'question': r[3], 'user_ans': '', 'unsure': False, 'correct': False} for r in rows]
        combined_title = " + ".join(selected_names)
        self.start_test(specific_data=test_data, set_name=combined_title)

    def start_test(self, specific_data, set_name="Retest"):
        self.current_set_name = set_name
        if specific_data:
            random.shuffle(specific_data)
        self.test_data = specific_data

        if not self.test_data:
            messagebox.showinfo("Empty", "No data to test.")
            return

        self.current_q_index = 0
        self.build_test_ui()
        self.load_question(0)

    def build_test_ui(self):
        self.clear_window()
        tk.Label(self, text=f"Testing Set: {self.current_set_name}", font=("Arial", 14, "bold")).pack(pady=5)
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.left_frame = tk.Frame(main_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # --- SCROLLABLE CONTENT AREA ---
        self.content_container = tk.Frame(self.left_frame)
        self.content_container.pack(fill=tk.BOTH, expand=True)
        
        self.content_canvas = tk.Canvas(self.content_container, highlightthickness=0)
        self.content_scrollbar = tk.Scrollbar(self.content_container, orient="vertical", command=self.content_canvas.yview)
        self.content_scroll_frame = tk.Frame(self.content_canvas)
        
        self.content_scroll_frame.bind("<Configure>", lambda e: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all")))
        
        self.content_canvas_window = self.content_canvas.create_window((0, 0), window=self.content_scroll_frame, anchor="n")
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)
        
        # Center the internal frame dynamically
        def _configure_content_canvas(event):
            self.content_canvas.itemconfig(self.content_canvas_window, width=event.width)
        self.content_canvas.bind("<Configure>", _configure_content_canvas)
        
        self.content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Items inside the scrollable content area
        self.question_text_lbl = tk.Label(self.content_scroll_frame, text="", font=("Arial", 16, "bold"), wraplength=620, justify=tk.CENTER)
        self.question_text_lbl.pack(pady=10)

        self.item_display_lbl = tk.Label(self.content_scroll_frame, text="", font=("Arial", 14), wraplength=620, justify=tk.CENTER)
        self.item_display_lbl.pack(expand=True, pady=10)
        
        # --- FIXED BOTTOM CONTROLS ---
        self.bottom_controls_frame = tk.Frame(self.left_frame)
        self.bottom_controls_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)
        
        self.ans_entry = tk.Entry(self.bottom_controls_frame, font=("Arial", 14), width=40)
        self.ans_entry.pack(pady=5)
        self.ans_entry.bind("<KeyRelease>", self.save_current_answer)
        
        self.unsure_var = tk.BooleanVar()
        tk.Checkbutton(self.bottom_controls_frame, text="Flag Unsure", variable=self.unsure_var, command=self.save_current_answer).pack()
        
        btn_frame = tk.Frame(self.bottom_controls_frame)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Prev", command=lambda: self.load_question(self.current_q_index - 1), width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Next", command=lambda: self.load_question(self.current_q_index + 1), width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Finish Test", command=self.show_grading_ui, bg="lightblue", width=15).pack(side=tk.LEFT, padx=20)
        
        # --- RIGHT SIDE NAV GRID ---
        self.right_frame = tk.Frame(main_frame, width=225, bg="lightgrey")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_frame.pack_propagate(False)
        
        tk.Label(self.right_frame, text="Questions Grid", bg="lightgrey", font=("Arial", 10, "bold")).pack(pady=10)
        
        grid_container = tk.Frame(self.right_frame, bg="lightgrey")
        grid_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=5)
        
        self.grid_canvas = tk.Canvas(grid_container, bg="lightgrey", highlightthickness=0)
        grid_scrollbar = tk.Scrollbar(grid_container, orient="vertical", command=self.grid_canvas.yview)
        
        self.grid_frame = tk.Frame(self.grid_canvas, bg="lightgrey")
        self.grid_frame.bind("<Configure>", lambda e: self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all")))
        
        self.grid_canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_canvas.configure(yscrollcommand=grid_scrollbar.set)
        
        grid_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Smart mousewheel: Scroll whichever canvas the mouse is hovering over
        def _on_mousewheel(event):
            try:
                widget_under_mouse = self.winfo_containing(event.x_root, event.y_root)
                if widget_under_mouse:
                    if str(self.content_canvas) in str(widget_under_mouse):
                        if self.content_canvas.winfo_exists():
                            self.content_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                    elif str(self.right_frame) in str(widget_under_mouse):
                        if self.grid_canvas.winfo_exists():
                            self.grid_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                pass
        
        self.bind_all("<MouseWheel>", _on_mousewheel)

        self.nav_buttons = []
        for i in range(len(self.test_data)):
            btn = tk.Button(self.grid_frame, text=str(i+1), width=4, command=lambda idx=i: self.load_question(idx))
            btn.grid(row=(i//5), column=i%5, padx=2, pady=2)
            self.nav_buttons.append(btn)

    def load_question(self, index):
        if index < 0 or index >= len(self.test_data): return
        self.current_q_index = index
        q = self.test_data[index]
        
        # Reset scroll to top when changing questions
        self.content_canvas.yview_moveto(0)
        
        # Populate Question Text 
        if q.get('question'):
            self.question_text_lbl.config(text=q['question'])
        else:
            self.question_text_lbl.config(text="")
            
        # Populate Main Item Content
        if q['type'] == 'text':
            self.item_display_lbl.config(image='', text=q['content'])
        else:
            try:
                img = Image.open(q['content'])
                img.thumbnail((500, 500))  # Slightly larger thumbnail since it can scroll now
                self.photo = ImageTk.PhotoImage(img)
                self.item_display_lbl.config(text='', image=self.photo)
            except:
                self.item_display_lbl.config(image='', text="[Image Not Found - Check Filepath]")
                
        self.ans_entry.delete(0, tk.END)
        self.ans_entry.insert(0, q['user_ans'])
        self.unsure_var.set(q['unsure'])
        self.update_grid_colors()

    def save_current_answer(self, event=None):
        q = self.test_data[self.current_q_index]
        q['user_ans'] = self.ans_entry.get()
        q['unsure'] = self.unsure_var.get()
        self.update_grid_colors()

    def update_grid_colors(self):
        for i, q in enumerate(self.test_data):
            color = "SystemButtonFace"
            if q['unsure']: color = "yellow"
            elif q['user_ans'].strip(): color = "lightgreen"
            self.nav_buttons[i].config(bg=color)
# ===================== MANUAL GRADING =====================
    def show_grading_ui(self):
        self.clear_window()
        
        # Unbind mousewheel here so it doesn't try to scroll the old test grids
        self.unbind_all("<MouseWheel>")
        
        tk.Label(self, text="Manual Review", font=("Arial", 16, "bold")).pack(pady=5)
        tk.Label(
            self,
            text="• Single-click a row to read its full text in the Details Pane below.\n• Double-click an '[Image]' cell in the 'Content' column to view it.\n• Double-click anywhere else to toggle Correct/Incorrect.",
            fg="gray"
        ).pack(pady=5)
        
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        tree_scroll = tk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        columns = ("Q", "Type", "Question", "Content", "Your Answer", "Correct Answer", "Status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10, yscrollcommand=tree_scroll.set)
        
        for col in columns: 
            self.tree.heading(col, text=col)
            if col == "Q":
                self.tree.column(col, width=40)
            elif col == "Type":
                self.tree.column(col, width=60)
            elif col == "Status":
                self.tree.column(col, width=80)
            else:
                self.tree.column(col, width=150)
            
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)
        
        for i, q in enumerate(self.test_data):
            content_preview = "[Image]" if q['type'] == 'image' else q['content']
            
            if q['user_ans'].strip().lower() == q['desc'].strip().lower() and q['user_ans'].strip() != "":
                q['correct'] = True
                
            status = "Correct" if q['correct'] else "Incorrect"
            self.tree.insert("", tk.END, iid=i, values=(i+1, q['type'], q.get('question', ''), content_preview, q['user_ans'], q['desc'], status))
            
        # Bindings for single click (preview) and double click (grade/image)
        self.tree.bind("<<TreeviewSelect>>", self.on_grading_select)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        # --- NEW: Details Pane for reading long text ---
        details_frame = tk.LabelFrame(self, text="Full Item Details")
        details_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.details_text = tk.Text(details_frame, height=5, wrap=tk.WORD, font=("Arial", 12), bg="#f9f9f9")
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.details_text.insert(tk.END, "Select a row above to see the full, wrapped text here...")
        self.details_text.config(state=tk.DISABLED) # Make it read-only
        
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Retest All", command=lambda: self.start_test(specific_data=self.reset_data(self.test_data), set_name=self.current_set_name)).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Retest Incorrect Only", command=self.retest_incorrect).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Back to Home Menu", command=self.show_main_menu, bg="#ffcccb").pack(side=tk.LEFT, padx=30)

    # --- NEW METHOD: Triggers when you single-click a row ---
    def on_grading_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        
        idx = int(selected[0])
        q = self.test_data[idx]
        
        # Enable text box, clear it, insert new text, then disable again
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete("1.0", tk.END)
        
        details = ""
        if q.get('question'):
            details += f"QUESTION:\n{q['question']}\n\n"
            
        if q['type'] == 'text':
            details += f"CONTENT:\n{q['content']}\n\n"
        else:
            details += f"CONTENT:\n[Image Path: {q['content']}]\n\n"
            
        details += f"YOUR ANSWER:\n{q['user_ans']}\n\n"
        details += f"CORRECT ANSWER:\n{q['desc']}"
        
        self.details_text.insert(tk.END, details)
        self.details_text.config(state=tk.DISABLED)

    def on_tree_double_click(self, event):
        item_id = self.tree.focus()
        if not item_id: return
        
        col = self.tree.identify_column(event.x)
        q_idx = int(item_id)
        q = self.test_data[q_idx]
        
        # Col #4 is now the "Content" column where [Image] is displayed
        if col == '#4' and q['type'] == 'image':
            self.show_image_popup(q['content'])
        else:
            self.toggle_correct(q_idx, item_id)

    def show_image_popup(self, image_path):
        popup = tk.Toplevel(self)
        popup.title("Image Preview")
        popup.geometry("600x600")
        
        try:
            img = Image.open(image_path)
            img.thumbnail((580, 580))
            photo = ImageTk.PhotoImage(img)
            
            lbl = tk.Label(popup, image=photo)
            lbl.image = photo 
            lbl.pack(expand=True, pady=10)
        except Exception as e:
            tk.Label(popup, text=f"Could not load image:\n{e}").pack(expand=True)

    def toggle_correct(self, q_idx, item_id):
        q = self.test_data[q_idx]
        q['correct'] = not q['correct']
        status = "Correct" if q['correct'] else "Incorrect"
        
        current_values = list(self.tree.item(item_id, "values"))
        current_values[6] = status
        self.tree.item(item_id, values=current_values)

    def reset_data(self, data_list):
        for q in data_list:
            q['user_ans'] = ''
            q['unsure'] = False
            q['correct'] = False
        return data_list

    def retest_incorrect(self):
        incorrect_data = [q for q in self.test_data if not q['correct']]
        if not incorrect_data:
            messagebox.showinfo("Done", "All answers are correct!")
            self.show_main_menu()
        else:
            self.start_test(specific_data=self.reset_data(incorrect_data), set_name=self.current_set_name + " (Retest)")

if __name__ == "__main__":
    app = FlashcardApp()
    app.mainloop()