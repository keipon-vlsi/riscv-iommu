{ buildPythonPackage, fetchFromGitHub, cocotb }:

buildPythonPackage rec {
  pname = "cocotbext-axi";
  version = "0.1.28"; # エラーログに合わせて最新版の 0.1.28 にしています

  # PyPIではなく、GitHubから直接取得する
  src = fetchFromGitHub {
    owner = "alexforencich";
    repo = "cocotbext-axi";
    rev = "v${version}"; # GitHubのタグ (v0.1.28)
    hash = "sha256-z8csYidDWTvNIYQgM/bPi4VsQwOSc9gnqGQEXMH/jU8"; # ★わざと空にしておき、後でエラーから取得します
  };

  # cocotb に依存していることを明示
  propagatedBuildInputs = [ cocotb ];

  # テストはスキップ
  doCheck = false;
}