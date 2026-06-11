from app.services.zafronix_api import _parse_roster_body, _normalize_player


def test_parse_roster_array_body():
    body = [
        {"jersey": 1, "name": "Memo Ochoa", "position": "GK", "club": {"name": "Club América", "country": "Mexico"}},
        {"jersey": 9, "name": "Santiago Gimenez", "position": "FWD", "club": {"name": "AC Milan", "country": "Italy"}},
    ]
    result = _parse_roster_body(body)
    assert result["ok"] is True
    assert len(result["players"]) == 2
    assert result["players"][0]["position"] == "GK"
    assert result["players"][1]["position"] == "FWD"
    assert result["players"][0]["club"] == "Club América (Mexico)"


def test_normalize_player_maps_df_to_def():
    player = _normalize_player({"name": "Test Defender", "position": "DF", "club": "FC Test"})
    assert player is not None
    assert player["position"] == "DEF"


def test_normalize_player_maps_fw_to_fwd():
    player = _normalize_player({"name": "Striker", "position": "FW", "club": "FC Test"})
    assert player is not None
    assert player["position"] == "FWD"
    assert player["raw_position"] == "FW"


def test_normalize_player_maps_mf_to_mid():
    player = _normalize_player({"name": "Mid", "position": "MF", "club": "FC Test"})
    assert player is not None
    assert player["position"] == "MID"


def test_normalize_player_unknown_goes_to_other():
    player = _normalize_player({"name": "Utility", "position": "AM", "club": "FC Test"})
    assert player is not None
    assert player["position"] == "OTHER"


def test_normalize_player_captain_suffix():
    player = _normalize_player({"name": "Lionel Messi (captain)", "position": "FW", "club": "MIA"})
    assert player is not None
    assert player["name"] == "Lionel Messi"
    assert player["is_captain"] is True


def test_parse_roster_with_coach_in_dict():
    body = {
        "coach": "Javier Aguirre",
        "players": [{"name": "Player A", "position": "MID", "jersey": 10}],
    }
    result = _parse_roster_body(body)
    assert result["coach"] == "Javier Aguirre"
    assert result["ok"] is True
