"""
Official 2026 international football tournament data:
48-team draw, 16 host cities. Match schedule comes from openfootball/worldcup.json.
"""

from __future__ import annotations

OFFICIAL_TEAMS = [
    {"code": "MEX", "name": "Mexico", "group": "A", "elo": 1780},
    {"code": "RSA", "name": "South Africa", "group": "A", "elo": 1620},
    {"code": "KOR", "name": "South Korea", "group": "A", "elo": 1780},
    {"code": "CZE", "name": "Czechia", "group": "A", "elo": 1720},
    {"code": "CAN", "name": "Canada", "group": "B", "elo": 1720},
    {"code": "BIH", "name": "Bosnia and Herzegovina", "group": "B", "elo": 1580},
    {"code": "QAT", "name": "Qatar", "group": "B", "elo": 1650},
    {"code": "SUI", "name": "Switzerland", "group": "B", "elo": 1800},
    {"code": "BRA", "name": "Brazil", "group": "C", "elo": 2100},
    {"code": "MAR", "name": "Morocco", "group": "C", "elo": 1880},
    {"code": "HAI", "name": "Haiti", "group": "C", "elo": 1480},
    {"code": "SCO", "name": "Scotland", "group": "C", "elo": 1750},
    {"code": "USA", "name": "United States", "group": "D", "elo": 1820},
    {"code": "PAR", "name": "Paraguay", "group": "D", "elo": 1650},
    {"code": "AUS", "name": "Australia", "group": "D", "elo": 1720},
    {"code": "TUR", "name": "Türkiye", "group": "D", "elo": 1780},
    {"code": "GER", "name": "Germany", "group": "E", "elo": 1980},
    {"code": "CUW", "name": "Curaçao", "group": "E", "elo": 1400},
    {"code": "CIV", "name": "Côte d'Ivoire", "group": "E", "elo": 1700},
    {"code": "ECU", "name": "Ecuador", "group": "E", "elo": 1750},
    {"code": "NED", "name": "Netherlands", "group": "F", "elo": 1920},
    {"code": "JPN", "name": "Japan", "group": "F", "elo": 1820},
    {"code": "SWE", "name": "Sweden", "group": "F", "elo": 1780},
    {"code": "TUN", "name": "Tunisia", "group": "F", "elo": 1650},
    {"code": "BEL", "name": "Belgium", "group": "G", "elo": 1880},
    {"code": "EGY", "name": "Egypt", "group": "G", "elo": 1700},
    {"code": "IRN", "name": "Iran", "group": "G", "elo": 1780},
    {"code": "NZL", "name": "New Zealand", "group": "G", "elo": 1550},
    {"code": "ESP", "name": "Spain", "group": "H", "elo": 2020},
    {"code": "CPV", "name": "Cape Verde", "group": "H", "elo": 1580},
    {"code": "KSA", "name": "Saudi Arabia", "group": "H", "elo": 1650},
    {"code": "URU", "name": "Uruguay", "group": "H", "elo": 1900},
    {"code": "FRA", "name": "France", "group": "I", "elo": 2050},
    {"code": "IRQ", "name": "Iraq", "group": "I", "elo": 1580},
    {"code": "SEN", "name": "Senegal", "group": "I", "elo": 1750},
    {"code": "NOR", "name": "Norway", "group": "I", "elo": 1720},
    {"code": "ARG", "name": "Argentina", "group": "J", "elo": 2080},
    {"code": "ALG", "name": "Algeria", "group": "J", "elo": 1680},
    {"code": "AUT", "name": "Austria", "group": "J", "elo": 1780},
    {"code": "JOR", "name": "Jordan", "group": "J", "elo": 1550},
    {"code": "POR", "name": "Portugal", "group": "K", "elo": 1950},
    {"code": "COD", "name": "DR Congo", "group": "K", "elo": 1600},
    {"code": "UZB", "name": "Uzbekistan", "group": "K", "elo": 1520},
    {"code": "COL", "name": "Colombia", "group": "K", "elo": 1880},
    {"code": "ENG", "name": "England", "group": "L", "elo": 2000},
    {"code": "CRO", "name": "Croatia", "group": "L", "elo": 1850},
    {"code": "GHA", "name": "Ghana", "group": "L", "elo": 1620},
    {"code": "PAN", "name": "Panama", "group": "L", "elo": 1600},
]

