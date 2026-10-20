from setups_manager.cli import main


def test_main_prints_greeting(capsys):
    assert main([]) == 0
    assert "setups-manager" in capsys.readouterr().out
