# Reference: compiled wheel import failure

## Observed pattern

An installed robot inspection application auto-imported action modules. The first failure was:

```text
ImportError: cannot import name ROBOT_FORCE_SENSOR_PATH
```

The failing action was a compiled Cython extension (`actions/forcesensor_calibration.cpython-312-x86_64-linux-gnu.so`). During exception handling, the TUI raised a second error:

```text
ModuleNotFoundError: No module named 'src.autolife_robot_inspection'
```

The deployed package was resolved from `site-packages`, had a local-wheel `direct_url.json`, and its wheel/version metadata did not line up cleanly with the environment's package listing. The compiled module and runtime SDK therefore required provenance/version comparison rather than a site-packages constant shim.

## Reusable probes

Run in the exact application environment:

```bash
python - <<'PY'
import importlib.util, importlib.metadata as md, sys
print(sys.executable)
for name in ["package", "package.plugins.failing_module"]:
    try:
        spec = importlib.util.find_spec(name)
        print(name, spec.origin if spec else None,
              list(spec.submodule_search_locations or []) if spec else None)
    except Exception as e:
        print(name, type(e).__name__, e)
try:
    d = md.distribution("distribution-name")
    print(d.version, d.locate_file(""))
except Exception as e:
    print(type(e).__name__, e)
PY

python -c 'import required_dependency; print(required_dependency.__file__)'
python -m pip show distribution-name required-dependency
```

For local wheels, inspect:

```bash
unzip -l /path/to/package.whl
cat site-packages/distribution_name-*.dist-info/direct_url.json
```

For a missing symbol, search source and installed artifacts first:

```bash
grep -R -n 'SYMBOL_NAME' /path/to/source /path/to/site-packages
strings /path/to/extension.so | grep 'SYMBOL_NAME'
```

## Interpretation

- The first exception identifies the initial dependency/API mismatch candidate.
- A traceback module name containing `src.` is evidence to inspect build layout and Cython module naming.
- A missing runtime dependency such as `rclpy` is an independent environment boundary; fix/verify it separately.
- Deprecation and fallback warnings are not fatal unless a later probe proves they prevent startup.

## Repair boundary

For tightly coupled compiled packages, rebuild and install a compatible set from one source/version/build context. Avoid modifying binary extensions or adding guessed compatibility constants in `site-packages`. Verify isolated imports, plugin discovery, and the original entry point in that order.
