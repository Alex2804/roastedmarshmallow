import typing

from marshmallow import ValidationError, INCLUDE, EXCLUDE, RAISE
from marshmallow.decorators import PRE_LOAD, POST_LOAD, PRE_DUMP, POST_DUMP, VALIDATES, VALIDATES_SCHEMA
from marshmallow.error_store import ErrorStore
from marshmallow.schema import Schema
from marshmallow.utils import is_collection, set_value, missing

from .visitor import Encoder, DeserializeArgs, SerializeArgs, CompileContext, EncodedReturn, visitor
from ..utils.template import Template

_recursive_template = '''
def $function_name($function_arguments):
    $function_body
'''

_deserialize_template = '''
$data = $input_data
$partial = $input_partial

#$partial_is_collection = is_collection($partial)

$original_data = $data

# pre processors
$pre_processing_template

$result = $dict_class()

# validation
$validation_template

# deserialization
$field_templates

if unknown != EXCLUDE:
    __unknown_fields = set($data) - $fields
    if unknown == INCLUDE:
        for __key in __unknown_fields:
            $result[__key] = $data[__key]
    elif __unknown_fields and unknown == RAISE:
        raise ValidationError(f'{$schema.error_messages["unknown"]}: {__unknown_fields}', str(__unknown_fields))

$data = $original_data

# field level validation
$field_level_validation_template

# schema level validation
$schema_level_validation_template

# post processors
$post_processing_template

$set_result
'''.strip()

_deserialize_pre_processing_template = '''
$data = $schema._invoke_load_processors(PRE_LOAD, $data, many=$many, original_data=$data, partial=$partial)
'''.strip()

_deserialize_validation_template = '''
if not isinstance($data, Mapping):
    raise ValidationError($schema.error_messages["type"])  # TODO: better error message
'''.strip()

_deserialize_field_template = '''
# deserialize $field_comment
$deserialize_field
'''.strip()

_deserialize_field_level_validation_template = '''
self._invoke_field_validators(error_store=__error_store, data=$result, many=$many)
if __error_store.errors:
    raise ValidationError(__error_store.errors, data=$original_data, valid_data=$result)
'''.strip()

_deserialize_schema_level_validation_template = '''
$schema._invoke_schema_validators(
    error_store=__error_store,
    pass_many=True,
    data=$result,
    original_data=$original_data,
    many=$many,
    partial=$partial,
    field_errors=False,
)
$schema._invoke_schema_validators(
    error_store=__error_store,
    pass_many=False,
    data=$result,
    original_data=$original_data,
    many=$many,
    partial=$partial,
    field_errors=False,
)
if __error_store.errors:
    raise ValidationError(__error_store.errors, data=$data, valid_data=$result)
'''.strip()

_deserialize_post_processing_template = '''
$result = $schema._invoke_load_processors(POST_LOAD, $result, many=$many, original_data=$original_data, partial=$partial)
'''.strip()


_serialize_template = '''
$obj = $input_obj

$original_obj = $obj
$pre_processing_template

$result = $dict_class()

$field_templates

$obj = $original_obj
$post_processing_template

$set_result
'''.strip()

_serialize_pre_processing_template = '''
$obj = $schema._invoke_dump_processors(PRE_DUMP, $obj, many=$many, original_data=$obj)
'''.strip()

_serialize_post_processing_template = '''
$result = $schema._invoke_dump_processors(POST_DUMP, $result, many=$many, original_data=$obj)
'''.strip()

_serialize_field_template = '''
# serialize $field_comment
$serialize_field
'''.strip()


