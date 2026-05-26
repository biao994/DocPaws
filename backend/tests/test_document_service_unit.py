import pytest


@pytest.mark.parametrize(
    "inp,expected",
    [
        (None, None),
        ("", None),
        ("/", None),
        ("  /  ", None),
        ("a", "a"),
        ("a/", "a"),
        ("/a", "a"),
        ("a/b", "a/b"),
        ("a//b", "a/b"),
        ("a\\b", "a/b"),
        ("\\a\\b\\", "a/b"),
        ("  a/b  ", "a/b"),
    ],
)
def test_normalize_folder_path_ok(inp, expected):
    from docpaws.usecases.document_service import normalize_folder_path

    assert normalize_folder_path(inp) == expected


@pytest.mark.parametrize("inp", ["..", "./a", "a/..", "a/./b", "a/../b"])
def test_normalize_folder_path_reject_dot_segments(inp):
    from docpaws.usecases.document_service import normalize_folder_path
    from docpaws.errors import AppError

    with pytest.raises(AppError):
        normalize_folder_path(inp)

