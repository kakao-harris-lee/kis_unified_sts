"""API 에러 메시지 sanitization 테스트"""


import pytest


class TestSanitizeErrorMessage:
    """sanitize_error_message() 기본 기능 테스트"""

    def test_sanitize_unix_file_path(self):
        """Unix 파일 경로 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("Config error in /etc/app/config.yaml")
        result = sanitize_error_message(exc)
        assert "/etc/app/config.yaml" not in result
        assert "[REDACTED]" in result

    def test_sanitize_windows_file_path(self):
        """Windows 파일 경로 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("Config error in C:\\Users\\app\\config.yaml")
        result = sanitize_error_message(exc)
        assert "C:\\Users\\app\\config.yaml" not in result
        assert "[REDACTED]" in result

    def test_sanitize_database_connection_string(self):
        """DB 연결 문자열 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ConnectionError("Failed to connect to postgresql://user:pass@localhost:5432/db")
        result = sanitize_error_message(exc)
        assert "postgresql://user:pass@localhost:5432/db" not in result
        assert "[REDACTED]" in result

    def test_sanitize_sql_query(self):
        """SQL 쿼리 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = RuntimeError("Query failed: SELECT * FROM users WHERE id=1")
        result = sanitize_error_message(exc)
        assert "SELECT * FROM users" not in result
        assert "[REDACTED]" in result

    def test_sanitize_ip_address(self):
        """IP 주소 및 포트 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ConnectionError("Failed to connect to 192.168.1.100:8080")
        result = sanitize_error_message(exc)
        assert "192.168.1.100:8080" not in result
        assert "[REDACTED]" in result

    def test_sanitize_api_key(self):
        """API 키 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("Invalid api_key: sk-1234567890abcdefghijklmn")
        result = sanitize_error_message(exc)
        assert "sk-1234567890abcdefghijklmn" not in result
        assert "[REDACTED]" in result

    def test_sanitize_python_object_reference(self):
        """Python 객체 참조 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = TypeError("Cannot serialize <MyClass object at 0x7f8b8c0d1e50>")
        result = sanitize_error_message(exc)
        assert "0x7f8b8c0d1e50" not in result
        assert "[REDACTED]" in result

    def test_include_type_parameter(self):
        """include_type=True 시 예외 타입 포함"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("Invalid input")
        result = sanitize_error_message(exc, include_type=True)
        assert "ValueError:" in result
        assert "Invalid input" in result

    def test_exclude_type_parameter(self):
        """include_type=False 시 예외 타입 미포함"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("Invalid input")
        result = sanitize_error_message(exc, include_type=False)
        assert "ValueError:" not in result
        assert "Invalid input" in result

    def test_use_generic_parameter(self):
        """use_generic=True 시 일반 메시지 반환"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("Some specific error with /path/to/file.py")
        result = sanitize_error_message(exc, use_generic=True)
        assert result == "Invalid input value"
        assert "/path/to/file.py" not in result

    def test_truncate_long_message(self):
        """긴 메시지 자르기"""
        from shared.api.error_sanitizer import sanitize_error_message

        long_message = "Error: " + ("x" * 300)
        exc = RuntimeError(long_message)
        result = sanitize_error_message(exc)
        assert len(result) <= 203  # 200 + "..."
        assert result.endswith("...")

    def test_empty_error_message(self):
        """빈 에러 메시지 처리"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("")
        result = sanitize_error_message(exc)
        # Should return generic message for ValueError
        assert result == "Invalid input value"

    def test_none_error_message(self):
        """None 에러 메시지 처리"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = RuntimeError()  # No message
        result = sanitize_error_message(exc)
        # Should return generic message
        assert "error occurred" in result.lower() or result == "Operation failed"


class TestSanitizeErrorDict:
    """sanitize_error_dict() JSON 응답 테스트"""

    def test_basic_error_dict(self):
        """기본 에러 딕셔너리 생성"""
        from shared.api.error_sanitizer import sanitize_error_dict

        exc = ValueError("Invalid input")
        result = sanitize_error_dict(exc)
        assert "error" in result
        assert result["error"] == "Invalid input"

    def test_error_dict_with_type(self):
        """타입 포함 에러 딕셔너리"""
        from shared.api.error_sanitizer import sanitize_error_dict

        exc = ValueError("Invalid input")
        result = sanitize_error_dict(exc, include_type=True)
        assert "error" in result
        assert "type" in result
        assert result["type"] == "ValueError"

    def test_error_dict_with_generic(self):
        """일반 메시지 에러 딕셔너리"""
        from shared.api.error_sanitizer import sanitize_error_dict

        exc = ValueError("Specific error")
        result = sanitize_error_dict(exc, use_generic=True)
        assert result["error"] == "Invalid input value"

    def test_error_dict_sanitizes_paths(self):
        """경로가 sanitize된 딕셔너리"""
        from shared.api.error_sanitizer import sanitize_error_dict

        exc = RuntimeError("Failed to load /etc/config.yaml")
        result = sanitize_error_dict(exc)
        assert "/etc/config.yaml" not in result["error"]
        assert "[REDACTED]" in result["error"]


