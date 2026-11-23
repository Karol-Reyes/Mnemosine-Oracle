# Recuperación sin LLM

| Pregunta | Tipo | Evidencia | RAG: recall | RAG: cantos | GraphRAG: recall | GraphRAG: cantos |
|---|---|---|---|---|---|---|
| q01 | cruce | - | - | Il. I, Od. I, Od. VIII | - | Il. I, Od. I, Od. VIII |
| q02 | cruce | Il. XVIII, Od. VIII | 0.00 | - | 1.00 | Il. XVIII, Od. VIII |
| q03 | cruce | Od. XI | 0.00 | Il. XXI | 1.00 | Od. IV, Od. XI |
| q04 | cruce | Il. XXIV, Od. V | 0.00 | - | 0.50 | Il. XVI, Il. XXIV, Od. I, Od. XI |
| q05 | cruce | Il. I, Od. IV, Od. XI | 0.67 | Il. I, Od. I, Od. XI | 1.00 | Il. I, Od. IV, Od. XI |
| q06 | cruce | Il. III, Od. IV | 0.50 | Il. III | 1.00 | Il. III, Od. IV |
| q07 | cruce | Od. XI | 0.00 | - | 1.00 | Od. XI |
| q08 | cruce | Il. III, Od. IV | 1.00 | Il. III, Od. IV | 0.50 | Od. IV |
| q09 | hibrida | Il. XXI | 0.00 | - | 1.00 | Il. I, Il. VI, Il. XVIII, Il. XXI |
| q10 | hibrida | - | - | - | - | Od. V, Od. VIII, Od. XI |
| q11 | hibrida | Il. XXI, Od. VIII | 0.00 | - | 1.00 | Il. III, Il. XXI, Od. VIII |
| q12 | hibrida | Od. I, Od. V | 0.00 | - | 1.00 | Od. I, Od. IV, Od. V |
| q13 | hibrida | Od. I, Od. IX | 0.00 | Il. I, Il. XVI, Il. XXIV, Od. XXII | 0.50 | Od. IV, Od. V, Od. VIII, Od. IX, Od. XI |
| q14 | hibrida | Il. XVI | 0.00 | - | 1.00 | Il. I, Il. VI, Il. XVI, Il. XXII |
| q15 | hibrida | Il. I, Il. XVIII | 0.00 | Il. XVI, Il. XXIV | 0.50 | Il. XVI, Il. XVIII, Il. XXI, Il. XXIV |
| q16 | hibrida | Od. I | 1.00 | Od. I | 0.00 | Od. IV |
| q17 | control | Il. XXII | 0.00 | Il. III, Il. VI, Il. XVI, Il. XVIII | 1.00 | Il. XVI, Il. XXII, Il. XXIV |
| q18 | control | Il. XVI | 1.00 | Il. XVI, Il. XVIII | 1.00 | Il. XVI |
| q19 | control | Od. XII | 0.00 | - | 1.00 | Od. XII |
| q20 | control | Od. XII | 1.00 | Il. III, Il. VI, Il. XVI, Od. VIII, Od. XII | 1.00 | Od. I, Od. XII |

| Tipo | RAG: recall medio | GraphRAG: recall medio |
|---|---|---|
| cruce | 0.31 | 0.86 |
| hibrida | 0.14 | 0.71 |
| control | 0.50 | 1.00 |
| total | 0.29 | 0.83 |
