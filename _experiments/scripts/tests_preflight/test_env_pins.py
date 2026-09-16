"""`check_env` on environments built to be wrong.

Gate 1 shells out to this module and reads only its exit status, so a check that
silently examines nothing is indistinguishable from a clean environment. That is
what happened: the stack was called "evaluation" and the file is
`requirements-eval.txt`, so `requirements-evaluation.txt` was read, no pin was
found, and an environment without jinja2, matplotlib or openpyxl still reported
"12 of 12 match".
"""

from __future__ import annotations

import pytest

from _experiments.env import check_env


def test_the_evaluation_stack_names_a_file_that_exists_and_pins_packages():
    path = check_env.pin_path("evaluation")
    assert path.is_file(), f"{path} is the file gate 1 checks and it is not in the repository"
    pins = check_env.read_pins(path)
    for package in ("numpy", "sqlglot", "jinja2", "matplotlib", "openpyxl", "pytest"):
        assert package in pins, f"{path.name} does not pin {package}"


def test_the_serving_stack_names_a_file_that_exists_and_pins_packages():
    path = check_env.pin_path("serving")
    assert path.is_file()
    assert "vllm" in check_env.read_pins(path)


def test_a_missing_package_is_reported_by_name(monkeypatch, capsys):
    monkeypatch.setattr(check_env, "installed",
                        lambda name: None if name == "sqlglot" else "9.9.9")
    monkeypatch.setattr(check_env, "platform_tools_pins", lambda: (None, {"numpy": "9.9.9"}))
    code = check_env.main([])
    assert code == 1
    assert "missing: sqlglot" in capsys.readouterr().err


def test_a_version_that_is_not_the_pin_is_reported(monkeypatch, capsys):
    pins = check_env.read_pins(check_env.pin_path("evaluation"))
    monkeypatch.setattr(check_env, "installed",
                        lambda name: "0.0.1" if name == "sqlglot" else pins.get(name, "9.9.9"))
    monkeypatch.setattr(check_env, "platform_tools_pins", lambda: (None, {"numpy": pins["numpy"]}))
    code = check_env.main([])
    assert code == 1
    err = capsys.readouterr().err
    assert "sqlglot: installed 0.0.1" in err


def test_a_pin_file_that_is_not_there_is_a_hard_error(monkeypatch, capsys):
    monkeypatch.setitem(check_env.PIN_FILES, "evaluation", "requirements-evaluation.txt")
    monkeypatch.setattr(check_env, "installed", lambda name: "9.9.9")
    code = check_env.main([])
    assert code == 2, "a pin file that does not exist must not read as a clean environment"
    assert "missing pin file" in capsys.readouterr().err


def test_read_pins_refuses_a_file_that_is_not_there(tmp_path):
    with pytest.raises(check_env.MissingPinFile):
        check_env.read_pins(tmp_path / "requirements-nothing.txt")


def test_a_pin_that_disagrees_with_the_platform_file_is_named(monkeypatch, capsys):
    pins = check_env.read_pins(check_env.pin_path("evaluation"))
    monkeypatch.setattr(check_env, "platform_tools_pins",
                        lambda: ("requirements-tools.txt", {"numpy": "1.26.4"}))
    monkeypatch.setattr(check_env, "installed", lambda name: pins.get(name, "1.26.4"))
    code = check_env.main([])
    assert code == 1
    err = capsys.readouterr().err
    assert "numpy" in err and "1.26.4" in err
