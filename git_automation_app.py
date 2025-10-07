import os
import subprocess
import shutil
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import datetime
import json
import re
import webbrowser
import platform

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

def run_cmd(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def find_repo_name_from_url(url):
    m = re.search(r"/([^/]+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    return "cloned_repo"

def generate_changelog_entry(author, story_id, up_file, down_file, obj_type):
    date_part = datetime.datetime.now().strftime("%Y%m%d")
    comment = story_id
    up_file = up_file.replace("\\", "/")
    down_file = down_file.replace("\\", "/")
    if obj_type == "Table":
        changelog = (
            f'<changeSet author="{author}" id="{date_part}_{story_id}">\n'
            f'    <comment>{comment}</comment>\n'
            f'    <sqlFile path="{up_file}" relativeToChangelogFile="true"/>\n'
            f'    <rollback>\n'
            f'        <sqlFile path="{down_file}" relativeToChangelogFile="true"/>\n'
            f'    </rollback>\n'
            f'</changeSet>'
        )
    elif obj_type in ("View", "Procedure"):
        changelog = (
            f'<changeSet author="{author}" id="{date_part}_{story_id}" runOnChange="true" runInTransaction="true">\n'
            f'    <comment>{comment}</comment>\n'
            f'    <sqlFile path="{up_file}" endDelimiter="" encoding="UTF-8"/>\n'
            f'    <rollback>\n'
            f'        <sqlFile path="{down_file}" relativeToChangelogFile="true"/>\n'
            f'    </rollback>\n'
            f'</changeSet>'
        )
    else:
        changelog = (
            f'<changeSet author="{author}" id="{date_part}_{story_id}">\n'
            f'    <comment>{comment}</comment>\n'
            f'    <sqlFile path="{up_file}" relativeToChangelogFile="true"/>\n'
            f'    <rollback>\n'
            f'        <sqlFile path="{down_file}" relativeToChangelogFile="true"/>\n'
            f'    </rollback>\n'
            f'</changeSet>'
        )
    return changelog

def append_to_changelog(changelog_path, changelog_entry):
    try:
        with open(changelog_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "</databaseChangeLog>" not in content:
            messagebox.showerror(
                "Invalid changelog",
                "Selected file is not a valid changelog XML (missing </databaseChangeLog> tag).",
            )
            return False
        new_content = re.sub(
            r"\n*\s*</databaseChangeLog>",
            f"\n{changelog_entry}\n</databaseChangeLog>",
            content,
        )
        with open(changelog_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to update changelog file:\n{e}")
        return False

def open_file_in_editor(path):
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("Open Error", f"Could not open file:\n{e}")

def git_get_modified_files(repo_path):
    success, output = run_cmd("git status --porcelain", cwd=repo_path)
    if not success:
        return []
    files = []
    for line in output.splitlines():
        if not line.strip():
            continue
        filename = line[3:].strip() if len(line) > 3 else ""
        if filename:
            files.append(filename)
    return files

def show_db_object_type_dialog(parent):
    dialog = tk.Toplevel(parent)
    dialog.title("Select DB Object Type")
    dialog.resizable(False, False)
    dialog.grab_set()
    selected = tk.StringVar(value="Table")

    tk.Label(dialog, text="Select the DB Object Type for changelog:", font=("Arial", 12, "bold")).pack(
        padx=20, pady=10
    )
    for obj_type in ("Table", "View", "Procedure"):
        rb = tk.Radiobutton(dialog, text=obj_type, variable=selected, value=obj_type, font=("Arial", 11))
        rb.pack(anchor="w", padx=40, pady=2)

    confirmed = {"ok": False}
    def on_ok():
        if selected.get() not in ("Table", "View", "Procedure"):
            messagebox.showwarning("Selection required", "Please select a DB Object Type to proceed.")
            return
        confirmed["ok"] = True
        dialog.destroy()
    def on_cancel():
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=15)
    btn_ok = tk.Button(btn_frame, text="OK", width=12, command=on_ok)
    btn_ok.pack(side=tk.LEFT, padx=10)
    btn_cancel = tk.Button(btn_frame, text="Cancel", width=12, command=on_cancel)
    btn_cancel.pack(side=tk.LEFT, padx=10)

    parent.wait_window(dialog)
    if confirmed["ok"]:
        return selected.get()
    else:
        return None

def get_github_pr_url(repo_path, branch):
    success, out = run_cmd("git config --get remote.origin.url", cwd=repo_path)
    if success and out.strip():
        url = out.strip()
        match = re.search(r"github\.com[/:](.+?)/(.+?)(?:\.git)?$", url)
        if match:
            owner, repository = match.group(1), match.group(2)
            return f"https://github.com/{owner}/{repository}/pull/new/{branch}"
    return None

def show_pr_popup(parent, url):
    popup = tk.Toplevel(parent)
    popup.title("Create Pull Request")
    popup.resizable(False, False)
    popup.grab_set()
    tk.Label(popup, text="Pull Request URL:", font=("Arial", 12, "bold")).pack(padx=20, pady=(15, 5))
    link = tk.Label(popup, text=url, fg="blue", cursor="hand2", font=("Arial", 11, "underline"))
    link.pack(padx=20, pady=(0, 15))
    def open_url(event):
        webbrowser.open(url)
        popup.destroy()
    link.bind("<Button-1>", open_url)

def main():
    root = tk.Tk()
    root.title("Git Automation App")
    root.geometry("750x400")

    config = load_config()
    if not config.get("username"):
        username = simpledialog.askstring("Setup", "Enter your username (for tracking):", parent=root)
        if not username:
            messagebox.showerror("Required", "Username is required!")
            root.destroy()
            return
        config["username"] = username
    if not config.get("git_name"):
        git_name = simpledialog.askstring("Setup", "Enter your git user.name:", parent=root)
        if not git_name:
            messagebox.showerror("Required", "git user.name required!")
            root.destroy()
            return
        config["git_name"] = git_name
    if not config.get("git_email"):
        git_email = simpledialog.askstring("Setup", "Enter your git user.email:", parent=root)
        if not git_email:
            messagebox.showerror("Required", "git user.email required!")
            root.destroy()
            return
        config["git_email"] = git_email

    save_config(config)
    username = config["username"]
    git_name = config["git_name"]
    git_email = config["git_email"]

    repo_path = None
    workflow_mode = tk.StringVar(value="DB Objects")

    top_frame = tk.Frame(root)
    top_frame.pack(padx=10, pady=10, fill=tk.X)
    btn_clone = tk.Button(top_frame, text="Clone Repository", width=20)
    btn_clone.pack(side=tk.LEFT, padx=5)
    btn_select = tk.Button(top_frame, text="Select Existing Repo", width=20)
    btn_select.pack(side=tk.LEFT, padx=5)
    label_repo = tk.Label(root, text="No repository selected", relief=tk.SUNKEN)
    label_repo.pack(fill=tk.X, padx=10, pady=5)

    wf_frame = tk.LabelFrame(root, text="Select Workflow Mode")
    wf_frame.pack(fill=tk.X, padx=10, pady=5)
    rb_db = tk.Radiobutton(wf_frame, text="DB Objects", variable=workflow_mode, value="DB Objects")
    rb_db.pack(anchor=tk.W, padx=10, pady=2)
    rb_ge = tk.Radiobutton(wf_frame, text="GE Scripts", variable=workflow_mode, value="GE Scripts")
    rb_ge.pack(anchor=tk.W, padx=10, pady=2)

    input_frame = tk.Frame(root)
    input_frame.pack(fill=tk.X, padx=10, pady=5)
    tk.Label(input_frame, text="Story ID:", width=14, anchor=tk.E).grid(row=0, column=0, sticky=tk.E)
    ent_story = tk.Entry(input_frame, width=32)
    ent_story.grid(row=0, column=1, pady=3, sticky=tk.W)
    tk.Label(input_frame, text="Branch Name:", width=14, anchor=tk.E).grid(row=1, column=0, sticky=tk.E)
    ent_branch = tk.Entry(input_frame, width=32)
    ent_branch.grid(row=1, column=1, pady=3, sticky=tk.W)
    tk.Label(input_frame, text="Commit Headline:", width=14, anchor=tk.E).grid(row=2, column=0, sticky=tk.E)
    ent_commit = tk.Entry(input_frame, width=50)
    ent_commit.grid(row=2, column=1, pady=3, sticky=tk.W)

    btn_start = tk.Button(root, text="Start Automation", state=tk.DISABLED)
    btn_start.pack(pady=10)
    status_label = tk.Label(root, text="", fg="blue")
    status_label.pack(fill=tk.X)
    output_text = tk.Text(root, height=20)

    def update_branch_name(*args):
        story = ent_story.get().strip()
        if story:
            ent_branch.delete(0, tk.END)
            ent_branch.insert(0, f"{story}_{username}")
        else:
            ent_branch.delete(0, tk.END)
    ent_story.bind("<KeyRelease>", update_branch_name)

    def enable_start():
        if repo_path:
            btn_start.config(state=tk.NORMAL)
        else:
            btn_start.config(state=tk.DISABLED)

    def clone_repo():
        nonlocal repo_path
        url = simpledialog.askstring("Clone Repository", "Enter Git repository URL:", parent=root)
        if not url:
            messagebox.showinfo("Cancelled", "Clone cancelled")
            return
        dest = filedialog.askdirectory(title="Select destination folder", initialdir=repo_path or os.path.expanduser("~"))
        if not dest:
            messagebox.showinfo("Cancelled", "No destination selected")
            return
        repo_name = find_repo_name_from_url(url)
        tgt_path = os.path.join(dest, repo_name)
        try:
            os.makedirs(tgt_path, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create directory:\n{e}")
            return
        status_label.config(text="Cloning repository...")
        root.update()
        success, out = run_cmd(f'git clone "{url}" "{tgt_path}"')
        status_label.config(text="")
        if success:
            repo_path = tgt_path
            label_repo.config(text=f"Selected repo: {repo_path}")
            enable_start()
            messagebox.showinfo("Success", "Repository cloned successfully")
        else:
            messagebox.showerror("Error", f"Git clone failed:\n{out}")

    def select_repo():
        nonlocal repo_path
        folder = filedialog.askdirectory(title="Select folder containing repositories", initialdir=repo_path or os.path.expanduser("~"))
        if not folder:
            messagebox.showinfo("Cancelled", "No folder selected")
            return
        repos = [
            os.path.join(folder, d)
            for d in os.listdir(folder)
            if os.path.isdir(os.path.join(folder, d, ".git"))
        ]
        if not repos:
            messagebox.showwarning("No Repos", "No git repositories found")
            return
        selected = []
        def on_select(event):
            sel = lb.curselection()
            if sel:
                selected.append(repos[sel[0]])
                top.destroy()
        top = tk.Toplevel(root)
        top.title("Select Repository")
        tk.Label(top, text="Select repository:", font=("Arial", 12, "bold")).pack(
            padx=10, pady=10
        )
        lb = tk.Listbox(top, width=80, height=15)
        lb.pack(padx=10, pady=10)
        for r in repos:
            lb.insert(tk.END, r)
        lb.bind("<<ListboxSelect>>", on_select)
        top.grab_set()
        root.wait_window(top)
        if selected:
            repo_path = selected[0]
            label_repo.config(text=f"Selected repo: {repo_path}")
            enable_start()

    def start_automation():
        nonlocal repo_path
        if not repo_path:
            messagebox.showerror("Error", "Please select or clone a repository first")
            return
        story = ent_story.get().strip()
        branch = ent_branch.get().strip()
        commit_headline = ent_commit.get().strip()
        if not story or not branch or not commit_headline:
            messagebox.showerror("Error", "Please fill all required fields")
            return
        full_branch = branch if "_" in branch else f"{story}_{branch}"

        if not output_text.winfo_ismapped():
            output_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            current_width = root.winfo_width()
            current_height = root.winfo_height()
            root.geometry(f"{current_width}x{current_height + 300}")

        status_label.config(text="Running git commands...")
        root.update()
        run_cmd(f'git config user.name "{git_name}"', cwd=repo_path)
        run_cmd(f'git config user.email "{git_email}"', cwd=repo_path)
        cmds = [
            ("git fetch origin", repo_path),
            ("git checkout dev", repo_path),
            ("git reset --hard origin/dev", repo_path),
            (f'git checkout -b "{full_branch}"', repo_path),
        ]
        for cmd, cwd in cmds:
            status_label.config(text=f"Running: {cmd}")
            root.update()
            success, out = run_cmd(cmd, cwd=cwd)
            output_text.insert(tk.END, f"$ {cmd}\n{out}\n")
            output_text.see(tk.END)
            if not success:
                messagebox.showerror("Git Error", f"Command failed:\n{cmd}\n{out}")
                status_label.config(text="Error")
                return

        if workflow_mode.get() == "GE Scripts":
            checkpoint_file = filedialog.askopenfilename(title="Select Checkpoint file")
            if not checkpoint_file:
                messagebox.showerror("Error", "Checkpoint file is required.")
                return
            expectation_file = filedialog.askopenfilename(title="Select Expectation file")
            if not expectation_file:
                messagebox.showerror("Error", "Expectation file is required.")
                return
            checkpoint_target = filedialog.askdirectory(
                title="Select target folder for Checkpoint file",
                initialdir=repo_path if repo_path else None
            )
            if not checkpoint_target:
                messagebox.showerror(
                    "Error", "Target folder for Checkpoint file is required."
                )
                return
            expectation_target = filedialog.askdirectory(
                title="Select target folder for Expectation file",
                initialdir=repo_path if repo_path else None
            )
            if not expectation_target:
                messagebox.showerror(
                    "Error", "Target folder for Expectation file is required."
                )
                return
            repo_abs = os.path.abspath(repo_path)
            for folder, name in [(checkpoint_target, "Checkpoint"), (expectation_target, "Expectation")]:
                folder_abs = os.path.abspath(folder)
                if not folder_abs.startswith(repo_abs):
                    messagebox.showerror(
                        "Invalid folder",
                        f"{name} target folder must be inside repository.",
                    )
                    return
            try:
                shutil.copy(checkpoint_file, checkpoint_target)
                shutil.copy(expectation_file, expectation_target)
            except Exception as e:
                messagebox.showerror("File Copy Error", f"Failed to copy files:\n{e}")
                return
            up_file = os.path.basename(checkpoint_file)
            down_file = os.path.basename(expectation_file)
            target_folders = {"up": checkpoint_target, "down": expectation_target}
        else:
            up_file_path = filedialog.askopenfilename(title="Select UP migration file")
            if not up_file_path:
                messagebox.showerror("Error", "UP migration file required.")
                return
            down_file_path = filedialog.askopenfilename(title="Select DOWN migration file")
            if not down_file_path:
                messagebox.showerror("Error", "DOWN migration file required.")
                return
            while True:
                target_folder = filedialog.askdirectory(
                    title="Select target folder INSIDE repository",
                    initialdir=repo_path if repo_path else None
                )
                if not target_folder:
                    messagebox.showerror("Error", "Target folder inside repo is required.")
                    return
                repo_abs = os.path.abspath(repo_path)
                tgt_abs = os.path.abspath(target_folder)
                if not tgt_abs.startswith(repo_abs):
                    messagebox.showerror("Error", "Target folder must be inside repository.")
                else:
                    break
            try:
                shutil.copy(up_file_path, target_folder)
                shutil.copy(down_file_path, target_folder)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy files:\n{e}")
                return
            up_file = os.path.basename(up_file_path)
            down_file = os.path.basename(down_file_path)
            target_folders = {"up": target_folder, "down": target_folder}

        changelog_file_to_add = None
        if workflow_mode.get() == "DB Objects":
            obj_type = show_db_object_type_dialog(root)
            if obj_type is None:
                messagebox.showinfo("Skipped", "Changelog update skipped (no DB Object Type selected)")
            else:
                changelog_path = filedialog.askopenfilename(
                    title="Select changelog.xml file",
                    filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
                    initialdir=repo_path if repo_path else None
                )
                if not changelog_path:
                    messagebox.showinfo("Skipped", "No changelog selected; skipping update")
                else:
                    changelog_dir = os.path.dirname(os.path.abspath(changelog_path))
                    if obj_type == "Table":
                        up_rel = os.path.relpath(os.path.join(target_folders["up"], up_file), changelog_dir)
                        down_rel = os.path.relpath(os.path.join(target_folders["down"], down_file), changelog_dir)
                    else:
                        up_rel = up_file
                        down_rel = down_file
                    changelog_entry = generate_changelog_entry(username, story, up_rel, down_rel, obj_type)
                    if append_to_changelog(changelog_path, changelog_entry):
                        messagebox.showinfo("Success", "Changelog updated successfully")
                        open_file_in_editor(changelog_path)
                        changelog_file_to_add = changelog_path

        files_to_add = [
            os.path.join(target_folders["up"], up_file),
            os.path.join(target_folders["down"], down_file),
        ]
        if workflow_mode.get() == "DB Objects" and changelog_file_to_add:
            files_to_add.append(changelog_file_to_add)

        for file_path in files_to_add:
            try:
                rel_path = os.path.relpath(file_path, repo_path)
            except Exception:
                rel_path = file_path
            cmd_add = f'git add "{rel_path}"'
            status_label.config(text=f"Adding {rel_path}")
            root.update()
            success, out = run_cmd(cmd_add, cwd=repo_path)
            output_text.insert(tk.END, f"$ {cmd_add}\n{out}\n")
            output_text.see(tk.END)
            if not success:
                messagebox.showerror("Error", f"Failed to add {rel_path}")
                return

        modified_files = git_get_modified_files(repo_path)
        if not modified_files:
            messagebox.showinfo("No changes", "No modified/new files to commit.")
            return
        file_list_text = "\n".join(modified_files)
        if not messagebox.askyesno(
            "Confirm Commit",
            f"The following files are staged for commit:\n\n{file_list_text}\n\nProceed?",
        ):
            messagebox.showinfo("Cancelled", "Commit operation cancelled")
            return

        commit_msg = f"AB#{story}: {commit_headline}"
        status_label.config(text="Committing changes...")
        root.update()
        success, out = run_cmd(f'git commit -m "{commit_msg}"', cwd=repo_path)
        output_text.insert(tk.END, f'$ git commit -m "{commit_msg}"\n{out}\n')
        output_text.see(tk.END)
        if not success:
            messagebox.showerror("Commit failed", "Commit failed or no changes to commit.")
            return

        status_label.config(text=f"Pushing branch {full_branch}...")
        root.update()
        success, out = run_cmd(f'git push origin "{full_branch}"', cwd=repo_path)
        output_text.insert(tk.END, f'$ git push origin "{full_branch}"\n{out}\n')
        output_text.see(tk.END)
        if not success:
            messagebox.showerror("Push failed", "Failed to push branch.")
            return

        pr_link = get_github_pr_url(repo_path, full_branch)
        if pr_link:
            status_label.config(text="Automation complete. Pull request link below.")
            show_pr_popup(root, pr_link)
        else:
            status_label.config(text="Automation complete.")

    btn_clone.config(command=clone_repo)
    btn_select.config(command=select_repo)
    btn_start.config(command=start_automation)
    enable_start()
    root.mainloop()

if __name__ == "__main__":
    main()