class TestErrorCategories:
    """에러 카테고리별 일반 메시지 테스트"""

    def test_value_error_generic(self):
        """ValueError 일반 메시지"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("Specific detail")
        result = sanitize_error_message(exc, use_generic=True)
        assert result == "Invalid input value"

    def test_type_error_generic(self):
        """TypeError 일반 메시지"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = TypeError("Specific detail")
        result = sanitize_error_message(exc, use_generic=True)
        assert result == "Invalid data type"

    def test_key_error_generic(self):
        """KeyError 일반 메시지"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = KeyError("missing_key")
        result = sanitize_error_message(exc, use_generic=True)
        assert result == "Missing required field"

    def test_connection_error_generic(self):
        """ConnectionError 일반 메시지"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ConnectionError("Specific detail")
        result = sanitize_error_message(exc, use_generic=True)
        assert result == "Connection failed"

    def test_timeout_error_generic(self):
        """TimeoutError 일반 메시지"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = TimeoutError("Specific detail")
        result = sanitize_error_message(exc, use_generic=True)
        assert result == "Request timeout"

    def test_file_not_found_error_generic(self):
        """FileNotFoundError 일반 메시지"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = FileNotFoundError("/path/to/file.txt")
        result = sanitize_error_message(exc, use_generic=True)
        assert result == "Resource not found"

    def test_unknown_error_generic(self):
        """알 수 없는 예외 일반 메시지"""
        from shared.api.error_sanitizer import sanitize_error_message

        class CustomException(Exception):
            pass

        exc = CustomException("Specific detail")
        result = sanitize_error_message(exc, use_generic=True)
        assert result == "An error occurred while processing your request"


class TestHelperFunctions:
    """내부 헬퍼 함수 테스트"""

    def test_get_base_exception_type(self):
        """예외 타입 이름 추출"""
        from shared.api.error_sanitizer import _get_base_exception_type

        exc = ValueError("test")
        result = _get_base_exception_type(exc)
        assert result == "ValueError"

    def test_get_base_exception_type_strips_module(self):
        """모듈 경로 제거"""
        from shared.api.error_sanitizer import _get_base_exception_type

        # Even for built-in exceptions, ensure only base name is returned
        exc = ValueError("test")
        result = _get_base_exception_type(exc)
        assert "." not in result
        assert result == "ValueError"

    def test_sanitize_message_multiple_patterns(self):
        """여러 패턴 동시 제거"""
        from shared.api.error_sanitizer import _sanitize_message

        message = "Error at /etc/config.yaml: Failed to connect to 192.168.1.1:5432"
        result = _sanitize_message(message)
        assert "/etc/config.yaml" not in result
        assert "192.168.1.1:5432" not in result
        assert "[REDACTED]" in result

    def test_get_generic_message_by_instance(self):
        """인스턴스 체크로 일반 메시지 결정"""
        from shared.api.error_sanitizer import _get_generic_message

        # ValueError instance
        exc = ValueError("test")
        result = _get_generic_message(exc)
        assert result == "Invalid input value"

        # OSError instance (inherits from ConnectionError check)
        exc = OSError("test")
        result = _get_generic_message(exc)
        assert result in ["Connection failed", "System error"]


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_sanitization_failure_fallback(self):
        """Sanitization 실패 시 폴백"""
        from shared.api.error_sanitizer import sanitize_error_message

        # Create an exception subclass that raises during str()
        class BadStrException(Exception):
            def __str__(self):
                raise RuntimeError("str() failed")

        mock_exc = BadStrException()
        result = sanitize_error_message(mock_exc)
        assert result == "An error occurred while processing your request"

    def test_unicode_in_error_message(self):
        """유니코드 에러 메시지 처리"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("한글 에러 메시지")
        result = sanitize_error_message(exc)
        assert "한글 에러 메시지" in result

    def test_special_characters_in_message(self):
        """특수 문자 포함 메시지"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = RuntimeError("Error: <special> & \"quoted\" $values")
        result = sanitize_error_message(exc)
        # Should preserve message structure while sanitizing
        assert isinstance(result, str)

    def test_nested_exception_type(self):
        """중첩된 예외 타입 이름"""
        from shared.api.error_sanitizer import _get_base_exception_type

        class OuterException(Exception):
            class InnerException(Exception):
                pass

        exc = OuterException.InnerException("test")
        result = _get_base_exception_type(exc)
        assert result == "InnerException"


