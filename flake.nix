{
  description = "resale-watch: saved-search aggregator for secondhand marketplaces";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAll = f: nixpkgs.lib.genAttrs systems (s: f nixpkgs.legacyPackages.${s});
    in {
      packages = forAll (pkgs:
        let
          py = pkgs.python3.withPackages (p: with p; [ requests fastapi uvicorn python-multipart mcp ]);
        in {
          default = pkgs.stdenvNoCC.mkDerivation {
            pname = "resale-watch";
            version = "0.1.0";
            src = self;
            nativeBuildInputs = [ pkgs.makeWrapper ];
            installPhase = ''
              mkdir -p $out/share/resale-watch $out/bin
              cp *.py schema.sql $out/share/resale-watch/
              makeWrapper ${py}/bin/python $out/bin/resale-watch \
                --add-flags $out/share/resale-watch/cli.py
            '';
            meta.mainProgram = "resale-watch";
          };
        });

      apps = forAll (pkgs:
        let bin = "${self.packages.${pkgs.stdenv.hostPlatform.system}.default}/bin/resale-watch";
            app = cmd: { type = "app"; program = toString (pkgs.writeShellScript "resale-watch-${cmd}" ''exec ${bin} ${cmd} "$@"''); };
        in {
          default = { type = "app"; program = bin; };
          poll = app "poll";
          mcp = app "mcp";
          web = app "web";
        });
    };
}
