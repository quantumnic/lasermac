"""Tests for updater — mocked, no network needed."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from lasermac import updater


class TestIsNewer:
    def test_newer_version(self):
        assert updater._is_newer("0.2.0", "0.1.0") is True

    def test_same_version(self):
        assert updater._is_newer("0.1.0", "0.1.0") is False

    def test_older_version(self):
        assert updater._is_newer("0.0.9", "0.1.0") is False

    def test_major_bump(self):
        assert updater._is_newer("1.0.0", "0.9.9") is True

    def test_patch_bump(self):
        assert updater._is_newer("0.1.1", "0.1.0") is True


class TestCheckForUpdate:
    def _mock_response(self, tag: str, url: str = "https://example.com", body: str = "notes"):
        data = json.dumps({
            "tag_name": tag,
            "html_url": url,
            "body": body,
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = data
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("lasermac.updater.urllib.request.urlopen")
    def test_update_available(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response("v0.4.0", "https://gh.com/release")
        result = updater.check_for_update()
        assert result is not None
        assert result["version"] == "0.4.0"
        assert result["url"] == "https://gh.com/release"
        assert result["notes"] == "notes"

    @patch("lasermac.updater.urllib.request.urlopen")
    def test_no_update_same_version(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response("v0.1.0")
        result = updater.check_for_update()
        assert result is None

    @patch("lasermac.updater.urllib.request.urlopen")
    def test_no_update_older(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response("v0.0.5")
        result = updater.check_for_update()
        assert result is None

    @patch("lasermac.updater.urllib.request.urlopen")
    def test_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("network error")
        result = updater.check_for_update()
        assert result is None

    @patch("lasermac.updater.urllib.request.urlopen")
    def test_no_body(self, mock_urlopen):
        data = json.dumps({"tag_name": "v0.4.0", "html_url": "https://x.com"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = data
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        result = updater.check_for_update()
        assert result is not None
        assert result["notes"] == ""

    @patch("lasermac.updater.urllib.request.urlopen")
    def test_tag_without_v_prefix(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response("0.5.0")
        result = updater.check_for_update()
        assert result is not None
        assert result["version"] == "0.5.0"


class TestCheckAsync:
    @patch("lasermac.updater.check_for_update")
    def test_calls_callback(self, mock_check):
        mock_check.return_value = {"version": "1.0.0", "url": "x", "notes": ""}
        cb = MagicMock()
        # Run synchronously for test by calling the inner function directly
        with patch("threading.Thread") as mock_thread:
            updater.check_async(cb)
            # Get the target function and run it
            target = mock_thread.call_args[1]["target"]
            target()
        cb.assert_called_once_with({"version": "1.0.0", "url": "x", "notes": ""})
