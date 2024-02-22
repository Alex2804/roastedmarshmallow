import typing
from datetime import datetime

from marshmallow import Schema, types
from marshmallow.decorators import PRE_LOAD, POST_LOAD, PRE_DUMP, POST_DUMP

from .compiler.encoders.encoder import DeserializeArgs, SerializeArgs
from .compiler.encoders.visitor import visitor
from .compiler.utils.compile_context import CompileContext, CompileFlags, EncodedReturn
from .compiler.utils.template import Template


_deserialize_template = '''
from datetime import datetime
from zipfile import ZipFile
import json

$profile_setup

with ZipFile("$experiment_filename", "r", allowZip64=True) as file:
    data = json.loads(file.read("experiment.json").decode("utf-8"))

$imports

from $schema_module import $schema_class
from marshmallow import RAISE

$schema = $schema_class()
$partial = False
$unknown = RAISE

$locals

$definitions

$pre_deserialize_routines

start = datetime.now()
$profile_begin
$deserialization
$profile_end
print(f"elapsed time: {(datetime.now() - start).total_seconds()}")

$post_deserialize_routines
'''.strip()


_serialize_template = '''
from datetime import datetime
from zipfile import ZipFile
import json

$profile_setup

with ZipFile("$experiment_filename", "r", allowZip64=True) as file:
    data = json.loads(file.read("experiment.json").decode("utf-8"))

$imports

from $schema_module import $schema_class
$schema = $schema_class()

from marshmallow.utils import RAISE
$obj = $schema.load(data, partial=False, unknown=RAISE)

$locals

$definitions

$pre_serialize_routines

start = datetime.now()
$profile_begin
$serialization
$profile_end
print(f"elapsed time: {(datetime.now() - start).total_seconds()}")

$post_serialize_routines
'''.strip()


def _order_local_dependencies(locals_: dict[str, tuple[typing.Any, str]]) -> list[tuple[str, str]]:
    dependencies = {k: (v, set()) for k, v in locals_.items()}
    for key, _ in dependencies.items():
        for k, ((_, s), _) in dependencies.items():
            if key in s:
                dependencies[k][1].add(key)

    all_dependencies = {}
    for key, (_, deps) in dependencies.items():
        stack = list(deps)
        seen = set()
        while len(stack) > 0:
            dep = stack.pop()
            seen.add(dep)
            if key in dependencies[dep][1]:
                raise ValueError(f'circular dependency between {key} and {dep}')
            stack += [d for d in dependencies[dep][1] if d not in stack and d not in seen]
        all_dependencies[key] = seen

    ordered_dependencies = []
    stack = list(all_dependencies.keys())
    while len(stack) > 0:
        key = stack.pop()
        if key in ordered_dependencies:
            continue
        deps = all_dependencies[key] - set(ordered_dependencies)
        if len(deps) == 0:
            ordered_dependencies.append(key)
        else:
            stack += [key] + list(deps)

    return [(key, locals_[key][1]) for key in ordered_dependencies]



