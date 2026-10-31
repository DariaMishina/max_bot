# Экран результата · 0.9.1-test · 31 октября 2026

Итерация только экрана результата и находящихся на нём уточнений. Остальные экраны
не переводятся на этот стиль до визуальной приёмки владельцем. APK:
`android/app/build/outputs/apk/debug/tarot-sphere-test-0.9.1.apk` (11).

Новые ресурсы встроены локально: `reading_botanical_paper.png` и
`reading_paper_texture.png` в `android/app/src/main/res/drawable-nodpi/`.
Ботаника — декоративный фон; текст, рамки, карты, форма и кнопки — реальные
Compose-компоненты. Текстура листа повторяется без растягивания по длине ответа.
Колода не заменялась. Шрифт Cormorant Garamond встроен с кириллицей и весами
400/500/600/700; лицензия SIL OFL находится в assets/licenses/OFL-CormorantGaramond.txt.
Источник: https://github.com/google/fonts/tree/main/ofl/cormorantgaramond

PNG рядом — реальные скриншоты Android 15 ARM64, а не генерация или HTML-макет.
Они сняты с `ReadingContent` через debug-only `ReadingReviewActivity` с локальными
демонстрационными данными. Демо использует текущую колоду и не отправляет вопросы.
Нижняя подпись «Демо» относится только к проверочному контейнеру; в приложении
сохраняется обычная навигация. Проверены 360/412 dp, 320 dp с шрифтом 200%,
длинный вопрос, прокрутка длинного ответа и поле уточнения с клавиатурой.
Полная регрессия аккаунта/сети/оплат и TalkBack в эту локальную проверку не входят.

Повторить проверку (только debug APK):

```bash
adb shell am start -n ru.tarotsphere.app.test/ru.tarotsphere.app.ReadingReviewActivity
# Длинный вопрос и ответ:
adb shell am start -n ru.tarotsphere.app.test/ru.tarotsphere.app.ReadingReviewActivity --ez long_text true
```

Тестовая Activity, демонстрационные данные и копии трёх карт находятся только в
`src/debug` и не попадают в release. Обычный запуск APK открывает приложение,
а не демонстрацию. Для пользовательской проверки откройте любой расклад из истории.

## Генерация ресурсов

Использован встроенный imagegen, две генерации. Референс первой —
`docs/design/rustore-aso-v1/01-result.jpg`, только для стилистики.

### Промпт ботанической бумаги

Use case: stylized-concept. Create a production background illustration asset for a native Android tarot reading screen, portrait 1024x1536. The supplied image is STYLE REFERENCE ONLY, not an edit target. Reproduce the exquisite vintage botanical engraved watercolor feel: muted olive leaves with intricate veins, slender ochre stems, tiny golden buds and two small ivory flowers, on softly fibrous warm ivory handmade paper. Composition: decorative foliage confined to outermost 8% left/right edges, richer at top corners (top 18%) and bottom corners. Central 82% of the entire image must be EMPTY warm pale cream paper for live UI text. Very subtle gold speckles, no prominent stars in center. Background color close to #F6EFDF, center nearly uniform to blend with matching native surfaces. Elegant antique book endpaper, soft natural material, finely detailed but restrained. NO text, letters, numbers, cards, boxes, frames, panels, buttons, logos, screenshots, UI or mockup. This is ONLY a decorative botanical paper background; all UI will be built separately. Avoid heavy dark stains, brown aged edges or crude vector leaves. Reference botanical quality and quiet luminous cream paper, not the reference screen content.

### Промпт фактуры листа

Use case: stylized-concept. Production material texture for a native reading interface: an evenly lit square sheet of luminous warm ivory handmade cotton paper, color close to #FFF9EE. Very subtle delicate paper fibers, tiny faint irregular warm gold flecks, refined printed-book paper. Straight-on perfectly flat scan, almost uniform, high readability for dark text overlaid later. No visible objects, folds, border, vignette, stains, shadows, gradients, illustrations, text, symbols or lettering. Extremely subtle organic texture, only about 3% contrast. Full bleed square 1024x1024.
