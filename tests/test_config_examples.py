from pathlib import Path


def _read_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def test_config_and_env_examples_have_no_overlapping_keys() -> None:
    config_keys = _read_keys(Path("config.ini.example"))
    env_keys = _read_keys(Path(".env.example"))
    assert config_keys.isdisjoint(env_keys)


def test_sensitive_keys_only_exist_in_env_example() -> None:
    config_keys = _read_keys(Path("config.ini.example"))
    env_keys = _read_keys(Path(".env.example"))

    sensitive_keys = {"DEEPL_API_KEY", "TELEGRAM_BOT_TOKEN", "MINIAPP_API_KEY"}
    assert sensitive_keys.issubset(env_keys)
    assert sensitive_keys.isdisjoint(config_keys)
