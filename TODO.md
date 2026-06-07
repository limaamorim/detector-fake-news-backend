# FakeCheck AI - TODO (Imagem - redução de falsos positivos)

## Planejado
- [x] Ajustar `calcular_score_imagem()` em `backend/app/services/scoring_service.py` para aplicar baseline e remover vieses estruturais que derrubam scores de imagens simples.

- [x] Refinar prompt em `backend/app/services/ai_service.py` para não considerar ausência de fonte/OCR como evidência de falsidade e para tratar headlines simples com evidência moderada.

- [x] Melhorar preprocessing OCR e normalização de texto em `backend/app/services/image_analyzer.py` (grayscale+contraste+binarização; correção de erros comuns e normalização de acentos).

- [x] Validar rapidamente com exemplos de OCR/headline e checar que classificação não fica mais em "Possível Desinformação" para casos plausíveis.