class CompiledSchema(Schema):
    _compiled_deserialize = None
    _compiled_deserialize_locals: dict[str, typing.Any] = {}

    _compiled_serialize = None
    _compiled_serialize_locals: dict[str, typing.Any] = {}

    _routines: dict[str, [typing.Callable]] = {}

    def _encode_deserialize(self, flags: CompileFlags, input_schema: str, input_partial: str, input_unknown: str) -> EncodedReturn:
        context = CompileContext(flags=flags)
        with context.stacks.scope(DeserializeArgs(object=input_schema,
                                                  result='result',
                                                  value='data',
                                                  partial=input_partial,
                                                  unknown=input_unknown)):
            return visitor.deserialize(self, context)

    def _encode_serialize(self, flags: CompileFlags, input_schema: str, input_obj: str) -> EncodedReturn:
        context = CompileContext(flags)
        with context.stacks.scope(SerializeArgs(object=input_schema,
                                                result='result',
                                                obj=input_obj)):
            return visitor.serialize(self, context)

    def compile(self, flags: CompileFlags):
        encoded_deserialize = self._encode_deserialize(flags, 'schema', 'partial', 'unknown')
        code = '\n\n'.join(encoded_deserialize.definitions) + '\n\n' + encoded_deserialize.code
        with open('raw_test_load.py', 'w') as f:
            f.write(code)
        self._compiled_deserialize_locals = {k: v[0] for k, v in encoded_deserialize.locals.items() if v[0] is not None}
        self._compiled_deserialize = compile(code, '', 'exec')
        self._routines[PRE_LOAD] = [v for v, _ in encoded_deserialize.pre_deserialize_routines.values()]
        self._routines[POST_LOAD] = [v for v, _ in encoded_deserialize.post_deserialize_routines.values()]

        encoded_serialize = self._encode_serialize(flags, 'schema', 'obj')
        code = '\n\n'.join(encoded_serialize.definitions) + '\n\n' + encoded_serialize.code
        with open('raw_test_dump.py', 'w') as f:
            f.write(code)
        self._compiled_serialize = compile(code, '', 'exec')
        self._compiled_serialize_locals = {k: v[0] for k, v in encoded_serialize.locals.items() if v[0] is not None}
        self._routines[PRE_DUMP] = [v for v, _ in encoded_serialize.pre_deserialize_routines.values()]
        self._routines[POST_DUMP] = [v for v, _ in encoded_serialize.post_deserialize_routines.values()]

    def compile_to_string(self, flags: CompileFlags, experiment_filename: str, profile_filename: str = None) -> tuple[str, str]:
        profile = profile_filename is not None
        schema, obj, partial, unknown = 'schema', 'obj', 'partial', 'unknown'
        encoded_deserialize = self._encode_deserialize(flags, schema, partial, unknown)
        imports = {k: (v, s) for k, (v, s) in encoded_deserialize.locals.items() if v is None or 'import ' in s}
        locals_ = {k: encoded_deserialize.locals[k] for k in encoded_deserialize.locals.keys() - imports.keys()}

        deserialize_template = Template(_deserialize_template)
        deserialize_template.substitute(
            schema=schema,
            partial=partial,
            unknown=unknown,
            schema_module=self.__class__.__module__,
            schema_class=self.__class__.__name__,
            experiment_filename=experiment_filename,
            imports='\n'.join([s for _, s in imports.values()]),
            locals='\n'.join(f'{k} = {v}' for k, v in _order_local_dependencies(locals_)),
            definitions='\n\n'.join(encoded_deserialize.definitions),
            pre_deserialize_routines='\n'.join(s for _, s in encoded_deserialize.pre_deserialize_routines.values()),
            deserialization=encoded_deserialize.code,
            post_deserialize_routines='\n'.join(s for _, s in encoded_deserialize.post_deserialize_routines.values()),
            profile_setup='import cProfile as profile\npr = profile.Profile()\npr.disable()\n' if profile else '',
            profile_begin='pr.enable()' if profile else '',
            profile_end=(f'pr.disable()\n'
                         f'pr.dump_stats("{profile_filename}")\n'
                         f'print(f"dumped stats to \'{profile_filename}\'")') if profile else '',
        )

        encoded_serialize = self._encode_serialize(flags, schema, obj)
        imports = {k: (v, s) for k, (v, s) in encoded_serialize.locals.items() if v is None or 'import ' in s}
        locals_ = {k: encoded_serialize.locals[k] for k in encoded_serialize.locals.keys() - imports.keys()}

        serialize_template = Template(_serialize_template)
        serialize_template.substitute(
            schema=schema,
            obj=obj,
            schema_module=self.__class__.__module__,
            schema_class=self.__class__.__name__,
            experiment_filename=experiment_filename,
            imports='\n'.join([s for _, s in imports.values()]),
            locals='\n'.join(f'{k} = {v}' for k, v in _order_local_dependencies(locals_)),
            definitions='\n\n'.join(encoded_serialize.definitions),
            pre_serialize_routines='\n'.join(s for _, s in encoded_serialize.pre_deserialize_routines.values()),
            serialization=encoded_serialize.code,
            post_serialize_routines='\n'.join(s for _, s in encoded_serialize.post_deserialize_routines.values()),
            profile_setup='import cProfile as profile\npr = profile.Profile()\npr.disable()\n' if profile else '',
            profile_begin='pr.enable()' if profile else '',
            profile_end=(f'pr.disable()\n'
                         f'pr.dump_stats("{profile_filename}")\n'
                         f'print(f"dumped stats to \'{profile_filename}\'")') if profile else '',
        )

        return str(deserialize_template), str(serialize_template)

    def load_compiled(
            self,
            data: (typing.Mapping[str, typing.Any] | typing.Iterable[typing.Mapping[str, typing.Any]]),
            *,
            partial: bool | types.StrSequenceOrSet | None = None,
            unknown: str | None = None
    ):
        if self._compiled_deserialize is None:
            raise RuntimeError('Schema not compiled')
        local = {'schema': self, 'data': data, 'partial': partial, 'unknown': unknown}
        local.update(self._compiled_deserialize_locals)
        for routine in self._routines[PRE_LOAD]:
            routine()
        start = datetime.now()
        exec(self._compiled_deserialize, local, local)
        compiled_load_time = (datetime.now() - start).total_seconds()
        for routine in self._routines[POST_LOAD]:
            routine()
        return local['result']

    def loads_compiled(
            self,
            json_data: str,
            *,
            partial: bool | types.StrSequenceOrSet | None = None,
            unknown: str | None = None,
            **kwargs
    ):
        data = self.opts.render_module.loads(json_data, **kwargs)
        return self.load_compiled(data, partial=partial, unknown=unknown)

    def dump_compiled(self, obj: typing.Any):
        if self._compiled_serialize is None:
            raise RuntimeError('Schema not compiled')
        local = {'schema': self, 'obj': obj}
        local.update(self._compiled_serialize_locals)
        for routine in self._routines[PRE_DUMP]:
            routine()
        exec(self._compiled_serialize, local, local)
        for routine in self._routines[POST_DUMP]:
            routine()
        return local['result']

    def dumps_compiled(self, obj: typing.Any):
        serialized = self.dump_compiled(obj)
        return self.opts.render_module.dumps(serialized)
