from ui.components.color_card import ColorCard
from ui.components.logo_card import LogoCard
from ui.layout import SectionCard
from ui.widgets import ModernSegmented


class DesignCard(SectionCard):
    """Step 2: tabs (Colours / Logo) that style the QR."""

    def __init__(self, parent):

        super().__init__(parent, title="Design", step=2)

        self.panes = {}
        self.panes["Colours"] = ColorCard(self.body)
        self.panes["Logo"] = LogoCard(self.body)
        self.colours = self.panes["Colours"]
        self.logo = self.panes["Logo"]

        self.tabs = ModernSegmented(
            self.body, values=list(self.panes), command=self.show_tab, height=32,
        )
        self.tabs.pack(anchor="w", pady=(0, 12))

        self.holder = self.body
        self._active = None
        self.show_tab("Colours")

    def show_tab(self, name):
        if self._active is not None:
            self.panes[self._active].pack_forget()
        self._active = name
        self.tabs.set(name)
        self.panes[name].pack(fill="x")

    def refresh_theme(self):
        super().refresh_theme()
        self.tabs.apply_theme()
        for pane in self.panes.values():
            pane.refresh_theme()