HOST_CITIES = {
    "Atlanta": {"country": "USA", "lat": 33.755, "lng": -84.401, "stadium": "Mercedes-Benz Stadium", "ticket_usd": 185},
    "Boston": {"country": "USA", "lat": 42.091, "lng": -71.264, "stadium": "Gillette Stadium", "ticket_usd": 165},
    "Dallas": {"country": "USA", "lat": 32.747, "lng": -97.093, "stadium": "AT&T Stadium", "ticket_usd": 195},
    "Houston": {"country": "USA", "lat": 29.685, "lng": -95.410, "stadium": "NRG Stadium", "ticket_usd": 175},
    "Kansas City": {"country": "USA", "lat": 39.049, "lng": -94.484, "stadium": "Arrowhead Stadium", "ticket_usd": 155},
    "Los Angeles": {"country": "USA", "lat": 33.953, "lng": -118.339, "stadium": "SoFi Stadium", "ticket_usd": 220},
    "Miami": {"country": "USA", "lat": 25.958, "lng": -80.239, "stadium": "Hard Rock Stadium", "ticket_usd": 210},
    "New York": {"country": "USA", "lat": 40.813, "lng": -74.074, "stadium": "MetLife Stadium", "ticket_usd": 230},
    "Philadelphia": {"country": "USA", "lat": 39.901, "lng": -75.168, "stadium": "Lincoln Financial Field", "ticket_usd": 170},
    "San Francisco": {"country": "USA", "lat": 37.403, "lng": -121.970, "stadium": "Levi's Stadium", "ticket_usd": 200},
    "Seattle": {"country": "USA", "lat": 47.595, "lng": -122.332, "stadium": "Lumen Field", "ticket_usd": 180},
    "Toronto": {"country": "Canada", "lat": 43.633, "lng": -79.419, "stadium": "BMO Field", "ticket_usd": 160},
    "Vancouver": {"country": "Canada", "lat": 49.277, "lng": -123.109, "stadium": "BC Place", "ticket_usd": 155},
    "Mexico City": {"country": "Mexico", "lat": 19.303, "lng": -99.151, "stadium": "Estadio Azteca", "ticket_usd": 140},
    "Guadalajara": {"country": "Mexico", "lat": 20.682, "lng": -103.462, "stadium": "Estadio Akron", "ticket_usd": 120},
    "Monterrey": {"country": "Mexico", "lat": 25.669, "lng": -100.244, "stadium": "Estadio BBVA", "ticket_usd": 125},
}

STADIUM_TO_CITY = {info["stadium"].lower(): city for city, info in HOST_CITIES.items()}

KNOCKOUT_ROUNDS = [
    {"id": "r32", "label": "Round of 32", "matches": 16},
    {"id": "r16", "label": "Round of 16", "matches": 8},
    {"id": "qf", "label": "Quarter-Finals", "matches": 4},
    {"id": "sf", "label": "Semi-Finals", "matches": 2},
    {"id": "final", "label": "Final", "matches": 1},
]

HISTORICAL_RESULTS = [
    ("BRA", "ARG", 2, 1), ("FRA", "GER", 1, 0), ("ENG", "ESP", 1, 1),
    ("USA", "MEX", 2, 0), ("KOR", "JPN", 1, 2), ("NED", "BEL", 3, 1),
    ("POR", "ENG", 0, 1), ("URU", "COL", 0, 1), ("MAR", "SEN", 1, 0),
    ("BRA", "FRA", 2, 0), ("ARG", "ENG", 1, 0), ("GER", "ESP", 0, 2),
    ("MEX", "USA", 1, 2), ("COL", "URU", 2, 1), ("FRA", "ENG", 1, 2),
    ("ESP", "GER", 2, 1), ("CAN", "USA", 1, 3), ("JPN", "BRA", 0, 4),
]
