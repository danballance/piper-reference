{pkgs, ...}: {
  dotenv.enable = true;
  languages.python = {
    enable = true;
    version = "3.12";
    uv = {
      enable = true;
      sync.enable = true;
    };
  };
}
