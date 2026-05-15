{
  description = "RISC-V IOMMU verification environment";

  inputs = {
    nixpkgs.url     = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # ----- Python 環境 -----
        py = pkgs.python311;
        pythonEnv = py.withPackages (ps:
          let
            # 1. cocotb 1.9.2
            #    cocotb 2.0 系は cocotb.handle._AssignmentResult を削除しており、
            #    cocotb-bus 0.2.1 (= 最新 release) と互換性が無い。
            #    cocotb-bus の cocotb 2.0 対応 release はまだ出ていないので、
            #    cocotb 側を 1.x の最後の安定版に固定する。
            #    sha256 が分からない場合は pkgs.lib.fakeHash にすると
            #    nix が「got: sha256-xxx」 と正しい値を教えてくれるので
            #    それで上書きする。
            myCocotb = ps.buildPythonPackage rec {
              pname = "cocotb";
              version = "1.9.2";
              src = ps.fetchPypi {
                inherit pname version;
                sha256 = "sha256-5M3q9R7BsU5UMAg6xW7cC0itBRhPAwfZDeRP97/bFlI";  # ← 初回 nix develop 実行時に
                                             #   出てくる正しい hash で書き換える
              };

              propagatedBuildInputs = [
                ps.find-libpython
              ];

              doCheck = false;
            };

            # 2. cocotb-bus
            myCocotbBus = ps.buildPythonPackage rec {
              pname = "cocotb-bus";
              version = "0.2.1";

              src = pkgs.fetchFromGitHub {
                owner = "cocotb";
                repo = "cocotb-bus";
                rev = "v${version}";
                hash = "sha256-B4bEM530wLlE6RUytJikGj1Xi7O+gDpjEB5bt7hw7CQ";
              };

              propagatedBuildInputs = [ myCocotb ];
              doCheck = false;
            };

          in [
            myCocotb
            myCocotbBus

            # 3. cocotbext-axi (= callPackage 経由)
            (ps.callPackage ./nix/cocotbext-axi.nix { cocotb = myCocotb; })

            # 4. その他 Python ツール
            ps.pytest
            ps.pyyaml
          ]
        );

        # ----- Verilator 5.046 を pin -----
        verilatorPinned = pkgs.verilator.overrideAttrs (old: rec {
          version = "5.046";
          src = pkgs.fetchFromGitHub {
            owner  = "verilator";
            repo   = "verilator";
            rev    = "v${version}";
            sha256 = "1gr1qhxvl4856hnmnx46dqd2qp0jhdh959zm2qfmxzzh19np7xkm";
          };
        });
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            # --- SystemVerilog シミュレータ ---
            verilatorPinned

            # --- C/C++ toolchain ---
            # Verilator が生成した C++ を local で build するのに必要
            pkgs.gcc
            pkgs.gnumake
            pkgs.pkg-config

            # --- FST 波形ダンプに必要なライブラリ ---
            # libfst (= verilated_fst_c.cpp) が <zlib.h> を直接 include する。
            # これが無いと FST build が "fatal error: 'zlib.h' file not found" で死ぬ。
            # pkg-config 経由 (= Makefile の ZLIB_CFLAGS / ZLIB_LIBS) で参照される。
            pkgs.zlib

            # FST 圧縮の代替バックエンド (= 新しめの Verilator は zstd も使う場合あり)
            pkgs.zstd

            # --- 波形ビューア & カバレッジ ---
            pkgs.gtkwave
            pkgs.lcov

            # --- バージョン管理 & 一般ユーティリティ ---
            pkgs.git
            pkgs.tree

            # --- Python (cocotb + 拡張) ---
            pythonEnv
          ];

          shellHook = ''
            unset VERILATOR_ROOT

            # -----------------------------------------------------------------
            # Colored, bold prompt for the nix dev shell
            # -----------------------------------------------------------------
            export PS1='\[\033[1;36m\](nix:iommu)\[\033[0m\] \[\033[1;33m\]\w\[\033[0m\] \[\033[1;32m\]\$\[\033[0m\] '

            BOLD=$'\033[1m'; CYAN=$'\033[1;36m'; GREEN=$'\033[1;32m'; RST=$'\033[0m'
            echo "$CYAN==== RISC-V IOMMU verification env ====$RST"
            echo "  ''${BOLD}verilator:$RST  $(verilator --version | head -n1)"
            echo "  ''${BOLD}python:$RST     $(python --version)"
            echo "  ''${BOLD}cocotb:$RST     $(python -c 'import cocotb; print(cocotb.__version__)')"
            echo "  ''${BOLD}gcc:$RST        $(gcc --version | head -n1)"
            echo "  ''${BOLD}pkg-config:$RST $(pkg-config --version)"
            echo "  ''${BOLD}zlib:$RST       $(pkg-config --modversion zlib    2>/dev/null || echo 'NOT FOUND')  (cflags: $(pkg-config --cflags zlib 2>/dev/null))"
            echo "  ''${BOLD}zstd:$RST       $(pkg-config --modversion libzstd 2>/dev/null || echo 'NOT FOUND')"
            echo "  ''${BOLD}gtkwave:$RST    $(gtkwave --version 2>&1 | head -n1 || echo 'NOT FOUND')"
            echo "$CYAN=======================================$RST"
          '';
        };
      });
}
