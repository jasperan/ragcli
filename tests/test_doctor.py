"""Tests for first-run diagnostics."""

import json

import ragcli.cli.commands.doctor as doctor_module
from ragcli.cli.commands.doctor import _resolve_oracle_config, doctor, parse_dsn_host_port


def test_parse_host_port_service_dsn():
    assert parse_dsn_host_port("localhost:1521/FREEPDB1") == ("localhost", 1521)


def test_parse_host_without_port_defaults_to_oracle_listener():
    assert parse_dsn_host_port("db.example.com/FREEPDB1") == ("db.example.com", 1521)


def test_parse_descriptor_returns_unknown():
    assert parse_dsn_host_port("(DESCRIPTION=(ADDRESS=(HOST=db)(PORT=1521)))") == (None, None)


def test_resolve_oracle_config_prefers_active_database_profile():
    config = {
        "database": {
            "active_profile": "local",
            "profiles": {
                "local": {"username": "PDBADMIN", "dsn": "oracle-free:1521/FREEPDB1"},
                "oci": {"username": "ADMIN", "dsn": "oci.example"},
            },
        },
        "oracle": {"username": "legacy", "dsn": "legacy.example"},
    }

    resolved, source = _resolve_oracle_config(config)

    assert resolved["username"] == "PDBADMIN"
    assert resolved["dsn"] == "oracle-free:1521/FREEPDB1"
    assert source == "database.profiles.local"


def test_doctor_json_writes_machine_readable_stdout(monkeypatch, capsys):
    def rich_print_should_not_be_used(*_args, **_kwargs):
        raise AssertionError("json output must bypass Rich rendering")

    monkeypatch.setattr(doctor_module.console, "print", rich_print_should_not_be_used)
    monkeypatch.setattr(doctor_module.importlib.metadata, "version", lambda _name: "1.2.3")
    monkeypatch.setattr(doctor_module, "_ragcli_executable", lambda: "/usr/bin/ragcli")
    monkeypatch.setattr(
        doctor_module,
        "_load_config_row",
        lambda rows: (
            rows.append(
                {
                    "component": "config",
                    "status": "fail",
                    "detail": "x" * 240,
                    "action": "",
                }
            )
            or (None, None)
        ),
    )
    monkeypatch.setattr(doctor_module, "_check_docker", lambda _rows: None)

    doctor(json_output=True)

    rows = json.loads(capsys.readouterr().out)
    assert rows[-1]["component"] == "config"
    assert rows[-1]["detail"] == "x" * 240
