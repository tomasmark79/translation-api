{ lib, python3Packages }:
python3Packages.buildPythonApplication {
  pname = "translation-api";
  version = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;
  pyproject = true;
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./LICENSE
      ./server.py
      ./tests
      ./scripts
      ./samples
    ];
  };
  build-system = [ python3Packages.setuptools ];
  dependencies = [ python3Packages.langdetect ];
  pythonImportsCheck = [ "server" ];
  doCheck = true;
  checkPhase = ''
    runHook preCheck
    python -m unittest discover -s tests -p 'test_*.py'
    runHook postCheck
  '';
  meta = {
    description = "Local asynchronous translation API backed by Ollama";
    homepage = "https://github.com/tomasmark79/translation-api";
    license = lib.licenses.gpl3Plus;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
      "x86_64-darwin"
      "aarch64-darwin"
    ];
    mainProgram = "translation-api";
  };
}
