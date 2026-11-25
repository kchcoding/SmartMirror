from app.services.outfit import recommend, target_warmth


def _c(id_, category, warmth, color="검정", waterproof=False):
    return {"id": id_, "name": f"{category}{id_}", "category": category, "warmth": warmth,
            "color": color, "waterproof": waterproof}


def test_hot_day_needs_no_outer():
    assert target_warmth(30)["outer"] == 0


def test_freezing_day_needs_thick_clothes():
    t = target_warmth(-3)
    assert t["top"] >= 4 and t["outer"] >= 4


def test_picks_closest_warmth():
    clothes = [_c(1, "top", 1), _c(2, "top", 3), _c(3, "bottom", 3), _c(4, "outer", 4)]
    weather = {"feels_like": 10, "precipitation": 0, "rain_prob_max": 0}
    best = recommend(weather, clothes=clothes)["candidates"][0]
    assert best["top"]["id"] == 2          # 체감 10° → 상의 목표 두께 3


def test_rain_prefers_waterproof_outer():
    clothes = [_c(1, "top", 3), _c(2, "bottom", 3), _c(3, "outer", 3, waterproof=False), _c(4, "outer", 3, waterproof=True)]
    weather = {"feels_like": 13, "precipitation": 0, "rain_prob_max": 90}
    best = recommend(weather, clothes=clothes)["candidates"][0]
    assert best["outer"]["id"] == 4


def test_empty_wardrobe_gives_message():
    res = recommend({"feels_like": 20, "precipitation": 0, "rain_prob_max": 0}, clothes=[])
    assert res["candidates"] == [] and res["message"]
