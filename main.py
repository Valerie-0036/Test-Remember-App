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
        self.geometry("950x650")
        
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
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_items (
                id SERIAL PRIMARY KEY,
                set_name VARCHAR(100),
                item_type VARCHAR(10),
                item_content TEXT,
                description TEXT
            )
        """)
        self.db_conn.commit()

        try:
            cursor.execute("ALTER TABLE test_items ADD COLUMN set_name VARCHAR(100)")
            self.db_conn.commit()
        except psycopg2.Error:
            self.db_conn.rollback()

    # ===================== MAIN MENU =====================
    def show_main_menu(self):
        self.clear_window()
        frame = tk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)
        
        tk.Label(frame, text="Main Menu", font=("Arial", 18, "bold")).pack(pady=10)
        
        tk.Button(frame, text="Create New Set from CSV", command=self.load_csv, width=30, bg="lightgreen").pack(pady=10)
        
        tk.Frame(frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=20)
        
        tk.Label(frame, text="Select a Set to Test:", font=("Arial", 12)).pack()
        
        list_frame = tk.Frame(frame)
        list_frame.pack(pady=10)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.set_listbox = tk.Listbox(list_frame, width=50, height=10, yscrollcommand=scrollbar.set)
        self.set_listbox.pack(side=tk.LEFT, fill=tk.BOTH)
        scrollbar.config(command=self.set_listbox.yview)
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT DISTINCT set_name FROM test_items WHERE set_name IS NOT NULL")
            sets = cursor.fetchall()
            for s in sets:
                if s[0]: 
                    self.set_listbox.insert(tk.END, s[0])
        except psycopg2.Error:
            self.db_conn.rollback()
            
        tk.Button(frame, text="Start Test", command=self.start_test_from_menu, width=30, bg="lightblue").pack(pady=10)
        tk.Button(frame, text="Delete Selected Set", command=self.delete_set_from_menu, width=30, bg="#ffcccb").pack(pady=5)

    def load_csv(self):
        filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not filepath: return
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            data = list(reader)
            
        if not data: return
        
        cols = len(data[0])
        self.temp_set_data = []
        if cols >= 2:
            self.temp_set_data = [{'type': 'text', 'content': row[0], 'desc': row[1]} for row in data]
        elif cols == 1:
            descriptions = [row[0] for row in data]
            image_paths = filedialog.askopenfilenames(title=f"Select {len(descriptions)} Images", filetypes=[("Images", "*.jpg *.png *.jpeg")])
            if not image_paths: return
            
            paired = list(zip(image_paths, descriptions))
            self.temp_set_data = [{'type': 'image', 'content': path, 'desc': desc} for path, desc in paired]
            
        self.show_preview_ui()
        
    def delete_set_from_menu(self):
        selection = self.set_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a set to delete.")
            return
            
        set_name = self.set_listbox.get(selection[0])
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to completely delete the set '{set_name}'?")
        
        if confirm:
            try:
                cursor = self.db_conn.cursor()
                cursor.execute("DELETE FROM test_items WHERE set_name = %s", (set_name,))
                self.db_conn.commit()
                messagebox.showinfo("Deleted", f"Set '{set_name}' has been successfully deleted.")
                self.show_main_menu() 
            except psycopg2.Error as e:
                self.db_conn.rollback()
                messagebox.showerror("Database Error", f"Failed to delete set: {e}")

    # ===================== PREVIEW & EDIT SET UI =====================
    def show_preview_ui(self):
        self.clear_window()
        tk.Label(self, text="Preview & Edit Set", font=("Arial", 16, "bold")).pack(pady=10)
        
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        tree_scroll = tk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        columns = ("Index", "Type", "Item / Image Path", "Description")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10, yscrollcommand=tree_scroll.set)
        
        for col in columns: 
            self.tree.heading(col, text=col)
            self.tree.column(col, width=200 if col != "Index" else 50)
            
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_preview_select)
        
        self.refresh_preview_tree()
        
        edit_frame = tk.LabelFrame(self, text="Edit Selected Item")
        edit_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(edit_frame, text="Item Content / Path:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.edit_content_var = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.edit_content_var, width=60).grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(edit_frame, text="Description:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.edit_desc_var = tk.StringVar()
        tk.Entry(edit_frame, textvariable=self.edit_desc_var, width=60).grid(row=1, column=1, padx=5, pady=5)
        
        btn_frame = tk.Frame(edit_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        tk.Button(btn_frame, text="Update Item", command=self.update_preview_item).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Delete Item", command=self.delete_preview_item, fg="red").pack(side=tk.LEFT, padx=10)
        
        action_frame = tk.Frame(self)
        action_frame.pack(pady=20)
        tk.Button(action_frame, text="Cancel", command=self.show_main_menu).pack(side=tk.LEFT, padx=10)
        tk.Button(action_frame, text="Confirm & Save Set", command=self.save_set_to_db, bg="lightgreen", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)

    def refresh_preview_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, item in enumerate(self.temp_set_data):
            self.tree.insert("", tk.END, iid=i, values=(i+1, item['type'], item['content'], item['desc']))

    def on_preview_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        idx = int(selected[0])
        item = self.temp_set_data[idx]
        self.edit_content_var.set(item['content'])
        self.edit_desc_var.set(item['desc'])

    def update_preview_item(self):
        selected = self.tree.selection()
        if not selected: return
        idx = int(selected[0])
        self.temp_set_data[idx]['content'] = self.edit_content_var.get()
        self.temp_set_data[idx]['desc'] = self.edit_desc_var.get()
        self.refresh_preview_tree()

    def delete_preview_item(self):
        selected = self.tree.selection()
        if not selected: return
        idx = int(selected[0])
        del self.temp_set_data[idx]
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
                    "INSERT INTO test_items (set_name, item_type, item_content, description) VALUES (%s, %s, %s, %s)", 
                    (set_name, item['type'], item['content'], item['desc'])
                )
            self.db_conn.commit()
            messagebox.showinfo("Success", f"Set '{set_name}' saved successfully!")
            self.show_main_menu()
        except psycopg2.Error as e:
            self.db_conn.rollback()
            messagebox.showerror("Database Error", f"Failed to save set: {e}")

    # ===================== TESTING UI =====================
    def start_test_from_menu(self):
        selection = self.set_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a set from the list.")
            return
            
        set_name = self.set_listbox.get(selection[0])
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT item_type, item_content, description FROM test_items WHERE set_name = %s", (set_name,))
        rows = cursor.fetchall()
        
        test_data = [{'type': r[0], 'content': r[1], 'desc': r[2], 'user_ans': '', 'unsure': False, 'correct': False} for r in rows]
        self.start_test(specific_data=test_data, set_name=set_name)

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
        
        self.item_display_lbl = tk.Label(self.left_frame, text="", font=("Arial", 16))
        self.item_display_lbl.pack(expand=True)
        
        self.ans_entry = tk.Entry(self.left_frame, font=("Arial", 14), width=40)
        self.ans_entry.pack(pady=10)
        self.ans_entry.bind("<KeyRelease>", self.save_current_answer)
        
        self.unsure_var = tk.BooleanVar()
        tk.Checkbutton(self.left_frame, text="Flag Unsure", variable=self.unsure_var, command=self.save_current_answer).pack()
        
        btn_frame = tk.Frame(self.left_frame)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Prev", command=lambda: self.load_question(self.current_q_index - 1), width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Next", command=lambda: self.load_question(self.current_q_index + 1), width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Finish Test", command=self.show_grading_ui, bg="lightblue", width=15).pack(side=tk.LEFT, padx=20)
        
        self.right_frame = tk.Frame(main_frame, width=225, bg="lightgrey")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_frame.pack_propagate(False)
        
        tk.Label(self.right_frame, text="Questions Grid", bg="lightgrey", font=("Arial", 10, "bold")).pack(pady=10)
        
        grid_container = tk.Frame(self.right_frame, bg="lightgrey")
        grid_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=5)
        
        canvas = tk.Canvas(grid_container, bg="lightgrey", highlightthickness=0)
        scrollbar = tk.Scrollbar(grid_container, orient="vertical", command=canvas.yview)
        
        self.grid_frame = tk.Frame(canvas, bg="lightgrey")
        self.grid_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.nav_buttons = []
        for i in range(len(self.test_data)):
            btn = tk.Button(self.grid_frame, text=str(i+1), width=4, command=lambda idx=i: self.load_question(idx))
            btn.grid(row=(i//5), column=i%5, padx=2, pady=2)
            self.nav_buttons.append(btn)

    def load_question(self, index):
        if index < 0 or index >= len(self.test_data): return
        self.current_q_index = index
        q = self.test_data[index]
        
        if q['type'] == 'text':
            self.item_display_lbl.config(image='', text=q['content'])
        else:
            try:
                img = Image.open(q['content'])
                img.thumbnail((450, 450))
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
        tk.Label(self, text="Manual Review", font=("Arial", 16, "bold")).pack(pady=5)
        tk.Label(self, text="• Double-click an '[Image]' cell in the 'Item' column to view it.\n• Double-click anywhere else to toggle Correct/Incorrect.", fg="gray").pack(pady=5)
        
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        tree_scroll = tk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        columns = ("Q", "Item", "Your Answer", "Correct Answer", "Status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15, yscrollcommand=tree_scroll.set)
        
        for col in columns: 
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150 if col != "Q" else 40)
            
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)
        
        for i, q in enumerate(self.test_data):
            item_preview = q['content'] if q['type'] == 'text' else "[Image]"
            
            if q['user_ans'].strip().lower() == q['desc'].strip().lower() and q['user_ans'].strip() != "":
                q['correct'] = True
                
            status = "Correct" if q['correct'] else "Incorrect"
            self.tree.insert("", tk.END, iid=i, values=(i+1, item_preview, q['user_ans'], q['desc'], status))
            
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Retest All", command=lambda: self.start_test(specific_data=self.reset_data(self.test_data), set_name=self.current_set_name)).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Retest Incorrect Only", command=self.retest_incorrect).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Back to Home Menu", command=self.show_main_menu, bg="#ffcccb").pack(side=tk.LEFT, padx=30)

    def on_tree_double_click(self, event):
        item_id = self.tree.focus()
        if not item_id: return
        
        col = self.tree.identify_column(event.x)
        q_idx = int(item_id)
        q = self.test_data[q_idx]
        
        if col == '#2' and q['type'] == 'image':
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
        current_values[4] = status
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