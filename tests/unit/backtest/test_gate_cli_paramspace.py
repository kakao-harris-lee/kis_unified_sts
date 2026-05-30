import importlib.util
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]  # tests/unit/backtest/ -> repo root
_spec = importlib.util.spec_from_file_location(
    "gfs", _REPO_ROOT / "scripts" / "gate_futures_strategy.py"
)
gfs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gfs)


def test_gate_script_imports_without_optuna(monkeypatch):
    """Regression: the script must import without optuna installed.

    CI runners do not install the heavy `optuna` dep, yet these unit tests
    exec_module the whole script. optuna is only needed at study-creation time
    inside main(), so module import + the pure helpers must not require it.
    Simulate optuna being absent and exec a fresh copy of the module.
    """
    monkeypatch.setitem(sys.modules, "optuna", None)
    monkeypatch.setitem(sys.modules, "optuna.samplers", None)

    spec = importlib.util.spec_from_file_location(
        "gfs_no_optuna", _REPO_ROOT / "scripts" / "gate_futures_strategy.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # must NOT raise ModuleNotFoundError

    out = mod.apply_params(
        {"strategy": {"entry": {"params": {"a": 1}}, "exit": {"params": {}}}},
        {"entry.params.a": 9},
    )
    assert out["strategy"]["entry"]["params"]["a"] == 9


def test_apply_dotted_params_deepcopies_and_sets_nested():
    base = {
        "strategy": {
            "entry": {"params": {"a": 1}},
            "exit": {"params": {}},
        }
    }
    out = gfs.apply_params(
        base,
        {"entry.params.a": 9, "exit.params.b": 2.5},
    )
    assert out["strategy"]["entry"]["params"]["a"] == 9
    assert out["strategy"]["exit"]["params"]["b"] == 2.5
    assert base["strategy"]["entry"]["params"]["a"] == 1  # deep-copied


class _Trial:
    def __init__(self):
        self.calls = []

    def suggest_float(self, name, low, high):
        self.calls.append((name, "f", low, high))
        return (low + high) / 2

    def suggest_int(self, name, low, high):
        self.calls.append((name, "i", low, high))
        return int((low + high) // 2)


def test_suggest_from_space():
    space = {
        "entry.params.oversold_threshold": {
            "type": "float",
            "low": -95,
            "high": -60,
        },
        "entry.params.williams_r_period": {"type": "int", "low": 7, "high": 28},
    }
    t = _Trial()
    params = gfs.suggest_params(t, space)
    assert params["entry.params.oversold_threshold"] == -77.5
    assert params["entry.params.williams_r_period"] == 17
