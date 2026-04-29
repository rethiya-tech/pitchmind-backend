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
    "executive_modern": Theme(
        "executive_modern", "Executive Modern", "#FFFFFF", "#1A1A1A", "#0F6E56"
    ),
    "corporate_zenith": Theme(
        "corporate_zenith", "Corporate Zenith", "#1A2A1A", "#FFFFFF", "#1D9E75"
    ),
    "digital_frontier": Theme(
        "digital_frontier", "Digital Frontier", "#0A1628", "#FFFFFF", "#5DCAA5"
    ),
    "nordic_flow": Theme(
        "nordic_flow", "Nordic Flow", "#F5F4F0", "#1A1A1A", "#1D9E75"
    ),
    "midnight_insight": Theme(
        "midnight_insight", "Midnight Insight", "#1A1A1A", "#FFFFFF", "#C8850A"
    ),
    "executive_gold": Theme(
        "executive_gold", "Executive Gold", "#0D0D0D", "#FFFFFF", "#C8850A"
    ),
}


def get_theme(theme_id: str) -> Theme:
    return THEMES[theme_id]
