"""DPI-aware check rows for the compact desktop window."""
import tkinter as tk


class AutomationCheck(tk.Frame):
    def __init__(self, master, text, variable, command):
        super().__init__(master,bg='#171e27',takefocus=True,highlightthickness=1,
                         highlightbackground='#171e27',highlightcolor='#b6a16b',cursor='hand2')
        self.text,self.variable,self.command = text,variable,command
        self.scale = max(1,self.winfo_fpixels('1i')/96)
        self.indicator = tk.Canvas(self,width=round(18*self.scale),height=round(18*self.scale),
                                   bg=self['bg'],highlightthickness=0)
        self.indicator.pack(side='left',padx=(round(9*self.scale),round(8*self.scale)),
                            pady=round(8*self.scale))
        self.label = tk.Label(self,text=text,bg=self['bg'],fg='#e0e6ed',font=('Segoe UI',9),anchor='w')
        self.label.pack(side='left',fill='x',expand=True,padx=(0,round(12*self.scale)))
        for widget in (self,self.indicator,self.label):
            widget.bind('<ButtonRelease-1>',lambda event:self.click())
            widget.bind('<Enter>',lambda event:self.hover(True))
            widget.bind('<Leave>',lambda event:self.hover(False))
        self.bind('<space>',lambda event:self.keyboard_invoke())
        self.bind('<Return>',lambda event:self.keyboard_invoke())
        self.trace = self.variable.trace_add('write',lambda *args:self.draw())
        self.bind('<Destroy>',self.release,add='+')
        self.draw()

    def release(self, event):
        if event.widget is self:self.variable.trace_remove('write',self.trace)

    def cget(self, key):
        return self.text if key=='text' else super().cget(key)

    def click(self):
        self.focus_set()
        self.invoke()

    def keyboard_invoke(self):
        self.invoke()
        return 'break'

    def invoke(self):
        self.variable.set(not self.variable.get())
        return self.command()

    def hover(self, active):
        color = '#202a35' if active else '#171e27'
        self.configure(bg=color)
        self.indicator.configure(bg=color)
        self.label.configure(bg=color)
        self.draw()

    def draw(self):
        self.indicator.delete('all')
        s = self.scale
        checked = self.variable.get()
        self.indicator.create_rectangle(2*s,2*s,16*s,16*s,
            fill='#c2ac76' if checked else self['bg'],
            outline='#c2ac76' if checked else '#718094',width=max(1,round(s)))
        if checked:self.indicator.create_line(5*s,9*s,8*s,12*s,13*s,6*s,
            fill='#10151c',width=max(2,round(1.7*s)),capstyle='round',joinstyle='round')
