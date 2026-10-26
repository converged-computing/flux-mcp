import os
import pwd
import shutil

LOGIN_DEFS = "/etc/login.defs"


def default_path(uid=None, login_defs=LOGIN_DEFS):
    """
    Return the PATH login(1) gives a user. This is ENV_PATH in login.defs, or
    ENV_SUPATH for root, and the POSIX CS_PATH if neither is set.
    """
    uid = os.getuid() if uid is None else uid
    key = "ENV_SUPATH" if uid == 0 else "ENV_PATH"
    try:
        with open(login_defs) as fd:
            for line in fd:
                fields = line.split()
                if len(fields) == 2 and fields[0] == key:
                    return fields[1].removeprefix("PATH=")
    except OSError:
        pass
    return os.confstr("CS_PATH")


def user_environment():
    """
    Return a minimal environment for the current user, built from the password
    database and login defaults and not from the environment of this process.
    """
    user = pwd.getpwuid(os.getuid())
    path = default_path(user.pw_uid).split(":")

    # A user in a Flux instance has flux on PATH, so keep it there for jobs.
    flux = shutil.which("flux")
    if flux and os.path.dirname(flux) not in path:
        path.append(os.path.dirname(flux))

    return {
        "HOME": user.pw_dir,
        "USER": user.pw_name,
        "LOGNAME": user.pw_name,
        "SHELL": user.pw_shell or "/bin/sh",
        "PATH": ":".join(path),
    }
