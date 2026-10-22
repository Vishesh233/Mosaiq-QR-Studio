from ui.components.color_card import ColorCard
from ui.components.logo_card import LogoCard
from ui.components.style_card import StyleCard
from ui.layout import SectionCard
from ui.widgets import ModernSegmented
from utils.qr_render import QRStyle


class DesignCard(SectionCard):
    """Step 2: tabs (Colours / Style / Logo) that style the QR."""

    def __init__(self, parent):

        super().__init__(parent, title="Design", step=2)

        self.change_callback = None

        self.panes = {}
        self.panes["Colours"] = ColorCard(self.body)
        self.panes["Style"] = StyleCard(self.body)
        self.panes["Logo"] = LogoCard(self.body)
        self.colours = self.panes["Colours"]
        self.style = self.panes["Style"]
        self.logo = self.panes["Logo"]
        for pane in self.panes.values():
            pane.change_callback = self._changed

        self.tabs = ModernSegmented(
            self.body, values=list(self.panes), command=self.show_tab, height=32,
        )
        self.tabs.pack(anchor="w", pady=(0, 12))

        self._active = None
        self.show_tab("Colours")

    def _changed(self):
        if self.change_callback:
            self.change_callback()

    def show_tab(self, name):
        if self._active is not None:
            self.panes[self._active].pack_forget()
        self._active = name
        self.tabs.set(name)
        self.panes[name].pack(fill="x")

    def get_style(self):
        """The QRStyle chosen in the tabs."""
        base = QRStyle(fg=self.colours.get_qr_color(), bg=self.colours.get_bg_color())
        return self.style.apply_to(base)

    def reset(self):
        """Back to black on white, plain shapes, no logo (one preview refresh)."""
        callback, self.change_callback = self.change_callback, None
        try:
            self.colours.reset_colors()
            self.style.reset()
            self.logo.reset_logo()
        finally:
            self.change_callback = callback

    def refresh_theme(self):
        super().refresh_theme()
        self.tabs.apply_theme()
        for pane in self.panes.values():
            pane.refresh_theme()
