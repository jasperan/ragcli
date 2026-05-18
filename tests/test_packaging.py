"""Packaging regression tests."""

from setuptools import find_packages


def test_console_script_target_is_packaged():
    packages = set(find_packages())

    assert "ragcli.cli" in packages
    assert "ragcli.cli.commands" in packages
    assert "ragcli.config" in packages
    assert "ragcli.visualization" in packages
