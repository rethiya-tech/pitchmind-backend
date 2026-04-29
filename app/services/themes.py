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
    # ── Creative ──────────────────────────────────────────────────────────────
    "vivid_purple": Theme(
        "vivid_purple", "Vivid Purple", "#150228", "#FFFFFF", "#A855F7",
        bg_image="vivid_purple_bg.png",
    ),
    "sunset_orange": Theme(
        "sunset_orange", "Sunset Orange", "#170500", "#FFFFFF", "#F97316",
        bg_image="sunset_orange_bg.png",
    ),
    "ocean_teal": Theme(
        "ocean_teal", "Ocean Teal", "#001818", "#FFFFFF", "#14B8A6",
        bg_image="ocean_teal_bg.png",
    ),
    "neon_blue": Theme(
        "neon_blue", "Neon Blue", "#000A16", "#F0F9FF", "#38BDF8",
        bg_image="neon_blue_bg.png",
    ),
    "ruby_red": Theme(
        "ruby_red", "Ruby Red", "#160000", "#FFFFFF", "#F43F5E",
        bg_image="ruby_red_bg.png",
    ),
    "cosmic_indigo": Theme(
        "cosmic_indigo", "Cosmic Indigo", "#000818", "#FFFFFF", "#818CF8",
        bg_image="cosmic_indigo_bg.png",
    ),
    # ── Minimal ───────────────────────────────────────────────────────────────
    "pure_white": Theme(
        "pure_white", "Pure White", "#FFFFFF", "#1F2937", "#3B82F6",
        bg_image="pure_white_bg.png",
    ),
    "warm_ivory": Theme(
        "warm_ivory", "Warm Ivory", "#FFFDF5", "#292524", "#D97706",
        bg_image="warm_ivory_bg.png",
    ),
    "soft_grey": Theme(
        "soft_grey", "Soft Grey", "#F8F9FA", "#1F2937", "#475569",
        bg_image="soft_grey_bg.png",
    ),
    "light_pearl": Theme(
        "light_pearl", "Light Pearl", "#EEF2FF", "#1E3A5F", "#4F46E5",
        bg_image="light_pearl_bg.png",
    ),
    "sage_mist": Theme(
        "sage_mist", "Sage Mist", "#F2F7F2", "#14532D", "#16A34A",
        bg_image="sage_mist_bg.png",
    ),
    "warm_slate": Theme(
        "warm_slate", "Warm Slate", "#F4F6F8", "#334155", "#64748B",
        bg_image="warm_slate_bg.png",
    ),
}


def get_theme(theme_id: str) -> Theme:
    return THEMES[theme_id]
