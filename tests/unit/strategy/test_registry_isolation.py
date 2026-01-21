"""Test registry isolation."""
import pytest


def test_registry_clear_isolates_tests():
    """Test that clear() properly isolates test runs."""
    from shared.strategy.registry import EntryRegistry

    # Clear first
    EntryRegistry.clear()

    # Register a test component
    @EntryRegistry.register("test_strategy_isolation")
    class TestStrategy:
        pass

    assert "test_strategy_isolation" in EntryRegistry.list_all()

    # Clear again
    EntryRegistry.clear()

    # Should be empty (not still have the strategy)
    assert "test_strategy_isolation" not in EntryRegistry.list_all()


def test_entry_and_exit_registries_are_independent():
    """Test that Entry and Exit registries don't share state."""
    from shared.strategy.registry import EntryRegistry, ExitRegistry

    EntryRegistry.clear()
    ExitRegistry.clear()

    # Register in entry only
    @EntryRegistry.register("test_entry_only")
    class TestEntry:
        pass

    # Register in exit only
    @ExitRegistry.register("test_exit_only")
    class TestExit:
        pass

    # Verify isolation
    assert "test_entry_only" in EntryRegistry.list_all()
    assert "test_entry_only" not in ExitRegistry.list_all()

    assert "test_exit_only" in ExitRegistry.list_all()
    assert "test_exit_only" not in EntryRegistry.list_all()


def test_registry_subclasses_have_separate_components():
    """Test that each registry subclass maintains its own components dict."""
    from shared.strategy.registry import EntryRegistry, ExitRegistry, SizerRegistry

    # Clear all
    EntryRegistry.clear()
    ExitRegistry.clear()
    SizerRegistry.clear()

    # Register one component in each
    EntryRegistry.register_class("entry_test", object)
    ExitRegistry.register_class("exit_test", object)
    SizerRegistry.register_class("sizer_test", object)

    # Verify each only has its own
    assert EntryRegistry.list_all() == ["entry_test"]
    assert ExitRegistry.list_all() == ["exit_test"]
    assert SizerRegistry.list_all() == ["sizer_test"]


def test_clear_does_not_affect_other_registries():
    """Test that clearing one registry doesn't affect others."""
    from shared.strategy.registry import EntryRegistry, ExitRegistry

    EntryRegistry.clear()
    ExitRegistry.clear()

    EntryRegistry.register_class("entry_comp", object)
    ExitRegistry.register_class("exit_comp", object)

    # Clear only entry
    EntryRegistry.clear()

    # Entry should be empty
    assert EntryRegistry.list_all() == []

    # Exit should still have its component
    assert "exit_comp" in ExitRegistry.list_all()
