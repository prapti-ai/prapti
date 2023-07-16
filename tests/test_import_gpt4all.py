def test_import_gpt4all():
    """check that gpt4all loads cleanly.
    as of July 26, 2023 gpt4all generates a deprecation warning, reported here:
        https://github.com/nomic-ai/gpt4all/issues/1212
    """
    import gpt4all
    assert True