class SchemaEncoder(Encoder[Schema]):
    @staticmethod
    def _schema_key(schema: Schema) -> str:
        return f'{schema.__class__.__name__}_{abs(hash(schema))}'

    @staticmethod
    def _dict_class_key(schema: Schema) -> str:
        return f'{schema.dict_class.__name__}_{abs(hash(schema.dict_class))}'

    @staticmethod
    def _recursive_function_name(schema: Schema) -> str:
        return f'evaluate_{SchemaEncoder._schema_key(schema)}'

    @staticmethod
    def _deserialize_set_result(result: str, obj_key: str, value: str) -> str:
        if '.' in obj_key:
            return f'set_value({result}, {obj_key}, {value})'
        return f'{result}["{obj_key}"] = {value}'

    def _encode_deserialize(self, schema: Schema, context: CompileContext) -> EncodedReturn:
        first_schema = len(context.stacks.retrieve('schema', [])) == 0
        recursive = next((
            s for s in context.stacks.retrieve('schema', [])
            if schema.__class__ == s.__class__ and schema.load_fields.keys() == s.load_fields.keys()
        ), None)
        if recursive:
            function = self._recursive_function_name(recursive)
            arguments = f'{context.stacks.value}, {context.stacks.partial}'
            return EncodedReturn(context.stacks.set_result(f'{function}({arguments})'), recurse={recursive})

        schema_locals = {}
        result = f'result_{context.stacks.scope_counter}'
        with context.stacks.scope(DeserializeArgs(object=self._schema_key(schema),
                                                  data=f'data_{context.stacks.scope_counter}',
                                                  partial=f'partial_{context.stacks.scope_counter}',
                                                  value=f'value_{context.stacks.scope_counter}',
                                                  result=result),
                                  schema=schema):
            field_code = ''
            deserialize_templates = []
            data_keys = set()
            encoded_fields = []
            for attr_name, field in schema.load_fields.items():
                data_key = visitor.name(field, attr_name)
                obj_key = field.attribute or attr_name

                data_keys.add(data_key)

                with context.stacks.scope(DeserializeArgs(
                        object=f'{context.stacks.object}.load_fields["{attr_name}"]',
                        value=f'{context.stacks.data}["{data_key}"]',
                        result=f'{context.stacks.result}["{obj_key}"]',
                        set_result=lambda v: self._deserialize_set_result(result, obj_key, v),
                        data_key=data_key
                )):
                    encoded_field = visitor.deserialize(field, context)
                    encoded_fields.append(encoded_field)

                if schema in encoded_field.recurse:
                    recursive = True

                comment = f'''{'.'.join([n for n in context.stacks.retrieve("data_key", []) if n] + [data_key])}'''

                field_template = Template(_deserialize_field_template)
                field_template.safe_substitute(field_comment=comment,
                                               data=context.stacks.data,
                                               data_key=data_key,
                                               obj_key=obj_key,
                                               deserialize_field=f'$deserialize_field_{len(deserialize_templates)}')

                deserialize_templates.append(encoded_field.code.strip())

                field_code += '\n\n' + str(field_template)

            template = Template(('__error_store = ErrorStore()\n' if first_schema else '') + _deserialize_template)
            template.safe_substitute(
                pre_processing_template=(_deserialize_pre_processing_template if schema._has_processors(PRE_LOAD) else ''),
                validation_template=_deserialize_validation_template if context.flags.validate else '',
                field_templates=field_code,
                field_level_validation_template=(_deserialize_field_level_validation_template if schema._hooks[VALIDATES] else ''),
                schema_level_validation_template=(_deserialize_schema_level_validation_template if schema._has_processors(VALIDATES_SCHEMA) else ''),
                post_processing_template=(_deserialize_post_processing_template if schema._has_processors(POST_LOAD) else '')
            )
            template.safe_substitute(schema=context.stacks.object,
                                     result=context.stacks.result,
                                     data=context.stacks.data,
                                     partial=context.stacks.partial,
                                     partial_is_collection=f'{context.stacks.partial}_is_collection',
                                     original_data=f'original_data_{context.stacks.scope_counter}',
                                     fields=str(data_keys),
                                     many='False')

            schema_locals[context.stacks.object] = (schema, context.stacks.retrieve('object')[-2])

        recursive_function = self._recursive_function_name(schema)
        if recursive:
            context.stacks.push(value='input_data', partial='input_partial')
            function_body = template.template + f'\nreturn $result'
            template = Template(_recursive_template)
            template.safe_substitute(function_name=recursive_function,
                                     function_arguments=f'{context.stacks.value}, {context.stacks.partial}')
            template.substitute_indented(function_body=function_body)

        dict_class_key = self._dict_class_key(schema)
        schema_locals[dict_class_key] = (schema.dict_class, f'from {schema.dict_class.__module__} import {schema.dict_class.__name__} as {dict_class_key}')
        if first_schema:
            schema_locals['ErrorStore'] = (ErrorStore, 'from marshmallow.error_store import ErrorStore')
        template.safe_substitute(dict_class=dict_class_key,
                                 input_data=context.stacks.value,
                                 input_partial=context.stacks.partial)

        template.substitute_indented({f'deserialize_field_{i}': t for i, t in enumerate(deserialize_templates)},
                                     set_result=self.set_result(context, result))

        schema_locals.update({
            'Mapping': (typing.Mapping, 'from typing import Mapping'),
            'ValidationError': (ValidationError, 'from marshmallow.exceptions import ValidationError'),
            'PRE_LOAD': (PRE_LOAD, 'from marshmallow.decorators import PRE_LOAD'),
            'VALIDATES': (VALIDATES, 'from marshmallow.decorators import VALIDATES'),
            'VALIDATES_SCHEMA': (VALIDATES_SCHEMA, 'from marshmallow.decorators import VALIDATES_SCHEMA'),
            'POST_LOAD': (POST_LOAD, 'from marshmallow.decorators import POST_LOAD'),
            'missing': (missing, 'from marshmallow.utils import missing'),
            'set_value': (set_value, 'from marshmallow.utils import set_value'),
            'is_collection': (is_collection, 'from marshmallow.utils import is_collection'),
            'RAISE': (RAISE, 'from marshmallow.utils import RAISE'),
            'EXCLUDE': (EXCLUDE, 'from marshmallow.utils import EXCLUDE'),
            'INCLUDE': (INCLUDE, 'from marshmallow.utils import INCLUDE'),
        })

        if recursive:
            context.stacks.pop('value', 'partial')
            return EncodedReturn(
                code=self.set_result(context, f'{recursive_function}({context.stacks.value}, {context.stacks.partial})'),
                definitions=[str(template)],
                locals_=schema_locals,
                encoded_returns=encoded_fields
            )
        else:
            return EncodedReturn(code=str(template), locals_=schema_locals, encoded_returns=encoded_fields)

    @staticmethod
    def _serialize_set_result(result: str, data_key: str, value: str) -> str:
        return f'{result}["{data_key}"] = {value}'

    def _encode_serialize(self, schema: Schema, context: CompileContext) -> EncodedReturn:
        recursive = next((
            s for s in context.stacks.retrieve('schema', [])
            if schema.__class__ == s.__class__ and schema.dump_fields.keys() == s.dump_fields.keys()
        ), None)
        if recursive:
            function = self._recursive_function_name(recursive)
            return EncodedReturn(code=self.set_result(context, f'{function}({context.stacks.value})'),
                                 recurse={recursive})

        schema_locals = {}
        result = f'result_{context.stacks.scope_counter}'
        with context.stacks.scope(SerializeArgs(object=f'schema_{id(schema)}',
                                                obj=f'obj_{context.stacks.scope_counter}',
                                                value=f'value_{context.stacks.scope_counter}',
                                                result=result),
                                  schema=schema):
            field_code = ''
            serialize_templates = []
            encoded_fields = []
            for attr_name, field in schema.dump_fields.items():
                obj_key = field.attribute or attr_name  # marshmallow uses only attr_name as obj key for dumping, but the preceding code for loading
                data_key = visitor.name(field, attr_name)

                tmp_object = f'{context.stacks.object}.dump_fields["{attr_name}"]'
                with context.stacks.scope(SerializeArgs(
                        object=tmp_object,
                        value=f'{tmp_object}.get_value({context.stacks.obj}, "{obj_key}")',
                        result=f'{context.stacks.result}["{data_key}"]',
                        set_result=lambda v: self._deserialize_set_result(result, data_key, v),
                        obj_key=obj_key
                )):
                    encoded_field = visitor.serialize(field, context)
                    encoded_fields.append(encoded_field)

                if schema in encoded_field.recurse:
                    recursive = True

                comment = f'''{'.'.join([n for n in context.stacks.retrieve("obj_key", []) if n] + [obj_key])}'''

                field_template = Template(_serialize_field_template)
                field_template.safe_substitute(field_comment=comment,
                                               obj=context.stacks.obj,
                                               obj_key=obj_key,
                                               data_key=data_key,
                                               serialize_field=f'$serialize_field_{len(serialize_templates)}')
                serialize_templates.append(encoded_field.code.strip())

                field_code += '\n\n' + str(field_template)

            template = Template(_serialize_template)
            template.safe_substitute(
                pre_processing_template=(_serialize_pre_processing_template if schema._has_processors(PRE_DUMP) else ''),
                field_templates=field_code,
                post_processing_template=(_serialize_post_processing_template if schema._has_processors(POST_DUMP) else '')
            )
            template.safe_substitute(schema=context.stacks.object,
                                     result=context.stacks.result,
                                     obj=context.stacks.obj,
                                     original_obj=f'original_obj_{context.stacks.scope_counter}',
                                     many='False')

            schema_locals[context.stacks.object] = (schema, context.stacks.retrieve('object')[-2])

        recursive_function = self._recursive_function_name(schema)
        if recursive:
            context.stacks.push(obj='input_obj')
            function_body = template.template + f'\nreturn $result'
            template = Template(_recursive_template)
            template.safe_substitute(function_name=recursive_function,
                                     function_arguments=context.stacks.obj)
            template.substitute_indented(function_body=function_body)

        dict_class_key = self._dict_class_key(schema)
        schema_locals[dict_class_key] = (schema.dict_class, f'from {schema.dict_class.__module__} import {schema.dict_class.__name__} as {dict_class_key}')
        template.safe_substitute(dict_class=dict_class_key,
                                 input_obj=context.stacks.obj)
        template.substitute_indented({f'serialize_field_{i}': t for i, t in enumerate(serialize_templates)},
                                     set_result=self.set_result(context, result))

        schema_locals.update({
            'Mapping': (typing.Mapping, 'from typing import Mapping'),
            'ValidationError': (ValidationError, 'from marshmallow.exceptions import ValidationError'),
            'PRE_DUMP': (PRE_DUMP, 'from marshmallow.decorators import PRE_DUMP'),
            'POST_DUMP': (POST_DUMP, 'from marshmallow.decorators import POST_DUMP'),
            'missing': (missing, 'from marshmallow.utils import missing'),
        })

        if recursive:
            context.stacks.pop('obj')
            return EncodedReturn(code=self.set_result(context, f'{recursive_function}({context.stacks.obj})'),
                                 definitions=[str(template)],
                                 locals_=schema_locals,
                                 encoded_returns=encoded_fields)
        else:
            return EncodedReturn(code=str(template), locals_=schema_locals, encoded_returns=encoded_fields)


visitor.register_encoder(SchemaEncoder)
