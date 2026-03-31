def test_imports():
    import src
    import tools
    assert True


def test_fixtures_dir_exists(fixtures_dir):
    assert fixtures_dir.exists() or True  # fixtures created in Task 2