class TestSensitivePatternRemoval:
    """민감 정보 패턴 제거 상세 테스트"""

    def test_remove_traceback_info(self):
        """트레이스백 정보 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = RuntimeError('File "/app/services/api/routes.py", line 123, in function')
        result = sanitize_error_message(exc)
        assert "/app/services/api/routes.py" not in result
        assert "line 123" not in result

    def test_remove_db_params(self):
        """DB 파라미터 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ConnectionError("Connection failed: host=localhost database=mydb")
        result = sanitize_error_message(exc)
        assert "host=localhost" not in result
        assert "database=mydb" not in result
        assert "[REDACTED]" in result

    def test_remove_function_signatures(self):
        """함수 시그니처 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = TypeError("my.module.submodule.function(arg1, arg2) failed")
        result = sanitize_error_message(exc)
        # Function signature should be replaced with [REDACTED]
        assert "my.module.submodule.function(arg1, arg2)" not in result
        assert "[REDACTED]" in result

    def test_preserve_safe_content(self):
        """안전한 콘텐츠는 보존"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("Invalid value: must be between 1 and 100")
        result = sanitize_error_message(exc)
        assert "Invalid value" in result
        assert "must be between 1 and 100" in result


@pytest.mark.asyncio
class TestGlobalExceptionHandler:
    """전역 예외 핸들러 통합 테스트"""

    async def test_handler_development_mode(self):
        """개발 모드: sanitized 상세 메시지"""
        pytest.importorskip("fastapi")

        # Create a simple test to verify handler behavior
        # Since we can't easily mock the whole FastAPI app, we test the logic
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("Invalid config in /etc/app/config.yaml")

        # Development mode: include_type=True, use_generic=False
        dev_result = sanitize_error_message(exc, include_type=True, use_generic=False)
        assert "ValueError:" in dev_result
        assert "/etc/app/config.yaml" not in dev_result
        assert "[REDACTED]" in dev_result

    async def test_handler_production_mode(self):
        """프로덕션 모드: 일반 메시지만"""
        pytest.importorskip("fastapi")
        from shared.api.error_sanitizer import sanitize_error_message

        exc = ValueError("Invalid config in /etc/app/config.yaml")

        # Production mode: use_generic=True
        prod_result = sanitize_error_message(exc, use_generic=True)
        assert prod_result == "Invalid input value"
        assert "/etc/app/config.yaml" not in prod_result
        assert "[REDACTED]" not in prod_result

    async def test_handler_sanitizes_all_exceptions(self):
        """모든 예외 타입 sanitize"""
        from shared.api.error_sanitizer import sanitize_error_message

        exceptions = [
            ValueError("test /path/file.py"),
            RuntimeError("test postgresql://localhost/db"),
            KeyError("test"),
            ConnectionError("test 192.168.1.1:8080"),
        ]

        for exc in exceptions:
            result = sanitize_error_message(exc)
            # No paths, no IPs, no DB strings
            assert "/path/file.py" not in result
            assert "postgresql://localhost/db" not in result
            assert "192.168.1.1:8080" not in result


class TestSecurityValidation:
    """보안 검증 테스트"""

    def test_no_information_leakage_in_generic_mode(self):
        """일반 모드에서 정보 유출 없음"""
        from shared.api.error_sanitizer import sanitize_error_message

        # Simulate real-world sensitive error
        exc = RuntimeError(
            "Failed to connect to postgresql://admin:secret@db.internal:5432/production "
            "at /app/services/trading/database.py line 456 in connect_db()"
        )

        result = sanitize_error_message(exc, use_generic=True)

        # Generic message should reveal nothing
        assert result == "Operation failed"
        assert "postgresql" not in result
        assert "admin" not in result
        assert "secret" not in result
        assert "db.internal" not in result
        assert "/app/services" not in result
        assert "database.py" not in result
        assert "456" not in result
        assert "connect_db" not in result

    def test_sanitized_mode_removes_sensitive_data(self):
        """Sanitized 모드도 민감 정보 제거"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = RuntimeError(
            "Database error: SELECT * FROM users WHERE password='secret123' "
            "at /home/user/app/db.py"
        )

        result = sanitize_error_message(exc, include_type=True, use_generic=False)

        # Should sanitize but keep structure
        assert "RuntimeError:" in result
        assert "password='secret123'" not in result
        assert "/home/user/app/db.py" not in result
        assert "[REDACTED]" in result

    def test_no_stack_trace_leakage(self):
        """스택 트레이스 정보 유출 없음"""
        from shared.api.error_sanitizer import sanitize_error_message

        exc = RuntimeError(
            'Traceback (most recent call last):\n'
            '  File "/app/main.py", line 123, in run\n'
            '  File "/app/services/api.py", line 456, in process\n'
            'RuntimeError: Operation failed'
        )

        result = sanitize_error_message(exc)

        # No file paths should remain
        assert "/app/main.py" not in result
        assert "/app/services/api.py" not in result
        assert "line 123" not in result
        assert "line 456" not in result
