"""Native recovery screen with a drawn cube and real file-by-file progress."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

from cpe_repair import execute_repair


def repair_window(plan, *, accepted=False):
    window = tk.Tk()
    window.title('CPE Recovery · CPELoader v2')
    window.geometry('780x600')
    window.minsize(720, 580)
    window.configure(bg='#101720')
    window.option_add('*Font', ('Segoe UI', 11))
    canvas = tk.Canvas(window, width=92, height=92, bg='#101720', highlightthickness=0)
    canvas.pack(pady=(24, 8))
    canvas.create_polygon(46, 6, 80, 25, 46, 45, 12, 25, fill='#9ff2d5', outline='')
    canvas.create_polygon(12, 25, 46, 45, 46, 85, 12, 65, fill='#35ad96', outline='')
    canvas.create_polygon(46, 45, 80, 25, 80, 65, 46, 85, fill='#20786f', outline='')
    canvas.create_line(30, 54, 40, 65, 65, 40, fill='white', width=4)
    tk.Label(window, text='Repair your Cube', bg='#101720', fg='#eef7fa',
             font=('Segoe UI', 25, 'bold')).pack()
    tk.Label(window, text='Bundled recovery image · No downloads or account required',
             bg='#101720', fg='#9fb1c3').pack(pady=(4, 12))
    tk.Label(window, text='Game folder: '+str(plan.root), bg='#101720', fg='#9fb1c3',
             font=('Segoe UI', 9), wraplength=680).pack(padx=24, pady=(0, 12))
    description = ('Close the game and CPE services before continuing. This restores official files\n'
                   'and can replace changes to bundled files. Originals are backed up first.\n'
                   'Repair may take up to 3 minutes; slow disks can take longer.\n'
                   'Your saves, extra custom files, lock state and original manifest are preserved.')
    tk.Label(window, text=description, bg='#101720', fg='#d5e1ec', justify='center').pack(padx=20)
    status = tk.StringVar(value=f'Ready · {len(plan.payloads)} file(s) need restoration')
    if plan.missing_loader:
        status.set('CPELOADER_MISSING: '+', '.join(plan.missing_loader)+' · will restore')
    tk.Label(window, textvariable=status, bg='#101720', fg='#9ff2d5',
             wraplength=690).pack(padx=28, pady=(18, 8))
    style = ttk.Style(window)
    style.theme_use('clam')
    style.configure('CPE.Horizontal.TProgressbar', background='#9ff2d5', troughcolor='#283442')
    bar = ttk.Progressbar(window, maximum=100, style='CPE.Horizontal.TProgressbar')
    bar.pack(fill='x', padx=42, pady=(0, 16))
    row = tk.Frame(window, bg='#101720')
    row.pack()
    events = queue.Queue()
    state = {'running': False, 'code': 2, 'done': False}

    def close():
        if state['running']:
            status.set('Repair is applying files. Please wait for verification or rollback before closing.')
        else:
            window.destroy()

    def start():
        if state['running'] or state['done']:
            return
        state['running'] = True
        repair.configure(state='disabled')
        cancel.configure(state='disabled')
        status.set('Preparing verified recovery image and backup…')

        def worker():
            try:
                result = execute_repair(plan, lambda n, text: events.put(('progress', (n, text))))
                events.put(('done', result))
            except Exception as exc:
                events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll():
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == 'progress':
                    bar['value'], text = value
                    status.set(text)
                else:
                    state.update(running=False, done=True, code=0 if kind == 'done' else 1)
                    cancel.configure(state='normal', text='Close')
                    if kind == 'done':
                        bar['value'] = 100
                        status.set('Repair complete. '+('Backup: '+value['backup'] if value['backup'] else 'No changes needed.'))
                    else:
                        status.set(value)
        except queue.Empty:
            pass
        window.after(75, poll)

    cancel = tk.Button(row, text='Cancel', command=close, bg='#273644', fg='white',
                       activebackground='#34495a', activeforeground='white', relief='flat', width=13)
    cancel.pack(side='left', padx=6)
    repair = tk.Button(row, text='Back up & repair', command=start, bg='#9ff2d5', fg='#10251f',
                       activebackground='#b8ffe6', relief='flat', width=18)
    repair.pack(side='left', padx=6)
    cancel.focus_set()
    window.protocol('WM_DELETE_WINDOW', close)
    window.bind('<Escape>', lambda event: close())
    window.after(75, poll)
    if accepted:
        window.after(150, start)
    window.mainloop()
    return state['code']
