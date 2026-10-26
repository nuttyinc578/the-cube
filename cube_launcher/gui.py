import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import __version__
from .cloud import sign_in, validate_config, open_website_signup
from .core import atomic_json, update_guard


class LauncherWindow:
    def __init__(self, root, manager):
        self.root, self.manager = root, manager
        self.events, self.busy = queue.Queue(), False
        self.catalog = manager.cached()
        root.title('The Cube Beta Launcher')
        root.geometry('960x720')
        root.minsize(820, 680)
        root.configure(bg='#101727')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', background='#101727', foreground='#e5edf8', font=('Segoe UI', 11))
        style.configure('TFrame', background='#101727')
        style.configure('TLabel', background='#101727')
        style.configure('TButton', padding=10, background='#253452', foreground='#ffffff')
        style.map('TButton', background=[('active', '#365176')])
        style.configure('TEntry', fieldbackground='#edf2fa', foreground='#101727')
        style.configure('TCombobox', fieldbackground='#edf2fa', foreground='#101727')
        style.configure('TNotebook.Tab', padding=(20, 10))
        shell = ttk.Frame(root, padding=28)
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='THE CUBE BETA', font=('Segoe UI', 28, 'bold')).pack(anchor='w')
        ttk.Label(shell, text=f'LAUNCHER {__version__}  /  Your worlds. Your instances.').pack(anchor='w', pady=(0, 20))
        tabs = ttk.Notebook(shell)
        tabs.pack(fill='both', expand=True)
        play, settings, cloud = [ttk.Frame(tabs, padding=20) for _ in range(3)]
        for page, name in ((play, 'Play & instances'), (settings, 'Settings'), (cloud, 'Nuttyinc Cloud')):
            tabs.add(page, text=name)
        self.instance = tk.StringVar(value='default')
        self.version = tk.StringVar()
        ttk.Label(play, text='Instance — choose an installed instance or type a new name').pack(anchor='w')
        self.instance_box = ttk.Combobox(play, textvariable=self.instance)
        self.instance_box.pack(fill='x', pady=(8, 16))
        self.instance_box.bind('<<ComboboxSelected>>', lambda event: self.describe())
        ttk.Label(play, text='Official version — verified portable releases').pack(anchor='w')
        self.version_box = ttk.Combobox(play, textvariable=self.version, state='readonly')
        self.version_box.pack(fill='x', pady=(8, 16))
        actions = ttk.Frame(play)
        actions.pack(fill='x')
        self.buttons = []
        for title, command in (('▶ Play', self.play), ('Download / Install', lambda: self.install(False)),
                               ('Update', lambda: self.install(True)), ('Refresh versions', self.refresh)):
            button = ttk.Button(actions, text=title, command=command)
            button.pack(side='left', padx=(0, 8))
            self.buttons.append(button)
        self.details = tk.StringVar()
        ttk.Label(play, textvariable=self.details, wraplength=710).pack(anchor='w', pady=18)
        ttk.Label(play, text='Unlocked CPELoader = updates blocked. No bypass profiles are honored.\nUpdates preserve settings/userdata and retain a full backup.\nVersions without portable binaries are not installed; editions 5.0 and older remain unsupported.', wraplength=710).pack(anchor='w')
        ttk.Label(settings, text='Data location (instances, downloads, backups)').pack(anchor='w')
        ttk.Label(settings, text=str(manager.root), wraplength=710).pack(anchor='w', pady=(8, 20))
        options = manager.settings()
        self.domain = tk.StringVar(value=options.get('cognito_domain', ''))
        self.client = tk.StringVar(value=options.get('cognito_client_id', ''))
        for label, variable in (('AWS Cognito HTTPS domain', self.domain), ('Public app client ID — never enter a secret', self.client)):
            ttk.Label(settings, text=label).pack(anchor='w')
            ttk.Entry(settings, textvariable=variable).pack(fill='x', pady=(6, 14))
        ttk.Button(settings, text='Save settings', command=self.save).pack(anchor='w')
        ttk.Label(settings, text='CLI: Cube Beta Launcher.exe versions | instances | play NAME\ninstall NAME VERSION | update NAME VERSION | status NAME\nUse --help for options. No shell commands are executed.', wraplength=710).pack(anchor='w', pady=18)
        self.account = tk.StringVar(value='Offline — no account required to play.')
        ttk.Label(cloud, textvariable=self.account, font=('Segoe UI', 15), wraplength=710).pack(anchor='w', pady=(0, 20))
        ttk.Button(cloud, text='Sign in with Nuttyinc Cloud', command=self.login).pack(anchor='w')
        ttk.Button(cloud, text='Create account on website', command=self.signup).pack(anchor='w', pady=(10, 0))
        ttk.Button(cloud, text='Clear launcher sign-in', command=lambda: self.account.set('Offline — browser session may still be signed in.')).pack(anchor='w', pady=10)
        ttk.Label(cloud, text='Create account opens your signup link and returns to the CloudFront website. Then use Sign in here to connect the launcher. The launcher never asks for passwords, stores tokens, or uploads saves. Launcher sign-in requires Cognito callback http://localhost:8765/callback and scopes openid + email. Cloud saves and multiplayer accounts are not implemented.', wraplength=710).pack(anchor='w', pady=16)
        self.status = tk.StringVar(value='Ready. Refresh versions to fetch official downloads.')
        ttk.Label(shell, textvariable=self.status, wraplength=820).pack(anchor='w', pady=(16, 0))
        self.reload_choices()
        root.after(100, self.poll)

    def reload_choices(self):
        self.instance_box['values'] = self.manager.instances()
        self.version_box['values'] = [r['version'] for r in self.catalog]
        if self.catalog and self.version.get() not in self.version_box['values']:
            self.version.set(self.catalog[0]['version'])
        self.describe()

    def describe(self):
        try:
            info = self.manager.info(self.instance.get())
            try:
                update_guard(self.manager.instance(self.instance.get())/'game')
                policy = 'Updates available with locked CPELoader.'
            except PermissionError as exc:
                policy = str(exc)
            self.details.set(f"Installed version: {info['version']}  /  {self.instance.get()}\n{policy}")
        except (OSError, ValueError, KeyError):
            self.details.set('New instance. Choose a version, then Download / Install.')

    def run(self, operation, complete=None):
        if self.busy:
            return
        self.busy = True
        for button in self.buttons:
            button.configure(state='disabled')
        def work():
            try:
                self.events.put(('done', operation(), complete))
            except Exception as exc:
                self.events.put(('error', str(exc), None))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        while not self.events.empty():
            kind, value, complete = self.events.get_nowait()
            if kind == 'progress':
                self.status.set(value)
                continue
            self.busy = False
            for button in self.buttons:
                button.configure(state='normal')
            if kind == 'error':
                self.status.set('Operation stopped. No automatic retry.')
                messagebox.showerror('Cube Beta Launcher', value)
            else:
                self.status.set('Done.')
                if complete:
                    complete(value)
                self.reload_choices()
        self.root.after(100, self.poll)

    def refresh(self):
        self.status.set('Fetching official GitHub versions…')
        self.run(self.manager.releases, lambda result: setattr(self, 'catalog', result))

    def install(self, update):
        release = next((r for r in self.catalog if r['version'] == self.version.get()), None)
        if not release:
            messagebox.showinfo('Choose a version', 'Refresh versions, then select a release.')
            return
        name = self.instance.get()
        if not messagebox.askyesno('Update instance' if update else 'Install instance',
            f"{'Update' if update else 'Install'} {name} to {release['version']}?\nClose the game first. Installation runs official game code when you press Play."):
            return
        self.run(lambda: self.manager.install(name, release, update, lambda message: self.events.put(('progress', message, None))))

    def play(self):
        name = self.instance.get()
        self.run(lambda: self.manager.play(name), lambda pid: self.status.set(f'Game started (PID {pid}).'))

    def save(self):
        try:
            options = {'cognito_domain': self.domain.get().strip(), 'cognito_client_id': self.client.get().strip()}
            if any(options.values()):
                validate_config(options)
            with self.manager.lock():
                atomic_json(self.manager.settings_path, options)
            self.status.set('Settings saved. No secrets stored.')
        except Exception as exc:
            messagebox.showerror('Settings', str(exc))

    def login(self):
        self.status.set('Complete sign-in in your browser (three-minute timeout).')
        self.run(lambda: sign_in(self.manager.settings()), lambda name: self.account.set('Signed in: ' + name))

    def signup(self):
        try:
            open_website_signup()
            self.status.set('Signup opened in your browser. After signup, return here and use Sign in.')
        except Exception as exc:
            messagebox.showerror('Create account', str(exc))


def show(manager):
    root = tk.Tk()
    LauncherWindow(root, manager)
    root.mainloop()
