from dataclasses import dataclass


@dataclass
class Theme:
    id: str
    name: str
    bg: str
    text: str
    accent: str
    font: str = "Plus Jakarta Sans"


THEMES: dict[str, Theme] = {
    "clean_slate": Theme(
        "clean_slate", "Clean Slate", "#FFFFFF", "#111827", "#1E40AF"
    ),
    "navy_gold": Theme(
        "navy_gold", "Navy Gold", "#0F1F3D", "#FFFFFF", "#D4A017"
    ),
    "dark_tech": Theme(
        "dark_tech", "Dark Tech", "#111827", "#F9FAFB", "#06B6D4"
    ),
    "charcoal_amber": Theme(
        "charcoal_amber", "Charcoal Amber", "#1F2937", "#F3F4F6", "#F59E0B"
    ),
    "steel_blue": Theme(
        "steel_blue", "Steel Blue", "#1E3A5F", "#FFFFFF", "#60A5FA"
    ),
    "forest_pro": Theme(
        "forest_pro", "Forest Pro", "#064E3B", "#FFFFFF", "#34D399"
    ),
}


def get_theme(theme_id: str) -> Theme:
    return THEMES[theme_id]
