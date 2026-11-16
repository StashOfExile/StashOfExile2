from . import Module


class Dashboard(Module):
    key, title, short, icon, kind = "dashboard", "Dashboard", "Dashboard", "▦", "module"
    blurb = "Where you stand at a glance, and the way into everything else."

    def build(self, body):
        from ..dashboard_page import Dashboard as Page
        self.page = Page(self.app, body)
        self.page.pack(fill="both", expand=True)

    def on_show(self):
        page = getattr(self, "page", None)
        if page is not None:
            page.redraw()
