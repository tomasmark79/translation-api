"""Integration check for the Linux installer; downloads real Python dependencies.

Uses an isolated home and a systemctl stub so no real services are changed.
Run as a non-root user: python3 tests/check_installer.py
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="translation-api-installer-") as temp:
        # Exercise shell and systemd quoting as well as ordinary installation.
        home = Path(temp) / 'home space %percent "quote'
        home.mkdir()
        stubs = Path(temp) / "stubs"
        stubs.mkdir()
        log = Path(temp) / "systemctl.log"
        systemctl = stubs / "systemctl"
        systemctl.write_text(
            '#!/usr/bin/env bash\n'
            'printf "%s\\n" "$*" >> "$SYSTEMCTL_LOG"\n'
            '[[ "$*" != "--user cat translation-api.service" ]]\n'
        )
        systemctl.chmod(0o755)
        env = dict(os.environ, HOME=str(home),
                   XDG_DATA_HOME=str(home / ".local/share"),
                   XDG_CONFIG_HOME=str(home / ".config"),
                   PATH=f"{stubs}:{os.environ['PATH']}", SYSTEMCTL_LOG=str(log))

        def install(*args, succeeds=True):
            result = subprocess.run(["bash", str(ROOT / "install-linux.sh"), *args],
                                    env=env, cwd=ROOT)
            assert (result.returncode == 0) == succeeds, (args, result.returncode)

        launcher = home / ".local/bin/translation-api"
        unit = home / ".config/systemd/user/translation-api.service"
        config = home / ".config/translation-api/arguments"
        data = home / ".local/share/translation-api"
        install("--update", succeeds=False)
        launcher.parent.mkdir(parents=True)
        launcher.write_text("foreign launcher\n")
        install(succeeds=False)
        assert launcher.read_text() == "foreign launcher\n"
        launcher.unlink()

        install("--service")
        assert unit.is_file()
        subprocess.run([str(launcher), "--version"], env=env, check=True)
        subprocess.run([sys.executable, str(ROOT / "tests/smoke.py"), str(launcher)],
                       env=env, check=True)
        subprocess.run([str(data / "venv/bin/python"), "-m", "unittest", "discover",
                        "-s", "tests", "-p", "test_*.py"], env=env, cwd=ROOT, check=True)
        config.write_text(config.read_text() + "# preserved on update\n")
        saved_config = config.read_text()
        log.write_text("")
        install("--update")
        assert config.read_text() == saved_config
        assert "--user restart translation-api.service" in log.read_text()

        # A symlink from another deployment must not be followed or removed.
        original_unit = unit.read_text()
        unit.unlink()
        foreign = Path(temp) / "foreign.service"
        foreign.write_text("foreign service\n")
        unit.symlink_to(foreign)
        install("--uninstall", succeeds=False)
        assert foreign.read_text() == "foreign service\n"
        assert launcher.exists()
        unit.unlink()
        unit.write_text(original_unit)

        install("--uninstall")
        assert not launcher.exists() and not unit.exists() and not data.exists()
        assert config.read_text() == saved_config
        assert "--user disable --now translation-api.service" in log.read_text()
        install("--uninstall")  # Idempotent removal.
        print("Installer lifecycle, configuration preservation and collision protection: OK")


if __name__ == "__main__":
    main()
