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
              doCheck = false;
            };

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

            (ps.callPackage ./nix/cocotbext-axi.nix { cocotb = myCocotb; })

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
            verilatorPinned
            pkgs.gcc
            pkgs.gnumake
            pkgs.lcov
            pkgs.gtkwave
            pkgs.git
            pkgs.pkg-config
            pythonEnv
          ];

          shellHook = ''
            unset VERILATOR_ROOT
            echo "==== RISC-V IOMMU verification env ===="
            echo "  verilator: $(verilator --version | head -n1)"
            echo "  python:    $(python --version)"
            echo "  cocotb:    $(python -c 'import cocotb; print(cocotb.__version__)')"
          '';
        };
      });
}