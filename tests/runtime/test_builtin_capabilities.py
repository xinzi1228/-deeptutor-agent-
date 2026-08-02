"""Builtin capability whitelist — only chat remains (标注星图 teaching product)."""

from __future__ import annotations


def test_only_chat_capability_registered() -> None:
    from deeptutor.runtime.bootstrap.builtin_capabilities import BUILTIN_CAPABILITY_CLASSES

    assert set(BUILTIN_CAPABILITY_CLASSES.keys()) == {"chat"}


def test_chat_capability_class_resolvable() -> None:
    from deeptutor.runtime.bootstrap.builtin_capabilities import BUILTIN_CAPABILITY_CLASSES

    cls = BUILTIN_CAPABILITY_CLASSES["chat"]
    module_path, _, attr = cls.partition(":")
    import importlib

    mod = importlib.import_module(module_path)
    assert hasattr(mod, attr)
