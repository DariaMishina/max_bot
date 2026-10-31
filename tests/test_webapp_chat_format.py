from html import unescape
import re
import unittest
import xml.etree.ElementTree as ET
from main.webapp_chat_format import chat_message_chunks


class ChatFormatTests(unittest.TestCase):
    def test_headings_for_all_three_schemas(self):
        for labels in [('Прошлое','Настоящее','Будущее'),('Ситуация','Возможность','Совет'),('Ваши чувства','Динамика отношений','Совет')]:
            text='Ваш расклад\n\nВопрос\n\n'+'\n\n'.join(label+': Карта\nОбычный текст.' for label in labels)+'\n\nОбщее толкование:\nИтоговый текст.'
            result=''.join(chat_message_chunks(text,labels))
            for label in labels:
                self.assertIn('<b>'+label+'</b>:', result)
            self.assertIn('<b>Общее толкование</b>:',result)
            self.assertNotIn('<b>Обычный текст.',result)

    def test_html_from_question_and_model_is_escaped(self):
        result=''.join(chat_message_chunks('Ваш расклад\n\n<b>Вопрос</b> & <script>alert(1)</script>'))
        self.assertIn('&lt;script&gt;', result)
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;b&gt;Вопрос&lt;/b&gt;',result)

    def test_long_escaped_text_has_balanced_bounded_chunks(self):
        text='Ваш расклад\n\n' + ('Вопрос <&> и ответ. ' * 1300)
        chunks=chat_message_chunks(text)
        self.assertGreater(len(chunks),1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk),3800)
            ET.fromstring('<root>'+chunk+'</root>')
        restored=unescape(re.sub(r'</?b>','',''.join(chunks)))
        self.assertEqual(restored,text)

    def test_markdown_does_not_make_body_bold(self):
        result=''.join(chat_message_chunks('Совет:\n**Обычный текст целиком.**'))
        self.assertEqual(result,'<b>Совет</b>:\nОбычный текст целиком.')
