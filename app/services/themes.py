import os
from dataclasses import dataclass, field

_ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets", "themes")


@dataclass
class Theme:
    id: str
    name: str
    bg: str
    text: str
    accent: str
    font: str = "Plus Jakarta Sans"
    bg_image: str | None = None

    def bg_image_path(self) -> str | None:
        if not self.bg_image:
            return None
        path = os.path.join(_ASSETS, self.bg_image)
        return path if os.path.isfile(path) else None


THEMES: dict[str, Theme] = {
    "clean_slate": Theme(
        "clean_slate", "Slate Pro", "#1E2A3A", "#FFFFFF", "#60A5FA",
        bg_image="clean_slate_bg.png",
    ),
    "navy_gold": Theme(
        "navy_gold", "Navy Gold", "#0A1628", "#FFFFFF", "#D4A017",
        bg_image="navy_gold_bg.png",
    ),
    "dark_tech": Theme(
        "dark_tech", "Dark Tech", "#0D1117", "#F9FAFB", "#06B6D4",
        bg_image="dark_tech_bg.png",
    ),
    "charcoal_amber": Theme(
        "charcoal_amber", "Charcoal Amber", "#1C2030", "#F3F4F6", "#F59E0B",
        bg_image="charcoal_amber_bg.png",
    ),
    "steel_blue": Theme(
        "steel_blue", "Steel Blue", "#1A3050", "#FFFFFF", "#60A5FA",
        bg_image="steel_blue_bg.png",
    ),
    "forest_pro": Theme(
        "forest_pro", "Forest Pro", "#04321E", "#FFFFFF", "#34D399",
        bg_image="forest_pro_bg.png",
    ),
}


def get_theme(theme_id: str) -> Theme:
    return THEMES[theme_id]
