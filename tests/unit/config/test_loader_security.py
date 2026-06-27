"""ConfigLoader 보안 테스트

Path traversal 공격 차단 검증.
"""

import pytest

from shared.config.loader import ConfigError, ConfigLoader


class TestPathTraversalPrevention:
    """Path traversal 공격 방지 테스트"""

    def test_path_traversal_attack_blocked(self):
        """Path traversal 공격 차단"""
        with pytest.raises(ConfigError, match="Path traversal"):
            ConfigLoader.load("../../../etc/passwd")

    def test_path_traversal_with_encoded_dots_blocked(self):
        """인코딩된 path traversal 차단"""
        with pytest.raises(ConfigError, match="Path traversal"):
            ConfigLoader.load("..%2F..%2Fetc/passwd")

    def test_path_traversal_with_mixed_encoding_blocked(self):
        """혼합 인코딩 path traversal 차단"""
        with pytest.raises(ConfigError, match="Path traversal"):
            ConfigLoader.load("..%2F../..%2Fetc/passwd")

    def test_path_traversal_with_double_encoding_blocked(self):
        """이중 인코딩 path traversal 차단"""
        with pytest.raises(ConfigError, match="Path traversal"):
            ConfigLoader.load("%2E%2E%2F%2E%2E%2Fetc/passwd")

    def test_valid_nested_path_allowed(self, tmp_path):
        """정상적인 중첩 경로는 허용"""
        # 임시 테스트 설정 디렉토리 생성
        config_dir = tmp_path / "config"
        strategies_dir = config_dir / "strategies" / "stock"
        strategies_dir.mkdir(parents=True)

        # 테스트 YAML 파일 생성
        test_file = strategies_dir / "test.yaml"
        test_file.write_text("strategy:\n  name: test\n  enabled: true\n")

        # ConfigLoader 설정 디렉토리 변경
        ConfigLoader.set_config_dir(config_dir)

        # Path traversal 에러가 발생하지 않아야 함
        try:
            result = ConfigLoader.load("strategies/stock/test.yaml")
            assert result is not None
            assert "strategy" in result
        except ConfigError as e:
            assert "Path traversal" not in str(e)

    def test_absolute_path_blocked(self):
        """절대 경로 차단"""
        with pytest.raises(ConfigError, match="Path traversal"):
            ConfigLoader.load("/etc/passwd")

    def test_backslash_path_traversal_blocked(self):
        """백슬래시 path traversal 차단 (Windows)"""
        with pytest.raises(ConfigError, match="Path traversal"):
            ConfigLoader.load("..\\..\\..\\etc\\passwd")


class TestExistsPathTraversal:
    """exists() 메서드 Path traversal 방지 테스트"""

    def test_exists_path_traversal_blocked(self):
        """exists() should block path traversal"""
        result = ConfigLoader.exists("../../../etc/passwd")
        assert result is False

    def test_exists_encoded_traversal_blocked(self):
        """exists() should block encoded path traversal"""
        result = ConfigLoader.exists("..%2F..%2Fetc/passwd")
        assert result is False

    def test_exists_double_encoded_traversal_blocked(self):
        """exists() should block double encoded path traversal"""
        result = ConfigLoader.exists("%2E%2E%2F%2E%2E%2Fetc/passwd")
        assert result is False

    def test_exists_backslash_traversal_blocked(self):
        """exists() should block backslash path traversal (Windows)"""
        result = ConfigLoader.exists("..\\..\\..\\etc\\passwd")
        assert result is False

    def test_exists_absolute_path_blocked(self):
        """exists() should block absolute paths"""
        result = ConfigLoader.exists("/etc/passwd")
        assert result is False

    def test_exists_valid_path_allowed(self, tmp_path):
        """exists() should allow valid nested paths"""
        # 임시 테스트 설정 디렉토리 생성
        config_dir = tmp_path / "config"
        strategies_dir = config_dir / "strategies" / "stock"
        strategies_dir.mkdir(parents=True)

        # 테스트 YAML 파일 생성
        test_file = strategies_dir / "test.yaml"
        test_file.write_text("strategy:\n  name: test\n")

        # ConfigLoader 설정 디렉토리 변경
        ConfigLoader.set_config_dir(config_dir)

        # 정상 경로는 True 반환
        result = ConfigLoader.exists("strategies/stock/test.yaml")
        assert result is True

    def test_exists_nonexistent_valid_path(self, tmp_path):
        """exists() should return False for valid but nonexistent paths"""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        ConfigLoader.set_config_dir(config_dir)

        # 존재하지 않지만 유효한 경로는 False 반환
        result = ConfigLoader.exists("strategies/nonexistent.yaml")
        assert result is False


class TestReloadPathTraversal:
    """reload() 메서드 Path traversal 방지 테스트"""

    def test_reload_path_traversal_blocked(self):
        """reload() should block path traversal"""
        with pytest.raises(ConfigError, match="Path traversal"):
            ConfigLoader.reload("../../../etc/passwd")

    def test_reload_encoded_traversal_blocked(self):
        """reload() should block encoded path traversal"""
        with pytest.raises(ConfigError, match="Path traversal"):
            ConfigLoader.reload("..%2F..%2Fetc/passwd")
