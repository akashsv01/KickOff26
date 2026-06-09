"""Squad names and demo lineup packages for match detail views."""

from __future__ import annotations

# Typical formation players per team code (display names)
_SQUAD_TEMPLATES: dict[str, list[str]] = {
    "BRA": ["Alisson", "Danilo", "Marquinhos", "Bastos", "Wendell", "Paquetá", "André", "Rodrygo", "Vinícius", "Raphinha", "Richarlison"],
    "ARG": ["Martínez", "Molina", "Romero", "Otamendi", "Tagliafico", "De Paul", "Mac Allister", "Lo Celso", "Messi", "Álvarez", "Lautaro"],
    "FRA": ["Maignan", "Koundé", "Saliba", "Upamecano", "Hernandez", "Tchouaméni", "Kanté", "Griezmann", "Dembélé", "Mbappé", "Giroud"],
    "GER": ["Neuer", "Kimmich", "Rüdiger", "Schlotterbeck", "Raum", "Kroos", "Gündogan", "Musiala", "Sané", "Havertz", "Wirtz"],
    "ENG": ["Pickford", "Walker", "Stones", "Maguire", "Shaw", "Rice", "Bellingham", "Foden", "Saka", "Kane", "Palmer"],
    "ESP": ["Simón", "Carvajal", "Laporte", "Le Normand", "Balde", "Rodri", "Pedri", "Olmo", "Yamal", "Morata", "Williams"],
    "MEX": ["Ochoa", "Araujo", "Vásquez", "Montes", "Gallardo", "Álvarez", "Chávez", "Lozano", "Herrera", "Jiménez", "Antuna"],
    "USA": ["Turner", "Dest", "Richards", "Robinson", "Ream", "Adams", "Musah", "McKennie", "Pulisic", "Weah", "Balogun"],
    "POR": ["Costa", "Cancelo", "Dias", "Inácio", "Mendes", "Neves", "Vitinha", "B.Fernandes", "Leão", "Ronaldo", "Ramos"],
    "NED": ["Verbruggen", "Dumfries", "De Ligt", "Van Dijk", "Blind", "Wijnaldum", "Gravenberch", "Gakpo", "Depay", "Simons", "Berg"],
}

_BENCH_TEMPLATES: dict[str, list[str]] = {
    "BRA": ["Ederson", "Breno", "Fabinho", "Casemiro", "Martinelli", "Endrick", "Vini Jr."],
    "ARG": ["Rulli", "Acuña", "Paredes", "Enzo", "Di María", "Correa", "Dibu"],
    "FRA": ["Areola", "Konaté", "Camavinga", "Coman", "Thuram", "Kolo Muani", "Zaire-Emery"],
    "GER": ["Ter Stegen", "Süle", "Brandt", "Wirtz", "Füllkrug", "Mittelstädt", "Andrich"],
    "ENG": ["Ramsdale", "Trippier", "Grealish", "Toney", "Watkins", "Mainoo", "Henderson"],
    "ESP": ["Raya", "Grimaldo", "Merino", "Ferran", "Joselu", "Oyarzabal", "Cucurella"],
    "MEX": ["Cota", "Sánchez", "Guardado", "Vega", "Funes Mori", "Ortega", "Reyes"],
    "USA": ["Horvath", "Long", "de la Torre", "Wright", "Pepi", "Morris", "Lund"],
    "POR": ["Patrício", "Pepe", "Palhinha", "Bernardo", "Jota", "Neto", "Inácio"],
    "NED": ["Flekken", "Frimpong", "Koopmeiners", "Malen", "Weghorst", "Stengs", "Zirkzee"],
}

_DEFAULT_NAMES = [
    "GK", "RB", "CB1", "CB2", "LB", "CDM", "CM", "CAM", "RW", "ST", "LW",
]

_DEMO_FALLBACK_NAMES = [
    "Jiménez", "Lozano", "Promes", "Mokoena", "Álvarez", "Williams", "Saka", "Kane",
]

_FORMATION = "4-3-3"
_XI_POSITIONS = ["GK", "RB", "CB", "CB", "LB", "CDM", "CM", "CAM", "RW", "ST", "LW"]
_XI_GRIDS = ["1:1", "2:4", "2:3", "2:2", "2:1", "3:3", "3:2", "3:1", "4:3", "4:2", "4:1"]
_BENCH_POSITIONS = ["GK", "DF", "DF", "MF", "MF", "FW", "FW"]


def get_squad_player_names(team_code: str) -> list[str]:
    """Return display names for demo event simulation."""
    names = _SQUAD_TEMPLATES.get(team_code)
    return list(names) if names else list(_DEMO_FALLBACK_NAMES)


def build_demo_lineup_package(team_code: str, team_name: str) -> dict:
    """Full lineup payload matching API-Football shape (formation, XI, bench, coach)."""
    names = _SQUAD_TEMPLATES.get(team_code)
    if not names:
        names = [f"{team_name} {_DEFAULT_NAMES[i]}" for i in range(11)]

    bench_names = _BENCH_TEMPLATES.get(team_code)
    if not bench_names:
        bench_names = [f"{team_name} Sub {i + 1}" for i in range(7)]

    starting_xi = [
        {
            "number": i + 1,
            "name": names[i],
            "position": _XI_POSITIONS[i],
            "grid": _XI_GRIDS[i],
        }
        for i in range(11)
    ]
    bench = [
        {
            "number": 12 + i,
            "name": bench_names[i],
            "position": _BENCH_POSITIONS[i],
            "grid": "",
        }
        for i in range(len(bench_names))
    ]
    return {
        "formation": _FORMATION,
        "coach": f"Coach {team_name}",
        "starting_xi": starting_xi,
        "bench": bench,
    }


def get_lineup(team_code: str, team_name: str) -> list[dict]:
    """Return 11-player starting lineup for display (legacy helper)."""
    return build_demo_lineup_package(team_code, team_name)["starting_xi"]
