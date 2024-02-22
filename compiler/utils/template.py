from __future__ import annotations

from typing import Mapping

import re

import string


class Template(string.Template):
    _compiled_indented_regexes = {}
    _compiled_regexes = {}

    def __str__(self):
        return self.template

    def substitute(self, mapping: Mapping[str, object] = None, **kwargs) -> str:
        self.template = super().substitute(mapping or {}, **kwargs)
        return self.template

    def safe_substitute(self, mapping: Mapping[str, object] = None, **kwargs) -> str:
        self.template = super().safe_substitute(mapping or {}, **kwargs)
        return self.template

    def substitute_regex(self, regex: str, replacement: str) -> str:
        if regex not in self._compiled_regexes:
            self._compiled_regexes[regex] = re.compile(regex)
        self.template = re.sub(self._compiled_regexes[regex], replacement, self.template)
        return self.template

    def substitute_indented(self, mapping: Mapping[str, str] = None, **kwargs) -> str:
        substitutions = {}
        for key, replacement in dict(mapping or {}, **kwargs).items():
            if key not in self._compiled_indented_regexes:
                self._compiled_indented_regexes[key] = re.compile(fr'(?:(?<=^)|(?<=\n))(([ \t#]*)\$+{key}([ \t]*(?:#.*)?))(?=\n|$)')
            for i, (to_replace, pre, post) in enumerate(set(re.findall(self._compiled_indented_regexes[key], self.template))):
                new_key = f'{key}_{i}'
                tmp_post = post or '\n'
                tmp_new_line = '\n' if self.template[-1] != '\n' else ''
                self.template += '\n'
                self.template = self.template.replace(f'{to_replace}{tmp_post}', f'{pre}${new_key}{tmp_post}')
                if tmp_new_line:
                    self.template = self.template[:-1]
                rep = replacement.replace('\n', '\n' + pre) if pre else replacement
                if post:
                    rep = rep.replace('\n', f'{post}\n', 1) if '\n' in rep else f'{rep}{post}'
                substitutions[new_key] = rep
        return self.safe_substitute(substitutions)
