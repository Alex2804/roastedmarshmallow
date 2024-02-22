from .field_encoder import FieldEncoder, DeserializeArgs, SerializeArgs, CompileContext, EncodedReturn, visitor
from ..utils.template import Template

from marshmallow.fields import Mapping


_template = '''
$value = $input_value
$validation_template

$result = $mapping_type()
for $key, $val in $value.items():
    $encoded_key
    $encoded_value
$set_result
'''

_deserialize_validation_template = '''
if not isinstance($value, Mapping):
    raise $field.make_error("invalid")
'''.strip()


class MappingEncoder(FieldEncoder[Mapping]):
    @staticmethod
    def _mapping_type_key(mapping: Mapping) -> str:
        return f'{mapping.mapping_type.__name__}_{abs(hash(mapping.mapping_type))}'

    def _encode(self, mapping: Mapping, context: CompileContext, visitor_fct, data_or_obj_key: str,
                validate: bool) -> EncodedReturn:
        encoded = []
        mapping_type_key = self._mapping_type_key(mapping)
        key = f'key_{context.stacks.scope_counter}'
        processed_key = f'evaluated_key_{context.stacks.scope_counter}'
        val = f'val_{context.stacks.scope_counter}'
        result = f'result_{context.stacks.scope_counter}'

        if not mapping_type_key and not mapping.mapping_type:
            template = Template(_deserialize_validation_template)
            template.template += '\n' + self.set_result(context, f'{mapping_type_key}({context.stacks.value})')
        else:
            if mapping.key_field is not None:
                with context.stacks.scope({data_or_obj_key: None},
                                          object=f'{context.stacks.object}.key_field',
                                          result=processed_key,
                                          set_result=None,
                                          value=key,
                                          data_key=None):
                    encoded_key = visitor_fct(mapping.key_field, context)
                    encoded.append(encoded_key)
            else:
                encoded_key = EncodedReturn(code='')
                processed_key = key

            if mapping.value_field is not None:
                with context.stacks.scope({data_or_obj_key: None},
                                          object=f'{context.stacks.object}.value_field',
                                          result=f'{result}[{processed_key}]',
                                          set_result=None,
                                          value=val,
                                          data_key=None):
                    encoded_value = visitor_fct(mapping.value_field, context)
                    encoded.append(encoded_value)
            else:
                encoded_value = EncodedReturn(code=f'{result}[{processed_key}] = {val}')

            template = Template(_template)
            template.substitute_indented(
                validation_template=_deserialize_validation_template if validate else '',
                encoded_key=encoded_key.code,
                encoded_value=encoded_value.code
            )

        template.safe_substitute(field=context.stacks.object,
                                 input_value=context.stacks.value,
                                 value=f'value_{context.stacks.scope_counter}',
                                 result=result,
                                 mapping_type=mapping_type_key,
                                 key=key,
                                 val=val)
        template.substitute_indented(set_result=self.set_result(context, result))

        return EncodedReturn(code=str(template),
                             locals_={mapping_type_key: (mapping.mapping_type, mapping.mapping_type.__name__)},
                             encoded_returns=encoded)

    def _encode_deserialize(self, mapping: Mapping, context: CompileContext) -> EncodedReturn:
        return self._encode(mapping, context, visitor.deserialize, 'data_key', context.flags.validate)

    def _encode_serialize(self, mapping: Mapping, context: CompileContext) -> EncodedReturn:
        return self._encode(mapping, context, visitor.serialize, 'obj_key', False)


visitor.register_encoder(MappingEncoder)
