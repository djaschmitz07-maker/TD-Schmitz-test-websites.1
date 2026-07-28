import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webview
from google import genai
from google.genai import types

class AIWebStudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Web Builder Studio Pro")
        self.root.geometry("1400x900")
        self.root.configure(bg="#111111") # Base Dark Canvas
        
        # State Tracking Assets
        self.current_project = ""
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.websites_dir = os.path.join(self.base_dir, "websites")
        os.makedirs(self.websites_dir, exist_ok=True)
        
        self.api_keys_file = os.path.join(self.base_dir, "api_keys.json")
        self.saved_keys = self.load_keys_from_disk()
        self.active_key_str = ""
        self.client = None
        self.current_webview_window = None

        self.setup_styles()
        self.build_layout()
        self.refresh_project_list()
        self.refresh_key_list()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Dark Theme Matrix Config
        self.style.configure("TPanedwindow", background="#111111")
        self.style.configure("Sidebar.TFrame", background="#111111")
        self.style.configure("Workspace.TFrame", background="#111111")
        
        # Typography Overrides
        self.style.configure("FeatureHeader.TLabel", font=("Arial", 11, "bold"), background="#111111", foreground="#ffffff")
        self.style.configure("CenteredHeader.TLabel", font=("Arial", 12, "bold"), background="#111111", foreground="#4dadff")
        self.style.configure("DarkLabel.TLabel", background="#111111", foreground="#aaaaaa")
        self.style.configure("TSeparator", background="#222222")

        # Corporate Blue Action Buttons
        self.style.configure("TButton", font=("Arial", 10, "bold"), background="#0066cc", foreground="#ffffff", borderwidth=0)
        self.style.map("TButton",
            background=[('pressed', '#004488'), ('active', '#0052a3')],
            foreground=[('pressed', '#ffffff'), ('active', '#ffffff')]
        )

    def build_layout(self):
        # Primary Screen Left-to-Right Splitter
        self.main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        # Left Column - Taskbar Sidebar (Dark Mode)
        self.feature_board = ttk.Frame(self.main_pane, style="Sidebar.TFrame", padding=12)
        self.main_pane.add(self.feature_board, weight=1)

        # Right Column - Combined Interactive Hub (Dark Mode)
        self.interactive_board = ttk.Frame(self.main_pane, style="Workspace.TFrame", padding=10)
        self.main_pane.add(self.interactive_board, weight=3)

        # =====================================================================
        # TASKBAR SIDEBAR COMPONENTS (LEFT SIDE)
        # =====================================================================
        vault_lbl = ttk.Label(self.feature_board, text="🔑 API Key Vault", style="FeatureHeader.TLabel")
        vault_lbl.pack(anchor=tk.W, pady=(0, 2))

        # BUG FIX: Swapped to native tk.Entry to allow custom dark backgrounds and borders
        self.key_name_entry = tk.Entry(self.feature_board, font=("Arial", 10), bg="#222222", fg="#ffffff", insertbackground="white", relief=tk.FLAT, bd=4)
        self.key_name_entry.insert(0, "Label Name")
        self.key_name_entry.pack(fill=tk.X, pady=4)

        self.key_val_entry = tk.Entry(self.feature_board, font=("Arial", 10), show="*", bg="#222222", fg="#ffffff", insertbackground="white", relief=tk.FLAT, bd=4)
        self.key_val_entry.pack(fill=tk.X, pady=4)

        vault_btn_frame = ttk.Frame(self.feature_board, style="Sidebar.TFrame")
        vault_btn_frame.pack(fill=tk.X, pady=(4, 6))
        ttk.Button(vault_btn_frame, text="Save Key", command=self.save_api_key).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,1))
        ttk.Button(vault_btn_frame, text="Delete", command=self.delete_api_key).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(1,0))

        self.keys_listbox = tk.Listbox(self.feature_board, height=3, font=("Arial", 9), bg="#222222", fg="#ffffff", selectbackground="#0066cc", highlightthickness=0, relief=tk.FLAT)
        self.keys_listbox.pack(fill=tk.X, pady=(2, 10))
        self.keys_listbox.bind('<<ListboxSelect>>', self.on_key_selected)

        # Context Sync Section
        sep1 = ttk.Separator(self.feature_board, orient=tk.HORIZONTAL)
        sep1.pack(fill=tk.X, pady=4)
        
        self.sync_context_btn = ttk.Button(self.feature_board, text="🔄 Sync & Update Folder", style="TButton", command=self.sync_existing_context)
        self.sync_context_btn.pack(fill=tk.X, pady=6)
        
        sep2 = ttk.Separator(self.feature_board, orient=tk.HORIZONTAL)
        sep2.pack(fill=tk.X, pady=4)

        # Project Explorer Panel
        explorer_lbl = ttk.Label(self.feature_board, text="📁 Website Project Explorer", style="FeatureHeader.TLabel")
        explorer_lbl.pack(anchor=tk.W, pady=(0, 2))

        # BUG FIX: Swapped to native tk.Entry
        self.new_proj_entry = tk.Entry(self.feature_board, font=("Arial", 10), bg="#222222", fg="#ffffff", insertbackground="white", relief=tk.FLAT, bd=4)
        self.new_proj_entry.insert(0, "new_website_name")
        self.new_proj_entry.pack(fill=tk.X, pady=4)

        ttk.Button(self.feature_board, text="➕ Create Project File", command=self.create_new_project).pack(fill=tk.X, pady=(2, 6))

        self.project_listbox = tk.Listbox(self.feature_board, font=("Arial", 10), bg="#222222", fg="#ffffff", selectbackground="#0066cc", highlightthickness=0, relief=tk.FLAT)
        self.project_listbox.pack(fill=tk.BOTH, expand=True, pady=2)
        self.project_listbox.bind('<<ListboxSelect>>', self.on_project_single_clicked)
        # =====================================================================
        # INTERACTIVE WORKSPACE HUB COMPONENTS (RIGHT SIDE)
        # =====================================================================
        self.header_panel = ttk.Frame(self.interactive_board, style="Workspace.TFrame")
        self.header_panel.pack(fill=tk.X, pady=(0, 10))

        # Centered active target workspace indicator label
        self.status_header = ttk.Label(self.header_panel, text="Active Project: None Selected", style="CenteredHeader.TLabel", justify=tk.CENTER)
        self.status_header.pack(side=tk.LEFT, expand=True, anchor=tk.CENTER, padx=(120, 0))

        # Dedicated right-hand click-to-render button
        self.view_page_btn = ttk.Button(self.header_panel, text="🌐 View Page", command=self.trigger_render_view)
        self.view_page_btn.pack(side=tk.RIGHT, padx=2)

        # Dialog text history tracking log (Clean white square layout container)
        self.chat_log = tk.Text(self.interactive_board, state=tk.DISABLED, bg="#ffffff", fg="#222222", wrap=tk.WORD, font=("Arial", 11), highlightthickness=1, highlightbackground="#cccccc")
        self.chat_log.pack(fill=tk.BOTH, expand=True, pady=4)

        # Input console panel widget
        ttk.Label(self.interactive_board, text="Describe your design updates / commands:", font=("Arial", 10, "bold"), style="FeatureHeader.TLabel").pack(anchor=tk.W, pady=(5,0))
        self.prompt_input = tk.Text(self.interactive_board, height=4, font=("Arial", 11), bg="#ffffff", fg="#222222", highlightthickness=1, highlightbackground="#cccccc")
        self.prompt_input.pack(fill=tk.X, pady=2)

        self.send_btn = ttk.Button(self.interactive_board, text="🚀 Send Request Loop & Auto-Write Code", command=self.process_ai_request, state=tk.DISABLED)
        self.send_btn.pack(fill=tk.X, pady=(6, 0))

    # =====================================================================
    # ENGINE CODES & LOCAL PERSISTENT STORAGE CONFIGURES
    # =====================================================================
    def load_keys_from_disk(self):
        if os.path.exists(self.api_keys_file):
            try:
                with open(self.api_keys_file, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_keys_to_disk(self):
        with open(self.api_keys_file, "w") as f:
            json.dump(self.saved_keys, f, indent=4)

    def refresh_key_list(self):
        self.keys_listbox.delete(0, tk.END)
        for key_name in self.saved_keys.keys():
            self.keys_listbox.insert(tk.END, key_name)

    def save_api_key(self):
        name = self.key_name_entry.get().strip()
        val = self.key_val_entry.get().strip()
        if not name or name in ["", "Label Name"]: return
        self.saved_keys[name] = val
        self.save_keys_to_disk()
        self.refresh_key_list()
        messagebox.showinfo("Success", f"Key saved: '{name}'")

    def delete_api_key(self):
        selected = self.keys_listbox.curselection()
        if not selected: return
        key_name = self.keys_listbox.get(selected)
        del self.saved_keys[key_name]
        self.save_keys_to_disk()
        self.refresh_key_list()
        self.client = None
        self.update_status_bar()

    def on_key_selected(self, event):
        selected = self.keys_listbox.curselection()
        if not selected: return
        key_name = self.keys_listbox.get(selected)
        self.active_key_str = self.saved_keys[key_name]
        try:
            self.client = genai.Client(api_key=self.active_key_str)
            self.log_to_chat("System", f"Switched API Brain Module Context: '{key_name}'")
            self.update_status_bar()
        except Exception as e:
            messagebox.showerror("Error", f"Failed key activation: {e}")

    def refresh_project_list(self):
        self.project_listbox.delete(0, tk.END)
        if os.path.exists(self.websites_dir):
            for item in os.listdir(self.websites_dir):
                if os.path.isdir(os.path.join(self.websites_dir, item)):
                    self.project_listbox.insert(tk.END, f"📄 {item}")
    def create_new_project(self):
        name = self.new_proj_entry.get().strip().lower().replace(" ", "_")
        if not name or name == "new_website_name": return
        p_dir = os.path.join(self.websites_dir, name)
        os.makedirs(os.path.join(p_dir, "images"), exist_ok=True)
        self.refresh_project_list()
        self.load_project_env(name)

    def on_project_single_clicked(self, event):
        selected = self.project_listbox.curselection()
        if not selected: return
        clean_name = self.project_listbox.get(selected).replace("📄 ", "")
        self.load_project_env(clean_name)

    def load_project_env(self, name):
        self.current_project = name
        self.project_dir = os.path.join(self.websites_dir, name)
        self.images_dir = os.path.join(self.project_dir, "images")
        self.html_file_path = os.path.join(self.project_dir, "index.html")
        
        self.status_header.config(text=f"Active Project: {name}")
        self.log_to_chat("System", f"Switched target file folder context to: '{name}'")
        self.update_status_bar()

    def sync_existing_context(self):
        if not self.current_project:
            messagebox.showwarning("Sync Warning", "Select a project directory on your sidebar explorer first!")
            return
        self.refresh_project_list()
        img_count = len(os.listdir(self.images_dir))
        file_present = "Found index.html" if os.path.exists(self.html_file_path) else "File Blank (index.html missing)"
        
        self.log_to_chat("Sync Engine", f"Re-anchored system context for '{self.current_project}':\n↳ Status: {file_present}\n↳ Linked Assets: {img_count} image files inside directory.")
        self.update_status_bar()

    def update_status_bar(self):
        if self.client and self.current_project:
            self.send_btn.config(state=tk.NORMAL)
        else:
            self.send_btn.config(state=tk.DISABLED)

    def log_to_chat(self, sender, msg):
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, f"\n[{sender}]: {msg}\n" + "—"*40 + "\n")
        self.chat_log.config(state=tk.DISABLED)
        self.chat_log.see(tk.END)

    def trigger_render_view(self):
        """Launches the independent browser console instance safely scheduled back onto the primary main thread loop."""
        if not self.current_project:
            messagebox.showwarning("Selection Missing", "Click on a website file folder in the sidebar explorer list first!")
            return
            
        if not os.path.exists(self.html_file_path) or os.path.getsize(self.html_file_path) == 0:
            messagebox.showinfo("Empty File", f"No HTML code has been written for '{self.current_project}' yet. Ask the AI to build something first!")
            return

        if self.current_webview_window is not None:
            try:
                self.current_webview_window.destroy()
            except:
                pass
            self.current_webview_window = None

        file_url = f"file:///{self.html_file_path.replace(os.sep, '/')}"
        
        def launch():
            self.current_webview_window = webview.create_window(f"Studio Render View - {self.current_project}", file_url)
            webview.start()

        self.root.after(0, launch)

    def process_ai_request(self):
        user_prompt = self.prompt_input.get("1.0", tk.END).strip()
        if not user_prompt: return
        
        self.log_to_chat("You", user_prompt)
        self.prompt_input.delete("1.0", tk.END)
        self.root.update()

        def async_api_worker():
            try:
                available_imgs = os.listdir(self.images_dir)
                img_meta = "Images inside your asset folder 'images/':\n" + "\n".join([f"- images/{i}" for i in available_imgs]) if available_imgs else "No asset images provided yet."

                existing_code = ""
                if os.path.exists(self.html_file_path):
                    with open(self.html_file_path, "r", encoding="utf-8") as f:
                        existing_code = f.read()

                system_instruction = (
                    "You are a master frontend designer engine. Return only pure, raw HTML layout modules with inline styling. "
                    "CRITICAL: Do NOT wrap code block packages inside backticks like ```html. Output raw layout strings only. No markdown text headers."
                    f"Active Project: {self.current_project}\n{img_meta}\n"
                )
                if existing_code:
                    system_instruction += f"Modify and update the existing index.html codebase template based on user requirements:\n\n{existing_code}"
                else:
                    system_instruction += "Create a beautifully scaled responsive index.html website asset from absolute scratch."

                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_prompt,
                    config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2),
                )
                
                with open(self.html_file_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                
                self.root.after(0, lambda: self.log_to_chat("AI Workspace Engine", f"Website written directly to disk for '{self.current_project}'! Click 'View Page' to render changes."))

            except Exception as e:
                self.root.after(0, lambda: self.log_to_chat("System Pipeline Error", str(e)))

        threading.Thread(target=async_api_worker, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = AIWebStudioApp(root)
    root.mainloop()
