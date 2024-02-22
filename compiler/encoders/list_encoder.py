from marshmallow.utils import is_collection

from .field_encoder import FieldEncoder, DeserializeArgs, SerializeArgs, CompileContext, EncodedReturn, visitor
from ..utils.template import Template

from marshmallow.fields import List


_template = '''
$validation_template
$result = []
for $each in $value:
    $encoded_inner
$set_result
'''.strip()

_deserialize_validation_template = '''
if not is_collection($value):
    raise $field.make_error("invalid")
'''.strip()


class ListEncoder(FieldEncoder[List]):
    def _encode_deserialize(self, lst: List, context: CompileContext) -> EncodedReturn:
        result = f'result_{context.stacks.scope_counter}'

        template = Template(_template)
        template.substitute_indented(
            validation_template=_deserialize_validation_template if context.flags.validate else '',
            set_result=self.set_result(context, result)
        )
        template.safe_substitute(field=context.stacks.object,
                                 value=context.stacks.value,
                                 result=result)

        with context.stacks.scope(DeserializeArgs(object=f'{context.stacks.object}.inner',
                                                  result=f'{result}[-1]',
                                                  set_result=lambda v: f'{result}.append({v})',
                                                  value=f'value_{context.stacks.scope_counter}',
                                                  data_key=None)):  # TODO: data_key to list index
            encoded_inner = visitor.deserialize(lst.inner, context)
            template.safe_substitute(each=context.stacks.value,
                                     processed_inner=context.stacks.result)
            template.substitute_indented(encoded_inner=encoded_inner.code)

        return EncodedReturn(code=str(template),
                             locals_={
                                 'is_collection': (is_collection, 'from extrap.marshmallow.utils import is_collection')
                             },
                             encoded_returns=[encoded_inner])

    def _encode_serialize(self, lst: List, context: CompileContext) -> EncodedReturn:
        result = f'result_{context.stacks.scope_counter}'

        template = Template(_template)
        template.substitute_indented(validation_template='',
                                     set_result=self.set_result(context, result))
        template.safe_substitute(value=context.stacks.value,
                                 result=result)

        with context.stacks.scope(SerializeArgs(object=f'{context.stacks.object}.inner',
                                                result=f'{result}[-1]',
                                                set_result=lambda v: f'{result}.append({v})',
                                                value=f'value_{context.stacks.scope_counter}',
                                                obj_key=None)):
            encoded_inner = visitor.serialize(lst.inner, context)
            template.safe_substitute(each=context.stacks.value,
                                     processed_inner=context.stacks.result)
            template.substitute_indented(encoded_inner=encoded_inner.code)

        return EncodedReturn(code=str(template), encoded_returns=[encoded_inner])


visitor.register_encoder(ListEncoder)
