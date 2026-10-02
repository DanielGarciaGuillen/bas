from app.main import decode_kw


def test_decode_kw_applies_x10_scale_factor():
    assert decode_kw(180) == 18.0
