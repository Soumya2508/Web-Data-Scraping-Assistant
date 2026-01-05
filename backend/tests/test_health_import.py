from app.main import create_app


def test_app_creates():
    app = create_app()
    assert app is not None
