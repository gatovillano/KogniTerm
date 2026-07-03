import importlib


def test_telegram_config_wizard_saves_channel(tmp_path, monkeypatch):
    config_file = tmp_path / ".kogniterm" / "server_config.json"
    monkeypatch.setenv("KOGNITERM_SERVER_CONFIG_FILE", str(config_file))

    from kogniterm.terminal.cli import CLIHandler

    handler = CLIHandler()
    input_values = iter(["telegram_ops", "y", "y", "y"])
    secret_values = iter(["123456:ABCDEF"])

    handler.handle_telegram_config(
        [],
        input_fn=lambda prompt: next(input_values),
        secret_input_fn=lambda prompt: next(secret_values),
        print_fn=lambda *args, **kwargs: None,
    )

    server_config_module = importlib.import_module("kogniterm.server.config")
    manager = server_config_module.ServerConfigManager()
    telegram_channels = [channel for channel in manager.settings.channels if channel.type == "telegram_bot"]

    assert len(telegram_channels) == 1
    assert telegram_channels[0].name == "telegram_ops"
    assert telegram_channels[0].enabled is True
    assert telegram_channels[0].params["token"] == "123456:ABCDEF"


def test_add_channel_upserts_existing_channel(tmp_path, monkeypatch):
    config_file = tmp_path / ".kogniterm" / "server_config.json"
    monkeypatch.setenv("KOGNITERM_SERVER_CONFIG_FILE", str(config_file))

    server_config_module = importlib.import_module("kogniterm.server.config")
    ChannelConfig = server_config_module.ChannelConfig
    ServerConfigManager = server_config_module.ServerConfigManager

    manager = ServerConfigManager()
    manager.add_channel(
        ChannelConfig(
            name="telegram_default",
            type="telegram",
            enabled=False,
            params={"token": "token-one"},
        )
    )
    manager.add_channel(
        ChannelConfig(
            name="telegram_default",
            type="telegram",
            enabled=True,
            params={"token": "token-two"},
        )
    )

    telegram_channels = [channel for channel in manager.settings.channels if channel.name == "telegram_default"]

    assert len(telegram_channels) == 1
    assert telegram_channels[0].enabled is True
    assert telegram_channels[0].params["token"] == "token-two"