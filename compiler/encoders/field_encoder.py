import typing
from typing import TypeVar, Hashable
from abc import ABC

from marshmallow import missing
from marshmallow.fields import Field

from .encoder import Encoder, DeserializeArgs, SerializeArgs, CompileContext, EncodedReturn, _T
from .visitor import visitor

from string import Template
from ..utils.template import Template


_deserialize_template = '''
$value = $input_value
if $value is None:
    $handle_none
else:
    $encoded_deserialize
    $validate_result
'''.strip()

_deserialize_with_data_key_template = '''
if '$data_key' in $data:
    $deserialize
$handle_not_in_data_template
'''.strip()

_deserialize_handle_not_in_data_template = '''
else:
    $handle_not_in_data
'''.strip()

_deserialize_disallow_none_template = 'raise $field.make_error("null")'
_deserialize_required_template = 'raise $field.make_error("required")'
_deserialize_validate_result_template = '$field._validate($result)'


_serialize_check_attribute_template = '''
$value = $input_value
$load_default
if $value is not missing:
    $encoded_serialize
'''.strip()

_serialize_load_default_template = '''
if $value is missing:
    $value = $default
'''.strip()


_F = TypeVar('_F', bound=Field)


class FieldEncoder(Encoder[_F], ABC):
    @staticmethod
    def _default_key(default: typing.Any) -> str:
        default_id = abs(hash(default)) if isinstance(default, Hashable) else id(default)
        return f'default_{default.__class__.__name__}_{default_id}'

    def _encode_name(self, field: _F, attr_name: str) -> str:
        return field.data_key or attr_name

    def encode_deserialize(self, field: _F, context: CompileContext) -> EncodedReturn:
        has_data_key = context.stacks.get('data_key')
        has_default = field.load_default is not None and field.load_default != missing
        value = f'value_{context.stacks.scope_counter}'
        
        with context.stacks.scope(DeserializeArgs(value=value)):
            encoded_field = self._encode_deserialize(field, context)

        if has_data_key:
            template = Template(_deserialize_with_data_key_template)
            template.substitute_indented(deserialize=_deserialize_template)
        else:
            template = Template(_deserialize_template)

        template.substitute_indented(
            handle_none=self.set_result(context, 'None') if field.allow_none else _deserialize_disallow_none_template,
            handle_not_in_data_template=_deserialize_handle_not_in_data_template if field.required or has_default else '',
            validate_result = _deserialize_validate_result_template if field.validators else ''
        )

        if field.required:
            template.substitute_indented(handle_not_in_data=_deserialize_required_template)
        elif has_default:
            default_key = self._default_key(field.load_default)
            template.substitute_indented(handle_not_in_data=self.set_result(context, default_key))
            if callable(field.load_default):
                encoded_field.locals[default_key] = (field.load_default(), f'{context.stacks.object}.load_default()')
            else:
                encoded_field.locals[default_key] = (field.load_default, f'{context.stacks.object}.load_default')
        
        template.safe_substitute(
            field=context.stacks.object,
            data_key=context.stacks.data_key,
            data=context.stacks.data,
            value=value,
            input_value=context.stacks.value,
            result=context.stacks.result,
        )

        template.substitute_indented(encoded_deserialize=encoded_field.code)
        encoded_field.code = str(template)
        return encoded_field

    def encode_serialize(self, field: _F, context: CompileContext) -> EncodedReturn:
        has_obj_key = context.stacks.get('obj_key')
        has_default = field.dump_default is not None and field.dump_default != missing

        if not field._CHECK_ATTRIBUTE:
            with context.stacks.scope(DeserializeArgs(value='None')):
                return self._encode_serialize(field, context)

        value = f'value_{context.stacks.scope_counter}'
        with context.stacks.scope(DeserializeArgs(value=value)):
            encoded_field = self._encode_serialize(field, context)

            template = Template(_serialize_check_attribute_template)
            template.substitute_indented(
                load_default = _serialize_load_default_template if has_default else ''
            )

            if has_default:
                default_key = self._default_key(field.load_default)
                template.safe_substitute(default=default_key)
                if callable(field.load_default):
                    encoded_field.locals[default_key] = (str(field.load_default()), f'{context.stacks.object}.dump_default()')
                else:
                    encoded_field.locals[default_key] = (str(field.load_default), f'{context.stacks.object}.dump_default')

        template.safe_substitute(value=value,
                                 input_value=context.stacks.value)

        template.substitute_indented(encoded_serialize=encoded_field.code)

        encoded_field.locals['missing'] = (missing, 'from marshmallow.utils import missing')
        encoded_field.code = str(template)
        return encoded_field


class GeneralFieldEncoder(FieldEncoder[Field]):
    def _encode_deserialize(self, field: Field, context: CompileContext) -> EncodedReturn:
        return EncodedReturn(code=self.set_result(context, f'{context.stacks.object}.deserialize({context.stacks.value}, "{context.stacks.data_key}", {context.stacks.data}, partial={context.stacks.partial})'))

    def _encode_serialize(self, field: Field, context: CompileContext) -> EncodedReturn:
        return EncodedReturn(code=self.set_result(context, f'{context.stacks.object}._serialize({context.stacks.value}, "{context.stacks.obj_key}", {context.stacks.obj})'))


visitor.register_field_fallback_encoder(GeneralFieldEncoder)
