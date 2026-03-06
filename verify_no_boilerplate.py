#!/usr/bin/env python3
"""
Verify that no config boilerplate remains outside of ServiceConfigBase.

This script checks that all configs with from_yaml/from_env either:
1. Are in base.py or mixins.py (the base classes), OR
2. Extend ServiceConfigBase (allowed to override for custom logic)

Configs that have from_yaml/from_env but DON'T extend ServiceConfigBase
are considered to have boilerplate and should be flagged.
"""
import os
import re
from pathlib import Path

# Files that are allowed to define from_yaml/from_env (base classes)
ALLOWED_BASE_FILES = {
    'shared/config/base.py',
    'shared/config/mixins.py',
}

def check_extends_service_config_base(file_path: str) -> bool:
    """Check if a file's config class extends ServiceConfigBase."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            # Check for ServiceConfigBase in class definition or imports
            if 'ServiceConfigBase' in content:
                # More precise check: look for class definition that extends it
                if re.search(r'class\s+\w+\([^)]*ServiceConfigBase[^)]*\):', content):
                    return True
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return False

def find_configs_with_methods():
    """Find all Python files with from_yaml or from_env methods."""
    configs_with_methods = []

    # Search in shared/ and services/
    for directory in ['./shared', './services']:
        if not os.path.exists(directory):
            continue

        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith('.py'):
                    continue

                file_path = os.path.join(root, file)
                relative_path = file_path.lstrip('./')

                # Skip base files
                if relative_path in ALLOWED_BASE_FILES:
                    continue

                # Check if file has from_yaml or from_env
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        if re.search(r'def from_yaml\s*\(|def from_env\s*\(', content):
                            configs_with_methods.append(relative_path)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    return configs_with_methods

def main():
    print("🔍 Checking for config boilerplate...\n")

    configs = find_configs_with_methods()

    if not configs:
        print("✅ No configs with from_yaml/from_env methods found outside base classes!")
        return 0

    print(f"Found {len(configs)} config file(s) with from_yaml/from_env methods:\n")

    boilerplate_configs = []
    migrated_configs = []

    for config_path in sorted(configs):
        extends_base = check_extends_service_config_base(config_path)

        if extends_base:
            migrated_configs.append(config_path)
            print(f"  ✅ {config_path} (extends ServiceConfigBase - custom override allowed)")
        else:
            boilerplate_configs.append(config_path)
            print(f"  ❌ {config_path} (has boilerplate - should extend ServiceConfigBase)")

    print(f"\n{'='*70}")
    print(f"Summary:")
    print(f"  Migrated configs (override allowed): {len(migrated_configs)}")
    print(f"  Configs with boilerplate: {len(boilerplate_configs)}")
    print(f"{'='*70}\n")

    if boilerplate_configs:
        print("❌ BOILERPLATE FOUND in the following files:")
        for config in boilerplate_configs:
            print(f"   - {config}")
        print("\nThese configs should be migrated to extend ServiceConfigBase.")
        print("See docs/config_patterns.md for migration guide.")
        return 1
    else:
        print("✅ SUCCESS: No boilerplate found!")
        print(f"   All {len(migrated_configs)} configs with from_yaml/from_env extend ServiceConfigBase.")
        print("   Custom overrides are allowed for complex logic (nested YAML, multi-prefix, etc.)")
        return 0

if __name__ == '__main__':
    exit(main())
