{pkgs, ...}: {
  languages.python = {
    enable = true;
    version = "3.12";
    poetry = {
      enable = true;
      install = {
        enable = true;
        verbosity = "debug";
      };
      activate.enable = true;
      package = pkgs.poetry;
    };
  };
}
