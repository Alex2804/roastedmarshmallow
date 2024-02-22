from __future__ import annotations

import typing
from typing import Any, Mapping
from contextlib import contextmanager


class CompileContextStacks:
    _stacks = {}
    _scope_counter = 0

    @property
    def scope_counter(self):
        return self._scope_counter

    def __getattr__(self, name):
        if name in self._stacks:
            return self._stacks[name][-1]
        else:
            raise AttributeError(f'No stack with name {name}!')

    def __contains__(self, key):
        return key in self._stacks

    def _push(self, name: str, value: Any):
        if name not in self._stacks:
            self._stacks[name] = []
        self._stacks[name].append(value)

    def push(self, mapping: Mapping = None, **kwargs):
        for name, value in dict(mapping or {}, **kwargs).items():
            self._push(name, value)

    def _pop(self, name: str) -> Any:
        if name not in self._stacks:
            raise KeyError(f'No stack with name {name}!')
        value = self._stacks[name].pop()
        if len(self._stacks[name]) == 0:
            self._stacks.pop(name)
        return value

    def pop(self, *args) -> tuple[Any] | Any:
        if len(args) == 1:
            return self._pop(args[0])
        else:
            return tuple([self._pop(name) for name in args])

    def retrieve(self, name: str, default=None) -> list[Any]:
        if name not in self._stacks:
            return default
        return self._stacks[name]

    def get(self, name: str, default=None) -> Any:
        if name not in self._stacks:
            return default
        return self._stacks[name][-1]

    @contextmanager
    def scope(self, mapping: Mapping[str, Any] = None, **kwargs):
        self.push(mapping, **kwargs)
        self._scope_counter += 1
        yield
        self._scope_counter -= 1
        self.pop(*set((mapping or {}).keys()).union(kwargs.keys()))


class CompileContextData(dict):

    def __getattr__(self, item):
        return self[item]

    def __setattr__(self, key, value):
        self[key] = value


class CompileFlags:
    validate: bool = True

    always_inline_bool: bool = False

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f'Unknown compile flag: {key} = {value}')
            elif not isinstance(getattr(self, key), type(value)):
                raise TypeError(f'Invalid type for compile flag {key}: {type(value)} != {type(getattr(self, key))}')
            setattr(self, key, value)


class CompileContext:
    _data = CompileContextData()
    _stacks = CompileContextStacks()

    def __init__(self, flags: CompileFlags):
        self.flags = flags

    def push(self):
        pass

    def pop(self):
        pass

    @property
    def data(self) -> CompileContextData:
        return self._data

    @property
    def stacks(self) -> CompileContextStacks:
        return self._stacks


class EncodedReturn:
    def __init__(self, code: str,
                 definitions: list[str] = None,
                 locals_: dict[str, tuple[typing.Any, str]] = None,
                 pre_deserialize_routines: dict[str, tuple[typing.Callable, str]] = None,
                 post_deserialize_routines: dict[str, tuple[typing.Callable, str]] = None,
                 encoded_returns: list[EncodedReturn] = None,
                 recurse: set[typing.Any] = None):
        self.code = code.strip('\n')
        self.definitions = definitions or []
        self.locals = locals_ or {}
        self.pre_deserialize_routines = pre_deserialize_routines or {}
        self.post_deserialize_routines = post_deserialize_routines or {}
        self.recurse = recurse or set()

        if encoded_returns:
            for encoded_return in encoded_returns:
                self.definitions = encoded_return.definitions + self.definitions
                self.locals.update(encoded_return.locals)
                self.pre_deserialize_routines.update(encoded_return.pre_deserialize_routines)
                self.post_deserialize_routines.update(encoded_return.post_deserialize_routines)
                self.recurse.update(encoded_return.recurse)
