import os
import pwd

import pytest

import flux_mcp.utils.environment as environment
from flux_mcp.utils import default_path, user_environment

NAMES = {"HOME", "USER", "LOGNAME", "SHELL", "PATH"}


@pytest.mark.parametrize(
    "line", ["ENV_PATH PATH=/a:/b", "ENV_PATH /a:/b", "ENV_PATH\tPATH=/a:/b"], ids=str
)
def test_default_path_reads_login_defs(tmp_path, line):
    defs = tmp_path / "login.defs"
    defs.write_text(f"# ENV_PATH PATH=/commented\n{line}\nENV_SUPATH PATH=/root/sbin\n")
    assert default_path(uid=1000, login_defs=str(defs)) == "/a:/b"


def test_default_path_for_root(tmp_path):
    defs = tmp_path / "login.defs"
    defs.write_text("ENV_PATH PATH=/a:/b\nENV_SUPATH PATH=/root/sbin\n")
    assert default_path(uid=0, login_defs=str(defs)) == "/root/sbin"


def test_default_path_without_login_defs(tmp_path):
    assert default_path(uid=1000, login_defs=str(tmp_path / "missing")) == os.confstr("CS_PATH")


def test_user_environment_ignores_server_environment(monkeypatch):
    for name in NAMES:
        monkeypatch.setenv(name, "/from/the/server")
    monkeypatch.setenv("SERVER_ONLY", "1")
    user = pwd.getpwuid(os.getuid())

    env = user_environment()
    assert set(env) == NAMES
    assert (env["HOME"], env["USER"], env["LOGNAME"]) == (user.pw_dir, user.pw_name, user.pw_name)
    assert env["SHELL"] == (user.pw_shell or "/bin/sh")
    assert env["PATH"] == default_path()


def test_flux_directory_added_to_path(monkeypatch):
    monkeypatch.setattr(environment.shutil, "which", lambda name: "/opt/flux/bin/flux")
    assert user_environment()["PATH"] == default_path() + ":/opt/flux/bin"


def test_flux_directory_not_duplicated(monkeypatch):
    first = default_path().split(":")[0]
    monkeypatch.setattr(environment.shutil, "which", lambda name: f"{first}/flux")
    assert user_environment()["PATH"] == default_path()
