import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from telegram.webview import WebViewExtractor


def test_parse_tg_web_app_data_success():
    """Проверка успешного парсинга и декодирования tgWebAppData из URL-фрагмента."""
    raw_init_data = "query_id=AAH_xxxx&user=%7B%22id%22%3A9000000000466709%2C%22first_name%22%3A%22Ivan%22%7D&auth_date=1794960000&hash=1234567890abcdef"
    url = f"https://oldprison-prod.luckygem.online/#tgWebAppData={raw_init_data}&tgWebAppVersion=8.0&tgWebAppPlatform=web"

    extracted = WebViewExtractor.parse_tg_web_app_data_from_url(url)
    assert "query_id=AAH_xxxx" in extracted
    assert 'user={"id":9000000000466709,"first_name":"Ivan"}' in extracted
    assert "auth_date=1794960000" in extracted
    assert "hash=1234567890abcdef" in extracted


def test_parse_tg_web_app_data_query_param():
    """Проверка извлечения tgWebAppData из строки запроса (?tgWebAppData=...)."""
    url = "https://oldprison-prod.luckygem.online/?tgWebAppData=user%3Dtest%26hash%3D123"
    extracted = WebViewExtractor.parse_tg_web_app_data_from_url(url)
    assert extracted == "user=test&hash=123"


def test_parse_tg_web_app_data_missing():
    """Проверка выброса исключения ValueError, если tgWebAppData отсутствует."""
    with pytest.raises(ValueError, match="tgWebAppData not found"):
        WebViewExtractor.parse_tg_web_app_data_from_url("https://oldprison-prod.luckygem.online/#tgWebAppVersion=8.0")


def test_parse_tg_web_app_data_empty_url():
    """Проверка выброса исключения ValueError при передаче пустого URL."""
    with pytest.raises(ValueError, match="URL cannot be empty"):
        WebViewExtractor.parse_tg_web_app_data_from_url("")
