{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = with pkgs; [
    automake
    autoconf
    libtool
    gettext
    pkg-config
    glib
    cups
    flex
    bison
    libtiff
  ];
}
