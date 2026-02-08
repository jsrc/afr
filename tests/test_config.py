from pathlib import Path

from afr_pusher.config import Settings


def test_settings_from_files_uses_defaults_when_files_missing(tmp_path: Path) -> None:
    settings = Settings.from_files(
        config_file=tmp_path / "missing.ini",
        env_file=tmp_path / ".env",
        base_env={},
    )

    assert settings.afr_homepage_url == "https://www.afr.com"
    assert settings.afr_max_articles == 10
    assert settings.request_timeout_sec == 12
    assert settings.translator_provider == "deepl"
    assert settings.run_interval_sec == 600
    assert settings.dry_run is False
    assert settings.telegram_bot_token is None
    assert settings.desktop_send_script is not None


def test_settings_from_files_reads_ini_values(tmp_path: Path) -> None:
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        "[settings]\n"
        "AFR_MAX_ARTICLES=7\n"
        "TRANSLATOR_PROVIDER=noop\n"
        "WECHAT_TARGET=Ops Team\n",
        encoding="utf-8",
    )

    settings = Settings.from_files(
        config_file=config_file,
        env_file=tmp_path / ".env",
        base_env={},
    )

    assert settings.afr_max_articles == 7
    assert settings.translator_provider == "noop"
    assert settings.wechat_target == "Ops Team"


def test_settings_from_files_uses_dotenv_to_override_ini(tmp_path: Path) -> None:
    config_file = tmp_path / "config.ini"
    config_file.write_text(
        "[settings]\n"
        "AFR_MAX_ARTICLES=10\n"
        "TELEGRAM_BOT_TOKEN=ini-token\n",
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AFR_MAX_ARTICLES=3\n"
        "TELEGRAM_BOT_TOKEN=env-token\n",
        encoding="utf-8",
    )

    settings = Settings.from_files(
        config_file=config_file,
        env_file=env_file,
        base_env={},
    )

    assert settings.afr_max_articles == 3
    assert settings.telegram_bot_token == "env-token"


def test_settings_from_files_keeps_os_env_as_highest_priority(tmp_path: Path) -> None:
    config_file = tmp_path / "config.ini"
    config_file.write_text("[settings]\nTELEGRAM_BOT_TOKEN=ini-token\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("TELEGRAM_BOT_TOKEN=env-token\n", encoding="utf-8")

    settings = Settings.from_files(
        config_file=config_file,
        env_file=env_file,
        base_env={"TELEGRAM_BOT_TOKEN": "os-token"},
    )

    assert settings.telegram_bot_token == "os-token"
