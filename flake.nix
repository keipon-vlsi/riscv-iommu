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
            # 1. cocotb 2.0.0
            myCocotb = ps.buildPythonPackage rec {
              pname = "cocotb";
              version = "2.0.0";
              src = ps.fetchPypi {
                inherit pname version;
                sha256 = "sha256-PWZ3Lfh9CjNIEPHEHPCQOXXjC7U4MotGuSCzPUIhtTY";
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
            echo "==== RISC-V IOMMU verification env ===="
            echo "  verilator:  $(verilator --version | head -n1)"
            echo "  python:     $(python --version)"
            echo "  cocotb:     $(python -c 'import cocotb; print(cocotb.__version__)')"
            echo "  gcc:        $(gcc --version | head -n1)"
            echo "  pkg-config: $(pkg-config --version)"
            echo "  zlib:       $(pkg-config --modversion zlib    2>/dev/null || echo 'NOT FOUND')  (cflags: $(pkg-config --cflags zlib 2>/dev/null))"
            echo "  zstd:       $(pkg-config --modversion libzstd 2>/dev/null || echo 'NOT FOUND')"
            echo "  gtkwave:    $(gtkwave --version 2>&1 | head -n1 || echo 'NOT FOUND')"
            echo "======================================="
          '';
        };
      });
}